from __future__ import annotations

import json
import unittest

from services.qa_service.engine import QAService, _apply_origin_action_policy, _factual_evidence_from_payload, _identify_evidence_gaps, _plan_followup_actions


class FakeRouteTool:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def _run(self, query: str, top_k: int = 12):
        return json.dumps(self.payload, ensure_ascii=False)


class FakeAnswerGenerator:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeSequentialAnswerGenerator:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self.responses:
            raise RuntimeError("no_more_responses")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeEvidenceNavigator:
    def __init__(self, *, listed_paths: list[str] | None = None, read_results: dict[str, dict[str, object]] | None = None) -> None:
        self.listed_paths = listed_paths or []
        self.read_results = read_results or {}
        self.calls: list[dict[str, object]] = []

    def list_evidence_paths(self, *, query: str, route_payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append({"tool": "list_evidence_paths", "query": query})
        return {"tool": "list_evidence_paths", "paths": list(self.listed_paths), "count": len(self.listed_paths)}

    def read_evidence_path(self, *, path: str, query: str = "", top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "read_evidence_path", "path": path, "query": query, "top_k": top_k})
        return dict(self.read_results.get(path, {"tool": "read_evidence_path", "path": path, "status": "empty", "items": [], "count": 0}))

    def search_evidence_text(self, *, query: str, scope_paths: list[str] | None = None, top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "search_evidence_text", "query": query, "scope_paths": scope_paths or [], "top_k": top_k})
        return {"tool": "search_evidence_text", "status": "empty", "items": [], "count": 0}


def _composition_payload() -> dict[str, object]:
    return {
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
        "service_trace_ids": {"graph": "g1"},
        "service_backends": {"graph": "graph-service"},
        "graph_result": {
            "code": 0,
            "message": "ok",
            "data": {
                "entity": {"canonical_name": "六味地黄丸", "entity_type": "formula"},
                "relations": [
                    {"predicate": "使用药材", "target": "熟地黄", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.91},
                    {"predicate": "使用药材", "target": "山茱萸", "source_book": "小儿药证直诀", "source_chapter": "卷下", "score": 0.9},
                ],
            },
        },
    }


def _deep_followup_payload() -> dict[str, object]:
    return {
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
        "graph_result": {"code": 0, "message": "ok", "data": {"entity": {"canonical_name": "六味地黄丸", "entity_type": "formula"}, "relations": []}},
    }


class QAServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_graph_path_payload_is_exposed_as_factual_evidence(self) -> None:
        payload = {
            "graph_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "paths": [
                        {
                            "nodes": ["肝郁脾虚", "逍遥散"],
                            "edges": ["推荐方剂"],
                            "score": 0.91,
                            "sources": [{"source_book": "医宗金鉴", "source_chapter": "杂病心法"}],
                        }
                    ]
                },
            }
        }

        evidence = _factual_evidence_from_payload(payload)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["source_type"], "graph_path")
        self.assertEqual(evidence[0]["predicate"], "推荐方剂")
        self.assertEqual(evidence[0]["target"], "逍遥散")
        self.assertEqual(evidence[0]["source_book"], "医宗金鉴")

    async def test_quick_mode_uses_grounded_llm_answer(self) -> None:
        answer_generator = FakeAnswerGenerator("Quick 2.0回答：六味地黄丸由熟地黄、山茱萸组成。")
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=answer_generator)

        result = await service.answer("六味地黄丸的组成是什么", mode="quick", top_k=12)

        self.assertEqual(result["mode"], "quick")
        self.assertEqual(result["generation_backend"], "grounded_llm")
        self.assertIn("Quick 2.0回答", result["answer"])
        self.assertGreaterEqual(len(result["factual_evidence"]), 1)
        self.assertEqual(result["planner_steps"][0]["stage"], "route_search")
        self.assertIn("熟地黄", answer_generator.calls[0]["user_prompt"])
        self.assertIn("事实证据", answer_generator.calls[0]["user_prompt"])

    async def test_quick_mode_falls_back_to_deterministic_when_llm_fails(self) -> None:
        service = QAService(
            route_tool=FakeRouteTool(_composition_payload()),
            answer_generator=FakeAnswerGenerator(RuntimeError("llm_down")),
        )

        result = await service.answer("六味地黄丸的组成是什么", mode="quick", top_k=12)

        self.assertEqual(result["generation_backend"], "deterministic_quick_fallback")
        self.assertIn("熟地黄", result["answer"])

    async def test_deep_mode_runs_followup_evidence_read_and_planner_llm(self) -> None:
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://六味地黄丸/使用药材"],
            read_results={
                "entity://六味地黄丸/使用药材": {
                    "tool": "read_evidence_path",
                    "path": "entity://六味地黄丸/使用药材",
                    "status": "ok",
                    "count": 2,
                    "items": [
                        {"evidence_type": "factual_grounding", "source_type": "graph", "source": "小儿药证直诀/卷下", "snippet": "使用药材: 熟地黄", "predicate": "使用药材", "target": "熟地黄", "score": 0.91},
                        {"evidence_type": "factual_grounding", "source_type": "graph", "source": "小儿药证直诀/卷下", "snippet": "使用药材: 山茱萸", "predicate": "使用药材", "target": "山茱萸", "score": 0.9},
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(_deep_followup_payload()),
            answer_generator=FakeAnswerGenerator("Deep 2.0回答：六味地黄丸由熟地黄、山茱萸等药组成。"),
            evidence_navigator=navigator,
        )

        result = await service.answer("六味地黄丸的组成是什么", mode="deep", top_k=12)

        self.assertEqual(result["mode"], "deep")
        self.assertEqual(result["generation_backend"], "planner_llm")
        self.assertIn("Deep 2.0回答", result["answer"])
        self.assertTrue(any(item["tool"] == "read_evidence_path" for item in result["tool_trace"]))
        self.assertTrue(any(call["tool"] == "read_evidence_path" for call in navigator.calls))
        self.assertGreaterEqual(len(result["factual_evidence"]), 1)
        self.assertTrue(any(step["stage"] == "planner" for step in result["planner_steps"]))
        self.assertTrue(any(step["tool"] == "read_evidence_path" for step in result["deep_trace"]))

    async def test_guard_refuses_high_risk_query(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))

        result = await service.answer("六味地黄丸一次吃几克", mode="quick", top_k=12)

        self.assertEqual(result["status"], "guard_refused")
        self.assertEqual(result["generation_backend"], "medical_guard")
        self.assertEqual(result["factual_evidence"], [])

    async def test_guard_allows_academic_dosage_threshold_query(self) -> None:
        service = QAService(
            route_tool=FakeRouteTool(_composition_payload()),
            answer_generator=FakeAnswerGenerator("这是一个关于剂量阈值效应的学术回答。"),
        )

        result = await service.answer(
            "请从AQP分布差异分析五苓散利小便与发汗是否存在剂量或煎煮法阈值效应",
            mode="quick",
            top_k=12,
        )

        self.assertNotEqual(result["status"], "guard_refused")
        self.assertEqual(result["generation_backend"], "grounded_llm")

    def test_origin_gap_prefers_entity_first_then_book_from_graph_source(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        wrong_doc_evidence = [
            {
                "source_type": "doc",
                "source": "医方集解.txt#12",
                "snippet": "逍遥散用于肝郁血虚、脾失健运之证。",
                "source_book": "医方集解",
                "source_chapter": "第12页",
            }
        ]
        gaps = _identify_evidence_gaps(
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload=payload,
            factual_evidence=wrong_doc_evidence,
            case_references=[],
        )
        self.assertIn("origin", gaps)

        first_actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload={**payload, "_planner_factual_evidence": wrong_doc_evidence},
            evidence_paths=["qa://六味地黄丸/similar"],
            gaps=gaps,
            max_actions=2,
            executed_actions=set(),
        )
        self.assertEqual(first_actions[0]["path"], "entity://六味地黄丸/*")

        graph_origin_evidence = [
            {
                "source_type": "graph",
                "source": "小儿药证直诀/卷下",
                "snippet": "使用药材: 熟地黄",
                "predicate": "使用药材",
                "target": "熟地黄",
                "source_book": "小儿药证直诀",
                "source_chapter": "卷下",
            }
        ]
        second_actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload={**payload, "_planner_factual_evidence": graph_origin_evidence},
            evidence_paths=["entity://六味地黄丸/*"],
            gaps=["origin"],
            max_actions=2,
            executed_actions=set(),
        )
        self.assertEqual(second_actions[0]["path"], "book://小儿药证直诀/*")

    def test_single_entity_query_does_not_create_comparison_gap(self) -> None:
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy", "compare_entities": []},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "肝郁脾虚",
                "compare_entities": [],
                "sources": ["graph_sqlite"],
            },
        }
        evidence = [
            {
                "source_type": "graph",
                "source": "中医内科学/郁证篇",
                "snippet": "治法: 疏肝健脾",
                "predicate": "治法",
                "target": "疏肝健脾",
                "source_book": "中医内科学",
                "source_chapter": "郁证篇",
            }
        ]

        gaps = _identify_evidence_gaps(
            query="肝郁脾虚的治法是什么？",
            payload=payload,
            factual_evidence=evidence,
            case_references=[],
        )

        self.assertEqual(gaps, [])

    def test_origin_action_policy_overrides_wrong_book_plan(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "_planner_factual_evidence": [],
        }
        wrong_actions = [
            {
                "skill": "read-formula-origin",
                "tool": "read_evidence_path",
                "path": "book://医方集解/*",
                "query": "六味地黄丸 出处 原文",
                "top_k": 6,
                "reason": "bad plan",
            }
        ]

        corrected = _apply_origin_action_policy(
            planner_skills=service.planner_skills,
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload=payload,
            evidence_paths=["entity://六味地黄丸/*", "book://医方集解/*"],
            gaps=["origin"],
            actions=wrong_actions,
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(corrected[0]["path"], "entity://六味地黄丸/*")
        self.assertEqual(len(corrected), 1)

    async def test_deep_mode_origin_policy_rewrites_wrong_planner_book_actions(self) -> None:
        payload = {
            "route": "retrieval",
            "route_reason": "classifier_retrieval_match",
            "status": "ok",
            "final_route": "retrieval",
            "executed_routes": ["retrieval"],
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "evidence_paths": ["qa://六味地黄丸/similar"],
            "retrieval_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "chunks": [
                        {
                            "source_file": "医方集解.txt",
                            "source_page": 12,
                            "text": "逍遥散用于肝郁血虚、脾失健运之证。",
                            "score": 0.9,
                        }
                    ]
                },
            },
        }
        navigator = FakeEvidenceNavigator(
            listed_paths=["qa://六味地黄丸/similar", "entity://六味地黄丸/*", "book://医方集解/*"],
            read_results={
                "entity://六味地黄丸/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://六味地黄丸/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph",
                            "source": "小儿药证直诀/卷下",
                            "snippet": "使用药材: 熟地黄",
                            "predicate": "使用药材",
                            "target": "熟地黄",
                            "source_book": "小儿药证直诀",
                            "source_chapter": "卷下",
                            "score": 0.91,
                        }
                    ],
                },
                "book://小儿药证直诀/*": {
                    "tool": "read_evidence_path",
                    "path": "book://小儿药证直诀/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "doc",
                            "source": "小儿药证直诀.txt#42",
                            "snippet": "六味地黄丸，治肾阴不足。",
                            "source_book": "小儿药证直诀",
                            "source_chapter": "卷下",
                            "score": 0.93,
                        }
                    ],
                },
            },
        )
        answer_generator = FakeSequentialAnswerGenerator(
            [
                "{\"gaps\":[\"origin\"],\"next_actions\":[{\"skill\":\"read-formula-origin\",\"path\":\"book://医方集解/*\",\"reason\":\"bad plan\"}],\"stop_reason\":\"\"}",
                "{\"gaps\":[\"origin\"],\"next_actions\":[{\"skill\":\"read-formula-origin\",\"path\":\"book://本草纲目/*\",\"reason\":\"bad plan\"}],\"stop_reason\":\"\"}",
                "Deep 2.0回答：六味地黄丸见《小儿药证直诀》卷下，可据此继续追原文。",
            ]
        )
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=answer_generator,
            evidence_navigator=navigator,
        )

        result = await service.answer("六味地黄丸出自哪本书？请给出处原文。", mode="deep", top_k=12)

        read_paths = [item["meta"]["path"] for item in result["tool_trace"] if item["tool"] == "read_evidence_path"]
        self.assertEqual(read_paths, ["entity://六味地黄丸/*", "book://小儿药证直诀/*"])
        self.assertIn("《小儿药证直诀》", result["answer"])


if __name__ == "__main__":
    unittest.main()
