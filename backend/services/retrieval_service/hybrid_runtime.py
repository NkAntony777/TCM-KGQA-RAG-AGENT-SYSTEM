from __future__ import annotations

from typing import Any, Callable

from services.retrieval_service.files_first_support import normalize_chunk
from services.retrieval_service.retrieval_responses import empty_search_response
from services.retrieval_service.vector_compatibility import maybe_fuse_files_first_with_vector


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
            try:
                docs, retrieval_mode = files_first_store.search(
                    query=query,
                    query_context=query_context,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=settings.leaf_retrieve_level,
                )
            except TypeError as exc:
                if "query_context" not in str(exc):
                    raise
                docs, retrieval_mode = files_first_store.search(
                    query=query,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=settings.leaf_retrieve_level,
                )
        except Exception as exc:
            warnings.append(str(exc))
            docs = []
            retrieval_mode = "files_first_error"
        milvus_collection_available = False
        try:
            milvus_collection_available = bool(milvus.has_collection())
        except Exception as exc:
            warnings.append(f"milvus_sparse_fallback_unavailable:{exc}")
        if not docs and sparse_vector and milvus_collection_available:
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

        docs, fused_mode = maybe_fuse_files_first_with_vector(
            settings=settings,
            files_first_store=files_first_store,
            milvus=milvus,
            local_store=local_store,
            embedding_client=embedding_client,
            query=query,
            query_context=query_context,
            docs=docs,
            top_k=top_k,
            candidate_k=candidate_k,
            warnings=warnings,
        )
        if fused_mode:
            retrieval_mode = fused_mode

    if not docs:
        if normalized_search_mode == "files_first" and not sparse_vector:
            warnings.append("files_first_sparse_query_empty")
        if not settings.vector_compatibility_enabled:
            warnings.append("vector_compatibility_disabled")
            return empty_search_response(
                retrieval_mode=retrieval_mode if retrieval_mode != "hybrid" else ("files_first_empty" if normalized_search_mode == "files_first" else "vector_compatibility_disabled"),
                candidate_k=max(candidate_k, top_k),
                warnings=warnings,
            )
        if normalized_search_mode == "files_first" and not settings.files_first_dense_fallback_enabled:
            warnings.append("files_first_dense_fallback_disabled")
            return empty_search_response(
                retrieval_mode=retrieval_mode if retrieval_mode != "hybrid" else "files_first_empty",
                candidate_k=max(candidate_k, top_k),
                warnings=warnings,
            )
        if not embedding_client.is_ready():
            return empty_search_response(
                retrieval_mode="unconfigured",
                candidate_k=candidate_k,
                warnings=["embedding_client_not_configured", *warnings],
            )

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
