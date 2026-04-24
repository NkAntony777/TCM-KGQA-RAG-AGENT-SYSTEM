from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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
