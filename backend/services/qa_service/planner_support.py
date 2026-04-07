from __future__ import annotations

from typing import Any

from services.qa_service.skill_registry import RuntimeSkill


def _pick_existing_path(paths: list[str], *, prefix: str, suffix: str) -> str:
    for path in paths:
        if path.startswith(prefix) and (suffix == "*" or path.endswith(suffix) or path.endswith("/*")):
            return path
    return ""


def _pick_first_matching_path(paths: list[str], *, prefixes: tuple[str, ...], allow_prefix_only: bool = False) -> str:
    for path in paths:
        if path.startswith(prefixes):
            return path
        if allow_prefix_only and any(prefix.startswith(path) or path.startswith(prefix) for prefix in prefixes):
            return path
    return ""


def _action_key(action: dict[str, Any]) -> str:
    scope = action.get("scope_paths", [])
    scope_text = "|".join(str(item).strip() for item in scope) if isinstance(scope, list) else ""
    return "::".join(
        [
            str(action.get("skill", "")).strip(),
            str(action.get("tool", "")).strip(),
            str(action.get("path", "")).strip(),
            str(action.get("query", "")).strip(),
            scope_text,
        ]
    )


def _top_graph_source_books(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    books: list[str] = []
    seen = set()
    for item in factual_evidence:
        if str(item.get("source_type", "")).strip() != "graph":
            continue
        source_book = str(item.get("source_book", "")).strip()
        if not source_book or source_book in seen:
            continue
        seen.add(source_book)
        books.append(source_book)
    return books


def _graph_source_hints_by_book(*, factual_evidence: list[dict[str, Any]]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for item in factual_evidence:
        if str(item.get("source_type", "")).strip() != "graph":
            continue
        source_book = str(item.get("source_book", "")).strip()
        snippet = str(item.get("snippet", "")).strip().replace("\n", " ")
        if not source_book or not snippet or source_book in hints:
            continue
        hints[source_book] = snippet[:80]
    return hints


def _preferred_path_for_skill(*, skill: str, payload: dict[str, Any], evidence_paths: list[str]) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    symptom_name = str(strategy.get("symptom_name", "")).strip()
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    if skill == "expand-entity-alias" and entity_name:
        return _pick_first_matching_path(
            evidence_paths,
            prefixes=(f"alias://{entity_name}",),
            allow_prefix_only=True,
        ) or f"alias://{entity_name}"
    if skill == "read-formula-composition" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="使用药材") or f"entity://{entity_name}/使用药材"
    if skill == "read-formula-origin":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://")) or (f"book://{entity_name}/*" if entity_name else "")
    if skill == "compare-formulas" and compare_entities:
        entity = compare_entities[0]
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity}/", suffix="*") or f"entity://{entity}/*"
    if skill == "compare-formulas" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") or f"entity://{entity_name}/*"
    if skill == "read-syndrome-treatment" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="治法") or f"entity://{entity_name}/治法"
    if skill == "trace-graph-path" and symptom_name:
        return _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
    if skill == "trace-graph-path" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="推荐方剂") or f"entity://{entity_name}/推荐方剂"
    if skill == "find-case-reference":
        return _pick_first_matching_path(evidence_paths, prefixes=("caseqa://",))
    if skill in {"search-source-text", "trace-source-passage"}:
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
    if skill == "read-formula-origin" and symptom_name:
        return _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
    return ""


def _build_skill_action(
    *,
    planner_skills: dict[str, RuntimeSkill],
    skill_name: str,
    query: str,
    reason: str,
    path: str = "",
    scope_paths: list[str] | None = None,
    top_k: int = 6,
    source_hint: str = "",
) -> dict[str, Any]:
    skill_meta = planner_skills.get(skill_name)
    tool_name = skill_meta.primary_tool if skill_meta is not None else ""
    action: dict[str, Any] = {
        "skill": skill_name,
        "tool": tool_name,
        "query": query,
        "top_k": top_k,
        "reason": reason,
    }
    if path:
        action["path"] = path
    if scope_paths:
        action["scope_paths"] = scope_paths
    if source_hint:
        action["source_hint"] = source_hint
    return action
