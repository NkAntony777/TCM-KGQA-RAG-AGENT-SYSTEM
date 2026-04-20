from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import httpx

from router.tcm_intent_classifier import analyze_tcm_query
from services.qa_service.alias_service import get_runtime_alias_service
from services.retrieval_service.backends import LocalHybridStore
from services.retrieval_service.backends import MilvusHybridStore
from services.retrieval_service.backends import OpenAICompatibleClient
from services.retrieval_service.files_first_support import (
    build_section_response as _build_section_response,
    LocalFilesFirstStore,
    ParentChunkStore,
    _query_flags,
)
from services.retrieval_service.hybrid_runtime import run_hybrid_search
from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings
from services.retrieval_service.settings import load_settings
from services.retrieval_service.settings import RetrievalServiceSettings
from services.retrieval_service.sparse_lexicon import runtime_entity_words as _runtime_entity_words
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
        milvus_health = self.milvus.health()
        local_health = self.local_store.health()
        files_first_health = self.files_first_store.health()
        structured_qa_health = self.structured_qa.health()
        if self.settings.vector_compatibility_enabled:
            case_qa_health = self.case_qa.health() if self.case_qa is not None else {
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
        if self._case_qa_error:
            case_qa_health["case_qa_error"] = self._case_qa_error
        milvus_collection_exists = bool(milvus_health.get("collection_exists"))
        local_index_available = bool(local_health.get("local_index_available"))
        files_first_index_available = bool(files_first_health.get("files_first_index_available"))
        hybrid_enabled = self.lexicon.is_ready() and files_first_index_available
        return {
            "status": "ok",
            "vector_compatibility_enabled": self.settings.vector_compatibility_enabled,
            "vector_store": "milvus" if milvus_collection_exists else ("disabled" if not self.settings.vector_compatibility_enabled else "local_hybrid_index"),
            "hybrid_enabled": hybrid_enabled,
            "files_first_enabled": self.lexicon.is_ready() and files_first_index_available,
            "embedding_configured": self.embedding_client.is_ready(),
            "rewrite_configured": self.rewrite_client.is_ready(),
            "sparse_lexicon_loaded": self.lexicon.is_ready(),
            "modern_corpus_available": self.settings.modern_corpus_path.exists(),
            "modern_corpus_path": str(self.settings.modern_corpus_path),
            "classic_corpus_available": self.settings.classic_corpus_path.exists(),
            "classic_corpus_path": str(self.settings.classic_corpus_path),
            "structured_qa_enabled": bool(structured_qa_health.get("available")),
            "case_qa_vector_fallback_enabled": self.settings.case_qa_vector_fallback_enabled,
            "files_first_dense_fallback_enabled": self.settings.files_first_dense_fallback_enabled,
            "runtime_entity_lexicon_loaded": bool(_runtime_entity_words(self.settings.runtime_graph_db_path)),
            **structured_qa_health,
            **case_qa_health,
            **milvus_health,
            **local_health,
            **files_first_health,
        }

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        structured_rows = self.structured_qa.search_case(query, top_k=max(1, int(top_k)))
        if structured_rows:
            chunks = [self._normalize_structured_case_chunk(item) for item in structured_rows if isinstance(item, dict)]
            return {
                "backend": "case-qa",
                "retrieval_mode": "structured_case_qa",
                "candidate_k": candidate_k,
                "chunks": chunks,
                "total": len(chunks),
                "warnings": [],
            }

        warnings: list[str] = []
        if not self.settings.case_qa_vector_fallback_enabled:
            return {
                "backend": "case-qa",
                "retrieval_mode": "structured_case_qa_empty",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["structured_case_qa_empty", "case_qa_vector_fallback_disabled"],
            }
        if not self.embedding_client.is_ready():
            return {
                "backend": "case-qa",
                "retrieval_mode": "unconfigured",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["embedding_client_not_configured"],
            }

        dense_vector = self.embedding_client.embed(
            [query],
            self.settings.case_qa_embedding_model,
            dimensions=self.settings.case_qa_embedding_dimensions,
        )[0]
        case_qa_store = self.case_qa
        if case_qa_store is None:
            return {
                "backend": "case-qa",
                "retrieval_mode": "vector_compatibility_disabled",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["case_qa_vector_hot_path_disabled"],
            }
        data = case_qa_store.search(
            query=query,
            query_embedding=dense_vector,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        warnings.extend(data.get("warnings", []))
        chunks = [self._normalize_case_chunk(item) for item in data.get("chunks", []) if isinstance(item, dict)]

        return {
            "backend": "case-qa",
            "retrieval_mode": data.get("retrieval_mode", "case_qa"),
            "candidate_k": candidate_k,
            "embedding_model": self.settings.case_qa_embedding_model,
            "embedding_dimensions": self.settings.case_qa_embedding_dimensions,
            "collection_count": data.get("collection_count", 0),
            "per_collection_k": data.get("per_collection_k"),
            "chunks": chunks,
            "total": len(chunks),
            "warnings": warnings,
        }

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
        result = run_hybrid_search(
            settings=self.settings,
            files_first_store=self.files_first_store,
            milvus=self.milvus,
            local_store=self.local_store,
            lexicon=self.lexicon,
            embedding_client=self.embedding_client,
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
            rerank_fn=self._rerank,
            auto_merge_fn=self._auto_merge,
            filter_docs_fn=self._filter_docs_by_file_path_prefixes,
            lexical_gate_fn=self._apply_lexical_sanity_gate,
        )
        refined_query = self._maybe_refine_files_first_query(
            query=query,
            search_mode=search_mode,
            result=result,
            top_k=top_k,
        )
        if not refined_query:
            return result
        refined_result = run_hybrid_search(
            settings=self.settings,
            files_first_store=self.files_first_store,
            milvus=self.milvus,
            local_store=self.local_store,
            lexicon=self.lexicon,
            embedding_client=self.embedding_client,
            query=refined_query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
            rerank_fn=self._rerank,
            auto_merge_fn=self._auto_merge,
            filter_docs_fn=self._filter_docs_by_file_path_prefixes,
            lexical_gate_fn=self._apply_lexical_sanity_gate,
        )
        if self._prefer_refined_result(primary=result, refined=refined_result):
            warnings = list(refined_result.get("warnings", [])) if isinstance(refined_result.get("warnings"), list) else []
            warnings.append(f"single_query_refinement_applied:{refined_query}")
            refined_result["warnings"] = warnings
            refined_result["refined_from_query"] = query
            refined_result["refined_query"] = refined_query
            return refined_result
        warnings = list(result.get("warnings", [])) if isinstance(result.get("warnings"), list) else []
        warnings.append("single_query_refinement_no_gain")
        result["warnings"] = warnings
        return result

    def _maybe_refine_files_first_query(
        self,
        *,
        query: str,
        search_mode: str,
        result: dict[str, Any],
        top_k: int,
    ) -> str:
        if (search_mode or "").strip().lower() != "files_first":
            return ""
        chunks = result.get("chunks", []) if isinstance(result.get("chunks"), list) else []
        if chunks and len(chunks) >= min(max(2, top_k // 2), top_k):
            return ""
        flags = _query_flags(query)
        warnings = {str(item).strip() for item in result.get("warnings", []) if str(item).strip()} if isinstance(result.get("warnings"), list) else set()
        top_score = float(chunks[0].get("score", 0.0) or 0.0) if chunks else 0.0
        if chunks and flags.get("source_query") and len(chunks) == 1 and top_score >= 5.0:
            top_title = str(chunks[0].get("chapter_title", "") or "")
            top_book = str(chunks[0].get("book_name", "") or "")
            for focus in self._primary_refine_entities(query):
                if focus and (focus in top_title or focus in top_book):
                    return ""
        low_confidence = (
            not chunks
            or "lexical_sanity_filtered_all" in warnings
            or "files_first_sparse_query_empty" in warnings
        )
        if not low_confidence:
            return ""
        return self._refine_files_first_query(query)

    def _refine_files_first_query(self, query: str) -> str:
        base_query = str(query or "").strip()
        if not base_query:
            return ""
        flags = _query_flags(base_query)
        fast_refined = self._fast_refine_files_first_query(base_query)
        if (
            fast_refined
            and fast_refined != base_query
            and (flags.get("property_query") or flags.get("composition_query") or flags.get("comparison_query"))
            and not flags.get("source_query")
        ):
            return fast_refined
        alias_service = get_runtime_alias_service()
        heuristic = alias_service.expand_query_with_aliases(
            base_query,
            max_aliases_per_entity=3,
            max_entities=2,
        )
        should_remote_rewrite = (
            self.rewrite_client.is_ready()
            and (flags.get("source_query") or flags.get("property_query") or flags.get("composition_query"))
        )
        if should_remote_rewrite:
            try:
                prompt = (
                    "请把下面的中医问题改写成一条更适合古籍全文检索与图谱检索的短查询。"
                    "要求：保留核心实体、证候、书名线索；补全常见古今异名或近义表述；不超过40字；只输出改写结果。\n"
                    f"问题：{base_query}"
                )
                rewritten = str(self.rewrite_client.chat(prompt, self.settings.rewrite_model) or "").strip()
                rewritten = re.sub(r"\s+", " ", rewritten)
                if rewritten and rewritten != base_query:
                    return rewritten
            except Exception:
                pass
        if fast_refined and fast_refined != base_query:
            return fast_refined
        return heuristic if heuristic != base_query else ""

    def _fast_refine_files_first_query(self, query: str) -> str:
        base_query = str(query or "").strip()
        if not base_query:
            return ""
        flags = _query_flags(base_query)
        alias_service = get_runtime_alias_service()
        terms: list[str] = []
        seen: set[str] = set()

        def push(value: str) -> None:
            normalized = re.sub(r"\s+", " ", str(value or "")).strip()
            if len(normalized) < 2 or normalized in seen:
                return
            seen.add(normalized)
            terms.append(normalized)

        try:
            analysis = analyze_tcm_query(base_query)
            for item in analysis.matched_entities:
                name = str(item.name).strip()
                if len(name) >= 2:
                    push(name)
                    if alias_service.is_available():
                        for alias_name in alias_service.aliases_for_entity(name, max_aliases=2):
                            push(str(alias_name).strip())
        except Exception:
            pass

        for match in re.finditer(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)", base_query):
            push(match.group(0))

        for pattern in (
            r"^([\u4e00-\u9fff]{2,8}?)(?:主|治)",
            r"中的([\u4e00-\u9fff]{2,8})",
            r"^([\u4e00-\u9fff]{2,8}?)(?:的性味|的功效|的归经)",
        ):
            for match in re.finditer(pattern, base_query):
                push(match.group(1))

        for match in re.finditer(r"《([^》]{2,16})》", base_query):
            push(match.group(1))

        for match in re.finditer(r"[\u4e00-\u9fff]{2,8}", base_query):
            token = str(match.group(0)).strip()
            if token in {"什么", "为何", "为什么", "请给", "请从", "作用", "区别", "不同", "如何", "对应"}:
                continue
            if len(terms) >= 6:
                break
            push(token)

        if flags.get("source_query"):
            for cue in ("出处", "原文", "条文", "记载"):
                push(cue)
            if any(term in base_query for term in ("黄芪", "黄耆", "当归", "柴胡", "人参", "甘草", "附子", "地黄")):
                push("本草")
        if flags.get("property_query"):
            for cue in ("功效", "作用", "方解", "归经", "性味"):
                push(cue)
        if flags.get("composition_query"):
            for cue in ("组成", "药味", "加减", "方后注"):
                push(cue)
        if flags.get("comparison_query"):
            for cue in ("比较", "区别", "异同"):
                push(cue)

        refined = " ".join(terms[:10]).strip()
        return refined if refined and refined != base_query else ""

    @staticmethod
    def _primary_refine_entities(query: str) -> list[str]:
        entities: list[str] = []
        for match in re.finditer(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)", query):
            entities.append(str(match.group(0)).strip())
        for pattern in (
            r"^([\u4e00-\u9fff]{2,8}?)(?:主|治)",
            r"中的([\u4e00-\u9fff]{2,8})",
            r"^([\u4e00-\u9fff]{2,8}?)(?:的性味|的功效|的归经)",
        ):
            for match in re.finditer(pattern, query):
                entities.append(str(match.group(1)).strip())
        deduped: list[str] = []
        seen: set[str] = set()
        for item in entities:
            if len(item) < 2 or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped[:4]

    @staticmethod
    def _prefer_refined_result(*, primary: dict[str, Any], refined: dict[str, Any]) -> bool:
        primary_chunks = primary.get("chunks", []) if isinstance(primary.get("chunks"), list) else []
        refined_chunks = refined.get("chunks", []) if isinstance(refined.get("chunks"), list) else []
        if not refined_chunks:
            return False
        if not primary_chunks:
            return True
        primary_top = float(primary_chunks[0].get("score", 0.0) or 0.0)
        refined_top = float(refined_chunks[0].get("score", 0.0) or 0.0)
        if len(refined_chunks) > len(primary_chunks):
            return True
        return refined_top > primary_top + 0.03

    def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
        strategy = (strategy or "complex").strip().lower()
        expanded_query = f"{query}。请结合证候、治法、方剂出处与原文进行检索。"
        step_back_question = f"{query} 背后的中医辨证与治法原则是什么？" if strategy in {"step_back", "complex"} else ""
        step_back_answer = ""
        hypothetical_doc = ""

        if step_back_question and self.rewrite_client.is_ready():
            prompt = f"请用不超过120字回答：{step_back_question}"
            step_back_answer = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
        elif step_back_question:
            step_back_answer = "先辨证后论治，结合症状、证候、治法与方剂来源综合判断。"

        if strategy in {"hyde", "complex"}:
            if self.rewrite_client.is_ready():
                prompt = f"请生成一段用于检索的假设性资料片段：{query}"
                hypothetical_doc = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
            else:
                hypothetical_doc = f"{query} 可从证候识别、治法匹配、方剂来源、古籍原文四个维度组织答案。"

        if step_back_question and step_back_answer:
            expanded_query = f"{expanded_query}\n退步问题：{step_back_question}\n退步问题答案：{step_back_answer}"

        return {
            "strategy": strategy,
            "expanded_query": expanded_query,
            "step_back_question": step_back_question,
            "step_back_answer": step_back_answer,
            "hypothetical_doc": hypothetical_doc,
        }

    def index_documents(self, docs: list[dict[str, Any]], *, reset_collection: bool = False) -> dict[str, Any]:
        parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) < self.settings.leaf_retrieve_level]
        leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == self.settings.leaf_retrieve_level]
        if not leaf_docs:
            raise ValueError("no_leaf_chunks_to_index")
        if not self.embedding_client.is_ready():
            raise RuntimeError("embedding_client_not_configured")

        leaf_texts = [str(doc.get("text", "")) for doc in leaf_docs]
        self.lexicon.fit(leaf_texts)
        sparse_vectors = [self.lexicon.encode_document(text) for text in leaf_texts]
        self.lexicon.save()

        dense_vectors = self._embed_texts_in_batches(leaf_texts)
        dense_dim = len(dense_vectors[0]) if dense_vectors else self.settings.dense_dim
        if reset_collection:
            try:
                self.milvus.reset_collection()
            except Exception:
                pass
            self.local_store.reset()

        rows = []
        for doc, dense_embedding, sparse_embedding in zip(leaf_docs, dense_vectors, sparse_vectors):
            rows.append(
                {
                    "dense_embedding": dense_embedding,
                    "sparse_embedding": sparse_embedding,
                    "text": doc.get("text", ""),
                    "filename": doc.get("filename", ""),
                    "file_type": doc.get("file_type", "TXT"),
                    "file_path": doc.get("file_path", ""),
                    "page_number": int(doc.get("page_number", 0) or 0),
                    "chunk_idx": int(doc.get("chunk_idx", 0) or 0),
                    "chunk_id": doc.get("chunk_id", ""),
                    "parent_chunk_id": doc.get("parent_chunk_id", ""),
                    "root_chunk_id": doc.get("root_chunk_id", ""),
                    "chunk_level": int(doc.get("chunk_level", self.settings.leaf_retrieve_level) or self.settings.leaf_retrieve_level),
                }
            )
        inserted_to = "local_hybrid_index"
        try:
            self.milvus.ensure_collection(dense_dim=dense_dim)
            self.milvus.insert(rows)
            inserted_to = "milvus"
        except Exception:
            self.local_store.save(rows)
        self.parent_store.upsert_documents(parent_docs)
        return {
            "indexed_leaf_chunks": len(leaf_docs),
            "indexed_parent_chunks": len(parent_docs),
            "collection": self.settings.milvus_collection,
            "dense_dim": dense_dim,
            "vector_store": inserted_to,
        }

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
        parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) < self.settings.leaf_retrieve_level]
        leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == self.settings.leaf_retrieve_level]
        if not leaf_docs:
            raise ValueError("no_leaf_chunks_to_index")

        leaf_texts = [str(doc.get("text", "")) for doc in leaf_docs]
        self.lexicon.fit(leaf_texts)
        self.lexicon.save()

        rows = []
        for doc in leaf_docs:
            rows.append(
                {
                    "text": doc.get("text", ""),
                    "filename": doc.get("filename", ""),
                    "file_type": doc.get("file_type", "TXT"),
                    "file_path": doc.get("file_path", ""),
                    "page_number": int(doc.get("page_number", 0) or 0),
                    "chunk_idx": int(doc.get("chunk_idx", 0) or 0),
                    "chunk_id": doc.get("chunk_id", ""),
                    "parent_chunk_id": doc.get("parent_chunk_id", ""),
                    "root_chunk_id": doc.get("root_chunk_id", ""),
                    "chunk_level": int(doc.get("chunk_level", self.settings.leaf_retrieve_level) or self.settings.leaf_retrieve_level),
                    "book_name": doc.get("book_name", ""),
                    "chapter_title": doc.get("chapter_title", ""),
                    "section_key": doc.get("section_key", ""),
                }
            )
        if reset_collection and not resume:
            self.files_first_store.reset()
        files_first_meta = self.files_first_store.rebuild(
            rows,
            state_path=state_path,
            reset=reset_collection and not resume,
            show_progress=show_progress,
            batch_size=batch_size,
        )
        self.parent_store.upsert_documents(parent_docs)
        return {
            "indexed_leaf_chunks": len(leaf_docs),
            "indexed_parent_chunks": len(parent_docs),
            "vector_store": "files_first_fts",
            **files_first_meta,
        }

    def _embed_texts_in_batches(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = max(1, int(self.settings.embedding_batch_size or 64))
        batches = [texts[start : start + batch_size] for start in range(0, len(texts), batch_size)]
        total_batches = len(batches)
        workers = max(1, int(self.settings.embedding_batch_workers or 1))
        show_progress = bool(self.settings.embedding_show_progress)

        def _print_progress(completed: int) -> None:
            if not show_progress:
                return
            width = 24
            filled = int(width * completed / max(1, total_batches))
            bar = "#" * filled + "-" * (width - filled)
            pct = completed * 100.0 / max(1, total_batches)
            print(
                f"[retrieval-index] embedding [{bar}] {completed}/{total_batches} ({pct:.1f}%) workers={workers}",
                flush=True,
            )

        def _embed_one(batch_index: int, batch: list[str]) -> tuple[int, list[list[float]]]:
            return batch_index, self.embedding_client.embed(batch, self.settings.embedding_model)

        if workers == 1:
            vectors: list[list[float]] = []
            for batch_index, batch in enumerate(batches):
                _index, embedded = _embed_one(batch_index, batch)
                vectors.extend(embedded)
                _print_progress(batch_index + 1)
            return vectors

        results: dict[int, list[list[float]]] = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(_embed_one, batch_index, batch): batch_index
                for batch_index, batch in enumerate(batches)
            }
            for future in as_completed(future_map):
                batch_index, embedded = future.result()
                results[batch_index] = embedded
                completed += 1
                _print_progress(completed)

        vectors: list[list[float]] = []
        for batch_index in range(total_batches):
            vectors.extend(results.get(batch_index, []))
        return vectors

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
        return self.index_corpus_files_with_options(corpus_paths, reset_collection=reset_collection, index_mode=index_mode)

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
        resolved_paths = [path for path in corpus_paths if path.exists()]
        if not resolved_paths:
            raise ValueError("no_corpus_files_found")
        combined_docs: list[dict[str, Any]] = []
        for path in resolved_paths:
            combined_docs.extend(self._load_corpus_file(path))
        docs = self._dedupe_docs(combined_docs)
        if (index_mode or "hybrid").strip().lower() == "files_first":
            result = self.index_documents_files_first(
                docs,
                reset_collection=reset_collection,
                state_path=files_first_state_path,
                resume=files_first_resume,
                show_progress=files_first_show_progress,
                batch_size=files_first_batch_size,
            )
        else:
            result = self.index_documents(docs, reset_collection=reset_collection)
        result["corpus_files"] = [str(path) for path in resolved_paths]
        result["indexed_documents"] = len(docs)
        result["index_mode"] = (index_mode or "hybrid").strip().lower()
        return result

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
        corpus_paths: list[Path] = []
        if include_sample and self.settings.sample_corpus_path.exists():
            corpus_paths.append(self.settings.sample_corpus_path)
        if include_modern and self.settings.modern_corpus_path.exists():
            corpus_paths.append(self.settings.modern_corpus_path)
        if include_classic and self.settings.classic_corpus_path.exists():
            corpus_paths.append(self.settings.classic_corpus_path)
        return self.index_corpus_files_with_options(
            corpus_paths,
            reset_collection=reset_collection,
            index_mode=index_mode,
            files_first_state_path=files_first_state_path,
            files_first_resume=files_first_resume,
            files_first_show_progress=files_first_show_progress,
            files_first_batch_size=files_first_batch_size,
        )

    def index_sample_corpus(self, *, reset_collection: bool = False) -> dict[str, Any]:
        return self.index_corpus_files([self.settings.sample_corpus_path], reset_collection=reset_collection)

    @staticmethod
    def _normalize_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": item.get("chunk_id", ""),
            "embedding_id": item.get("embedding_id", ""),
            "collection": item.get("collection", ""),
            "text": str(item.get("text", "")).strip(),
            "document": str(item.get("document", "")).strip(),
            "answer": str(item.get("answer", "")).strip(),
            "source_file": item.get("source_file", "caseqa"),
            "source_page": item.get("source_page"),
            "score": float(item.get("score", 0.0) or 0.0),
            "distance": float(item.get("distance", 0.0) or 0.0),
            "rerank_score": float(item.get("rerank_score", 0.0) or 0.0),
            "metadata": item.get("metadata", {}),
        }

    @staticmethod
    def _normalize_structured_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        record_id = str(item.get("record_id", "")).strip()
        collection = str(item.get("collection", "")).strip() or "qa_structured_case"
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        symptom_text = str(item.get("symptom_text", "")).strip()
        syndrome_text = str(item.get("syndrome_text", "")).strip()
        formula_text = str(item.get("formula_text", "")).strip()
        summary_parts = [question, symptom_text, syndrome_text, formula_text]
        document = "\n".join(part for part in summary_parts if part)
        return {
            "chunk_id": record_id,
            "embedding_id": str(item.get("embedding_id", "")).strip() or record_id,
            "collection": collection,
            "text": answer or question,
            "document": document,
            "answer": answer,
            "source_file": f"caseqa:{collection}",
            "source_page": None,
            "score": float(item.get("_rerank_score", 0.0) or 0.0),
            "distance": 0.0,
            "rerank_score": float(item.get("_rerank_score", 0.0) or 0.0),
            "metadata": {
                "record_id": record_id,
                "question": question,
                "answer": answer,
                "age": str(item.get("age", "")).strip(),
                "sex": str(item.get("sex", "")).strip(),
                "chief_complaint": str(item.get("chief_complaint", "")).strip(),
                "history": str(item.get("history", "")).strip(),
                "tongue": str(item.get("tongue", "")).strip(),
                "pulse": str(item.get("pulse", "")).strip(),
                "symptom_text": symptom_text,
                "syndrome_text": syndrome_text,
                "formula_text": formula_text,
            },
        }

    def _auto_merge(self, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        meta = {
            "auto_merge_enabled": self.settings.auto_merge_enabled,
            "auto_merge_applied": False,
            "auto_merge_threshold": self.settings.auto_merge_threshold,
            "auto_merge_replaced_chunks": 0,
            "auto_merge_steps": 0,
        }
        if not self.settings.auto_merge_enabled or not docs:
            return docs[:top_k], meta

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for doc in docs:
            parent_id = str(doc.get("parent_chunk_id", "")).strip()
            if parent_id:
                groups[parent_id].append(doc)

        target_parent_ids = [
            parent_id for parent_id, children in groups.items()
            if len(children) >= self.settings.auto_merge_threshold
        ]
        if not target_parent_ids:
            return docs[:top_k], meta

        parent_map = {
            item.get("chunk_id", ""): item
            for item in self.parent_store.get_documents_by_ids(target_parent_ids)
            if item.get("chunk_id")
        }
        merged_docs: list[dict[str, Any]] = []
        replaced_count = 0
        for doc in docs:
            parent_id = str(doc.get("parent_chunk_id", "")).strip()
            if not parent_id or parent_id not in parent_map:
                merged_docs.append(doc)
                continue
            parent_doc = dict(parent_map[parent_id])
            parent_doc["score"] = max(float(parent_doc.get("score", 0.0)), float(doc.get("score", 0.0)))
            if doc.get("match_snippet") and not parent_doc.get("match_snippet"):
                parent_doc["match_snippet"] = doc.get("match_snippet")
            parent_doc["merged_from_children"] = True
            parent_doc["merged_child_count"] = len(groups[parent_id])
            merged_docs.append(parent_doc)
            replaced_count += 1

        deduped: list[dict[str, Any]] = []
        seen = set()
        for item in merged_docs:
            key = item.get("chunk_id") or (item.get("filename"), item.get("page_number"), item.get("text"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        deduped.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        meta.update(
            {
                "auto_merge_applied": replaced_count > 0,
                "auto_merge_replaced_chunks": replaced_count,
                "auto_merge_steps": 1 if replaced_count > 0 else 0,
            }
        )
        return deduped[:top_k], meta

    def _apply_lexical_sanity_gate(
        self,
        query: str,
        docs: list[dict[str, Any]],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if not docs:
            return docs
        anchors = self._extract_query_anchors(query)
        if not anchors:
            return docs

        filtered = [item for item in docs if self._doc_matches_anchors(item, anchors)]
        if len(filtered) == len(docs):
            return docs
        if filtered:
            warnings.append(f"lexical_sanity_filtered:{len(docs)}->{len(filtered)}")
            return filtered
        warnings.append("lexical_sanity_filtered_all")
        return docs

    @staticmethod
    def _doc_matches_anchors(item: dict[str, Any], anchors: list[str]) -> bool:
        haystacks = [
            str(item.get("text", "") or ""),
            str(item.get("source_file", "") or ""),
            str(item.get("filename", "") or ""),
            str(item.get("file_path", "") or ""),
            str(item.get("book_name", "") or ""),
            str(item.get("chapter_title", "") or ""),
            str(item.get("section_summary", "") or ""),
            str(item.get("topic_tags", "") or ""),
            str(item.get("entity_tags", "") or ""),
        ]
        joined = "\n".join(part for part in haystacks if part).lower()
        for anchor in anchors:
            probe = anchor.lower()
            if probe and probe in joined:
                return True
        return False

    @staticmethod
    def _extract_query_anchors(query: str) -> list[str]:
        anchors: list[str] = []
        try:
            analysis = analyze_tcm_query(query)
            for item in analysis.matched_entities:
                if "source_book" in item.types:
                    continue
                name = str(item.name).strip()
                if len(name) >= 2:
                    anchors.append(name)
        except Exception:
            pass

        for match in re.finditer(r"《([^》]{2,24})》", query):
            anchors.append(str(match.group(1)).strip())
        for match in re.finditer(r"([\u4e00-\u9fff]{2,24}?)(?:里|中)(?!医|药|方)", query):
            candidate = str(match.group(1)).strip()
            if len(candidate) >= 2:
                anchors.append(candidate)
        for match in re.finditer(r"[\u4e00-\u9fff]{2,10}(?:经|论|方论|心典|浅注|集解|方|本草)", query):
            anchors.append(str(match.group(0)).strip())

        for match in re.finditer(r"[\u4e00-\u9fff]{2,10}(?:丸|散|汤|饮|膏|丹|颗粒|胶囊)", query):
            anchors.append(match.group(0))
        for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9\-]{1,14}\b", query):
            token = match.group(0)
            if len(token) >= 2:
                anchors.append(token)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in anchors:
            normalized = str(item).strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped

    def _rerank(self, query: str, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], bool, str | None]:
        payload = {
            "model": self.settings.rerank_model,
            "query": query,
            "documents": [doc.get("text", "") for doc in docs],
            "top_n": min(top_k, len(docs)),
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.rerank_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(self.settings.rerank_endpoint, headers=headers, json=payload, timeout=15.0)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            reranked: list[dict[str, Any]] = []
            for item in results:
                index = item.get("index")
                if isinstance(index, int) and 0 <= index < len(docs):
                    doc = dict(docs[index])
                    if item.get("relevance_score") is not None:
                        doc["rerank_score"] = float(item["relevance_score"])
                    reranked.append(doc)
            return (reranked or docs[:top_k], True, None if reranked else "empty_rerank_results")
        except Exception as exc:
            return docs[:top_k], False, str(exc)

    def read_section(self, path: str, *, top_k: int = 12) -> dict[str, Any]:
        payload = self.files_first_store.read_section(path=path, top_k=top_k)
        return _build_section_response(path=path, payload=payload, parent_store=self.parent_store)

    @staticmethod
    def _filter_docs_by_file_path_prefixes(
        docs: list[dict[str, Any]],
        prefixes: list[str] | None,
    ) -> list[dict[str, Any]]:
        normalized = [str(item or "").strip() for item in (prefixes or []) if str(item or "").strip()]
        if not normalized:
            return docs
        filtered: list[dict[str, Any]] = []
        for item in docs:
            file_path = str(item.get("file_path", "") or "").strip()
            if any(file_path.startswith(prefix) for prefix in normalized):
                filtered.append(item)
        return filtered

_retrieval_engine: RetrievalEngine | None = None


def get_retrieval_engine() -> RetrievalEngine:
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine
