from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from skills.licencia_conducir.document_qa import (
    answer_document_question,
    generate_initial_summary,
)
from skills.licencia_conducir.matcher import (
    extract_fields,
    load_terminal_document,
    load_terminal_document_by_name,
    match_leaf,
    normalize_fields,
)


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
    return {"route": "document_qa" if phase == "document_qa" else "collect"}


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
        return {
            "route": "terminal",
            "terminal_leaf_id": result.leaf["id"],
            "terminal_document": result.leaf["archivo_md"],
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


def build_graph():
    builder = StateGraph(LicenseGraphState)
    builder.add_node("phase", phase_node)
    builder.add_node("extract", extract_node)
    builder.add_node("decide", decide_node)
    builder.add_node("ask", ask_node)
    builder.add_node("terminal", terminal_node)
    builder.add_node("document_qa", document_qa_node)
    builder.add_node("unsupported", unsupported_node)

    builder.add_edge(START, "phase")
    builder.add_conditional_edges(
        "phase",
        route_after_phase,
        {
            "collect": "extract",
            "document_qa": "document_qa",
        },
    )
    builder.add_edge("extract", "decide")
    builder.add_conditional_edges(
        "decide",
        route_after_decision,
        {
            "ask": "ask",
            "terminal": "terminal",
            "unsupported": "unsupported",
        },
    )
    builder.add_edge("ask", END)
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
