from functools import lru_cache
from pathlib import Path

import yaml

from utils.text import normalize_text

from .rag_answer import generate_answer
from .retriever import retrieve


CURRENT_SUPPORTED_TOPIC = "ochavas"
AMBIGUOUS_OCHAVA_PATTERNS = (
    "poner ochava",
    "poner ochavas",
    "hacer ochava",
    "hacer ochavas",
    "necesito ochava",
    "necesito ochavas",
    "me piden ochava",
    "me piden ochavas",
    "consulta por ochava",
    "consulta por ochavas",
)
SPECIFIC_CONTEXT_TERMS = (
    "dimension",
    "dimensiones",
    "minima",
    "minimo",
    "metro",
    "metros",
    "angulo",
    "agudo",
    "obtuso",
    "existente",
    "esquina",
    "fuera de centros urbanos",
    "centros urbanos",
    "trazado",
    "fraccionamiento",
    "cuando no",
    "no se exige",
    "altura",
    "acera",
)
DIRECT_CLOSE_TERMS = (
    "no esta",
    "no estoy",
    "no es",
    "fuera de",
    "cuando no",
    "no se exige",
    "dimension minima",
    "dimensiones minimas",
    "cuanto mide",
)
EXPLORATORY_TERMS = (
    "explicame",
    "contame",
    "que casos",
    "cuales son los casos",
    "informacion",
    "general",
    "resumen",
)


@lru_cache(maxsize=1)
def load_data() -> dict:
    data_path = Path(__file__).with_name("data.yaml")
    with data_path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def detect_topic(text: str, current_fields: dict[str, object]) -> str | None:
    normalized_text = normalize_text(text)
    if "ochava" in normalized_text:
        return CURRENT_SUPPORTED_TOPIC

    current_topic = current_fields.get("tema")
    if current_topic == CURRENT_SUPPORTED_TOPIC:
        return CURRENT_SUPPORTED_TOPIC

    return None


def has_specific_context(text: str) -> bool:
    normalized_text = normalize_text(text)
    return any(term in normalized_text for term in SPECIFIC_CONTEXT_TERMS)


def needs_context_question(text: str, current_fields: dict[str, object]) -> bool:
    normalized_text = normalize_text(text)
    if current_fields.get("contexto_pendiente"):
        return False

    if any(pattern in normalized_text for pattern in AMBIGUOUS_OCHAVA_PATTERNS):
        return not has_specific_context(text)

    return False


def build_retrieval_query(text: str, topic: str | None) -> str:
    if topic == CURRENT_SUPPORTED_TOPIC and "ochava" not in normalize_text(text):
        return f"Tema actual: ochavas. Pregunta: {text}"
    return text


def should_close_after_answer(text: str, current_fields: dict[str, object]) -> bool:
    normalized_text = normalize_text(text)
    if current_fields.get("contexto_pendiente"):
        return False
    if any(term in normalized_text for term in EXPLORATORY_TERMS):
        return False
    return any(term in normalized_text for term in DIRECT_CLOSE_TERMS)


def format_retrieval_answer(results: list[dict]) -> str:
    lines = [
        "Encontré estos artículos relacionados en la muestra cargada del Volumen XV:",
        "",
    ]

    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        url = metadata.get("url", "")
        score = result.get("score", 0.0)
        text = result.get("texto", "").strip()
        if len(text) > 700:
            text = text[:697].rstrip() + "..."

        lines.extend(
            [
                f"{index}. Artículo {result.get('numero')} "
                f"(score {score:.3f})",
                text,
                f"Fuente: {url}",
                "",
            ]
        )

    lines.append(
        "Nota: esta respuesta muestra evidencia recuperada; todavía no es una "
        "respuesta RAG redactada por LLM."
    )
    return "\n".join(lines)


def generate_answer_with_fallback(
    text: str,
    results: list[dict],
    current_fields: dict[str, object],
) -> str:
    effective_fields = {
        **current_fields,
        "contexto_pendiente": [],
    }
    try:
        return generate_answer(text, results, effective_fields)
    except Exception as error:
        return (
            "No pude generar una respuesta redactada con el LLM. "
            "Te muestro la evidencia recuperada directamente.\n\n"
            f"{format_retrieval_answer(results)}\n\n"
            f"Detalle técnico: {error}"
        )


def unsupported_topic_response() -> dict:
    data = load_data()
    metadata = data["metadata"]

    return {
        "status": "need_input",
        "question": (
            "Por ahora esta prueba de permiso de construcción tiene cargada "
            "una muestra sobre ochavas. ¿Querés consultar sobre ochavas o "
            "querés que tomemos otro tema para una próxima ingesta?"
        ),
        "answer": None,
        "state_updates": {
            "tema": None,
            "source_name": metadata["source_name"],
        },
    }


def context_question_response(text: str) -> dict:
    return {
        "status": "need_input",
        "question": (
            "Para orientarte mejor sobre ochavas, necesito precisar el caso. "
            "¿Se trata de una esquina existente, un nuevo trazado o "
            "fraccionamiento, una situación fuera de centros urbanos, o un "
            "caso con ángulo agudo u obtuso?"
        ),
        "answer": None,
        "state_updates": {
            "tema": CURRENT_SUPPORTED_TOPIC,
            "ultima_consulta": text,
            "contexto_pendiente": ["tipo_de_situacion"],
        },
    }


def retrieval_error_response(error: Exception) -> dict:
    return {
        "status": "document_qa",
        "question": None,
        "answer": (
            "Identifiqué una consulta sobre permiso de construcción, pero no "
            "pude consultar el índice local de ochavas.\n\n"
            "Verificá que LM Studio esté activo, que `EMBEDDING_PROVIDER` sea "
            "`lmstudio` y que exista el archivo "
            "`skills/permiso_construccion/index/ochavas_embeddings.jsonl`.\n\n"
            f"Detalle técnico: {error}"
        ),
        "state_updates": {
            "tema": CURRENT_SUPPORTED_TOPIC,
        },
    }


def handle(
    text: str,
    current_fields: dict[str, object],
    history: list[dict[str, str]] | None = None,
) -> dict:
    topic = detect_topic(text, current_fields)
    if topic is None:
        return unsupported_topic_response()

    if needs_context_question(text, current_fields):
        return context_question_response(text)

    query = build_retrieval_query(text, topic)
    try:
        results = retrieve(query, top_k=3)
    except Exception as error:
        return retrieval_error_response(error)

    if not results:
        return {
            "status": "need_input",
            "question": (
                "No encontré evidencia suficiente en la muestra cargada sobre "
                "ochavas. ¿Podés reformular la consulta o precisar el caso?"
            ),
            "answer": None,
            "state_updates": {
                "tema": topic,
                "ultima_consulta": text,
            },
        }

    status = "final" if should_close_after_answer(text, current_fields) else "document_qa"
    return {
        "status": status,
        "question": None,
        "answer": generate_answer_with_fallback(text, results, current_fields),
        "state_updates": {
            "tema": topic,
            "ultima_consulta": text,
            "contexto_pendiente": [],
        },
    }
