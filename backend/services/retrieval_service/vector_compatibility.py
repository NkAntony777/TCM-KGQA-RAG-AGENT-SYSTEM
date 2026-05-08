from __future__ import annotations

from collections import defaultdict
from typing import Any


def maybe_fuse_files_first_with_vector(
    *,
    settings: Any,
    files_first_store: Any,
    milvus: Any,
    local_store: Any,
    embedding_client: Any,
    query: str,
    query_context: dict[str, Any] | None,
    docs: list[dict[str, Any]],
    top_k: int,
    candidate_k: int,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], str | None]:
    if not docs or not settings.vector_compatibility_enabled or not embedding_client.is_ready():
        return docs, None
    if not _should_apply_files_first_vector_fusion(
        query=query,
        query_context=query_context,
        docs=docs,
        top_k=top_k,
    ):
        return docs, None

    try:
        dense_vector = embedding_client.embed(
            [str((query_context or {}).get("expanded_query", "")).strip() or query],
            settings.embedding_model,
        )[0]
        candidate_limit = max(candidate_k, top_k) * 2
        if milvus.has_collection():
            vector_hits = milvus.dense_search(
                dense_embedding=dense_vector,
                top_k=candidate_limit,
                candidate_k=candidate_limit,
                leaf_level=settings.leaf_retrieve_level,
            )
        else:
            vector_hits, _vector_mode = local_store.search(
                dense_embedding=dense_vector,
                sparse_embedding={},
                top_k=candidate_limit,
                candidate_k=candidate_limit,
                leaf_level=settings.leaf_retrieve_level,
            )
        hydrated = files_first_store.get_docs_by_chunk_ids(
            [str(item.get("chunk_id", "")).strip() for item in vector_hits if str(item.get("chunk_id", "")).strip()]
        )
        if not hydrated:
            return docs, None
        fused_docs = merge_files_first_with_vector_candidates(
            files_first_docs=docs,
            vector_docs=hydrated,
            top_k=max(top_k, candidate_k),
        )
        warnings.append("files_first_vector_fusion_applied")
        return fused_docs, "files_first_vector_fused"
    except Exception as exc:
        warnings.append(f"files_first_vector_fusion_failed:{exc}")
        return docs, None


def _should_apply_files_first_vector_fusion(
    *,
    query: str,
    query_context: dict[str, Any] | None,
    docs: list[dict[str, Any]],
    top_k: int,
) -> bool:
    if not docs:
        return False
    if bool((query_context or {}).get("weak_anchor", False)):
        return True
    if bool((query_context or {}).get("need_broad_recall", False)):
        return True
    text = str(query or "")
    if any(marker in text for marker in ("出处", "哪本书", "哪部书", "哪一篇", "记载出自")):
        return True
    if len(docs) < max(3, top_k):
        return True
    unique_chapters = {str(item.get("chapter_title", "")).strip() for item in docs if str(item.get("chapter_title", "")).strip()}
    return len(unique_chapters) <= 1


def merge_files_first_with_vector_candidates(
    *,
    files_first_docs: list[dict[str, Any]],
    vector_docs: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    section_best: dict[str, dict[str, Any]] = {}
    rrf_scores: defaultdict[str, float] = defaultdict(float)

    def add_rank(rows: list[dict[str, Any]], *, weight: float) -> None:
        for rank, row in enumerate(rows, start=1):
            section_key = str(row.get("section_key") or row.get("chunk_id") or "").strip()
            if not section_key:
                continue
            rrf_scores[section_key] += weight / (40 + rank)
            existing = section_best.get(section_key)
            if existing is None:
                section_best[section_key] = dict(row)
                continue
            existing_score = float(existing.get("score", 0.0) or 0.0)
            current_score = float(row.get("score", 0.0) or 0.0)
            if current_score > existing_score:
                section_best[section_key] = dict(row)

    add_rank(files_first_docs, weight=1.35)
    add_rank(vector_docs, weight=1.0)

    ranked_sections = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)[: max(1, top_k)]
    results: list[dict[str, Any]] = []
    for index, (section_key, score) in enumerate(ranked_sections, start=1):
        row = dict(section_best[section_key])
        row["score"] = float(row.get("score", 0.0) or 0.0) + score
        row["rrf_rank"] = index
        results.append(row)
    return results
