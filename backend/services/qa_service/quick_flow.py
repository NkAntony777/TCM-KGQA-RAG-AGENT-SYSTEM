from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator

from services.qa_service.evidence import (
    _coverage_gaps_from_state,
    _coverage_summary_from_state,
    _init_coverage_state,
    _merge_evidence_items,
    _new_unique_evidence,
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
    yield {"type": "qa_mode", "mode": result_mode}

    route_decision_step = _planner_step(stage="route_decision", label="分析查询并选择路由", detail=f"query={query[:60]}")
    planner_steps = [route_decision_step]
    yield {"type": "planner_step", "step": route_decision_step}
    await asyncio.sleep(0)

    route_context = service._prepare_route_context(query=query, top_k=top_k, include_executed_routes=False)
    payload = route_context.payload
    request_cache: dict[str, dict[str, Any]] = {}
    route_search_step = _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={payload.get('final_route', payload.get('route', 'unknown'))}")
    planner_steps.append(route_search_step)
    yield {"type": "planner_step", "step": route_search_step}
    yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
    yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_context.route_meta), "meta": route_context.route_meta}

    if route_context.route_event:
        yield {"type": "route", **route_context.route_event}
    await asyncio.sleep(0)

    retrieval_step = _planner_step(stage="retrieval", label="执行文件优先检索", detail="图谱 / FFSR / 病例索引 / 补召回")
    planner_steps.append(retrieval_step)
    yield {"type": "planner_step", "step": retrieval_step}
    await asyncio.sleep(0)

    tool_trace = [{"tool": "tcm_route_search", "meta": route_context.route_meta}]
    notes = list(notes_prefix or [])
    evidence_paths = list(payload.get("evidence_paths", [])) if isinstance(payload.get("evidence_paths"), list) else []
    factual_evidence = route_context.factual_evidence
    case_references = route_context.case_references
    initial_items = factual_evidence + case_references
    if initial_items:
        yield {"type": "evidence", "items": initial_items}
        await asyncio.sleep(0)

    evidence_org_step = _planner_step(stage="evidence_organization", label="整理证据与覆盖分析", detail=f"factual={len(factual_evidence)}; cases={len(case_references)}")
    planner_steps.append(evidence_org_step)
    yield {"type": "planner_step", "step": evidence_org_step}
    await asyncio.sleep(0)

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
    yield {"type": "planner_step", "step": answer_step}
    await asyncio.sleep(0)

    # Emit a live evidence bundle before the blocking LLM call so the frontend
    # can mark retrieval/coverage stages as completed before answer generation.
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
