from __future__ import annotations

import os
from typing import Any

from services.graph_service.path_search import NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS
from services.graph_service.path_search import NEBULA_PATH_QUERY_AUTO_MIN_HOPS
from services.graph_service.path_search import search_ranked_paths as _search_ranked_paths
from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name


SYMPTOM_RELATIONS = {"常见症状", "表现症状", "相关症状"}
SYNDROME_CHAIN_TARGET_TYPES = {"syndrome", "disease"}


def use_primary(engine) -> bool:
    return engine.primary_store.ready()


def path_query_mode() -> str:
    mode = os.getenv("PATH_QUERY_EXECUTION_MODE", "nebula_first").strip().lower()
    return mode if mode in {"local_first", "nebula_first", "auto"} else "local_first"


def should_prefer_nebula_path(
    engine,
    *,
    max_hops: int,
    start_candidates: list[str],
    end_candidates: list[str],
) -> bool:
    if not use_primary(engine) or not start_candidates or not end_candidates:
        return False
    mode = path_query_mode()
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


def direct_path_query_via_nebula(
    engine,
    *,
    start_candidates: list[str],
    end_candidates: list[str],
    max_hops: int,
    path_limit: int,
) -> dict[str, Any]:
    built_paths: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    rows = engine.primary_store.find_shortest_path_rows(
        start_candidates[:3],
        end_candidates[:3],
        max_hops=max_hops,
        limit=max(1, path_limit * 3),
        with_prop=False,
    )
    skeletons = [engine._extract_nebula_path_skeleton(row) for row in rows]
    skeletons = [item for item in skeletons if item]
    vertex_vids: set[str] = set()
    edge_refs: list[dict[str, Any]] = []
    for skeleton in skeletons:
        vertex_vids.update(skeleton["node_vids"])
        edge_refs.extend(skeleton["edge_refs"])
    vertex_map = engine.primary_store.fetch_vertices_by_vids(sorted(vertex_vids))
    edge_map = engine.primary_store.fetch_edges_by_refs(edge_refs)
    for skeleton in skeletons:
        payload = engine._build_payload_from_nebula_skeleton(
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


def syndrome_chain_via_nebula(engine, symptom: str, *, top_k: int) -> dict[str, Any]:
    symptom_candidates = engine._resolve_entities_via_primary(symptom, preferred_types={"symptom"})
    if not symptom_candidates:
        symptom_candidates = engine.fallback_engine._resolve_entities(symptom, preferred_types={"symptom"})
    if not symptom_candidates:
        symptom_candidates = engine._resolve_entities_via_primary(symptom)
    if not symptom_candidates:
        symptom_candidates = engine.fallback_engine._resolve_entities(symptom)
    if not symptom_candidates:
        return {"symptom": symptom.strip(), "syndromes": []}
    try:
        symptom_names = symptom_candidates[:5]
        raw_rows = engine._primary_batch_neighbors(
            symptom_names,
            reverse=True,
            predicates=list(SYMPTOM_RELATIONS),
            target_types=list(SYNDROME_CHAIN_TARGET_TYPES),
            limit_per_entity=max(8, top_k * 8),
        )
        deduped: dict[str, dict[str, Any]] = {}
        source_vid_to_name = engine._source_vid_name_map(symptom_names)
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
                "recommended_formulas": engine.fallback_engine._collect_recommended_formulas(syndrome_name),
            }
            item.update(engine._evidence_payload_from_row(row))
            existing = deduped.get(syndrome_name)
            if existing is None or float(item["score"]) > float(existing["score"]):
                deduped[syndrome_name] = item

        results = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)[: max(1, top_k)]
        return {"symptom": symptom.strip(), "syndromes": results}
    except Exception:
        return {"symptom": symptom.strip(), "syndromes": []}


def path_query_relation_rows(engine, entity_name: str) -> list[dict[str, Any]]:
    return engine.fallback_engine._annotate_relation_rows(
        engine._collect_nebula_relations(entity_name),
        anchor_entity_type=engine.fallback_engine.entity_type(entity_name),
    )


def fallback_ranked_path_search(
    engine,
    *,
    start_candidates: list[str],
    end_candidates: list[str],
    max_hops: int,
    path_limit: int,
) -> dict[str, Any]:
    return _search_ranked_paths(
        start_candidates=start_candidates,
        target_set=set(end_candidates),
        max_hops=max_hops,
        path_limit=path_limit,
        relation_rows=engine._path_query_relation_rows,
        build_path_payload=engine.fallback_engine._build_path_payload,
    )
