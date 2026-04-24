"""Query-context normalization for files-first retrieval."""

from __future__ import annotations

from typing import Any

from services.retrieval_service import files_first_methods as ffm


def merge_query_flags(base_flags: dict[str, bool], query_context: dict[str, Any] | None) -> dict[str, bool]:
    flags = dict(base_flags)
    if not query_context:
        return flags
    question_type = str(query_context.get("question_type", "")).strip()
    facets = {str(item).strip() for item in query_context.get("answer_facets", []) if str(item).strip()}
    if question_type == "source_locate":
        flags["source_query"] = True
    if question_type == "composition" or "组成" in facets:
        flags["composition_query"] = True
    if question_type == "property" or facets & {"功效", "归经", "别名", "主治", "治法"}:
        flags["property_query"] = True
    if question_type == "comparison":
        flags["comparison_query"] = True
    return flags


def unique_nonempty_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    stack: list[str] = []
    for value in values:
        if isinstance(value, list):
            stack.extend(str(item).strip() for item in value if str(item).strip())
        else:
            normalized = str(value or "").strip()
            if normalized:
                stack.append(normalized)
    for item in stack:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def apply_query_context(
    *,
    query: str,
    tokenizer,
    query_context: dict[str, Any] | None,
) -> tuple[dict[str, bool], list[str], list[str], str, bool, bool]:
    base_flags = ffm._query_flags(query)
    flags = merge_query_flags(base_flags, query_context)
    heuristic_entities = ffm._sanitize_focus_entities(ffm._extract_focus_entities(query, tokenizer))
    llm_entities = [
        str(item).strip()
        for item in (query_context or {}).get("focus_entities", [])
        if str(item).strip()
    ]
    primary_entity = str((query_context or {}).get("primary_entity", "")).strip()
    ordered = []
    seen: set[str] = set()
    for item in [primary_entity, *llm_entities, *heuristic_entities]:
        normalized = str(item or "").strip()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    books_in_query = unique_nonempty_strings(
        [*[(query_context or {}).get("source_book_hints", [])], ffm._books_in_query(query)]
    )
    expanded_query = str((query_context or {}).get("expanded_query", "")).strip()
    weak_anchor = bool((query_context or {}).get("weak_anchor", False))
    need_broad_recall = bool((query_context or {}).get("need_broad_recall", False))
    return flags, ordered[:4], books_in_query[:8], expanded_query, weak_anchor, need_broad_recall
