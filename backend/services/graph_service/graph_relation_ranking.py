from __future__ import annotations

import math
from collections import Counter
from typing import Any

from services.common.evidence_payloads import normalize_source_chapter_label
from services.graph_service.relation_governance import ACCEPTABLE_POLYSEMY
from services.graph_service.relation_governance import hinted_predicates as governance_hinted_predicates
from services.graph_service.relation_governance import LIKELY_DIRTY
from services.graph_service.relation_governance import priority_boost as governance_priority_boost
from services.graph_service.relation_governance import relation_metadata
from services.graph_service.relation_governance import REVIEW_NEEDED
from services.graph_service.relation_utils import normalize_relation_name as _normalize_relation_name
from services.graph_service.relation_utils import PREDICATE_BASE_PRIORITY


RRF_RANK_CONSTANT = 20


def select_relation_clusters(engine, rows: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
    clusters = build_relation_clusters(rows)
    if not clusters:
        return []
    apply_rrf_scores(engine, clusters, query_text=query_text)
    return diversify_relation_clusters(engine, clusters, query_text=query_text, top_k=top_k)


def build_relation_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        predicate = _normalize_relation_name(str(row.get("predicate", "")).strip())
        target = str(row.get("target", "")).strip()
        direction = str(row.get("direction", "")).strip()
        if not predicate or not target or not direction:
            continue
        key = (predicate, target, direction)
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


def apply_rrf_scores(engine, clusters: list[dict[str, Any]], *, query_text: str) -> None:
    rank_views = [
        sorted(
            clusters,
            key=lambda item: (
                -relation_score(engine, item, query_text),
                -predicate_priority(item),
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
                -predicate_priority(item),
                -relation_score(engine, item, query_text),
                -int(item.get("source_book_count", 0) or 0),
                -float(item.get("max_confidence", 0.0) or 0.0),
            ),
        ),
    ]
    if any(engine._source_book_match_score(item, query_text) > 0 for item in clusters):
        rank_views.append(
            sorted(
                clusters,
                key=lambda item: (
                    -engine._source_book_match_score(item, query_text),
                    -relation_score(engine, item, query_text),
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


def diversify_relation_clusters(engine, clusters: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
    hinted = hinted_predicates(query_text)
    diversity_lambda = 0.18 if hinted else 0.42
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
            if hinted:
                if predicate in hinted:
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


def predicate_priority(relation: dict[str, Any]) -> float:
    predicate = _normalize_relation_name(str(relation.get("predicate", "")).strip())
    return float(PREDICATE_BASE_PRIORITY.get(predicate, 0.6)) + float(governance_priority_boost(predicate))


def hinted_predicates(query_text: str) -> set[str]:
    return {_normalize_relation_name(item) for item in governance_hinted_predicates(query_text)}


def relation_score(engine, relation: dict[str, Any], query_text: str) -> int:
    score = 0
    predicate = str(relation.get("predicate", "")).strip()
    target = str(relation.get("target", "")).strip()
    source_text = str(relation.get("source_text", "")).strip()
    source_chapter = str(relation.get("source_chapter", "")).strip()
    predicate_family = str(relation.get("predicate_family", "")).strip()
    normalized_predicate = str(relation.get("normalized_predicate", "")).strip()
    normalized_query = (query_text or "").strip()
    query_fragments = engine._query_fragments(normalized_query)
    hinted = hinted_predicates(normalized_query)
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
    score += engine._source_book_match_score(relation, normalized_query) * 80
    if source_chapter and source_chapter in normalized_query:
        score += 10
    score += int(round(predicate_priority(relation) * 10))
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
