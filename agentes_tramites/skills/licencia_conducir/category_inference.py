import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from llm_client import build_llm_client, get_model
from skills.licencia_conducir.matcher import category_group


SKILL_DIR = Path(__file__).resolve().parent
CATEGORY_NODE_PATH = SKILL_DIR / "nodos_skills" / "skill_nodo_categoria.md"

CategoryStatus = Literal["detected", "need_input", "unknown"]
Confidence = Literal["alta", "media", "baja"]
Category = Literal["A", "G1", "G2", "B", "C", "D", "E", "F", "H", "G3"]
CategoryGroup = Literal["amateur", "profesional"]


@dataclass(frozen=True)
class CategoryInference:
    status: CategoryStatus
    categoria_inferida: str | None = None
    grupo_categoria_inferido: str | None = None
    confidence: str | None = None
    question: str | None = None
    reason: str | None = None


class CategoryInferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CategoryStatus
    categoria_inferida: Category | None
    grupo_categoria_inferido: CategoryGroup | None
    confidence: Confidence | None
    question: str | None
    reason: str

    @model_validator(mode="after")
    def validate_contract(self) -> "CategoryInferenceResult":
        if self.status == "detected":
            if not self.categoria_inferida:
                raise ValueError("detected requiere categoria_inferida.")
            expected_group = category_group(self.categoria_inferida)
            if self.grupo_categoria_inferido != expected_group:
                raise ValueError("grupo_categoria_inferido no coincide.")
            if self.confidence is None:
                raise ValueError("detected requiere confidence.")
            if self.question is not None:
                raise ValueError("detected debe usar question null.")
            return self

        if self.categoria_inferida is not None:
            raise ValueError("Solo detected puede devolver categoria_inferida.")
        if self.grupo_categoria_inferido is not None:
            raise ValueError("Solo detected puede devolver grupo_categoria_inferido.")
        if self.status == "need_input" and not self.question:
            raise ValueError("need_input requiere question.")
        return self


@lru_cache(maxsize=1)
def load_category_node_guide() -> str:
    return CATEGORY_NODE_PATH.read_text(encoding="utf-8")


def infer_category(text: str) -> CategoryInference:
    try:
        return _infer_category_with_llm(text)
    except Exception:
        return CategoryInference(
            status="unknown",
            question=(
                "No pude interpretar la categoria automaticamente. "
                "Decime la categoria A, G1, G2, B, C, D, E, F, H o G3, "
                "o describime con mas detalle el vehiculo."
            ),
            reason="Fallo la inferencia automatica de categoria.",
        )


def _infer_category_with_llm(text: str) -> CategoryInference:
    guide = load_category_node_guide()
    client = build_llm_client()
    response = client.chat.completions.create(
        model=get_model("document"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Sos un clasificador de categoria de licencia. "
                    "Usa exclusivamente la guia provista. No respondas "
                    "requisitos del tramite. Devolve solo JSON valido."
                ),
            },
            {
                "role": "system",
                "content": f"GUIA DEL NODO:\n\n{guide}",
            },
            {"role": "user", "content": text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "category_inference",
                "strict": True,
                "schema": CategoryInferenceResult.model_json_schema(),
            },
        },
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("El proveedor LLM no devolvio una inferencia.")
    return parse_category_inference(content)


def parse_category_inference(content: str) -> CategoryInference:
    try:
        parsed = CategoryInferenceResult.model_validate_json(content)
    except ValidationError:
        # Algunos proveedores locales no respetan response_format de forma
        # estricta; este intento mantiene el fallo controlado si devuelven JSON.
        data = json.loads(content)
        parsed = CategoryInferenceResult.model_validate(data)

    return CategoryInference(
        status=parsed.status,
        categoria_inferida=parsed.categoria_inferida,
        grupo_categoria_inferido=parsed.grupo_categoria_inferido,
        confidence=parsed.confidence,
        question=parsed.question,
        reason=parsed.reason,
    )
