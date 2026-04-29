from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services.graph_service.engine import get_graph_engine

router = APIRouter()


TYPE_LABELS = {
    "formula": "方剂",
    "herb": "药材",
    "syndrome": "证候",
    "symptom": "症状",
    "disease": "疾病",
    "therapy": "治法",
    "book": "古籍",
    "chapter": "章节",
    "property": "药性",
    "channel": "经络",
    "food": "食物",
    "category": "范畴",
    "medicine": "药物",
    "processing_method": "用法",
    "other": "其他",
}

SCHEMA_NODES = [
    ("formula", "方剂"),
    ("herb", "药材"),
    ("syndrome", "证候"),
    ("symptom", "症状"),
    ("disease", "疾病"),
    ("therapy", "治法"),
    ("book", "古籍"),
    ("property", "药性"),
    ("channel", "经络"),
    ("category", "范畴"),
    ("food", "食物"),
]

SCHEMA_EDGES = [
    ("formula", "herb", "使用药材"),
    ("formula", "syndrome", "治疗证候"),
    ("formula", "symptom", "治疗症状"),
    ("formula", "disease", "治疗疾病"),
    ("syndrome", "formula", "推荐方剂"),
    ("disease", "formula", "推荐方剂"),
    ("herb", "channel", "归经"),
    ("herb", "property", "药性/五味"),
    ("formula", "therapy", "功效/治法"),
    ("formula", "category", "属于范畴"),
    ("herb", "food", "食忌"),
    ("book", "formula", "记载/证据来源"),
]


def _active_graph_engine() -> Any:
    return get_graph_engine()


def _primary_graph_ready(engine: Any) -> bool:
    try:
        return bool(hasattr(engine, "_use_primary") and engine._use_primary())
    except Exception:
        return False


def _graph_backend(engine: Any) -> str:
    try:
        health = engine.health()
        return str(health.get("backend") or health.get("active_backend") or engine.__class__.__name__)
    except Exception:
        return engine.__class__.__name__


def _graph_stats(engine: Any) -> dict[str, Any]:
    try:
        health = engine.health()
    except Exception:
        return {}
    fallback = health.get("fallback") if isinstance(health.get("fallback"), dict) else {}
    return {
        "graph_backend": str(health.get("backend") or health.get("active_backend") or engine.__class__.__name__),
        "graph_node_count": health.get("node_count") or fallback.get("node_count"),
        "graph_edge_count": health.get("edge_count") or fallback.get("edge_count"),
        "graph_evidence_count": health.get("evidence_count") or fallback.get("evidence_count"),
    }


def _normalize_type(value: Any) -> str:
    raw = str(value or "other").strip() or "other"
    return raw if raw in TYPE_LABELS else "other"


def _node(node_id: str, label: str, node_type: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "type": _normalize_type(node_type),
        "type_label": TYPE_LABELS.get(_normalize_type(node_type), "其他"),
        **extra,
    }


def _edge(source: str, target: str, predicate: str, **extra: Any) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "predicate": str(predicate or "关联"),
        **extra,
    }


def _relation_to_graph_items(center: str, relation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    target = str(relation.get("target", "")).strip()
    if not target:
        return None
    target_type = _normalize_type(relation.get("target_type"))
    direction = str(relation.get("direction", "out") or "out")
    predicate = str(relation.get("predicate", "关联") or "关联")
    node = _node(
        target,
        target,
        target_type,
        evidence_count=int(relation.get("evidence_count", 1) or 1),
        source_count=int(relation.get("source_book_count", 0) or 0),
        score=relation.get("score"),
    )
    if direction == "in":
        graph_edge = _edge(
            target,
            center,
            predicate,
            evidence_count=int(relation.get("evidence_count", 1) or 1),
            source_books=relation.get("source_books") or [],
            source_text=relation.get("source_text") or "",
            confidence=relation.get("confidence"),
            reverse=True,
        )
    else:
        graph_edge = _edge(
            center,
            target,
            predicate,
            evidence_count=int(relation.get("evidence_count", 1) or 1),
            source_books=relation.get("source_books") or [],
            source_text=relation.get("source_text") or "",
            confidence=relation.get("confidence"),
            reverse=False,
        )
    return node, graph_edge


def _batched_second_hop_relations(engine: Any, anchors: list[str], *, limit_per_entity: int) -> dict[str, list[dict[str, Any]]] | None:
    if not anchors or not _primary_graph_ready(engine) or not hasattr(engine, "_group_nebula_relations_by_source"):
        return None
    try:
        # Nebula GO FROM <many vids> LIMIT is not guaranteed to be balanced per VID.
        # Query each first-hop anchor separately so one high-degree node cannot consume the whole 2-hop budget.
        grouped: dict[str, list[dict[str, Any]]] = {anchor: [] for anchor in anchors}
        for anchor in anchors:
            rows = engine._group_nebula_relations_by_source(
                [anchor],
                limit_per_entity=max(1, limit_per_entity),
                directions=(False, True),
            )
            grouped[anchor] = rows.get(anchor, [])
        return grouped
    except Exception:
        return None


@router.get("/graph/schema-summary")
async def graph_schema_summary() -> dict[str, Any]:
    nodes = [_node(node_id, label, node_id, is_schema=True) for node_id, label in SCHEMA_NODES]
    edges = [_edge(source, target, predicate, is_schema=True) for source, target, predicate in SCHEMA_EDGES]
    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "kind": "schema",
            "depth": 0,
            "truncated": False,
            "note": "类型层面的图谱结构摘要，不展示全量实例节点。",
        },
    }


@router.get("/graph/subgraph")
async def graph_subgraph(
    entity: str = Query(..., min_length=1),
    depth: int = Query(default=2, ge=1, le=2),
    limit: int = Query(default=120, ge=8, le=200),
) -> dict[str, Any]:
    engine = _active_graph_engine()
    if depth >= 2:
        # Keep room for second-hop expansion; otherwise first-hop lookup fills the whole limit.
        top_k = min(max(24, limit // 2), 80)
    else:
        top_k = min(limit - 1, 48)
    lookup = engine.entity_lookup(entity, top_k=top_k)
    entity_info = lookup.get("entity") or {}
    center = str(entity_info.get("canonical_name") or entity).strip()
    center_type = _normalize_type(entity_info.get("entity_type"))

    nodes: dict[str, dict[str, Any]] = {
        center: _node(center, center, center_type, is_center=True, evidence_count=0, source_count=0),
    }
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    relations = list(lookup.get("relations") or [])
    for relation in relations:
        converted = _relation_to_graph_items(center, relation)
        if not converted:
            continue
        node, edge = converted
        nodes.setdefault(node["id"], node)
        key = (edge["source"], edge["target"], edge["predicate"])
        edges.setdefault(key, edge)
        if len(nodes) >= limit:
            break

    if depth >= 2 and len(nodes) < limit:
        # Prefer Nebula's batched neighbor expansion for interactive visualization.
        first_hop = [node_id for node_id in list(nodes.keys()) if node_id != center][: min(24, max(8, limit // 5))]
        second_hop_budget = max(1, limit - len(nodes))
        limit_per_entity = max(2, min(8, (second_hop_budget // max(1, len(first_hop))) + 1))
        batched_relations = _batched_second_hop_relations(engine, first_hop, limit_per_entity=limit_per_entity)
        if batched_relations is not None:
            iterable = ((neighbor, batched_relations.get(neighbor, [])) for neighbor in first_hop)
        else:
            iterable = ((neighbor, engine.entity_lookup(neighbor, top_k=4).get("relations") or []) for neighbor in first_hop)

        for neighbor, neighbor_relations in iterable:
            if len(nodes) >= limit:
                break
            for relation in neighbor_relations:
                converted = _relation_to_graph_items(neighbor, relation)
                if not converted:
                    continue
                node, edge = converted
                nodes.setdefault(node["id"], node)
                key = (edge["source"], edge["target"], edge["predicate"])
                edges.setdefault(key, edge)
                if len(nodes) >= limit:
                    break

    node_values = list(nodes.values())[:limit]
    edge_values = list(edges.values())[: max(limit * 2, 24)]
    stats = _graph_stats(engine)
    return {
        "nodes": node_values,
        "edges": edge_values,
        "meta": {
            "kind": "subgraph",
            "center": center,
            "depth": depth,
            "limit": limit,
            "truncated": len(nodes) > len(node_values) or len(edges) > len(edge_values),
            "node_total_before_limit": len(nodes),
            "edge_total_before_limit": len(edges),
            "primary_graph_ready": _primary_graph_ready(engine),
            **stats,
        },
    }
