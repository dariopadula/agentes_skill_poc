import unittest
from unittest.mock import patch

from skills.licencia_conducir.category_inference import CategoryInference
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
    def test_explicit_category_does_not_use_llm_inference(self) -> None:
        fields: dict[str, object] = {
            "tramite": "renovacion",
            "pending_field": "categoria",
        }

        with patch("skills.licencia_conducir.graph.infer_category") as inference:
            result = handle("G2", fields)

        inference.assert_not_called()
        self.assertEqual(result["status"], "need_input")
        self.assertEqual(result["state_updates"]["categoria"], "G2")
        self.assertEqual(result["state_updates"]["grupo_categoria"], "amateur")
        self.assertEqual(result["state_updates"]["pending_field"], "edad")

    @patch(
        "skills.licencia_conducir.graph.infer_category",
        return_value=CategoryInference(
            status="detected",
            categoria_inferida="G3",
            grupo_categoria_inferido="profesional",
            confidence="alta",
            reason="el usuario menciono una moto de 900 cc",
        ),
    )
    def test_natural_category_description_requires_confirmation(self, inference) -> None:
        fields: dict[str, object] = {"tramite": "renovacion"}

        first = handle("quiero renovar la licencia", fields)
        fields.update(first["state_updates"])

        second = handle("moto de 900 cc", fields)
        fields.update(second["state_updates"])

        inference.assert_called_once_with("moto de 900 cc")
        self.assertEqual(second["status"], "need_input")
        self.assertIn("categoria G3", second["question"])
        self.assertEqual(fields["phase"], "category_inference_confirmation")
        self.assertEqual(fields["categoria_inferida"], "G3")
        self.assertNotIn("categoria", fields)

        third = handle("si", fields)

        self.assertEqual(third["status"], "need_input")
        self.assertEqual(third["state_updates"]["categoria"], "G3")
        self.assertEqual(third["state_updates"]["grupo_categoria"], "profesional")
        self.assertEqual(third["state_updates"]["pending_field"], "edad")

    @patch(
        "skills.licencia_conducir.graph.infer_category",
        return_value=CategoryInference(
            status="detected",
            categoria_inferida="E",
            grupo_categoria_inferido="profesional",
            confidence="alta",
            reason="el usuario menciono taxi",
        ),
    )
    def test_rejected_category_inference_asks_again(self, _inference) -> None:
        fields: dict[str, object] = {
            "tramite": "renovacion",
            "pending_field": "categoria",
        }

        first = handle("taxi", fields)
        fields.update(first["state_updates"])
        second = handle("no", fields)

        self.assertEqual(second["status"], "need_input")
        self.assertIn("describime con mas detalle", second["question"])
        self.assertEqual(second["state_updates"]["phase"], "collect")
        self.assertEqual(second["state_updates"]["pending_field"], "categoria")
        self.assertEqual(second["state_updates"]["categoria_inferida"], "")

    @patch(
        "skills.licencia_conducir.graph.infer_category",
        return_value=CategoryInference(
            status="need_input",
            confidence="media",
            question="¿La moto es de hasta 50 cc, hasta 200 cc o de mayor cilindrada?",
            reason="La palabra moto requiere cilindrada.",
        ),
    )
    def test_ambiguous_category_description_asks_llm_question(self, _inference) -> None:
        fields: dict[str, object] = {
            "tramite": "renovacion",
            "pending_field": "categoria",
        }

        result = handle("moto", fields)

        self.assertEqual(result["status"], "need_input")
        self.assertIn("moto", result["question"])
        self.assertEqual(result["state_updates"]["pending_field"], "categoria")
        self.assertNotIn("categoria", result["state_updates"])

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
