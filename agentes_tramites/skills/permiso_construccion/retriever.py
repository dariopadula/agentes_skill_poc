import argparse
import json
import math
from pathlib import Path
from typing import Any

from config import load_environment
from llm_client import build_embedding_client, get_model


SKILL_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX_PATH = SKILL_DIR / "index" / "ochavas_embeddings.jsonl"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0

    return dot_product / (left_norm * right_norm)


def load_index(index_path: Path = DEFAULT_INDEX_PATH) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with index_path.open(encoding="utf-8") as index_file:
        for line in index_file:
            if line.strip():
                records.append(json.loads(line))
    return records


def create_query_embedding(query: str) -> list[float]:
    load_environment()
    client = build_embedding_client()
    response = client.embeddings.create(model=get_model("embedding"), input=query)
    return list(response.data[0].embedding)


def retrieve(
    query: str,
    *,
    index_path: Path = DEFAULT_INDEX_PATH,
    top_k: int = 3,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    query_embedding = create_query_embedding(query)
    results = []

    for record in load_index(index_path):
        score = cosine_similarity(query_embedding, record["embedding"])
        if score >= min_score:
            results.append(
                {
                    "score": score,
                    "id": record["id"],
                    "numero": record["numero"],
                    "texto": record["texto"],
                    "metadata": record["metadata"],
                }
            )

    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupera artículos similares desde el índice local."
    )
    parser.add_argument("query")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = retrieve(
        args.query,
        index_path=args.index,
        top_k=args.top_k,
        min_score=args.min_score,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
