import asyncio
import unittest

from api.qa import QAAnswerRequest, answer_question


class QAApiTests(unittest.TestCase):
    def test_query_param_mode_overrides_body_mode(self) -> None:
        async def fake_answer(query: str, *, mode: str, top_k: int):
            self.assertEqual(query, "六味地黄丸出自哪本书？请给出处原文。")
            self.assertEqual(mode, "deep")
            self.assertEqual(top_k, 12)
            return {
                "answer": "test",
                "mode": mode,
                "status": "ok",
                "route": {"route": "hybrid", "reason": "test", "status": "ok", "final_route": "hybrid", "executed_routes": ["graph", "retrieval"]},
                "factual_evidence": [],
                "case_references": [],
                "citations": [],
                "planner_steps": [],
                "deep_trace": [],
                "evidence_bundle": {},
                "tool_trace": [],
                "notes": [],
                "query_analysis": {},
                "retrieval_strategy": {},
                "evidence_paths": [],
                "service_trace_ids": {},
                "service_backends": {},
            }

        from api import qa as qa_module

        original_get_qa_service = qa_module.get_qa_service

        class FakeQAService:
            async def answer(self, query: str, *, mode: str, top_k: int):
                return await fake_answer(query, mode=mode, top_k=top_k)

        try:
            qa_module.get_qa_service = lambda: FakeQAService()  # type: ignore[assignment]
            response = asyncio.run(
                answer_question(
                    QAAnswerRequest(query="六味地黄丸出自哪本书？请给出处原文。", mode="quick", top_k=12),
                    mode="deep",
                )
            )
            self.assertEqual(response["data"]["mode"], "deep")
        finally:
            qa_module.get_qa_service = original_get_qa_service  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
