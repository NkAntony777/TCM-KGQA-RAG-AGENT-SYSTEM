from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.tcm_evidence_tools import EvidenceNavigator


class FakeAliasService:
    def detect_entities(self, text: str, *, limit: int = 3) -> list[str]:
        return ["六味地黄丸"] if "六味地黄丸" in text else []

    def expand_query_with_aliases(self, query: str, **kwargs) -> str:
        return f"{query} 地黄丸 六味丸" if "六味地黄丸" in query else query

    def alias_relations(self, entity_name: str, *, max_items: int = 6):
        if entity_name != "六味地黄丸":
            return []
        return [
            SimpleNamespace(
                entity="六味地黄丸",
                alias="地黄丸",
                source_book="小儿药证直诀",
                source_chapter="卷下",
                source_text="六味地黄丸，一名地黄丸。",
                support=2,
            )
        ]


class EvidenceNavigatorSourceLiteTests(unittest.TestCase):
    def test_book_read_uses_source_lite_retrieval_and_filters_book(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "六味地黄丸，治肾阴不足。",
                        "score": 0.92,
                    },
                    {
                        "source_file": "医方集解.txt",
                        "source_page": 12,
                        "text": "逍遥散用于肝郁血虚。",
                        "score": 0.95,
                    },
                ]
            },
        }

        with patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload) as mock_hybrid:
            result = EvidenceNavigator().read_evidence_path(
                path="book://小儿药证直诀/*",
                query="六味地黄丸 出处 原文",
                top_k=4,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["source_book"], "小儿药证直诀")
        self.assertEqual(mock_hybrid.call_args.kwargs["candidate_k"], 8)
        self.assertEqual(mock_hybrid.call_args.kwargs["enable_rerank"], False)
        self.assertEqual(mock_hybrid.call_args.kwargs["search_mode"], "files_first")
        self.assertEqual(mock_hybrid.call_args.kwargs["allowed_file_path_prefixes"], ["classic://", "sample://"])

    def test_book_read_can_use_graph_source_hint_to_narrow_query(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "六味地黄丸，治肾阴不足。",
                        "score": 0.92,
                    }
                ]
            },
        }

        with patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload) as mock_hybrid:
            EvidenceNavigator().read_evidence_path(
                path="book://小儿药证直诀/*",
                query="六味地黄丸 出处 原文",
                source_hint="使用药材: 熟地黄",
                top_k=4,
            )

        self.assertIn("熟地黄", mock_hybrid.call_args.kwargs["query"])
        self.assertEqual(mock_hybrid.call_args.kwargs["allowed_file_path_prefixes"], ["classic://", "sample://"])

    def test_book_read_expands_query_with_aliases_for_old_formula_names(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "地黄丸，治肾怯失音囟开不合。",
                        "score": 0.92,
                    }
                ]
            },
        }

        with (
            patch("tools.tcm_evidence_tools.get_runtime_alias_service", return_value=FakeAliasService()),
            patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload) as mock_hybrid,
        ):
            EvidenceNavigator().read_evidence_path(
                path="book://小儿药证直诀/*",
                query="六味地黄丸 出处 原文",
                top_k=4,
            )

        self.assertIn("地黄丸", mock_hybrid.call_args.kwargs["query"])
        self.assertIn("六味丸", mock_hybrid.call_args.kwargs["query"])

    def test_book_read_normalizes_numeric_filename_prefix_for_source_book(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "133-小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "六味地黄丸，治肾阴不足。",
                        "score": 0.92,
                    }
                ]
            },
        }

        with patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload):
            result = EvidenceNavigator().read_evidence_path(
                path="book://小儿药证直诀/*",
                query="六味地黄丸 出处 原文",
                top_k=4,
            )

        self.assertEqual(result["items"][0]["source_book"], "小儿药证直诀")

    def test_search_evidence_text_prefers_book_scoped_source_lite_channel(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "六味地黄丸，治肾阴不足。",
                        "score": 0.92,
                    }
                ]
            },
        }

        with (
            patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload) as mock_hybrid,
            patch("tools.tcm_evidence_tools.call_retrieval_case_qa") as mock_case_qa,
        ):
            result = EvidenceNavigator().search_evidence_text(
                query="六味地黄丸 出处 原文",
                scope_paths=["book://小儿药证直诀/*"],
                top_k=3,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["source_book"], "小儿药证直诀")
        self.assertEqual(mock_hybrid.call_count, 1)
        self.assertEqual(mock_hybrid.call_args.kwargs["enable_rerank"], False)
        mock_case_qa.assert_not_called()

    def test_alias_path_returns_graph_alias_items(self) -> None:
        with patch("tools.tcm_evidence_tools.get_runtime_alias_service", return_value=FakeAliasService()):
            result = EvidenceNavigator().read_evidence_path(
                path="alias://六味地黄丸",
                query="六味地黄丸有什么别名",
                top_k=4,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["predicate"], "别名")
        self.assertEqual(result["items"][0]["target"], "地黄丸")

    def test_chapter_path_reads_full_section(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "section": {
                    "book_name": "小儿药证直诀",
                    "chapter_title": "卷上",
                    "text": "古籍：小儿药证直诀\n篇名：卷上\n地黄丸主之，治肾虚。",
                    "source_file": "133-小儿药证直诀.txt",
                    "page_number": 1,
                },
                "items": [],
                "count": 2,
            },
        }

        with patch("tools.tcm_evidence_tools.call_retrieval_read_section", return_value=payload) as mock_read:
            result = EvidenceNavigator().read_evidence_path(
                path="chapter://小儿药证直诀/卷上",
                query="六味地黄丸 出处 原文",
                top_k=4,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["source_type"], "chapter")
        self.assertEqual(result["items"][0]["source_chapter"], "卷上")
        self.assertEqual(mock_read.call_args.kwargs["path"], "chapter://小儿药证直诀/卷上")

    def test_list_evidence_paths_includes_chapter_path_from_retrieval_chunks(self) -> None:
        payload = {
            "retrieval_result": {
                "data": {
                    "chunks": [
                        {
                            "source_file": "133-小儿药证直诀.txt",
                            "chapter_title": "卷上",
                            "text": "地黄丸主之，治肾虚。",
                        }
                    ]
                }
            },
            "retrieval_strategy": {"entity_name": "六味地黄丸"},
            "evidence_paths": [],
        }

        result = EvidenceNavigator().list_evidence_paths(
            query="六味地黄丸 出处 原文",
            route_payload=payload,
        )

        self.assertIn("chapter://小儿药证直诀/卷上", result["paths"])

    def test_herb2_book_scope_uses_herb2_prefix_filter(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "HERB2_reference.txt",
                        "source_page": 0,
                        "text": "冰片镇痛与 TRPM8 相关。",
                        "score": 0.92,
                    }
                ]
            },
        }

        with patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload) as mock_hybrid:
            result = EvidenceNavigator().read_evidence_path(
                path="book://HERB2/*",
                query="冰片 TRPM8 机制",
                top_k=4,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(mock_hybrid.call_args.kwargs["allowed_file_path_prefixes"], ["herb2://"])
        self.assertEqual(mock_hybrid.call_args.kwargs["search_mode"], "files_first")


if __name__ == "__main__":
    unittest.main()
