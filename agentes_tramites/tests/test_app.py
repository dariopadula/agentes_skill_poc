import unittest
from unittest.mock import patch

from app import document_model_description, router_description
from routers import FallbackRouter, KeywordRouter, LLMRouter


class AppDescriptionTests(unittest.TestCase):
    def test_document_description_includes_provider_and_model(self) -> None:
        with (
            patch("app.get_provider_name", return_value="OpenAI"),
            patch("app.get_model", return_value="gpt-5-mini"),
        ):
            description = document_model_description()

        self.assertEqual(description, "OpenAI (gpt-5-mini)")

    def test_llm_router_description_includes_provider_and_model(self) -> None:
        with (
            patch("routers.build_llm_client"),
            patch("routers.get_model", return_value="gpt-4.1-mini"),
            patch("routers.get_llm_provider", return_value="openai"),
            patch("routers.get_provider_name", return_value="OpenAI"),
        ):
            primary = LLMRouter({})

        router = FallbackRouter(primary=primary, fallback=KeywordRouter({}))

        self.assertEqual(
            router_description(router),
            "OpenAI (gpt-4.1-mini) con fallback local",
        )


if __name__ == "__main__":
    unittest.main()
