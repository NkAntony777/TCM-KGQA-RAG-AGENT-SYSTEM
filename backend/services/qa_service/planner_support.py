from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from services.common.evidence_payloads import normalize_book_label
from services.qa_service.alias_service import get_runtime_alias_service
from services.qa_service.skill_registry import RuntimeSkill


def _normalize_path_text(value: str) -> str:
    return unquote(str(value or "").strip())


def _split_evidence_path(path: str) -> tuple[str, str, str]:
    normalized = _normalize_path_text(path)
    if "://" not in normalized:
        return "", "", ""
    scheme, body = normalized.split("://", 1)
    head, _, tail = body.partition("/")
    return scheme.strip(), head.strip(), tail.strip()


def _normalize_evidence_path(path: str) -> str:
    scheme, head, tail = _split_evidence_path(path)
    if not scheme:
        return _normalize_path_text(path)
    normalized_head = normalize_book_label(head) if scheme in {"book", "chapter"} else head
    if scheme == "book":
        normalized_tail = tail or "*"
        return f"book://{normalized_head}/{normalized_tail}" if normalized_head else _normalize_path_text(path)
    if tail:
        return f"{scheme}://{normalized_head}/{tail}" if normalized_head else _normalize_path_text(path)
    return f"{scheme}://{normalized_head}" if normalized_head else _normalize_path_text(path)


def _path_head_candidates(scheme: str, head: str) -> tuple[str, ...]:
    normalized_head = _normalize_path_text(head)
    if not normalized_head:
        return ()

    candidates: list[str] = []
    seen = set()

    def add(candidate: str) -> None:
        value = _normalize_path_text(candidate)
        if not value or value in seen:
            return
        seen.add(value)
        candidates.append(value)

    add(normalized_head)
    if scheme in {"book", "chapter"}:
        add(normalize_book_label(normalized_head))
    elif scheme in {"entity", "alias"}:
        try:
            alias_service = get_runtime_alias_service()
            for alias in alias_service.aliases_for_entity(normalized_head, max_aliases=8):
                add(alias)
        except Exception:
            pass
    return tuple(candidates)


def _path_head_matches(*, path_scheme: str, path_head: str, expected_scheme: str, expected_head: str) -> bool:
    if path_scheme != expected_scheme:
        return False
    path_candidates = set(_path_head_candidates(path_scheme, path_head))
    expected_candidates = set(_path_head_candidates(expected_scheme, expected_head))
    return bool(path_candidates.intersection(expected_candidates))


def _tail_matches(*, tail: str, suffix: str) -> bool:
    normalized_tail = _normalize_path_text(tail).strip("/")
    normalized_suffix = _normalize_path_text(suffix).strip("/")
    if normalized_suffix == "*":
        return True
    return normalized_tail in {normalized_suffix, "*"}


def _path_matches_prefix(path: str, prefix: str, *, allow_prefix_only: bool) -> bool:
    normalized_path = _normalize_path_text(path)
    normalized_prefix = _normalize_path_text(prefix)
    if normalized_path.startswith(normalized_prefix):
        return True
    if allow_prefix_only and normalized_prefix.startswith(normalized_path):
        return True

    path_scheme, path_head, path_tail = _split_evidence_path(normalized_path)
    prefix_scheme, prefix_head, prefix_tail = _split_evidence_path(normalized_prefix)
    if not _path_head_matches(
        path_scheme=path_scheme,
        path_head=path_head,
        expected_scheme=prefix_scheme,
        expected_head=prefix_head,
    ):
        return False
    if not prefix_tail:
        return True
    normalized_path_tail = _normalize_path_text(path_tail).strip("/")
    normalized_prefix_tail = _normalize_path_text(prefix_tail).strip("/")
    if normalized_path_tail.startswith(normalized_prefix_tail):
        return True
    return allow_prefix_only and normalized_prefix_tail.startswith(normalized_path_tail)


def _pick_existing_path(paths: list[str], *, prefix: str, suffix: str) -> str:
    expected_scheme, expected_head, _ = _split_evidence_path(prefix)
    for path in paths:
        path_scheme, path_head, path_tail = _split_evidence_path(path)
        if not _path_head_matches(
            path_scheme=path_scheme,
            path_head=path_head,
            expected_scheme=expected_scheme,
            expected_head=expected_head,
        ):
            continue
        if _tail_matches(tail=path_tail, suffix=suffix):
            return _normalize_evidence_path(path)
    return ""


def _pick_first_matching_path(paths: list[str], *, prefixes: tuple[str, ...], allow_prefix_only: bool = False) -> str:
    for path in paths:
        if any(_path_matches_prefix(path, prefix, allow_prefix_only=allow_prefix_only) for prefix in prefixes):
            return _normalize_evidence_path(path)
    return ""


def _pick_best_source_path(
    paths: list[str],
    *,
    preferred_books: list[str] | None = None,
) -> str:
    candidate_books: list[str] = []
    for item in preferred_books or []:
        book_name = str(item).strip()
        if not book_name:
            continue
        normalized = normalize_book_label(book_name)
        for candidate in (book_name, normalized):
            if candidate and candidate not in candidate_books:
                candidate_books.append(candidate)
    for book_name in candidate_books:
        for path in paths:
            path_scheme, path_head, _ = _split_evidence_path(path)
            if _path_head_matches(
                path_scheme=path_scheme,
                path_head=path_head,
                expected_scheme="chapter",
                expected_head=book_name,
            ):
                return _normalize_evidence_path(path)
        for path in paths:
            path_scheme, path_head, _ = _split_evidence_path(path)
            if _path_head_matches(
                path_scheme=path_scheme,
                path_head=path_head,
                expected_scheme="book",
                expected_head=book_name,
            ):
                return _normalize_evidence_path(path)
    if candidate_books:
        return ""
    for prefix in ("chapter://", "book://", "qa://"):
        for path in paths:
            if _normalize_path_text(path).startswith(prefix):
                return _normalize_evidence_path(path)
    return ""


def _book_path_fallback(book_name: str) -> str:
    normalized = normalize_book_label(book_name)
    return f"book://{normalized or book_name}/*" if (normalized or book_name) else ""


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
        return _pick_best_source_path(evidence_paths) or (f"book://{entity_name}/*" if entity_name else "")
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
        return _pick_best_source_path(evidence_paths)
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
