from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from services.qa_service.engine import QAService, _apply_origin_action_policy, _factual_evidence_from_payload, _identify_evidence_gaps, _plan_followup_actions
from services.qa_service.evidence import _coverage_gaps_from_state, _init_coverage_state, _update_coverage_state
from services.qa_service.planner_support import _pick_best_source_path
from services.qa_service.prompts import _build_planner_user_prompt, _requested_answer_dimensions


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


class FakePlannerAliasService:
    def aliases_for_entity(self, entity_name: str, *, max_aliases: int = 8, max_depth: int = 2) -> list[str]:
        mapping = {
            "六味地黄丸": ["地黄丸", "六味丸"],
            "地黄丸": ["六味地黄丸", "六味丸"],
            "六味丸": ["六味地黄丸", "地黄丸"],
        }
        return mapping.get(entity_name, [])


class FakeEvidenceNavigator:
    def __init__(
        self,
        *,
        listed_paths: list[str] | None = None,
        read_results: dict[str, dict[str, object]] | None = None,
        search_results: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.listed_paths = listed_paths or []
        self.read_results = read_results or {}
        self.search_results = search_results or {}
        self.calls: list[dict[str, object]] = []

    def list_evidence_paths(self, *, query: str, route_payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append({"tool": "list_evidence_paths", "query": query})
        return {"tool": "list_evidence_paths", "paths": list(self.listed_paths), "count": len(self.listed_paths)}

    def read_evidence_path(self, *, path: str, query: str = "", source_hint: str = "", top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "read_evidence_path", "path": path, "query": query, "source_hint": source_hint, "top_k": top_k})
        return dict(self.read_results.get(path, {"tool": "read_evidence_path", "path": path, "status": "empty", "items": [], "count": 0}))

    def search_evidence_text(self, *, query: str, source_hint: str = "", scope_paths: list[str] | None = None, top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "search_evidence_text", "query": query, "source_hint": source_hint, "scope_paths": scope_paths or [], "top_k": top_k})
        key = json.dumps({"query": query, "scope_paths": scope_paths or []}, ensure_ascii=False, sort_keys=True)
        return dict(self.search_results.get(key, {"tool": "search_evidence_text", "status": "empty", "items": [], "count": 0}))


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
        self.assertEqual(evidence[0]["evidence_path"], "chapter://医宗金鉴/杂病心法")
        self.assertEqual(evidence[0]["source_scope_path"], "book://医宗金鉴/*")

    def test_retrieval_payload_keeps_logical_source_trace_metadata(self) -> None:
        payload = {
            "retrieval_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "chunks": [
                        {
                            "source_file": "133-小儿药证直诀.txt",
                            "source_page": 42,
                            "chapter_title": "卷下",
                            "file_path": "classic://小儿药证直诀/0042-00",
                            "text": "六味地黄丸，治肾阴不足。",
                            "score": 0.92,
                        }
                    ]
                },
            }
        }

        evidence = _factual_evidence_from_payload(payload)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["source_type"], "doc")
        self.assertEqual(evidence[0]["evidence_path"], "chapter://小儿药证直诀/卷下")
        self.assertEqual(evidence[0]["source_scope_path"], "book://小儿药证直诀/*")
        self.assertEqual(evidence[0]["file_path"], "classic://小儿药证直诀/0042-00")
        self.assertEqual(evidence[0]["source_page"], 42)

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

    async def test_quick_mode_runs_bounded_followup_for_comparison_gap(self) -> None:
        payload = {
            "route": "hybrid",
            "route_reason": "compare_entities_forced_hybrid",
            "status": "ok",
            "final_route": "hybrid",
            "executed_routes": ["graph", "retrieval"],
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "逍遥散",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "evidence_paths": ["entity://逍遥散/*", "entity://柴胡疏肝散/*", "book://医方集解/*"],
            "graph_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "relations": [
                        {
                            "predicate": "功效",
                            "target": "疏肝健脾",
                            "source_book": "医方集解",
                            "source_chapter": "卷三",
                            "source_text": "逍遥散功效为疏肝健脾。",
                            "score": 0.92,
                        }
                    ]
                },
            },
        }
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://逍遥散/*", "entity://柴胡疏肝散/*", "book://医方集解/*"],
            read_results={
                "entity://柴胡疏肝散/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://柴胡疏肝散/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph",
                            "source": "医方集解/卷四",
                            "snippet": "柴胡疏肝散功效为疏肝理气。",
                            "predicate": "功效",
                            "target": "疏肝理气",
                            "source_book": "医方集解",
                            "source_chapter": "卷四",
                            "anchor_entity": "柴胡疏肝散",
                            "score": 0.91,
                        }
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=FakeAnswerGenerator("Quick对比回答：逍遥散偏疏肝健脾，柴胡疏肝散偏疏肝理气。"),
            evidence_navigator=navigator,
        )

        result = await service.answer("请比较逍遥散与柴胡疏肝散的功效与病机差异。", mode="quick", top_k=12)

        self.assertEqual(result["generation_backend"], "grounded_llm")
        self.assertTrue(any(item["tool"] == "list_evidence_paths" for item in result["tool_trace"]))
        self.assertTrue(any(item["tool"] == "read_evidence_path" for item in result["tool_trace"]))
        self.assertTrue(any(step["stage"] == "quick_followup" for step in result["planner_steps"]))
        self.assertIn("Quick对比回答", result["answer"])

    async def test_quick_mode_uses_two_followups_for_comparison_and_reasoning_gaps(self) -> None:
        payload = {
            "route": "hybrid",
            "route_reason": "compare_entities_forced_hybrid",
            "status": "ok",
            "final_route": "hybrid",
            "executed_routes": ["graph", "retrieval"],
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "逍遥散",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "evidence_paths": ["entity://逍遥散/*", "entity://柴胡疏肝散/*", "book://医方集解/*"],
            "graph_result": {
                "code": 0,
                "message": "ok",
                "data": {
                    "relations": [
                        {
                            "predicate": "功效",
                            "target": "疏肝健脾",
                            "source_book": "医方集解",
                            "source_chapter": "卷三",
                            "source_text": "逍遥散功效为疏肝健脾。",
                            "score": 0.92,
                        }
                    ]
                },
            },
        }
        search_key = json.dumps(
            {"query": "逍遥散 柴胡疏肝散 功效 病机 古籍 教材 出处", "scope_paths": ["book://医方集解/*"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://逍遥散/*", "entity://柴胡疏肝散/*", "book://医方集解/*"],
            read_results={
                "entity://柴胡疏肝散/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://柴胡疏肝散/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph",
                            "source": "医方集解/卷四",
                            "snippet": "柴胡疏肝散功效为疏肝理气。",
                            "predicate": "功效",
                            "target": "疏肝理气",
                            "source_book": "医方集解",
                            "source_chapter": "卷四",
                            "anchor_entity": "柴胡疏肝散",
                            "score": 0.91,
                        }
                    ],
                }
            },
            search_results={
                search_key: {
                    "tool": "search_evidence_text",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "doc",
                            "source": "医方集解.txt#13",
                            "snippet": "逍遥散与柴胡疏肝散病机有别：前者重养血健脾，后者重疏肝理气止痛。",
                            "source_book": "医方集解",
                            "source_chapter": "卷四",
                            "score": 0.9,
                        }
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=FakeAnswerGenerator("Quick增强回答：已补齐比较与病机证据。"),
            evidence_navigator=navigator,
        )

        result = await service.answer("请比较逍遥散与柴胡疏肝散的功效与病机差异。", mode="quick", top_k=12)

        self.assertEqual(
            [call["tool"] for call in navigator.calls],
            ["list_evidence_paths", "read_evidence_path", "search_evidence_text"],
        )
        self.assertTrue(any(item["tool"] == "search_evidence_text" for item in result["tool_trace"]))
        self.assertFalse(any(str(note).startswith("quick_followup_remaining_gaps:") for note in result["notes"]))
        self.assertIn("Quick增强回答", result["answer"])

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
        self.assertEqual(result["deep_trace"][0]["round"], 1)
        self.assertEqual(result["deep_trace"][0]["action_index"], 1)
        self.assertIn(result["deep_trace"][0]["status"], {"ok", "empty", "degraded"})
        self.assertIn("coverage_before_step", result["deep_trace"][0])
        self.assertIn("deep_trace", result["evidence_bundle"])
        self.assertIn("planner_steps", result["evidence_bundle"])

    async def test_deep_stream_emits_agent_style_new_response_boundaries(self) -> None:
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://六味地黄丸/使用药材"],
            read_results={
                "entity://六味地黄丸/使用药材": {
                    "tool": "read_evidence_path",
                    "path": "entity://六味地黄丸/使用药材",
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
                            "score": 0.91,
                        }
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(_deep_followup_payload()),
            answer_generator=FakeAnswerGenerator("Deep streaming answer"),
            evidence_navigator=navigator,
        )

        events = []
        async for event in service.stream_answer("六味地黄丸的组成是什么", mode="deep", top_k=12):
            events.append(event["type"])

        self.assertIn("new_response", events)
        self.assertGreaterEqual(events.count("new_response"), 2)
        self.assertEqual(events[-1], "result")

    async def test_execute_action_uses_request_scope_cache(self) -> None:
        navigator = FakeEvidenceNavigator(
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
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(_deep_followup_payload()),
            answer_generator=FakeAnswerGenerator("unused"),
            evidence_navigator=navigator,
        )
        action = {
            "skill": "read-formula-origin",
            "tool": "read_evidence_path",
            "path": "entity://六味地黄丸/*",
            "query": "六味地黄丸 出处 原文",
            "top_k": 6,
        }
        request_cache: dict[str, dict[str, object]] = {}

        first = service._execute_action(action, request_cache=request_cache)
        second = service._execute_action(action, request_cache=request_cache)

        read_calls = [call for call in navigator.calls if call["tool"] == "read_evidence_path"]
        self.assertEqual(len(read_calls), 1)
        self.assertEqual(first["cache_hit"], False)
        self.assertEqual(second["cache_hit"], True)

    async def test_list_evidence_paths_uses_request_scope_cache(self) -> None:
        payload = _deep_followup_payload()
        navigator = FakeEvidenceNavigator(listed_paths=["entity://六味地黄丸/使用药材", "alias://六味地黄丸"])
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=FakeAnswerGenerator("unused"),
            evidence_navigator=navigator,
        )
        request_cache: dict[str, dict[str, object]] = {}

        first_paths, first_cache_hit = service._list_evidence_paths(
            query="六味地黄丸的组成是什么",
            payload=payload,
            request_cache=request_cache,
        )
        second_paths, second_cache_hit = service._list_evidence_paths(
            query="六味地黄丸的组成是什么",
            payload=payload,
            request_cache=request_cache,
        )

        list_calls = [call for call in navigator.calls if call["tool"] == "list_evidence_paths"]
        self.assertEqual(len(list_calls), 1)
        self.assertEqual(first_paths, second_paths)
        self.assertFalse(first_cache_hit)
        self.assertTrue(second_cache_hit)

    async def test_execute_action_reuses_entity_reads_for_compare_queries(self) -> None:
        navigator = FakeEvidenceNavigator(
            read_results={
                "entity://逍遥散/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://逍遥散/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph",
                            "source": "医方集解/卷三",
                            "snippet": "逍遥散功效为疏肝健脾。",
                            "predicate": "功效",
                            "target": "疏肝健脾",
                            "source_book": "医方集解",
                            "source_chapter": "卷三",
                            "anchor_entity": "逍遥散",
                            "score": 0.92,
                        }
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(_deep_followup_payload()),
            answer_generator=FakeAnswerGenerator("unused"),
            evidence_navigator=navigator,
        )
        request_cache: dict[str, dict[str, object]] = {}
        first_action = {
            "skill": "compare-formulas",
            "tool": "read_evidence_path",
            "path": "entity://逍遥散/*",
            "query": "逍遥散 功效 柴胡疏肝散 比较",
            "top_k": 6,
        }
        second_action = {
            "skill": "compare-formulas",
            "tool": "read_evidence_path",
            "path": "entity://逍遥散/*",
            "query": "逍遥散 柴胡疏肝散 区别 共同点 适用边界",
            "top_k": 6,
        }

        first = service._execute_action(first_action, request_cache=request_cache)
        second = service._execute_action(second_action, request_cache=request_cache)

        read_calls = [call for call in navigator.calls if call["tool"] == "read_evidence_path"]
        self.assertEqual(len(read_calls), 1)
        self.assertEqual(first["cache_hit"], False)
        self.assertEqual(second["cache_hit"], True)

    async def test_execute_action_uses_selected_source_path_as_search_scope(self) -> None:
        search_key = json.dumps(
            {"query": "六味地黄丸 出处 原文", "scope_paths": ["chapter://小儿药证直诀/卷下"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        navigator = FakeEvidenceNavigator(
            search_results={
                search_key: {
                    "tool": "search_evidence_text",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "chapter",
                            "source": "小儿药证直诀/卷下",
                            "snippet": "六味地黄丸，治肾怯失音，囟开不合，神不足。",
                            "source_book": "小儿药证直诀",
                            "source_chapter": "卷下",
                            "score": 1.0,
                        }
                    ],
                }
            },
        )
        service = QAService(
            route_tool=FakeRouteTool(_deep_followup_payload()),
            answer_generator=FakeAnswerGenerator("unused"),
            evidence_navigator=navigator,
        )
        request_cache: dict[str, dict[str, object]] = {}

        result = service._execute_action(
            {
                "skill": "trace-source-passage",
                "tool": "search_evidence_text",
                "path": "chapter://小儿药证直诀/卷下",
                "query": "六味地黄丸 出处 原文",
                "top_k": 4,
            },
            request_cache=request_cache,
        )

        search_calls = [call for call in navigator.calls if call["tool"] == "search_evidence_text"]
        self.assertEqual(len(search_calls), 1)
        self.assertEqual(search_calls[0]["scope_paths"], ["chapter://小儿药证直诀/卷下"])
        self.assertEqual(result["status"], "ok")

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
        self.assertIn("source_hint", second_actions[0])
        self.assertIn("熟地黄", second_actions[0]["source_hint"])

    def test_requested_answer_dimensions_cover_reasoning_and_modern_mapping(self) -> None:
        dimensions = _requested_answer_dimensions(
            "请分析病机，并做鉴别，说明指导意义及其与现代GABA机制的对应关系。"
        )
        self.assertEqual(dimensions, ["病机", "鉴别", "指导意义", "现代对接"])

    def test_origin_gap_prefers_chapter_path_before_book_when_available(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
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

        actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload={**payload, "_planner_factual_evidence": graph_origin_evidence},
            evidence_paths=["entity://六味地黄丸/*", "chapter://小儿药证直诀/卷下", "book://小儿药证直诀/*"],
            gaps=["origin"],
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(actions[0]["path"], "chapter://小儿药证直诀/卷下")

    def test_clause_query_prefers_existing_chapter_path_for_direct_source_followup(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "五苓散",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }

        actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="《伤寒论》五苓散方后注“多饮暖水，汗出愈”是什么意思？",
            payload={**payload, "_planner_factual_evidence": []},
            evidence_paths=["entity://五苓散/*", "chapter://伤寒论/辨太阳病脉证并治", "book://伤寒论/*"],
            gaps=["origin"],
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(actions[0]["path"], "chapter://伤寒论/辨太阳病脉证并治")

    def test_clause_query_origin_policy_rewrites_to_existing_chapter_path(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "五苓散",
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "_planner_factual_evidence": [],
        }
        wrong_actions = [
            {
                "skill": "read-formula-origin",
                "tool": "read_evidence_path",
                "path": "entity://五苓散/*",
                "query": "五苓散 出处 原文",
                "top_k": 6,
                "reason": "bad plan",
            }
        ]

        corrected = _apply_origin_action_policy(
            planner_skills=service.planner_skills,
            query="《伤寒论》五苓散方后注“多饮暖水，汗出愈”是什么意思？",
            payload=payload,
            evidence_paths=["entity://五苓散/*", "chapter://伤寒论/辨太阳病脉证并治", "book://伤寒论/*"],
            gaps=["origin"],
            actions=wrong_actions,
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(corrected[0]["path"], "chapter://伤寒论/辨太阳病脉证并治")

    def test_origin_gap_normalizes_graph_book_path_for_followup_read(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        graph_origin_evidence = [
            {
                "source_type": "graph",
                "source": "089-医方论/089-医方论_正文",
                "snippet": "地黄（砂仁酒拌、九蒸九晒）八两",
                "predicate": "使用药材",
                "target": "地黄",
                "source_book": "089-医方论",
                "source_chapter": "089-医方论_正文",
            }
        ]

        actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload={**payload, "_planner_factual_evidence": graph_origin_evidence},
            evidence_paths=["entity://六味地黄丸/*", "book://医方论/*"],
            gaps=["origin"],
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(actions[0]["path"], "book://医方论/*")

    def test_origin_gap_uses_alias_path_when_only_old_name_scope_is_available(self) -> None:
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

        with patch("services.qa_service.planner_support.get_runtime_alias_service", return_value=FakePlannerAliasService()):
            actions = _plan_followup_actions(
                planner_skills=service.planner_skills,
                query="六味地黄丸出自哪本书？请给出处原文。",
                payload=payload,
                evidence_paths=["alias://地黄丸"],
                gaps=["origin"],
                max_actions=2,
                executed_actions=set(),
            )

        self.assertEqual(actions[0]["skill"], "expand-entity-alias")
        self.assertEqual(actions[0]["path"], "alias://地黄丸")
        self.assertEqual(actions[1]["path"], "entity://六味地黄丸/*")

    def test_origin_gap_reuses_alias_backed_entity_scope_for_canonical_entity(self) -> None:
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

        with patch("services.qa_service.planner_support.get_runtime_alias_service", return_value=FakePlannerAliasService()):
            actions = _plan_followup_actions(
                planner_skills=service.planner_skills,
                query="六味地黄丸出自哪本书？请给出处原文。",
                payload=payload,
                evidence_paths=["entity://地黄丸/*"],
                gaps=["origin"],
                max_actions=2,
                executed_actions=set(),
            )

        self.assertEqual(actions[0]["path"], "entity://地黄丸/*")

    def test_pick_best_source_path_normalizes_prefixed_book_and_encoded_chapter_path(self) -> None:
        self.assertEqual(
            _pick_best_source_path(
                ["book://089-医方论/*", "chapter://089-医方论/%E5%8D%B7%E4%B8%8A"],
                preferred_books=["医方论"],
            ),
            "chapter://医方论/卷上",
        )

    def test_clause_query_triggers_origin_and_source_trace_gaps(self) -> None:
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "五苓散",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        factual_evidence = [
            {
                "source_type": "graph",
                "source": "伤寒论/辨太阳病脉证并治",
                "snippet": "功效: 利水渗湿，温阳化气。",
                "predicate": "功效",
                "target": "利水渗湿，温阳化气",
                "source_book": "伤寒论",
                "source_chapter": "辨太阳病脉证并治",
                "anchor_entity": "五苓散",
            }
        ]

        gaps = _identify_evidence_gaps(
            query="《伤寒论》五苓散方后注“多饮暖水，汗出愈”是什么意思？",
            payload=payload,
            factual_evidence=factual_evidence,
            case_references=[],
        )

        self.assertIn("origin", gaps)
        self.assertIn("source_trace", gaps)

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

    def test_comparison_gap_clears_when_all_compare_entities_have_anchored_evidence(self) -> None:
        payload = {
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["小柴胡汤", "柴胡桂枝干姜汤"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "小柴胡汤",
                "compare_entities": ["小柴胡汤", "柴胡桂枝干姜汤"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        evidence = [
            {
                "source_type": "graph",
                "source": "伤寒论/辨少阳病",
                "snippet": "和解少阳。",
                "predicate": "功效",
                "target": "和解少阳",
                "source_book": "伤寒论",
                "source_chapter": "辨少阳病",
                "anchor_entity": "小柴胡汤",
            },
            {
                "source_type": "graph",
                "source": "伤寒论/辨少阳病",
                "snippet": "解表里之邪，复津液以助阳。",
                "predicate": "功效",
                "target": "解表里之邪，复津液以助阳",
                "source_book": "伤寒论",
                "source_chapter": "辨少阳病",
                "anchor_entity": "柴胡桂枝干姜汤",
            },
        ]

        gaps = _identify_evidence_gaps(
            query="请比较小柴胡汤与柴胡桂枝干姜汤在病机与治法上的区别。",
            payload=payload,
            factual_evidence=evidence,
            case_references=[],
        )

        self.assertNotIn("comparison", gaps)

    def test_comparison_gap_ignores_noisy_non_primary_compare_entities(self) -> None:
        payload = {
            "query_analysis": {
                "dominant_intent": "compare_entities",
                "compare_entities": ["小柴胡汤方", "咳者", "人参", "加减法", "柴胡桂枝干姜汤"],
            },
            "retrieval_strategy": {
                "intent": "compare_entities",
                "entity_name": "小柴胡汤方",
                "compare_entities": ["小柴胡汤方", "咳者", "人参", "加减法", "柴胡桂枝干姜汤"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        evidence = [
            {
                "source_type": "graph",
                "source": "伤寒论/辨少阳病",
                "snippet": "和解少阳。",
                "predicate": "功效",
                "target": "和解少阳",
                "source_book": "伤寒论",
                "source_chapter": "辨少阳病",
                "anchor_entity": "小柴胡汤方",
            },
            {
                "source_type": "graph",
                "source": "伤寒论/辨少阳病",
                "snippet": "解表里之邪，复津液以助阳。",
                "predicate": "功效",
                "target": "解表里之邪，复津液以助阳",
                "source_book": "伤寒论",
                "source_chapter": "辨少阳病",
                "anchor_entity": "柴胡桂枝干姜汤",
            },
        ]

        gaps = _identify_evidence_gaps(
            query="请比较小柴胡汤方与柴胡桂枝干姜汤的咳嗽病机差异。",
            payload=payload,
            factual_evidence=evidence,
            case_references=[],
        )

        self.assertNotIn("comparison", gaps)

    def test_path_reasoning_gap_accepts_reasoning_text_without_graph_path(self) -> None:
        payload = {
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["小建中汤", "黄连阿胶汤"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "小建中汤",
                "compare_entities": ["小建中汤", "黄连阿胶汤"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        evidence = [
            {
                "source_type": "graph",
                "source": "金匮要略/血痹虚劳病脉证并治",
                "snippet": "小建中汤温中补虚，和里缓急，适用于中焦虚寒而阴阳两伤之证。",
                "predicate": "功效",
                "target": "温中补虚，和里缓急",
                "source_book": "金匮要略",
                "source_chapter": "血痹虚劳病脉证并治",
                "anchor_entity": "小建中汤",
            },
            {
                "source_type": "graph",
                "source": "伤寒论/少阴病",
                "snippet": "黄连阿胶汤交通心肾，主治阴虚火旺、心肾不交之虚烦不寐。",
                "predicate": "功效",
                "target": "交通心肾",
                "source_book": "伤寒论",
                "source_chapter": "少阴病",
                "anchor_entity": "黄连阿胶汤",
            },
        ]

        gaps = _identify_evidence_gaps(
            query="请从病机角度比较小建中汤与黄连阿胶汤在虚烦治疗上的区别。",
            payload=payload,
            factual_evidence=evidence,
            case_references=[],
        )

        self.assertNotIn("path_reasoning", gaps)

    def test_incremental_coverage_state_matches_gap_identifier(self) -> None:
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        factual_evidence = [
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
        query = "六味地黄丸出自哪本书？请给出处原文。"

        state = _init_coverage_state(query=query, payload=payload, evidence_paths=["entity://六味地黄丸/*"])
        _update_coverage_state(state, new_factual_evidence=factual_evidence, new_case_references=[])

        self.assertEqual(
            _coverage_gaps_from_state(state),
            _identify_evidence_gaps(query=query, payload=payload, factual_evidence=factual_evidence, case_references=[]),
        )

    def test_chapter_evidence_counts_as_doc_origin_and_source_trace(self) -> None:
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }
        factual_evidence = [
            {
                "source_type": "chapter",
                "source": "小儿药证直诀/卷下",
                "snippet": "六味地黄丸，治肾怯失音，囟开不合，神不足。",
                "predicate": "",
                "target": "",
                "source_book": "小儿药证直诀",
                "source_chapter": "卷下",
            }
        ]

        gaps = _identify_evidence_gaps(
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload=payload,
            factual_evidence=factual_evidence,
            case_references=[],
        )

        self.assertNotIn("origin", gaps)
        self.assertNotIn("source_trace", gaps)

    def test_doc_only_formula_efficacy_evidence_does_not_require_graph_anchor(self) -> None:
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "逍遥散",
                "sources": ["classic_docs"],
            },
        }
        factual_evidence = [
            {
                "source_type": "doc",
                "source": "医方集解.txt#12",
                "snippet": "逍遥散功效为疏肝健脾，养血调经。",
                "predicate": "功效",
                "target": "疏肝健脾",
                "source_book": "医方集解",
                "source_chapter": "卷一",
            }
        ]

        gaps = _identify_evidence_gaps(
            query="逍遥散的功效是什么？",
            payload=payload,
            factual_evidence=factual_evidence,
            case_references=[],
        )

        self.assertNotIn("efficacy", gaps)

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

    def test_comparison_gap_prioritizes_uncovered_entities(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["柴胡桂枝干姜汤", "乌梅丸", "黄连汤"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "柴胡桂枝干姜汤",
                "compare_entities": ["柴胡桂枝干姜汤", "乌梅丸", "黄连汤"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "_planner_factual_evidence": [
                {
                    "source_type": "graph",
                    "source": "伤寒论/辨太阳病脉证并治",
                    "snippet": "柴胡桂枝干姜汤主之",
                    "predicate": "主方",
                    "target": "柴胡桂枝干姜汤",
                    "source_book": "伤寒论",
                    "source_chapter": "辨太阳病脉证并治",
                }
            ],
        }

        actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query="请比较柴胡桂枝干姜汤、乌梅丸、黄连汤在寒热错杂证中的结构异同。",
            payload=payload,
            evidence_paths=[
                "entity://柴胡桂枝干姜汤/*",
                "entity://乌梅丸/*",
                "entity://黄连汤/*",
                "book://伤寒论/*",
            ],
            gaps=["comparison"],
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual([action["skill"] for action in actions], ["compare-formulas", "compare-formulas"])
        self.assertEqual([action["path"] for action in actions], ["entity://乌梅丸/*", "entity://黄连汤/*"])
        self.assertTrue(all("比较" in action["query"] for action in actions))
        self.assertTrue(any("病机" in action["query"] for action in actions))

    def test_path_reasoning_gap_builds_decomposed_queries(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_efficacy"},
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "柴胡桂枝干姜汤",
                "compare_entities": ["柴胡桂枝干姜汤", "乌梅丸", "黄连汤"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
        }

        actions = _plan_followup_actions(
            planner_skills=service.planner_skills,
            query=(
                "《伤寒论》第147条柴胡桂枝干姜汤证，若从厥阴病上热下寒与胆热脾寒角度，"
                "比较柴胡桂枝干姜汤、乌梅丸、黄连汤在寒热错杂证中的结构异同。"
            ),
            payload=payload,
            evidence_paths=[
                "entity://柴胡桂枝干姜汤/推荐方剂",
                "book://伤寒论/*",
            ],
            gaps=["path_reasoning"],
            max_actions=2,
            executed_actions=set(),
        )

        self.assertEqual(actions[0]["skill"], "trace-graph-path")
        self.assertEqual(actions[0]["path"], "entity://柴胡桂枝干姜汤/推荐方剂")
        self.assertIn("《伤寒论》第147条柴胡桂枝干姜汤证", actions[0]["query"])
        self.assertEqual(actions[1]["skill"], "trace-source-passage")
        self.assertEqual(actions[1]["path"], "book://伤寒论/*")
        self.assertIn("柴胡桂枝干姜汤 乌梅丸 黄连汤 病机 主治 比较", actions[1]["query"])

    def test_source_trace_prefers_chapter_scope_before_book(self) -> None:
        service = QAService(route_tool=FakeRouteTool(_composition_payload()), answer_generator=FakeAnswerGenerator("unused"))
        payload = {
            "query_analysis": {"dominant_intent": "formula_origin"},
            "retrieval_strategy": {
                "intent": "formula_origin",
                "entity_name": "六味地黄丸",
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "_planner_factual_evidence": [
                {
                    "source_type": "graph",
                    "source": "小儿药证直诀/卷下",
                    "snippet": "使用药材: 熟地黄",
                    "predicate": "使用药材",
                    "target": "熟地黄",
                    "source_book": "小儿药证直诀",
                    "source_chapter": "卷下",
                }
            ],
        }

        actions = service._resolve_followup_actions(
            query="六味地黄丸出处原文是什么？",
            payload=payload,
            evidence_paths=["entity://六味地黄丸/*", "book://小儿药证直诀/*", "chapter://小儿药证直诀/卷下"],
            factual_evidence=payload["_planner_factual_evidence"],
            plan={"gaps": ["source_trace"], "next_actions": []},
            heuristic_gaps=["source_trace"],
            plan_gaps=["source_trace"],
            executed_actions=set(),
        )

        self.assertEqual(actions[0]["path"], "chapter://小儿药证直诀/卷下")
        self.assertEqual(actions[0]["scope_paths"], ["chapter://小儿药证直诀/卷下"])

    def test_pick_best_source_path_matches_normalized_book_name(self) -> None:
        self.assertEqual(
            _pick_best_source_path(
                ["book://医方论/*", "chapter://医方论/卷上"],
                preferred_books=["089-医方论"],
            ),
            "chapter://医方论/卷上",
        )

    def test_planner_prompt_uses_summary_view_instead_of_full_long_snippets(self) -> None:
        prompt = _build_planner_user_prompt(
            query="六味地黄丸出自哪本书？请给出处原文。",
            payload={"retrieval_strategy": {"intent": "formula_origin", "entity_name": "六味地黄丸"}},
            evidence_paths=["entity://六味地黄丸/*", "book://小儿药证直诀/*"],
            factual_evidence=[
                {
                    "source_type": "doc",
                    "source": "小儿药证直诀.txt#42",
                    "predicate": "",
                    "target": "",
                    "snippet": "六味地黄丸，治肾阴不足。" * 20,
                }
            ],
            case_references=[],
            deep_trace=[],
            heuristic_gaps=["origin"],
            max_actions=2,
            executed_actions=["read_evidence_path::entity://六味地黄丸/*"],
            coverage_summary={"gaps": ["origin"], "sufficient": False},
        )

        self.assertIn("factual_summary:", prompt)
        self.assertNotIn("六味地黄丸，治肾阴不足。" * 5, prompt)
        self.assertIn("executed_actions:", prompt)

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
        read_calls = [item for item in navigator.calls if item["tool"] == "read_evidence_path" and item["path"] == "book://小儿药证直诀/*"]
        self.assertTrue(read_calls)
        self.assertIn("熟地黄", str(read_calls[0].get("source_hint", "")))
        self.assertIn("《小儿药证直诀》", result["answer"])

    async def test_deep_mode_keeps_distinct_tool_names_for_parallel_followup_actions(self) -> None:
        payload = {
            "route": "hybrid",
            "route_reason": "compare_entities_forced_hybrid",
            "status": "ok",
            "final_route": "hybrid",
            "executed_routes": ["graph", "retrieval"],
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "逍遥散",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "evidence_paths": ["entity://逍遥散/*", "book://医方集解/*"],
            "graph_result": {"code": 0, "message": "ok", "data": {"relations": []}},
            "retrieval_result": {"code": 0, "message": "ok", "data": {"chunks": []}},
        }
        search_key = json.dumps(
            {"query": "逍遥散 教材佐证", "scope_paths": ["book://医方集解/*"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://逍遥散/*", "book://医方集解/*"],
            read_results={
                "entity://逍遥散/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://逍遥散/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph",
                            "source": "医方集解/卷三",
                            "snippet": "功效: 疏肝解郁",
                            "predicate": "功效",
                            "target": "疏肝解郁",
                            "source_book": "医方集解",
                            "source_chapter": "卷三",
                            "score": 0.91,
                        }
                    ],
                }
            },
            search_results={
                search_key: {
                    "tool": "search_evidence_text",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "doc",
                            "source": "医方集解.txt#12",
                            "snippet": "逍遥散治肝郁血虚，脾失健运。",
                            "source_book": "医方集解",
                            "source_chapter": "第12页",
                            "score": 0.88,
                        }
                    ],
                }
            },
        )
        answer_generator = FakeSequentialAnswerGenerator(
            [
                (
                    "{\"gaps\":[\"comparison\",\"source_trace\"],\"next_actions\":["
                    "{\"skill\":\"compare-formulas\",\"path\":\"entity://逍遥散/*\",\"query\":\"比较逍遥散与柴胡疏肝散\"},"
                    "{\"skill\":\"search-source-text\",\"query\":\"逍遥散 教材佐证\",\"scope_paths\":[\"book://医方集解/*\"]}"
                    "],\"stop_reason\":\"\"}"
                ),
                "Deep 2.0回答：逍遥散可见功效证据，并可补充教材佐证。",
            ]
        )
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=answer_generator,
            evidence_navigator=navigator,
        )

        result = await service.answer("请比较逍遥散和柴胡疏肝散的功效。", mode="deep", top_k=12)

        deep_tools = [item["tool"] for item in result["tool_trace"] if item["tool"] not in {"tcm_route_search", "list_evidence_paths"}]
        self.assertIn("read_evidence_path", deep_tools)
        self.assertIn("search_evidence_text", deep_tools)

    async def test_deep_mode_stops_after_round_when_coverage_becomes_sufficient(self) -> None:
        payload = {
            "route": "hybrid",
            "route_reason": "compare_entities_forced_hybrid",
            "status": "ok",
            "final_route": "hybrid",
            "executed_routes": ["graph", "retrieval"],
            "query_analysis": {
                "dominant_intent": "formula_efficacy",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
            },
            "retrieval_strategy": {
                "intent": "formula_efficacy",
                "entity_name": "逍遥散",
                "compare_entities": ["逍遥散", "柴胡疏肝散"],
                "sources": ["graph_sqlite", "classic_docs"],
            },
            "evidence_paths": ["entity://逍遥散/*", "book://医方集解/*"],
            "graph_result": {"code": 0, "message": "ok", "data": {"relations": []}},
        }
        navigator = FakeEvidenceNavigator(
            listed_paths=["entity://逍遥散/*", "book://医方集解/*"],
            read_results={
                "entity://逍遥散/*": {
                    "tool": "read_evidence_path",
                    "path": "entity://逍遥散/*",
                    "status": "ok",
                    "count": 1,
                    "items": [
                        {
                            "evidence_type": "factual_grounding",
                            "source_type": "graph_path",
                            "source": "医方集解/卷三",
                            "snippet": "逍遥散与柴胡疏肝散病机不同：前者偏养血健脾，后者偏疏肝理气。",
                            "predicate": "功效",
                            "target": "疏肝健脾",
                            "source_book": "医方集解",
                            "source_chapter": "卷三",
                            "anchor_entity": "逍遥散",
                            "path_nodes": ["肝郁血虚", "逍遥散", "柴胡疏肝散"],
                            "score": 0.93,
                        }
                    ],
                }
            },
        )
        answer_generator = FakeSequentialAnswerGenerator(
            [
                "{\"gaps\":[\"comparison\",\"path_reasoning\"],\"next_actions\":[{\"skill\":\"compare-formulas\",\"path\":\"entity://逍遥散/*\",\"query\":\"比较逍遥散与柴胡疏肝散的功效与病机\",\"reason\":\"补充比较证据\"}],\"stop_reason\":\"\"}",
                "Deep增强回答：首轮补证据后已满足比较与病机覆盖。",
            ]
        )
        service = QAService(
            route_tool=FakeRouteTool(payload),
            answer_generator=answer_generator,
            evidence_navigator=navigator,
        )

        result = await service.answer("请比较逍遥散与柴胡疏肝散的功效与病机差异。", mode="deep", top_k=12)

        self.assertEqual(len(answer_generator.calls), 2)
        self.assertTrue(any(step["stage"] == "coverage_ok" and step["detail"] == "round=1" for step in result["planner_steps"]))
        self.assertFalse(any(step["stage"] == "gap_check" and step["detail"].startswith("round=2") for step in result["planner_steps"]))
        self.assertIn("Deep增强回答", result["answer"])


if __name__ == "__main__":
    unittest.main()
