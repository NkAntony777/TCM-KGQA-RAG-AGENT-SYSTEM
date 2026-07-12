from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import unittest
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat as chat_module
from api import qa as qa_module
from services.common.medical_guard import RiskLevel, assess_query
from services.qa_service import engine as engine_module
from services.qa_service.engine import QAService
from services.qa_service.exceptions import QueryEmptyError
from services.qa_service.helpers import _safe_json_loads
from services.qa_service.prompts import _build_grounded_user_prompt
from tests.fakes import FakeAnswerGenerator, FakeEvidenceNavigator, FakeRouteTool


def _prompt(
    *,
    query: str = "六味地黄丸的组成是什么",
    factual_evidence: list[dict[str, Any]] | None = None,
    evidence_groups: dict[str, list[dict[str, Any]]] | None = None,
    case_references: list[dict[str, Any]] | None = None,
    full_evidence_mode: bool = False,
) -> str:
    return _build_grounded_user_prompt(
        query=query,
        payload={
            "retrieval_strategy": {
                "intent": "formula_composition",
                "entity_name": "六味地黄丸",
            },
            "query_analysis": {"dominant_intent": "formula_composition"},
        },
        mode="quick",
        factual_evidence=factual_evidence or [],
        evidence_groups=evidence_groups or {},
        case_references=case_references or [],
        citations=[],
        notes=[],
        book_citations=[],
        deep_trace=[],
        evidence_limit=4,
        full_evidence_mode=full_evidence_mode,
    )


class QAAdvancedCoverageTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_qa_service_returns_single_instance_under_concurrent_calls(self) -> None:
        class FakeSingletonService:
            created = 0
            created_lock = threading.Lock()

            def __init__(self) -> None:
                with self.created_lock:
                    type(self).created += 1

        original_singleton = engine_module._qa_service
        original_class = engine_module.QAService
        engine_module._qa_service = None
        engine_module.QAService = FakeSingletonService
        barrier = threading.Barrier(50)

        def call_service():
            barrier.wait(timeout=5)
            return engine_module.get_qa_service()

        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                instances = await asyncio.gather(
                    *(loop.run_in_executor(executor, call_service) for _ in range(50))
                )
            self.assertTrue(all(instance is instances[0] for instance in instances))
            self.assertEqual(FakeSingletonService.created, 1)
        finally:
            engine_module._qa_service = original_singleton
            engine_module.QAService = original_class

    def test_grounded_prompt_with_empty_factual_evidence(self) -> None:
        prompt = _prompt(factual_evidence=[], evidence_groups={}, case_references=[])
        self.assertIn("当前没有事实证据", prompt)
        self.assertIn("事实证据摘要：", prompt)

    def test_grounded_prompt_with_empty_case_references(self) -> None:
        evidence = [
            {
                "source_type": "graph",
                "source": "entity://六味地黄丸/使用药材",
                "predicate": "使用药材",
                "target": "熟地黄",
                "source_book": "小儿药证直诀",
                "source_chapter": "卷下",
            }
        ]
        prompt = _prompt(
            factual_evidence=evidence,
            evidence_groups={"structured": evidence},
            case_references=[],
        )
        self.assertIn("结构化图谱证据", prompt)
        self.assertIn("使用药材:熟地黄", prompt)
        self.assertNotIn("案例参考：", prompt)

    def test_grounded_prompt_truncates_very_long_evidence_snippet(self) -> None:
        long_snippet = "熟" * 12_050
        evidence = [
            {
                "source_type": "doc",
                "source": "book://小儿药证直诀/卷下",
                "snippet": long_snippet,
            }
        ]
        prompt = _prompt(
            query="请给出六味地黄丸组成中熟地黄相关原文",
            factual_evidence=evidence,
            evidence_groups={"documentary": evidence},
            case_references=[],
            full_evidence_mode=True,
        )
        self.assertIn("熟" * 10_000, prompt)
        self.assertNotIn("熟" * 10_001, prompt)

    def test_grounded_prompt_handles_evidence_missing_optional_fields(self) -> None:
        evidence = [{}]
        prompt = _prompt(
            factual_evidence=evidence,
            evidence_groups={"structured": evidence},
            case_references=[],
        )
        self.assertIn("[unknown] unknown | 命中相关证据", prompt)

    def test_post_qa_answer_whitespace_query_returns_400(self) -> None:
        test_case = self

        class FakeQAService:
            async def answer(self, query: str, *, mode: str, top_k: int):
                test_case.assertEqual(query, "   ")
                test_case.assertEqual(mode, "quick")
                test_case.assertEqual(top_k, 12)
                raise QueryEmptyError("query_empty")

        original_get_qa_service = qa_module.get_qa_service
        try:
            qa_module.get_qa_service = lambda: FakeQAService()
            app = FastAPI()
            app.include_router(qa_module.router)
            response = TestClient(app).post(
                "/qa/answer",
                json={"query": "   ", "mode": "quick", "top_k": 12},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], "query_empty")
        finally:
            qa_module.get_qa_service = original_get_qa_service

    def test_post_chat_with_invalid_session_id_returns_validation_error(self) -> None:
        app = FastAPI()
        app.include_router(chat_module.router)
        response = TestClient(app).post(
            "/chat",
            json={
                "message": "六味地黄丸由哪些药材组成",
                "session_id": "",
                "stream": False,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertTrue(
            any("session_id" in item.get("loc", []) for item in response.json()["detail"])
        )

    def test_safe_json_loads_malformed_json_returns_default_dict(self) -> None:
        default = {"status": "fallback"}
        self.assertIs(_safe_json_loads("{bad json", default=default), default)

    def test_assess_query_refuses_harmful_tcm_dosage_query(self) -> None:
        result = assess_query("我想用熟地黄配六味地黄丸，每次用量多少克最合适？")
        self.assertTrue(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)
        self.assertTrue(result.refuse_response)

    async def test_stream_answer_refused_query_yields_guard_refused_result(self) -> None:
        service = QAService(
            route_tool=FakeRouteTool({}),
            answer_generator=FakeAnswerGenerator("unused"),
            evidence_navigator=FakeEvidenceNavigator(),
        )
        events = [
            event
            async for event in service.stream_answer(
                "六味地黄丸每次吃多少克最合适？",
                mode="quick",
                top_k=12,
            )
        ]
        self.assertEqual([event["type"] for event in events], ["qa_mode", "token", "done", "result"])
        result = events[-1]["result"]
        self.assertEqual(result["status"], "guard_refused")
        self.assertEqual(result["generation_backend"], "medical_guard")
        self.assertEqual(result["route"]["status"], "guard_refused")
        self.assertIn("不能提供个体化用药方案", result["answer"])


if __name__ == "__main__":
    unittest.main()
