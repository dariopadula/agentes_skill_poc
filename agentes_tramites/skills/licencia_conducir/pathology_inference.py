import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from llm_client import build_llm_client, get_model


SKILL_DIR = Path(__file__).resolve().parent
PATHOLOGY_NODE_PATH = SKILL_DIR / "nodos_skills" / "skill_nodo_patologias.md"

PathologyStatus = Literal["detected", "not_detected", "need_input", "unknown"]
Confidence = Literal["alta", "media", "baja"]


@dataclass(frozen=True)
class DetectedCondition:
    codigo: int
    nombre: str
    texto_usuario: str


@dataclass(frozen=True)
class PathologyInference:
    status: PathologyStatus
    patologias_inferidas: bool | None = None
    codigos_patologias_inferidos: list[int] = field(default_factory=list)
    condiciones_detectadas: list[DetectedCondition] = field(default_factory=list)
    confidence: str | None = None
    question: str | None = None
    reason: str | None = None


class DetectedConditionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: int = Field(ge=1)
    nombre: str
    texto_usuario: str


class PathologyInferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PathologyStatus
    patologias_inferidas: bool | None
    codigos_patologias_inferidos: list[int]
    condiciones_detectadas: list[DetectedConditionResult]
    confidence: Confidence | None
    question: str | None
    reason: str

    @model_validator(mode="after")
    def validate_contract(self) -> "PathologyInferenceResult":
        if self.status == "detected":
            if self.patologias_inferidas is not True:
                raise ValueError("detected requiere patologias_inferidas true.")
            if not self.codigos_patologias_inferidos:
                raise ValueError("detected requiere al menos un codigo.")
            if not self.condiciones_detectadas:
                raise ValueError("detected requiere condiciones_detectadas.")
            if self.confidence is None:
                raise ValueError("detected requiere confidence.")
            if self.question is not None:
                raise ValueError("detected debe usar question null.")
            return self

        if self.status == "not_detected":
            if self.patologias_inferidas is not False:
                raise ValueError("not_detected requiere patologias_inferidas false.")
            if self.codigos_patologias_inferidos:
                raise ValueError("not_detected no debe devolver codigos.")
            if self.condiciones_detectadas:
                raise ValueError("not_detected no debe devolver condiciones.")
            if self.question is not None:
                raise ValueError("not_detected debe usar question null.")
            return self

        if self.patologias_inferidas is not None:
            raise ValueError("Solo detected/not_detected infieren patologias.")
        if self.codigos_patologias_inferidos:
            raise ValueError("Solo detected puede devolver codigos.")
        if self.condiciones_detectadas:
            raise ValueError("Solo detected puede devolver condiciones.")
        if self.status == "need_input" and not self.question:
            raise ValueError("need_input requiere question.")
        return self


@lru_cache(maxsize=1)
def load_pathology_node_guide() -> str:
    return PATHOLOGY_NODE_PATH.read_text(encoding="utf-8")


def infer_pathology(text: str) -> PathologyInference:
    try:
        return _infer_pathology_with_llm(text)
    except Exception:
        return PathologyInference(
            status="unknown",
            question=(
                "No pude interpretar si eso cuenta como patologia o restriccion. "
                "Para avanzar, responde si tenes una patologia o restriccion "
                "medica registrada, o no si no tenes."
            ),
            reason="Fallo la inferencia automatica de patologias.",
        )


def _infer_pathology_with_llm(text: str) -> PathologyInference:
    guide = load_pathology_node_guide()
    client = build_llm_client()
    response = client.chat.completions.create(
        model=get_model("document"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Sos un clasificador administrativo de patologias para "
                    "licencia de conducir. Usa exclusivamente la guia provista. "
                    "No diagnostiques, no des consejo medico y no respondas "
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
                "name": "pathology_inference",
                "strict": True,
                "schema": PathologyInferenceResult.model_json_schema(),
            },
        },
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("El proveedor LLM no devolvio una inferencia.")
    return parse_pathology_inference(content)


def parse_pathology_inference(content: str) -> PathologyInference:
    try:
        parsed = PathologyInferenceResult.model_validate_json(content)
    except ValidationError:
        data = json.loads(content)
        parsed = PathologyInferenceResult.model_validate(data)

    return PathologyInference(
        status=parsed.status,
        patologias_inferidas=parsed.patologias_inferidas,
        codigos_patologias_inferidos=parsed.codigos_patologias_inferidos,
        condiciones_detectadas=[
            DetectedCondition(
                codigo=condition.codigo,
                nombre=condition.nombre,
                texto_usuario=condition.texto_usuario,
            )
            for condition in parsed.condiciones_detectadas
        ],
        confidence=parsed.confidence,
        question=parsed.question,
        reason=parsed.reason,
    )
