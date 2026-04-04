from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from services.graph_service.nebulagraph_store import NebulaGraphStore
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

RELATION_QUERY_HINTS: dict[str, set[str]] = {
    "功效": {"功效"},
    "归经": {"归经"},
    "药材": {"使用药材"},
    "配伍": {"使用药材"},
    "组成": {"使用药材"},
    "证候": {"治疗证候", "推荐方剂", "常见症状"},
    "辨证": {"治疗证候", "推荐方剂", "常见症状"},
    "症状": {"治疗症状", "常见症状"},
    "治法": {"治法"},
    "疾病": {"治疗疾病"},
    "范畴": {"属于范畴"},
    "类别": {"属于范畴"},
    "别名": {"别名"},
}

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


@dataclass(frozen=True)
class GraphServiceSettings:
    backend_dir: Path
    sample_graph_path: Path
    runtime_graph_path: Path
    sample_evidence_path: Path | None = None
    runtime_evidence_path: Path | None = None
    runtime_db_path: Path | None = None


def load_settings() -> GraphServiceSettings:
    backend_dir = Path(__file__).resolve().parents[2]
    runtime_graph_path = backend_dir / "services" / "graph_service" / "data" / "graph_runtime.json"
    return GraphServiceSettings(
        backend_dir=backend_dir,
        sample_graph_path=backend_dir / "services" / "graph_service" / "data" / "sample_graph.json",
        runtime_graph_path=runtime_graph_path,
        runtime_evidence_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.evidence.jsonl",
        runtime_db_path=runtime_graph_path.with_suffix(".db"),
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
        )

    def health(self) -> dict[str, Any]:
        stats = self.store.stats()
        runtime_triples = int(stats.get("runtime_triples", 0) or 0)
        sample_triples = int(stats.get("sample_triples", 0) or 0)
        if runtime_triples > 0:
            backend = "sqlite_runtime_graph"
        elif sample_triples > 0:
            backend = "sqlite_sample_graph"
        else:
            backend = "sqlite_empty_graph"
        return {
            "status": "ok" if stats["exists"] else "empty",
            "backend": backend,
            "version": "v4",
            "graph_loaded": bool(stats["exists"]),
            "graph_path": str(stats.get("db_path") or self.settings.runtime_db_path or self.settings.runtime_graph_path.with_suffix(".db")),
            "evidence_path": str(self.settings.runtime_evidence_path or ""),
            "evidence_paths": [str(self.settings.runtime_evidence_path)] if self.settings.runtime_evidence_path else [],
            "evidence_count": stats["evidence_count"],
            "seed_graph_loaded": sample_triples > 0,
            "runtime_graph_loaded": runtime_triples > 0,
            "node_count": stats["node_count"],
            "edge_count": stats["total_triples"],
        }

    def entity_lookup(self, name: str, top_k: int = 20) -> dict[str, Any]:
        candidates = self._resolve_entities(name)
        if not candidates:
            return {}
        canonical_name = candidates[0]
        entity_type = self.entity_type(canonical_name)
        relations = self._select_relation_clusters(
            self._collect_relations(canonical_name),
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
        start_candidates = self._resolve_entities(start)
        end_candidates = self._resolve_entities(end)
        if not start_candidates or not end_candidates:
            return {"paths": [], "total": 0}

        target_set = set(end_candidates[:3])
        built_paths: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, ...]] = set()

        for start_node in start_candidates[:3]:
            queue: list[list[str]] = [[start_node]]
            while queue and len(built_paths) < path_limit:
                current_path = queue.pop(0)
                current_node = current_path[-1]
                if len(current_path) - 1 >= max_hops:
                    continue
                for next_node in self._adjacent_names(current_node):
                    if next_node in current_path:
                        continue
                    new_path = current_path + [next_node]
                    signature = tuple(new_path)
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)
                    if next_node in target_set:
                        payload = self._build_path_payload(new_path)
                        if payload:
                            built_paths.append(payload)
                            if len(built_paths) >= path_limit:
                                break
                    if len(new_path) - 1 < max_hops:
                        queue.append(new_path)

        built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}

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

    def _resolve_entities(self, query: str, preferred_types: set[str] | None = None) -> list[str]:
        return self.store.resolve_entities(query, preferred_types, limit=20)

    def _collect_relations(self, entity_name: str) -> list[dict[str, Any]]:
        return self.store.collect_relations(entity_name)

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
            source_chapter = str(row.get("source_chapter", "")).strip()
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
        return float(PREDICATE_BASE_PRIORITY.get(predicate, 0.6))

    def _hinted_predicates(self, query_text: str) -> set[str]:
        hinted: set[str] = set()
        normalized_query = (query_text or "").strip()
        for token, predicates in RELATION_QUERY_HINTS.items():
            if token in normalized_query:
                hinted.update(predicates)
        return hinted

    def _relation_score(self, relation: dict[str, Any], query_text: str) -> int:
        score = 0
        predicate = str(relation.get("predicate", "")).strip()
        target = str(relation.get("target", "")).strip()
        source_text = str(relation.get("source_text", "")).strip()
        normalized_query = (query_text or "").strip()
        for token, preferred_predicates in RELATION_QUERY_HINTS.items():
            if token in normalized_query and predicate in preferred_predicates:
                score += 50
        if predicate and predicate in normalized_query:
            score += 20
        if target and target in normalized_query:
            score += 10
        if source_text and any(fragment and fragment in source_text for fragment in self._query_fragments(normalized_query)):
            score += 5
        score += int(round(self._predicate_priority(relation) * 10))
        score += min(int(relation.get("source_book_count", 0) or 0), 5)
        score += min(int(math.log1p(int(relation.get("evidence_count", 0) or 0)) * 4), 8)
        if relation.get("direction") == "out":
            score += 1
        return score

    def _query_fragments(self, query_text: str) -> list[str]:
        fragments = [
            item.strip(" ，。？?：:（）()")
            for item in query_text.replace("有什么", " ").replace("是什么", " ").replace("有哪些", " ").replace("什么", " ").split()
        ]
        return [item for item in fragments if len(item) >= 2]

    def _adjacent_names(self, entity_name: str) -> list[str]:
        return self.store.adjacent_names(entity_name)

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
            source_item: dict[str, Any] = {
                "source_book": str(edge_data.get("source_book", "")),
                "source_chapter": str(edge_data.get("source_chapter", "")),
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
        using_primary = primary.get("status") == "ok"
        return {
            "status": "ok" if using_primary else fallback.get("status", "ok"),
            "backend": "nebulagraph_primary" if using_primary else fallback.get("backend", "sqlite_runtime_graph"),
            "selected_backend": "nebula",
            "active_backend": "nebula" if using_primary else "sqlite_fallback",
            "primary": primary,
            "fallback": fallback,
            "graph_path": fallback.get("graph_path", ""),
            "evidence_path": fallback.get("evidence_path", ""),
            "evidence_paths": fallback.get("evidence_paths", []),
            "evidence_count": fallback.get("evidence_count", 0),
            "node_count": fallback.get("node_count", 0),
            "edge_count": fallback.get("edge_count", 0),
        }

    def entity_lookup(self, name: str, top_k: int = 20) -> dict[str, Any]:
        if not self._use_primary():
            return self.fallback_engine.entity_lookup(name, top_k=top_k)
        try:
            candidates = self.fallback_engine._resolve_entities(name)
            if not candidates:
                return {}
            for canonical_name in candidates[:5]:
                if not self.primary_store.exact_entity(canonical_name):
                    continue
                relations = self.fallback_engine._select_relation_clusters(
                    self._collect_nebula_relations(canonical_name),
                    query_text=name,
                    top_k=max(1, top_k),
                )
                entity_type = self.fallback_engine.entity_type(canonical_name)
                if not relations and canonical_name != candidates[0]:
                    continue
                return {
                    "entity": {
                        "name": name.strip(),
                        "canonical_name": canonical_name,
                        "entity_type": entity_type,
                    },
                    "relations": relations,
                    "total": len(relations),
                }
        except Exception:
            pass
        return self.fallback_engine.entity_lookup(name, top_k=top_k)

    def path_query(self, start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
        if not self._use_primary():
            return self.fallback_engine.path_query(start, end, max_hops=max_hops, path_limit=path_limit)
        try:
            start_candidates = self.fallback_engine._resolve_entities(start)[:3]
            end_candidates = self.fallback_engine._resolve_entities(end)[:3]
            if not start_candidates or not end_candidates:
                return {"paths": [], "total": 0}

            target_set = set(end_candidates)
            built_paths: list[dict[str, Any]] = []
            seen_signatures: set[tuple[str, ...]] = set()

            for start_node in start_candidates:
                queue: list[list[str]] = [[start_node]]
                while queue and len(built_paths) < path_limit:
                    current_path = queue.pop(0)
                    current_node = current_path[-1]
                    if len(current_path) - 1 >= max_hops:
                        continue
                    for next_node in self._adjacent_names(current_node):
                        if next_node in current_path:
                            continue
                        new_path = current_path + [next_node]
                        signature = tuple(new_path)
                        if signature in seen_signatures:
                            continue
                        seen_signatures.add(signature)
                        if next_node in target_set:
                            payload = self.fallback_engine._build_path_payload(new_path)
                            if payload:
                                built_paths.append(payload)
                                if len(built_paths) >= path_limit:
                                    break
                        if len(new_path) - 1 < max_hops:
                            queue.append(new_path)

            built_paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
            return {"paths": built_paths[:path_limit], "total": len(built_paths[:path_limit])}
        except Exception:
            return self.fallback_engine.path_query(start, end, max_hops=max_hops, path_limit=path_limit)

    def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
        if not self._use_primary():
            return self.fallback_engine.syndrome_chain(symptom, top_k=top_k)
        try:
            symptom_candidates = self.fallback_engine._resolve_entities(symptom, preferred_types={"symptom"})
            if not symptom_candidates:
                symptom_candidates = self.fallback_engine._resolve_entities(symptom)
            if not symptom_candidates:
                return {"symptom": symptom.strip(), "syndromes": []}

            deduped: dict[str, dict[str, Any]] = {}
            for symptom_node in symptom_candidates[:5]:
                for row in self.primary_store.neighbors(symptom_node, reverse=True):
                    syndrome_name = str(row.get("neighbor_name", "")).strip()
                    syndrome_type = str(row.get("neighbor_type", "")).strip()
                    predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
                    if not syndrome_name or syndrome_type != "syndrome" or predicate not in SYMPTOM_RELATIONS:
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
            return self.fallback_engine.syndrome_chain(symptom, top_k=top_k)

    def _use_primary(self) -> bool:
        return self.primary_store.ready()

    def _collect_nebula_relations(self, entity_name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self.primary_store.neighbors(entity_name, reverse=False):
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
        for row in self.primary_store.neighbors(entity_name, reverse=True):
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
        for row in self.primary_store.neighbors(entity_name, reverse=False):
            name = str(row.get("neighbor_name", "")).strip()
            if name:
                names.add(name)
        for row in self.primary_store.neighbors(entity_name, reverse=True):
            name = str(row.get("neighbor_name", "")).strip()
            if name:
                names.add(name)
        return sorted(names)

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
        selected_backend = os.getenv("GRAPH_BACKEND", "nebula").strip().lower()
        fallback_engine = GraphQueryEngine()
        if selected_backend == "nebula":
            _graph_engine = NebulaPrimaryGraphEngine(
                primary_store=NebulaGraphStore(),
                fallback_engine=fallback_engine,
            )
        else:
            _graph_engine = fallback_engine
    return _graph_engine
