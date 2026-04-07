from __future__ import annotations

import asyncio
import json
from typing import Any

from services.qa_service.evidence import (
    _build_book_citations,
    _build_citations,
    _case_reference_from_payload,
    _coverage_summary,
    _factual_evidence_from_payload,
)
from services.qa_service.helpers import _extract_json_object, _route_from_payload, _safe_json_loads
from services.qa_service.models import AnswerMode, QAServiceSettings, RouteContext
from services.qa_service.prompts import (
    _build_grounded_system_prompt,
    _build_grounded_user_prompt,
    _compose_fallback_answer,
)


def _load_route_payload(route_tool, *, query: str, top_k: int) -> dict[str, Any]:
    route_output = route_tool._run(query=query, top_k=top_k)
    payload = _safe_json_loads(route_output)
    if isinstance(payload, dict):
        return payload
    return {"status": "evidence_insufficient", "notes": ["route_output_unparseable"]}


def _prepare_route_context(route_tool, *, query: str, top_k: int, include_executed_routes: bool, payload: dict[str, Any] | None = None) -> RouteContext:
    resolved_payload = payload or _load_route_payload(route_tool, query=query, top_k=top_k)
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


def _cache_key(tool: str, payload: dict[str, Any]) -> str:
    return f"{tool}::{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"


async def _generate_grounded_answer(
    *,
    answer_generator,
    settings: QAServiceSettings,
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
        content = await answer_generator.acomplete(
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
                evidence_limit=settings.max_quick_prompt_evidence if mode == "quick" else settings.max_deep_prompt_evidence,
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


async def _build_response(
    *,
    answer_generator,
    settings: QAServiceSettings,
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
        limit=settings.max_citations,
    )
    answer, generation_backend, generation_notes = await _generate_grounded_answer(
        answer_generator=answer_generator,
        settings=settings,
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
    selected_factual = factual[: settings.max_factual_evidence]
    selected_cases = cases[: settings.max_case_references]
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
    *,
    settings: QAServiceSettings,
    query: str,
    payload: dict[str, Any],
    evidence_paths: list[str],
    factual_evidence: list[dict[str, Any]],
    case_references: list[dict[str, Any]],
    coverage_summary: dict[str, Any] | None,
    planner_steps: list[dict[str, str]],
    deep_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_factual = factual_evidence[: settings.max_factual_evidence]
    selected_cases = case_references[: settings.max_case_references]
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


def _execute_action(*, evidence_navigator, settings: QAServiceSettings, action: dict[str, Any], request_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tool = str(action.get("tool", "")).strip()
    cache_key = _cache_key(
        tool,
        {
            "path": action.get("path", ""),
            "query": action.get("query", ""),
            "source_hint": action.get("source_hint", ""),
            "scope_paths": action.get("scope_paths", []),
            "top_k": int(action.get("top_k", settings.deep_read_top_k) or settings.deep_read_top_k),
        },
    )
    cached = request_cache.get(cache_key)
    if cached is not None:
        return {**cached, "cache_hit": True}

    if tool == "read_evidence_path":
        result = evidence_navigator.read_evidence_path(
            path=str(action.get("path", "")),
            query=str(action.get("query", "")),
            source_hint=str(action.get("source_hint", "")),
            top_k=int(action.get("top_k", settings.deep_read_top_k) or settings.deep_read_top_k),
        )
        request_cache[cache_key] = dict(result)
        return {**result, "cache_hit": False}
    if tool == "search_evidence_text":
        scopes = action.get("scope_paths", [])
        result = evidence_navigator.search_evidence_text(
            query=str(action.get("query", "")),
            source_hint=str(action.get("source_hint", "")),
            scope_paths=scopes if isinstance(scopes, list) else [],
            top_k=int(action.get("top_k", settings.deep_read_top_k) or settings.deep_read_top_k),
        )
        request_cache[cache_key] = dict(result)
        return {**result, "cache_hit": False}
    return {"tool": tool or "unknown", "status": "error", "count": 0, "items": [], "cache_hit": False}


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


async def _execute_actions_for_round(
    *,
    evidence_navigator,
    settings: QAServiceSettings,
    actions: list[dict[str, Any]],
    request_cache: dict[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if _can_parallelize_actions(actions):
        tasks = [
            asyncio.to_thread(
                _execute_action,
                evidence_navigator=evidence_navigator,
                settings=settings,
                action=action,
                request_cache=request_cache,
            )
            for action in actions
        ]
        results = await asyncio.gather(*tasks)
        return list(zip(actions, results))
    return [
        (
            action,
            _execute_action(
                evidence_navigator=evidence_navigator,
                settings=settings,
                action=action,
                request_cache=request_cache,
            ),
        )
        for action in actions
    ]
