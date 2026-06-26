import unittest
from unittest.mock import patch

from skills.licencia_conducir.handler import handle
from skills.licencia_conducir.matcher import (
    extract_fields,
    match_leaf,
    validate_terminal_assets,
)


class LicenseMatcherTests(unittest.TestCase):
    def test_terminal_assets_are_consistent(self) -> None:
        self.assertEqual(validate_terminal_assets(), [])

    def test_all_terminal_leaves(self) -> None:
        cases = {
            "licencia_primera_vez_a_hasta_74": {
                "tramite": "primera_vez",
                "categoria": "A",
                "edad": 30,
                "patologias": False,
            },
            "licencia_primera_vez_g1_g2_hasta_74": {
                "tramite": "primera_vez",
                "categoria": "G1",
                "edad": 16,
                "patologias": False,
            },
            "licencia_profesional_primera_vez": {
                "tramite": "primera_vez",
                "categoria": "C",
                "edad": 35,
                "patologias": False,
            },
            "renovacion_a_g1_g2_hasta_74_sin_patologias": {
                "tramite": "renovacion",
                "categoria": "A",
                "edad": 40,
                "patologias": False,
            },
            "renovacion_a_g1_g2_hasta_74_con_patologias": {
                "tramite": "renovacion",
                "categoria": "G2",
                "edad": 60,
                "patologias": True,
            },
            "renovacion_profesional": {
                "tramite": "renovacion",
                "categoria": "D",
                "edad": 50,
            },
            "duplicado_licencia": {
                "tramite": "duplicado",
                "licencia_vigente": True,
            },
            "homologacion_licencia_amateur": {
                "tramite": "homologacion",
                "categoria": "A",
            },
        }

        for expected_leaf, fields in cases.items():
            with self.subTest(expected_leaf=expected_leaf):
                result = match_leaf(fields)
                self.assertEqual(result.status, "matched")
                self.assertEqual(result.leaf["id"], expected_leaf)

    def test_uncovered_combination_is_not_forced(self) -> None:
        result = match_leaf(
            {
                "tramite": "renovacion",
                "categoria": "A",
                "edad": 80,
                "patologias": False,
            }
        )
        self.assertEqual(result.status, "unsupported")

    def test_sacar_licencia_does_not_imply_first_time(self) -> None:
        updates = extract_fields("quiero sacar la licencia de conducir", {})

        self.assertNotIn("tramite", updates)

    def test_explicit_first_time_is_detected(self) -> None:
        updates = extract_fields("quiero licencia por primera vez", {})

        self.assertEqual(updates["tramite"], "primera_vez")


class LicenseGraphTests(unittest.TestCase):
    @patch(
        "skills.licencia_conducir.graph.generate_initial_summary",
        return_value="Resumen inicial del trámite.",
    )
    def test_renewal_conversation_enters_document_qa(self, _summary) -> None:
        fields: dict[str, object] = {}
        history: list[dict[str, str]] = []

        for text, expected_status in (
            ("quiero renovar la libreta", "need_input"),
            ("A", "need_input"),
            ("35", "need_input"),
            ("no tengo", "need_input"),
        ):
            history.append({"role": "user", "content": text})
            result = handle(text, fields, history)
            self.assertEqual(result["status"], expected_status)
            fields.update(result["state_updates"])
            history.append(
                {
                    "role": "assistant",
                    "content": result.get("question") or result.get("answer") or "",
                }
            )

        self.assertIn("Antes de darte los requisitos", result["question"])
        self.assertEqual(fields["phase"], "case_confirmation")
        self.assertEqual(
            fields["pending_terminal_leaf_id"],
            "renovacion_a_g1_g2_hasta_74_sin_patologias",
        )

        history.append({"role": "user", "content": "si"})
        result = handle("si", fields, history)
        self.assertEqual(result["status"], "document_qa")
        self.assertEqual(
            result["terminal_leaf_id"],
            "renovacion_a_g1_g2_hasta_74_sin_patologias",
        )
        self.assertEqual(result["answer"], "Resumen inicial del trámite.")
        fields.update(result["state_updates"])
        self.assertEqual(fields["phase"], "document_qa")

    @patch(
        "skills.licencia_conducir.graph.generate_initial_summary",
        return_value="Resumen inicial.",
    )
    def test_duplicate_conversation(self, _summary) -> None:
        fields: dict[str, object] = {}
        first = handle("perdí mi licencia", fields)
        fields.update(first["state_updates"])
        second = handle("sí", fields)
        fields.update(second["state_updates"])
        third = handle("si", fields)

        self.assertEqual(first["status"], "need_input")
        self.assertEqual(second["status"], "need_input")
        self.assertIn("Antes de darte los requisitos", second["question"])
        self.assertEqual(third["status"], "document_qa")
        self.assertEqual(third["terminal_leaf_id"], "duplicado_licencia")

    @patch(
        "skills.licencia_conducir.graph.answer_document_question",
        return_value="La agenda se solicita por el canal indicado.",
    )
    def test_document_qa_uses_selected_document_and_history(self, answer_mock) -> None:
        fields = {
            "phase": "document_qa",
            "terminal_leaf_id": "renovacion_a_g1_g2_hasta_74_sin_patologias",
            "terminal_document": (
                "renovacion_a_g1_g2_hasta_74_sin_patologias.md"
            ),
        }
        history = [
            {"role": "assistant", "content": "Resumen inicial."},
            {"role": "user", "content": "¿Cómo saco hora?"},
        ]

        result = handle("¿Cómo saco hora?", fields, history)

        self.assertEqual(result["status"], "document_qa")
        self.assertEqual(
            result["answer"],
            "La agenda se solicita por el canal indicado.",
        )
        markdown, received_history = answer_mock.call_args.args
        self.assertIn("## Agenda", markdown)
        self.assertEqual(received_history, history)


if __name__ == "__main__":
    unittest.main()
