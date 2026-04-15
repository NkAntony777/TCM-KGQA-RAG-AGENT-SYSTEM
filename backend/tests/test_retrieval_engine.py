from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval_service.engine import RetrievalEngine, RetrievalServiceSettings, SparseLexiconStore


class FakeEmbeddingClient:
    def is_ready(self) -> bool:
        return True

    def embed(self, texts: list[str], model: str, *, dimensions: int | None = None) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRewriteClient:
    def __init__(self, rewritten: str):
        self.rewritten = rewritten

    def is_ready(self) -> bool:
        return True

    def chat(self, prompt: str, model: str) -> str:
        return self.rewritten


class FakeFilesFirstStoreSequence:
    def __init__(self, responses: list[tuple[list[dict], str]]):
        self.responses = list(responses)
        self.calls = 0

    def health(self) -> dict:
        return {"files_first_index_available": True, "files_first_index_docs": 2}

    def search(self, *, query: str, top_k: int, candidate_k: int, leaf_level: int):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return [], "fts_local"


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


class FakeCaseQAStore:
    def health(self) -> dict:
        return {
            "case_qa_configured": True,
            "case_qa_client_available": True,
            "case_qa_db_path": "E:/tcm_vector_db",
            "case_qa_collection_prefix": "tcm_shard_",
            "case_qa_collection_count": 2,
            "case_qa_collections": ["tcm_shard_0", "tcm_shard_1"],
        }

    def search(self, *, query: str, query_embedding: list[float], top_k: int, candidate_k: int) -> dict:
        return {
            "retrieval_mode": "chroma_case_qa",
            "collection_count": 2,
            "per_collection_k": 2,
            "chunks": [
                {
                    "chunk_id": "case-1",
                    "embedding_id": "case-1",
                    "collection": "tcm_shard_0",
                    "document": "基本信息: 年龄: 47 性别: 女 主诉: 胁肋胀痛 失眠 现病史: 口苦。",
                    "answer": "诊断: 肝郁脾虚证 治疗方案: 方剂: 逍遥散。",
                    "text": "诊断: 肝郁脾虚证 治疗方案: 方剂: 逍遥散。",
                    "source_file": "caseqa:tcm_shard_0",
                    "score": 0.88,
                    "distance": 0.12,
                    "rerank_score": 1.03,
                    "metadata": {"answer": "诊断: 肝郁脾虚证 治疗方案: 方剂: 逍遥散。"},
                }
            ],
            "total": 1,
            "warnings": [],
        }


class RetrievalEngineTests(unittest.TestCase):
    def _settings(self, tmpdir: Path, *, vector_compatibility_enabled: bool = True) -> RetrievalServiceSettings:
        return RetrievalServiceSettings(
            project_backend_dir=tmpdir,
            vector_compatibility_enabled=vector_compatibility_enabled,
            milvus_uri=str(tmpdir / "milvus_demo.db"),
            milvus_host="127.0.0.1",
            milvus_port="19530",
            milvus_collection="test_collection",
            embedding_base_url="http://example.com/v1",
            embedding_model="embedding-model",
            embedding_api_key="test-key",
            case_qa_embedding_model="case-qa-embedding-model",
            case_qa_embedding_dimensions=1024,
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
            embedding_batch_size=2,
            chroma_case_db_path=tmpdir / "case_db",
            chroma_case_mirror_path=tmpdir / "case_db_mirror",
            chroma_case_collection_prefix="tcm_shard_",
            case_qa_vector_fallback_enabled=False,
            structured_qa_index_path=tmpdir / "qa_structured.sqlite",
            structured_qa_input_path=tmpdir / "qa_input.jsonl",
            structured_case_input_path=tmpdir / "case_input.jsonl",
            files_first_dense_fallback_enabled=False,
            sparse_lexicon_path=tmpdir / "sparse.json",
            parent_chunk_store_path=tmpdir / "parents.json",
            local_index_path=tmpdir / "local_index.json",
            sample_corpus_path=tmpdir / "sample.json",
            modern_corpus_path=tmpdir / "modern.json",
            classic_corpus_path=tmpdir / "classic.json",
            runtime_graph_db_path=tmpdir / "graph_runtime.db",
            section_summary_cache_path=tmpdir / "section_summary_cache.sqlite",
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
            result = engine.search_hybrid("逍遥散有什么功效", top_k=3, candidate_k=6, enable_rerank=False, search_mode="hybrid")
            self.assertEqual(result["retrieval_mode"], "dense_local_fallback")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["source_file"], "医方集解.txt")

    def test_search_case_qa_prefers_structured_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            engine.structured_qa = type(
                "FakeStructuredQAIndex",
                (),
                {
                    "search_case": lambda self, query, top_k=10: [
                        {
                            "record_id": "case-1",
                            "embedding_id": "case-1",
                            "collection": "qa_structured_case",
                            "question": "主诉: 胁肋胀痛 失眠 口苦。",
                            "answer": "诊断: 肝郁脾虚证；方剂: 逍遥散。",
                            "chief_complaint": "胁肋胀痛",
                            "history": "失眠 口苦",
                            "tongue": "舌淡红",
                            "pulse": "脉弦",
                            "symptom_text": "胁肋胀痛；失眠；口苦",
                            "syndrome_text": "肝郁脾虚证",
                            "formula_text": "逍遥散",
                            "_rerank_score": 9.25,
                        }
                    ]
                },
            )()
            result = engine.search_case_qa("基本信息: 年龄:47 性别:女 主诉:胁肋胀痛 失眠", top_k=3, candidate_k=12)
            self.assertEqual(result["retrieval_mode"], "structured_case_qa")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["collection"], "qa_structured_case")
            self.assertIn("逍遥散", result["chunks"][0]["answer"])
            self.assertIn("胁肋胀痛", result["chunks"][0]["document"])

    def test_health_marks_vector_hot_path_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp), vector_compatibility_enabled=False))
            health = engine.health()

        self.assertFalse(health["vector_compatibility_enabled"])
        self.assertEqual(health["vector_store"], "disabled")
        self.assertTrue(health["case_qa_vector_hot_path_disabled"])
        self.assertIsNone(engine.case_qa)

    def test_search_hybrid_skips_dense_branch_when_vector_compatibility_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp), vector_compatibility_enabled=False))
            engine.embedding_client = FakeEmbeddingClient()
            result = engine.search_hybrid("逍遥散有什么功效", top_k=3, candidate_k=6, enable_rerank=False, search_mode="hybrid")

        self.assertEqual(result["retrieval_mode"], "vector_compatibility_disabled")
        self.assertEqual(result["total"], 0)
        self.assertIn("vector_compatibility_disabled", result["warnings"])

    def test_search_hybrid_filters_docs_that_miss_query_anchor_entity(self) -> None:
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

            result = engine.search_hybrid(
                "请从AQP分布差异分析五苓散利小便与发汗是否存在阈值效应",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="hybrid",
            )

            self.assertEqual(result["total"], 0)

    def test_search_hybrid_applies_single_query_refinement_for_low_hit_files_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp), vector_compatibility_enabled=False))
            engine.files_first_store = FakeFilesFirstStoreSequence(
                [
                    ([], "fts_local"),
                    (
                        [
                            {
                                "chunk_id": "section::1",
                                "text": "小柴胡汤功效为和解少阳。",
                                "filename": "伤寒论.txt",
                                "file_type": "SECTION",
                                "file_path": "classic://伤寒论/0001",
                                "page_number": 1,
                                "chunk_idx": 0,
                                "chunk_level": 2,
                                "parent_chunk_id": "",
                                "root_chunk_id": "",
                                "book_name": "伤寒论",
                                "chapter_title": "辨太阳病脉证并治",
                                "section_key": "伤寒论::辨太阳病脉证并治",
                                "score": 0.42,
                                "match_snippet": "小柴胡汤 [功效] 为和解少阳",
                            }
                        ],
                        "fts_local_section",
                    ),
                ]
            )
            engine.rewrite_client = FakeRewriteClient("小柴胡汤 功效 和解少阳")

            result = engine.search_hybrid(
                "小柴胡汤有啥用",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="files_first",
            )

            self.assertEqual(engine.files_first_store.calls, 2)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["refined_query"], "小柴胡汤 功效 和解少阳")
            self.assertIn("single_query_refinement_applied", " ".join(result["warnings"]))
            self.assertEqual(result["chunks"][0]["book_name"], "伤寒论")
            self.assertEqual(result["chunks"][0]["file_type"], "SECTION")
            self.assertEqual(result["chunks"][0]["chunk_level"], 2)

    def test_search_hybrid_can_filter_by_file_path_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            engine.embedding_client = FakeEmbeddingClient()
            engine.milvus = FakeMilvusStore()
            engine.local_store.save(
                [
                    {
                        "chunk_id": "leaf-modern",
                        "text": "TRPM8 是冰片镇痛相关靶点。",
                        "filename": "HERB2_reference.txt",
                        "file_path": "herb2://reference/HBREF0001",
                        "page_number": 0,
                        "file_type": "TXT",
                        "chunk_idx": 1,
                        "chunk_level": 3,
                        "parent_chunk_id": "",
                        "root_chunk_id": "root-modern",
                        "dense_embedding": [0.1, 0.2, 0.3],
                        "sparse_embedding": {},
                        "score": 0.91,
                        "rrf_rank": 1,
                    }
                ]
            )

            result = engine.search_hybrid(
                "冰片 TRPM8 机制",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="hybrid",
                allowed_file_path_prefixes=["herb2://"],
            )
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["file_path"], "herb2://reference/HBREF0001")

            filtered_out = engine.search_hybrid(
                "冰片 TRPM8 机制",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="hybrid",
                allowed_file_path_prefixes=["classic://"],
            )
            self.assertEqual(filtered_out["total"], 0)
            self.assertIn("source_prefix_filtered_all", filtered_out["warnings"])

    def test_search_hybrid_files_first_does_not_fall_back_to_dense_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            engine.embedding_client = FakeEmbeddingClient()
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

            result = engine.search_hybrid(
                "逍遥散有什么功效",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="files_first",
            )

            self.assertEqual(result["retrieval_mode"], "fts_missing")
            self.assertEqual(result["total"], 0)
            self.assertIn("files_first_dense_fallback_disabled", result["warnings"])

    def test_search_hybrid_files_first_can_use_sparse_local_without_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RetrievalEngine(self._settings(Path(tmp)))
            engine.lexicon.fit(["六味地黄丸出自小儿药证直诀。"])
            engine.local_store.save(
                [
                    {
                        "chunk_id": "leaf-1",
                        "text": "六味地黄丸出自小儿药证直诀。",
                        "filename": "小儿药证直诀.txt",
                        "file_path": "classic://小儿药证直诀/1",
                        "page_number": 1,
                        "file_type": "TXT",
                        "chunk_idx": 0,
                        "chunk_level": 3,
                        "parent_chunk_id": "",
                        "root_chunk_id": "root-1",
                        "dense_embedding": [],
                        "sparse_embedding": engine.lexicon.encode_document("六味地黄丸出自小儿药证直诀。"),
                    }
                ]
            )

            result = engine.search_hybrid(
                "六味地黄丸 出处 原文",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="files_first",
            )

            self.assertEqual(result["retrieval_mode"], "sparse_local")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["file_path"], "classic://小儿药证直诀/1")

    def test_index_configured_corpora_merges_sample_and_modern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            settings = self._settings(tmpdir)
            settings.sample_corpus_path.write_text(
                """
                [
                  {
                    "chunk_id": "sample-1",
                    "text": "六味地黄丸出自小儿药证直诀。",
                    "filename": "sample.txt",
                    "file_type": "TXT",
                    "file_path": "classic://sample/1",
                    "page_number": 1,
                    "chunk_idx": 0,
                    "parent_chunk_id": "",
                    "root_chunk_id": "sample-1",
                    "chunk_level": 3
                  }
                ]
                """,
                encoding="utf-8",
            )
            settings.modern_corpus_path.write_text(
                """
                [
                  {
                    "chunk_id": "modern-1",
                    "text": "冰片可能通过 TRPM8 发挥镇痛作用。",
                    "filename": "HERB2_reference.txt",
                    "file_type": "TXT",
                    "file_path": "herb2://reference/HBREF0001",
                    "page_number": 0,
                    "chunk_idx": 0,
                    "parent_chunk_id": "",
                    "root_chunk_id": "modern-1",
                    "chunk_level": 3
                  }
                ]
                """,
                encoding="utf-8",
            )
            engine = RetrievalEngine(settings)
            engine.embedding_client = FakeEmbeddingClient()
            engine.milvus = FakeMilvusStore()

            result = engine.index_configured_corpora(reset_collection=True)

            self.assertEqual(result["indexed_documents"], 2)
            self.assertEqual(len(result["corpus_files"]), 2)
            local_rows = engine.local_store.load()
            self.assertEqual(len(local_rows), 2)
            self.assertEqual({row["file_path"] for row in local_rows}, {"classic://sample/1", "herb2://reference/HBREF0001"})

    def test_index_configured_corpora_can_include_classic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            settings = self._settings(tmpdir)
            settings.classic_corpus_path.write_text(
                """
                [
                  {
                    "chunk_id": "classic-1",
                    "text": "古籍：小儿药证直诀\\n篇名：卷上\\n六味地黄丸，治肾怯失音。",
                    "filename": "133-小儿药证直诀.txt",
                    "file_type": "TXT",
                    "file_path": "classic://小儿药证直诀/0001-01",
                    "page_number": 1,
                    "chunk_idx": 0,
                    "parent_chunk_id": "",
                    "root_chunk_id": "classic-1",
                    "chunk_level": 3
                  }
                ]
                """,
                encoding="utf-8",
            )
            engine = RetrievalEngine(settings)
            engine.embedding_client = FakeEmbeddingClient()
            engine.milvus = FakeMilvusStore()

            result = engine.index_configured_corpora(
                reset_collection=True,
                include_sample=False,
                include_modern=False,
                include_classic=True,
            )

            self.assertEqual(result["indexed_documents"], 1)
            self.assertEqual(len(result["corpus_files"]), 1)
            local_rows = engine.local_store.load()
            self.assertEqual(len(local_rows), 1)
            self.assertEqual(local_rows[0]["file_path"], "classic://小儿药证直诀/0001-01")

    def test_files_first_index_can_search_classic_without_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            settings = self._settings(tmpdir)
            settings.classic_corpus_path.write_text(
                """
                [
                  {
                    "chunk_id": "classic-parent-1",
                    "text": "古籍：小儿药证直诀\\n篇名：卷上\\n地黄丸主之，治肾虚。又云补肾阴。",
                    "filename": "133-小儿药证直诀.txt",
                    "file_type": "TXT",
                    "file_path": "classic://小儿药证直诀/0001",
                    "page_number": 1,
                    "chunk_idx": 0,
                    "parent_chunk_id": "",
                    "root_chunk_id": "classic-parent-1",
                    "chunk_level": 2,
                    "book_name": "小儿药证直诀",
                    "chapter_title": "卷上",
                    "section_key": "小儿药证直诀::0001"
                  },
                  {
                    "chunk_id": "classic-1",
                    "text": "古籍：小儿药证直诀\\n篇名：卷上\\n地黄丸主之，治肾虚。",
                    "filename": "133-小儿药证直诀.txt",
                    "file_type": "TXT",
                    "file_path": "classic://小儿药证直诀/0001-01",
                    "page_number": 1,
                    "chunk_idx": 0,
                    "parent_chunk_id": "classic-parent-1",
                    "root_chunk_id": "classic-parent-1",
                    "chunk_level": 3
                  },
                  {
                    "chunk_id": "classic-2",
                    "text": "古籍：小儿药证直诀\\n篇名：卷上\\n又云补肾阴。",
                    "filename": "133-小儿药证直诀.txt",
                    "file_type": "TXT",
                    "file_path": "classic://小儿药证直诀/0001-02",
                    "page_number": 1,
                    "chunk_idx": 1,
                    "parent_chunk_id": "classic-parent-1",
                    "root_chunk_id": "classic-parent-1",
                    "chunk_level": 3
                  }
                ]
                """,
                encoding="utf-8",
            )
            engine = RetrievalEngine(settings)
            engine.milvus = FakeMilvusStore()

            index_result = engine.index_configured_corpora(
                reset_collection=True,
                include_sample=False,
                include_modern=False,
                include_classic=True,
                index_mode="files_first",
            )
            result = engine.search_hybrid(
                "地黄丸 肾虚 小儿药证直诀",
                top_k=3,
                candidate_k=6,
                enable_rerank=False,
                search_mode="files_first",
            )

            self.assertEqual(index_result["index_mode"], "files_first")
            self.assertEqual(index_result["vector_store"], "files_first_fts")
            self.assertEqual(result["retrieval_mode"], "fts_local")
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["chunks"][0]["file_path"], "classic://小儿药证直诀/0001")
            self.assertEqual(result["chunks"][0]["chunk_level"], 2)
            self.assertEqual(result["chunks"][0]["book_name"], "小儿药证直诀")
            self.assertEqual(result["chunks"][0]["chapter_title"], "卷上")
            self.assertTrue(result["chunks"][0]["match_snippet"])

            section = engine.read_section("chapter://小儿药证直诀/卷上", top_k=16)
            self.assertEqual(section["status"], "ok")
            self.assertEqual(section["section"]["book_name"], "小儿药证直诀")
            self.assertEqual(section["section"]["chapter_title"], "卷上")
            self.assertIn("补肾阴", section["section"]["text"])


if __name__ == "__main__":
    unittest.main()
