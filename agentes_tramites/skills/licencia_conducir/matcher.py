import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.text import normalize_text


SKILL_DIR = Path(__file__).resolve().parent
LEAVES_PATH = SKILL_DIR / "hojas_terminales.json"
DOCUMENTS_DIR = SKILL_DIR / "documentos_terminales"

PROFESSIONAL_CATEGORIES = {"B", "C", "D", "E", "F", "H", "G3"}
AMATEUR_CATEGORIES = {"A", "G1", "G2"}

FIELD_ORDER = (
    "tramite",
    "categoria",
    "edad",
    "patologias",
    "licencia_vigente",
)

QUESTIONS = {
    "tramite": (
        "¿Qué trámite necesitás: primera vez, renovación, duplicado "
        "u homologación?"
    ),
    "categoria": (
        "¿Sabés qué categoría de licencia querés tramitar o renovar? "
        "Podés responder A, G1, G2, B, C, D, E, F, H o G3. "
        "Si no la sabés, contame qué vehículo querés manejar, por ejemplo "
        "auto, moto, taxi, camión, ómnibus o maquinaria."
    ),
    "edad": "¿Qué edad tenés?",
    "patologias": (
        "¿Tenés alguna patología o restricción médica registrada? "
        "Respondé sí o no."
    ),
    "licencia_vigente": "¿La licencia está vigente? Respondé sí o no.",
}


@dataclass(frozen=True)
class MatchResult:
    status: str
    leaf: dict[str, Any] | None = None
    missing_field: str | None = None
    question: str | None = None
    reason: str | None = None


@lru_cache(maxsize=1)
def load_leaves() -> list[dict[str, Any]]:
    with LEAVES_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def category_group(category: str | None) -> str | None:
    if category in AMATEUR_CATEGORIES:
        return "amateur"
    if category in PROFESSIONAL_CATEGORIES:
        return "profesional"
    return None


def normalize_fields(fields: dict[str, object]) -> dict[str, object]:
    normalized = {
        key: value for key, value in fields.items() if value is not None
    }

    category = normalized.get("categoria")
    if isinstance(category, str):
        category = category.upper()
        normalized["categoria"] = category
        group = category_group(category)
        if group:
            normalized["grupo_categoria"] = group

    return normalized


def extract_fields(text: str, current_fields: dict[str, object]) -> dict[str, object]:
    """Extrae respuestas evidentes sin usar un LLM dentro de la skill."""
    normalized = normalize_text(text)
    updates: dict[str, object] = {}

    if any(
        term in normalized
        for term in (
            "primera vez",
            "primera licencia",
            "nunca tuve licencia",
            "nunca tuve libreta",
        )
    ):
        updates["tramite"] = "primera_vez"
    elif any(term in normalized for term in ("renovar", "renovacion", "vencio")):
        updates["tramite"] = "renovacion"
    elif any(
        term in normalized
        for term in ("duplicado", "perdi", "extrav", "robaron", "hurto")
    ):
        updates["tramite"] = "duplicado"
    elif any(term in normalized for term in ("homologar", "homologacion", "canje")):
        updates["tramite"] = "homologacion"

    category_match = re.search(
        r"\b(?:categoria\s+)?(g1|g2|g3|b|c|d|e|f|h)\b",
        normalized,
    )
    if category_match:
        updates["categoria"] = category_match.group(1).upper()
    elif (
        re.search(r"\b(?:categoria|licencia)\s+a\b", normalized)
        or normalized == "a"
    ):
        updates["categoria"] = "A"
    if "profesional" in normalized and "categoria" not in updates:
        updates["grupo_categoria"] = "profesional"

    age_match = re.search(r"\b(?:tengo\s+)?(\d{1,3})(?:\s+anos)?\b", normalized)
    if age_match:
        age = int(age_match.group(1))
        if 14 <= age <= 110:
            updates["edad"] = age

    expected_field = next_missing_field(current_fields)
    boolean_value = extract_boolean(normalized)
    if boolean_value is not None and expected_field in {
        "patologias",
        "licencia_vigente",
    }:
        updates[expected_field] = boolean_value

    if any(
        term in normalized
        for term in (
            "tengo patologia",
            "tengo una patologia",
            "restriccion medica",
            "diabetes",
            "problema visual",
            "problema auditivo",
        )
    ):
        updates["patologias"] = True
    elif any(
        term in normalized
        for term in ("sin patologias", "sin restricciones medicas")
    ):
        updates["patologias"] = False

    if any(term in normalized for term in ("esta vigente", "sigue vigente")):
        updates["licencia_vigente"] = True
    elif any(term in normalized for term in ("esta vencida", "no esta vigente")):
        updates["licencia_vigente"] = False

    if "categoria" in updates:
        group = category_group(str(updates["categoria"]))
        if group:
            updates["grupo_categoria"] = group

    return updates


def extract_boolean(normalized_text: str) -> bool | None:
    if normalized_text in {
        "si",
        "sí",
        "correcto",
        "afirmativo",
        "si tengo",
        "sigue vigente",
    }:
        return True
    if normalized_text in {
        "no",
        "negativo",
        "no tengo",
        "no tengo ninguna",
        "ninguna",
        "esta vencida",
    }:
        return False
    return None


def next_missing_field(fields: dict[str, object]) -> str | None:
    result = match_leaf(fields)
    return result.missing_field if result.status == "need_input" else None


def match_leaf(fields: dict[str, object]) -> MatchResult:
    normalized = normalize_fields(fields)
    candidates = [
        leaf for leaf in load_leaves() if is_compatible(leaf, normalized)
    ]

    if not candidates:
        return MatchResult(
            status="unsupported",
            reason=(
                "La combinación informada no está cubierta por las hojas "
                "terminales disponibles en esta PoC."
            ),
        )

    missing_field = choose_missing_field(candidates, normalized)
    if missing_field:
        return MatchResult(
            status="need_input",
            missing_field=missing_field,
            question=QUESTIONS[missing_field],
        )

    exact_matches = [
        leaf for leaf in candidates if conditions_satisfied(leaf, normalized)
    ]
    if len(exact_matches) == 1:
        return MatchResult(status="matched", leaf=exact_matches[0])

    if len(exact_matches) > 1:
        return MatchResult(
            status="unsupported",
            reason="Las respuestas coinciden con más de una hoja terminal.",
        )

    return MatchResult(
        status="unsupported",
        reason="No se pudo determinar una hoja terminal con estos datos.",
    )


def is_compatible(leaf: dict[str, Any], fields: dict[str, object]) -> bool:
    conditions = leaf["condiciones"]

    if "tramite" in fields and fields["tramite"] != conditions.get("tramite"):
        return False

    category = fields.get("categoria")
    if category is not None:
        categories = conditions.get("categorias")
        if categories is not None and category not in categories:
            return False

    group = fields.get("grupo_categoria")
    condition_group = conditions.get("grupo_categoria")
    if group is not None and condition_group is not None and group != condition_group:
        return False

    age = fields.get("edad")
    if isinstance(age, int):
        minimum = conditions.get("edad_min")
        maximum = conditions.get("edad_max")
        if minimum is not None and age < minimum:
            return False
        if maximum is not None and age > maximum:
            return False

    for boolean_field in ("patologias", "licencia_vigente"):
        condition_value = conditions.get(boolean_field)
        if (
            boolean_field in fields
            and condition_value is not None
            and fields[boolean_field] != condition_value
        ):
            return False

    return True


def choose_missing_field(
    candidates: list[dict[str, Any]],
    fields: dict[str, object],
) -> str | None:
    for field_name in FIELD_ORDER:
        if field_name in fields:
            continue
        if field_is_required(field_name, candidates):
            return field_name
    return None


def field_is_required(field_name: str, candidates: list[dict[str, Any]]) -> bool:
    if field_name == "categoria":
        return any(
            "categorias" in leaf["condiciones"]
            or "grupo_categoria" in leaf["condiciones"]
            for leaf in candidates
        )
    if field_name == "edad":
        return any(
            leaf["condiciones"].get("edad_min") is not None
            or leaf["condiciones"].get("edad_max") is not None
            for leaf in candidates
        )
    return any(
        leaf["condiciones"].get(field_name) is not None for leaf in candidates
    )


def conditions_satisfied(
    leaf: dict[str, Any],
    fields: dict[str, object],
) -> bool:
    conditions = leaf["condiciones"]

    if fields.get("tramite") != conditions.get("tramite"):
        return False

    if "categorias" in conditions:
        if fields.get("categoria") not in conditions["categorias"]:
            return False
    elif "grupo_categoria" in conditions:
        if fields.get("grupo_categoria") != conditions["grupo_categoria"]:
            return False

    if (
        conditions.get("edad_min") is not None
        or conditions.get("edad_max") is not None
    ):
        age = fields.get("edad")
        if not isinstance(age, int):
            return False

    for boolean_field in ("patologias", "licencia_vigente"):
        if (
            conditions.get(boolean_field) is not None
            and fields.get(boolean_field) != conditions[boolean_field]
        ):
            return False

    return is_compatible(leaf, fields)


def load_terminal_document(leaf: dict[str, Any]) -> str:
    return load_terminal_document_by_name(leaf["archivo_md"])


def load_terminal_document_by_name(filename: str) -> str:
    registered_files = {leaf["archivo_md"] for leaf in load_leaves()}
    if filename not in registered_files:
        raise ValueError(f"Documento terminal no registrado: {filename}")

    document_path = DOCUMENTS_DIR / filename
    if not document_path.is_file():
        raise FileNotFoundError(
            f"No existe el documento terminal: {document_path.name}"
        )
    return document_path.read_text(encoding="utf-8")


def validate_terminal_assets() -> list[str]:
    errors: list[str] = []
    leaves = load_leaves()
    expected_files = {leaf["archivo_md"] for leaf in leaves}
    existing_files = {path.name for path in DOCUMENTS_DIR.glob("*.md")}

    for leaf in leaves:
        if not leaf.get("id"):
            errors.append("Hay una hoja sin id.")
        if not leaf.get("condiciones"):
            errors.append(f"La hoja {leaf.get('id')} no tiene condiciones.")

    for missing in sorted(expected_files - existing_files):
        errors.append(f"Falta el documento terminal {missing}.")
    for orphan in sorted(existing_files - expected_files):
        errors.append(f"Documento terminal sin hoja: {orphan}.")

    return errors
