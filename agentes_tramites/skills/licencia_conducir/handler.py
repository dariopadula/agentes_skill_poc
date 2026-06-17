from skills.licencia_conducir.graph import run_graph


def handle(
    text: str,
    current_fields: dict[str, object],
    history: list[dict[str, str]] | None = None,
) -> dict:
    """Adapta la salida de LangGraph al contrato común de las skills."""
    result = run_graph(text, current_fields, history or [])
    return {
        "status": result["status"],
        "question": result.get("question"),
        "answer": result.get("answer"),
        "state_updates": result.get("state_updates", {}),
        "terminal_leaf_id": result.get("terminal_leaf_id"),
        "terminal_document": result.get("terminal_document"),
    }
