import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, Field

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
    tramite: Literal[
        "primera_vez",
        "renovacion",
        "duplicado",
        "homologacion",
    ] | None = None
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
    ] | None = None
    grupo_categoria: Literal["amateur", "profesional"] | None = None
    edad: int | None = Field(default=None, ge=0, le=120)
    patologias: bool | None = None
    licencia_vigente: bool | None = None


class LLMRouteResult(BaseModel):
    skill: str
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_fields: ExtractedFields


class OpenAIRouter:
    """Router semántico con salida estructurada mediante OpenAI."""

    def __init__(
        self,
        catalog: dict[str, dict[str, object]],
        model: str | None = None,
    ) -> None:
        # El import diferido permite usar el modo local sin instalar/cargar el SDK.
        from openai import OpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY.")

        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.catalog = catalog

    def route(self, text: str) -> RouteDecision:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Sos un router de trámites ciudadanos. "
                        "Elegí exclusivamente una skill del catálogo siguiente "
                        "o devolvé 'unknown' si ninguna corresponde. Extraé "
                        "solamente datos expresados por el usuario y únicamente "
                        "si figuran en datos_que_puede_extraer para la skill. "
                        "No inventes datos.\n\n"
                        f"CATÁLOGO:\n{json.dumps(self.catalog, ensure_ascii=False)}"
                    ),
                },
                {"role": "user", "content": text},
            ],
            text_format=LLMRouteResult,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI no devolvió una decisión estructurada.")

        if parsed.skill != "unknown" and parsed.skill not in self.catalog:
            raise RuntimeError(
                f"OpenAI devolvió una skill no registrada: {parsed.skill}"
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

    if not os.getenv("OPENAI_API_KEY"):
        return keyword_router

    return FallbackRouter(
        primary=OpenAIRouter(catalog),
        fallback=keyword_router,
    )
