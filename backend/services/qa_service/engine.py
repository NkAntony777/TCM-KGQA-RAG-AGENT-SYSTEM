from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from services.common.medical_guard import assess_query
from services.qa_service.evidence import (
    _build_book_citations,
    _build_citations,
    _case_reference_from_payload,
    _coverage_gaps_from_state,
    _coverage_summary_from_state,
    _coverage_summary,
    _factual_evidence_from_payload,
    _identify_evidence_gaps,
    _init_coverage_state,
    _merge_evidence_items,
    _new_unique_evidence,
    _update_coverage_state,
)
from services.qa_service.helpers import (
    _compact_json,
    _extract_json_object,
    _finalize_result,
    _guard_refused_result,
    _planner_step,
    _planner_step_for_action,
    _route_from_payload,
    _safe_json_loads,
    _tool_input_for_action,
    _trace_step,
)
from services.qa_service.llm_client import GroundedAnswerLLMClient
from services.qa_service.models import AnswerMode, QAServiceSettings, RouteContext
from services.qa_service.planner import (
    _action_key,
    _apply_origin_action_policy,
    _normalize_gap_names,
    _normalize_planner_actions,
    _plan_followup_actions,
)
from services.qa_service.prompts import (
    _build_grounded_system_prompt,
    _build_grounded_user_prompt,
    _build_planner_system_prompt,
    _build_planner_user_prompt,
    _compose_fallback_answer,
)
from services.qa_service.skill_registry import get_runtime_skills
from tools.tcm_evidence_tools import EvidenceNavigator
from tools.tcm_route_tool import TCMRouteSearchTool


class QAService:
    def __init__(
        self,
        *,
        route_tool: TCMRouteSearchTool | None = None,
        agent_manager_ref=None,
        settings: QAServiceSettings | None = None,
        answer_generator=None,
        evidence_navigator: EvidenceNavigator | None = None,
    ) -> None:
        self.route_tool = route_tool or TCMRouteSearchTool()
        self.agent_manager = agent_manager_ref
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
        yield {"type": "qa_mode", "mode": result_mode}

        route_context = self._prepare_route_context(query=query, top_k=top_k, include_executed_routes=False)
        payload = route_context.payload
        planner_steps = [
            _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={payload.get('final_route', payload.get('route', 'unknown'))}"),
            _planner_step(stage="answer_synthesis", label="生成最终答案", detail="quick_grounded_answer"),
        ]
        yield {"type": "planner_step", "step": planner_steps[0]}
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
        yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_context.route_meta), "meta": route_context.route_meta}

        if route_context.route_event:
            yield {"type": "route", **route_context.route_event}

        factual_evidence = route_context.factual_evidence
        case_references = route_context.case_references
        initial_items = factual_evidence + case_references
        if initial_items:
            yield {"type": "evidence", "items": initial_items}

        result = await self._build_response(
            query=query,
            payload=payload,
            mode=result_mode,
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=[{"tool": "tcm_route_search", "meta": route_context.route_meta}],
            notes=list(notes_prefix or []),
            evidence_paths=payload.get("evidence_paths", []),
            planner_steps=planner_steps,
            deep_trace=[],
        )
        if status_override:
            result["status"] = status_override
        if generation_backend_override:
            result["generation_backend"] = generation_backend_override
        result = _finalize_result(result=result, guard=guard)

        if result.get("notes"):
            yield {"type": "notes", "items": result["notes"]}
        if result.get("citations"):
            yield {"type": "citations", "items": result["citations"]}
        if result.get("evidence_bundle"):
            yield {"type": "evidence_bundle", "bundle": result["evidence_bundle"]}
        yield {"type": "planner_step", "step": planner_steps[-1]}
        yield {"type": "token", "content": result["answer"]}
        yield {"type": "done", "content": result["answer"]}
        yield {"type": "result", "result": result}

    async def _stream_deep(self, query: str, *, top_k: int, guard) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "qa_mode", "mode": "deep"}
        request_cache: dict[str, dict[str, Any]] = {}

        payload = self._load_route_payload(query=query, top_k=top_k)
        if payload.get("notes") == ["route_output_unparseable"]:
            async for event in self._stream_quick(
                query,
                top_k=top_k,
                guard=guard,
                result_mode="deep",
                notes_prefix=["deep_mode_fallback_to_quick:route_output_unparseable"],
                status_override="degraded",
                generation_backend_override="quick_fallback",
            ):
                yield event
            return

        route_context = self._prepare_route_context(query=query, top_k=top_k, include_executed_routes=True, payload=payload)
        planner_steps: list[dict[str, str]] = []
        deep_trace: list[dict[str, Any]] = []
        notes: list[str] = []
        tool_trace: list[dict[str, Any]] = []

        route_step = _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={route_context.route_meta['final_route']}")
        planner_steps.append(route_step)
        yield {"type": "planner_step", "step": route_step}
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
        yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_context.route_meta), "meta": route_context.route_meta}
        tool_trace.append({"tool": "tcm_route_search", "meta": route_context.route_meta})

        if route_context.route_event:
            yield {"type": "route", **route_context.route_event}

        factual_evidence = route_context.factual_evidence
        case_references = route_context.case_references
        initial_items = factual_evidence + case_references
        if initial_items:
            yield {"type": "evidence", "items": initial_items}

        list_step = _planner_step(stage="inspect_paths", label="整理证据路径", detail="derive_from_route_payload")
        planner_steps.append(list_step)
        yield {"type": "planner_step", "step": list_step}
        yield {"type": "tool_start", "tool": "list_evidence_paths", "input": _compact_json({"query": query})}
        list_cache_key = self._cache_key(
            "list_evidence_paths",
            {"query": query, "route_signature": payload.get("final_route", payload.get("route")), "evidence_paths": payload.get("evidence_paths", [])},
        )
        list_result = request_cache.get(list_cache_key)
        list_cache_hit = list_result is not None
        if list_result is None:
            list_result = self.evidence_navigator.list_evidence_paths(query=query, route_payload=payload)
            request_cache[list_cache_key] = dict(list_result)
        evidence_paths = list(list_result.get("paths", [])) if isinstance(list_result.get("paths"), list) else []
        coverage_state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
        _update_coverage_state(
            coverage_state,
            new_factual_evidence=factual_evidence,
            new_case_references=case_references,
        )
        list_meta = {"count": len(evidence_paths), "query": query, "cache_hit": list_cache_hit}
        yield {"type": "tool_end", "tool": "list_evidence_paths", "output": _compact_json(list_meta), "meta": list_meta}
        tool_trace.append({"tool": "list_evidence_paths", "meta": list_meta})
        yield {"type": "new_response"}

        executed_actions: set[str] = set()
        for round_index in range(1, self.settings.max_deep_rounds + 1):
            heuristic_gaps = _coverage_gaps_from_state(coverage_state)
            gap_step = _planner_step(stage="gap_check", label="分析证据缺口", detail=f"round={round_index}; gaps={','.join(heuristic_gaps) or 'none'}")
            planner_steps.append(gap_step)
            yield {"type": "planner_step", "step": gap_step}
            if not heuristic_gaps:
                notes.append(f"deep_round_{round_index}:coverage_sufficient")
                stop_step = _planner_step(stage="coverage_ok", label="证据覆盖满足", detail=f"round={round_index}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break

            plan, planner_backend, planner_note = await self._generate_followup_plan(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                case_references=case_references,
                deep_trace=deep_trace,
                heuristic_gaps=heuristic_gaps,
                coverage_summary=_coverage_summary_from_state(coverage_state),
                executed_actions=executed_actions,
            )
            if planner_note:
                notes.append(planner_note)
            plan_step = _planner_step(stage="planner", label="规划下一步检索", detail=f"round={round_index}; backend={planner_backend}; actions={len(plan.get('next_actions', []))}")
            planner_steps.append(plan_step)
            yield {"type": "planner_step", "step": plan_step}

            plan_gaps = [str(item).strip() for item in plan.get("gaps", []) if str(item).strip()] if isinstance(plan.get("gaps"), list) else heuristic_gaps
            actions = self._resolve_followup_actions(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                plan=plan,
                heuristic_gaps=heuristic_gaps,
                plan_gaps=plan_gaps,
                executed_actions=executed_actions,
            )
            if not actions:
                stop_reason = str(plan.get("stop_reason", "") or "no_followup_action").strip()
                notes.append(f"deep_round_{round_index}:{stop_reason}")
                stop_step = _planner_step(stage="stop", label="结束补检索", detail=f"round={round_index}; reason={stop_reason}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break

            new_items_this_round = 0
            for action_index, action in enumerate(actions, start=1):
                executed_actions.add(_action_key(action))
                step = _planner_step_for_action(action=action, round_index=round_index, action_index=action_index)
                planner_steps.append(step)
                yield {"type": "planner_step", "step": step}
                tool_name = str(action.get("tool", "followup"))
                yield {"type": "tool_start", "tool": tool_name, "input": _tool_input_for_action(action)}
            action_batch_results = await self._execute_actions_for_round(
                actions=actions,
                request_cache=request_cache,
            )
            for action_index, (action, result) in enumerate(action_batch_results, start=1):
                coverage_before = _coverage_summary_from_state(coverage_state)
                tool_name = str(action.get("tool", "followup"))
                action_status = str(result.get("status", "ok") or "ok")
                meta = {
                    "status": action_status,
                    "count": result.get("count", 0),
                    "reason": action.get("reason", ""),
                    "path": action.get("path"),
                    "query": action.get("query"),
                    "skill": action.get("skill"),
                    "cache_hit": bool(result.get("cache_hit")),
                }
                yield {"type": "tool_end", "tool": tool_name, "output": _compact_json(meta), "meta": meta}
                tool_trace.append({"tool": tool_name, "meta": meta})

                items = result.get("items", []) if isinstance(result.get("items"), list) else []
                if not items:
                    trace_step = _trace_step(
                        step_index=len(deep_trace) + 1,
                        round_index=round_index,
                        action_index=action_index,
                        action=action,
                        status=action_status,
                        new_evidence=[],
                        coverage_before_step=coverage_before,
                        coverage_after_step=_coverage_summary_from_state(coverage_state),
                    )
                    deep_trace.append(trace_step)
                    yield {"type": "deep_trace_step", "step": trace_step}
                    yield {
                        "type": "evidence_bundle",
                        "bundle": self._build_live_evidence_bundle(
                            query=query,
                            payload=payload,
                            evidence_paths=evidence_paths,
                            factual_evidence=factual_evidence,
                            case_references=case_references,
                            coverage_summary=_coverage_summary_from_state(coverage_state),
                            planner_steps=planner_steps,
                            deep_trace=deep_trace,
                        ),
                    }
                    yield {"type": "new_response"}
                    continue

                new_factual = [item for item in items if str(item.get("evidence_type", "")).strip() != "case_reference"]
                new_cases = [item for item in items if str(item.get("evidence_type", "")).strip() == "case_reference"]
                added_factual: list[dict[str, Any]] = []
                added_cases: list[dict[str, Any]] = []
                if new_factual:
                    added_factual = _new_unique_evidence(primary=new_factual, existing=factual_evidence)
                    factual_evidence = _merge_evidence_items(primary=new_factual, fallback=factual_evidence)
                    new_items_this_round += len(added_factual)
                if new_cases:
                    added_cases = _new_unique_evidence(primary=new_cases, existing=case_references)
                    case_references = _merge_evidence_items(primary=new_cases, fallback=case_references)
                    new_items_this_round += len(added_cases)
                merged_new_items = added_factual + added_cases
                _update_coverage_state(
                    coverage_state,
                    new_factual_evidence=added_factual,
                    new_case_references=added_cases,
                )
                if merged_new_items:
                    yield {"type": "evidence", "items": merged_new_items}
                trace_step = _trace_step(
                    step_index=len(deep_trace) + 1,
                    round_index=round_index,
                    action_index=action_index,
                    action=action,
                    status=action_status,
                    new_evidence=merged_new_items[: self.settings.max_trace_evidence_per_step],
                    coverage_before_step=coverage_before,
                    coverage_after_step=_coverage_summary_from_state(coverage_state),
                )
                deep_trace.append(trace_step)
                yield {"type": "deep_trace_step", "step": trace_step}
                yield {
                    "type": "evidence_bundle",
                    "bundle": self._build_live_evidence_bundle(
                        query=query,
                        payload=payload,
                        evidence_paths=evidence_paths,
                        factual_evidence=factual_evidence,
                        case_references=case_references,
                        coverage_summary=_coverage_summary_from_state(coverage_state),
                        planner_steps=planner_steps,
                        deep_trace=deep_trace,
                    ),
                }
                yield {"type": "new_response"}

            if new_items_this_round <= 0:
                notes.append(f"deep_round_{round_index}:no_new_evidence")
                stop_step = _planner_step(stage="stop", label="未补到新证据", detail=f"round={round_index}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break
        else:
            notes.append("deep_round_limit_reached")
            stop_step = _planner_step(stage="stop", label="达到轮次上限", detail=f"max_rounds={self.settings.max_deep_rounds}")
            planner_steps.append(stop_step)
            yield {"type": "planner_step", "step": stop_step}

        answer_step = _planner_step(stage="answer_synthesis", label="生成最终答案", detail="deep_grounded_answer")
        planner_steps.append(answer_step)
        yield {"type": "new_response"}
        yield {"type": "planner_step", "step": answer_step}

        result = await self._build_response(
            query=query,
            payload=payload,
            mode="deep",
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=tool_trace,
            notes=notes,
            evidence_paths=evidence_paths,
            planner_steps=planner_steps,
            deep_trace=deep_trace,
        )
        result = _finalize_result(result=result, guard=guard)

        if result.get("notes"):
            yield {"type": "notes", "items": result["notes"]}
        if result.get("citations"):
            yield {"type": "citations", "items": result["citations"]}
        if result.get("evidence_bundle"):
            yield {"type": "evidence_bundle", "bundle": result["evidence_bundle"]}
        yield {"type": "token", "content": result["answer"]}
        yield {"type": "done", "content": result["answer"]}
        yield {"type": "result", "result": result}

    def _load_route_payload(self, *, query: str, top_k: int) -> dict[str, Any]:
        route_output = self.route_tool._run(query=query, top_k=top_k)
        payload = _safe_json_loads(route_output)
        if isinstance(payload, dict):
            return payload
        return {"status": "evidence_insufficient", "notes": ["route_output_unparseable"]}

    def _prepare_route_context(
        self,
        *,
        query: str,
        top_k: int,
        include_executed_routes: bool,
        payload: dict[str, Any] | None = None,
    ) -> RouteContext:
        resolved_payload = payload or self._load_route_payload(query=query, top_k=top_k)
        route_meta = {
            "status": resolved_payload.get("status", "evidence_insufficient" if not include_executed_routes else "ok"),
            "final_route": resolved_payload.get("final_route", resolved_payload.get("route")),
            "query": query,
        }
        if include_executed_routes:
            route_meta["executed_routes"] = resolved_payload.get("executed_routes", [])
        else:
            route_meta["count"] = len(resolved_payload.get("evidence_paths", [])) if isinstance(resolved_payload.get("evidence_paths"), list) else 0
        return RouteContext(
            payload=resolved_payload,
            route_meta=route_meta,
            route_event=_route_from_payload(resolved_payload),
            factual_evidence=_factual_evidence_from_payload(resolved_payload),
            case_references=_case_reference_from_payload(resolved_payload),
        )

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
        planner_payload = {**payload, "_planner_factual_evidence": factual_evidence}
        resolved_gaps = plan_gaps or heuristic_gaps
        raw_actions = plan.get("next_actions", []) if isinstance(plan.get("next_actions"), list) else []
        actions = _normalize_planner_actions(
            planner_skills=self.planner_skills,
            raw_actions=raw_actions,
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            executed_actions=executed_actions,
            max_actions=self.settings.max_actions_per_round,
        )
        if not actions:
            fallback_actions = _plan_followup_actions(
                planner_skills=self.planner_skills,
                query=query,
                payload=planner_payload,
                evidence_paths=evidence_paths,
                gaps=resolved_gaps,
                max_actions=self.settings.max_actions_per_round,
                executed_actions=executed_actions,
            )
            actions = _normalize_planner_actions(
                planner_skills=self.planner_skills,
                raw_actions=fallback_actions,
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                executed_actions=executed_actions,
                max_actions=self.settings.max_actions_per_round,
            )
        return _apply_origin_action_policy(
            planner_skills=self.planner_skills,
            query=query,
            payload=planner_payload,
            evidence_paths=evidence_paths,
            gaps=resolved_gaps,
            actions=actions,
            max_actions=self.settings.max_actions_per_round,
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
        fallback_plan = {
            "gaps": heuristic_gaps,
            "next_actions": _plan_followup_actions(
                planner_skills=self.planner_skills,
                query=query,
                payload={**payload, "_planner_factual_evidence": factual_evidence},
                evidence_paths=evidence_paths,
                gaps=heuristic_gaps,
                max_actions=self.settings.max_actions_per_round,
                executed_actions=executed_actions,
            ),
            "stop_reason": "",
        }
        try:
            content = await self.answer_generator.acomplete(
                system_prompt=_build_planner_system_prompt(self.planner_skills),
                user_prompt=_build_planner_user_prompt(
                    query=query,
                    payload=payload,
                    evidence_paths=evidence_paths,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    deep_trace=deep_trace,
                    heuristic_gaps=heuristic_gaps,
                    max_actions=self.settings.max_actions_per_round,
                    executed_actions=sorted(executed_actions),
                    coverage_summary=coverage_summary,
                ),
            )
            parsed = _extract_json_object(content)
            if not isinstance(parsed, dict):
                raise RuntimeError("planner_json_unparseable")
            parsed["gaps"] = _normalize_gap_names(parsed.get("gaps", [])) or heuristic_gaps
            parsed.setdefault("next_actions", [])
            parsed.setdefault("stop_reason", "")
            return parsed, "planner_llm", None
        except Exception as exc:
            return fallback_plan, "heuristic_planner", f"planner_llm_fallback:{exc}"

    def _execute_action(self, action: dict[str, Any], *, request_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
        tool = str(action.get("tool", "")).strip()
        cache_key = self._cache_key(
            tool,
            {
                "path": action.get("path", ""),
                "query": action.get("query", ""),
                "source_hint": action.get("source_hint", ""),
                "scope_paths": action.get("scope_paths", []),
                "top_k": int(action.get("top_k", self.settings.deep_read_top_k) or self.settings.deep_read_top_k),
            },
        )
        cached = request_cache.get(cache_key)
        if cached is not None:
            return {**cached, "cache_hit": True}

        if tool == "read_evidence_path":
            result = self.evidence_navigator.read_evidence_path(
                path=str(action.get("path", "")),
                query=str(action.get("query", "")),
                source_hint=str(action.get("source_hint", "")),
                top_k=int(action.get("top_k", self.settings.deep_read_top_k) or self.settings.deep_read_top_k),
            )
            request_cache[cache_key] = dict(result)
            return {**result, "cache_hit": False}
        if tool == "search_evidence_text":
            scopes = action.get("scope_paths", [])
            result = self.evidence_navigator.search_evidence_text(
                query=str(action.get("query", "")),
                source_hint=str(action.get("source_hint", "")),
                scope_paths=scopes if isinstance(scopes, list) else [],
                top_k=int(action.get("top_k", self.settings.deep_read_top_k) or self.settings.deep_read_top_k),
            )
            request_cache[cache_key] = dict(result)
            return {**result, "cache_hit": False}
        return {"tool": tool or "unknown", "status": "error", "count": 0, "items": [], "cache_hit": False}

    @staticmethod
    def _cache_key(tool: str, payload: dict[str, Any]) -> str:
        return f"{tool}::{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"

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
        factual = factual_evidence or _factual_evidence_from_payload(payload)
        cases = case_references or _case_reference_from_payload(payload)
        book_citations = _build_book_citations(factual_evidence=factual)
        citations = _build_citations(
            factual_evidence=factual,
            case_references=cases,
            book_citations=book_citations,
            limit=self.settings.max_citations,
        )
        answer, generation_backend, generation_notes = await self._generate_grounded_answer(
            query=query,
            payload=payload,
            mode=mode,
            factual_evidence=factual,
            case_references=cases,
            citations=citations,
            notes=notes or [],
            book_citations=book_citations,
            deep_trace=deep_trace or [],
        )
        selected_factual = factual[: self.settings.max_factual_evidence]
        selected_cases = cases[: self.settings.max_case_references]
        coverage = _coverage_summary(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths or [],
            factual_evidence=factual,
            case_references=cases,
        )
        return {
            "mode": mode,
            "status": str(payload.get("status", "ok") or "ok"),
            "answer": answer,
            "query_analysis": payload.get("query_analysis", {}),
            "retrieval_strategy": payload.get("retrieval_strategy", {}),
            "route": _route_from_payload(payload),
            "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
            "factual_evidence": selected_factual,
            "case_references": selected_cases,
            "citations": citations,
            "book_citations": book_citations,
            "planner_steps": planner_steps or [],
            "deep_trace": deep_trace or [],
            "evidence_bundle": {
                "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
                "factual_evidence": selected_factual,
                "case_references": selected_cases,
                "book_citations": book_citations,
                "coverage": coverage,
                "planner_steps": planner_steps or [],
                "deep_trace": deep_trace or [],
            },
            "service_trace_ids": payload.get("service_trace_ids", {}),
            "service_backends": payload.get("service_backends", {}),
            "generation_backend": generation_backend,
            "tool_trace": tool_trace or [],
            "notes": list(notes or []) + list(generation_notes),
        }

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
        selected_factual = factual_evidence[: self.settings.max_factual_evidence]
        selected_cases = case_references[: self.settings.max_case_references]
        return {
            "evidence_paths": evidence_paths,
            "factual_evidence": selected_factual,
            "case_references": selected_cases,
            "book_citations": _build_book_citations(factual_evidence=factual_evidence),
            "coverage": coverage_summary
            or _coverage_summary(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                case_references=case_references,
            ),
            "planner_steps": planner_steps,
            "deep_trace": deep_trace,
        }

    async def _execute_actions_for_round(
        self,
        *,
        actions: list[dict[str, Any]],
        request_cache: dict[str, dict[str, Any]],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        if self._can_parallelize_actions(actions):
            tasks = [
                asyncio.to_thread(self._execute_action, action, request_cache=request_cache)
                for action in actions
            ]
            results = await asyncio.gather(*tasks)
            return list(zip(actions, results))
        return [
            (action, self._execute_action(action, request_cache=request_cache))
            for action in actions
        ]

    @staticmethod
    def _can_parallelize_actions(actions: list[dict[str, Any]]) -> bool:
        if len(actions) < 2:
            return False
        parallel_safe_skills = {
            "search-source-text",
            "find-case-reference",
            "read-syndrome-treatment",
            "compare-formulas",
            "trace-source-passage",
        }
        if any(str(action.get("skill", "")).strip() not in parallel_safe_skills for action in actions):
            return False
        keys = {
            (
                str(action.get("tool", "")).strip(),
                str(action.get("path", "")).strip(),
                str(action.get("query", "")).strip(),
                tuple(str(item).strip() for item in action.get("scope_paths", []) if str(item).strip())
                if isinstance(action.get("scope_paths"), list)
                else (),
            )
            for action in actions
        }
        return len(keys) == len(actions)

    async def _generate_grounded_answer(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        mode: AnswerMode,
        factual_evidence: list[dict[str, Any]],
        case_references: list[dict[str, Any]],
        citations: list[str],
        notes: list[str],
        book_citations: list[str],
        deep_trace: list[dict[str, Any]],
    ) -> tuple[str, str, list[str]]:
        try:
            content = await self.answer_generator.acomplete(
                system_prompt=_build_grounded_system_prompt(mode=mode),
                user_prompt=_build_grounded_user_prompt(
                    query=query,
                    payload=payload,
                    mode=mode,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    citations=citations,
                    notes=notes,
                    book_citations=book_citations,
                    deep_trace=deep_trace,
                    evidence_limit=self.settings.max_quick_prompt_evidence if mode == "quick" else self.settings.max_deep_prompt_evidence,
                ),
            )
            if content:
                return content, "grounded_llm" if mode == "quick" else "planner_llm", []
            raise RuntimeError("llm_empty_response")
        except Exception as exc:
            return (
                _compose_fallback_answer(
                    query=query,
                    payload=payload,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    citations=citations,
                ),
                "deterministic_quick_fallback" if mode == "quick" else "planner_deterministic_fallback",
                [f"{mode}_llm_fallback:{exc}"],
            )


_qa_service: QAService | None = None


def get_qa_service() -> QAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service
