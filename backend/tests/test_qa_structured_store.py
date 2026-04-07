from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings


class _FakeAliasService:
    def is_available(self) -> bool:
        return True

    def detect_entities(self, text: str, *, limit: int = 3) -> list[str]:
        if "六味地黄丸" in text:
            return ["六味地黄丸"]
        return []

    def aliases_for_entity(self, entity_name: str, *, max_aliases: int = 6, max_depth: int = 2) -> list[str]:
        if entity_name == "六味地黄丸":
            return ["地黄丸", "六味丸"][:max_aliases]
        return []

    def expand_query_with_aliases(
        self,
        query: str,
        *,
        focus_entities: list[str] | None = None,
        max_aliases_per_entity: int = 3,
        max_entities: int = 2,
    ) -> str:
        if "六味地黄丸" in query:
            return f"{query} 地黄丸 六味丸"
        return query


class _FakeJieba:
    def add_word(self, word: str, freq: int = 0) -> None:
        return None

    def cut_for_search(self, text: str):
        if "远行奔走时脚上会起泡" in text:
            return ["远行奔走", "脚上起泡"]
        if "托里消毒饮中的金银花在方剂中起什么作用" in text:
            return ["托里消毒饮", "金银花", "方中作用"]
        return [text]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class StructuredQAIndexTests(unittest.TestCase):
    def test_search_qa_expands_aliases_before_matching(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        qa_input = root / "qa.jsonl"
        case_input = root / "case.jsonl"
        index_path = root / "qa_structured.sqlite"
        _write_jsonl(
            qa_input,
            [
                {
                    "record_id": "qa-1",
                    "collection": "qa",
                    "embedding_id": "legacy-1",
                    "bucket": "origin_qa",
                    "question_type": "origin",
                    "question": "地黄丸出自哪本书？",
                    "answer": "地黄丸出自《小儿药证直诀》。",
                    "formula_candidates": ["地黄丸"],
                    "keywords": ["地黄丸", "出处", "原文"],
                    "symptom_terms": [],
                    "syndrome_terms": [],
                    "search_text": "地黄丸 出处 原文 小儿药证直诀",
                }
            ],
        )
        _write_jsonl(case_input, [])
        index = StructuredQAIndex(
            StructuredQAIndexSettings(
                index_path=index_path,
                qa_input_path=qa_input,
                case_input_path=case_input,
            )
        )
        index.rebuild(batch_size=10)

        with patch(
            "services.retrieval_service.qa_structured_store.get_runtime_alias_service",
            return_value=_FakeAliasService(),
        ):
            rows = index.search_qa("六味地黄丸 出处 原文", top_k=3)
        del index

        self.assertTrue(rows)
        self.assertEqual(rows[0]["record_id"], "qa-1")

    def test_search_qa_uses_jieba_terms_for_long_chinese_questions(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        qa_input = root / "qa.jsonl"
        case_input = root / "case.jsonl"
        index_path = root / "qa_structured.sqlite"
        _write_jsonl(
            qa_input,
            [
                {
                    "record_id": "qa-2",
                    "collection": "qa",
                    "embedding_id": "legacy-2",
                    "bucket": "generic_qa",
                    "question_type": "definition_or_explanation",
                    "question": "远行奔走脚上起泡怎么办？",
                    "answer": "多因摩擦所致，可先休息并保持局部清洁。",
                    "formula_candidates": [],
                    "keywords": ["远行奔走", "脚上起泡"],
                    "symptom_terms": [],
                    "syndrome_terms": [],
                    "search_text": "远行奔走 脚上起泡 摩擦",
                }
            ],
        )
        _write_jsonl(case_input, [])
        index = StructuredQAIndex(
            StructuredQAIndexSettings(
                index_path=index_path,
                qa_input_path=qa_input,
                case_input_path=case_input,
            )
        )
        index.rebuild(batch_size=10)

        with patch("services.retrieval_service.qa_structured_store.jieba", new=_FakeJieba()):
            with patch(
                "services.retrieval_service.qa_structured_store.get_runtime_alias_service",
                return_value=_FakeAliasService(),
            ):
                rows = index.search_qa("为什么远行奔走时脚上会起泡", top_k=3)
        del index

        self.assertTrue(rows)
        self.assertEqual(rows[0]["record_id"], "qa-2")

    def test_search_qa_boosts_formula_role_matches(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        qa_input = root / "qa.jsonl"
        case_input = root / "case.jsonl"
        index_path = root / "qa_structured.sqlite"
        _write_jsonl(
            qa_input,
            [
                {
                    "record_id": "qa-role",
                    "collection": "qa",
                    "embedding_id": "legacy-role",
                    "bucket": "formula_qa",
                    "question_type": "efficacy",
                    "question": "托里消毒饮中金银花有什么作用？",
                    "answer": "金银花在托里消毒饮中有清热解毒、消痈散结之用。",
                    "formula_candidates": ["托里消毒饮", "金银花"],
                    "keywords": ["托里消毒饮", "金银花", "作用", "功效"],
                    "symptom_terms": [],
                    "syndrome_terms": [],
                    "search_text": "托里消毒饮 金银花 方中作用 清热解毒 消痈散结",
                },
                {
                    "record_id": "qa-noise",
                    "collection": "qa",
                    "embedding_id": "legacy-noise",
                    "bucket": "formula_qa",
                    "question_type": "composition",
                    "question": "荆芥甘草防风汤的药物组成是什么？",
                    "answer": "荆芥半两、防风半两、甘草三钱。",
                    "formula_candidates": ["荆芥甘草防风汤"],
                    "keywords": ["组成", "成分"],
                    "symptom_terms": [],
                    "syndrome_terms": [],
                    "search_text": "荆芥甘草防风汤 组成 成分",
                },
            ],
        )
        _write_jsonl(case_input, [])
        index = StructuredQAIndex(
            StructuredQAIndexSettings(
                index_path=index_path,
                qa_input_path=qa_input,
                case_input_path=case_input,
            )
        )
        index.rebuild(batch_size=10)

        with patch("services.retrieval_service.qa_structured_store.jieba", new=_FakeJieba()):
            with patch(
                "services.retrieval_service.qa_structured_store.get_runtime_alias_service",
                return_value=_FakeAliasService(),
            ):
                rows = index.search_qa("托里消毒饮中的金银花在方剂中起什么作用", top_k=3)
        del index

        self.assertTrue(rows)
        self.assertEqual(rows[0]["record_id"], "qa-role")


if __name__ == "__main__":
    unittest.main()
