from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator

from services.qa_service._base_flow import (
    _assign_initial_evidence,
    _build_action_meta,
    _process_action_items,
    _yield_answer_synthesis_step,
    _yield_evidence_org_step,
    _yield_final_results,
    _yield_initial_evidence,
    _yield_qa_mode,
    _yield_retrieval_step,
    _yield_route_decision_step,
    _yield_route_event,
    _yield_route_search,
)
from services.qa_service.evidence import (
    _coverage_gaps_from_state,
    _coverage_summary_from_state,
    _deep_quality_gaps_from_state,
    _init_coverage_state,
    _update_coverage_state,
)
from services.qa_service.helpers import (
    _compact_json,
    _planner_step,
    _planner_step_for_action,
    _tool_input_for_action,
    _trace_step,
)
from services.qa_service.planner import _action_key

if TYPE_CHECKING:
    from services.qa_service.engine import QAService


async def stream_deep(
    service: "QAService",
    query: str,
    *,
    top_k: int,
    guard,
    full_evidence_mode: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    async for event in _yield_qa_mode("deep"):
        yield event
    await asyncio.sleep(0)
    request_cache: dict[str, dict[str, Any]] = {}

    planner_steps: list[dict[str, str]] = []
    async for event in _yield_route_decision_step(query, planner_steps):
        yield event

    payload = service._load_route_payload(query=query, top_k=top_k)
    if payload.get("notes") == ["route_output_unparseable"]:
        async for event in service._stream_quick(
            query,
            top_k=top_k,
            guard=guard,
            result_mode="deep",
            notes_prefix=["deep_mode_fallback_to_quick:route_output_unparseable"],
            status_override="degraded",
            generation_backend_override="quick_fallback",
            full_evidence_mode=full_evidence_mode,
        ):
            yield event
        return

    route_context = service._prepare_route_context(query=query, top_k=top_k, include_executed_routes=True, payload=payload)
    deep_trace: list[dict[str, Any]] = []
    notes: list[str] = []
    tool_trace: list[dict[str, Any]] = []

    async for event in _yield_route_search(query, top_k, route_context, planner_steps, tool_trace):
        yield event

    async for event in _yield_route_event(route_context):
        yield event

    factual_evidence, case_references, initial_items = _assign_initial_evidence(route_context)

    async for event in _yield_initial_evidence(initial_items):
        yield event

    async for event in _yield_retrieval_step(planner_steps):
        yield event

    async for event in _yield_evidence_org_step(planner_steps, factual_evidence, case_references):
        yield event

    list_step = _planner_step(stage="inspect_paths", label="整理证据路径", detail="derive_from_route_payload")
    planner_steps.append(list_step)
    yield {"type": "planner_step", "step": list_step}
    yield {"type": "tool_start", "tool": "list_evidence_paths", "input": _compact_json({"query": query})}
    evidence_paths, list_cache_hit = service._list_evidence_paths(query=query, payload=payload, request_cache=request_cache)
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
    for round_index in range(1, service.settings.max_deep_rounds + 1):
        heuristic_gaps = _coverage_gaps_from_state(coverage_state)
        quality_gaps = _deep_quality_gaps_from_state(coverage_state)
        active_gaps = list(dict.fromkeys([*heuristic_gaps, *quality_gaps]))
        gap_step = _planner_step(stage="gap_check", label="分析证据缺口", detail=f"round={round_index}; gaps={','.join(active_gaps) or 'none'}")
        planner_steps.append(gap_step)
        yield {"type": "planner_step", "step": gap_step}
        if not active_gaps:
            notes.append(f"deep_round_{round_index}:coverage_sufficient")
            stop_step = _planner_step(stage="coverage_ok", label="证据覆盖满足", detail=f"round={round_index}")
            planner_steps.append(stop_step)
            yield {"type": "planner_step", "step": stop_step}
            break

        plan, planner_backend, planner_note = await service._generate_followup_plan(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            case_references=case_references,
            deep_trace=deep_trace,
            heuristic_gaps=active_gaps,
            coverage_summary=_coverage_summary_from_state(coverage_state),
            executed_actions=executed_actions,
        )
        if planner_note:
            notes.append(planner_note)
        plan_step = _planner_step(stage="planner", label="规划下一步检索", detail=f"round={round_index}; backend={planner_backend}; actions={len(plan.get('next_actions', []))}")
        planner_steps.append(plan_step)
        yield {"type": "planner_step", "step": plan_step}

        plan_gaps = [str(item).strip() for item in plan.get("gaps", []) if str(item).strip()] if isinstance(plan.get("gaps"), list) else active_gaps
        actions = service._resolve_followup_actions(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            plan=plan,
            heuristic_gaps=active_gaps,
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
        action_batch_results = await service._execute_actions_for_round(actions=actions, request_cache=request_cache)
        for action_index, (action, result) in enumerate(action_batch_results, start=1):
            coverage_before = _coverage_summary_from_state(coverage_state)
            tool_name = str(action.get("tool", "followup"))
            action_status = str(result.get("status", "ok") or "ok")
            meta = _build_action_meta(action, result)
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
                    "bundle": service._build_live_evidence_bundle(
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

            factual_evidence, case_references, merged_new_items = _process_action_items(
                items, factual_evidence, case_references, coverage_state,
            )
            new_items_this_round += len(merged_new_items)
            if merged_new_items:
                yield {"type": "evidence", "items": merged_new_items}
            trace_step = _trace_step(
                step_index=len(deep_trace) + 1,
                round_index=round_index,
                action_index=action_index,
                action=action,
                status=action_status,
                new_evidence=merged_new_items[: service.settings.max_trace_evidence_per_step],
                coverage_before_step=coverage_before,
                coverage_after_step=_coverage_summary_from_state(coverage_state),
            )
            deep_trace.append(trace_step)
            yield {"type": "deep_trace_step", "step": trace_step}
            yield {
                "type": "evidence_bundle",
                "bundle": service._build_live_evidence_bundle(
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

        remaining_gaps = _coverage_gaps_from_state(coverage_state)
        remaining_quality_gaps = _deep_quality_gaps_from_state(coverage_state)
        remaining_active_gaps = list(dict.fromkeys([*remaining_gaps, *remaining_quality_gaps]))
        if new_items_this_round <= 0 and not remaining_quality_gaps:
            notes.append(f"deep_round_{round_index}:no_new_evidence")
            stop_step = _planner_step(stage="stop", label="未补到新证据", detail=f"round={round_index}")
            planner_steps.append(stop_step)
            yield {"type": "planner_step", "step": stop_step}
            break
        if not remaining_active_gaps:
            notes.append(f"deep_round_{round_index}:coverage_sufficient")
            stop_step = _planner_step(stage="coverage_ok", label="证据覆盖满足", detail=f"round={round_index}")
            planner_steps.append(stop_step)
            yield {"type": "planner_step", "step": stop_step}
            break
        if new_items_this_round <= 0 and remaining_quality_gaps:
            notes.append(f"deep_round_{round_index}:quality_gaps_persist:{','.join(remaining_quality_gaps)}")
    else:
        notes.append("deep_round_limit_reached")
        stop_step = _planner_step(stage="stop", label="达到轮次上限", detail=f"max_rounds={service.settings.max_deep_rounds}")
        planner_steps.append(stop_step)
        yield {"type": "planner_step", "step": stop_step}

    async for event in _yield_answer_synthesis_step(planner_steps, detail="deep_grounded_answer", emit_new_response=True):
        yield event

    result = await service._build_response(
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
        full_evidence_mode=full_evidence_mode,
    )
    async for event in _yield_final_results(result, guard):
        yield event
