from __future__ import annotations

from typing import Any, Protocol


class GraphFallbackBackend(Protocol):
    """Stable local graph fallback boundary used by Nebula primary code."""

    def health(self) -> dict[str, Any]: ...

    def entity_lookup(
        self,
        name: str,
        *,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> dict[str, Any]: ...

    def path_query(self, start: str, end: str, *, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]: ...

    def syndrome_chain(self, symptom: str, *, top_k: int = 5) -> dict[str, Any]: ...

    def resolve_entities(self, query: str, preferred_types: set[str] | None = None, *, exact_only: bool = False) -> list[str]: ...

    def entity_type(self, entity_name: str) -> str: ...

    def annotate_relation_rows(self, rows: list[dict[str, Any]], *, anchor_entity_type: str) -> list[dict[str, Any]]: ...

    def filter_relations(
        self,
        rows: list[dict[str, Any]],
        *,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    def select_relation_clusters(self, rows: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]: ...

    def collect_recommended_formulas(self, syndrome_node: str) -> list[str]: ...

    def fast_path_candidates(
        self,
        *,
        start_candidates: list[str],
        end_candidates: list[str],
        max_hops: int,
        path_limit: int,
    ) -> dict[str, Any]: ...

    def build_path_payload(self, nodes: list[str]) -> dict[str, Any] | None: ...

    def edge_evidence_payload(self, edge_data: dict[str, Any]) -> dict[str, Any]: ...

    def first_edge_between(self, left: str, right: str) -> dict[str, Any] | None: ...

    def source_book_exists(self, source_book: str) -> bool: ...

    def query_fragments(self, query_text: str) -> list[str]: ...

    def query_mentions_source_book(self, query_text: str, source_book: str) -> bool: ...


class LocalGraphFallbackAdapter:
    """Public adapter over the local graph fallback engine.

    Nebula primary code should depend on this adapter instead of reaching into
    GraphQueryEngine private methods directly.
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def health(self) -> dict[str, Any]:
        return self.engine.health()

    def entity_lookup(
        self,
        name: str,
        *,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.engine.entity_lookup(
            name,
            top_k=top_k,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )

    def path_query(self, start: str, end: str, *, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
        return self.engine.path_query(start, end, max_hops=max_hops, path_limit=path_limit)

    def syndrome_chain(self, symptom: str, *, top_k: int = 5) -> dict[str, Any]:
        return self.engine.syndrome_chain(symptom, top_k=top_k)

    def resolve_entities(self, query: str, preferred_types: set[str] | None = None, *, exact_only: bool = False) -> list[str]:
        try:
            return self.engine._resolve_entities(query, preferred_types=preferred_types, exact_only=exact_only)
        except TypeError:
            return self.engine._resolve_entities(query, preferred_types=preferred_types)

    def entity_type(self, entity_name: str) -> str:
        return self.engine.entity_type(entity_name)

    def annotate_relation_rows(self, rows: list[dict[str, Any]], *, anchor_entity_type: str) -> list[dict[str, Any]]:
        return self.engine._annotate_relation_rows(rows, anchor_entity_type=anchor_entity_type)

    def filter_relations(
        self,
        rows: list[dict[str, Any]],
        *,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self.engine._filter_relations(
            rows,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )

    def select_relation_clusters(self, rows: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
        return self.engine._select_relation_clusters(rows, query_text=query_text, top_k=top_k)

    def collect_recommended_formulas(self, syndrome_node: str) -> list[str]:
        return self.engine._collect_recommended_formulas(syndrome_node)

    def fast_path_candidates(
        self,
        *,
        start_candidates: list[str],
        end_candidates: list[str],
        max_hops: int,
        path_limit: int,
    ) -> dict[str, Any]:
        return self.engine._fast_path_candidates(
            start_candidates=start_candidates,
            end_candidates=end_candidates,
            max_hops=max_hops,
            path_limit=path_limit,
        )

    def build_path_payload(self, nodes: list[str]) -> dict[str, Any] | None:
        return self.engine._build_path_payload(nodes)

    def edge_evidence_payload(self, edge_data: dict[str, Any]) -> dict[str, Any]:
        return self.engine._edge_evidence_payload(edge_data)

    def first_edge_between(self, left: str, right: str) -> dict[str, Any] | None:
        return self.engine.store.first_edge_between(left, right)

    def source_book_exists(self, source_book: str) -> bool:
        return self.engine.store.source_book_exists(source_book)

    def query_fragments(self, query_text: str) -> list[str]:
        return self.engine._query_fragments(query_text)

    def query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
        return self.engine._query_mentions_source_book(query_text, source_book)
