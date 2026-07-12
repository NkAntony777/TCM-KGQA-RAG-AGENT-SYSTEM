from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator

from services.qa_service._base_flow import (
    _assign_initial_evidence,
    _build_action_meta,
    _process_action_items,
    _yield_answer_synthesis_step,
    _yield_evidence_org_step,
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
    _init_coverage_state,
    _update_coverage_state,
)
from services.qa_service.helpers import (
    _compact_json,
    _finalize_result,
    _planner_step,
    _tool_input_for_action,
)
from services.qa_service.models import AnswerMode

if TYPE_CHECKING:
    from services.qa_service.engine import QAService


async def stream_quick(
    service: "QAService",
    query: str,
    *,
    top_k: int,
    guard,
    result_mode: AnswerMode = "quick",
    notes_prefix: list[str] | None = None,
    status_override: str | None = None,
    generation_backend_override: str | None = None,
    full_evidence_mode: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    async for event in _yield_qa_mode(result_mode):
        yield event

    planner_steps: list = []
    async for event in _yield_route_decision_step(query, planner_steps):
        yield event

    route_context = service._prepare_route_context(query=query, top_k=top_k, include_executed_routes=False)
    payload = route_context.payload
    request_cache: dict[str, dict[str, Any]] = {}

    async for event in _yield_route_search(query, top_k, route_context, planner_steps):
        yield event

    async for event in _yield_route_event(route_context):
        yield event

    async for event in _yield_retrieval_step(planner_steps):
        yield event

    tool_trace = [{"tool": "tcm_route_search", "meta": route_context.route_meta}]
    notes = list(notes_prefix or [])
    evidence_paths = list(payload.get("evidence_paths", [])) if isinstance(payload.get("evidence_paths"), list) else []
    factual_evidence, case_references, initial_items = _assign_initial_evidence(route_context)

    async for event in _yield_initial_evidence(initial_items):
        yield event

    async for event in _yield_evidence_org_step(planner_steps, factual_evidence, case_references):
        yield event

    coverage_state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
    _update_coverage_state(
        coverage_state,
        new_factual_evidence=factual_evidence,
        new_case_references=case_references,
    )
    heuristic_gaps = _coverage_gaps_from_state(coverage_state)

    if service._should_run_quick_followup(payload=payload, heuristic_gaps=heuristic_gaps):
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
        listed_paths, list_cache_hit = service._list_evidence_paths(query=query, payload=payload, request_cache=request_cache)
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

        planned_actions = service._resolve_followup_actions(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            plan={"gaps": heuristic_gaps, "next_actions": []},
            heuristic_gaps=heuristic_gaps,
            plan_gaps=heuristic_gaps,
            executed_actions=set(),
        )
        actions = planned_actions[: service._quick_followup_action_limit(heuristic_gaps=heuristic_gaps)]

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
            action_batch_results = await service._execute_actions_for_round(actions=actions, request_cache=request_cache)
            for action, result in action_batch_results:
                tool_name = str(action.get("tool", "followup"))
                meta = _build_action_meta(action, result)
                yield {"type": "tool_end", "tool": tool_name, "output": _compact_json(meta), "meta": meta}
                tool_trace.append({"tool": tool_name, "meta": meta})
                items = result.get("items", []) if isinstance(result.get("items"), list) else []
                if not items:
                    continue
                factual_evidence, case_references, merged_new_items = _process_action_items(
                    items, factual_evidence, case_references, coverage_state,
                )
                if merged_new_items:
                    yield {"type": "evidence", "items": merged_new_items}
            remaining_gaps = _coverage_gaps_from_state(coverage_state)
            if remaining_gaps:
                notes.append(f"quick_followup_remaining_gaps:{','.join(remaining_gaps)}")

    async for event in _yield_answer_synthesis_step(planner_steps, detail="quick_grounded_answer"):
        yield event
    await asyncio.sleep(0)

    live_coverage_summary = _coverage_summary_from_state(coverage_state)
    yield {
        "type": "evidence_bundle",
        "bundle": service._build_live_evidence_bundle(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            case_references=case_references,
            coverage_summary=live_coverage_summary,
            planner_steps=planner_steps,
            deep_trace=[],
        ),
    }
    await asyncio.sleep(0)

    result = await service._build_response(
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
        full_evidence_mode=full_evidence_mode,
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
        await asyncio.sleep(0)
    yield {"type": "token", "content": result["answer"]}
    await asyncio.sleep(0)
    yield {"type": "done", "content": result["answer"]}
    await asyncio.sleep(0)
    yield {"type": "result", "result": result}
