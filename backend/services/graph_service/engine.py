from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from services.graph_service.nebulagraph_store import NebulaGraphStore


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
FORMULA_RELATIONS = {"推荐方剂"}
FORMULA_TO_SYNDROME_RELATIONS = {"治疗证候"}
FORMULA_TO_SYMPTOM_RELATIONS = {"治疗症状", "常见症状"}

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


def load_settings() -> GraphServiceSettings:
    backend_dir = Path(__file__).resolve().parents[2]
    return GraphServiceSettings(
        backend_dir=backend_dir,
        sample_graph_path=backend_dir / "services" / "graph_service" / "data" / "sample_graph.json",
        runtime_graph_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.json",
        runtime_evidence_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.evidence.jsonl",
    )


class GraphQueryEngine:
    def __init__(self, settings: GraphServiceSettings | None = None):
        self.settings = settings or load_settings()
        self.graph = nx.MultiDiGraph()
        self.loaded_graph_path = self.settings.sample_graph_path
        self.loaded_evidence_path: Path | None = None
        self.loaded_evidence_paths: list[Path] = []
        self.runtime_graph_loaded = False
        self.seed_graph_loaded = False
        self.evidence_by_fact_id: dict[str, dict[str, Any]] = {}
        self._load_graphs()

    def _load_graphs(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.runtime_graph_loaded = False
        self.seed_graph_loaded = False

        evidence_paths: list[Path] = []
        if self.settings.sample_evidence_path and self.settings.sample_evidence_path.exists():
            evidence_paths.append(self.settings.sample_evidence_path)
        if self.settings.runtime_evidence_path and self.settings.runtime_evidence_path.exists():
            evidence_paths.append(self.settings.runtime_evidence_path)

        self.loaded_evidence_paths = evidence_paths
        self.loaded_evidence_path = evidence_paths[-1] if evidence_paths else None
        self.evidence_by_fact_id = self._load_evidence_map(evidence_paths)

        if self.settings.sample_graph_path.exists():
            self._load_graph_file(self.settings.sample_graph_path)
            self.seed_graph_loaded = True
            self.loaded_graph_path = self.settings.sample_graph_path

        if self.settings.runtime_graph_path.exists():
            self._load_graph_file(self.settings.runtime_graph_path)
            self.runtime_graph_loaded = True
            self.loaded_graph_path = self.settings.runtime_graph_path

        if not self.seed_graph_loaded and not self.runtime_graph_loaded:
            raise ValueError("no_graph_data_available")

    def _load_graph_file(self, graph_path: Path) -> None:
        payload = json.loads(graph_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("invalid_sample_graph")

        seen_edges: set[tuple[str, str, str, str, str, tuple[str, ...]]] = set()
        for source, target, edge_data in self.graph.edges(data=True):
            seen_edges.add(
                (
                    str(source),
                    str(edge_data.get("relation", "")),
                    str(target),
                    str(edge_data.get("source_book", "")),
                    str(edge_data.get("source_chapter", "")),
                    tuple(self._extract_fact_ids(edge_data)),
                )
            )

        for row in payload:
            if not isinstance(row, dict):
                continue
            subject = str(row.get("subject", "")).strip()
            predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
            obj = str(row.get("object", "")).strip()
            if not subject or not predicate or not obj:
                continue

            subject_type = str(row.get("subject_type", "entity")).strip() or "entity"
            object_type = str(row.get("object_type", "entity")).strip() or "entity"
            source_book = str(row.get("source_book", "")).strip()
            source_chapter = str(row.get("source_chapter", "")).strip()
            fact_ids = self._extract_fact_ids(row)

            self._upsert_node(subject, subject_type)
            self._upsert_node(obj, object_type)

            edge_signature = (
                subject,
                predicate,
                obj,
                source_book,
                source_chapter,
                tuple(fact_ids),
            )
            if edge_signature in seen_edges:
                continue
            seen_edges.add(edge_signature)

            self.graph.add_edge(
                subject,
                obj,
                relation=predicate,
                source_book=source_book,
                source_chapter=source_chapter,
                fact_ids=fact_ids,
            )

    def _upsert_node(self, node_name: str, entity_type: str) -> None:
        if not self.graph.has_node(node_name):
            self.graph.add_node(node_name, entity_type=entity_type)
            return

        current_type = str(self.graph.nodes[node_name].get("entity_type", "entity")).strip() or "entity"
        if current_type == "entity" and entity_type != "entity":
            self.graph.nodes[node_name]["entity_type"] = entity_type

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": "networkx_runtime_graph" if self.loaded_graph_path == self.settings.runtime_graph_path else "networkx_small_graph",
            "version": "v3",
            "graph_loaded": True,
            "graph_path": str(self.loaded_graph_path),
            "evidence_path": str(self.loaded_evidence_path) if self.loaded_evidence_path else "",
            "evidence_paths": [str(path) for path in self.loaded_evidence_paths],
            "evidence_count": len(self.evidence_by_fact_id),
            "seed_graph_loaded": self.seed_graph_loaded,
            "runtime_graph_loaded": self.runtime_graph_loaded,
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
        }

    def entity_lookup(self, name: str, top_k: int = 20) -> dict[str, Any]:
        candidates = self._resolve_entities(name)
        if not candidates:
            return {}

        canonical_name = candidates[0]
        entity_type = str(self.graph.nodes[canonical_name].get("entity_type", "entity"))
        relations = self._collect_relations(canonical_name, query_text=name)[: max(1, top_k)]
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

        undirected = self.graph.to_undirected()
        paths: list[dict[str, Any]] = []
        seen = set()

        for start_node in start_candidates[:3]:
            for end_node in end_candidates[:3]:
                if start_node == end_node:
                    continue
                try:
                    candidate_paths = nx.all_simple_paths(
                        undirected,
                        source=start_node,
                        target=end_node,
                        cutoff=max_hops,
                    )
                except (nx.NetworkXError, nx.NodeNotFound):
                    continue

                for raw_path in candidate_paths:
                    if len(raw_path) < 2:
                        continue
                    signature = tuple(raw_path)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    path = self._build_path_payload(raw_path)
                    if path:
                        paths.append(path)
                    if len(paths) >= path_limit:
                        break
                if len(paths) >= path_limit:
                    break
            if len(paths) >= path_limit:
                break

        paths.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return {"paths": paths[:path_limit], "total": len(paths[:path_limit])}

    def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
        symptom_candidates = self._resolve_entities(symptom, preferred_types={"symptom"})
        if not symptom_candidates:
            symptom_candidates = self._resolve_entities(symptom)
        if not symptom_candidates:
            return {"symptom": symptom.strip(), "syndromes": []}

        scored: list[dict[str, Any]] = []
        for symptom_node in symptom_candidates[:5]:
            syndrome_scores: dict[str, dict[str, Any]] = {}

            for syndrome_node, _, edge_data in self.graph.in_edges(symptom_node, data=True):
                if self.graph.nodes[syndrome_node].get("entity_type") != "syndrome":
                    continue
                relation = _normalize_relation_name(str(edge_data.get("relation", "")))
                if relation not in SYMPTOM_RELATIONS:
                    continue
                score = 0.92 if symptom_node == symptom.strip() else 0.82
                evidence = self._edge_evidence_payload(edge_data)
                existing = syndrome_scores.get(syndrome_node)
                if existing is None or score > float(existing.get("score", 0.0)):
                    syndrome_scores[syndrome_node] = {
                        "score": score,
                        "evidence": evidence,
                    }

            for syndrome_node, syndrome_meta in syndrome_scores.items():
                formulas = self._collect_recommended_formulas(syndrome_node)
                item = {
                    "name": syndrome_node,
                    "score": round(float(syndrome_meta.get("score", 0.0)), 4),
                    "recommended_formulas": sorted(set(formulas)),
                }
                evidence = syndrome_meta.get("evidence")
                if isinstance(evidence, dict):
                    item.update(evidence)
                scored.append(item)

        deduped: dict[str, dict[str, Any]] = {}
        for item in scored:
            key = item["name"]
            existing = deduped.get(key)
            if existing is None or item["score"] > existing["score"]:
                deduped[key] = item

        results = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)[: max(1, top_k)]
        return {"symptom": symptom.strip(), "syndromes": results}

    def _resolve_entities(self, query: str, preferred_types: set[str] | None = None) -> list[str]:
        normalized = (query or "").strip()
        if not normalized:
            return []

        exact: list[str] = []
        contains: list[str] = []
        for node, attrs in self.graph.nodes(data=True):
            node_name = str(node)
            node_type = str(attrs.get("entity_type", "entity"))
            if preferred_types and node_type not in preferred_types:
                continue
            if normalized == node_name:
                exact.append(node_name)
            elif normalized in node_name or node_name in normalized:
                contains.append(node_name)

        ranked = exact + sorted(contains, key=lambda item: (len(item), item))
        return ranked

    def _collect_relations(self, entity_name: str, query_text: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for _, target, edge_data in self.graph.out_edges(entity_name, data=True):
            rows.append(
                {
                    "predicate": _normalize_relation_name(str(edge_data.get("relation", ""))),
                    "target": target,
                    "direction": "out",
                    "source_book": str(edge_data.get("source_book", "")),
                    "source_chapter": str(edge_data.get("source_chapter", "")),
                    **self._edge_evidence_payload(edge_data),
                }
            )

        for source, _, edge_data in self.graph.in_edges(entity_name, data=True):
            rows.append(
                {
                    "predicate": _normalize_relation_name(str(edge_data.get("relation", ""))),
                    "target": source,
                    "direction": "in",
                    "source_book": str(edge_data.get("source_book", "")),
                    "source_chapter": str(edge_data.get("source_chapter", "")),
                    **self._edge_evidence_payload(edge_data),
                }
            )

        rows.sort(
            key=lambda item: (
                -self._relation_score(item, query_text),
                item["direction"],
                item["predicate"],
                item["target"],
            )
        )
        return rows

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

    def _build_path_payload(self, nodes: list[str]) -> dict[str, Any] | None:
        edges: list[str] = []
        sources: list[dict[str, Any]] = []

        for left, right in zip(nodes, nodes[1:]):
            edge_data = self._first_edge_payload(left, right)
            reverse = False
            if edge_data is None:
                edge_data = self._first_edge_payload(right, left)
                reverse = True
            if edge_data is None:
                return None

            relation = _normalize_relation_name(str(edge_data.get("relation", "相关")))
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
        return {
            "nodes": nodes,
            "edges": edges,
            "score": score,
            "sources": sources,
        }

    def _first_edge_payload(self, source: str, target: str) -> dict[str, Any] | None:
        payload = self.graph.get_edge_data(source, target)
        if not payload:
            return None
        first_key = next(iter(payload))
        return payload[first_key]

    def _extract_fact_ids(self, row: dict[str, Any]) -> list[str]:
        fact_ids: list[str] = []
        raw_fact_ids = row.get("fact_ids")
        if isinstance(raw_fact_ids, list):
            for item in raw_fact_ids:
                value = str(item).strip()
                if value and value not in fact_ids:
                    fact_ids.append(value)

        raw_fact_id = str(row.get("fact_id", "")).strip()
        if raw_fact_id and raw_fact_id not in fact_ids:
            fact_ids.append(raw_fact_id)
        return fact_ids

    def _load_evidence_map(self, path: Path | None) -> dict[str, dict[str, Any]]:
        evidence_map: dict[str, dict[str, Any]] = {}
        paths: list[Path] = []
        if isinstance(path, Path):
            paths = [path]
        elif isinstance(path, list):
            paths = [item for item in path if isinstance(item, Path)]

        for evidence_path in paths:
            if not evidence_path.exists():
                continue
            with evidence_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        continue
                    fact_id = str(row.get("fact_id", "")).strip()
                    if not fact_id:
                        continue
                    evidence_map[fact_id] = {
                        "fact_id": fact_id,
                        "source_book": str(row.get("source_book", "")).strip(),
                        "source_chapter": str(row.get("source_chapter", "")).strip(),
                        "source_text": str(row.get("source_text", "")).strip(),
                        "confidence": float(row.get("confidence", 0.0)),
                    }
        return evidence_map

    def _collect_recommended_formulas(self, syndrome_node: str) -> list[str]:
        formulas: set[str] = set()

        for _, target, edge_data in self.graph.out_edges(syndrome_node, data=True):
            relation = _normalize_relation_name(str(edge_data.get("relation", "")))
            if relation in FORMULA_RELATIONS and self.graph.nodes[target].get("entity_type") == "formula":
                formulas.add(str(target))

        for source, _, edge_data in self.graph.in_edges(syndrome_node, data=True):
            if self.graph.nodes[source].get("entity_type") != "formula":
                continue
            relation = _normalize_relation_name(str(edge_data.get("relation", "")))
            if relation in FORMULA_TO_SYNDROME_RELATIONS:
                formulas.add(str(source))

        return sorted(formulas)

    def _edge_evidence_payload(self, edge_data: dict[str, Any]) -> dict[str, Any]:
        fact_ids = self._extract_fact_ids(edge_data)
        if not fact_ids:
            return {}

        payload: dict[str, Any] = {
            "fact_id": fact_ids[0],
            "fact_ids": fact_ids,
        }
        evidence_items = [
            self.evidence_by_fact_id[fact_id]
            for fact_id in fact_ids
            if fact_id in self.evidence_by_fact_id
        ]
        if not evidence_items:
            return payload

        best = max(evidence_items, key=lambda item: float(item.get("confidence", 0.0)))
        payload.update(
            {
                "fact_id": str(best.get("fact_id", fact_ids[0])),
                "source_text": str(best.get("source_text", "")),
                "confidence": float(best.get("confidence", 0.0)),
            }
        )
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
            "backend": "nebulagraph_primary" if using_primary else fallback.get("backend", "networkx_runtime_graph"),
            "selected_backend": "nebula",
            "active_backend": "nebula" if using_primary else "networkx_fallback",
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
                entity_type = str(self.fallback_engine.graph.nodes[canonical_name].get("entity_type", "entity"))
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

                    neighbors = self._adjacent_names(current_node)
                    for next_node in neighbors:
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
        fact_id = str(row.get("fact_id", "")).strip()
        payload: dict[str, Any] = {}
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
            try:
                payload["confidence"] = float(confidence)
            except (TypeError, ValueError):
                pass
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
