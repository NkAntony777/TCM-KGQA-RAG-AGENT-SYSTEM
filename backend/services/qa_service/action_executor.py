from __future__ import annotations

import asyncio
import json
from typing import Any

from services.qa_service.models import QAServiceSettings


def _cache_key(tool: str, payload: dict[str, Any]) -> str:
    return f"{tool}::{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"


def _action_cache_payload(*, action: dict[str, Any], settings: QAServiceSettings) -> dict[str, Any]:
    tool = str(action.get("tool", "")).strip()
    normalized_path = str(action.get("path", "")).strip()
    resolved_top_k = int(action.get("top_k", settings.deep_read_top_k) or settings.deep_read_top_k)
    if tool == "read_evidence_path":
        scheme = normalized_path.split("://", 1)[0] if "://" in normalized_path else ""
        payload = {
            "path": normalized_path,
            "top_k": resolved_top_k,
        }
        if scheme in {"book", "qa", "caseqa"}:
            payload["query"] = str(action.get("query", "")).strip()
            payload["source_hint"] = str(action.get("source_hint", "")).strip()
        return payload
    scopes = action.get("scope_paths", [])
    normalized_scopes = scopes if isinstance(scopes, list) else []
    if not normalized_scopes:
        fallback_path = str(action.get("path", "")).strip()
        if fallback_path.startswith(("chapter://", "book://", "qa://", "caseqa://")):
            normalized_scopes = [fallback_path]
    return {
        "path": normalized_path,
        "query": str(action.get("query", "")).strip(),
        "source_hint": str(action.get("source_hint", "")).strip(),
        "scope_paths": normalized_scopes,
        "top_k": resolved_top_k,
    }


def _execute_action(*, evidence_navigator, settings: QAServiceSettings, action: dict[str, Any], request_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tool = str(action.get("tool", "")).strip()
    cache_key = _cache_key(tool, _action_cache_payload(action=action, settings=settings))
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
        normalized_scopes = scopes if isinstance(scopes, list) else []
        if not normalized_scopes:
            fallback_path = str(action.get("path", "")).strip()
            if fallback_path.startswith(("chapter://", "book://", "qa://", "caseqa://")):
                normalized_scopes = [fallback_path]
        result = evidence_navigator.search_evidence_text(
            query=str(action.get("query", "")),
            source_hint=str(action.get("source_hint", "")),
            scope_paths=normalized_scopes,
            top_k=int(action.get("top_k", settings.deep_read_top_k) or settings.deep_read_top_k),
        )
        request_cache[cache_key] = dict(result)
        return {**result, "cache_hit": False}
    return {"tool": tool or "unknown", "status": "error", "count": 0, "items": [], "cache_hit": False}


def _can_parallelize_actions(actions: list[dict[str, Any]]) -> bool:
    if len(actions) < 2:
        return False
    parallel_safe_skills = {
        "expand-entity-alias",
        "read-formula-composition",
        "read-formula-origin",
        "search-source-text",
        "find-case-reference",
        "read-syndrome-treatment",
        "compare-formulas",
        "trace-source-passage",
        "trace-graph-path",
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
