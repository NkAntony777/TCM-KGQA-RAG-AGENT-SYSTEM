from __future__ import annotations

from collections import deque
from typing import Any, Callable

from services.graph_service.relation_governance import LIKELY_DIRTY
from services.graph_service.relation_governance import REVIEW_NEEDED
from services.graph_service.relation_governance import bridge_allowed
from services.graph_service.relation_governance import path_expand_allowed
from services.graph_service.relation_governance import priority_boost as governance_priority_boost
from services.graph_service.relation_utils import PREDICATE_BASE_PRIORITY
from services.graph_service.relation_utils import normalize_relation_name


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


def path_query_predicate_priority(predicate: str) -> float:
    normalized = normalize_relation_name(predicate)
    return (
        float(PREDICATE_BASE_PRIORITY.get(normalized, 0.6))
        + float(PATH_QUERY_PREDICATE_BOOST.get(normalized, 0.0))
        + float(governance_priority_boost(normalized))
    )


def ordered_path_neighbors(
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
            path_query_predicate_priority(predicate),
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


def search_ranked_paths(
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
            neighbors = ordered_path_neighbors(_cached_relation_rows(node), target_set=target_set)
            ordered_neighbor_cache[cache_key] = neighbors
        return neighbors

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
