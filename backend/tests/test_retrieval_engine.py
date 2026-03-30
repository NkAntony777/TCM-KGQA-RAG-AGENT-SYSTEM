from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval_service.engine import RetrievalEngine, RetrievalServiceSettings, SparseLexiconStore


class FakeEmbeddingClient:
    def is_ready(self) -> bool:
        return True

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeMilvusStore:
    def health(self) -> dict:
        return {"milvus_available": True, "collection_exists": True}

    def has_collection(self) -> bool:
        return False

    def hybrid_search(self, **kwargs):
        return []

    def dense_search(self, **kwargs):
        return [
            {
                "chunk_id": "leaf-1",
                "text": "逍遥散用于肝郁脾虚。",
                "filename": "医方集解.txt",
                "page_number": 12,
                "file_type": "TXT",
                "chunk_idx": 1,
                "chunk_level": 3,
                "parent_chunk_id": "",
                "root_chunk_id": "root-1",
                "score": 0.88,
                "rrf_rank": 1,
            }
        ]


class RetrievalEngineTests(unittest.TestCase):
    def _settings(self, tmpdir: Path) -> RetrievalServiceSettings:
        return RetrievalServiceSettings(
            project_backend_dir=tmpdir,
            milvus_uri=str(tmpdir / "milvus_demo.db"),
            milvus_host="127.0.0.1",
            milvus_port="19530",
            milvus_collection="test_collection",
            embedding_base_url="http://example.com/v1",
            embedding_model="embedding-model",
            embedding_api_key="test-key",
            rewrite_base_url="",
            rewrite_model="rewrite-model",
            rewrite_api_key="",
            rerank_endpoint="",
            rerank_model="",
            rerank_api_key="",
            auto_merge_enabled=True,
            auto_merge_threshold=2,
            leaf_retrieve_level=3,
            dense_dim=3,
            sparse_lexicon_path=tmpdir / "sparse.json",
            parent_chunk_store_path=tmpdir / "parents.json",
            local_index_path=tmpdir / "local_index.json",
            sample_corpus_path=tmpdir / "sample.json",
        )

    def test_sparse_lexicon_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SparseLexiconStore(Path(tmp) / "lexicon.json")
            store.fit(["逍遥散用于肝郁脾虚", "柴胡归肝经"])
            vector = store.encode_document("逍遥散用于肝郁")
            self.assertTrue(vector)
            store.save()

            reloaded = SparseLexiconStore(Path(tmp) / "lexicon.json")
            query_vector = reloaded.encode_query("逍遥散")
            self.assertTrue(query_vector)
            self.assertEqual(reloaded.encode_query("不存在的词"), {})

    def test_rewrite_query_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            result = engine.rewrite_query("逍遥散有什么功效", strategy="complex")
            self.assertIn("expanded_query", result)
            self.assertTrue(result["step_back_question"])
            self.assertTrue(result["hypothetical_doc"])

    def test_search_hybrid_dense_fallback_normalizes_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            engine.embedding_client = FakeEmbeddingClient()
            engine.milvus = FakeMilvusStore()
            engine.local_store.save(
                [
                    {
                        "chunk_id": "leaf-1",
                        "text": "逍遥散用于肝郁脾虚。",
                        "filename": "医方集解.txt",
                        "page_number": 12,
                        "file_type": "TXT",
                        "chunk_idx": 1,
                        "chunk_level": 3,
                        "parent_chunk_id": "",
                        "root_chunk_id": "root-1",
                        "dense_embedding": [0.1, 0.2, 0.3],
                        "sparse_embedding": {},
                        "score": 0.88,
                        "rrf_rank": 1,
                    }
                ]
            )
            result = engine.search_hybrid("逍遥散有什么功效", top_k=3, candidate_k=6, enable_rerank=False)
            self.assertEqual(result["retrieval_mode"], "dense_local_fallback")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["source_file"], "医方集解.txt")


if __name__ == "__main__":
    unittest.main()
