from __future__ import annotations

from typing import Any, Callable

from services.retrieval_service.files_first_support import normalize_chunk


def run_hybrid_search(
    *,
    settings,
    files_first_store,
    milvus,
    local_store,
    lexicon,
    embedding_client,
    query_context,
    query: str,
    top_k: int,
    candidate_k: int,
    enable_rerank: bool,
    allowed_file_path_prefixes: list[str] | None,
    search_mode: str,
    rerank_fn: Callable[[str, list[dict[str, Any]], int], tuple[list[dict[str, Any]], bool, str | None]],
    auto_merge_fn: Callable[[list[dict[str, Any]], int], tuple[list[dict[str, Any]], dict[str, Any]]],
    filter_docs_fn: Callable[[list[dict[str, Any]], list[str] | None], list[dict[str, Any]]],
    lexical_gate_fn: Callable[[str, list[dict[str, Any]], list[str]], list[dict[str, Any]]],
) -> dict[str, Any]:
    warnings: list[str] = []
    sparse_vector = lexicon.encode_query(query)
    normalized_search_mode = (search_mode or "hybrid").strip().lower()
    retrieval_mode = "hybrid"
    docs: list[dict[str, Any]] = []

    if normalized_search_mode == "files_first":
        try:
            docs, retrieval_mode = files_first_store.search(
                query=query,
                query_context=query_context,
                top_k=top_k,
                candidate_k=max(candidate_k, top_k),
                leaf_level=settings.leaf_retrieve_level,
            )
            if not docs and sparse_vector and milvus.has_collection():
                docs = milvus.sparse_search(
                    sparse_embedding=sparse_vector,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=settings.leaf_retrieve_level,
                )
                retrieval_mode = "sparse_milvus"
            elif not docs and sparse_vector:
                docs, retrieval_mode = local_store.search_sparse(
                    sparse_embedding=sparse_vector,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=settings.leaf_retrieve_level,
                )
        except Exception as exc:
            warnings.append(str(exc))
            docs = []
            retrieval_mode = "files_first_error"

        if docs and settings.vector_compatibility_enabled and embedding_client.is_ready():
            if _should_apply_files_first_vector_fusion(
                query=query,
                query_context=query_context,
                docs=docs,
                top_k=top_k,
            ):
                try:
                    dense_vector = embedding_client.embed([str((query_context or {}).get("expanded_query", "")).strip() or query], settings.embedding_model)[0]
                    if milvus.has_collection():
                        vector_hits = milvus.dense_search(
                            dense_embedding=dense_vector,
                            top_k=max(candidate_k, top_k) * 2,
                            candidate_k=max(candidate_k, top_k) * 2,
                            leaf_level=settings.leaf_retrieve_level,
                        )
                    else:
                        vector_hits, _vector_mode = local_store.search(
                            dense_embedding=dense_vector,
                            sparse_embedding={},
                            top_k=max(candidate_k, top_k) * 2,
                            candidate_k=max(candidate_k, top_k) * 2,
                            leaf_level=settings.leaf_retrieve_level,
                        )
                    hydrated = files_first_store.get_docs_by_chunk_ids(
                        [str(item.get("chunk_id", "")).strip() for item in vector_hits if str(item.get("chunk_id", "")).strip()]
                    )
                    if hydrated:
                        docs = _merge_files_first_with_vector_candidates(
                            files_first_docs=docs,
                            vector_docs=hydrated,
                            top_k=max(top_k, candidate_k),
                        )
                        retrieval_mode = "files_first_vector_fused"
                        warnings.append("files_first_vector_fusion_applied")
                except Exception as exc:
                    warnings.append(f"files_first_vector_fusion_failed:{exc}")

    if not docs:
        if normalized_search_mode == "files_first" and not sparse_vector:
            warnings.append("files_first_sparse_query_empty")
        if not settings.vector_compatibility_enabled:
            warnings.append("vector_compatibility_disabled")
            return {
                "backend": "supermew_hybrid",
                "retrieval_mode": retrieval_mode if retrieval_mode != "hybrid" else ("files_first_empty" if normalized_search_mode == "files_first" else "vector_compatibility_disabled"),
                "rerank_applied": False,
                "candidate_k": max(candidate_k, top_k),
                "chunks": [],
                "total": 0,
                "warnings": warnings,
            }
        if normalized_search_mode == "files_first" and not settings.files_first_dense_fallback_enabled:
            warnings.append("files_first_dense_fallback_disabled")
            return {
                "backend": "supermew_hybrid",
                "retrieval_mode": retrieval_mode if retrieval_mode != "hybrid" else "files_first_empty",
                "rerank_applied": False,
                "candidate_k": max(candidate_k, top_k),
                "chunks": [],
                "total": 0,
                "warnings": warnings,
            }
        if not embedding_client.is_ready():
            return {
                "backend": "supermew_hybrid",
                "retrieval_mode": "unconfigured",
                "rerank_applied": False,
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["embedding_client_not_configured", *warnings],
            }

        dense_vector = embedding_client.embed([query], settings.embedding_model)[0]
        try:
            if milvus.has_collection():
                if sparse_vector and lexicon.is_ready():
                    docs = milvus.hybrid_search(
                        dense_embedding=dense_vector,
                        sparse_embedding=sparse_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=settings.leaf_retrieve_level,
                    )
                    retrieval_mode = "hybrid" if normalized_search_mode != "files_first" else "files_first_dense_hybrid_fallback"
                else:
                    retrieval_mode = "dense_fallback" if normalized_search_mode != "files_first" else "files_first_dense_fallback"
                    docs = milvus.dense_search(
                        dense_embedding=dense_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=settings.leaf_retrieve_level,
                    )
                    if not sparse_vector:
                        warnings.append("sparse_lexicon_missing_or_query_terms_unseen")
            else:
                docs, retrieval_mode = local_store.search(
                    dense_embedding=dense_vector,
                    sparse_embedding=sparse_vector,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=settings.leaf_retrieve_level,
                )
                if normalized_search_mode == "files_first":
                    retrieval_mode = f"files_first_{retrieval_mode}"
                if retrieval_mode.endswith("dense_local_fallback") and not sparse_vector:
                    warnings.append("sparse_lexicon_missing_or_query_terms_unseen")
        except Exception as exc:
            warnings.append(str(exc))
            docs = []

    docs = filter_docs_fn(docs, allowed_file_path_prefixes)
    if allowed_file_path_prefixes and not docs:
        warnings.append("source_prefix_filtered_all")

    reranked_docs = docs
    rerank_applied = False
    rerank_error = None
    if enable_rerank and settings.rerank_endpoint and settings.rerank_model and settings.rerank_api_key and docs:
        reranked_docs, rerank_applied, rerank_error = rerank_fn(query, docs, top_k)
        if rerank_error:
            warnings.append(rerank_error)
    else:
        reranked_docs = docs[:top_k]

    merged_docs, merge_meta = auto_merge_fn(reranked_docs, top_k)
    normalized = [normalize_chunk(item) for item in merged_docs[:top_k]]
    normalized = lexical_gate_fn(query, normalized, warnings)

    return {
        "backend": "supermew_hybrid",
        "retrieval_mode": retrieval_mode,
        "rerank_applied": rerank_applied,
        "rerank_model": settings.rerank_model or None,
        "rerank_endpoint": settings.rerank_endpoint or None,
        "rerank_error": rerank_error,
        "candidate_k": max(candidate_k, top_k),
        "leaf_retrieve_level": settings.leaf_retrieve_level,
        "auto_merge_enabled": merge_meta["auto_merge_enabled"],
        "auto_merge_applied": merge_meta["auto_merge_applied"],
        "auto_merge_threshold": merge_meta["auto_merge_threshold"],
        "auto_merge_replaced_chunks": merge_meta["auto_merge_replaced_chunks"],
        "auto_merge_steps": merge_meta["auto_merge_steps"],
        "chunks": normalized,
        "total": len(normalized),
        "warnings": warnings,
    }


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


def _merge_files_first_with_vector_candidates(
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
