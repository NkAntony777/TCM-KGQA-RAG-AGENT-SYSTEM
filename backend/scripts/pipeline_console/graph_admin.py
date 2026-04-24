from __future__ import annotations

from threading import RLock
from typing import Any, Callable


RuntimeGraphStoreFactory = Callable[[], Any]
ProcessedBooksProvider = Callable[[], set[str]]
BookOverridesProvider = Callable[[], dict[str, list[str]]]
BookOverrideMarker = Callable[[list[str]], dict[str, list[str]]]
PublishBusyMarker = Callable[[], str | None]


def graph_stats_payload(runtime_graph_store: RuntimeGraphStoreFactory) -> dict[str, Any]:
    stats = runtime_graph_store().stats()
    return {
        "exists": bool(stats["exists"]),
        "total_triples": int(stats["total_triples"]),
        "evidence_count": int(stats["evidence_count"]),
        "predicate_dist": [(item["predicate"], int(item["count"])) for item in stats["predicate_dist"]],
        "book_dist": [(item["name"], int(item["count"])) for item in stats["book_dist"]],
    }


def graph_books_payload(
    *,
    runtime_graph_store: RuntimeGraphStoreFactory,
    processed_books_provider: ProcessedBooksProvider,
    book_overrides_provider: BookOverridesProvider,
    limit: int,
    keyword: str,
) -> dict[str, Any]:
    store = runtime_graph_store()
    normalized_keyword = str(keyword or "").strip()
    rows = store.list_books(limit=max(1, limit), keyword=normalized_keyword)
    processed_stems = processed_books_provider()
    return {
        "exists": bool(store.stats()["exists"]),
        "books": [
            {
                "name": row["name"],
                "triple_count": int(row["triple_count"]),
                "processed": row["name"] in processed_stems,
            }
            for row in rows
        ],
        "total": store.total_books(normalized_keyword),
        "force_unprocessed": book_overrides_provider().get("force_unprocessed", []),
    }


def graph_book_triples_payload(
    *,
    runtime_graph_store: RuntimeGraphStoreFactory,
    book_name: str,
    limit: int,
) -> dict[str, Any]:
    store = runtime_graph_store()
    bounded_limit = max(1, limit)
    matched = store.book_triples(book_name, limit=bounded_limit)
    return {
        "book": book_name,
        "total": store.book_total(book_name),
        "rows": matched[:bounded_limit],
    }


def delete_books_from_runtime_graph(
    book_names: list[str],
    *,
    runtime_graph_store: RuntimeGraphStoreFactory,
    runtime_graph_mutation_lock: RLock,
    publish_busy_marker: PublishBusyMarker,
    load_book_status_overrides: BookOverridesProvider,
    mark_books_force_unprocessed: BookOverrideMarker,
    sync_nebula: bool = True,
    mark_unprocessed: bool = True,
) -> dict[str, Any]:
    books = sorted({str(name).strip() for name in book_names if str(name).strip()})
    if not books:
        raise ValueError("book_names_required")

    with runtime_graph_mutation_lock:
        busy_marker = publish_busy_marker()
        if busy_marker:
            raise RuntimeError(f"publish_queue_busy: {busy_marker}")
        store = runtime_graph_store()
        delete_result = store.delete_books(books)
        removed_rows = delete_result.get("removed_rows", [])
        removed_triples = int(delete_result.get("removed_triples", 0) or 0)
        orphan_entities = list(delete_result.get("orphan_entities", []))
        remaining_evidence = int(delete_result.get("remaining_evidence", 0) or 0)
        override_payload: dict[str, list[str]] | None = mark_books_force_unprocessed(books) if mark_unprocessed else None

    nebula_result: dict[str, Any] | None = None
    if sync_nebula:
        if removed_rows:
            from services.graph_service.nebulagraph_store import NebulaGraphStore

            nebula_store = NebulaGraphStore()
            nebula_result = nebula_store.delete_rows(removed_rows, orphan_entity_names=orphan_entities)
        else:
            nebula_result = {
                "mode": "delete_rows",
                "deleted_edges": 0,
                "deleted_vertices": 0,
                "skipped": "no_matching_runtime_rows",
            }

    return {
        "books": books,
        "removed_triples": removed_triples,
        "remaining_triples": int(delete_result.get("remaining_triples", 0) or 0),
        "removed_evidence": int(delete_result.get("removed_evidence", 0) or 0),
        "remaining_evidence": remaining_evidence,
        "orphan_entities": orphan_entities,
        "force_unprocessed": (override_payload or load_book_status_overrides()).get("force_unprocessed", []),
        "nebula": nebula_result,
    }
