from __future__ import annotations

import json
import unittest

from services.qa_service.engine import QAService
from services.qa_service.evidence_selector import select_evidence_for_answer
from services.qa_service.models import QAServiceSettings
from services.qa_service.prompts import _build_grounded_system_prompt, _build_grounded_user_prompt
from tests.fakes import FakeAnswerGenerator, FakeRouteTool


def _make_factual_evidence(count: int) -> list[dict[str, object]]:
    return [
        {
            "evidence_type": "factual_grounding",
            "source_type": "graph" if i % 2 == 0 else "doc",
            "source": f"source-{i}",
            "source_book": "小儿药证直诀",
            "source_chapter": "卷下",
            "predicate": "使用药材",
            "target": f"药材-{i}",
            "snippet": f"这是一段很长的原文摘录，用于测试全证据模式是否会截断。药材-{i} 的功效非常重要。" + "x" * 300,
            "score": 0.9 - i * 0.01,
        }
        for i in range(count)
    ]


def _make_case_references(count: int) -> list[dict[str, object]]:
    return [
        {
            "evidence_type": "case_reference",
            "source_type": "case_qa",
            "source": f"case-{i}",
            "document": f"医案-{i}",
            "snippet": f"病例摘要内容，用于测试全证据模式。" + "y" * 200,
        }
        for i in range(count)
    ]


class TestSelectEvidenceForAnswerFullEvidenceMode(unittest.TestCase):
    def test_full_evidence_mode_returns_all_candidates(self) -> None:
        factual = _make_factual_evidence(12)
        cases = _make_case_references(5)
        result = select_evidence_for_answer(
            query="六味地黄丸的组成",
            payload={
                "query_analysis": {"dominant_intent": "formula_composition"},
                "retrieval_strategy": {"intent": "formula_composition", "entity_name": "六味地黄丸"},
            },
            mode="quick",
            factual_evidence=factual,
            case_references=cases,
            evidence_paths=["entity://六味地黄丸/使用药材"],
            full_evidence_mode=True,
        )
        self.assertEqual(len(result["selected_cards"]), 17)
        self.assertIn("selector_mode:full_evidence", result["selection_notes"])

    def test_full_evidence_mode_preserves_long_excerpts(self) -> None:
        factual = _make_factual_evidence(1)
        result = select_evidence_for_answer(
            query="六味地黄丸的组成",
            payload={
                "query_analysis": {"dominant_intent": "formula_composition"},
                "retrieval_strategy": {"intent": "formula_composition", "entity_name": "六味地黄丸"},
            },
            mode="quick",
            factual_evidence=factual,
            case_references=[],
            evidence_paths=[],
            full_evidence_mode=True,
        )
        card = result["selected_cards"][0]
        excerpt = str(card.get("excerpt", ""))
        self.assertGreater(len(excerpt), 300)
        self.assertIn("x" * 50, excerpt)

    def test_compact_mode_limits_candidates(self) -> None:
        factual = _make_factual_evidence(20)
        result = select_evidence_for_answer(
            query="六味地黄丸的组成",
            payload={
                "query_analysis": {"dominant_intent": "formula_composition"},
                "retrieval_strategy": {"intent": "formula_composition", "entity_name": "六味地黄丸"},
            },
            mode="quick",
            factual_evidence=factual,
            case_references=[],
            evidence_paths=[],
            full_evidence_mode=False,
        )
        self.assertLessEqual(len(result["selected_cards"]), 10)


class TestGroundedPromptsFullEvidenceMode(unittest.TestCase):
    def test_system_prompt_mentions_full_evidence(self) -> None:
        prompt = _build_grounded_system_prompt(mode="quick", full_evidence_mode=True)
        self.assertIn("全证据模式", prompt)
        self.assertIn("充分阅读", prompt)

    def test_user_prompt_includes_all_evidence_in_full_mode(self) -> None:
        factual = _make_factual_evidence(8)
        cases = _make_case_references(2)
        selected = select_evidence_for_answer(
            query="六味地黄丸的组成",
            payload={
                "query_analysis": {"dominant_intent": "formula_composition"},
                "retrieval_strategy": {"intent": "formula_composition", "entity_name": "六味地黄丸"},
            },
            mode="quick",
            factual_evidence=factual,
            case_references=cases,
            evidence_paths=[],
            full_evidence_mode=True,
        )
        prompt = _build_grounded_user_prompt(
            query="六味地黄丸的组成",
            payload={
                "query_analysis": {"dominant_intent": "formula_composition"},
                "retrieval_strategy": {"intent": "formula_composition", "entity_name": "六味地黄丸"},
            },
            mode="quick",
            factual_evidence=factual,
            evidence_groups={"structured": [], "documentary": [], "other": []},
            case_references=cases,
            citations=[],
            notes=[],
            book_citations=[],
            deep_trace=[],
            evidence_limit=4,
            selected_evidence=selected,
            full_evidence_mode=True,
        )
        self.assertIn("完整证据卡（共 10 条）", prompt)
        self.assertIn("药材-0", prompt)
        self.assertIn("药材-7", prompt)
        self.assertIn("医案-0", prompt)


class TestQAServiceFullEvidenceMode(unittest.IsolatedAsyncioTestCase):
    async def test_answer_uses_full_evidence_in_prompt(self) -> None:
        payload = {
            "route": "graph",
            "route_reason": "formula keyword matched",
            "status": "ok",
            "final_route": "graph",
            "executed_routes": ["graph"],
            "query_analysis": {"dominant_intent": "formula_composition"},
            "retrieval_strategy": {
                "intent": "formula_composition",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite"],
            },
            "evidence_paths": ["entity://六味地黄丸/使用药材"],
            "graph_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "entity": {"canonical_name": "六味地黄丸", "entity_type": "formula"},
                    "relations": [
                        {"predicate": "使用药材", "target": "熟地黄", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.91},
                        {"predicate": "使用药材", "target": "山茱萸", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.9},
                        {"predicate": "使用药材", "target": "山药", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.89},
                        {"predicate": "使用药材", "target": "泽泻", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.88},
                        {"predicate": "使用药材", "target": "牡丹皮", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.87},
                        {"predicate": "使用药材", "target": "茯苓", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.86},
                    ],
                },
            },
        }
        answer_generator = FakeAnswerGenerator("组成包括熟地黄、山茱萸等。")
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=answer_generator,
            settings=QAServiceSettings(full_evidence_mode=True),
        )

        result = await service.answer("六味地黄丸的组成是什么", mode="quick", top_k=12)

        self.assertEqual(result["mode"], "quick")
        self.assertEqual(len(answer_generator.calls), 1)
        user_prompt = answer_generator.calls[0]["user_prompt"]
        self.assertIn("完整证据卡", user_prompt)
        self.assertIn("熟地黄", user_prompt)
        self.assertIn("山茱萸", user_prompt)
        self.assertIn("山药", user_prompt)
        self.assertIn("泽泻", user_prompt)
        self.assertIn("牡丹皮", user_prompt)
        self.assertIn("茯苓", user_prompt)

    async def test_stream_answer_respects_per_request_full_evidence_flag(self) -> None:
        payload = {
            "route": "graph",
            "route_reason": "formula keyword matched",
            "status": "ok",
            "final_route": "graph",
            "executed_routes": ["graph"],
            "query_analysis": {"dominant_intent": "formula_composition"},
            "retrieval_strategy": {
                "intent": "formula_composition",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite"],
            },
            "evidence_paths": ["entity://六味地黄丸/使用药材"],
            "graph_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "entity": {"canonical_name": "六味地黄丸", "entity_type": "formula"},
                    "relations": [
                        {"predicate": "使用药材", "target": "熟地黄", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.91},
                    ],
                },
            },
        }
        answer_generator = FakeAnswerGenerator("组成包括熟地黄。")
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=answer_generator,
            settings=QAServiceSettings(full_evidence_mode=False),
        )

        result = await service.answer(
            "六味地黄丸的组成是什么", mode="quick", top_k=12, full_evidence_mode=True
        )

        self.assertEqual(result["mode"], "quick")
        user_prompt = answer_generator.calls[0]["user_prompt"]
        self.assertIn("完整证据卡", user_prompt)


class TestQAServiceSettingsDefaults(unittest.TestCase):
    def test_default_settings_have_full_evidence_mode_disabled(self) -> None:
        settings = QAServiceSettings()
        self.assertFalse(settings.full_evidence_mode)
        self.assertEqual(settings.max_factual_evidence, 6)
        self.assertEqual(settings.max_case_references, 3)

    def test_settings_can_enable_full_evidence_mode(self) -> None:
        settings = QAServiceSettings(full_evidence_mode=True, max_factual_evidence=200, max_case_references=100)
        self.assertTrue(settings.full_evidence_mode)
        self.assertEqual(settings.max_factual_evidence, 200)
        self.assertEqual(settings.max_case_references, 100)


if __name__ == "__main__":
    unittest.main()
