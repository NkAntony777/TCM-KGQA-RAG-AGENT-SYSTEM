from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
        relations = self._compact_relations(
            self._collect_relations(canonical_name, query_text=name),
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

    def _collect_relations(self, entity_name: str, query_text: str = "") -> list[dict[str, Any]]:
        rows = self.store.collect_relations(entity_name)
        rows.sort(
            key=lambda item: (
                -self._relation_score(item, query_text),
                -float(item.get("confidence", 0.0) or 0.0),
                item.get("direction", ""),
                item.get("predicate", ""),
                item.get("target", ""),
            )
        )
        return rows

    def _compact_relations(self, rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (
                str(row.get("predicate", "")).strip(),
                str(row.get("target", "")).strip(),
                str(row.get("direction", "")).strip(),
            )
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = row
                continue
            current_confidence = float(row.get("confidence", 0.0) or 0.0)
            existing_confidence = float(existing.get("confidence", 0.0) or 0.0)
            if current_confidence > existing_confidence:
                deduped[key] = row
        compacted = list(deduped.values())
        compacted.sort(
            key=lambda item: (
                -float(item.get("confidence", 0.0) or 0.0),
                item.get("direction", ""),
                item.get("predicate", ""),
                item.get("target", ""),
            )
        )
        return compacted[:top_k]

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
                relations = self._collect_nebula_relations(canonical_name, query_text=name)[: max(1, top_k)]
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

    def _collect_nebula_relations(self, entity_name: str, query_text: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self.primary_store.neighbors(entity_name, reverse=False):
            rows.append(
                {
                    "predicate": _normalize_relation_name(str(row.get("predicate", "")).strip()),
                    "target": str(row.get("neighbor_name", "")).strip(),
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
                    "direction": "in",
                    "source_book": str(row.get("source_book", "")).strip(),
                    "source_chapter": str(row.get("source_chapter", "")).strip(),
                    **self._evidence_payload_from_row(row),
                }
            )
        rows.sort(
            key=lambda item: (
                -self.fallback_engine._relation_score(item, query_text),
                item["direction"],
                item["predicate"],
                item["target"],
            )
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
