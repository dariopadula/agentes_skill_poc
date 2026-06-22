import re

from llm_client import build_llm_client, get_model


MAX_HISTORY_MESSAGES = 8

BASE_INSTRUCTIONS = """
Sos un asistente de trámites ciudadanos.
Respondé únicamente con información contenida en el documento Markdown
provisto por la aplicación.

Reglas:
- No inventes requisitos, patologías, costos, enlaces ni excepciones.
- Si el documento no contiene la respuesta, decilo explícitamente.
- Usá lenguaje claro, breve y directo.
- Cuando corresponda, mencioná la sección del documento que respalda la respuesta.
- No confundas información de otros trámites.
""".strip()


def generate_initial_summary(markdown: str) -> str:
    prompt = """
Presentá el resultado de este trámite al ciudadano.

Primero indicá de forma clara qué documentación y comprobantes debe llevar.
Después resumí los pasos principales.
Finalmente ofrecé, en una sola pregunta breve, ampliar otros temas que estén
realmente presentes en el documento, por ejemplo agenda, patologías,
requisitos diferenciales, alertas o fuente. No enumeres temas inexistentes.
""".strip()

    try:
        return _call_model(markdown, [{"role": "user", "content": prompt}])
    except Exception:
        return _fallback_initial_summary(markdown)


def answer_document_question(
    markdown: str,
    history: list[dict[str, str]],
) -> str:
    messages = [
        message
        for message in history[-MAX_HISTORY_MESSAGES:]
        if message.get("role") in {"user", "assistant"}
    ]
    try:
        return _call_model(markdown, messages)
    except Exception:
        question = messages[-1]["content"] if messages else ""
        return _fallback_question_answer(markdown, question)


def _call_model(markdown: str, messages: list[dict[str, str]]) -> str:
    client = build_llm_client()
    response = client.chat.completions.create(
        model=get_model("document"),
        messages=[
            {
                "role": "system",
                "content": BASE_INSTRUCTIONS,
            },
            {
                "role": "system",
                "content": f"DOCUMENTO DE REFERENCIA:\n\n{markdown}",
            },
            *messages,
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("El proveedor LLM no devolvió texto.")
    return content.strip()


def _fallback_initial_summary(markdown: str) -> str:
    requirements = _extract_section(markdown, "Requisitos")
    steps = _extract_section(markdown, "Cómo se hace")
    parts = [
        "No pude generar el resumen con el LLM. "
        "Te muestro directamente la información del documento.",
    ]
    if requirements:
        parts.append(f"## Documentación y requisitos\n{requirements}")
    if steps:
        parts.append(f"## Pasos principales\n{steps}")
    parts.append(
        "Podés preguntarme por agenda, alertas u otra información incluida "
        "en este trámite."
    )
    return "\n\n".join(parts)


def _fallback_question_answer(markdown: str, question: str) -> str:
    normalized = question.lower()
    section_by_keyword = {
        "agenda": "Agenda",
        "turno": "Agenda",
        "hora": "Agenda",
        "patolog": "Alertas importantes",
        "diabet": "Alertas importantes",
        "llevar": "Requisitos",
        "document": "Requisitos",
        "requisito": "Requisitos",
        "paso": "Cómo se hace",
        "hacer": "Cómo se hace",
        "alerta": "Alertas importantes",
        "fuente": "Fuente",
    }
    for keyword, section in section_by_keyword.items():
        if keyword in normalized:
            content = _extract_section(markdown, section)
            if content:
                return (
                    "No pude consultar el LLM. Según la sección "
                    f"“{section}” del documento:\n\n{content}"
                )

    return (
        "No pude consultar el LLM y no encontré una sección claramente "
        "relacionada con esa pregunta. Probá preguntar por requisitos, pasos, "
        "agenda, alertas o fuente."
    )


def _extract_section(markdown: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""
