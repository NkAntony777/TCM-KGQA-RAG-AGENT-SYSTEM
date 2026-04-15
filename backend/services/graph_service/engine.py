from __future__ import annotations

import json
import os
from collections import Counter, deque
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any, Callable

from services.common.evidence_payloads import normalize_book_label
from services.common.evidence_payloads import normalize_source_chapter_label
from services.graph_service.nebulagraph_store import entity_vid
from services.graph_service.nebulagraph_store import NebulaGraphStore
from services.graph_service.relation_governance import ACCEPTABLE_POLYSEMY
from services.graph_service.relation_governance import bridge_allowed
from services.graph_service.relation_governance import expand_filter_predicates
from services.graph_service.relation_governance import hinted_predicates as governance_hinted_predicates
from services.graph_service.relation_governance import LIKELY_DIRTY
from services.graph_service.relation_governance import ontology_boundary_ok
from services.graph_service.relation_governance import ontology_boundary_tier
from services.graph_service.relation_governance import path_expand_allowed
from services.graph_service.relation_governance import priority_boost as governance_priority_boost
from services.graph_service.relation_governance import relation_metadata
from services.graph_service.relation_governance import REVIEW_NEEDED
from services.graph_service.runtime_store import RuntimeGraphStore


def _legacy_utf8_gbk_alias(text: str) -> str:
    """Recover one common mojibake form without leaving corrupted literals in source."""
    try:
        return text.encode("utf-8").decode("gbk")
    except UnicodeDecodeError:
        return text


RELATION_ALIASES = {
    _legacy_utf8_gbk_alias("常见症状"): "常见症状",
    _legacy_utf8_gbk_alias("表现症状"): "表现症状",
    _legacy_utf8_gbk_alias("相关症状"): "相关症状",
    _legacy_utf8_gbk_alias("推荐方剂"): "推荐方剂",
}


def _normalize_relation_name(name: str) -> str:
    normalized = (name or "").strip()
    return RELATION_ALIASES.get(normalized, normalized)


SYMPTOM_RELATIONS = {"常见症状", "表现症状", "相关症状"}
SYNDROME_CHAIN_TARGET_TYPES = {"syndrome", "disease"}

PREDICATE_BASE_PRIORITY: dict[str, float] = {
    "治疗证候": 1.0,
    "功效": 0.98,
    "使用药材": 0.96,
    "治疗症状": 0.93,
    "治法": 0.9,
    "治疗疾病": 0.9,
    "推荐方剂": 0.88,
    "归经": 0.85,
    "药性": 0.82,
    "配伍禁忌": 0.8,
    "食忌": 0.78,
    "常见症状": 0.76,
    "别名": 0.72,
    "属于范畴": 0.65,
}

RRF_RANK_CONSTANT = 20
PATH_QUERY_FANOUT_CAP = 24
NEBULA_PATH_QUERY_AUTO_MIN_HOPS = 4
NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS = 4
PATH_QUERY_PREDICATE_BOOST: dict[str, float] = {
    "推荐方剂": 0.14,
    "治疗证候": 0.14,
    "常见症状": 0.12,
    "治疗症状": 0.1,
    "功效": 0.09,
    "使用药材": 0.08,
}


def _path_query_predicate_priority(predicate: str) -> float:
    normalized = _normalize_relation_name(predicate)
    return (
        float(PREDICATE_BASE_PRIORITY.get(normalized, 0.6))
        + float(PATH_QUERY_PREDICATE_BOOST.get(normalized, 0.0))
        + float(governance_priority_boost(normalized))
    )


QUERY_FRAGMENT_SPLIT_PATTERN = re.compile(r"[\s，。；、！？?：:（）()\[\]【】《》“”\"'·/]+")


def _ordered_path_neighbors(
    rows: list[dict[str, Any]],
    *,
    target_set: set[str],
    fanout_cap: int = PATH_QUERY_FANOUT_CAP,
) -> list[str]:
    best_by_neighbor: dict[str, tuple[int, float, float, str]] = {}
    for row in rows:
        predicate = str(row.get("predicate", "")).strip()
        if not path_expand_allowed(predicate) or not bridge_allowed(predicate):
            continue
        if row.get("ontology_boundary_tier") in {LIKELY_DIRTY, REVIEW_NEEDED}:
            continue
        neighbor = str(row.get("target") or row.get("neighbor_name") or "").strip()
        if not neighbor:
            continue
        score = (
            1 if neighbor in target_set else 0,
            _path_query_predicate_priority(predicate),
            float(row.get("confidence", 0.0) or 0.0),
            neighbor,
        )
        existing = best_by_neighbor.get(neighbor)
        if existing is None or score > existing:
            best_by_neighbor[neighbor] = score
    ordered = sorted(
        best_by_neighbor.items(),
        key=lambda item: (-item[1][0], -item[1][1], -item[1][2], item[0]),
    )
    return [neighbor for neighbor, _ in ordered[: max(1, fanout_cap)]]


def _search_ranked_paths(
    *,
    start_candidates: list[str],
    target_set: set[str],
    max_hops: int,
    path_limit: int,
    relation_rows: Callable[[str], list[dict[str, Any]]],
    build_path_payload: Callable[[list[str]], dict[str, Any] | None],
) -> dict[str, Any]:
    if not start_candidates or not target_set:
        return {"paths": [], "total": 0}

    built_paths: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    relation_cache: dict[str, list[dict[str, Any]]] = {}
    ordered_neighbor_cache: dict[tuple[str, tuple[str, ...]], list[str]] = {}

    def _cached_relation_rows(node: str) -> list[dict[str, Any]]:
        rows = relation_cache.get(node)
        if rows is None:
            rows = relation_rows(node)
            relation_cache[node] = rows
        return rows

    def _cached_ordered_neighbors(node: str) -> list[str]:
        cache_key = (node, tuple(sorted(target_set)))
        neighbors = ordered_neighbor_cache.get(cache_key)
        if neighbors is None:
            neighbors = _ordered_path_neighbors(_cached_relation_rows(node), target_set=target_set)
            ordered_neighbor_cache[cache_key] = neighbors
        return neighbors

    # Fast path: try exact edge and high-value 2-hop bridge before broad BFS.
    for start_node in start_candidates[:3]:
        if len(built_paths) >= path_limit:
            break
        direct_payload = build_path_payload([start_node, next(iter(target_set))]) if len(target_set) == 1 else None
        if direct_payload and tuple(direct_payload.get("nodes", [])) not in seen_signatures:
            seen_signatures.add(tuple(direct_payload.get("nodes", [])))
            built_paths.append(direct_payload)
            if len(built_paths) >= path_limit:
                break
        if max_hops < 2:
            continue
        start_neighbors = _cached_ordered_neighbors(start_node)
        target_neighbors_by_target: dict[str, set[str]] = {
            target: set(_cached_ordered_neighbors(target))
            for target in list(target_set)[:3]
        }
        for target in list(target_set)[:3]:
            if target in start_neighbors:
                payload = build_path_payload([start_node, target])
                if payload:
                    signature = tuple(payload.get("nodes", []))
                    if signature not in seen_signatures:
                        seen_signatures.add(signature)
                        built_paths.append(payload)
                        if len(built_paths) >= path_limit:
                            break
            bridge_candidates = [neighbor for neighbor in start_neighbors if neighbor in target_neighbors_by_target.get(target, set())]
            for bridge in bridge_candidates[: min(6, path_limit)]:
                payload = build_path_payload([start_node, bridge, target])
                if not payload:
                    continue
                signature = tuple(payload.get("nodes", []))
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                built_paths.append(payload)
                if len(built_paths) >= path_limit:
                    break
            if len(built_paths) >= path_limit:
                break

    for start_node in start_candidates[:3]:
        queue: deque[list[str]] = deque([[start_node]])
        best_depth_by_node: dict[str, int] = {start_node: 0}
        while queue and len(built_paths) < path_limit:
            current_path = queue.popleft()
            current_node = current_path[-1]
            current_depth = len(current_path) - 1
            if current_depth >= max_hops:
                continue
            for next_node in _cached_ordered_neighbors(current_node):
                if next_node in current_path:
                    continue
                new_path = current_path + [next_node]
                signature = tuple(new_path)
                if signature in seen_signatures:
                    continue
                new_depth = current_depth + 1
                if next_node not in target_set:
                    best_depth = best_depth_by_node.get(next_node)
                    if best_depth is not None and new_depth >= best_depth:
                        continue
                    best_depth_by_node[next_node] = new_depth
                seen_signatures.add(signature)
                if next_node in target_set:
                    payload = build_path_payload(new_path)
                    if payload:
                        built_paths.append(payload)
                        if len(built_paths) >= path_limit:
                            break
                if new_depth < max_hops:
                    queue.append(new_path)

    built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}


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
        clusters = self._build_relation_clusters(rows)
        if not clusters:
            return []
        self._apply_rrf_scores(clusters, query_text=query_text)
        return self._diversify_relation_clusters(clusters, query_text=query_text, top_k=top_k)

    def _build_relation_clusters(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
            target = str(row.get("target", "")).strip()
            direction = str(row.get("direction", "")).strip()
            if not predicate or not target or not direction:
                continue
            key = (
                predicate,
                target,
                direction,
            )
            confidence = float(row.get("confidence", 0.0) or 0.0)
            source_book = str(row.get("source_book", "")).strip()
            source_chapter = normalize_source_chapter_label(
                source_book=source_book,
                source_chapter=str(row.get("source_chapter", "")).strip(),
            )
            raw_fact_ids = row.get("fact_ids")
            fact_ids: set[str] = set()
            if isinstance(raw_fact_ids, list):
                fact_ids = {str(item).strip() for item in raw_fact_ids if str(item).strip()}
            fact_id = str(row.get("fact_id", "")).strip()
            if fact_id:
                fact_ids.add(fact_id)
            existing = deduped.get(key)
            if existing is None:
                cluster = dict(row)
                cluster["predicate"] = predicate
                cluster["target"] = target
                cluster["direction"] = direction
                cluster["target_type"] = str(row.get("target_type", "")).strip() or "other"
                cluster.update(relation_metadata(predicate))
                cluster["ontology_boundary_ok"] = row.get("ontology_boundary_ok")
                cluster["ontology_boundary_tier"] = row.get("ontology_boundary_tier")
                cluster["_source_books"] = {source_book} if source_book else set()
                cluster["_source_chapters"] = {source_chapter} if source_chapter else set()
                cluster["_fact_ids"] = set(fact_ids)
                cluster["_confidence_sum"] = confidence
                cluster["_evidence_count"] = 1
                deduped[key] = cluster
                continue
            existing["_evidence_count"] = int(existing.get("_evidence_count", 0) or 0) + 1
            existing["_confidence_sum"] = float(existing.get("_confidence_sum", 0.0) or 0.0) + confidence
            if source_book:
                existing["_source_books"].add(source_book)
            if source_chapter:
                existing["_source_chapters"].add(source_chapter)
            if row.get("ontology_boundary_ok") is False:
                existing["ontology_boundary_ok"] = False
            existing_tier = str(existing.get("ontology_boundary_tier", "")).strip()
            row_tier = str(row.get("ontology_boundary_tier", "")).strip()
            if row_tier == LIKELY_DIRTY or (row_tier == REVIEW_NEEDED and existing_tier != LIKELY_DIRTY):
                existing["ontology_boundary_tier"] = row_tier
            existing["_fact_ids"].update(fact_ids)
            current_confidence = confidence
            existing_confidence = float(existing.get("confidence", 0.0) or 0.0)
            existing_text = str(existing.get("source_text", "")).strip()
            current_text = str(row.get("source_text", "")).strip()
            if current_confidence > existing_confidence or (
                math.isclose(current_confidence, existing_confidence) and len(current_text) > len(existing_text)
            ):
                for field in ("fact_id", "source_text", "confidence", "source_book", "source_chapter", "target_type"):
                    if field in row and row.get(field) not in (None, ""):
                        existing[field] = row.get(field)

        clusters: list[dict[str, Any]] = []
        for cluster in deduped.values():
            source_books = sorted(book for book in cluster.pop("_source_books", set()) if book)
            source_chapters = sorted(chapter for chapter in cluster.pop("_source_chapters", set()) if chapter)
            fact_ids = sorted(fact_id for fact_id in cluster.pop("_fact_ids", set()) if fact_id)
            evidence_count = int(cluster.pop("_evidence_count", 0) or 0)
            confidence_sum = float(cluster.pop("_confidence_sum", 0.0) or 0.0)
            avg_confidence = confidence_sum / evidence_count if evidence_count else float(cluster.get("confidence", 0.0) or 0.0)
            cluster["evidence_count"] = evidence_count
            cluster["source_book_count"] = len(source_books)
            cluster["source_chapter_count"] = len(source_chapters)
            cluster["source_books"] = source_books[:5]
            cluster["avg_confidence"] = round(avg_confidence, 4)
            cluster["max_confidence"] = round(float(cluster.get("confidence", 0.0) or 0.0), 4)
            if fact_ids:
                cluster["fact_ids"] = fact_ids[:12]
                cluster["fact_id"] = str(cluster.get("fact_id", "")).strip() or fact_ids[0]
            clusters.append(cluster)
        return clusters

    def _apply_rrf_scores(self, clusters: list[dict[str, Any]], *, query_text: str) -> None:
        rank_views = [
            sorted(
                clusters,
                key=lambda item: (
                    -self._relation_score(item, query_text),
                    -self._predicate_priority(item),
                    -float(item.get("max_confidence", 0.0) or 0.0),
                    -int(item.get("source_book_count", 0) or 0),
                ),
            ),
            sorted(
                clusters,
                key=lambda item: (
                    -float(item.get("max_confidence", 0.0) or 0.0),
                    -float(item.get("avg_confidence", 0.0) or 0.0),
                    -int(item.get("source_book_count", 0) or 0),
                    -int(item.get("evidence_count", 0) or 0),
                ),
            ),
            sorted(
                clusters,
                key=lambda item: (
                    -int(item.get("source_book_count", 0) or 0),
                    -int(item.get("evidence_count", 0) or 0),
                    -float(item.get("max_confidence", 0.0) or 0.0),
                ),
            ),
            sorted(
                clusters,
                key=lambda item: (
                    -self._predicate_priority(item),
                    -self._relation_score(item, query_text),
                    -int(item.get("source_book_count", 0) or 0),
                    -float(item.get("max_confidence", 0.0) or 0.0),
                ),
            ),
        ]
        if any(self._source_book_match_score(item, query_text) > 0 for item in clusters):
            rank_views.append(
                sorted(
                    clusters,
                    key=lambda item: (
                        -self._source_book_match_score(item, query_text),
                        -self._relation_score(item, query_text),
                        -float(item.get("max_confidence", 0.0) or 0.0),
                    ),
                )
            )
        for cluster in clusters:
            cluster["_fusion_score"] = 0.0
        for view in rank_views:
            for rank, cluster in enumerate(view, start=1):
                cluster["_fusion_score"] += 1.0 / (RRF_RANK_CONSTANT + rank)
        max_fusion = max(float(cluster.get("_fusion_score", 0.0) or 0.0) for cluster in clusters) or 1.0
        for cluster in clusters:
            cluster["_fusion_score_norm"] = float(cluster.get("_fusion_score", 0.0) or 0.0) / max_fusion

    def _diversify_relation_clusters(self, clusters: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
        hinted_predicates = self._hinted_predicates(query_text)
        diversity_lambda = 0.18 if hinted_predicates else 0.42
        remaining = list(clusters)
        selected: list[dict[str, Any]] = []
        predicate_counts: Counter[str] = Counter()
        direction_counts: Counter[str] = Counter()
        target_type_counts: Counter[str] = Counter()
        target_predicate_coverage = min(max(3, top_k // 2), top_k)

        while remaining and len(selected) < top_k:
            best_index = 0
            best_score = float("-inf")
            for index, cluster in enumerate(remaining):
                predicate = str(cluster.get("predicate", "")).strip()
                direction = str(cluster.get("direction", "")).strip()
                target_type = str(cluster.get("target_type", "")).strip() or "other"
                predicate_novelty = 1.0 / (1 + predicate_counts[predicate])
                direction_novelty = 1.0 / (1 + direction_counts[direction])
                target_type_novelty = 1.0 / (1 + target_type_counts[target_type])
                novelty = 0.7 * predicate_novelty + 0.15 * direction_novelty + 0.15 * target_type_novelty
                if predicate_counts[predicate] == 0:
                    novelty += 0.2
                tier = str(cluster.get("ontology_boundary_tier", "")).strip()
                if tier == REVIEW_NEEDED:
                    novelty *= 0.55
                elif tier == LIKELY_DIRTY:
                    novelty *= 0.2
                hinted_bonus = 0.0
                if hinted_predicates:
                    if predicate in hinted_predicates:
                        hinted_bonus = 0.08
                    else:
                        novelty *= 0.55
                elif len(predicate_counts) < target_predicate_coverage and predicate_counts[predicate] > 0:
                    novelty *= 0.55
                diversified_score = (
                    (1.0 - diversity_lambda) * float(cluster.get("_fusion_score_norm", 0.0) or 0.0)
                    + diversity_lambda * novelty
                    + hinted_bonus
                )
                if diversified_score > best_score:
                    best_score = diversified_score
                    best_index = index
            chosen = remaining.pop(best_index)
            chosen["score"] = round(best_score, 4)
            selected.append(chosen)
            predicate_counts[str(chosen.get("predicate", "")).strip()] += 1
            direction_counts[str(chosen.get("direction", "")).strip()] += 1
            target_type_counts[str(chosen.get("target_type", "")).strip() or "other"] += 1

        for cluster in selected:
            cluster.pop("_fusion_score", None)
            cluster.pop("_fusion_score_norm", None)
        return selected

    def _predicate_priority(self, relation: dict[str, Any]) -> float:
        predicate = _normalize_relation_name(str(relation.get("predicate", "")).strip())
        return float(PREDICATE_BASE_PRIORITY.get(predicate, 0.6)) + float(governance_priority_boost(predicate))

    def _hinted_predicates(self, query_text: str) -> set[str]:
        return {_normalize_relation_name(item) for item in governance_hinted_predicates(query_text)}

    def _relation_score(self, relation: dict[str, Any], query_text: str) -> int:
        score = 0
        predicate = str(relation.get("predicate", "")).strip()
        target = str(relation.get("target", "")).strip()
        source_text = str(relation.get("source_text", "")).strip()
        source_book = str(relation.get("source_book", "")).strip()
        source_chapter = str(relation.get("source_chapter", "")).strip()
        predicate_family = str(relation.get("predicate_family", "")).strip()
        normalized_predicate = str(relation.get("normalized_predicate", "")).strip()
        normalized_query = (query_text or "").strip()
        query_fragments = self._query_fragments(normalized_query)
        hinted = self._hinted_predicates(normalized_query)
        if predicate in hinted:
            score += 50
        if predicate and predicate in normalized_query:
            score += 20
        if normalized_predicate and normalized_predicate in normalized_query:
            score += 18
        if predicate_family and predicate_family.replace("族", "") in normalized_query:
            score += 16
        if target and target in normalized_query:
            score += 10
        if target and target in query_fragments:
            score += 18
        if source_text and any(fragment and fragment in source_text for fragment in query_fragments):
            score += 5
        score += self._source_book_match_score(relation, normalized_query) * 80
        if source_chapter and source_chapter in normalized_query:
            score += 10
        score += int(round(self._predicate_priority(relation) * 10))
        score += min(int(relation.get("source_book_count", 0) or 0), 5)
        score += min(int(math.log1p(int(relation.get("evidence_count", 0) or 0)) * 4), 8)
        if relation.get("direction") == "out":
            score += 1
        tier = str(relation.get("ontology_boundary_tier", "")).strip()
        if tier == ACCEPTABLE_POLYSEMY:
            score -= 6
        elif tier == REVIEW_NEEDED:
            score -= 18
        elif tier == LIKELY_DIRTY:
            score -= 30
        return score

    def _query_fragments(self, query_text: str) -> list[str]:
        normalized = (
            str(query_text or "")
            .replace("有什么", " ")
            .replace("是什么", " ")
            .replace("有哪些", " ")
            .replace("什么", " ")
            .replace("请从", " ")
            .replace("请结合", " ")
            .replace("并说明", " ")
            .replace("并论述", " ")
            .replace("并比较", " ")
        )
        candidates = [item.strip() for item in QUERY_FRAGMENT_SPLIT_PATTERN.split(normalized)]
        fragments: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            item = item.lstrip("中就按从与和及并请")
            if len(item) < 2:
                continue
            if item in seen:
                continue
            seen.add(item)
            fragments.append(item)
        return fragments

    def _query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
        normalized_query = str(query_text or "").strip()
        normalized_book = normalize_book_label(source_book)
        if not normalized_query or not normalized_book:
            return False
        if normalized_book in normalized_query:
            return True
        return f"《{normalized_book}》" in normalized_query

    def _source_book_match_score(self, relation: dict[str, Any], query_text: str) -> int:
        source_book = str(relation.get("source_book", "")).strip()
        if not source_book:
            return 0
        return 2 if self._query_mentions_source_book(query_text, source_book) else 0

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


class NebulaPrimaryGraphEngine:
    def __init__(
        self,
        primary_store: NebulaGraphStore | None = None,
        fallback_engine: GraphQueryEngine | None = None,
    ):
        self.primary_store = primary_store or NebulaGraphStore()
        self.fallback_engine = fallback_engine or GraphQueryEngine()

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
                    self.fallback_engine._annotate_relation_rows(  # noqa: SLF001
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
                        self.fallback_engine._annotate_relation_rows(  # noqa: SLF001
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
            fast_paths = self.fallback_engine._fast_path_candidates(  # noqa: SLF001
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
            return _search_ranked_paths(
                start_candidates=start_candidates,
                target_set=set(end_candidates),
                max_hops=max_hops,
                path_limit=path_limit,
                relation_rows=self._path_query_relation_rows,
                build_path_payload=self.fallback_engine._build_path_payload,
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
        symptom_candidates = self._resolve_entities_via_primary(symptom, preferred_types={"symptom"})
        if not symptom_candidates:
            symptom_candidates = self.fallback_engine._resolve_entities(symptom, preferred_types={"symptom"})
        if not symptom_candidates:
            symptom_candidates = self._resolve_entities_via_primary(symptom)
        if not symptom_candidates:
            symptom_candidates = self.fallback_engine._resolve_entities(symptom)
        if not symptom_candidates:
            return {"symptom": symptom.strip(), "syndromes": []}
        try:
            symptom_names = symptom_candidates[:5]
            raw_rows = self._primary_batch_neighbors(
                symptom_names,
                reverse=True,
                predicates=list(SYMPTOM_RELATIONS),
                target_types=list(SYNDROME_CHAIN_TARGET_TYPES),
                limit_per_entity=max(8, top_k * 8),
            )
            deduped: dict[str, dict[str, Any]] = {}
            source_vid_to_name = self._source_vid_name_map(symptom_names)
            for row in raw_rows:
                symptom_node = source_vid_to_name.get(str(row.get("source_vid", "")).strip(), symptom.strip())
                if symptom_node == symptom.strip() and len(symptom_names) == 1:
                    symptom_node = symptom_names[0]
                syndrome_name = str(row.get("neighbor_name", "")).strip()
                syndrome_type = str(row.get("neighbor_type", "")).strip()
                predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
                if (
                    not syndrome_name
                    or predicate not in SYMPTOM_RELATIONS
                    or (syndrome_type and syndrome_type not in SYNDROME_CHAIN_TARGET_TYPES)
                ):
                    continue
                item = {
                    "name": syndrome_name,
                    "score": 0.92 if symptom_node == symptom.strip() else 0.82,
                    "recommended_formulas": self.fallback_engine._collect_recommended_formulas(syndrome_name),
                }
                item.update(self._evidence_payload_from_row(row))
                existing = deduped.get(syndrome_name)
                if existing is None or float(item["score"]) > float(existing["score"]):
                    deduped[syndrome_name] = item

            results = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)[: max(1, top_k)]
            return {"symptom": symptom.strip(), "syndromes": results}
        except Exception:
            return {"symptom": symptom.strip(), "syndromes": []}

    def _use_primary(self) -> bool:
        return self.primary_store.ready()

    def _path_query_mode(self) -> str:
        mode = os.getenv("PATH_QUERY_EXECUTION_MODE", "nebula_first").strip().lower()
        return mode if mode in {"local_first", "nebula_first", "auto"} else "local_first"

    def _should_prefer_nebula_path(
        self,
        *,
        max_hops: int,
        start_candidates: list[str],
        end_candidates: list[str],
    ) -> bool:
        if not self._use_primary() or not start_candidates or not end_candidates:
            return False
        mode = self._path_query_mode()
        if mode == "nebula_first":
            return True
        if mode == "auto":
            auto_min_hops = int(os.getenv("NEBULA_PATH_QUERY_AUTO_MIN_HOPS", str(NEBULA_PATH_QUERY_AUTO_MIN_HOPS)).strip() or NEBULA_PATH_QUERY_AUTO_MIN_HOPS)
            auto_min_pairs = int(
                os.getenv("NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS", str(NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS)).strip()
                or NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS
            )
            pair_count = max(1, len(start_candidates[:3])) * max(1, len(end_candidates[:3]))
            return int(max_hops) >= auto_min_hops or pair_count >= auto_min_pairs
        return False

    def _direct_path_query_via_nebula(
        self,
        *,
        start_candidates: list[str],
        end_candidates: list[str],
        max_hops: int,
        path_limit: int,
    ) -> dict[str, Any]:
        built_paths: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, ...]] = set()
        rows = self.primary_store.find_shortest_path_rows(
            start_candidates[:3],
            end_candidates[:3],
            max_hops=max_hops,
            limit=max(1, path_limit * 3),
            with_prop=False,
        )
        skeletons = [self._extract_nebula_path_skeleton(row) for row in rows]
        skeletons = [item for item in skeletons if item]
        vertex_vids: set[str] = set()
        edge_refs: list[dict[str, Any]] = []
        for skeleton in skeletons:
            vertex_vids.update(skeleton["node_vids"])
            edge_refs.extend(skeleton["edge_refs"])
        vertex_map = self.primary_store.fetch_vertices_by_vids(sorted(vertex_vids))
        edge_map = self.primary_store.fetch_edges_by_refs(edge_refs)
        for skeleton in skeletons:
            payload = self._build_payload_from_nebula_skeleton(
                skeleton,
                vertex_map=vertex_map,
                edge_map=edge_map,
            )
            if not payload:
                continue
            signature = tuple(payload.get("nodes", []))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            built_paths.append(payload)
            if len(built_paths) >= path_limit:
                break
        built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit]), "strategy": "nebula_shortest_path"}

    def _build_payload_from_nebula_path_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        segments = row.get("p")
        if not isinstance(segments, list) or len(segments) < 3:
            return None
        vertex_segments = [segment for index, segment in enumerate(segments) if index % 2 == 0 and isinstance(segment, dict)]
        edge_segments = [segment for index, segment in enumerate(segments) if index % 2 == 1 and isinstance(segment, dict)]
        nodes = [str(segment.get("entity.name", "")).strip() for segment in vertex_segments]
        if not nodes or any(not name for name in nodes):
            return None
        if len(edge_segments) != len(nodes) - 1:
            return None
        edges: list[str] = []
        sources: list[dict[str, Any]] = []
        for left, right, segment in zip(nodes, nodes[1:], edge_segments):
            predicate = _normalize_relation_name(str(segment.get("predicate", "相关")).strip() or "相关")
            reverse = False
            edge_data = self.fallback_engine.store.first_edge_between(left, right)
            if not edge_data:
                edge_data = self.fallback_engine.store.first_edge_between(right, left)
                reverse = bool(edge_data)
            if edge_data:
                predicate = _normalize_relation_name(str(edge_data.get("predicate", predicate)).strip() or predicate)
                source_book = str(edge_data.get("source_book", "")).strip()
                source_item: dict[str, Any] = {
                    "source_book": source_book,
                    "source_chapter": normalize_source_chapter_label(
                        source_book=source_book,
                        source_chapter=str(edge_data.get("source_chapter", "")).strip(),
                    ),
                }
                source_item.update(self.fallback_engine._edge_evidence_payload(edge_data))  # noqa: SLF001
            else:
                source_book = str(segment.get("source_book", "")).strip()
                source_item = {
                    "source_book": source_book,
                    "source_chapter": normalize_source_chapter_label(
                        source_book=source_book,
                        source_chapter=str(segment.get("source_chapter", "")).strip(),
                    ),
                }
                source_item.update(self._evidence_payload_from_row(segment))
            if reverse:
                predicate = f"{predicate}(逆向)"
            edges.append(predicate)
            if source_item not in sources:
                sources.append(source_item)
        if len(nodes) < 2 or len(edges) != len(nodes) - 1:
            return None
        hop_count = len(nodes) - 1
        score = round(1.0 / max(hop_count, 1) + min(len(sources), 3) * 0.05, 4)
        return {"nodes": nodes, "edges": edges, "score": score, "sources": sources}

    def _extract_nebula_path_skeleton(self, row: dict[str, Any]) -> dict[str, Any] | None:
        segments = row.get("p")
        if not isinstance(segments, list) or len(segments) < 3:
            return None
        node_vids: list[str] = []
        edge_refs: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                return None
            if index % 2 == 0:
                vid = str(segment.get("vid", "")).strip()
                if not vid:
                    return None
                node_vids.append(vid)
            else:
                src = str(segment.get("src", "")).strip()
                dst = str(segment.get("dst", "")).strip()
                ranking = segment.get("ranking")
                edge_type = int(segment.get("edge_type", 0) or 0)
                if not src or not dst or ranking in (None, ""):
                    return None
                if edge_type < 0:
                    src, dst = dst, src
                edge_refs.append({"src": src, "dst": dst, "ranking": int(ranking)})
        if len(edge_refs) != len(node_vids) - 1:
            return None
        return {"node_vids": node_vids, "edge_refs": edge_refs}

    def _build_payload_from_nebula_skeleton(
        self,
        skeleton: dict[str, Any],
        *,
        vertex_map: dict[str, dict[str, Any]],
        edge_map: dict[tuple[str, str, int], dict[str, Any]],
    ) -> dict[str, Any] | None:
        node_vids = list(skeleton.get("node_vids", []))
        edge_refs = list(skeleton.get("edge_refs", []))
        if not node_vids or len(edge_refs) != len(node_vids) - 1:
            return None
        nodes: list[str] = []
        edges: list[str] = []
        sources: list[dict[str, Any]] = []
        for vid in node_vids:
            vertex = vertex_map.get(vid, {})
            name = str(vertex.get("name", "")).strip()
            if not name:
                return None
            nodes.append(name)
        for index, ref in enumerate(edge_refs):
            src = str(ref.get("src", "")).strip()
            dst = str(ref.get("dst", "")).strip()
            ranking = int(ref.get("ranking", 0) or 0)
            edge_data = edge_map.get((src, dst, ranking))
            reverse = False
            if edge_data is None:
                edge_data = edge_map.get((dst, src, ranking))
                reverse = edge_data is not None
            if edge_data is None:
                return None
            predicate = _normalize_relation_name(str(edge_data.get("predicate", "相关")).strip() or "相关")
            if reverse:
                predicate = f"{predicate}(逆向)"
            edges.append(predicate)
            source_book = str(edge_data.get("source_book", "")).strip()
            source_item: dict[str, Any] = {
                "source_book": source_book,
                "source_chapter": normalize_source_chapter_label(
                    source_book=source_book,
                    source_chapter=str(edge_data.get("source_chapter", "")).strip(),
                ),
            }
            source_item.update(
                {
                    "fact_id": str(edge_data.get("fact_id", "")).strip(),
                    "fact_ids": list(edge_data.get("fact_ids", [])),
                    "source_text": str(edge_data.get("source_text", "")).strip(),
                    "confidence": float(edge_data.get("confidence", 0.0) or 0.0),
                }
            )
            if source_item not in sources:
                sources.append(source_item)
        hop_count = len(nodes) - 1
        score = round(1.0 / max(hop_count, 1) + min(len(sources), 3) * 0.05, 4)
        return {"nodes": nodes, "edges": edges, "score": score, "sources": sources}

    def _collect_nebula_relations(self, entity_name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self._primary_batch_neighbors([entity_name], reverse=False, limit_per_entity=256):
            rows.append(
                {
                    "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                    "target": str(row.get("neighbor_name", "")).strip(),
                    "target_type": str(row.get("neighbor_type", "")).strip() or "other",
                    "direction": "out",
                    "source_book": str(row.get("source_book", "")).strip(),
                    "source_chapter": str(row.get("source_chapter", "")).strip(),
                    **self._evidence_payload_from_row(row),
                }
            )
        for row in self._primary_batch_neighbors([entity_name], reverse=True, limit_per_entity=256):
            rows.append(
                {
                    "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                    "target": str(row.get("neighbor_name", "")).strip(),
                    "target_type": str(row.get("neighbor_type", "")).strip() or "other",
                    "direction": "in",
                    "source_book": str(row.get("source_book", "")).strip(),
                    "source_chapter": str(row.get("source_chapter", "")).strip(),
                    **self._evidence_payload_from_row(row),
                }
            )
        return rows

    def _adjacent_names(self, entity_name: str) -> list[str]:
        names: set[str] = set()
        for row in self._primary_batch_neighbors([entity_name], reverse=False, limit_per_entity=128):
            name = str(row.get("neighbor_name", "")).strip()
            if name:
                names.add(name)
        for row in self._primary_batch_neighbors([entity_name], reverse=True, limit_per_entity=128):
            name = str(row.get("neighbor_name", "")).strip()
            if name:
                names.add(name)
        return sorted(names)

    def _group_nebula_relations_by_source(
        self,
        entity_names: list[str],
        *,
        predicate_allowlist: list[str] | None = None,
        source_books: list[str] | None = None,
        limit_per_entity: int = 256,
        directions: tuple[bool, ...] = (False, True),
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in entity_names}
        source_vid_to_name = self._source_vid_name_map(entity_names)
        for reverse in directions:
            rows = self._primary_batch_neighbors(
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
                        **self._evidence_payload_from_row(row),
                    }
                )
        return grouped

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
        if hasattr(self.primary_store, "batch_neighbors"):
            return self.primary_store.batch_neighbors(
                entity_names,
                reverse=reverse,
                predicates=predicates,
                target_types=target_types,
                source_books=source_books,
                limit_per_entity=limit_per_entity,
            )
        source_vid_to_name = self._source_vid_name_map(entity_names)
        source_book_set = {str(item).strip() for item in source_books or [] if str(item).strip()}
        target_type_set = {str(item).strip() for item in target_types or [] if str(item).strip()}
        predicate_set = {_normalize_relation_name(str(item).strip()) for item in predicates or [] if str(item).strip()}
        rows: list[dict[str, Any]] = []
        for name in entity_names:
            source_vid = self._primary_vid(name)
            count = 0
            for row in self.primary_store.neighbors(name, reverse=reverse):
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

    def _source_vid_name_map(self, entity_names: list[str]) -> dict[str, str]:
        return {self._primary_vid(name): name for name in entity_names if str(name).strip()}

    def _primary_vertex_map(self, entity_names: list[str]) -> dict[str, dict[str, Any]]:
        if hasattr(self.primary_store, "batch_exact_entities"):
            return self.primary_store.batch_exact_entities(entity_names)
        if hasattr(self.primary_store, "fetch_vertices_by_vids"):
            vertex_map = self.primary_store.fetch_vertices_by_vids([self._primary_vid(name) for name in entity_names if str(name).strip()])
            return {
                str(item.get("name", "")).strip(): item
                for item in vertex_map.values()
                if str(item.get("name", "")).strip()
            }
        result: dict[str, dict[str, Any]] = {}
        for name in entity_names:
            rows = self.primary_store.exact_entity(name)
            if rows:
                result[name] = rows[0]
        return result

    def _primary_vid(self, entity_name: str) -> str:
        max_length = getattr(getattr(self.primary_store, "settings", None), "vid_max_length", 64)
        return entity_vid(entity_name, max_length=max_length)

    def _resolve_entities_via_primary(
        self,
        query: str,
        preferred_types: set[str] | None = None,
        *,
        exact_only: bool = False,
    ) -> list[str]:
        normalized = str(query or "").strip()
        if not normalized or not self._use_primary():
            return []
        candidates: list[str] = []
        seen: set[str] = set()
        exact_names: list[str] = []
        try:
            if hasattr(self.primary_store, "exact_entity_names"):
                exact_names = self.primary_store.exact_entity_names(normalized, preferred_types=preferred_types)
            elif hasattr(self.primary_store, "exact_entity"):
                preferred = {str(item).strip() for item in preferred_types or set() if str(item).strip()}
                rows = self.primary_store.exact_entity(normalized)
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
                alias_names = self.primary_store.alias_candidates(exact_names[0], preferred_types=preferred_types, limit=20)
            except Exception:
                alias_names = []
            for item in alias_names:
                text = str(item).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                candidates.append(text)
        return candidates

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
        if not exact_candidates:
            return None
        exact_name = str(exact_candidates[0]).strip()
        grouped_rows = self._group_nebula_relations_by_source(
            [exact_name],
            predicate_allowlist=predicate_allowlist,
            source_books=self._query_source_book_hints(query_text),
            limit_per_entity=limit_per_entity,
            directions=self._entity_lookup_directions(
                query_text=query_text,
                predicate_allowlist=predicate_allowlist,
            ),
        )
        rows = grouped_rows.get(exact_name, [])
        if not rows:
            return None
        entity_type = self.fallback_engine.entity_type(exact_name)
        relations = self.fallback_engine._select_relation_clusters(
            self.fallback_engine._filter_relations(
                self.fallback_engine._annotate_relation_rows(rows, anchor_entity_type=entity_type),  # noqa: SLF001
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

    def _entity_lookup_limit_per_candidate(self, *, query_text: str, predicate_allowlist: list[str] | None) -> int:
        allow = {_normalize_relation_name(item) for item in predicate_allowlist or []}
        if allow == {"使用药材"}:
            return 24
        if allow and allow <= {"功效", "治法"}:
            return 20
        if allow and allow <= {"治疗证候", "治疗疾病", "治疗症状"}:
            return 24
        if self._query_has_source_constraint(query_text):
            return 16
        return 48

    def _entity_lookup_directions(self, *, query_text: str, predicate_allowlist: list[str] | None) -> tuple[bool, ...]:
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
        if self._query_has_source_constraint(query_text):
            return (False,)
        return (False, True)

    def _query_has_source_constraint(self, query_text: str) -> bool:
        fragments = self._query_fragments(query_text)
        if "出处" in query_text or "原文" in query_text or "原句" in query_text:
            return True
        return any(self._query_mentions_source_book(query_text, fragment) for fragment in fragments)

    def _query_source_book_hints(self, query_text: str) -> list[str]:
        fragments = self._query_fragments(query_text)
        hints: list[str] = []
        for fragment in fragments:
            if self.fallback_engine.store.source_book_exists(fragment):  # noqa: SLF001
                if fragment not in hints:
                    hints.append(fragment)
        return hints

    def _query_fragments(self, query_text: str) -> list[str]:
        return self.fallback_engine._query_fragments(query_text)  # noqa: SLF001

    def _query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
        return self.fallback_engine._query_mentions_source_book(query_text, source_book)  # noqa: SLF001

    def _path_query_relation_rows(self, entity_name: str) -> list[dict[str, Any]]:
        return self.fallback_engine._annotate_relation_rows(  # noqa: SLF001
            self._collect_nebula_relations(entity_name),
            anchor_entity_type=self.fallback_engine.entity_type(entity_name),
        )

    def _evidence_payload_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        fact_id = str(row.get("fact_id", "")).strip()
        if fact_id:
            payload["fact_id"] = fact_id
        fact_ids_raw = row.get("fact_ids", "")
        if isinstance(fact_ids_raw, str) and fact_ids_raw.strip():
            try:
                fact_ids = json.loads(fact_ids_raw)
            except json.JSONDecodeError:
                fact_ids = [fact_ids_raw]
            if isinstance(fact_ids, list) and fact_ids:
                payload["fact_ids"] = [str(item) for item in fact_ids if str(item).strip()]
        source_text = str(row.get("source_text", "")).strip()
        if source_text:
            payload["source_text"] = source_text
        confidence = row.get("confidence")
        if confidence not in (None, ""):
            payload["confidence"] = float(confidence)
        return payload


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
