import argparse
import json
from pathlib import Path
from typing import Any

from config import load_environment
from llm_client import build_embedding_client, get_model


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = SKILL_DIR / "documentos" / "articulos_muestra_ochavas.json"
DEFAULT_OUTPUT_PATH = SKILL_DIR / "index" / "ochavas_embeddings.jsonl"


def build_embedding_text(article: dict[str, Any]) -> str:
    hierarchy = article.get("jerarquia") or {}
    hierarchy_text = " > ".join(
        str(value)
        for value in (
            hierarchy.get("volumen"),
            hierarchy.get("parte"),
            hierarchy.get("libro"),
            hierarchy.get("titulo"),
            hierarchy.get("capitulo"),
            hierarchy.get("seccion"),
        )
        if value
    )

    return "\n".join(
        line
        for line in (
            f"Artículo {article.get('numero', '')}".strip(),
            hierarchy_text,
            f"Estado: {article.get('estado', '')}".strip(),
            f"Texto: {article.get('texto', '')}".strip(),
        )
        if line
    )


def create_embedding(client: Any, model: str, text: str) -> list[float]:
    response = client.embeddings.create(model=model, input=text)
    return list(response.data[0].embedding)


def build_index(input_path: Path, output_path: Path) -> int:
    load_environment()
    client = build_embedding_client()
    model = get_model("embedding")

    source = json.loads(input_path.read_text(encoding="utf-8-sig"))
    articles = source.get("articulos", [])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for article in articles:
            embedding_text = build_embedding_text(article)
            record = {
                "id": article["id"],
                "numero": article["numero"],
                "texto": article["texto"],
                "embedding_text": embedding_text,
                "embedding_model": model,
                "embedding": create_embedding(client, model, embedding_text),
                "metadata": {
                    "node_id": article.get("node_id"),
                    "estado": article.get("estado"),
                    "url": article.get("url"),
                    "fuente_armado": article.get("fuente_armado"),
                    "jerarquia": article.get("jerarquia"),
                    "fuentes": article.get("fuentes", []),
                    "fecha_consulta": article.get("fecha_consulta"),
                },
            }
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return len(articles)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un índice JSONL de embeddings para permiso de construcción."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_index(args.input, args.output)
    print(f"Índice generado: {args.output} ({count} artículos)")


if __name__ == "__main__":
    main()
