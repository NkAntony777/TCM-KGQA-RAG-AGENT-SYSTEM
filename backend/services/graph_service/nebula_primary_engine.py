from __future__ import annotations

from typing import TYPE_CHECKING, Any

from services.graph_service.nebulagraph_store import NebulaGraphStore
from services.graph_service.nebula_entity_support import entity_lookup_directions as _entity_lookup_directions_support
from services.graph_service.nebula_entity_support import entity_lookup_exact_hit_payload as _entity_lookup_exact_hit_payload_support
from services.graph_service.nebula_entity_support import entity_lookup_limit_per_candidate as _entity_lookup_limit_per_candidate_support
from services.graph_service.nebula_entity_support import query_has_source_constraint as _query_has_source_constraint_support
from services.graph_service.nebula_entity_support import query_source_book_hints as _query_source_book_hints_support
from services.graph_service.nebula_neighbor_support import adjacent_names as _adjacent_names_support
from services.graph_service.nebula_neighbor_support import collect_nebula_relations as _collect_nebula_relations_support
from services.graph_service.nebula_neighbor_support import group_nebula_relations_by_source as _group_nebula_relations_by_source_support
from services.graph_service.nebula_neighbor_support import primary_batch_neighbors as _primary_batch_neighbors_support
from services.graph_service.nebula_neighbor_support import primary_vertex_map as _primary_vertex_map_support
from services.graph_service.nebula_neighbor_support import primary_vid as _primary_vid_support
from services.graph_service.nebula_neighbor_support import resolve_entities_via_primary as _resolve_entities_via_primary_support
from services.graph_service.nebula_neighbor_support import source_vid_name_map as _source_vid_name_map_support
from services.graph_service.nebula_payload_support import build_payload_from_nebula_path_row as _build_payload_from_nebula_path_row_support
from services.graph_service.nebula_payload_support import build_payload_from_nebula_skeleton as _build_payload_from_nebula_skeleton_support
from services.graph_service.nebula_payload_support import evidence_payload_from_row as _evidence_payload_from_row_support
from services.graph_service.nebula_payload_support import extract_nebula_path_skeleton as _extract_nebula_path_skeleton_support
from services.graph_service.nebula_query_support import direct_path_query_via_nebula as _direct_path_query_via_nebula_support
from services.graph_service.nebula_query_support import fallback_ranked_path_search as _fallback_ranked_path_search_support
from services.graph_service.nebula_query_support import path_query_mode as _path_query_mode_support
from services.graph_service.nebula_query_support import path_query_relation_rows as _path_query_relation_rows_support
from services.graph_service.nebula_query_support import should_prefer_nebula_path as _should_prefer_nebula_path_support
from services.graph_service.nebula_query_support import syndrome_chain_via_nebula as _syndrome_chain_via_nebula_support
from services.graph_service.nebula_query_support import use_primary as _use_primary_support
from services.graph_service.relation_governance import expand_filter_predicates

if TYPE_CHECKING:
    from services.graph_service.engine import GraphQueryEngine


class NebulaPrimaryGraphEngine:
    def __init__(
        self,
        primary_store: NebulaGraphStore | None = None,
        fallback_engine: GraphQueryEngine | None = None,
    ):
        self.primary_store = primary_store or NebulaGraphStore()
        if fallback_engine is None:
            from services.graph_service.engine import GraphQueryEngine

            fallback_engine = GraphQueryEngine()
        self.fallback_engine = fallback_engine

    def health(self) -> dict[str, Any]:
        primary = self.primary_store.health()
        fallback = self.fallback_engine.health()
        local_ready = fallback.get("status") == "ok"
        nebula_ready = primary.get("status") == "ok"
        active_backend = "nebula" if nebula_ready else ("sqlite_fallback" if local_ready else "unavailable")
        status = "ok" if nebula_ready or local_ready else primary.get("status", "error")
        return {
            "status": status,
            "backend": "nebulagraph_primary" if nebula_ready else fallback.get("backend", "sqlite_runtime_graph"),
            "selected_backend": "nebula",
            "active_backend": active_backend,
            "primary": primary,
            "fallback": fallback,
            "graph_path": fallback.get("graph_path", ""),
            "evidence_path": fallback.get("evidence_path", ""),
            "evidence_paths": fallback.get("evidence_paths", []),
            "evidence_count": fallback.get("evidence_count", 0),
            "node_count": fallback.get("node_count", 0),
            "edge_count": fallback.get("edge_count", 0),
        }

    def entity_lookup(
        self,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> dict[str, Any]:
        if self._use_primary():
            try:
                nebula_result = self._entity_lookup_via_nebula(
                    name,
                    top_k=top_k,
                    predicate_allowlist=predicate_allowlist,
                    predicate_blocklist=predicate_blocklist,
                )
                if nebula_result:
                    return nebula_result
            except Exception:
                pass
        return self.fallback_engine.entity_lookup(
            name,
            top_k=top_k,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )

    def _entity_lookup_via_nebula(
        self,
        name: str,
        *,
        top_k: int,
        predicate_allowlist: list[str] | None,
        predicate_blocklist: list[str] | None,
    ) -> dict[str, Any]:
        normalized_name = str(name or "").strip()
        predicate_allow_expanded = list(expand_filter_predicates(predicate_allowlist or [])) if predicate_allowlist else []
        source_aware = self._query_has_source_constraint(normalized_name)
        limit_per_entity = self._entity_lookup_limit_per_candidate(
            query_text=normalized_name,
            predicate_allowlist=predicate_allow_expanded,
        )

        exact_candidates = self._resolve_entities_via_primary(normalized_name, exact_only=True)
        exact_payload = self._entity_lookup_exact_hit_payload(
            exact_candidates,
            query_text=normalized_name,
            predicate_allowlist=predicate_allow_expanded,
            predicate_blocklist=predicate_blocklist,
            top_k=top_k,
            limit_per_entity=limit_per_entity,
        )
        if exact_payload is not None:
            return exact_payload

        candidates = list(exact_candidates)
        if not source_aware:
            layered_candidates = self._resolve_entities_via_primary(normalized_name)
            for item in layered_candidates:
                if item not in candidates:
                    candidates.append(item)
        if not candidates:
            return {}
        candidate_names = candidates[:5]
        vertex_map = self._primary_vertex_map(candidate_names)
        grouped_rows = self._group_nebula_relations_by_source(
            candidate_names,
            predicate_allowlist=predicate_allow_expanded or None,
            source_books=self._query_source_book_hints(normalized_name) if source_aware else None,
            limit_per_entity=limit_per_entity,
            directions=self._entity_lookup_directions(
                query_text=normalized_name,
                predicate_allowlist=predicate_allow_expanded or None,
            ),
        )
        candidate_rankings: list[tuple[int, int, int, str, str, list[dict[str, Any]]]] = []
        for canonical_name in candidate_names:
            if canonical_name not in vertex_map:
                continue
            entity_type = self.fallback_engine.entity_type(canonical_name)
            relations = self.fallback_engine._select_relation_clusters(
                self.fallback_engine._filter_relations(
                    self.fallback_engine._annotate_relation_rows(
                        grouped_rows.get(canonical_name, []),
                        anchor_entity_type=entity_type,
                    ),
                    predicate_allowlist=predicate_allowlist,
                    predicate_blocklist=predicate_blocklist,
                ),
                query_text=name,
                top_k=max(1, top_k),
            )
            if not relations:
                continue
            relation_peak = max(self.fallback_engine._relation_score(item, name) for item in relations)
            predicate_peak = max(int(round(self.fallback_engine._predicate_priority(item) * 100)) for item in relations)
            exact_name_bonus = 1 if canonical_name == name.strip() else 0
            candidate_rankings.append(
                (
                    relation_peak + exact_name_bonus * 12,
                    predicate_peak,
                    len(relations),
                    canonical_name,
                    entity_type,
                    relations,
                )
            )
        if candidate_rankings:
            candidate_rankings.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
            exact_candidate = next((item for item in candidate_rankings if item[3] == name.strip()), None)
            best_candidate = candidate_rankings[0]
            best_non_exact = next((item for item in candidate_rankings if item[3] != name.strip()), None)
            selected_rows: list[dict[str, Any]] = []
            selected_names: list[str] = []
            if exact_candidate is not None:
                selected_rows.extend(grouped_rows.get(exact_candidate[3], []))
                selected_names.append(exact_candidate[3])
            if best_candidate[3] not in selected_names:
                selected_rows.extend(grouped_rows.get(best_candidate[3], []))
                selected_names.append(best_candidate[3])
            if best_non_exact is not None and best_non_exact[3] not in selected_names:
                selected_rows.extend(grouped_rows.get(best_non_exact[3], []))
                selected_names.append(best_non_exact[3])
            if selected_rows:
                primary_entity_name = exact_candidate[3] if exact_candidate is not None else best_candidate[3]
                primary_entity_type = exact_candidate[4] if exact_candidate is not None else best_candidate[4]
                merged_relations = self.fallback_engine._select_relation_clusters(
                    self.fallback_engine._filter_relations(
                        self.fallback_engine._annotate_relation_rows(
                            selected_rows,
                            anchor_entity_type=primary_entity_type,
                        ),
                        predicate_allowlist=predicate_allowlist,
                        predicate_blocklist=predicate_blocklist,
                    ),
                    query_text=name,
                    top_k=max(1, top_k),
                )
                return {
                    "entity": {
                        "name": name.strip(),
                        "canonical_name": primary_entity_name,
                        "entity_type": primary_entity_type,
                    },
                    "relations": merged_relations,
                    "total": len(merged_relations),
                    "merged_candidates": selected_names,
                }
        if candidate_names and candidate_names[0] in vertex_map:
            entity_type = self.fallback_engine.entity_type(candidate_names[0])
            return {
                "entity": {
                    "name": name.strip(),
                    "canonical_name": candidate_names[0],
                    "entity_type": entity_type,
                },
                "relations": [],
                "total": 0,
            }
        return {}

    def path_query(self, start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
        start_candidates = self._resolve_entities_via_primary(start, exact_only=True)[:3]
        end_candidates = self._resolve_entities_via_primary(end, exact_only=True)[:3]
        if not start_candidates:
            start_candidates = self.fallback_engine._resolve_entities(start, exact_only=True)[:3]
        if not end_candidates:
            end_candidates = self.fallback_engine._resolve_entities(end, exact_only=True)[:3]
        if self._should_prefer_nebula_path(max_hops=max_hops, start_candidates=start_candidates, end_candidates=end_candidates):
            nebula_result = self._direct_path_query_via_nebula(
                start_candidates=start_candidates,
                end_candidates=end_candidates,
                max_hops=max_hops,
                path_limit=path_limit,
            )
            if int(nebula_result.get("total", 0) or 0) > 0:
                return nebula_result
        local_result = self.fallback_engine.path_query(start, end, max_hops=max_hops, path_limit=path_limit)
        if int(local_result.get("total", 0) or 0) > 0:
            return local_result
        if not self._use_primary():
            return local_result
        try:
            fast_paths = self.fallback_engine._fast_path_candidates(
                start_candidates=start_candidates,
                end_candidates=end_candidates,
                max_hops=max_hops,
                path_limit=path_limit,
            )
            if int(fast_paths.get("total", 0) or 0) > 0:
                return fast_paths
            nebula_result = self._direct_path_query_via_nebula(
                start_candidates=start_candidates,
                end_candidates=end_candidates,
                max_hops=max_hops,
                path_limit=path_limit,
            )
            if int(nebula_result.get("total", 0) or 0) > 0:
                return nebula_result
            return _fallback_ranked_path_search_support(
                self,
                start_candidates=start_candidates,
                end_candidates=end_candidates,
                max_hops=max_hops,
                path_limit=path_limit,
            )
        except Exception:
            return local_result

    def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
        if self._use_primary():
            try:
                nebula_result = self._syndrome_chain_via_nebula(symptom, top_k=top_k)
                if nebula_result.get("syndromes"):
                    return nebula_result
            except Exception:
                pass
        return self.fallback_engine.syndrome_chain(symptom, top_k=top_k)

    def _syndrome_chain_via_nebula(self, symptom: str, *, top_k: int) -> dict[str, Any]:
        return _syndrome_chain_via_nebula_support(self, symptom, top_k=top_k)

    def _use_primary(self) -> bool:
        return _use_primary_support(self)

    def _path_query_mode(self) -> str:
        return _path_query_mode_support()

    def _should_prefer_nebula_path(
        self,
        *,
        max_hops: int,
        start_candidates: list[str],
        end_candidates: list[str],
    ) -> bool:
        return _should_prefer_nebula_path_support(
            self,
            max_hops=max_hops,
            start_candidates=start_candidates,
            end_candidates=end_candidates,
        )

    def _direct_path_query_via_nebula(
        self,
        *,
        start_candidates: list[str],
        end_candidates: list[str],
        max_hops: int,
        path_limit: int,
    ) -> dict[str, Any]:
        return _direct_path_query_via_nebula_support(
            self,
            start_candidates=start_candidates,
            end_candidates=end_candidates,
            max_hops=max_hops,
            path_limit=path_limit,
        )

    def _build_payload_from_nebula_path_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return _build_payload_from_nebula_path_row_support(row, fallback_engine=self.fallback_engine)

    def _extract_nebula_path_skeleton(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return _extract_nebula_path_skeleton_support(row)

    def _build_payload_from_nebula_skeleton(
        self,
        skeleton: dict[str, Any],
        *,
        vertex_map: dict[str, dict[str, Any]],
        edge_map: dict[tuple[str, str, int], dict[str, Any]],
    ) -> dict[str, Any] | None:
        return _build_payload_from_nebula_skeleton_support(
            skeleton,
            vertex_map=vertex_map,
            edge_map=edge_map,
        )

    def _collect_nebula_relations(self, entity_name: str) -> list[dict[str, Any]]:
        return _collect_nebula_relations_support(self, entity_name)

    def _adjacent_names(self, entity_name: str) -> list[str]:
        return _adjacent_names_support(self, entity_name)

    def _group_nebula_relations_by_source(
        self,
        entity_names: list[str],
        *,
        predicate_allowlist: list[str] | None = None,
        source_books: list[str] | None = None,
        limit_per_entity: int = 256,
        directions: tuple[bool, ...] = (False, True),
    ) -> dict[str, list[dict[str, Any]]]:
        return _group_nebula_relations_by_source_support(
            self,
            entity_names,
            predicate_allowlist=predicate_allowlist,
            source_books=source_books,
            limit_per_entity=limit_per_entity,
            directions=directions,
        )

    def _primary_batch_neighbors(
        self,
        entity_names: list[str],
        *,
        reverse: bool,
        predicates: list[str] | None = None,
        target_types: list[str] | None = None,
        source_books: list[str] | None = None,
        limit_per_entity: int = 64,
    ) -> list[dict[str, Any]]:
        return _primary_batch_neighbors_support(
            self,
            entity_names,
            reverse=reverse,
            predicates=predicates,
            target_types=target_types,
            source_books=source_books,
            limit_per_entity=limit_per_entity,
        )

    def _source_vid_name_map(self, entity_names: list[str]) -> dict[str, str]:
        return _source_vid_name_map_support(self, entity_names)

    def _primary_vertex_map(self, entity_names: list[str]) -> dict[str, dict[str, Any]]:
        return _primary_vertex_map_support(self, entity_names)

    def _primary_vid(self, entity_name: str) -> str:
        return _primary_vid_support(self, entity_name)

    def _resolve_entities_via_primary(
        self,
        query: str,
        preferred_types: set[str] | None = None,
        *,
        exact_only: bool = False,
    ) -> list[str]:
        return _resolve_entities_via_primary_support(
            self,
            query,
            preferred_types=preferred_types,
            exact_only=exact_only,
        )

    def _entity_lookup_exact_hit_payload(
        self,
        exact_candidates: list[str],
        *,
        query_text: str,
        predicate_allowlist: list[str] | None,
        predicate_blocklist: list[str] | None,
        top_k: int,
        limit_per_entity: int,
    ) -> dict[str, Any] | None:
        return _entity_lookup_exact_hit_payload_support(
            self,
            exact_candidates,
            query_text=query_text,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
            top_k=top_k,
            limit_per_entity=limit_per_entity,
        )

    def _entity_lookup_limit_per_candidate(self, *, query_text: str, predicate_allowlist: list[str] | None) -> int:
        return _entity_lookup_limit_per_candidate_support(
            query_text=query_text,
            predicate_allowlist=predicate_allowlist,
            query_has_source_constraint_func=self._query_has_source_constraint,
        )

    def _entity_lookup_directions(self, *, query_text: str, predicate_allowlist: list[str] | None) -> tuple[bool, ...]:
        return _entity_lookup_directions_support(
            query_text=query_text,
            predicate_allowlist=predicate_allowlist,
            query_has_source_constraint_func=self._query_has_source_constraint,
        )

    def _query_has_source_constraint(self, query_text: str) -> bool:
        return _query_has_source_constraint_support(
            query_text,
            query_fragments_func=self._query_fragments,
            query_mentions_source_book_func=self._query_mentions_source_book,
        )

    def _query_source_book_hints(self, query_text: str) -> list[str]:
        return _query_source_book_hints_support(
            query_text,
            query_fragments_func=self._query_fragments,
            source_book_exists_func=self.fallback_engine.store.source_book_exists,
        )

    def _query_fragments(self, query_text: str) -> list[str]:
        return self.fallback_engine._query_fragments(query_text)

    def _query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
        return self.fallback_engine._query_mentions_source_book(query_text, source_book)

    def _path_query_relation_rows(self, entity_name: str) -> list[dict[str, Any]]:
        return _path_query_relation_rows_support(self, entity_name)

    def _evidence_payload_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return _evidence_payload_from_row_support(row)
