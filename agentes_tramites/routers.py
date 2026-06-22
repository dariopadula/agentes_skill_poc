import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from llm_client import (
    build_llm_client,
    get_llm_provider,
    get_model,
    get_provider_name,
    is_llm_configured,
)
from utils.text import normalize_text


@dataclass
class RouteDecision:
    """Decisión común para cualquier implementación de router."""

    skill: str | None
    confidence: float
    extracted_fields: dict[str, object] = field(default_factory=dict)


class Router(Protocol):
    def route(self, text: str) -> RouteDecision:
        ...


class KeywordRouter:
    """Router local, determinista y sin dependencias externas."""

    def __init__(self, catalog: dict[str, dict[str, object]]) -> None:
        self.catalog = catalog

    def route(self, text: str) -> RouteDecision:
        normalized = normalize_text(text)
        candidates: list[tuple[int, str]] = []

        for skill_name, metadata in self.catalog.items():
            keywords = metadata["palabras_clave"]
            matches = [
                word
                for word in keywords
                if re.search(
                    rf"\b{re.escape(normalize_text(str(word)))}\b",
                    normalized,
                )
            ]
            if matches:
                candidates.append((len(matches), skill_name))

        if not candidates:
            return RouteDecision(skill=None, confidence=0.0)

        match_count, selected_skill = max(candidates)
        confidence = min(0.60 + 0.10 * match_count, 0.95)
        return RouteDecision(skill=selected_skill, confidence=confidence)


class ExtractedFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tramite: Literal[
        "primera_vez",
        "renovacion",
        "duplicado",
        "homologacion",
    ] | None
    categoria: Literal[
        "A",
        "G1",
        "G2",
        "B",
        "C",
        "D",
        "E",
        "F",
        "H",
        "G3",
    ] | None
    grupo_categoria: Literal["amateur", "profesional"] | None
    edad: int | None = Field(ge=0, le=120)
    patologias: bool | None
    licencia_vigente: bool | None


class LLMRouteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_fields: ExtractedFields


class LLMRouter:
    """Router semántico independiente del proveedor configurado."""

    def __init__(
        self,
        catalog: dict[str, dict[str, object]],
        model: str | None = None,
    ) -> None:
        self.client = build_llm_client()
        self.model = model or get_model("router")
        self.provider = get_llm_provider()
        self.provider_name = get_provider_name()
        self.catalog = catalog

    def route(self, text: str) -> RouteDecision:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sos un router de trámites ciudadanos. "
                        "Elegí exclusivamente una skill del catálogo siguiente "
                        "o devolvé 'unknown' si ninguna corresponde. Extraé "
                        "solamente datos expresados por el usuario y únicamente "
                        "si figuran en datos_que_puede_extraer para la skill. "
                        "No inventes datos. Devolvé todos los campos del esquema; "
                        "usá null cuando un dato no haya sido expresado.\n\n"
                        f"CATÁLOGO:\n{json.dumps(self.catalog, ensure_ascii=False)}"
                    ),
                },
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "route_decision",
                    "strict": True,
                    "schema": LLMRouteResult.model_json_schema(),
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(
                f"{self.provider_name} no devolvió una decisión estructurada."
            )
        parsed = LLMRouteResult.model_validate_json(content)

        if parsed.skill != "unknown" and parsed.skill not in self.catalog:
            raise RuntimeError(
                f"{self.provider_name} devolvió una skill no registrada: "
                f"{parsed.skill}"
            )

        return RouteDecision(
            skill=None if parsed.skill == "unknown" else parsed.skill,
            confidence=parsed.confidence,
            extracted_fields=parsed.extracted_fields.model_dump(exclude_none=True),
        )


class FallbackRouter:
    """Intenta el router principal y vuelve al local ante cualquier error."""

    def __init__(self, primary: Router, fallback: Router) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_error: str | None = None

    def route(self, text: str) -> RouteDecision:
        try:
            self.last_error = None
            return self.primary.route(text)
        except Exception as exc:
            self.last_error = str(exc)
            return self.fallback.route(text)

    def consume_last_error(self) -> str | None:
        """Devuelve el último error y evita volver a mostrarlo."""
        error = self.last_error
        self.last_error = None
        return error


def build_router(
    catalog: dict[str, dict[str, object]],
    mode: str | None = None,
) -> Router:
    """Construye el router según ROUTER_MODE: keywords, llm o auto."""
    selected_mode = (mode or os.getenv("ROUTER_MODE", "keywords")).lower()
    keyword_router = KeywordRouter(catalog)

    if selected_mode == "keywords":
        return keyword_router

    if selected_mode not in {"llm", "auto"}:
        raise ValueError("ROUTER_MODE debe ser 'keywords', 'llm' o 'auto'.")

    if not is_llm_configured("router"):
        return keyword_router

    return FallbackRouter(
        primary=LLMRouter(catalog),
        fallback=keyword_router,
    )
