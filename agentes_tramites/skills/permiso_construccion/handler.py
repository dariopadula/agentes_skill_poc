from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_data() -> dict:
    data_path = Path(__file__).with_name("data.yaml")
    with data_path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def handle(
    text: str,
    current_fields: dict[str, object],
    history: list[dict[str, str]] | None = None,
) -> dict:
    """Respuesta mínima: alcanza para probar selección y ejecución."""
    data = load_data()
    metadata = data["metadata"]
    answer = data["answer"]

    return {
        "status": "final",
        "question": None,
        "answer": (
            f"Trámite identificado: {metadata['title']}\n\n"
            f"{answer['message']}\n"
            f"Próximo paso de la PoC: {answer['next_step']}\n\n"
            f"Trazabilidad: {metadata['source_name']}\n"
            f"Advertencia: {metadata['disclaimer']}"
        ),
        "state_updates": {},
    }
