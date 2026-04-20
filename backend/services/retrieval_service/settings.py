from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _vector_compatibility_enabled_from_env() -> bool:
    return _first_env("RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED", default="false").lower() == "true"


@dataclass(frozen=True)
class RetrievalServiceSettings:
    project_backend_dir: Path
    vector_compatibility_enabled: bool
    milvus_uri: str
    milvus_host: str
    milvus_port: str
    milvus_collection: str
    embedding_base_url: str
    embedding_model: str
    embedding_api_key: str
    case_qa_embedding_model: str
    case_qa_embedding_dimensions: int
    rewrite_base_url: str
    rewrite_model: str
    rewrite_api_key: str
    rerank_endpoint: str
    rerank_model: str
    rerank_api_key: str
    auto_merge_enabled: bool
    auto_merge_threshold: int
    leaf_retrieve_level: int
    dense_dim: int
    embedding_batch_size: int
    embedding_batch_workers: int
    embedding_show_progress: bool
    chroma_case_db_path: Path
    chroma_case_mirror_path: Path
    chroma_case_collection_prefix: str
    case_qa_vector_fallback_enabled: bool
    structured_qa_index_path: Path
    structured_qa_input_path: Path
    structured_case_input_path: Path
    files_first_dense_fallback_enabled: bool
    sparse_lexicon_path: Path
    parent_chunk_store_path: Path
    local_index_path: Path
    sample_corpus_path: Path
    modern_corpus_path: Path
    classic_corpus_path: Path
    runtime_graph_db_path: Path
    section_summary_cache_path: Path


def load_settings() -> RetrievalServiceSettings:
    backend_dir = Path(__file__).resolve().parents[2]
    vector_compatibility_enabled = _vector_compatibility_enabled_from_env()
    base_url = _first_env("EMBEDDING_BASE_URL", "LLM_BASE_URL", "BASE_URL", "OPENAI_BASE_URL")
    api_key = _first_env("EMBEDDING_API_KEY", "LLM_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY")
    rewrite_base_url = _first_env("LLM_BASE_URL", "BASE_URL", "OPENAI_BASE_URL", default=base_url)
    rewrite_api_key = _first_env("LLM_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY", default=api_key)
    rerank_endpoint = _first_env("RETRIEVAL_RERANK_ENDPOINT", "RERANK_BINDING_HOST").rstrip("/")
    if rerank_endpoint and not rerank_endpoint.endswith("/v1/rerank"):
        rerank_endpoint = f"{rerank_endpoint}/v1/rerank"

    return RetrievalServiceSettings(
        project_backend_dir=backend_dir,
        vector_compatibility_enabled=vector_compatibility_enabled,
        milvus_uri=_first_env("MILVUS_URI"),
        milvus_host=_first_env("MILVUS_HOST", default="127.0.0.1"),
        milvus_port=_first_env("MILVUS_PORT", default="19530"),
        milvus_collection=_first_env("MILVUS_COLLECTION", default="embeddings_collection"),
        embedding_base_url=base_url,
        embedding_model=_first_env("EMBEDDING_MODEL", "EMBEDDER", default="text-embedding-3-small"),
        embedding_api_key=api_key,
        case_qa_embedding_model=_first_env("CASE_QA_EMBEDDING_MODEL", "EMBEDDING_MODEL", "EMBEDDER", default="text-embedding-3-small"),
        case_qa_embedding_dimensions=int(_first_env("CASE_QA_EMBEDDING_DIM", default="1024")),
        rewrite_base_url=rewrite_base_url,
        rewrite_model=_first_env("RETRIEVAL_REWRITE_MODEL", "LLM_MODEL", "MODEL", default="gpt-4.1-mini"),
        rewrite_api_key=rewrite_api_key,
        rerank_endpoint=rerank_endpoint,
        rerank_model=_first_env("RETRIEVAL_RERANK_MODEL", "RERANK_MODEL"),
        rerank_api_key=_first_env("RETRIEVAL_RERANK_API_KEY", "RERANK_API_KEY"),
        auto_merge_enabled=_first_env("AUTO_MERGE_ENABLED", default="true").lower() != "false",
        auto_merge_threshold=int(_first_env("AUTO_MERGE_THRESHOLD", default="2")),
        leaf_retrieve_level=int(_first_env("LEAF_RETRIEVE_LEVEL", default="3")),
        dense_dim=int(_first_env("RETRIEVAL_DENSE_DIM", default="2560")),
        embedding_batch_size=int(_first_env("RETRIEVAL_EMBED_BATCH_SIZE", default="64")),
        embedding_batch_workers=int(_first_env("RETRIEVAL_EMBED_WORKERS", default="1")),
        embedding_show_progress=_first_env("RETRIEVAL_EMBED_PROGRESS", default="false").lower() == "true",
        chroma_case_db_path=Path(_first_env("CHROMA_CASE_DB_PATH", default="E:/tcm_vector_db")),
        chroma_case_mirror_path=backend_dir / "storage" / "chroma_case_query_mirror",
        chroma_case_collection_prefix=_first_env("CHROMA_CASE_COLLECTION_PREFIX", default="tcm_shard_"),
        case_qa_vector_fallback_enabled=vector_compatibility_enabled
        and _first_env("CASE_QA_VECTOR_FALLBACK_ENABLED", default="false").lower() == "true",
        structured_qa_index_path=backend_dir / "storage" / "qa_structured_index.sqlite",
        structured_qa_input_path=backend_dir / "services" / "retrieval_service" / "data" / "case_qa_clean" / "qa_fts_ready.jsonl",
        structured_case_input_path=backend_dir / "services" / "retrieval_service" / "data" / "case_qa_clean" / "case_fts_ready.jsonl",
        files_first_dense_fallback_enabled=vector_compatibility_enabled
        and _first_env("FILES_FIRST_DENSE_FALLBACK_ENABLED", default="false").lower() == "true",
        sparse_lexicon_path=backend_dir / "storage" / "retrieval_sparse_lexicon.json",
        parent_chunk_store_path=backend_dir / "storage" / "retrieval_parent_chunks.json",
        local_index_path=backend_dir / "storage" / "retrieval_local_index.json",
        sample_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "sample_corpus.json",
        modern_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "herb2_modern_corpus.json",
        classic_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "classic_books_corpus.json",
        runtime_graph_db_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.db",
        section_summary_cache_path=backend_dir / "storage" / "section_summary_cache.sqlite",
    )
