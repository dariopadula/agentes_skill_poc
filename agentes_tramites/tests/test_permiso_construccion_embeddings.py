import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from skills.permiso_construccion.ingesta.build_embeddings_index import (
    build_embedding_text,
    build_index,
)
from skills.permiso_construccion.retriever import cosine_similarity, retrieve


class PermisoConstruccionEmbeddingsTests(unittest.TestCase):
    def test_build_embedding_text_includes_article_hierarchy_and_body(self) -> None:
        article = {
            "numero": "D.3186",
            "estado": "vigente",
            "texto": "Texto del artículo.",
            "jerarquia": {
                "volumen": "Volumen XV",
                "parte": "Parte Legislativa",
                "libro": "Libro XV",
                "titulo": "Título I",
                "capitulo": "Capítulo I De las ochavas",
                "seccion": None,
            },
        }

        text = build_embedding_text(article)

        self.assertIn("Artículo D.3186", text)
        self.assertIn("Volumen XV > Parte Legislativa", text)
        self.assertIn("Estado: vigente", text)
        self.assertIn("Texto del artículo.", text)

    def test_cosine_similarity_orders_equal_vectors_highest(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_build_index_writes_jsonl_records(self) -> None:
        client = MagicMock()
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
        )
        source = {
            "articulos": [
                {
                    "id": "articulo_1",
                    "numero": "D.1",
                    "estado": "vigente",
                    "texto": "Texto.",
                    "node_id": "1",
                    "url": "https://example.test/articulo/1",
                    "fuente_armado": "https://example.test/armado/1",
                    "jerarquia": {"capitulo": "Capítulo I"},
                    "fuentes": [],
                    "fecha_consulta": "2026-06-24",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "articulos.json"
            output_path = Path(temp_dir) / "index.jsonl"
            input_path.write_text(json.dumps(source), encoding="utf-8")

            with (
                patch(
                    "skills.permiso_construccion.ingesta.build_embeddings_index.build_embedding_client",
                    return_value=client,
                ),
                patch(
                    "skills.permiso_construccion.ingesta.build_embeddings_index.get_model",
                    return_value="embedding-model",
                ),
                patch(
                    "skills.permiso_construccion.ingesta.build_embeddings_index.load_environment"
                ),
            ):
                count = build_index(input_path, output_path)

            self.assertEqual(count, 1)
            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(record["id"], "articulo_1")
            self.assertEqual(record["embedding_model"], "embedding-model")
            self.assertEqual(record["embedding"], [0.1, 0.2, 0.3])

    def test_retrieve_returns_top_matching_records(self) -> None:
        records = [
            {
                "id": "articulo_a",
                "numero": "D.1",
                "texto": "A",
                "embedding": [1.0, 0.0],
                "metadata": {"url": "a"},
            },
            {
                "id": "articulo_b",
                "numero": "D.2",
                "texto": "B",
                "embedding": [0.0, 1.0],
                "metadata": {"url": "b"},
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "index.jsonl"
            index_path.write_text(
                "\n".join(json.dumps(record) for record in records),
                encoding="utf-8",
            )

            with patch(
                "skills.permiso_construccion.retriever.create_query_embedding",
                return_value=[1.0, 0.0],
            ):
                results = retrieve("ochava", index_path=index_path, top_k=1)

        self.assertEqual(results[0]["id"], "articulo_a")
        self.assertTrue(math.isclose(results[0]["score"], 1.0))


if __name__ == "__main__":
    unittest.main()
