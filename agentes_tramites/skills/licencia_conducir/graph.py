from typing import TypedDict

from langgraph.graph import END, START, StateGraph

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
    return {"route": "collect"}


def route_after_phase(state: LicenseGraphState) -> str:
    return state["route"]


def extract_node(state: LicenseGraphState) -> LicenseGraphState:
    current_fields = state.get("current_fields", {})
    updates = extract_fields(state.get("text", ""), current_fields)
    combined = normalize_fields({**current_fields, **updates})
    return {
        "fields": combined,
        "state_updates": updates,
    }


def decide_node(state: LicenseGraphState) -> LicenseGraphState:
    result = match_leaf(state["fields"])

    if result.status == "need_input":
        return {
            "route": "ask",
            "status": "need_input",
            "question": result.question,
            "answer": None,
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
    builder.add_node("document_qa", document_qa_node)
    builder.add_node("unsupported", unsupported_node)

    builder.add_edge(START, "phase")
    builder.add_conditional_edges(
        "phase",
        route_after_phase,
        {
            "collect": "extract",
            "case_confirmation": "confirm_case",
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
            "terminal": "terminal",
            "unsupported": "unsupported",
        },
    )
    builder.add_edge("ask", END)
    builder.add_edge("confirm_case", END)
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
