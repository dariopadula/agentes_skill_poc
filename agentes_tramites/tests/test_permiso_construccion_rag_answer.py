import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from skills.permiso_construccion.rag_answer import build_prompt, generate_answer


ARTICLE = {
    "score": 0.87,
    "numero": "D.3187",
    "texto": "La dimensión de esa ochava será de cinco metros.",
    "metadata": {
        "url": "https://normativa.montevideo.gub.uy/articulo/77702",
        "fuentes": [
            {
                "nombre": "OM de 22.06.1931",
                "referencia": "art. 2",
            }
        ],
    },
}


class PermisoConstruccionRAGAnswerTests(unittest.TestCase):
    def test_prompt_includes_question_articles_and_sources(self) -> None:
        prompt = build_prompt(
            "¿Qué dimensión mínima debe tener una ochava?",
            [ARTICLE],
            {"tema": "ochavas"},
        )

        self.assertIn("Tema activo: ochavas", prompt)
        self.assertIn("Artículo D.3187", prompt)
        self.assertIn("cinco metros", prompt)
        self.assertIn("https://normativa.montevideo.gub.uy/articulo/77702", prompt)
        self.assertIn("OM de 22.06.1931", prompt)
        self.assertIn("Respuesta directa", prompt)
        self.assertIn("Evitá enumerar todos los escenarios", prompt)

    def test_generate_answer_uses_document_model_without_temperature(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="La ochava debe tener cinco metros según D.3187."
                    )
                )
            ]
        )

        with (
            patch(
                "skills.permiso_construccion.rag_answer.build_llm_client",
                return_value=client,
            ),
            patch(
                "skills.permiso_construccion.rag_answer.get_model",
                return_value="document-local",
            ),
        ):
            answer = generate_answer(
                "¿Qué dimensión mínima debe tener una ochava?",
                [ARTICLE],
                {"tema": "ochavas"},
            )

        self.assertIn("cinco metros", answer)
        call_arguments = client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_arguments["model"], "document-local")
        self.assertNotIn("temperature", call_arguments)


if __name__ == "__main__":
    unittest.main()
