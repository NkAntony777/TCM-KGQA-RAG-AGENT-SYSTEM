from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services.retrieval_service.backends import LocalHybridStore
from services.retrieval_service.backends import MilvusHybridStore
from services.retrieval_service.backends import OpenAICompatibleClient
from services.retrieval_service.files_first_support import (
    build_section_response as _build_section_response,
    LocalFilesFirstStore,
    ParentChunkStore,
)
from services.retrieval_service import retrieval_indexing
from services.retrieval_service import query_rewrite_runtime
from services.retrieval_service import retrieval_quality
from services.retrieval_service import case_qa_runtime
from services.retrieval_service.engine_health import build_retrieval_health
from services.retrieval_service.query_understanding import LLMQueryUnderstanding
from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings
from services.retrieval_service.search_runtime import search_hybrid as _search_hybrid
from services.retrieval_service.settings import load_settings
from services.retrieval_service.settings import RetrievalServiceSettings
from services.retrieval_service.sparse_lexicon import SparseLexiconStore

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class RetrievalEngine:
    def __init__(self, settings: RetrievalServiceSettings | None = None):
        self.settings = settings or load_settings()
        self.lexicon = SparseLexiconStore(
            self.settings.sparse_lexicon_path,
            runtime_graph_db_path=self.settings.runtime_graph_db_path,
        )
        self.parent_store = ParentChunkStore(self.settings.parent_chunk_store_path)
        self.local_store = LocalHybridStore(self.settings.local_index_path)
        self.files_first_store = LocalFilesFirstStore(
            self.settings.local_index_path.with_suffix(".fts.db"),
            tokenizer=self.lexicon,
            summary_cache_path=self.settings.section_summary_cache_path,
        )
        self.embedding_client = OpenAICompatibleClient(
            base_url=self.settings.embedding_base_url,
            api_key=self.settings.embedding_api_key,
        )
        self.structured_qa = StructuredQAIndex(
            StructuredQAIndexSettings(
                index_path=self.settings.structured_qa_index_path,
                qa_input_path=self.settings.structured_qa_input_path,
                case_input_path=self.settings.structured_case_input_path,
            )
        )
        self._case_qa = None
        self._case_qa_error = ""
        self.rewrite_client = OpenAICompatibleClient(
            base_url=self.settings.rewrite_base_url,
            api_key=self.settings.rewrite_api_key,
        )
        self.query_understanding = LLMQueryUnderstanding(
            client=self.rewrite_client,
            model=self.settings.rewrite_model,
        )
        self.milvus = MilvusHybridStore(self.settings)

    @property
    def case_qa(self):
        if self._case_qa is None and self.settings.vector_compatibility_enabled:
            try:
                from services.retrieval_service.chroma_case_store import ChromaCaseQASettings, ChromaCaseQAStore

                self._case_qa = ChromaCaseQAStore(
                    ChromaCaseQASettings(
                        db_path=self.settings.chroma_case_db_path,
                        mirror_path=self.settings.chroma_case_mirror_path,
                        collection_prefix=self.settings.chroma_case_collection_prefix,
                    )
                )
            except Exception as exc:
                self._case_qa_error = str(exc)
                self._case_qa = None
        return self._case_qa

    @case_qa.setter
    def case_qa(self, value) -> None:
        self._case_qa = value

    def health(self) -> dict[str, Any]:
        return build_retrieval_health(self)

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        return case_qa_runtime.search_case_qa(self, query, top_k=top_k, candidate_k=candidate_k)

    def search_hybrid(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
        enable_rerank: bool,
        allowed_file_path_prefixes: list[str] | None = None,
        search_mode: str = "files_first",
    ) -> dict[str, Any]:
        return _search_hybrid(
            self,
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )

    def _maybe_refine_files_first_query(
        self,
        *,
        query: str,
        search_mode: str,
        result: dict[str, Any],
        top_k: int,
    ) -> str:
        return query_rewrite_runtime._maybe_refine_files_first_query(
            self,
            query=query,
            search_mode=search_mode,
            result=result,
            top_k=top_k,
        )

    def _refine_files_first_query(self, query: str) -> str:
        return query_rewrite_runtime._refine_files_first_query(self, query)

    def _fast_refine_files_first_query(self, query: str) -> str:
        return query_rewrite_runtime._fast_refine_files_first_query(self, query)

    @staticmethod
    def _primary_refine_entities(query: str) -> list[str]:
        return query_rewrite_runtime._primary_refine_entities(query)

    @staticmethod
    def _prefer_refined_result(*, primary: dict[str, Any], refined: dict[str, Any]) -> bool:
        return query_rewrite_runtime._prefer_refined_result(primary=primary, refined=refined)

    def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
        return query_rewrite_runtime.rewrite_query(self, query, strategy)

    def index_documents(self, docs: list[dict[str, Any]], *, reset_collection: bool = False) -> dict[str, Any]:
        return retrieval_indexing.index_documents(self, docs, reset_collection=reset_collection)

    def index_documents_files_first(
        self,
        docs: list[dict[str, Any]],
        *,
        reset_collection: bool = False,
        state_path: Path | None = None,
        resume: bool = False,
        show_progress: bool = False,
        batch_size: int = 512,
    ) -> dict[str, Any]:
        return retrieval_indexing.index_documents_files_first(
            self,
            docs,
            reset_collection=reset_collection,
            state_path=state_path,
            resume=resume,
            show_progress=show_progress,
            batch_size=batch_size,
        )

    def _embed_texts_in_batches(self, texts: list[str]) -> list[list[float]]:
        return retrieval_indexing._embed_texts_in_batches(self, texts)

    @staticmethod
    def _load_corpus_file(path: Path) -> list[dict[str, Any]]:
        docs = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(docs, list):
            raise ValueError(f"invalid_corpus_file: {path}")
        return [item for item in docs if isinstance(item, dict)]

    @staticmethod
    def _dedupe_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for doc in docs:
            key = str(doc.get("chunk_id", "")).strip()
            if not key:
                key = "|".join(
                    [
                        str(doc.get("filename", "")).strip(),
                        str(doc.get("file_path", "")).strip(),
                        str(doc.get("page_number", "")).strip(),
                        str(doc.get("chunk_idx", "")).strip(),
                    ]
                )
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def index_corpus_files(self, corpus_paths: list[Path], *, reset_collection: bool = False, index_mode: str = "hybrid") -> dict[str, Any]:
        return retrieval_indexing.index_corpus_files(self, corpus_paths, reset_collection=reset_collection, index_mode=index_mode)

    def index_corpus_files_with_options(
        self,
        corpus_paths: list[Path],
        *,
        reset_collection: bool = False,
        index_mode: str = "hybrid",
        files_first_state_path: Path | None = None,
        files_first_resume: bool = False,
        files_first_show_progress: bool = False,
        files_first_batch_size: int = 512,
    ) -> dict[str, Any]:
        return retrieval_indexing.index_corpus_files_with_options(
            self,
            corpus_paths,
            reset_collection=reset_collection,
            index_mode=index_mode,
            files_first_state_path=files_first_state_path,
            files_first_resume=files_first_resume,
            files_first_show_progress=files_first_show_progress,
            files_first_batch_size=files_first_batch_size,
        )

    def index_configured_corpora(
        self,
        *,
        reset_collection: bool = False,
        include_sample: bool = True,
        include_modern: bool = True,
        include_classic: bool = True,
        index_mode: str = "hybrid",
        files_first_state_path: Path | None = None,
        files_first_resume: bool = False,
        files_first_show_progress: bool = False,
        files_first_batch_size: int = 512,
    ) -> dict[str, Any]:
        return retrieval_indexing.index_configured_corpora(
            self,
            reset_collection=reset_collection,
            include_sample=include_sample,
            include_modern=include_modern,
            include_classic=include_classic,
            index_mode=index_mode,
            files_first_state_path=files_first_state_path,
            files_first_resume=files_first_resume,
            files_first_show_progress=files_first_show_progress,
            files_first_batch_size=files_first_batch_size,
        )

    def index_sample_corpus(self, *, reset_collection: bool = False) -> dict[str, Any]:
        return retrieval_indexing.index_sample_corpus(self, reset_collection=reset_collection)

    @staticmethod
    def _normalize_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        return case_qa_runtime._normalize_case_chunk(item)

    @staticmethod
    def _normalize_structured_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        return case_qa_runtime._normalize_structured_case_chunk(item)

    def _auto_merge(self, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return retrieval_quality._auto_merge(self, docs, top_k)

    def _apply_lexical_sanity_gate(
        self,
        query: str,
        docs: list[dict[str, Any]],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        return retrieval_quality._apply_lexical_sanity_gate(self, query, docs, warnings)

    @staticmethod
    def _doc_matches_anchors(item: dict[str, Any], anchors: list[str]) -> bool:
        return retrieval_quality._doc_matches_anchors(item, anchors)

    @staticmethod
    def _extract_query_anchors(query: str) -> list[str]:
        return retrieval_quality._extract_query_anchors(query)

    def _rerank(self, query: str, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], bool, str | None]:
        return retrieval_quality._rerank(self, query, docs, top_k)

    def read_section(self, path: str, *, top_k: int = 12) -> dict[str, Any]:
        payload = self.files_first_store.read_section(path=path, top_k=top_k)
        return _build_section_response(path=path, payload=payload, parent_store=self.parent_store)

    @staticmethod
    def _filter_docs_by_file_path_prefixes(
        docs: list[dict[str, Any]],
        prefixes: list[str] | None,
    ) -> list[dict[str, Any]]:
        return retrieval_quality._filter_docs_by_file_path_prefixes(docs, prefixes)

_retrieval_engine: RetrievalEngine | None = None
_retrieval_engine_lock = threading.Lock()


def get_retrieval_engine() -> RetrievalEngine:
    global _retrieval_engine
    if _retrieval_engine is None:
        with _retrieval_engine_lock:
            if _retrieval_engine is None:
                _retrieval_engine = RetrievalEngine()
    return _retrieval_engine
