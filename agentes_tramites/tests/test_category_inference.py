import unittest

from pydantic import ValidationError

from skills.licencia_conducir.category_inference import (
    CategoryInferenceResult,
    parse_category_inference,
)


class CategoryInferenceTests(unittest.TestCase):
    def test_parse_detected_category(self) -> None:
        result = parse_category_inference(
            """
            {
              "status": "detected",
              "categoria_inferida": "G3",
              "grupo_categoria_inferido": "profesional",
              "confidence": "alta",
              "question": null,
              "reason": "El usuario indico una moto de 900 cc."
            }
            """
        )

        self.assertEqual(result.status, "detected")
        self.assertEqual(result.categoria_inferida, "G3")
        self.assertEqual(result.grupo_categoria_inferido, "profesional")

    def test_detected_category_requires_matching_group(self) -> None:
        with self.assertRaises(ValidationError):
            CategoryInferenceResult.model_validate(
                {
                    "status": "detected",
                    "categoria_inferida": "G3",
                    "grupo_categoria_inferido": "amateur",
                    "confidence": "alta",
                    "question": None,
                    "reason": "Grupo incorrecto.",
                }
            )

    def test_need_input_requires_question(self) -> None:
        with self.assertRaises(ValidationError):
            CategoryInferenceResult.model_validate(
                {
                    "status": "need_input",
                    "categoria_inferida": None,
                    "grupo_categoria_inferido": None,
                    "confidence": "media",
                    "question": None,
                    "reason": "Falta cilindrada.",
                }
            )


if __name__ == "__main__":
    unittest.main()
