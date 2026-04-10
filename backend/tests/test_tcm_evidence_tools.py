from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.tcm_evidence_tools import EvidenceNavigator, _filter_items_by_book, _source_scope_specs


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
    def test_filter_items_by_book_matches_normalized_book_label(self) -> None:
        items = [
            {"source": "089-医方论/卷上", "source_book": "089-医方论", "snippet": "六味地黄丸"},
            {"source": "168-保婴撮要/卷下", "source_book": "168-保婴撮要", "snippet": "地黄丸"},
        ]
        filtered = _filter_items_by_book(items, book_name="医方论")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["source_book"], "089-医方论")

    def test_source_scope_specs_normalize_numeric_book_prefix(self) -> None:
        specs = _source_scope_specs(["book://089-医方论/*", "book://医方论/*"])
        self.assertEqual(specs[0][0], "医方论")
        self.assertEqual(len(specs), 1)

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

    def test_search_evidence_text_keeps_chapter_scoped_source_trace_bounded(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "section": {
                    "book_name": "小儿药证直诀",
                    "chapter_title": "卷下",
                    "text": "古籍：小儿药证直诀\n篇名：卷下\n六味地黄丸，治肾怯失音，囟开不合，神不足。",
                    "source_file": "133-小儿药证直诀.txt",
                    "page_number": 42,
                },
                "items": [],
                "count": 1,
            },
        }

        with (
            patch("tools.tcm_evidence_tools.call_retrieval_read_section", return_value=payload) as mock_read,
            patch("tools.tcm_evidence_tools.call_retrieval_hybrid") as mock_hybrid,
            patch("tools.tcm_evidence_tools.call_retrieval_case_qa") as mock_case_qa,
        ):
            result = EvidenceNavigator().search_evidence_text(
                query="六味地黄丸 出处 原文",
                scope_paths=["chapter://小儿药证直诀/卷下", "qa://六味地黄丸/similar"],
                top_k=3,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["source_type"], "chapter")
        self.assertEqual(mock_read.call_count, 1)
        mock_hybrid.assert_not_called()
        mock_case_qa.assert_not_called()

    def test_search_evidence_text_does_not_fan_out_after_book_scoped_source_trace_hit(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "小儿药证直诀.txt",
                        "source_page": 42,
                        "chapter_title": "卷下",
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
                scope_paths=["book://小儿药证直诀/*", "qa://六味地黄丸/similar"],
                top_k=3,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
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
        self.assertEqual(result["items"][0]["evidence_path"], "chapter://小儿药证直诀/卷上")
        self.assertEqual(result["items"][0]["source_scope_path"], "book://小儿药证直诀/*")
        self.assertEqual(mock_read.call_args.kwargs["path"], "chapter://小儿药证直诀/卷上")

    def test_book_read_exposes_logical_source_trace_metadata(self) -> None:
        payload = {
            "code": 0,
            "message": "ok",
            "backend": "retrieval-service",
            "data": {
                "chunks": [
                    {
                        "source_file": "133-小儿药证直诀.txt",
                        "source_page": 42,
                        "chapter_title": "卷下",
                        "file_path": "classic://小儿药证直诀/0042-00",
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

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["items"][0]["evidence_path"], "chapter://小儿药证直诀/卷下")
        self.assertEqual(result["items"][0]["source_scope_path"], "book://小儿药证直诀/*")
        self.assertEqual(result["items"][0]["file_path"], "classic://小儿药证直诀/0042-00")
        self.assertEqual(result["items"][0]["source_page"], 42)

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

    def test_list_evidence_paths_prioritizes_non_vector_source_paths_before_qa(self) -> None:
        payload = {
            "retrieval_strategy": {"entity_name": "六味地黄丸"},
            "evidence_paths": ["qa://六味地黄丸/similar", "entity://六味地黄丸/*"],
            "graph_result": {
                "data": {
                    "relations": [
                        {
                            "predicate": "出处",
                            "target": "六味地黄丸",
                            "source_book": "小儿药证直诀",
                            "source_chapter": "卷下",
                            "source_text": "六味地黄丸见卷下。",
                        }
                    ]
                }
            },
        }

        result = EvidenceNavigator().list_evidence_paths(
            query="六味地黄丸出自哪本书？请给出处原文。",
            route_payload=payload,
        )

        self.assertEqual(result["paths"][0], "entity://六味地黄丸/*")
        self.assertIn("chapter://小儿药证直诀/卷下", result["paths"])
        self.assertLess(result["paths"].index("chapter://小儿药证直诀/卷下"), result["paths"].index("qa://六味地黄丸/similar"))

    def test_list_evidence_paths_normalizes_graph_book_label_and_skips_file_slug_chapter(self) -> None:
        payload = {
            "retrieval_strategy": {"entity_name": "六味地黄丸"},
            "graph_result": {
                "data": {
                    "relations": [
                        {
                            "predicate": "别名",
                            "target": "地黄丸",
                            "source_book": "089-医方论",
                            "source_chapter": "089-医方论_正文",
                            "source_text": "（即六味地黄丸）",
                        }
                    ]
                }
            },
        }

        result = EvidenceNavigator().list_evidence_paths(
            query="六味地黄丸出自哪本书？请给出处原文。",
            route_payload=payload,
        )

        self.assertIn("book://医方论/*", result["paths"])
        self.assertNotIn("book://089-医方论/*", result["paths"])
        self.assertFalse(any(path.startswith("chapter://医方论/089-医方论_正文") for path in result["paths"]))

    def test_list_evidence_paths_orders_paths_by_logical_priority(self) -> None:
        payload = {
            "evidence_paths": [
                "qa://六味地黄丸/similar",
                "book://小儿药证直诀/*",
                "alias://六味地黄丸",
                "entity://六味地黄丸/*",
                "chapter://小儿药证直诀/%E5%8D%B7%E4%B8%8A",
                "caseqa://六味地黄丸/similar",
                "entity://六味地黄丸/*",
            ],
            "retrieval_strategy": {"entity_name": "六味地黄丸"},
        }

        result = EvidenceNavigator().list_evidence_paths(
            query="六味地黄丸出自哪本书？请给出处原文。",
            route_payload=payload,
        )

        self.assertEqual(
            result["paths"],
            [
                "entity://六味地黄丸/*",
                "alias://六味地黄丸",
                "chapter://小儿药证直诀/卷上",
                "book://小儿药证直诀/*",
                "qa://六味地黄丸/similar",
                "caseqa://六味地黄丸/similar",
            ],
        )

    def test_search_evidence_text_dedupes_duplicate_doc_items(self) -> None:
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
                    },
                    {
                        "source_file": "133-小儿药证直诀.txt",
                        "source_page": 42,
                        "text": "六味地黄丸，治肾阴不足。",
                        "score": 0.91,
                    },
                ]
            },
        }

        with (
            patch("tools.tcm_evidence_tools.call_retrieval_hybrid", return_value=payload),
            patch(
                "tools.tcm_evidence_tools.call_retrieval_case_qa",
                return_value={"code": 0, "message": "ok", "backend": "retrieval-service", "data": {"chunks": []}},
            ),
        ):
            result = EvidenceNavigator().search_evidence_text(
                query="六味地黄丸 出处 原文",
                top_k=2,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["source"], "133-小儿药证直诀.txt#42")

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
