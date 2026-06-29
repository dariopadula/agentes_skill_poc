import unittest

from pydantic import ValidationError

from skills.licencia_conducir.pathology_inference import (
    PathologyInferenceResult,
    parse_pathology_inference,
)


class PathologyInferenceTests(unittest.TestCase):
    def test_parse_detected_pathology(self) -> None:
        result = parse_pathology_inference(
            """
            {
              "status": "detected",
              "patologias_inferidas": true,
              "codigos_patologias_inferidos": [2, 15],
              "condiciones_detectadas": [
                {
                  "codigo": 2,
                  "nombre": "Afecciones cardiovasculares",
                  "texto_usuario": "soy hipertenso"
                },
                {
                  "codigo": 15,
                  "nombre": "Lentes de contacto",
                  "texto_usuario": "uso lentes de contacto"
                }
              ],
              "confidence": "alta",
              "question": null,
              "reason": "El usuario menciono hipertension y lentes de contacto."
            }
            """
        )

        self.assertEqual(result.status, "detected")
        self.assertTrue(result.patologias_inferidas)
        self.assertEqual(result.codigos_patologias_inferidos, [2, 15])
        self.assertEqual(len(result.condiciones_detectadas), 2)

    def test_detected_requires_codes_and_conditions(self) -> None:
        with self.assertRaises(ValidationError):
            PathologyInferenceResult.model_validate(
                {
                    "status": "detected",
                    "patologias_inferidas": True,
                    "codigos_patologias_inferidos": [],
                    "condiciones_detectadas": [],
                    "confidence": "alta",
                    "question": None,
                    "reason": "Sin codigos.",
                }
            )

    def test_not_detected_rejects_codes(self) -> None:
        with self.assertRaises(ValidationError):
            PathologyInferenceResult.model_validate(
                {
                    "status": "not_detected",
                    "patologias_inferidas": False,
                    "codigos_patologias_inferidos": [3],
                    "condiciones_detectadas": [],
                    "confidence": "media",
                    "question": None,
                    "reason": "No corresponde.",
                }
            )

    def test_need_input_requires_question(self) -> None:
        with self.assertRaises(ValidationError):
            PathologyInferenceResult.model_validate(
                {
                    "status": "need_input",
                    "patologias_inferidas": None,
                    "codigos_patologias_inferidos": [],
                    "condiciones_detectadas": [],
                    "confidence": "media",
                    "question": None,
                    "reason": "Falta detalle.",
                }
            )


if __name__ == "__main__":
    unittest.main()
