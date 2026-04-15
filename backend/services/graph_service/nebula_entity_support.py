from __future__ import annotations

from typing import Any

from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name


def entity_lookup_exact_hit_payload(
    engine,
    exact_candidates: list[str],
    *,
    query_text: str,
    predicate_allowlist: list[str] | None,
    predicate_blocklist: list[str] | None,
    top_k: int,
    limit_per_entity: int,
) -> dict[str, Any] | None:
    if not exact_candidates:
        return None
    exact_name = str(exact_candidates[0]).strip()
    grouped_rows = engine._group_nebula_relations_by_source(
        [exact_name],
        predicate_allowlist=predicate_allowlist,
        source_books=engine._query_source_book_hints(query_text),
        limit_per_entity=limit_per_entity,
        directions=engine._entity_lookup_directions(
            query_text=query_text,
            predicate_allowlist=predicate_allowlist,
        ),
    )
    rows = grouped_rows.get(exact_name, [])
    if not rows:
        return None
    entity_type = engine.fallback_engine.entity_type(exact_name)
    relations = engine.fallback_engine._select_relation_clusters(
        engine.fallback_engine._filter_relations(
            engine.fallback_engine._annotate_relation_rows(rows, anchor_entity_type=entity_type),
            predicate_allowlist=predicate_allowlist or None,
            predicate_blocklist=predicate_blocklist,
        ),
        query_text=query_text,
        top_k=max(1, top_k),
    )
    min_relations = 1 if predicate_allowlist else min(max(2, top_k // 2), top_k)
    if len(relations) < min_relations:
        return None
    return {
        "entity": {
            "name": query_text.strip(),
            "canonical_name": exact_name,
            "entity_type": entity_type,
        },
        "relations": relations,
        "total": len(relations),
        "merged_candidates": [exact_name],
    }


def entity_lookup_limit_per_candidate(
    *,
    query_text: str,
    predicate_allowlist: list[str] | None,
    query_has_source_constraint_func,
) -> int:
    allow = {_normalize_relation_name(item) for item in predicate_allowlist or []}
    if allow == {"使用药材"}:
        return 24
    if allow and allow <= {"功效", "治法"}:
        return 20
    if allow and allow <= {"治疗证候", "治疗疾病", "治疗症状"}:
        return 24
    if query_has_source_constraint_func(query_text):
        return 16
    return 48


def entity_lookup_directions(*, query_text: str, predicate_allowlist: list[str] | None, query_has_source_constraint_func) -> tuple[bool, ...]:
    allow = {_normalize_relation_name(item) for item in predicate_allowlist or []}
    out_only_predicates = {
        "使用药材",
        "功效",
        "治法",
        "治疗证候",
        "治疗疾病",
        "治疗症状",
        "归经",
        "药性",
        "五味",
    }
    if allow and allow <= out_only_predicates:
        return (False,)
    if query_has_source_constraint_func(query_text):
        return (False,)
    return (False, True)


def query_has_source_constraint(query_text: str, *, query_fragments_func, query_mentions_source_book_func) -> bool:
    fragments = query_fragments_func(query_text)
    if "出处" in query_text or "原文" in query_text or "原句" in query_text:
        return True
    return any(query_mentions_source_book_func(query_text, fragment) for fragment in fragments)


def query_source_book_hints(query_text: str, *, query_fragments_func, source_book_exists_func) -> list[str]:
    fragments = query_fragments_func(query_text)
    hints: list[str] = []
    for fragment in fragments:
        if source_book_exists_func(fragment):
            if fragment not in hints:
                hints.append(fragment)
    return hints
