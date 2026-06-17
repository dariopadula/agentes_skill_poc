import os

from config import load_environment

# Debe ejecutarse antes de construir el router.
ENV_PATH = load_environment()

from orchestrator import Orchestrator
from routers import FallbackRouter, OpenAIRouter
from skill_registry import build_default_registry
from state import ConversationState


def router_description(router: object) -> str:
    if isinstance(router, FallbackRouter):
        primary = router.primary
        if isinstance(primary, OpenAIRouter):
            return f"OpenAI ({primary.model}) con fallback local"
        return "router principal con fallback local"
    return "palabras clave (local)"


def main() -> None:
    """Ejecuta una conversación simple por consola."""
    orchestrator = Orchestrator(build_default_registry())
    state = ConversationState()

    print("Asistente de trámites (PoC)")
    print(f"Modo configurado: {os.getenv('ROUTER_MODE', 'keywords')}")
    print(f"Router efectivo: {router_description(orchestrator.router)}")
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

        if (
            isinstance(orchestrator.router, FallbackRouter)
            and orchestrator.router.last_error
        ):
            print(
                "Diagnóstico: OpenAI falló; se utilizó el router local. "
                f"Detalle: {orchestrator.router.last_error}\n"
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
