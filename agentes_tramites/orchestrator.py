from routers import RouteDecision, Router, build_router
from skill_registry import SkillRegistry
from state import ConversationState
from utils.text import normalize_text


YES_WORDS = {"si", "sÃ­", "correcto", "afirmativo", "dale", "ok"}
NO_WORDS = {"no", "negativo", "incorrecto"}


class Orchestrator:
    """Selecciona una skill y delega en ella la conversación."""

    def __init__(self, registry: SkillRegistry, router: Router | None = None) -> None:
        self.registry = registry
        self.router = router or build_router(registry.routing_catalog())

    def handle(self, text: str, state: ConversationState) -> dict:
        state.add_message("user", text)

        if state.pending_skill is not None and state.active_skill is None:
            confirmation = _extract_confirmation(text)
            if confirmation is True:
                state.active_skill = state.pending_skill
                original_text = state.pending_skill_text or text
                state.pending_skill = None
                state.pending_skill_reason = None
                state.pending_skill_text = None
                text = original_text
            elif confirmation is False:
                state.pending_skill = None
                state.pending_skill_reason = None
                state.pending_skill_text = None
                result = {
                    "status": "not_found",
                    "question": None,
                    "answer": (
                        "Entendido. Decime con otras palabras quÃ© trÃ¡mite "
                        "necesitÃ¡s realizar."
                    ),
                    "state_updates": {},
                }
                state.add_message("assistant", result["answer"])
                return result
            else:
                skill = self.registry.get(state.pending_skill)
                result = {
                    "status": "need_input",
                    "question": (
                        f"Necesito confirmar si te referÃ­s a "
                        f"{skill.display_name}. RespondÃ© sÃ­ o no."
                    ),
                    "answer": None,
                    "state_updates": {},
                }
                state.add_message("assistant", result["question"])
                return result

        if state.active_skill is None:
            decision = self.router.route(text)
            decision = _normalize_decision(text, decision)
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

            if decision.needs_confirmation:
                skill = self.registry.get(decision.skill)
                state.pending_skill = decision.skill
                state.pending_skill_reason = decision.reason
                state.pending_skill_text = text
                result = {
                    "status": "need_input",
                    "question": (
                        f"EntendÃ­ que te referÃ­s a {skill.display_name}. "
                        "Â¿Es correcto?"
                    ),
                    "answer": None,
                    "state_updates": {},
                }
                state.add_message("assistant", result["question"])
                return result

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


def _extract_confirmation(text: str) -> bool | None:
    normalized = normalize_text(text)
    if normalized in YES_WORDS:
        return True
    if normalized in NO_WORDS:
        return False
    return None


def _normalize_decision(text: str, decision: RouteDecision) -> RouteDecision:
    if decision.skill != "licencia_conducir":
        return decision

    normalized = normalize_text(text)
    extracted_fields = dict(decision.extracted_fields)

    if _is_weak_first_time_inference(normalized, extracted_fields):
        extracted_fields.pop("tramite", None)

    needs_confirmation = decision.needs_confirmation
    reason = decision.reason
    if _has_clear_license_context(normalized):
        needs_confirmation = False
        reason = None
    elif _has_ambiguous_license_context(normalized):
        needs_confirmation = True
        reason = reason or (
            "La consulta menciona libreta, pero no confirma que sea de conducir."
        )

    return RouteDecision(
        skill=decision.skill,
        confidence=decision.confidence,
        extracted_fields=extracted_fields,
        needs_confirmation=needs_confirmation,
        reason=reason,
    )


def _has_clear_license_context(normalized_text: str) -> bool:
    return (
        "licencia de conducir" in normalized_text
        or "libreta de conducir" in normalized_text
        or "conducir" in normalized_text
        or "manejar" in normalized_text
    )


def _has_ambiguous_license_context(normalized_text: str) -> bool:
    return "libreta" in normalized_text and not _has_clear_license_context(
        normalized_text
    )


def _is_weak_first_time_inference(
    normalized_text: str,
    extracted_fields: dict[str, object],
) -> bool:
    if extracted_fields.get("tramite") != "primera_vez":
        return False

    explicit_first_time_terms = (
        "primera vez",
        "primera licencia",
        "nunca tuve licencia",
        "nunca tuve libreta",
    )
    if any(term in normalized_text for term in explicit_first_time_terms):
        return False

    weak_terms = (
        "sacar la licencia",
        "sacar licencia",
        "sacar la libreta",
        "sacar libreta",
        "obtener licencia",
    )
    return any(term in normalized_text for term in weak_terms)
