import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from skills.licencia_conducir.document_qa import _call_model


class DocumentQATests(unittest.TestCase):
    def test_document_request_does_not_send_temperature(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Respuesta documental.")
                )
            ]
        )

        with (
            patch(
                "skills.licencia_conducir.document_qa.build_llm_client",
                return_value=client,
            ),
            patch(
                "skills.licencia_conducir.document_qa.get_model",
                return_value="gpt-5-mini",
            ),
        ):
            result = _call_model(
                "# Documento",
                [{"role": "user", "content": "¿Cuáles son los pasos?"}],
            )

        self.assertEqual(result, "Respuesta documental.")
        call_arguments = client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_arguments["model"], "gpt-5-mini")
        self.assertNotIn("temperature", call_arguments)


if __name__ == "__main__":
    unittest.main()
