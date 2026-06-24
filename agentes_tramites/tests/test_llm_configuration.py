import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from llm_client import (
    build_embedding_client,
    build_llm_client,
    get_embedding_provider,
    get_llm_provider,
    get_model,
    is_llm_configured,
)
from routers import FallbackRouter, KeywordRouter, LLMRouter, build_router


CATALOG = {
    "licencia_conducir": {
        "nombre": "Licencia de conducir",
        "descripcion": "Consultas sobre licencias.",
        "ejemplos_usuario": ["quiero renovar la licencia"],
        "datos_que_puede_extraer": ["tramite"],
        "cuando_usar": ["Consultas sobre licencias."],
        "palabras_clave": ["licencia"],
    }
}


class LLMConfigurationTests(unittest.TestCase):
    def tearDown(self) -> None:
        build_llm_client.cache_clear()
        build_embedding_client.cache_clear()

    def test_lmstudio_configuration_selects_models_by_role(self) -> None:
        environment = {
            "LLM_PROVIDER": "lmstudio",
            "EMBEDDING_PROVIDER": "lmstudio",
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "ROUTER_MODEL": "router-local",
            "DOCUMENT_MODEL": "document-local",
            "EMBEDDING_MODEL": "embedding-local",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(get_llm_provider(), "lmstudio")
            self.assertEqual(get_embedding_provider(), "lmstudio")
            self.assertEqual(get_model("router"), "router-local")
            self.assertEqual(get_model("document"), "document-local")
            self.assertEqual(get_model("embedding"), "embedding-local")
            self.assertTrue(is_llm_configured("router"))
            self.assertTrue(is_llm_configured("embedding"))

    def test_unknown_provider_is_rejected(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "otro"}, clear=True):
            with self.assertRaises(ValueError):
                get_llm_provider()

    def test_embedding_provider_can_differ_from_llm_provider(self) -> None:
        environment = {
            "LLM_PROVIDER": "openai",
            "EMBEDDING_PROVIDER": "lmstudio",
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "EMBEDDING_MODEL": "embedding-local",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(get_llm_provider(), "openai")
            self.assertEqual(get_embedding_provider(), "lmstudio")
            self.assertEqual(get_model("embedding"), "embedding-local")
            self.assertTrue(is_llm_configured("embedding"))

    @patch("openai.OpenAI")
    def test_factory_points_client_to_lmstudio(self, openai_mock) -> None:
        environment = {
            "LLM_PROVIDER": "lmstudio",
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "LM_STUDIO_API_KEY": "lm-studio",
        }
        with patch.dict(os.environ, environment, clear=True):
            build_llm_client()

        openai_mock.assert_called_once_with(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
        )

    @patch("openai.OpenAI")
    def test_embedding_factory_points_client_to_lmstudio(self, openai_mock) -> None:
        environment = {
            "LLM_PROVIDER": "openai",
            "EMBEDDING_PROVIDER": "lmstudio",
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "LM_STUDIO_API_KEY": "lm-studio",
        }
        with patch.dict(os.environ, environment, clear=True):
            build_embedding_client()

        openai_mock.assert_called_once_with(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
        )

    def test_keywords_mode_does_not_build_an_llm_client(self) -> None:
        with patch("routers.LLMRouter") as router_mock:
            router = build_router(CATALOG, mode="keywords")

        self.assertIsInstance(router, KeywordRouter)
        router_mock.assert_not_called()


class LLMRouterTests(unittest.TestCase):
    def test_valid_structured_result_is_converted_to_route_decision(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"skill":"licencia_conducir","confidence":0.9,'
                            '"extracted_fields":{"tramite":"renovacion",'
                            '"categoria":null,"grupo_categoria":null,'
                            '"edad":null,"patologias":null,'
                            '"licencia_vigente":null}}'
                        )
                    )
                )
            ]
        )

        with (
            patch("routers.build_llm_client", return_value=client),
            patch("routers.get_model", return_value="router-local"),
            patch("routers.get_llm_provider", return_value="lmstudio"),
            patch("routers.get_provider_name", return_value="LM Studio"),
        ):
            decision = LLMRouter(CATALOG).route("quiero renovar")

        self.assertEqual(decision.skill, "licencia_conducir")
        self.assertEqual(
            decision.extracted_fields,
            {"tramite": "renovacion"},
        )
        call_arguments = client.chat.completions.create.call_args.kwargs
        self.assertNotIn("temperature", call_arguments)

    def test_router_failure_uses_keyword_fallback(self) -> None:
        primary = MagicMock()
        primary.route.side_effect = RuntimeError("servidor no disponible")
        router = FallbackRouter(primary=primary, fallback=KeywordRouter(CATALOG))

        decision = router.route("necesito licencia")

        self.assertEqual(decision.skill, "licencia_conducir")
        self.assertEqual(router.last_error, "servidor no disponible")

    def test_router_error_is_consumed_only_once(self) -> None:
        primary = MagicMock()
        primary.route.side_effect = RuntimeError("error anterior")
        router = FallbackRouter(primary=primary, fallback=KeywordRouter(CATALOG))

        router.route("necesito licencia")

        self.assertEqual(router.consume_last_error(), "error anterior")
        self.assertIsNone(router.consume_last_error())


if __name__ == "__main__":
    unittest.main()
