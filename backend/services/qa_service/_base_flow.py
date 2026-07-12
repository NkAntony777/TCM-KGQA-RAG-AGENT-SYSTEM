from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from services.qa_service.evidence import (
    _merge_evidence_items,
    _new_unique_evidence,
    _update_coverage_state,
)
from services.qa_service.helpers import (
    _compact_json,
    _finalize_result,
    _planner_step,
)


async def _yield_qa_mode(mode: str) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "qa_mode", "mode": mode}


async def _yield_route_decision_step(
    query: str,
    planner_steps: list,
) -> AsyncIterator[dict[str, Any]]:
    step = _planner_step(stage="route_decision", label="分析查询并选择路由", detail=f"query={query[:60]}")
    planner_steps.append(step)
    yield {"type": "planner_step", "step": step}
    await asyncio.sleep(0)


async def _yield_route_search(
    query: str,
    top_k: int,
    route_context,
    planner_steps: list,
    tool_trace: list | None = None,
) -> AsyncIterator[dict[str, Any]]:
    route_detail = route_context.route_meta.get("final_route", route_context.route_meta.get("route", "unknown"))
    step = _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={route_detail}")
    planner_steps.append(step)
    yield {"type": "planner_step", "step": step}
    yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
    yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_context.route_meta), "meta": route_context.route_meta}
    if tool_trace is not None:
        tool_trace.append({"tool": "tcm_route_search", "meta": route_context.route_meta})


async def _yield_route_event(route_context) -> AsyncIterator[dict[str, Any]]:
    if route_context.route_event:
        yield {"type": "route", **route_context.route_event}
    await asyncio.sleep(0)


def _assign_initial_evidence(route_context) -> tuple[list, list, list]:
    factual_evidence = route_context.factual_evidence
    case_references = route_context.case_references
    initial_items = factual_evidence + case_references
    return factual_evidence, case_references, initial_items


async def _yield_initial_evidence(initial_items: list) -> AsyncIterator[dict[str, Any]]:
    if initial_items:
        yield {"type": "evidence", "items": initial_items}
        await asyncio.sleep(0)


async def _yield_retrieval_step(planner_steps: list) -> AsyncIterator[dict[str, Any]]:
    step = _planner_step(stage="retrieval", label="执行文件优先检索", detail="图谱 / FFSR / 病例索引 / 补召回")
    planner_steps.append(step)
    yield {"type": "planner_step", "step": step}
    await asyncio.sleep(0)


async def _yield_evidence_org_step(
    planner_steps: list,
    factual_evidence: list,
    case_references: list,
) -> AsyncIterator[dict[str, Any]]:
    step = _planner_step(
        stage="evidence_organization",
        label="整理证据与覆盖分析",
        detail=f"factual={len(factual_evidence)}; cases={len(case_references)}",
    )
    planner_steps.append(step)
    yield {"type": "planner_step", "step": step}
    await asyncio.sleep(0)


def _build_action_meta(action: dict, result: dict) -> dict:
    return {
        "status": str(result.get("status", "ok") or "ok"),
        "count": result.get("count", 0),
        "reason": action.get("reason", ""),
        "path": action.get("path"),
        "query": action.get("query"),
        "skill": action.get("skill"),
        "cache_hit": bool(result.get("cache_hit")),
    }


def _process_action_items(
    items: list[dict],
    factual_evidence: list[dict],
    case_references: list[dict],
    coverage_state: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    new_factual = [item for item in items if str(item.get("evidence_type", "")).strip() != "case_reference"]
    new_cases = [item for item in items if str(item.get("evidence_type", "")).strip() == "case_reference"]
    added_factual = _new_unique_evidence(primary=new_factual, existing=factual_evidence) if new_factual else []
    added_cases = _new_unique_evidence(primary=new_cases, existing=case_references) if new_cases else []
    if new_factual:
        factual_evidence = _merge_evidence_items(primary=new_factual, fallback=factual_evidence)
    if new_cases:
        case_references = _merge_evidence_items(primary=new_cases, fallback=case_references)
    _update_coverage_state(
        coverage_state,
        new_factual_evidence=added_factual,
        new_case_references=added_cases,
    )
    merged_new_items = added_factual + added_cases
    return factual_evidence, case_references, merged_new_items


async def _yield_answer_synthesis_step(
    planner_steps: list,
    *,
    detail: str,
    emit_new_response: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    step = _planner_step(stage="answer_synthesis", label="生成最终答案", detail=detail)
    planner_steps.append(step)
    if emit_new_response:
        yield {"type": "new_response"}
    yield {"type": "planner_step", "step": step}


async def _yield_final_results(result: dict, guard) -> AsyncIterator[dict[str, Any]]:
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
