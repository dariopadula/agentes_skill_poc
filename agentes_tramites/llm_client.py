import os
from functools import lru_cache
from typing import Literal


LLMRole = Literal["router", "document"]
SUPPORTED_PROVIDERS = {"openai", "lmstudio"}


def get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("LLM_PROVIDER debe ser 'openai' o 'lmstudio'.")
    return provider


def get_provider_name() -> str:
    return "LM Studio" if get_llm_provider() == "lmstudio" else "OpenAI"


def get_model(role: LLMRole) -> str:
    variable = "ROUTER_MODEL" if role == "router" else "DOCUMENT_MODEL"
    configured = os.getenv(variable, "").strip()
    if configured:
        return configured

    # Compatibilidad con la configuración anterior del proyecto.
    legacy_model = os.getenv("OPENAI_MODEL", "").strip()
    if legacy_model:
        return legacy_model

    if get_llm_provider() == "openai":
        return "gpt-4.1-mini" if role == "router" else "gpt-5-mini"

    raise RuntimeError(f"Falta configurar {variable} para LM Studio.")


def is_llm_configured(role: LLMRole) -> bool:
    try:
        provider = get_llm_provider()
        get_model(role)
    except (RuntimeError, ValueError):
        return False

    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())

    return bool(os.getenv("LM_STUDIO_BASE_URL", "").strip())


@lru_cache(maxsize=1)
def build_llm_client():
    """Construye un cliente compatible con el proveedor configurado."""
    from openai import OpenAI

    provider = get_llm_provider()
    if provider == "lmstudio":
        base_url = os.getenv("LM_STUDIO_BASE_URL", "").strip()
        if not base_url:
            raise RuntimeError("Falta configurar LM_STUDIO_BASE_URL.")
        return OpenAI(
            base_url=base_url,
            api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio").strip()
            or "lm-studio",
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Falta configurar OPENAI_API_KEY.")
    return OpenAI(api_key=api_key)
