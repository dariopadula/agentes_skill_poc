from routers import Router, build_router
from skill_registry import SkillRegistry
from state import ConversationState


class Orchestrator:
    """Selecciona una skill y delega en ella la conversación."""

    def __init__(self, registry: SkillRegistry, router: Router | None = None) -> None:
        self.registry = registry
        self.router = router or build_router(registry.routing_catalog())

    def handle(self, text: str, state: ConversationState) -> dict:
        state.add_message("user", text)

        if state.active_skill is None:
            decision = self.router.route(text)
            if decision.skill is None:
                return {
                    "status": "not_found",
                    "question": None,
                    "answer": (
                        "No pude identificar el trámite. Skills disponibles: "
                        f"{', '.join(self.registry.names())}."
                    ),
                    "state_updates": {},
                }

            state.active_skill = decision.skill
            state.update_fields(decision.extracted_fields)

        skill = self.registry.get(state.active_skill)
        result = skill.handler(text, state.fields, state.history)
        state.update_fields(result.get("state_updates", {}))

        # Tanto el router local como el LLM respetan este contrato:
        # Ejemplo:
        # {
        #   "skill": "licencia_conducir",
        #   "confidence": 0.92,
        #   "extracted_fields": {
        #       "tramite": "renovacion",
        #       "categoria": "A",
        #       "edad": null
        #   }
        # }
        # Por eso las skills no necesitan saber qué router fue utilizado.

        if result.get("question"):
            state.add_message("assistant", result["question"])
        elif result.get("answer"):
            state.add_message("assistant", result["answer"])

        return result
