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
    def test_non_stream_chat_returns_plain_content_and_segments(self) -> None:
        async def fake_astream(message: str, history: list[dict[str, str]]):
            self.assertEqual(message, "逍遥散有什么功效")
            self.assertEqual(history, [])
            yield {"type": "tool_start", "tool": "tcm_route_search", "input": "{\"query\":\"逍遥散有什么功效\"}"}
            yield {
                "type": "tool_end",
                "tool": "tcm_route_search",
                "output": "{\"route\":\"hybrid\"}",
                "meta": {"trace_id": "trace-1"},
            }
            yield {
                "type": "route",
                "route": "hybrid",
                "reason": "test_reason",
                "status": "ok",
                "final_route": "hybrid",
                "executed_routes": ["graph", "retrieval"],
                "degradation": [],
                "service_health": {},
                "service_trace_ids": {"retrieval": "trace-1"},
                "service_backends": {"retrieval": "retrieval-service"},
            }
            yield {
                "type": "evidence",
                "items": [
                    {
                        "source_type": "doc",
                        "source": "医方集解.txt#12",
                        "snippet": "逍遥散用于肝郁脾虚。",
                        "score": 0.9,
                    }
                ],
            }
            yield {"type": "token", "content": "逍遥散具有疏肝解郁、健脾养血之功。"}
            yield {"type": "done", "content": "逍遥散具有疏肝解郁、健脾养血之功。"}

        async def fake_generate_title(first_user_message: str) -> str:
            self.assertEqual(first_user_message, "逍遥散有什么功效")
            return "逍遥散功效"

        original_session_manager = agent_manager.session_manager
        original_astream = agent_manager.astream
        original_generate_title = agent_manager.generate_title

        try:
            with tempfile.TemporaryDirectory() as tmp:
                agent_manager.session_manager = SessionManager(Path(tmp))
                agent_manager.astream = fake_astream  # type: ignore[assignment]
                agent_manager.generate_title = fake_generate_title  # type: ignore[assignment]

                response = asyncio.run(
                    chat(
                        ChatRequest(
                            message="逍遥散有什么功效",
                            session_id="chat-api-test",
                            stream=False,
                        )
                    )
                )

                body = json.loads(response.body.decode("utf-8"))
                self.assertEqual(body["content"], "逍遥散具有疏肝解郁、健脾养血之功。")
                self.assertEqual(body["title"], "逍遥散功效")
                self.assertEqual(len(body["segments"]), 1)
                self.assertEqual(body["segments"][0]["route"]["final_route"], "hybrid")
                self.assertEqual(body["segments"][0]["evidence"][0]["source"], "医方集解.txt#12")

                saved = agent_manager.session_manager.get_history("chat-api-test")
                self.assertEqual(saved["title"], "逍遥散功效")
                self.assertEqual(len(saved["messages"]), 2)
                self.assertEqual(saved["messages"][0]["role"], "user")
                self.assertEqual(saved["messages"][1]["role"], "assistant")
        finally:
            agent_manager.session_manager = original_session_manager
            agent_manager.astream = original_astream  # type: ignore[assignment]
            agent_manager.generate_title = original_generate_title  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
