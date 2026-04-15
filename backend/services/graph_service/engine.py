from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.common.evidence_payloads import normalize_source_chapter_label
from services.graph_service.nebulagraph_store import NebulaGraphStore
from services.graph_service.nebula_entity_support import entity_lookup_directions as _entity_lookup_directions_support
from services.graph_service.nebula_entity_support import entity_lookup_exact_hit_payload as _entity_lookup_exact_hit_payload_support
from services.graph_service.nebula_entity_support import entity_lookup_limit_per_candidate as _entity_lookup_limit_per_candidate_support
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
from services.graph_service.graph_relation_ranking import apply_rrf_scores as _apply_rrf_scores_support
from services.graph_service.graph_relation_ranking import build_relation_clusters as _build_relation_clusters_support
from services.graph_service.graph_relation_ranking import diversify_relation_clusters as _diversify_relation_clusters_support
from services.graph_service.graph_relation_ranking import hinted_predicates as _hinted_predicates_support
from services.graph_service.graph_relation_ranking import predicate_priority as _predicate_priority_support
from services.graph_service.graph_relation_ranking import relation_score as _relation_score_support
from services.graph_service.graph_relation_ranking import select_relation_clusters as _select_relation_clusters_support
from services.graph_service.nebula_primary_engine import NebulaPrimaryGraphEngine as _NebulaPrimaryGraphEngineImpl
from services.graph_service.nebula_query_support import direct_path_query_via_nebula as _direct_path_query_via_nebula_support
from services.graph_service.nebula_query_support import fallback_ranked_path_search as _fallback_ranked_path_search_support
from services.graph_service.nebula_query_support import path_query_mode as _path_query_mode_support
from services.graph_service.nebula_query_support import path_query_relation_rows as _path_query_relation_rows_support
from services.graph_service.nebula_query_support import should_prefer_nebula_path as _should_prefer_nebula_path_support
from services.graph_service.nebula_query_support import syndrome_chain_via_nebula as _syndrome_chain_via_nebula_support
from services.graph_service.nebula_query_support import use_primary as _use_primary_support
from services.graph_service.nebula_entity_support import query_has_source_constraint as _query_has_source_constraint_support
from services.graph_service.nebula_entity_support import query_source_book_hints as _query_source_book_hints_support
from services.graph_service.path_search import ordered_path_neighbors as _ordered_path_neighbors
from services.graph_service.path_search import search_ranked_paths as _search_ranked_paths
from services.graph_service.query_text import query_fragments as _query_fragments_from_text
from services.graph_service.query_text import query_mentions_source_book as _query_mentions_source_book_text
from services.graph_service.query_text import source_book_match_score as _source_book_match_score
from services.graph_service.relation_governance import expand_filter_predicates
from services.graph_service.relation_governance import ontology_boundary_ok
from services.graph_service.relation_governance import ontology_boundary_tier
from services.graph_service.relation_governance import relation_metadata
from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name
from services.graph_service.runtime_store import RuntimeGraphStore


SYMPTOM_RELATIONS = {"常见症状", "表现症状", "相关症状"}
SYNDROME_CHAIN_TARGET_TYPES = {"syndrome", "disease"}

RRF_RANK_CONSTANT = 20


@dataclass(frozen=True)
class GraphServiceSettings:
    backend_dir: Path
    sample_graph_path: Path
    runtime_graph_path: Path
    sample_evidence_path: Path | None = None
    runtime_evidence_path: Path | None = None
    runtime_db_path: Path | None = None
    modern_graph_path: Path | None = None
    modern_evidence_path: Path | None = None


def load_settings() -> GraphServiceSettings:
    backend_dir = Path(__file__).resolve().parents[2]
    runtime_graph_path = backend_dir / "services" / "graph_service" / "data" / "graph_runtime.json"
    return GraphServiceSettings(
        backend_dir=backend_dir,
        sample_graph_path=backend_dir / "services" / "graph_service" / "data" / "sample_graph.json",
        runtime_graph_path=runtime_graph_path,
        runtime_evidence_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.evidence.jsonl",
        runtime_db_path=runtime_graph_path.with_suffix(".db"),
        modern_graph_path=backend_dir / "services" / "graph_service" / "data" / "modern_graph_runtime.jsonl",
        modern_evidence_path=backend_dir / "services" / "graph_service" / "data" / "modern_graph_runtime.evidence.jsonl",
    )


class GraphQueryEngine:
    def __init__(self, settings: GraphServiceSettings | None = None):
        self.settings = settings or load_settings()
        runtime_evidence_path = self.settings.runtime_evidence_path or self.settings.runtime_graph_path.with_name(
            f"{self.settings.runtime_graph_path.stem}.evidence.jsonl"
        )
        self.store = RuntimeGraphStore.from_graph_paths(
            graph_path=self.settings.runtime_graph_path,
            evidence_path=runtime_evidence_path,
            sample_graph_path=self.settings.sample_graph_path,
            sample_evidence_path=self.settings.sample_evidence_path,
            modern_graph_path=self.settings.modern_graph_path,
            modern_evidence_path=self.settings.modern_evidence_path,
        )

    def health(self) -> dict[str, Any]:
        stats = self.store.stats()
        runtime_triples = int(stats.get("runtime_triples", 0) or 0)
        sample_triples = int(stats.get("sample_triples", 0) or 0)
        modern_graph_triples = int(stats.get("modern_graph_triples", 0) or 0)
        if runtime_triples > 0 or modern_graph_triples > 0:
            backend = "sqlite_runtime_graph"
        elif sample_triples > 0:
            backend = "sqlite_sample_graph"
        else:
            backend = "sqlite_empty_graph"
        evidence_paths = []
        for item in [self.settings.runtime_evidence_path, self.settings.modern_evidence_path]:
            if item:
                evidence_paths.append(str(item))
        return {
            "status": "ok" if stats["exists"] else "empty",
            "backend": backend,
            "version": "v4",
            "graph_loaded": bool(stats["exists"]),
            "graph_path": str(stats.get("db_path") or self.settings.runtime_db_path or self.settings.runtime_graph_path.with_suffix(".db")),
            "evidence_path": str(self.settings.runtime_evidence_path or ""),
            "evidence_paths": evidence_paths,
            "evidence_count": stats["evidence_count"],
            "seed_graph_loaded": sample_triples > 0,
            "runtime_graph_loaded": runtime_triples > 0,
            "modern_graph_loaded": modern_graph_triples > 0,
            "modern_graph_triples": modern_graph_triples,
            "node_count": stats["node_count"],
            "edge_count": stats["total_triples"],
        }

    def entity_lookup(
        self,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> dict[str, Any]:
        candidates = self._resolve_entities(name)
        if not candidates:
            return {}
        canonical_name = candidates[0]
        entity_type = self.entity_type(canonical_name)
        relations = self._select_relation_clusters(
            self._filter_relations(
                self._annotate_relation_rows(self._collect_relations(canonical_name), anchor_entity_type=entity_type),
                predicate_allowlist=predicate_allowlist,
                predicate_blocklist=predicate_blocklist,
            ),
            query_text=name,
            top_k=max(1, top_k),
        )
        return {
            "entity": {
                "name": name.strip(),
                "canonical_name": canonical_name,
                "entity_type": entity_type,
            },
            "relations": relations,
            "total": len(relations),
        }

    def path_query(self, start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
        start_candidates = self._resolve_entities(start, exact_only=True)
        end_candidates = self._resolve_entities(end, exact_only=True)
        fast_paths = self._fast_path_candidates(
            start_candidates=start_candidates,
            end_candidates=end_candidates,
            max_hops=max_hops,
            path_limit=path_limit,
        )
        if int(fast_paths.get("total", 0) or 0) > 0:
            return fast_paths
        return _search_ranked_paths(
            start_candidates=start_candidates,
            target_set=set(end_candidates[:3]),
            max_hops=max_hops,
            path_limit=path_limit,
            relation_rows=self._path_query_relation_rows,
            build_path_payload=self._build_path_payload,
        )

    def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
        symptom_candidates = self._resolve_entities(symptom, preferred_types={"symptom"})
        if not symptom_candidates:
            symptom_candidates = self._resolve_entities(symptom)
        if not symptom_candidates:
            return {"symptom": symptom.strip(), "syndromes": []}

        deduped: dict[str, dict[str, Any]] = {}
        for symptom_node in symptom_candidates[:5]:
            for row in self.store.syndromes_for_symptom(symptom_node):
                syndrome_name = str(row.get("target", "")).strip()
                predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
                if not syndrome_name or predicate not in SYMPTOM_RELATIONS:
                    continue
                item = {
                    "name": syndrome_name,
                    "score": 0.92 if symptom_node == symptom.strip() else 0.82,
                    "recommended_formulas": self._collect_recommended_formulas(syndrome_name),
                }
                item.update(self._edge_evidence_payload(row))
                existing = deduped.get(syndrome_name)
                if existing is None or float(item["score"]) > float(existing["score"]):
                    deduped[syndrome_name] = item

        results = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)[: max(1, top_k)]
        return {"symptom": symptom.strip(), "syndromes": results}

    def entity_type(self, entity_name: str) -> str:
        return self.store.entity_type(entity_name)

    def _resolve_entities(self, query: str, preferred_types: set[str] | None = None, *, exact_only: bool = False) -> list[str]:
        if exact_only:
            exact = self.store.exact_entities(query, preferred_types, limit=20)
            if exact:
                return exact
        return self.store.resolve_entities(query, preferred_types, limit=20)

    def _collect_relations(self, entity_name: str) -> list[dict[str, Any]]:
        return self.store.collect_relations(entity_name)

    def _annotate_relation_rows(self, rows: list[dict[str, Any]], *, anchor_entity_type: str) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            predicate = _normalize_relation_name(str(item.get("predicate", "")).strip())
            source_book = str(item.get("source_book", "")).strip()
            item["predicate"] = predicate
            item["source_chapter"] = normalize_source_chapter_label(
                source_book=source_book,
                source_chapter=str(item.get("source_chapter", "")).strip(),
            )
            item.update(relation_metadata(predicate))
            item["ontology_boundary_tier"] = ontology_boundary_tier(
                predicate=predicate,
                direction=str(item.get("direction", "")).strip() or "out",
                anchor_entity_type=anchor_entity_type,
                target_type=str(item.get("target_type", "")).strip() or "other",
            )
            item["ontology_boundary_ok"] = ontology_boundary_ok(
                predicate=predicate,
                direction=str(item.get("direction", "")).strip() or "out",
                anchor_entity_type=anchor_entity_type,
                target_type=str(item.get("target_type", "")).strip() or "other",
            )
            annotated.append(item)
        return annotated

    def _filter_relations(
        self,
        rows: list[dict[str, Any]],
        *,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        allow = {_normalize_relation_name(item) for item in expand_filter_predicates(predicate_allowlist or [])}
        block = {_normalize_relation_name(item) for item in expand_filter_predicates(predicate_blocklist or [])}
        if not allow and not block:
            return rows
        filtered: list[dict[str, Any]] = []
        for row in rows:
            predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
            if allow and predicate not in allow:
                continue
            if block and predicate in block:
                continue
            filtered.append(row)
        return filtered

    def _select_relation_clusters(self, rows: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
        return _select_relation_clusters_support(self, rows, query_text=query_text, top_k=top_k)

    def _build_relation_clusters(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _build_relation_clusters_support(rows)

    def _apply_rrf_scores(self, clusters: list[dict[str, Any]], *, query_text: str) -> None:
        _apply_rrf_scores_support(self, clusters, query_text=query_text)

    def _diversify_relation_clusters(self, clusters: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
        return _diversify_relation_clusters_support(self, clusters, query_text=query_text, top_k=top_k)

    def _predicate_priority(self, relation: dict[str, Any]) -> float:
        return _predicate_priority_support(relation)

    def _hinted_predicates(self, query_text: str) -> set[str]:
        return _hinted_predicates_support(query_text)

    def _relation_score(self, relation: dict[str, Any], query_text: str) -> int:
        return _relation_score_support(self, relation, query_text)

    def _query_fragments(self, query_text: str) -> list[str]:
        return _query_fragments_from_text(query_text)

    def _query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
        return _query_mentions_source_book_text(query_text, source_book)

    def _source_book_match_score(self, relation: dict[str, Any], query_text: str) -> int:
        return _source_book_match_score(relation, query_text)

    def _adjacent_names(self, entity_name: str) -> list[str]:
        return self.store.adjacent_names(entity_name)

    def _path_query_relation_rows(self, entity_name: str) -> list[dict[str, Any]]:
        return self._annotate_relation_rows(
            self.store.collect_relations(entity_name),
            anchor_entity_type=self.entity_type(entity_name),
        )

    def _fast_path_candidates(
        self,
        *,
        start_candidates: list[str],
        end_candidates: list[str],
        max_hops: int,
        path_limit: int,
    ) -> dict[str, Any]:
        if not start_candidates or not end_candidates:
            return {"paths": [], "total": 0}
        built_paths: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, ...]] = set()
        for start_node in start_candidates[:2]:
            for end_node in end_candidates[:2]:
                direct_payload = self._build_path_payload([start_node, end_node])
                if direct_payload:
                    signature = tuple(direct_payload.get("nodes", []))
                    if signature not in seen_signatures:
                        seen_signatures.add(signature)
                        built_paths.append(direct_payload)
                        if len(built_paths) >= path_limit:
                            built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
                            return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}
                if max_hops < 2:
                    continue
                for bridge in self.store.two_hop_bridges(start_node, end_node, limit=max(4, path_limit * 2))[: max(2, path_limit)]:
                    payload = self._build_path_payload([start_node, bridge, end_node])
                    if not payload:
                        continue
                    signature = tuple(payload.get("nodes", []))
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)
                    built_paths.append(payload)
                    if len(built_paths) >= path_limit:
                        built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
                        return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}
        built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}

    def _build_path_payload(self, nodes: list[str]) -> dict[str, Any] | None:
        edges: list[str] = []
        sources: list[dict[str, Any]] = []
        for left, right in zip(nodes, nodes[1:]):
            edge_data = self.store.first_edge_between(left, right)
            reverse = False
            if not edge_data:
                edge_data = self.store.first_edge_between(right, left)
                reverse = True
            if not edge_data:
                return None
            relation = _normalize_relation_name(str(edge_data.get("predicate", "相关")))
            if reverse:
                relation = f"{relation}(逆向)"
            edges.append(relation)
            source_book = str(edge_data.get("source_book", ""))
            source_item: dict[str, Any] = {
                "source_book": source_book,
                "source_chapter": normalize_source_chapter_label(
                    source_book=source_book,
                    source_chapter=str(edge_data.get("source_chapter", "")),
                ),
            }
            source_item.update(self._edge_evidence_payload(edge_data))
            if source_item not in sources:
                sources.append(source_item)

        hop_count = len(nodes) - 1
        score = round(1.0 / max(hop_count, 1) + min(len(sources), 3) * 0.05, 4)
        return {"nodes": nodes, "edges": edges, "score": score, "sources": sources}

    def _collect_recommended_formulas(self, syndrome_node: str) -> list[str]:
        return self.store.recommended_formulas(syndrome_node)

    def _edge_evidence_payload(self, edge_data: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        fact_id = str(edge_data.get("fact_id", "")).strip()
        if fact_id:
            payload["fact_id"] = fact_id
        fact_ids = edge_data.get("fact_ids")
        if isinstance(fact_ids, list) and fact_ids:
            payload["fact_ids"] = [str(item).strip() for item in fact_ids if str(item).strip()]
        source_text = str(edge_data.get("source_text", "")).strip()
        if source_text:
            payload["source_text"] = source_text
        confidence = edge_data.get("confidence")
        if confidence not in (None, ""):
            payload["confidence"] = float(confidence or 0.0)
        return payload


NebulaPrimaryGraphEngine = _NebulaPrimaryGraphEngineImpl

_graph_engine: GraphQueryEngine | NebulaPrimaryGraphEngine | None = None


def get_graph_engine() -> GraphQueryEngine | NebulaPrimaryGraphEngine:
    global _graph_engine
    if _graph_engine is None:
        selected_backend = os.getenv("GRAPH_BACKEND", "sqlite").strip().lower()
        fallback_engine = GraphQueryEngine()
        if selected_backend in {"nebula", "sqlite"}:
            _graph_engine = NebulaPrimaryGraphEngine(
                primary_store=NebulaGraphStore(),
                fallback_engine=fallback_engine,
            )
        else:
            _graph_engine = fallback_engine
    return _graph_engine

