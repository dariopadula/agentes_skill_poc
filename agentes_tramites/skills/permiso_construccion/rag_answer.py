from llm_client import build_llm_client, get_model


BASE_INSTRUCTIONS = """
Sos un asistente de trámites ciudadanos de la Intendencia.
Respondé únicamente con la evidencia normativa recuperada por la aplicación.

Reglas:
- No inventes requisitos, dimensiones, excepciones, costos ni enlaces.
- Si los artículos recuperados no alcanzan para responder, decilo claramente.
- Citá los artículos usados por número, por ejemplo: Artículo D.3187.
- Incluí las URL de los artículos citados.
- Usá lenguaje claro y orientado a una persona que quiere hacer un trámite.
- Respondé primero la pregunta concreta del usuario.
- No listes escenarios alternativos salvo que sean imprescindibles para no dar
  una respuesta incorrecta.
- Usá como máximo 1 o 2 artículos en la respuesta principal, salvo que sea
  realmente necesario citar más.
- Si falta información para confirmar el caso, hacé una sola pregunta
  aclaratoria al final.
""".strip()


def generate_answer(
    question: str,
    retrieved_articles: list[dict],
    current_fields: dict[str, object] | None = None,
) -> str:
    prompt = build_prompt(question, retrieved_articles, current_fields or {})
    client = build_llm_client()
    response = client.chat.completions.create(
        model=get_model("document"),
        messages=[
            {"role": "system", "content": BASE_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("El proveedor LLM no devolvió texto.")
    return content.strip()


def build_prompt(
    question: str,
    retrieved_articles: list[dict],
    current_fields: dict[str, object],
) -> str:
    topic = current_fields.get("tema") or "permiso de construcción"
    pending_context = current_fields.get("contexto_pendiente") or []
    article_blocks = "\n\n".join(
        format_article_for_prompt(article)
        for article in retrieved_articles
    )

    return f"""
Tema activo: {topic}
Contexto pendiente declarado por la skill: {pending_context}
Pregunta del usuario: {question}

Artículos recuperados:

{article_blocks}

Redactá una respuesta breve y clara.

Estructura sugerida:
1. Respuesta directa en una o dos frases.
2. Fuente normativa usada.
3. Una sola pregunta aclaratoria final si ayuda a confirmar el caso.

Evitá enumerar todos los escenarios recuperados si la pregunta puede
responderse con una condición concreta del usuario.
""".strip()


def format_article_for_prompt(article: dict) -> str:
    metadata = article.get("metadata", {})
    url = metadata.get("url", "")
    sources = metadata.get("fuentes", [])
    source_lines = "\n".join(
        f"- {source.get('nombre', '')}; referencia: {source.get('referencia', '')}"
        for source in sources
    )

    return f"""
Artículo {article.get("numero")}
Score de recuperación: {article.get("score", 0.0):.3f}
URL: {url}
Texto:
{article.get("texto", "")}
Fuentes normativas:
{source_lines or "- Sin fuentes adicionales registradas."}
""".strip()
