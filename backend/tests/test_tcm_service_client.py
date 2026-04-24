from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_retrieval_case_qa,
    call_retrieval_hybrid,
    service_health_snapshot,
)


class ServiceClientLocalFallbackTests(unittest.TestCase):
    def test_graph_entity_lookup_fallback_uses_local_graph_engine(self) -> None:
        fake_engine = type(
            "FakeGraphEngine",
            (),
            {
                "entity_lookup": lambda self, name, top_k=12, predicate_allowlist=None, predicate_blocklist=None: {
                    "entity": {"canonical_name": name, "entity_type": "formula"},
                    "relations": [
                        {
                            "predicate": "使用药材",
                            "target": "熟地黄",
                            "source_book": "小儿药证直诀",
                            "source_chapter": "卷下",
                        }
                    ],
                    "total": 1,
                }
            },
        )()

        with (
            patch("tools.tcm_service_client._post", side_effect=RuntimeError("graph_down")),
            patch("tools.tcm_service_client.get_graph_engine", return_value=fake_engine),
        ):
            result = call_graph_entity_lookup("六味地黄丸", top_k=6, predicate_allowlist=["使用药材"])

        self.assertEqual(result["backend"], "local-engine")
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["relations"][0]["target"], "熟地黄")

    def test_retrieval_hybrid_fallback_uses_local_retrieval_engine(self) -> None:
        fake_engine = type(
            "FakeRetrievalEngine",
            (),
            {
                "search_hybrid": lambda self, **kwargs: {
                    "retrieval_mode": "files_first",
                    "chunks": [
                        {
                            "text": "六味地黄丸见《小儿药证直诀》。",
                            "source_file": "133-小儿药证直诀.txt",
                            "source_page": 42,
                            "score": 0.93,
                        }
                    ],
                    "total": 1,
                    "warnings": [],
                }
            },
        )()

        with (
            patch("tools.tcm_service_client._post", side_effect=RuntimeError("retrieval_down")),
            patch("tools.tcm_service_client.get_retrieval_engine", return_value=fake_engine),
        ):
            result = call_retrieval_hybrid(
                query="六味地黄丸 出处 原文",
                top_k=4,
                candidate_k=12,
                enable_rerank=False,
                search_mode="files_first",
                allowed_file_path_prefixes=["classic://"],
            )

        self.assertEqual(result["backend"], "local-engine")
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["retrieval_mode"], "files_first")
        self.assertEqual(result["data"]["chunks"][0]["source_file"], "133-小儿药证直诀.txt")

    def test_retrieval_hybrid_fallback_degrades_to_files_first_when_dense_local_fails(self) -> None:
        class FakeRetrievalEngine:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def search_hybrid(self, **kwargs):
                self.calls.append(kwargs)
                if kwargs.get("search_mode") == "files_first":
                    return {
                        "retrieval_mode": "files_first",
                        "chunks": [
                            {
                                "text": "四君子汤用于脾胃气虚。",
                                "source_file": "093-时方歌括.txt",
                                "source_page": 10,
                                "score": 0.91,
                            }
                        ],
                        "total": 1,
                        "warnings": [],
                    }
                raise RuntimeError("embedding_request_failed")

        fake_engine = FakeRetrievalEngine()

        with (
            patch("tools.tcm_service_client._post", side_effect=RuntimeError("retrieval_down")),
            patch("tools.tcm_service_client.get_retrieval_engine", return_value=fake_engine),
        ):
            result = call_retrieval_hybrid(
                query="四君子汤和六君子汤的区别",
                top_k=4,
                candidate_k=12,
                enable_rerank=True,
                search_mode="hybrid",
            )

        self.assertEqual(result["backend"], "local-engine")
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["retrieval_mode"], "files_first")
        self.assertEqual(len(fake_engine.calls), 2)
        self.assertEqual(fake_engine.calls[1]["search_mode"], "files_first")
        self.assertIn("local_dense_fallback_failed:embedding_request_failed", result["data"]["warnings"])

    def test_case_qa_fallback_uses_local_retrieval_engine(self) -> None:
        fake_engine = type(
            "FakeRetrievalEngine",
            (),
            {
                "search_case_qa": lambda self, **kwargs: {
                    "retrieval_mode": "case_qa_local",
                    "chunks": [
                        {
                            "document": "主诉: 胁肋胀痛",
                            "answer": "诊断: 肝郁脾虚证；方剂: 逍遥散。",
                            "collection": "tcm_shard_0",
                            "score": 0.88,
                        }
                    ],
                    "total": 1,
                    "warnings": [],
                }
            },
        )()

        with (
            patch("tools.tcm_service_client._post", side_effect=RuntimeError("retrieval_down")),
            patch("tools.tcm_service_client.get_retrieval_engine", return_value=fake_engine),
        ):
            result = call_retrieval_case_qa(
                query="胁肋胀痛 口苦 失眠",
                top_k=3,
                candidate_k=12,
            )

        self.assertEqual(result["backend"], "local-engine")
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["retrieval_mode"], "case_qa_local")
        self.assertIn("逍遥散", result["data"]["chunks"][0]["answer"])

    def test_service_health_snapshot_skips_sidecar_probe_in_local_mode(self) -> None:
        with patch("tools.tcm_service_client._health", side_effect=AssertionError("should not probe")):
            snapshot = service_health_snapshot()

        self.assertEqual(snapshot["execution_mode"], "local")
        self.assertTrue(snapshot["sidecar_probe_skipped"])
        self.assertEqual(snapshot["graph_backend"], "local-engine")

    def test_sidecar_mode_defaults_to_local_real_engine_fallback(self) -> None:
        fake_engine = type(
            "FakeGraphEngine",
            (),
            {
                "entity_lookup": lambda self, name, top_k=12, predicate_allowlist=None, predicate_blocklist=None: {
                    "entity": {"canonical_name": name, "entity_type": "formula"},
                    "relations": [{"predicate": "使用药材", "target": "熟地黄"}],
                    "total": 1,
                }
            },
        )()

        with (
            patch.dict("os.environ", {"TCM_SERVICE_MODE": "sidecar"}, clear=False),
            patch("tools.tcm_service_client._post", side_effect=RuntimeError("graph_down")),
            patch("tools.tcm_service_client.get_graph_engine", return_value=fake_engine),
        ):
            result = call_graph_entity_lookup("六味地黄丸", top_k=6)

        self.assertEqual(result["backend"], "local-fallback")
        self.assertEqual(result["code"], 0)
        self.assertIn("graph-service unavailable", result["warning"])


if __name__ == "__main__":
    unittest.main()
