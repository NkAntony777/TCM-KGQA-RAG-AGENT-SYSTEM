from __future__ import annotations

from typing import Any, AsyncIterator

from services.common.medical_guard import assess_query
from services.qa_service.evidence import _factual_evidence_from_payload
from services.qa_service.evidence import _identify_evidence_gaps
from services.qa_service.helpers import _guard_refused_result
from services.qa_service.llm_client import GroundedAnswerLLMClient
from services.qa_service.quick_flow import stream_quick as _stream_quick_flow
from services.qa_service.deep_flow import stream_deep as _stream_deep_flow
from services.qa_service.models import AnswerMode, QAServiceSettings, RouteContext
from services.qa_service.planner import _apply_origin_action_policy, _plan_followup_actions
from services.qa_service.planner_runtime import generate_followup_plan, resolve_followup_actions
from services.qa_service.runtime_support import (
    _build_live_evidence_bundle as _runtime_build_live_evidence_bundle,
    _build_response as _runtime_build_response,
    _can_parallelize_actions as _runtime_can_parallelize_actions,
    _cache_key as _runtime_cache_key,
    _execute_action as _runtime_execute_action,
    _execute_actions_for_round as _runtime_execute_actions_for_round,
    _load_route_payload as _runtime_load_route_payload,
    _prepare_route_context as _runtime_prepare_route_context,
)
from services.qa_service.skill_registry import get_runtime_skills
from tools.tcm_evidence_tools import EvidenceNavigator
from tools.tcm_route_tool import TCMRouteSearchTool

__all__ = [
    "QAService",
    "get_qa_service",
    "_apply_origin_action_policy",
    "_factual_evidence_from_payload",
    "_identify_evidence_gaps",
    "_plan_followup_actions",
]


class QAService:
    def __init__(
        self,
        *,
        route_tool: TCMRouteSearchTool | None = None,
        settings: QAServiceSettings | None = None,
        answer_generator=None,
        evidence_navigator: EvidenceNavigator | None = None,
    ) -> None:
        self.route_tool = route_tool or TCMRouteSearchTool()
        self.settings = settings or QAServiceSettings()
        self.answer_generator = answer_generator or GroundedAnswerLLMClient()
        self.evidence_navigator = evidence_navigator or EvidenceNavigator()
        self.planner_skills = get_runtime_skills(
            executable_only=True,
            allowed_tools={"read_evidence_path", "search_evidence_text"},
        )

    async def answer(
        self,
        query: str,
        *,
        mode: AnswerMode = "quick",
        top_k: int | None = None,
    ) -> dict[str, Any]:
        final_result: dict[str, Any] | None = None
        async for event in self.stream_answer(query, mode=mode, top_k=top_k):
            if event.get("type") == "result" and isinstance(event.get("result"), dict):
                final_result = event["result"]
        if final_result is None:
            raise RuntimeError("qa_result_missing")
        return final_result

    async def stream_answer(
        self,
        query: str,
        *,
        mode: AnswerMode = "quick",
        top_k: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            raise ValueError("query_empty")

        resolved_top_k = max(1, int(top_k or self.settings.default_top_k))
        guard = assess_query(normalized_query)
        if guard.should_refuse:
            result = _guard_refused_result(mode=mode, guard=guard)
            yield {"type": "qa_mode", "mode": mode}
            yield {"type": "token", "content": result["answer"]}
            yield {"type": "done", "content": result["answer"]}
            yield {"type": "result", "result": result}
            return

        if mode == "deep":
            try:
                async for event in self._stream_deep(normalized_query, top_k=resolved_top_k, guard=guard):
                    yield event
                return
            except Exception as exc:
                async for event in self._stream_quick(
                    normalized_query,
                    top_k=resolved_top_k,
                    guard=guard,
                    result_mode="deep",
                    notes_prefix=[f"deep_mode_fallback_to_quick:{exc}"],
                    status_override="degraded",
                    generation_backend_override="quick_fallback",
                ):
                    yield event
                return

        async for event in self._stream_quick(normalized_query, top_k=resolved_top_k, guard=guard):
            yield event

    async def _stream_quick(
        self,
        query: str,
        *,
        top_k: int,
        guard,
        result_mode: AnswerMode = "quick",
        notes_prefix: list[str] | None = None,
        status_override: str | None = None,
        generation_backend_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in _stream_quick_flow(
            self,
            query,
            top_k=top_k,
            guard=guard,
            result_mode=result_mode,
            notes_prefix=notes_prefix,
            status_override=status_override,
            generation_backend_override=generation_backend_override,
        ):
            yield event

    async def _stream_deep(self, query: str, *, top_k: int, guard) -> AsyncIterator[dict[str, Any]]:
        async for event in _stream_deep_flow(self, query, top_k=top_k, guard=guard):
            yield event

    def _load_route_payload(self, *, query: str, top_k: int) -> dict[str, Any]:
        return _runtime_load_route_payload(self.route_tool, query=query, top_k=top_k)

    def _prepare_route_context(
        self,
        *,
        query: str,
        top_k: int,
        include_executed_routes: bool,
        payload: dict[str, Any] | None = None,
    ) -> RouteContext:
        return _runtime_prepare_route_context(
            self.route_tool,
            query=query,
            top_k=top_k,
            include_executed_routes=include_executed_routes,
            payload=payload,
        )

    def _list_evidence_paths(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        request_cache: dict[str, dict[str, Any]],
    ) -> tuple[list[str], bool]:
        strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
        list_cache_key = self._cache_key(
            "list_evidence_paths",
            {
                "query": query,
                "route_signature": payload.get("final_route", payload.get("route")),
                "evidence_paths": payload.get("evidence_paths", []),
                "entity_name": strategy.get("entity_name"),
                "compare_entities": strategy.get("compare_entities", []),
                "symptom_name": strategy.get("symptom_name"),
            },
        )
        list_result = request_cache.get(list_cache_key)
        cache_hit = list_result is not None
        if list_result is None:
            list_result = self.evidence_navigator.list_evidence_paths(query=query, route_payload=payload)
            request_cache[list_cache_key] = dict(list_result)
        paths = list(list_result.get("paths", [])) if isinstance(list_result.get("paths"), list) else []
        return paths, cache_hit

    def _should_run_quick_followup(self, *, payload: dict[str, Any], heuristic_gaps: list[str]) -> bool:
        if self.settings.max_quick_followup_actions <= 0 or not heuristic_gaps:
            return False
        quick_followup_gaps = {
            "composition",
            "efficacy",
            "indication",
            "origin",
            "source_trace",
            "path_reasoning",
            "comparison",
            "case_reference",
            "syndrome_formula",
        }
        if not any(gap in quick_followup_gaps for gap in heuristic_gaps):
            return False
        return str(payload.get("status", "ok") or "ok") in {"ok", "degraded"}

    def _quick_followup_action_limit(self, *, heuristic_gaps: list[str]) -> int:
        if self.settings.max_quick_followup_actions <= 0:
            return 0
        gap_set = {gap for gap in heuristic_gaps if gap}
        preferred_limit = 1
        if "comparison" in gap_set:
            preferred_limit = 2
        elif len(gap_set.intersection({"origin", "source_trace", "path_reasoning"})) >= 2:
            preferred_limit = 2
        return min(self.settings.max_quick_followup_actions, preferred_limit)

    def _resolve_followup_actions(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        evidence_paths: list[str],
        factual_evidence: list[dict[str, Any]],
        plan: dict[str, Any],
        heuristic_gaps: list[str],
        plan_gaps: list[str],
        executed_actions: set[str],
    ) -> list[dict[str, Any]]:
        return resolve_followup_actions(
            planner_skills=self.planner_skills,
            settings=self.settings,
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            plan=plan,
            heuristic_gaps=heuristic_gaps,
            plan_gaps=plan_gaps,
            executed_actions=executed_actions,
        )

    async def _generate_followup_plan(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        evidence_paths: list[str],
        factual_evidence: list[dict[str, Any]],
        case_references: list[dict[str, Any]],
        deep_trace: list[dict[str, Any]],
        heuristic_gaps: list[str],
        coverage_summary: dict[str, Any],
        executed_actions: set[str],
    ) -> tuple[dict[str, Any], str, str | None]:
        return await generate_followup_plan(
            planner_skills=self.planner_skills,
            settings=self.settings,
            answer_generator=self.answer_generator,
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            case_references=case_references,
            deep_trace=deep_trace,
            heuristic_gaps=heuristic_gaps,
            coverage_summary=coverage_summary,
            executed_actions=executed_actions,
        )

    @staticmethod
    def _cache_key(tool: str, payload: dict[str, Any]) -> str:
        return _runtime_cache_key(tool, payload)

    async def _build_response(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        mode: AnswerMode,
        factual_evidence: list[dict[str, Any]] | None = None,
        case_references: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
        notes: list[str] | None = None,
        evidence_paths: list[str] | None = None,
        planner_steps: list[dict[str, str]] | None = None,
        deep_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await _runtime_build_response(
            answer_generator=self.answer_generator,
            settings=self.settings,
            query=query,
            payload=payload,
            mode=mode,
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=tool_trace,
            notes=notes,
            evidence_paths=evidence_paths,
            planner_steps=planner_steps,
            deep_trace=deep_trace,
        )

    def _build_live_evidence_bundle(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        evidence_paths: list[str],
        factual_evidence: list[dict[str, Any]],
        case_references: list[dict[str, Any]],
        coverage_summary: dict[str, Any] | None,
        planner_steps: list[dict[str, str]],
        deep_trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return _runtime_build_live_evidence_bundle(
            settings=self.settings,
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            case_references=case_references,
            coverage_summary=coverage_summary,
            planner_steps=planner_steps,
            deep_trace=deep_trace,
        )

    async def _execute_actions_for_round(
        self,
        *,
        actions: list[dict[str, Any]],
        request_cache: dict[str, dict[str, Any]],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return await _runtime_execute_actions_for_round(
            evidence_navigator=self.evidence_navigator,
            settings=self.settings,
            actions=actions,
            request_cache=request_cache,
        )

    def _execute_action(
        self,
        action: dict[str, Any],
        *,
        request_cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return _runtime_execute_action(
            evidence_navigator=self.evidence_navigator,
            settings=self.settings,
            action=action,
            request_cache=request_cache,
        )

    @staticmethod
    def _can_parallelize_actions(actions: list[dict[str, Any]]) -> bool:
        return _runtime_can_parallelize_actions(actions)


_qa_service: QAService | None = None


def get_qa_service() -> QAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service
