import os

from config import load_environment

# Debe ejecutarse antes de construir el router.
ENV_PATH = load_environment()

from llm_client import get_model, get_provider_name
from orchestrator import Orchestrator
from routers import FallbackRouter, LLMRouter
from skill_registry import build_default_registry
from state import ConversationState


def router_description(router: object) -> str:
    if isinstance(router, FallbackRouter):
        primary = router.primary
        if isinstance(primary, LLMRouter):
            return (
                f"{primary.provider_name} ({primary.model}) "
                "con fallback local"
            )
        return "router principal con fallback local"
    return "palabras clave (local)"


def document_model_description() -> str:
    return f"{get_provider_name()} ({get_model('document')})"


def main() -> None:
    """Ejecuta una conversación simple por consola."""
    orchestrator = Orchestrator(build_default_registry())
    state = ConversationState()

    print("Asistente de trámites (PoC)")
    print(f"Modo configurado: {os.getenv('ROUTER_MODE', 'keywords')}")
    print(f"Router efectivo: {router_description(orchestrator.router)}")
    print(f"Modelo documental: {document_model_description()}")
    print(
        "Escribí tu consulta. Usá 'finalizar' para cerrar el trámite actual, "
        "'nueva consulta' para empezar otro o 'salir' para terminar.\n"
    )

    while True:
        try:
            user_text = input("Vos: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not user_text:
            continue
        if user_text.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego.")
            break
        if user_text.lower() in {"finalizar", "fin"}:
            state.reset()
            print("Asistente: Trámite finalizado. Podés iniciar otra consulta.\n")
            continue
        if user_text.lower() == "nueva consulta":
            state.reset()
            print("Asistente: Estado reiniciado. ¿Qué trámite necesitás?\n")
            continue

        result = orchestrator.handle(user_text, state)

        if isinstance(orchestrator.router, FallbackRouter):
            router_error = orchestrator.router.consume_last_error()
        else:
            router_error = None

        if router_error:
            print(
                "Diagnóstico: el proveedor LLM falló; se utilizó el router local. "
                f"Detalle: {router_error}\n"
            )

        if result["status"] == "need_input":
            print(f"Asistente: {result['question']}\n")
        elif result["status"] == "final":
            print(f"Asistente:\n{result['answer']}\n")
            state.reset()
        elif result["status"] == "document_qa":
            print(f"Asistente:\n{result['answer']}\n")
        else:
            print(f"Asistente: {result['answer']}\n")


if __name__ == "__main__":
    main()
