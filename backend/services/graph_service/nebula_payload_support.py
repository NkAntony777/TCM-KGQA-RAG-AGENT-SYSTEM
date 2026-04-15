from __future__ import annotations

import json
from typing import Any

from services.common.evidence_payloads import normalize_source_chapter_label
from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name


def evidence_payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
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


def extract_nebula_path_skeleton(row: dict[str, Any]) -> dict[str, Any] | None:
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


def build_payload_from_nebula_path_row(
    row: dict[str, Any],
    *,
    fallback_engine,
) -> dict[str, Any] | None:
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
        edge_data = fallback_engine.store.first_edge_between(left, right)
        if not edge_data:
            edge_data = fallback_engine.store.first_edge_between(right, left)
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
            source_item.update(fallback_engine._edge_evidence_payload(edge_data))
        else:
            source_book = str(segment.get("source_book", "")).strip()
            source_item = {
                "source_book": source_book,
                "source_chapter": normalize_source_chapter_label(
                    source_book=source_book,
                    source_chapter=str(segment.get("source_chapter", "")).strip(),
                ),
            }
            source_item.update(evidence_payload_from_row(segment))
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


def build_payload_from_nebula_skeleton(
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
    for ref in edge_refs:
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
