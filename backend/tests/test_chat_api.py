from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from api.chat import ChatRequest, chat
from graph.agent import agent_manager
from graph.session_manager import SessionManager


class ChatApiTests(unittest.TestCase):
    def test_non_stream_chat_uses_qa_engine_segments(self) -> None:
        async def fake_answer(message: str, *, mode: str, top_k: int):
            self.assertEqual(message, "逍遥散有什么功效")
            self.assertEqual(mode, "deep")
            self.assertEqual(top_k, 12)
            return {
                "answer": "逍遥散具有疏肝解郁、健脾养血之功。",
                "mode": "deep",
                "status": "ok",
                "route": {
                    "route": "hybrid",
                    "reason": "test_reason",
                    "status": "ok",
                    "final_route": "hybrid",
                    "executed_routes": ["graph", "retrieval"],
                },
                "factual_evidence": [
                    {
                        "source_type": "doc",
                        "source": "医方集解.txt#12",
                        "snippet": "逍遥散用于肝郁脾虚。",
                        "score": 0.9,
                    }
                ],
                "case_references": [],
                "citations": ["医方集解.txt#12 逍遥散用于肝郁脾虚"],
                "planner_steps": [
                    {"stage": "route_search", "label": "执行首轮检索", "detail": "route=hybrid"},
                    {"stage": "gap_check", "label": "分析证据缺口", "detail": "round=1; gaps=efficacy"},
                ],
                "tool_trace": [
                    {
                        "tool": "tcm_route_search",
                        "meta": {"status": "ok", "final_route": "hybrid"},
                    },
                    {
                        "tool": "read_evidence_path",
                        "meta": {"status": "ok", "path": "entity://逍遥散/功效", "reason": "补充功效证据", "count": 1},
                    },
                ],
                "notes": ["deep_round_1:gaps=efficacy"],
                "query_analysis": {},
                "retrieval_strategy": {},
                "evidence_paths": ["entity://逍遥散/功效"],
                "service_trace_ids": {},
                "service_backends": {},
            }

        async def fake_generate_title(first_user_message: str) -> str:
            self.assertEqual(first_user_message, "逍遥散有什么功效")
            return "逍遥散功效"

        from api import chat as chat_module

        original_session_manager = agent_manager.session_manager
        original_generate_title = agent_manager.generate_title
        original_get_qa_service = chat_module.get_qa_service

        class FakeQAService:
            async def answer(self, message: str, *, mode: str, top_k: int):
                return await fake_answer(message, mode=mode, top_k=top_k)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                agent_manager.session_manager = SessionManager(Path(tmp))
                agent_manager.generate_title = fake_generate_title  # type: ignore[assignment]
                chat_module.get_qa_service = lambda: FakeQAService()  # type: ignore[assignment]

                response = asyncio.run(
                    chat(
                        ChatRequest(
                            message="逍遥散有什么功效",
                            session_id="chat-api-test",
                            stream=False,
                            mode="deep",
                        )
                    )
                )

                body = json.loads(response.body.decode("utf-8"))
                self.assertEqual(body["content"], "逍遥散具有疏肝解郁、健脾养血之功。")
                self.assertEqual(body["title"], "逍遥散功效")
                self.assertEqual(len(body["segments"]), 1)
                self.assertEqual(body["segments"][0]["route"]["final_route"], "hybrid")
                self.assertEqual(body["segments"][0]["evidence"][0]["source"], "医方集解.txt#12")
                self.assertEqual(body["segments"][0]["planner_steps"][0]["stage"], "route_search")
                self.assertEqual(body["segments"][0]["notes"], ["deep_round_1:gaps=efficacy"])
                self.assertEqual(body["segments"][0]["qa_mode"], "deep")
                self.assertEqual(len(body["segments"][0]["tool_calls"]), 2)

                saved = agent_manager.session_manager.get_history("chat-api-test")
                self.assertEqual(saved["title"], "逍遥散功效")
                self.assertEqual(len(saved["messages"]), 2)
                self.assertEqual(saved["messages"][0]["role"], "user")
                self.assertEqual(saved["messages"][1]["role"], "assistant")
                self.assertEqual(saved["messages"][1]["planner_steps"][1]["stage"], "gap_check")
                self.assertEqual(saved["messages"][1]["notes"], ["deep_round_1:gaps=efficacy"])
                self.assertEqual(saved["messages"][1]["qa_mode"], "deep")
        finally:
            agent_manager.session_manager = original_session_manager
            agent_manager.generate_title = original_generate_title  # type: ignore[assignment]
            chat_module.get_qa_service = original_get_qa_service  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
