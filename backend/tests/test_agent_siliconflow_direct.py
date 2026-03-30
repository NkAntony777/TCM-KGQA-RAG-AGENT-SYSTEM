from __future__ import annotations

import asyncio
import json
import tempfile
import types
import unittest
from pathlib import Path

from graph.agent import AgentManager


class FakeRouteTool:
    name = "tcm_route_search"

    def _run(self, query: str, top_k: int = 5) -> str:
        return json.dumps(
            {
                "route": "hybrid",
                "route_reason": "unit_test",
                "final_route": "hybrid",
                "status": "ok",
                "executed_routes": ["graph", "retrieval"],
                "degradation": [],
                "service_health": {
                    "graph_service_up": True,
                    "retrieval_service_up": True,
                },
                "service_trace_ids": {
                    "graph": "graph-trace",
                    "retrieval": "retrieval-trace",
                },
                "service_backends": {
                    "graph": "graph-service",
                    "retrieval": "retrieval-service",
                },
                "graph_result": {
                    "code": 0,
                    "data": {
                        "entity": {"canonical_name": "逍遥散"},
                        "relations": [
                            {"predicate": "治疗证候", "target": "肝郁脾虚", "source_book": "和剂局方", "source_chapter": "方剂门"}
                        ],
                    },
                },
                "retrieval_result": {
                    "code": 0,
                    "data": {
                        "chunks": [
                            {
                                "text": "逍遥散用于肝郁血虚、脾失健运之证。",
                                "source_file": "医方集解.txt",
                                "source_page": 12,
                                "score": 0.9,
                            }
                        ]
                    },
                },
            },
            ensure_ascii=False,
        )


class AgentSiliconFlowDirectTests(unittest.TestCase):
    def test_astream_uses_direct_siliconflow_branch(self) -> None:
        test_case = self

        async def collect_events() -> list[dict]:
            with tempfile.TemporaryDirectory() as tmp:
                manager = AgentManager()
                manager.base_dir = Path(tmp)
                manager.tools = [FakeRouteTool()]
                manager._should_use_siliconflow_direct = lambda: True  # type: ignore[method-assign]

                async def fake_stream(self, *, message: str, history: list[dict], route_output: str):
                    test_case.assertIn("逍遥散有什么功效", message)
                    payload = json.loads(route_output)
                    test_case.assertEqual(payload["final_route"], "hybrid")
                    yield {"type": "token", "content": "逍遥散具有疏肝解郁、健脾养血之功。"}
                    yield {"type": "done", "content": "逍遥散具有疏肝解郁、健脾养血之功。"}

                manager._stream_siliconflow_grounded_answer = types.MethodType(fake_stream, manager)

                events: list[dict] = []
                async for event in manager.astream("逍遥散有什么功效", []):
                    events.append(event)
                return events

        events = asyncio.run(collect_events())
        event_types = [item["type"] for item in events]
        self.assertEqual(
            event_types,
            ["tool_start", "tool_end", "route", "evidence", "new_response", "token", "done"],
        )
        self.assertEqual(events[-1]["content"], "逍遥散具有疏肝解郁、健脾养血之功。")


if __name__ == "__main__":
    unittest.main()
