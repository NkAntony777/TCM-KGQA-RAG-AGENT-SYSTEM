from __future__ import annotations

from typing import Any

from services.retrieval_service.hybrid_runtime import run_hybrid_search


def search_hybrid(
    engine: Any,
    query: str,
    *,
    top_k: int,
    candidate_k: int,
    enable_rerank: bool,
    allowed_file_path_prefixes: list[str] | None = None,
    search_mode: str = "files_first",
) -> dict[str, Any]:
    query_context = _build_query_context(engine, query=query, search_mode=search_mode)
    result = _run_once(
        engine,
        query=query,
        query_context=query_context,
        top_k=top_k,
        candidate_k=candidate_k,
        enable_rerank=enable_rerank,
        allowed_file_path_prefixes=allowed_file_path_prefixes,
        search_mode=search_mode,
    )
    refined_query = engine._maybe_refine_files_first_query(
        query=query,
        search_mode=search_mode,
        result=result,
        top_k=top_k,
    )
    if not refined_query:
        return result

    refined_result = _run_once(
        engine,
        query=refined_query,
        query_context=query_context,
        top_k=top_k,
        candidate_k=candidate_k,
        enable_rerank=enable_rerank,
        allowed_file_path_prefixes=allowed_file_path_prefixes,
        search_mode=search_mode,
    )
    if engine._prefer_refined_result(primary=result, refined=refined_result):
        warnings = list(refined_result.get("warnings", [])) if isinstance(refined_result.get("warnings"), list) else []
        warnings.append(f"single_query_refinement_applied:{refined_query}")
        refined_result["warnings"] = warnings
        refined_result["refined_from_query"] = query
        refined_result["refined_query"] = refined_query
        if query_context:
            refined_result["query_context"] = query_context
        return refined_result

    warnings = list(result.get("warnings", [])) if isinstance(result.get("warnings"), list) else []
    warnings.append("single_query_refinement_no_gain")
    result["warnings"] = warnings
    if query_context:
        result["query_context"] = query_context
    return result


def _build_query_context(engine: Any, *, query: str, search_mode: str) -> dict[str, Any] | None:
    if (search_mode or "").strip().lower() != "files_first":
        return None
    if not engine.query_understanding.should_run(query):
        return None
    understanding = engine.query_understanding.understand(query)
    return understanding.to_context() if understanding is not None else None


def _run_once(
    engine: Any,
    *,
    query: str,
    query_context: dict[str, Any] | None,
    top_k: int,
    candidate_k: int,
    enable_rerank: bool,
    allowed_file_path_prefixes: list[str] | None,
    search_mode: str,
) -> dict[str, Any]:
    return run_hybrid_search(
        settings=engine.settings,
        files_first_store=engine.files_first_store,
        milvus=engine.milvus,
        local_store=engine.local_store,
        lexicon=engine.lexicon,
        embedding_client=engine.embedding_client,
        query_context=query_context,
        query=query,
        top_k=top_k,
        candidate_k=candidate_k,
        enable_rerank=enable_rerank,
        allowed_file_path_prefixes=allowed_file_path_prefixes,
        search_mode=search_mode,
        rerank_fn=engine._rerank,
        auto_merge_fn=engine._auto_merge,
        filter_docs_fn=engine._filter_docs_by_file_path_prefixes,
        lexical_gate_fn=engine._apply_lexical_sanity_gate,
    )
