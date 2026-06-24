import unittest
from unittest.mock import patch

from skills.permiso_construccion.handler import handle


RETRIEVED_ARTICLE = {
    "score": 0.87,
    "numero": "D.3187",
    "texto": "La dimensión de esa ochava será de cinco metros.",
    "metadata": {
        "url": "https://normativa.montevideo.gub.uy/articulo/77702"
    },
}


class PermisoConstruccionHandlerTests(unittest.TestCase):
    def test_ambiguous_ochava_query_asks_for_context(self) -> None:
        result = handle("tengo que poner ochavas", {})

        self.assertEqual(result["status"], "need_input")
        self.assertIn("necesito precisar el caso", result["question"])
        self.assertEqual(result["state_updates"]["tema"], "ochavas")
        self.assertEqual(
            result["state_updates"]["contexto_pendiente"],
            ["tipo_de_situacion"],
        )

    @patch("skills.permiso_construccion.handler.generate_answer")
    @patch("skills.permiso_construccion.handler.retrieve")
    def test_specific_ochava_query_returns_rag_answer(
        self,
        retrieve_mock,
        generate_answer_mock,
    ) -> None:
        retrieve_mock.return_value = [RETRIEVED_ARTICLE]
        generate_answer_mock.return_value = (
            "La dimensión mínima surge del Artículo D.3187."
        )

        result = handle("qué casos existen para las ochavas", {})

        self.assertEqual(result["status"], "document_qa")
        self.assertIn("Artículo D.3187", result["answer"])
        self.assertEqual(result["state_updates"]["tema"], "ochavas")
        retrieve_mock.assert_called_once()
        generate_answer_mock.assert_called_once()
        generated_fields = generate_answer_mock.call_args.args[2]
        self.assertEqual(generated_fields["contexto_pendiente"], [])

    @patch("skills.permiso_construccion.handler.generate_answer")
    @patch("skills.permiso_construccion.handler.retrieve")
    def test_rag_failure_returns_retrieval_fallback(
        self,
        retrieve_mock,
        generate_answer_mock,
    ) -> None:
        retrieve_mock.return_value = [RETRIEVED_ARTICLE]
        generate_answer_mock.side_effect = RuntimeError("modelo no disponible")

        result = handle("qué dimensión mínima debe tener una ochava", {})

        self.assertEqual(result["status"], "final")
        self.assertIn("evidencia recuperada", result["answer"])
        self.assertIn("Artículo D.3187", result["answer"])

    @patch("skills.permiso_construccion.handler.generate_answer")
    @patch("skills.permiso_construccion.handler.retrieve")
    def test_direct_query_closes_after_answer(
        self,
        retrieve_mock,
        generate_answer_mock,
    ) -> None:
        retrieve_mock.return_value = [RETRIEVED_ARTICLE]
        generate_answer_mock.return_value = (
            "No corresponde ochava según el Artículo D.3189."
        )

        result = handle(
            "si mi edificacion no esta en una esquina, tengo que poner ochava?",
            {},
        )

        self.assertEqual(result["status"], "final")

    @patch("skills.permiso_construccion.handler.generate_answer")
    @patch("skills.permiso_construccion.handler.retrieve")
    def test_follow_up_query_uses_existing_topic(
        self,
        retrieve_mock,
        generate_answer_mock,
    ) -> None:
        retrieve_mock.return_value = [RETRIEVED_ARTICLE]
        generate_answer_mock.return_value = "Respuesta RAG."

        handle("cuál es la dimensión mínima", {"tema": "ochavas"})

        query = retrieve_mock.call_args.args[0]
        self.assertIn("Tema actual: ochavas", query)

    def test_unknown_topic_asks_to_confirm_supported_sample(self) -> None:
        result = handle("quiero consultar sobre retiros frontales", {})

        self.assertEqual(result["status"], "need_input")
        self.assertIn("muestra sobre ochavas", result["question"])


if __name__ == "__main__":
    unittest.main()
