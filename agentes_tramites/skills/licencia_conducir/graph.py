from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from skills.licencia_conducir.category_inference import infer_category
from skills.licencia_conducir.document_qa import (
    answer_document_question,
    generate_initial_summary,
)
from skills.licencia_conducir.matcher import (
    category_group,
    extract_fields,
    load_terminal_document,
    load_terminal_document_by_name,
    match_leaf,
    normalize_fields,
)
from skills.licencia_conducir.pathology_inference import infer_pathology
from utils.text import normalize_text


YES_WORDS = {"si", "sÃ­", "correcto", "afirmativo", "dale", "ok"}
NO_WORDS = {"no", "negativo", "incorrecto"}


class LicenseGraphState(TypedDict, total=False):
    text: str
    current_fields: dict[str, object]
    history: list[dict[str, str]]
    fields: dict[str, object]
    state_updates: dict[str, object]
    route: str
    status: str
    question: str | None
    answer: str | None
    terminal_leaf_id: str | None
    terminal_document: str | None


def phase_node(state: LicenseGraphState) -> LicenseGraphState:
    phase = state.get("current_fields", {}).get("phase")
    if phase == "document_qa":
        return {"route": "document_qa"}
    if phase == "case_confirmation":
        return {"route": "case_confirmation"}
    if phase == "category_inference_confirmation":
        return {"route": "category_inference_confirmation"}
    if phase == "pathology_inference_confirmation":
        return {"route": "pathology_inference_confirmation"}
    return {"route": "collect"}


def route_after_phase(state: LicenseGraphState) -> str:
    return state["route"]


def extract_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    updates = extract_fields(state.get("text", ""), current_fields)
    pending_field = current_fields.get("pending_field")
    if pending_field in updates:
        updates["pending_field"] = ""
    combined = normalize_fields({**current_fields, **updates})
    return {
        "fields": combined,
        "state_updates": updates,
    }


def decide_node(state: LicenseGraphState) -> LicenseGraphState:
    result = match_leaf(state["fields"])

    if result.status == "need_input":
        if (
            result.missing_field == "categoria"
            and state.get("current_fields", {}).get("pending_field") == "categoria"
        ):
            inference = infer_category(state.get("text", ""))
            if inference.status == "detected":
                question = build_category_confirmation_question(inference)
                return {
                    "route": "confirm_category",
                    "status": "need_input",
                    "question": question,
                    "answer": None,
                    "state_updates": {
                        **state.get("state_updates", {}),
                        "phase": "category_inference_confirmation",
                        "pending_field": "",
                        "categoria_inferida": inference.categoria_inferida,
                        "grupo_categoria_inferido": (
                            inference.grupo_categoria_inferido
                        ),
                        "categoria_inferencia_confianza": inference.confidence,
                        "categoria_inferencia_motivo": inference.reason,
                    },
                }

            return {
                "route": "ask",
                "status": "need_input",
                "question": inference.question or result.question,
                "answer": None,
                "state_updates": {
                    **state.get("state_updates", {}),
                    "pending_field": "categoria",
                },
            }

        if (
            result.missing_field == "patologias"
            and state.get("current_fields", {}).get("pending_field") == "patologias"
        ):
            inference = infer_pathology(state.get("text", ""))
            if inference.status == "detected":
                question = build_pathology_confirmation_question(inference)
                return {
                    "route": "confirm_pathology",
                    "status": "need_input",
                    "question": question,
                    "answer": None,
                    "state_updates": {
                        **state.get("state_updates", {}),
                        "phase": "pathology_inference_confirmation",
                        "pending_field": "",
                        "patologias_inferidas": inference.patologias_inferidas,
                        "codigos_patologias_inferidos": (
                            inference.codigos_patologias_inferidos
                        ),
                        "condiciones_patologias_inferidas": [
                            {
                                "codigo": condition.codigo,
                                "nombre": condition.nombre,
                                "texto_usuario": condition.texto_usuario,
                            }
                            for condition in inference.condiciones_detectadas
                        ],
                        "patologias_inferencia_confianza": inference.confidence,
                        "patologias_inferencia_motivo": inference.reason,
                    },
                }

            if inference.status == "not_detected":
                question = (
                    "No encontre eso dentro de la guia de patologias o "
                    "restricciones medicas que tengo cargada para este "
                    "tramite. Con esa informacion no lo voy a registrar como "
                    "patologia. ¿Tenes alguna otra condicion cronica, "
                    "restriccion medica o medicacion permanente que quieras "
                    "mencionar?"
                )
            else:
                question = inference.question or result.question

            return {
                "route": "ask",
                "status": "need_input",
                "question": question,
                "answer": None,
                "state_updates": {
                    **state.get("state_updates", {}),
                    "pending_field": "patologias",
                },
            }

        return {
            "route": "ask",
            "status": "need_input",
            "question": result.question,
            "answer": None,
            "state_updates": {
                **state.get("state_updates", {}),
                "pending_field": result.missing_field or "",
            },
        }

    if result.status == "matched" and result.leaf is not None:
        question = build_case_confirmation_question(
            state["fields"],
            result.leaf["titulo"],
        )
        return {
            "route": "confirm_case",
            "status": "need_input",
            "question": question,
            "answer": None,
            "terminal_leaf_id": result.leaf["id"],
            "terminal_document": result.leaf["archivo_md"],
            "state_updates": {
                **state.get("state_updates", {}),
                "phase": "case_confirmation",
                "pending_terminal_leaf_id": result.leaf["id"],
                "pending_terminal_document": result.leaf["archivo_md"],
            },
        }

    return {
        "route": "unsupported",
        "status": "final",
        "question": None,
        "answer": (
            f"{result.reason}\n\n"
            "Esta primera versión sólo responde los casos representados en "
            "las hojas terminales extraídas del insumo."
        ),
    }


def ask_node(state: LicenseGraphState) -> LicenseGraphState:
    return {
        "status": "need_input",
        "question": state["question"],
        "answer": None,
    }


def terminal_node(state: LicenseGraphState) -> LicenseGraphState:
    result = match_leaf(state["fields"])
    if result.leaf is None:
        raise RuntimeError("El nodo terminal no recibió una hoja válida.")

    markdown = load_terminal_document(result.leaf)
    summary = generate_initial_summary(markdown)
    return {
        "status": "document_qa",
        "question": None,
        "answer": summary,
        "terminal_leaf_id": result.leaf["id"],
        "terminal_document": result.leaf["archivo_md"],
        "state_updates": {
            **state.get("state_updates", {}),
            "phase": "document_qa",
            "terminal_leaf_id": result.leaf["id"],
            "terminal_document": result.leaf["archivo_md"],
        },
    }


def confirm_case_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    if current_fields.get("phase") != "case_confirmation":
        return {
            "status": state.get("status", "need_input"),
            "question": state.get("question"),
            "answer": state.get("answer"),
            "terminal_leaf_id": state.get("terminal_leaf_id"),
            "terminal_document": state.get("terminal_document"),
            "state_updates": state.get("state_updates", {}),
        }

    confirmation = extract_confirmation(state.get("text", ""))

    if confirmation is True:
        filename = current_fields.get("pending_terminal_document")
        leaf_id = current_fields.get("pending_terminal_leaf_id")
        if not isinstance(filename, str) or not isinstance(leaf_id, str):
            return {
                "status": "final",
                "question": None,
                "answer": (
                    "La sesiÃ³n perdiÃ³ el caso pendiente de confirmaciÃ³n. "
                    "IniciÃ¡ una nueva consulta."
                ),
            }

        markdown = load_terminal_document_by_name(filename)
        summary = generate_initial_summary(markdown)
        return {
            "status": "document_qa",
            "question": None,
            "answer": summary,
            "terminal_leaf_id": leaf_id,
            "terminal_document": filename,
            "state_updates": {
                "phase": "document_qa",
                "terminal_leaf_id": leaf_id,
                "terminal_document": filename,
            },
        }

    if confirmation is False:
        return {
            "status": "need_input",
            "question": (
                "Entendido. Indicame quÃ© dato querÃ©s corregir: trÃ¡mite, "
                "categorÃ­a, edad, patologÃ­as o vigencia de la licencia."
            ),
            "answer": None,
            "state_updates": {
                "phase": "collect",
            },
        }

    return {
        "status": "need_input",
        "question": "Necesito que confirmes si el caso es correcto. RespondÃ© sÃ­ o no.",
        "answer": None,
        "state_updates": {},
    }


def confirm_category_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    if current_fields.get("phase") != "category_inference_confirmation":
        return {
            "status": state.get("status", "need_input"),
            "question": state.get("question"),
            "answer": state.get("answer"),
            "terminal_leaf_id": state.get("terminal_leaf_id"),
            "terminal_document": state.get("terminal_document"),
            "state_updates": state.get("state_updates", {}),
        }

    confirmation = extract_confirmation(state.get("text", ""))

    if confirmation is True:
        category = current_fields.get("categoria_inferida")
        group = current_fields.get("grupo_categoria_inferido")
        if not isinstance(category, str) or not isinstance(group, str):
            return {
                "status": "need_input",
                "question": (
                    "La sesion perdio la categoria inferida. Decime la "
                    "categoria A, G1, G2, B, C, D, E, F, H o G3, o describime "
                    "el vehiculo."
                ),
                "answer": None,
                "state_updates": clear_category_inference_updates(
                    phase="collect",
                    pending_field="categoria",
                ),
            }

        promoted_fields = normalize_fields({**current_fields, "categoria": category})
        result = match_leaf(promoted_fields)
        updates = clear_category_inference_updates(
            phase="collect",
            pending_field=result.missing_field or "",
        )
        updates.update(
            {
                "categoria": category,
                "grupo_categoria": group,
            }
        )

        if result.status == "need_input":
            return {
                "status": "need_input",
                "question": result.question,
                "answer": None,
                "state_updates": updates,
            }

        if result.status == "matched" and result.leaf is not None:
            updates.update(
                {
                    "phase": "case_confirmation",
                    "pending_terminal_leaf_id": result.leaf["id"],
                    "pending_terminal_document": result.leaf["archivo_md"],
                }
            )
            return {
                "status": "need_input",
                "question": build_case_confirmation_question(
                    promoted_fields,
                    result.leaf["titulo"],
                ),
                "answer": None,
                "terminal_leaf_id": result.leaf["id"],
                "terminal_document": result.leaf["archivo_md"],
                "state_updates": updates,
            }

        return {
            "status": "final",
            "question": None,
            "answer": (
                f"{result.reason}\n\n"
                "Esta primera version solo responde los casos representados "
                "en las hojas terminales extraidas del insumo."
            ),
            "state_updates": updates,
        }

    if confirmation is False:
        return {
            "status": "need_input",
            "question": (
                "Entendido. Decime la categoria A, G1, G2, B, C, D, E, F, H "
                "o G3, o describime con mas detalle el vehiculo que queres "
                "manejar."
            ),
            "answer": None,
            "state_updates": clear_category_inference_updates(
                phase="collect",
                pending_field="categoria",
            ),
        }

    return {
        "status": "need_input",
        "question": (
            "Necesito que confirmes si la categoria inferida es correcta. "
            "Responde si o no."
        ),
        "answer": None,
        "state_updates": {},
    }


def confirm_pathology_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    if current_fields.get("phase") != "pathology_inference_confirmation":
        return {
            "status": state.get("status", "need_input"),
            "question": state.get("question"),
            "answer": state.get("answer"),
            "terminal_leaf_id": state.get("terminal_leaf_id"),
            "terminal_document": state.get("terminal_document"),
            "state_updates": state.get("state_updates", {}),
        }

    confirmation = extract_confirmation(state.get("text", ""))

    if confirmation is True:
        promoted_fields = normalize_fields({**current_fields, "patologias": True})
        result = match_leaf(promoted_fields)
        updates = clear_pathology_inference_updates(
            phase="collect",
            pending_field=result.missing_field or "",
        )
        updates.update(
            {
                "patologias": True,
                "codigos_patologias": current_fields.get(
                    "codigos_patologias_inferidos",
                    [],
                ),
                "condiciones_patologias": current_fields.get(
                    "condiciones_patologias_inferidas",
                    [],
                ),
            }
        )

        if result.status == "need_input":
            return {
                "status": "need_input",
                "question": result.question,
                "answer": None,
                "state_updates": updates,
            }

        if result.status == "matched" and result.leaf is not None:
            updates.update(
                {
                    "phase": "case_confirmation",
                    "pending_terminal_leaf_id": result.leaf["id"],
                    "pending_terminal_document": result.leaf["archivo_md"],
                }
            )
            return {
                "status": "need_input",
                "question": build_case_confirmation_question(
                    promoted_fields,
                    result.leaf["titulo"],
                ),
                "answer": None,
                "terminal_leaf_id": result.leaf["id"],
                "terminal_document": result.leaf["archivo_md"],
                "state_updates": updates,
            }

        return {
            "status": "final",
            "question": None,
            "answer": (
                f"{result.reason}\n\n"
                "Esta primera version solo responde los casos representados "
                "en las hojas terminales extraidas del insumo."
            ),
            "state_updates": updates,
        }

    if confirmation is False:
        return {
            "status": "need_input",
            "question": (
                "Entendido. Para avanzar, respondeme si tenes una patologia "
                "o restriccion medica registrada: si o no. Si no sabes si tu "
                "caso cuenta, podes describirlo con mas detalle."
            ),
            "answer": None,
            "state_updates": clear_pathology_inference_updates(
                phase="collect",
                pending_field="patologias",
            ),
        }

    return {
        "status": "need_input",
        "question": (
            "Necesito que confirmes si entendi bien la condicion mencionada. "
            "Responde si o no."
        ),
        "answer": None,
        "state_updates": {},
    }


def document_qa_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    filename = current_fields.get("terminal_document")
    if not isinstance(filename, str):
        return {
            "status": "final",
            "question": None,
            "answer": "La sesión perdió el documento terminal. Iniciá una nueva consulta.",
        }

    markdown = load_terminal_document_by_name(filename)
    answer = answer_document_question(markdown, state.get("history", []))
    return {
        "status": "document_qa",
        "question": None,
        "answer": answer,
        "terminal_leaf_id": current_fields.get("terminal_leaf_id"),
        "terminal_document": filename,
        "state_updates": {},
    }


def unsupported_node(state: LicenseGraphState) -> LicenseGraphState:
    return {
        "status": "final",
        "question": None,
        "answer": state["answer"],
    }


def route_after_decision(state: LicenseGraphState) -> str:
    return state["route"]


def extract_confirmation(text: str) -> bool | None:
    normalized = normalize_text(text)
    if normalized in YES_WORDS:
        return True
    if normalized in NO_WORDS:
        return False
    return None


def clear_category_inference_updates(
    *,
    phase: str,
    pending_field: str,
) -> dict[str, object]:
    return {
        "phase": phase,
        "pending_field": pending_field,
        "categoria_inferida": "",
        "grupo_categoria_inferido": "",
        "categoria_inferencia_confianza": "",
        "categoria_inferencia_motivo": "",
    }


def build_category_confirmation_question(inference) -> str:
    return (
        f"Entendi que corresponde a la categoria "
        f"{inference.categoria_inferida} ({inference.grupo_categoria_inferido}), "
        f"porque {inference.reason}. ¿Es correcto?"
    )


def clear_pathology_inference_updates(
    *,
    phase: str,
    pending_field: str,
) -> dict[str, object]:
    return {
        "phase": phase,
        "pending_field": pending_field,
        "patologias_inferidas": "",
        "codigos_patologias_inferidos": [],
        "condiciones_patologias_inferidas": [],
        "patologias_inferencia_confianza": "",
        "patologias_inferencia_motivo": "",
    }


def build_pathology_confirmation_question(inference) -> str:
    labels = [
        condition.nombre
        for condition in inference.condiciones_detectadas
        if condition.nombre
    ]
    if labels:
        detected = ", ".join(labels)
    else:
        detected = inference.reason or "la condicion que mencionaste"

    return (
        f"Entendi que mencionaste: {detected}. "
        "Para este tramite, eso se considera patologia o restriccion medica "
        "y lo voy a registrar como si. ¿Es correcto?"
    )


def build_case_confirmation_question(
    fields: dict[str, object],
    leaf_title: str,
) -> str:
    lines = [
        "Antes de darte los requisitos, confirmo el caso:",
        "",
        f"- Caso identificado: {leaf_title}.",
    ]

    tramite = format_tramite(fields.get("tramite"))
    if tramite:
        lines.append(f"- TrÃ¡mite: {tramite}.")

    categoria = fields.get("categoria")
    if isinstance(categoria, str):
        group = category_group(categoria)
        if group:
            lines.append(f"- CategorÃ­a: {categoria} ({group}).")
        else:
            lines.append(f"- CategorÃ­a: {categoria}.")

    edad = fields.get("edad")
    if isinstance(edad, int):
        lines.append(f"- Edad: {edad} aÃ±os.")

    if "patologias" in fields:
        value = "sÃ­" if fields["patologias"] is True else "no"
        lines.append(f"- PatologÃ­as o restricciones mÃ©dicas: {value}.")

    if "licencia_vigente" in fields:
        value = "sÃ­" if fields["licencia_vigente"] is True else "no"
        lines.append(f"- Licencia vigente: {value}.")

    lines.extend(["", "Â¿Es correcto?"])
    return "\n".join(lines)


def format_tramite(value: object) -> str | None:
    labels = {
        "primera_vez": "primera vez",
        "renovacion": "renovaciÃ³n",
        "duplicado": "duplicado",
        "homologacion": "homologaciÃ³n",
    }
    if isinstance(value, str):
        return labels.get(value, value)
    return None


def build_graph():
    builder = StateGraph(LicenseGraphState)
    builder.add_node("phase", phase_node)
    builder.add_node("extract", extract_node)
    builder.add_node("decide", decide_node)
    builder.add_node("ask", ask_node)
    builder.add_node("terminal", terminal_node)
    builder.add_node("confirm_case", confirm_case_node)
    builder.add_node("confirm_category", confirm_category_node)
    builder.add_node("confirm_pathology", confirm_pathology_node)
    builder.add_node("document_qa", document_qa_node)
    builder.add_node("unsupported", unsupported_node)

    builder.add_edge(START, "phase")
    builder.add_conditional_edges(
        "phase",
        route_after_phase,
        {
            "collect": "extract",
            "case_confirmation": "confirm_case",
            "category_inference_confirmation": "confirm_category",
            "pathology_inference_confirmation": "confirm_pathology",
            "document_qa": "document_qa",
        },
    )
    builder.add_edge("extract", "decide")
    builder.add_conditional_edges(
        "decide",
        route_after_decision,
        {
            "ask": "ask",
            "confirm_case": "confirm_case",
            "confirm_category": "confirm_category",
            "confirm_pathology": "confirm_pathology",
            "terminal": "terminal",
            "unsupported": "unsupported",
        },
    )
    builder.add_edge("ask", END)
    builder.add_edge("confirm_case", END)
    builder.add_edge("confirm_category", END)
    builder.add_edge("confirm_pathology", END)
    builder.add_edge("terminal", END)
    builder.add_edge("document_qa", END)
    builder.add_edge("unsupported", END)
    return builder.compile()


license_graph = build_graph()


def run_graph(
    text: str,
    current_fields: dict[str, object],
    history: list[dict[str, str]],
) -> LicenseGraphState:
    return license_graph.invoke(
        {
            "text": text,
            "current_fields": current_fields,
            "history": history,
        }
    )
