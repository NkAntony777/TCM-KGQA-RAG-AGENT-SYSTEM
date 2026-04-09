from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from services.qa_service.engine import QAService
from services.qa_service.prompts import _build_grounded_user_prompt
from tools.tcm_route_tool import TCMRouteSearchTool


class FakeAnswerGenerator:
    def __init__(self, response: str) -> None:
        self.response = response

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self.response


def _large_route_payload() -> dict[str, object]:
    graph_relations = [
        {
            "predicate": "功效",
            "target": f"疏肝解郁-{index}",
            "source_book": "医方集解",
            "source_chapter": f"卷{index}",
            "source_text": "逍遥散用于肝郁血虚、脾失健运之证。" * 6,
            "score": 0.9,
        }
        for index in range(24)
    ]
    retrieval_chunks = [
        {
            "source_file": "医方集解.txt",
            "source_page": index + 1,
            "text": ("逍遥散与柴胡疏肝散均可用于肝郁证，但前者兼顾养血健脾，后者更偏行气止痛。") * 8,
            "score": 0.85,
            "rerank_score": 0.95,
        }
        for index in range(12)
    ]
    return {
        "route": "hybrid",
        "route_reason": "compare_entities_forced_hybrid",
        "status": "ok",
        "final_route": "hybrid",
        "executed_routes": ["graph", "retrieval"],
        "query_analysis": {
            "dominant_intent": "formula_origin",
            "compare_entities": ["逍遥散", "柴胡疏肝散"],
        },
        "retrieval_strategy": {
            "intent": "formula_origin",
            "preferred_route": "hybrid",
            "entity_name": "逍遥散",
            "compare_entities": ["逍遥散", "柴胡疏肝散"],
            "sources": ["graph_sqlite", "classic_docs"],
        },
        "evidence_paths": [
            "entity://逍遥散/功效",
            "entity://柴胡疏肝散/功效",
            "qa://逍遥散/similar",
        ],
        "service_trace_ids": {"graph": "g1", "retrieval": "r1", "case_qa": None},
        "service_backends": {"graph": "graph-service", "retrieval": "retrieval-service", "case_qa": None},
        "graph_result": {
            "code": 0,
            "message": "ok",
            "trace_id": "g1",
            "backend": "graph-service",
            "data": {
                "entity": {"canonical_name": "逍遥散", "entity_type": "formula"},
                "relations": graph_relations,
            },
        },
        "retrieval_result": {
            "code": 0,
            "message": "ok",
            "trace_id": "r1",
            "backend": "retrieval-service",
            "data": {
                "chunks": retrieval_chunks,
            },
        },
    }


class RouteToolLargeOutputTests(unittest.TestCase):
    def test_route_tool_keeps_large_payload_as_valid_json(self) -> None:
        tool = TCMRouteSearchTool()

        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value=_large_route_payload()["graph_result"],
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value=_large_route_payload()["retrieval_result"],
            ),
        ):
            raw = tool._run("请比较逍遥散和柴胡疏肝散的功效与适用证候，并结合古籍或教材出处说明。", top_k=12)

        parsed = json.loads(raw)
        self.assertGreater(len(raw), 10000)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["final_route"], "hybrid")
        self.assertEqual(parsed["executed_routes"], ["graph", "retrieval"])


class QAServiceLargeOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_deep_mode_accepts_large_route_output_without_quick_fallback(self) -> None:
        route_payload = _large_route_payload()
        route_output = json.dumps(route_payload, ensure_ascii=False, indent=2)
        self.assertGreater(len(route_output), 10000)

        class FakeRouteTool:
            def _run(self, query: str, top_k: int = 12):
                return route_output

        service = QAService(
            route_tool=FakeRouteTool(),
            answer_generator=FakeAnswerGenerator("Deep planner回答：逍遥散偏养血健脾，柴胡疏肝散偏行气止痛。"),
        )

        result = await service.answer(
            "请比较逍遥散和柴胡疏肝散的功效与适用证候，并结合古籍或教材出处说明。",
            mode="deep",
            top_k=12,
        )

        self.assertEqual(result["mode"], "deep")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["generation_backend"], "planner_llm")
        self.assertEqual(result["route"]["final_route"], "hybrid")
        self.assertGreaterEqual(len(result["factual_evidence"]), 1)
        self.assertIn("Deep planner回答", result["answer"])


class GroundedPromptCompactionTests(unittest.TestCase):
    def test_grounded_prompt_compacts_non_source_query(self) -> None:
        prompt = _build_grounded_user_prompt(
            query="逍遥散的功效与主治是什么？",
            payload={"retrieval_strategy": {"intent": "formula_efficacy", "entity_name": "逍遥散"}},
            mode="quick",
            factual_evidence=[
                {
                    "source_type": "graph",
                    "source": "医方集解#12",
                    "source_book": "医方集解",
                    "source_chapter": "卷三",
                    "anchor_entity": "逍遥散",
                    "predicate": "功效",
                    "target": "疏肝健脾",
                    "snippet": "逍遥散用于肝郁血虚、脾失健运之证。" * 12,
                }
            ],
            case_references=[],
            citations=["医方集解/卷三"],
            notes=[],
            book_citations=["医方集解/卷三"],
            deep_trace=[],
            evidence_limit=4,
        )

        self.assertIn("事实证据摘要：", prompt)
        self.assertIn("逍遥散 -> 功效:疏肝健脾", prompt)
        self.assertNotIn("摘录:", prompt)
        self.assertNotIn(("逍遥散用于肝郁血虚、脾失健运之证。" * 3), prompt)

    def test_grounded_prompt_keeps_excerpt_for_source_query(self) -> None:
        prompt = _build_grounded_user_prompt(
            query="逍遥散出自哪本书？请给出处原文。",
            payload={"retrieval_strategy": {"intent": "formula_origin", "entity_name": "逍遥散"}},
            mode="deep",
            factual_evidence=[
                {
                    "source_type": "chapter",
                    "source": "医方集解/卷三",
                    "source_book": "医方集解",
                    "source_chapter": "卷三",
                    "snippet": "逍遥散，治肝郁血虚，脾弱不运。" * 6,
                }
            ],
            case_references=[],
            citations=["医方集解/卷三"],
            notes=[],
            book_citations=["医方集解/卷三"],
            deep_trace=[],
            evidence_limit=6,
        )

        self.assertIn("摘录:", prompt)
        self.assertIn("允许引用上面的出处摘录", prompt)


if __name__ == "__main__":
    unittest.main()
