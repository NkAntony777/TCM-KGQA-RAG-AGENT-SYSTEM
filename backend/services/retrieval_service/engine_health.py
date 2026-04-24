from __future__ import annotations

from typing import Any

from services.retrieval_service.sparse_lexicon import runtime_entity_words


def build_retrieval_health(engine: Any) -> dict[str, Any]:
    milvus_health = engine.milvus.health()
    local_health = engine.local_store.health()
    files_first_health = engine.files_first_store.health()
    structured_qa_health = engine.structured_qa.health()
    if engine.settings.vector_compatibility_enabled:
        case_qa_health = engine.case_qa.health() if engine.case_qa is not None else {
            "case_qa_configured": False,
            "case_qa_client_available": False,
        }
    else:
        case_qa_health = {
            "case_qa_configured": False,
            "case_qa_client_available": False,
            "case_qa_collection_count": 0,
            "case_qa_collections": [],
            "case_qa_vector_hot_path_disabled": True,
        }
    if engine._case_qa_error:
        case_qa_health["case_qa_error"] = engine._case_qa_error
    milvus_collection_exists = bool(milvus_health.get("collection_exists"))
    files_first_index_available = bool(files_first_health.get("files_first_index_available"))
    hybrid_enabled = engine.lexicon.is_ready() and files_first_index_available
    return {
        "status": "ok",
        "vector_compatibility_enabled": engine.settings.vector_compatibility_enabled,
        "vector_store": (
            "milvus"
            if milvus_collection_exists
            else ("disabled" if not engine.settings.vector_compatibility_enabled else "local_hybrid_index")
        ),
        "hybrid_enabled": hybrid_enabled,
        "files_first_enabled": engine.lexicon.is_ready() and files_first_index_available,
        "embedding_configured": engine.embedding_client.is_ready(),
        "rewrite_configured": engine.rewrite_client.is_ready(),
        "sparse_lexicon_loaded": engine.lexicon.is_ready(),
        "modern_corpus_available": engine.settings.modern_corpus_path.exists(),
        "modern_corpus_path": str(engine.settings.modern_corpus_path),
        "classic_corpus_available": engine.settings.classic_corpus_path.exists(),
        "classic_corpus_path": str(engine.settings.classic_corpus_path),
        "structured_qa_enabled": bool(structured_qa_health.get("available")),
        "case_qa_vector_fallback_enabled": engine.settings.case_qa_vector_fallback_enabled,
        "files_first_dense_fallback_enabled": engine.settings.files_first_dense_fallback_enabled,
        "runtime_entity_lexicon_loaded": bool(runtime_entity_words(engine.settings.runtime_graph_db_path)),
        **structured_qa_health,
        **case_qa_health,
        **milvus_health,
        **local_health,
        **files_first_health,
    }
