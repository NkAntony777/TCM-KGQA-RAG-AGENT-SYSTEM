from __future__ import annotations

from typing import Any

from services.graph_service.nebulagraph_store import entity_vid
from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name


def collect_nebula_relations(engine, entity_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in primary_batch_neighbors(engine, [entity_name], reverse=False, limit_per_entity=256):
        rows.append(
            {
                "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                "target": str(row.get("neighbor_name", "")).strip(),
                "target_type": str(row.get("neighbor_type", "")).strip() or "other",
                "direction": "out",
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                **engine._evidence_payload_from_row(row),
            }
        )
    for row in primary_batch_neighbors(engine, [entity_name], reverse=True, limit_per_entity=256):
        rows.append(
            {
                "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                "target": str(row.get("neighbor_name", "")).strip(),
                "target_type": str(row.get("neighbor_type", "")).strip() or "other",
                "direction": "in",
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                **engine._evidence_payload_from_row(row),
            }
        )
    return rows


def adjacent_names(engine, entity_name: str) -> list[str]:
    names: set[str] = set()
    for row in primary_batch_neighbors(engine, [entity_name], reverse=False, limit_per_entity=128):
        name = str(row.get("neighbor_name", "")).strip()
        if name:
            names.add(name)
    for row in primary_batch_neighbors(engine, [entity_name], reverse=True, limit_per_entity=128):
        name = str(row.get("neighbor_name", "")).strip()
        if name:
            names.add(name)
    return sorted(names)


def group_nebula_relations_by_source(
    engine,
    entity_names: list[str],
    *,
    predicate_allowlist: list[str] | None = None,
    source_books: list[str] | None = None,
    limit_per_entity: int = 256,
    directions: tuple[bool, ...] = (False, True),
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in entity_names}
    source_vid_to_name = source_vid_name_map(engine, entity_names)
    for reverse in directions:
        rows = primary_batch_neighbors(
            engine,
            entity_names,
            reverse=reverse,
            predicates=predicate_allowlist,
            source_books=source_books,
            limit_per_entity=limit_per_entity,
        )
        direction = "in" if reverse else "out"
        for row in rows:
            source_name = source_vid_to_name.get(str(row.get("source_vid", "")).strip())
            if not source_name and len(entity_names) == 1:
                source_name = entity_names[0]
            if not source_name:
                continue
            grouped.setdefault(source_name, []).append(
                {
                    "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                    "target": str(row.get("neighbor_name", "")).strip(),
                    "target_type": str(row.get("neighbor_type", "")).strip() or "other",
                    "direction": direction,
                    "source_book": str(row.get("source_book", "")).strip(),
                    "source_chapter": str(row.get("source_chapter", "")).strip(),
                    **engine._evidence_payload_from_row(row),
                }
            )
    return grouped


def primary_batch_neighbors(
    engine,
    entity_names: list[str],
    *,
    reverse: bool,
    predicates: list[str] | None = None,
    target_types: list[str] | None = None,
    source_books: list[str] | None = None,
    limit_per_entity: int = 64,
) -> list[dict[str, Any]]:
    if hasattr(engine.primary_store, "batch_neighbors"):
        return engine.primary_store.batch_neighbors(
            entity_names,
            reverse=reverse,
            predicates=predicates,
            target_types=target_types,
            source_books=source_books,
            limit_per_entity=limit_per_entity,
        )
    source_book_set = {str(item).strip() for item in source_books or [] if str(item).strip()}
    target_type_set = {str(item).strip() for item in target_types or [] if str(item).strip()}
    predicate_set = {_normalize_relation_name(str(item).strip()) for item in predicates or [] if str(item).strip()}
    rows: list[dict[str, Any]] = []
    for name in entity_names:
        source_vid = primary_vid(engine, name)
        count = 0
        for row in engine.primary_store.neighbors(name, reverse=reverse):
            predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
            target_type = str(row.get("neighbor_type", "")).strip()
            source_book = str(row.get("source_book", "")).strip()
            if predicate_set and predicate not in predicate_set:
                continue
            if target_type_set and target_type not in target_type_set:
                continue
            if source_book_set and source_book not in source_book_set:
                continue
            item = dict(row)
            item.setdefault("source_vid", source_vid)
            rows.append(item)
            count += 1
            if count >= max(1, limit_per_entity):
                break
    return rows


def source_vid_name_map(engine, entity_names: list[str]) -> dict[str, str]:
    return {primary_vid(engine, name): name for name in entity_names if str(name).strip()}


def primary_vertex_map(engine, entity_names: list[str]) -> dict[str, dict[str, Any]]:
    if hasattr(engine.primary_store, "batch_exact_entities"):
        return engine.primary_store.batch_exact_entities(entity_names)
    if hasattr(engine.primary_store, "fetch_vertices_by_vids"):
        vertex_map = engine.primary_store.fetch_vertices_by_vids([primary_vid(engine, name) for name in entity_names if str(name).strip()])
        return {
            str(item.get("name", "")).strip(): item
            for item in vertex_map.values()
            if str(item.get("name", "")).strip()
        }
    result: dict[str, dict[str, Any]] = {}
    for name in entity_names:
        rows = engine.primary_store.exact_entity(name)
        if rows:
            result[name] = rows[0]
    return result


def primary_vid(engine, entity_name: str) -> str:
    max_length = getattr(getattr(engine.primary_store, "settings", None), "vid_max_length", 64)
    return entity_vid(entity_name, max_length=max_length)


def resolve_entities_via_primary(
    engine,
    query: str,
    preferred_types: set[str] | None = None,
    *,
    exact_only: bool = False,
) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized or not engine._use_primary():
        return []
    candidates: list[str] = []
    seen: set[str] = set()
    exact_names: list[str] = []
    try:
        if hasattr(engine.primary_store, "exact_entity_names"):
            exact_names = engine.primary_store.exact_entity_names(normalized, preferred_types=preferred_types)
        elif hasattr(engine.primary_store, "exact_entity"):
            preferred = {str(item).strip() for item in preferred_types or set() if str(item).strip()}
            rows = engine.primary_store.exact_entity(normalized)
            for row in rows:
                name = str(row.get("name", "")).strip()
                entity_type = str(row.get("entity_type", "")).strip()
                if not name:
                    continue
                if preferred and entity_type not in preferred:
                    continue
                exact_names.append(name)
    except Exception:
        exact_names = []
    for item in exact_names:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        candidates.append(text)
    if exact_only:
        return candidates
    if exact_names:
        try:
            alias_names = engine.primary_store.alias_candidates(exact_names[0], preferred_types=preferred_types, limit=20)
        except Exception:
            alias_names = []
        for item in alias_names:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            candidates.append(text)
    return candidates
