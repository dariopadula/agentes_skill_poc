import unittest

from orchestrator import Orchestrator
from routers import RouteDecision
from skill_registry import build_default_registry
from state import ConversationState


class StaticRouter:
    def __init__(self, decision: RouteDecision) -> None:
        self.decision = decision

    def route(self, text: str) -> RouteDecision:
        return self.decision


class OrchestratorConfirmationTests(unittest.TestCase):
    def test_ambiguous_skill_requires_confirmation(self) -> None:
        orchestrator = Orchestrator(build_default_registry())
        state = ConversationState()

        result = orchestrator.handle("quiero sacar la libreta", state)

        self.assertEqual(result["status"], "need_input")
        self.assertIsNone(state.active_skill)
        self.assertEqual(state.pending_skill, "licencia_conducir")
        self.assertIn("Licencia de conducir", result["question"])

    def test_confirmed_pending_skill_is_activated(self) -> None:
        orchestrator = Orchestrator(build_default_registry())
        state = ConversationState()

        orchestrator.handle("quiero sacar la libreta", state)
        result = orchestrator.handle("si", state)

        self.assertEqual(result["status"], "need_input")
        self.assertEqual(state.active_skill, "licencia_conducir")
        self.assertIsNone(state.pending_skill)

    def test_clear_license_query_does_not_require_skill_confirmation(self) -> None:
        orchestrator = Orchestrator(build_default_registry())
        state = ConversationState()

        result = orchestrator.handle("quiero sacar la libreta de conducir", state)

        self.assertEqual(result["status"], "need_input")
        self.assertEqual(state.active_skill, "licencia_conducir")
        self.assertIsNone(state.pending_skill)

    def test_clear_license_context_overrides_llm_confirmation(self) -> None:
        router = StaticRouter(
            RouteDecision(
                skill="licencia_conducir",
                confidence=0.8,
                needs_confirmation=True,
            )
        )
        orchestrator = Orchestrator(build_default_registry(), router=router)
        state = ConversationState()

        result = orchestrator.handle("quiero sacar la libreta de conducir", state)

        self.assertEqual(result["status"], "need_input")
        self.assertEqual(state.active_skill, "licencia_conducir")
        self.assertIsNone(state.pending_skill)

    def test_confirmed_ambiguous_query_reuses_original_text(self) -> None:
        orchestrator = Orchestrator(build_default_registry())
        state = ConversationState()

        first = orchestrator.handle("perdon, quiero renovar la libreta", state)
        second = orchestrator.handle("si", state)

        self.assertEqual(first["status"], "need_input")
        self.assertEqual(state.active_skill, "licencia_conducir")
        self.assertEqual(second["status"], "need_input")
        self.assertIn("categor", second["question"].lower())
        self.assertEqual(state.fields["tramite"], "renovacion")

    def test_weak_first_time_inference_from_router_is_removed(self) -> None:
        router = StaticRouter(
            RouteDecision(
                skill="licencia_conducir",
                confidence=0.9,
                extracted_fields={"tramite": "primera_vez"},
                needs_confirmation=False,
            )
        )
        orchestrator = Orchestrator(build_default_registry(), router=router)
        state = ConversationState()

        result = orchestrator.handle("quiero sacar la licencia de conducir", state)

        self.assertEqual(result["status"], "need_input")
        self.assertIn("tr", result["question"].lower())
        self.assertNotIn("tramite", state.fields)

    def test_reset_clears_pending_skill_text(self) -> None:
        state = ConversationState()
        state.pending_skill = "licencia_conducir"
        state.pending_skill_text = "quiero renovar la libreta"

        state.reset()

        self.assertIsNone(state.pending_skill)
        self.assertIsNone(state.pending_skill_text)


if __name__ == "__main__":
    unittest.main()
