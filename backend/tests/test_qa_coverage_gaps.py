from __future__ import annotations

import unittest
from typing import Any

from services.qa_service.action_executor import _can_parallelize_actions, _execute_action
from services.qa_service.engine import QAService
from services.qa_service.answer_generator import _can_retry_generation
from services.qa_service.evidence_selector import (
    SCORE_DOC_SOURCE_TYPE,
    SCORE_FACET_MATCH,
    SCORE_HAS_EXCERPT,
    SCORE_PATH_HAS_SCHEME,
    SCORE_QUERY_TERM_MATCH,
    SCORE_SOURCE_LABEL_KNOWN,
    SCORE_STRUCTURED_TYPE,
    _score_item,
    select_evidence_for_answer,
)
from services.qa_service.exceptions import LLMAuthError
from services.qa_service.models import QAServiceSettings
from tests.fakes import FakeAnswerGenerator, FakeEvidenceNavigator, FakeRouteTool, FakeSequentialAnswerGenerator


def _comp_payload() -> dict[str, Any]:
    return {
        "route": "graph",
        "route_reason": "test",
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


class FakeTimeoutRecordingGenerator:
    """FakeSequentialAnswerGenerator that records timeout_seconds at each call."""
    def __init__(self, responses: list[str | Exception], *, timeout_seconds: float = 60.0) -> None:
        self.responses = list(responses)
        self.timeout_seconds = timeout_seconds
        self.timeout_at_call: list[float] = []
        self.calls: list[dict[str, str]] = []

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.timeout_at_call.append(self.timeout_seconds)
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self.responses:
            raise RuntimeError("no_more_responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class QACoverageGapTests(unittest.IsolatedAsyncioTestCase):

    # ── 1. LLM retry with timeout escalation ──────────────────────────────

    async def test_llm_retry_escalates_timeout_on_deep_mode(self) -> None:
        gen = FakeTimeoutRecordingGenerator(
            [RuntimeError("first_timeout"), "Deep success answer"],
            timeout_seconds=30.0,
        )
        service = QAService(
            route_tool=FakeRouteTool(_comp_payload()),
            answer_generator=gen,
        )
        result = await service.answer("六味地黄丸的组成是什么", mode="deep", top_k=12)

        self.assertEqual(result["generation_backend"], "planner_llm")
        self.assertIn("Deep success answer", result["answer"])
        self.assertEqual(len(gen.calls), 2)
        # deep plan: [max(30,60)=60, max(60,120)=120]
        self.assertEqual(len(gen.timeout_at_call), 2)
        self.assertAlmostEqual(gen.timeout_at_call[0], 60.0)
        self.assertAlmostEqual(gen.timeout_at_call[1], 120.0)

    # ── 2. Deep → quick → deterministic when both fail ───────────────────

    async def test_deep_falls_to_deterministic_when_quick_fallback_also_fails(self) -> None:
        gen = FakeSequentialAnswerGenerator(
            [RuntimeError("deep_1"), RuntimeError("deep_2"), RuntimeError("quick_fallback")]
        )
        service = QAService(
            route_tool=FakeRouteTool(_comp_payload()),
            answer_generator=gen,
        )
        result = await service.answer("六味地黄丸的组成是什么", mode="deep", top_k=12)

        self.assertEqual(result["generation_backend"], "planner_deterministic_fallback")
        self.assertEqual(len(gen.calls), 3)
        self.assertTrue(any("deep_quick_llm_fallback" in n for n in result["notes"]))

    # ── 3. LLMAuthError stops retry ──────────────────────────────────────

    async def test_llm_auth_error_does_not_retry(self) -> None:
        gen = FakeAnswerGenerator(LLMAuthError("invalid_api_key"))
        service = QAService(
            route_tool=FakeRouteTool(_comp_payload()),
            answer_generator=gen,
        )
        result = await service.answer("六味地黄丸的组成是什么", mode="quick", top_k=12)

        self.assertEqual(result["generation_backend"], "deterministic_quick_fallback")
        self.assertEqual(len(gen.calls), 1)
        self.assertFalse(any("quick_llm_retry" in n for n in result.get("notes", [])))

    def test_can_retry_generation_returns_false_for_auth_error(self) -> None:
        self.assertFalse(_can_retry_generation(LLMAuthError("invalid")))

    # ── 4. ConnectionError retries ───────────────────────────────────────

    async def test_connection_error_triggers_retry(self) -> None:
        gen = FakeSequentialAnswerGenerator(
            [ConnectionError("connection_reset"), "Quick success answer"]
        )
        service = QAService(
            route_tool=FakeRouteTool(_comp_payload()),
            answer_generator=gen,
        )
        result = await service.answer("六味地黄丸的组成是什么", mode="quick", top_k=12)

        self.assertEqual(result["generation_backend"], "grounded_llm")
        self.assertIn("Quick success answer", result["answer"])
        self.assertEqual(len(gen.calls), 2)

    def test_can_retry_generation_returns_true_for_connection_error(self) -> None:
        self.assertTrue(_can_retry_generation(ConnectionError("reset")))

    # ── 5. _score_item uses named constants ──────────────────────────────

    def test_score_item_uses_named_constants(self) -> None:
        item: dict[str, Any] = {
            "source_type": "graph",
            "source_book": "伤寒论",
            "source_chapter": "辨太阳病",
            "predicate": "功效",
            "target": "疏肝健脾",
            "snippet": "疏肝健脾是核心功效",
            "source_text": "功效为疏肝健脾。",
            "score": 0.5,
            "evidence_path": "entity://逍遥散/功效",
        }
        score = _score_item(
            item,
            facet="efficacy",
            required_facets=["efficacy"],
            query_terms={"疏肝健脾"},
        )
        expected = (
            0.5
            + SCORE_FACET_MATCH
            + SCORE_QUERY_TERM_MATCH
            + SCORE_SOURCE_LABEL_KNOWN
            + SCORE_HAS_EXCERPT
            + SCORE_STRUCTURED_TYPE
            + SCORE_PATH_HAS_SCHEME
        )
        self.assertAlmostEqual(score, expected)

        doc_item: dict[str, Any] = {
            "source_type": "doc",
            "source": "some_file.txt",
            "snippet": "text snippet",
            "score": 0.3,
        }
        score2 = _score_item(
            doc_item, facet="general", required_facets=["efficacy"], query_terms=set()
        )
        expected2 = 0.3 + SCORE_SOURCE_LABEL_KNOWN + SCORE_HAS_EXCERPT + SCORE_DOC_SOURCE_TYPE
        self.assertAlmostEqual(score2, expected2)

    # ── 6. _execute_action cache hit / miss ─────────────────────────────

    def test_execute_action_cache_miss_then_hit(self) -> None:
        nav = FakeEvidenceNavigator(
            read_results={
                "entity://test/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://test/*",
                    "status": "ok",
                    "count": 1,
                    "items": [{"snippet": "data", "score": 0.9}],
                }
            },
        )
        settings = QAServiceSettings()
        action: dict[str, Any] = {
            "skill": "read-formula-composition",
            "tool": "read_evidence_path",
            "path": "entity://test/*",
            "query": "组成",
            "top_k": 6,
        }
        cache: dict[str, dict[str, Any]] = {}
        first = _execute_action(evidence_navigator=nav, settings=settings, action=action, request_cache=cache)
        second = _execute_action(evidence_navigator=nav, settings=settings, action=action, request_cache=cache)

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])

    # ── 7. _can_parallelize_actions edge cases ──────────────────────────

    def test_can_parallelize_zero_or_one_action(self) -> None:
        self.assertFalse(_can_parallelize_actions([]))
        self.assertFalse(_can_parallelize_actions([{"skill": "read-formula-origin", "tool": "read_evidence_path", "path": "x", "query": ""}]))

    def test_can_parallelize_two_actions_with_different_keys(self) -> None:
        actions = [
            {"skill": "read-formula-origin", "tool": "read_evidence_path", "path": "entity://A/*", "query": "组成", "scope_paths": []},
            {"skill": "compare-formulas", "tool": "read_evidence_path", "path": "entity://B/*", "query": "功效", "scope_paths": []},
        ]
        self.assertTrue(_can_parallelize_actions(actions))

    def test_cannot_parallelize_actions_with_same_key(self) -> None:
        actions = [
            {"skill": "read-formula-origin", "tool": "read_evidence_path", "path": "entity://A/*", "query": "组成"},
            {"skill": "read-formula-origin", "tool": "read_evidence_path", "path": "entity://A/*", "query": "组成"},
        ]
        self.assertFalse(_can_parallelize_actions(actions))

    def test_cannot_parallelize_unsupported_skill(self) -> None:
        actions = [
            {"skill": "read-formula-origin", "tool": "read_evidence_path", "path": "entity://A/*", "query": "组成"},
            {"skill": "my-custom-skill", "tool": "read_evidence_path", "path": "entity://B/*", "query": "功效"},
        ]
        self.assertFalse(_can_parallelize_actions(actions))

    # ── 8. select_evidence_for_answer compact-mode budget ───────────────

    def test_select_evidence_compact_quick_mode_respects_budget(self) -> None:
        items = []
        for i in range(15):
            items.append({
                "source_type": "graph",
                "source": f"book/ch{i}",
                "snippet": f"item {i}",
                "predicate": "功效",
                "target": f"t{i}",
                "source_book": "book",
                "source_chapter": f"ch{i}",
                "score": 0.5,
                "evidence_path": "entity://test/功效",
            })
        payload: dict[str, Any] = {
            "retrieval_strategy": {"intent": "formula_efficacy", "entity_name": "test"},
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "evidence_paths": ["entity://test/*"],
        }
        result = select_evidence_for_answer(
            query="test的功效是什么",
            payload=payload,
            mode="quick",
            factual_evidence=items,
            case_references=[],
            evidence_paths=["entity://test/*"],
        )
        self.assertLessEqual(len(result["selected_cards"]), 10)
        self.assertIn("selector_budget:10", result["selection_notes"])

    def test_select_evidence_compact_deep_mode_respects_budget(self) -> None:
        items = []
        for i in range(40):
            items.append({
                "source_type": "graph",
                "source": f"book/ch{i}",
                "snippet": f"item {i}",
                "predicate": "功效",
                "target": f"t{i}",
                "source_book": "book",
                "source_chapter": f"ch{i}",
                "score": 0.5,
                "evidence_path": "entity://test/功效",
            })
        payload: dict[str, Any] = {
            "retrieval_strategy": {"intent": "formula_efficacy", "entity_name": "test"},
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "evidence_paths": ["entity://test/*"],
        }
        result = select_evidence_for_answer(
            query="test的功效是什么",
            payload=payload,
            mode="deep",
            factual_evidence=items,
            case_references=[],
            evidence_paths=["entity://test/*"],
        )
        self.assertLessEqual(len(result["selected_cards"]), 24)
        self.assertIn("selector_budget:24", result["selection_notes"])


if __name__ == "__main__":
    unittest.main()
