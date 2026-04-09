from __future__ import annotations

from typing import Any, AsyncIterator

from services.common.medical_guard import assess_query
from services.qa_service.evidence import (
    _coverage_gaps_from_state,
    _coverage_summary_from_state,
    _factual_evidence_from_payload,
    _identify_evidence_gaps,
    _init_coverage_state,
    _merge_evidence_items,
    _new_unique_evidence,
    _update_coverage_state,
)
from services.qa_service.helpers import (
    _compact_json,
    _finalize_result,
    _guard_refused_result,
    _planner_step,
    _planner_step_for_action,
    _tool_input_for_action,
    _trace_step,
)
from services.qa_service.llm_client import GroundedAnswerLLMClient
from services.qa_service.models import AnswerMode, QAServiceSettings, RouteContext
from services.qa_service.planner import _action_key, _apply_origin_action_policy, _plan_followup_actions
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
        request_cache: dict[str, dict[str, Any]] = {}
        planner_steps = [
            _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={payload.get('final_route', payload.get('route', 'unknown'))}"),
        ]
        yield {"type": "planner_step", "step": planner_steps[0]}
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
        yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_context.route_meta), "meta": route_context.route_meta}

        if route_context.route_event:
            yield {"type": "route", **route_context.route_event}

        tool_trace = [{"tool": "tcm_route_search", "meta": route_context.route_meta}]
        notes = list(notes_prefix or [])
        evidence_paths = list(payload.get("evidence_paths", [])) if isinstance(payload.get("evidence_paths"), list) else []
        factual_evidence = route_context.factual_evidence
        case_references = route_context.case_references
        initial_items = factual_evidence + case_references
        if initial_items:
            yield {"type": "evidence", "items": initial_items}

        coverage_state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
        _update_coverage_state(
            coverage_state,
            new_factual_evidence=factual_evidence,
            new_case_references=case_references,
        )
        heuristic_gaps = _coverage_gaps_from_state(coverage_state)

        if self._should_run_quick_followup(payload=payload, heuristic_gaps=heuristic_gaps):
            gap_step = _planner_step(
                stage="gap_check",
                label="分析证据缺口",
                detail=f"quick; gaps={','.join(heuristic_gaps) or 'none'}",
            )
            planner_steps.append(gap_step)
            yield {"type": "planner_step", "step": gap_step}

            list_step = _planner_step(stage="inspect_paths", label="整理证据路径", detail="quick_followup")
            planner_steps.append(list_step)
            yield {"type": "planner_step", "step": list_step}
            yield {"type": "tool_start", "tool": "list_evidence_paths", "input": _compact_json({"query": query})}
            listed_paths, list_cache_hit = self._list_evidence_paths(query=query, payload=payload, request_cache=request_cache)
            if listed_paths:
                evidence_paths = listed_paths
            coverage_state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
            _update_coverage_state(
                coverage_state,
                new_factual_evidence=factual_evidence,
                new_case_references=case_references,
            )
            heuristic_gaps = _coverage_gaps_from_state(coverage_state)
            list_meta = {"count": len(evidence_paths), "query": query, "cache_hit": list_cache_hit}
            yield {"type": "tool_end", "tool": "list_evidence_paths", "output": _compact_json(list_meta), "meta": list_meta}
            tool_trace.append({"tool": "list_evidence_paths", "meta": list_meta})

            planned_actions = self._resolve_followup_actions(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                plan={"gaps": heuristic_gaps, "next_actions": []},
                heuristic_gaps=heuristic_gaps,
                plan_gaps=heuristic_gaps,
                executed_actions=set(),
            )
            actions = planned_actions[: self._quick_followup_action_limit(heuristic_gaps=heuristic_gaps)]

            if actions:
                follow_step = _planner_step(
                    stage="quick_followup",
                    label="快速补证据",
                    detail=f"actions={len(actions)}; gaps={','.join(heuristic_gaps) or 'none'}",
                )
                planner_steps.append(follow_step)
                yield {"type": "planner_step", "step": follow_step}
                for action in actions:
                    yield {"type": "tool_start", "tool": str(action.get('tool', 'followup')), "input": _tool_input_for_action(action)}
                action_batch_results = await self._execute_actions_for_round(actions=actions, request_cache=request_cache)
                for action, result in action_batch_results:
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
                        continue
                    new_factual = [item for item in items if str(item.get("evidence_type", "")).strip() != "case_reference"]
                    new_cases = [item for item in items if str(item.get("evidence_type", "")).strip() == "case_reference"]
                    added_factual = _new_unique_evidence(primary=new_factual, existing=factual_evidence) if new_factual else []
                    added_cases = _new_unique_evidence(primary=new_cases, existing=case_references) if new_cases else []
                    if added_factual:
                        factual_evidence = _merge_evidence_items(primary=new_factual, fallback=factual_evidence)
                    if added_cases:
                        case_references = _merge_evidence_items(primary=new_cases, fallback=case_references)
                    _update_coverage_state(
                        coverage_state,
                        new_factual_evidence=added_factual,
                        new_case_references=added_cases,
                    )
                    merged_new_items = added_factual + added_cases
                    if merged_new_items:
                        yield {"type": "evidence", "items": merged_new_items}
                remaining_gaps = _coverage_gaps_from_state(coverage_state)
                if remaining_gaps:
                    notes.append(f"quick_followup_remaining_gaps:{','.join(remaining_gaps)}")

        answer_step = _planner_step(stage="answer_synthesis", label="生成最终答案", detail="quick_grounded_answer")
        planner_steps.append(answer_step)
        result = await self._build_response(
            query=query,
            payload=payload,
            mode=result_mode,
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=tool_trace,
            notes=notes,
            evidence_paths=evidence_paths,
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
        yield {"type": "planner_step", "step": answer_step}
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
        evidence_paths, list_cache_hit = self._list_evidence_paths(query=query, payload=payload, request_cache=request_cache)
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
            remaining_gaps = _coverage_gaps_from_state(coverage_state)
            if not remaining_gaps:
                notes.append(f"deep_round_{round_index}:coverage_sufficient")
                stop_step = _planner_step(stage="coverage_ok", label="证据覆盖满足", detail=f"round={round_index}")
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
