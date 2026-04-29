from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "false")


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.experiment_env import collect_experiment_environment
from paper_experiments.run_classics_baseline_matrix import _run_method
from paper_experiments.run_classics_vector_vs_filesfirst import (
    DEFAULT_DATASET,
    DEFAULT_SQLITE_DB,
    _build_engine,
    _load_cases,
    _prepare_query,
)


DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "classics_framework_baselines_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Classics_Framework_Baselines_Latest.md"
DEFAULT_CACHE_DIR = BACKEND_ROOT / "storage" / "framework_baselines"


@dataclass(frozen=True)
class ClassicRow:
    chunk_id: str
    file_path: str
    filename: str
    file_type: str
    page_number: int
    chunk_idx: int
    parent_chunk_id: str
    root_chunk_id: str
    chunk_level: int
    book_name: str
    chapter_title: str
    text: str

    def as_chunk(self, *, score: float | None = None, rank: int = 0, snippet: str | None = None) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_path": self.file_path,
            "page_number": self.page_number,
            "chunk_idx": self.chunk_idx,
            "parent_chunk_id": self.parent_chunk_id,
            "root_chunk_id": self.root_chunk_id,
            "chunk_level": self.chunk_level,
            "book_name": self.book_name,
            "chapter_title": self.chapter_title,
            "section_key": f"{self.book_name}::{self.chapter_title}",
            "section_summary": "",
            "topic_tags": "",
            "entity_tags": "",
            "match_snippet": snippet if snippet is not None else self.text[:180],
            "score": score,
            "rrf_rank": rank,
        }


def _sqlite_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_classic_rows(sqlite_db: Path, *, max_docs: int | None = None) -> list[ClassicRow]:
    if not sqlite_db.exists():
        raise FileNotFoundError(f"classics_vector_sqlite_not_found: {sqlite_db}")
    limit_sql = " LIMIT ?" if max_docs and max_docs > 0 else ""
    params: tuple[Any, ...] = (int(max_docs),) if max_docs and max_docs > 0 else ()
    with _sqlite_connect(sqlite_db) as conn:
        rows = conn.execute(
            f"""
            SELECT chunk_id, file_path, filename, file_type, page_number, chunk_idx,
                   parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, text
            FROM vector_rows
            WHERE file_path LIKE 'classic://%'
            ORDER BY chunk_id
            {limit_sql}
            """,
            params,
        ).fetchall()
    return [
        ClassicRow(
            chunk_id=str(row["chunk_id"]),
            file_path=str(row["file_path"]),
            filename=str(row["filename"]),
            file_type=str(row["file_type"]),
            page_number=int(row["page_number"]),
            chunk_idx=int(row["chunk_idx"]),
            parent_chunk_id=str(row["parent_chunk_id"]),
            root_chunk_id=str(row["root_chunk_id"]),
            chunk_level=int(row["chunk_level"]),
            book_name=str(row["book_name"] or ""),
            chapter_title=str(row["chapter_title"] or ""),
            text=str(row["text"] or ""),
        )
        for row in rows
    ]


def _detect_dense_dim(sqlite_db: Path) -> int:
    with _sqlite_connect(sqlite_db) as conn:
        row = conn.execute(
            """
            SELECT length(dense_blob) AS bytes
            FROM vector_rows
            WHERE file_path LIKE 'classic://%' AND dense_blob IS NOT NULL
            ORDER BY chunk_id
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise RuntimeError("dense_blob_missing")
    return int(row["bytes"]) // 4


def _matrix_cache_paths(cache_dir: Path, *, row_count: int, dim: int, max_docs: int | None) -> tuple[Path, Path, Path]:
    suffix = f"{row_count}x{dim}" if not max_docs else f"{row_count}x{dim}_max{max_docs}"
    return (
        cache_dir / f"classics_dense_{suffix}.float32",
        cache_dir / f"classics_dense_norms_{suffix}.float32",
        cache_dir / f"classics_dense_{suffix}.meta.json",
    )


def _build_or_load_dense_cache(
    sqlite_db: Path,
    *,
    rows: list[ClassicRow],
    cache_dir: Path,
    max_docs: int | None,
    rebuild: bool,
) -> tuple[np.memmap, np.memmap]:
    dim = _detect_dense_dim(sqlite_db)
    row_count = len(rows)
    matrix_path, norms_path, meta_path = _matrix_cache_paths(
        cache_dir,
        row_count=row_count,
        dim=dim,
        max_docs=max_docs,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    expected_meta = {
        "sqlite_db": str(sqlite_db.resolve()),
        "sqlite_mtime": sqlite_db.stat().st_mtime,
        "row_count": row_count,
        "dim": dim,
        "max_docs": max_docs,
        "row_order": "ORDER BY chunk_id WHERE file_path LIKE classic://%",
        "source": "vector_rows.dense_blob",
    }
    if not rebuild and matrix_path.exists() and norms_path.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
        if all(meta.get(key) == value for key, value in expected_meta.items()):
            matrix = np.memmap(matrix_path, dtype=np.float32, mode="r", shape=(row_count, dim))
            norms = np.memmap(norms_path, dtype=np.float32, mode="r", shape=(row_count,))
            return matrix, norms

    matrix = np.memmap(matrix_path, dtype=np.float32, mode="w+", shape=(row_count, dim))
    norms = np.memmap(norms_path, dtype=np.float32, mode="w+", shape=(row_count,))
    limit_sql = " LIMIT ?" if max_docs and max_docs > 0 else ""
    params: tuple[Any, ...] = (int(max_docs),) if max_docs and max_docs > 0 else ()
    with _sqlite_connect(sqlite_db) as conn:
        cursor = conn.execute(
            f"""
            SELECT chunk_id, dense_blob
            FROM vector_rows
            WHERE file_path LIKE 'classic://%'
            ORDER BY chunk_id
            {limit_sql}
            """,
            params,
        )
        for idx, row in enumerate(cursor):
            blob = row["dense_blob"]
            vector = np.frombuffer(blob, dtype=np.float32)
            if vector.shape[0] != dim:
                raise RuntimeError(f"dense_dim_mismatch: {row['chunk_id']} has {vector.shape[0]}, expected {dim}")
            if idx >= row_count:
                raise RuntimeError("dense_cache_row_overflow")
            matrix[idx, :] = vector
            norms[idx] = float(np.linalg.norm(vector))
            if idx < row_count and rows[idx].chunk_id != str(row["chunk_id"]):
                raise RuntimeError(f"dense_cache_row_order_mismatch: {idx}")
    matrix.flush()
    norms.flush()
    meta_path.write_text(json.dumps(expected_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    matrix = np.memmap(matrix_path, dtype=np.float32, mode="r", shape=(row_count, dim))
    norms = np.memmap(norms_path, dtype=np.float32, mode="r", shape=(row_count,))
    return matrix, norms


class LlamaIndexSQLiteDenseBaseline:
    def __init__(
        self,
        *,
        rows: list[ClassicRow],
        matrix: np.memmap,
        norms: np.memmap,
        embedding_client: Any,
        embedding_model: str,
        similarity: str,
    ) -> None:
        try:
            from llama_index.core.base.base_retriever import BaseRetriever
            from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("llama_index_not_installed") from exc

        class _Retriever(BaseRetriever):
            def __init__(self, outer: "LlamaIndexSQLiteDenseBaseline", top_k: int) -> None:
                super().__init__()
                self._outer = outer
                self._top_k = top_k

            def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
                return self._outer._retrieve_nodes(str(query_bundle.query_str), top_k=self._top_k)

        self._retriever_cls = _Retriever
        self._node_cls = TextNode
        self._node_with_score_cls = NodeWithScore
        self.rows = rows
        self.matrix = matrix
        self.norms = norms
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.similarity = similarity

    def _scores(self, query: str) -> np.ndarray:
        query_embedding = self.embedding_client.embed([query], self.embedding_model)[0]
        query_vector = np.asarray(query_embedding, dtype=np.float32)
        if query_vector.shape[0] != self.matrix.shape[1]:
            raise RuntimeError(f"query_embedding_dim_mismatch: {query_vector.shape[0]} != {self.matrix.shape[1]}")
        scores = np.asarray(self.matrix @ query_vector, dtype=np.float32)
        if self.similarity == "cosine":
            query_norm = float(np.linalg.norm(query_vector))
            denom = np.asarray(self.norms, dtype=np.float32) * max(query_norm, 1e-12)
            scores = scores / np.maximum(denom, 1e-12)
        return scores

    def _retrieve_nodes(self, query: str, *, top_k: int) -> list[Any]:
        scores = self._scores(query)
        k = min(max(1, top_k), scores.shape[0])
        candidate_idx = np.argpartition(scores, -k)[-k:]
        ranked_idx = candidate_idx[np.argsort(scores[candidate_idx])[::-1]]
        results: list[Any] = []
        for rank, row_idx in enumerate(ranked_idx.tolist(), start=1):
            row = self.rows[row_idx]
            node = self._node_cls(
                id_=row.chunk_id,
                text=row.text,
                metadata={
                    "chunk_id": row.chunk_id,
                    "file_path": row.file_path,
                    "filename": row.filename,
                    "file_type": row.file_type,
                    "page_number": row.page_number,
                    "chunk_idx": row.chunk_idx,
                    "parent_chunk_id": row.parent_chunk_id,
                    "root_chunk_id": row.root_chunk_id,
                    "chunk_level": row.chunk_level,
                    "book_name": row.book_name,
                    "chapter_title": row.chapter_title,
                    "rrf_rank": rank,
                },
            )
            results.append(self._node_with_score_cls(node=node, score=float(scores[row_idx])))
        return results

    def search(self, *, query: str, top_k: int, candidate_k: int) -> dict[str, Any]:
        retriever = self._retriever_cls(self, top_k=max(top_k, candidate_k))
        node_results = retriever.retrieve(query)
        chunks: list[dict[str, Any]] = []
        for rank, item in enumerate(node_results[:top_k], start=1):
            meta = dict(item.node.metadata or {})
            chunk_id = str(meta.get("chunk_id") or item.node.node_id)
            row = self.rows_by_id.get(chunk_id)
            if row is None:
                continue
            chunks.append(row.as_chunk(score=float(item.score or 0.0), rank=rank))
        return {
            "retrieval_mode": f"llamaindex_sqlite_dense_{self.similarity}",
            "chunks": chunks,
            "total": len(chunks),
            "warnings": [],
        }

    @property
    def rows_by_id(self) -> dict[str, ClassicRow]:
        if not hasattr(self, "_rows_by_id"):
            self._rows_by_id = {row.chunk_id: row for row in self.rows}
        return self._rows_by_id


class HaystackBM25Baseline:
    def __init__(self, *, rows: list[ClassicRow]) -> None:
        try:
            from haystack import Document
            from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
            from haystack.document_stores.in_memory import InMemoryDocumentStore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("haystack_ai_not_installed") from exc

        self.rows_by_id = {row.chunk_id: row for row in rows}
        self.document_store = InMemoryDocumentStore()
        documents = [
            Document(
                id=row.chunk_id,
                content=row.text,
                meta={
                    "chunk_id": row.chunk_id,
                    "file_path": row.file_path,
                    "filename": row.filename,
                    "file_type": row.file_type,
                    "page_number": row.page_number,
                    "chunk_idx": row.chunk_idx,
                    "parent_chunk_id": row.parent_chunk_id,
                    "root_chunk_id": row.root_chunk_id,
                    "chunk_level": row.chunk_level,
                    "book_name": row.book_name,
                    "chapter_title": row.chapter_title,
                },
            )
            for row in rows
        ]
        self.document_store.write_documents(documents)
        self.retriever = InMemoryBM25Retriever(document_store=self.document_store)

    def search(self, *, query: str, top_k: int, candidate_k: int) -> dict[str, Any]:
        result = self.retriever.run(query=query, top_k=max(top_k, candidate_k))
        chunks: list[dict[str, Any]] = []
        for rank, document in enumerate(result.get("documents", [])[:top_k], start=1):
            meta = dict(document.meta or {})
            row = self.rows_by_id.get(str(meta.get("chunk_id") or document.id))
            if row is None:
                continue
            chunks.append(row.as_chunk(score=float(document.score or 0.0), rank=rank))
        return {
            "retrieval_mode": "haystack_inmemory_bm25_default",
            "chunks": chunks,
            "total": len(chunks),
            "warnings": [],
        }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Classics Framework Baselines",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {report['settings']['dataset_path']} |",
        f"| sqlite_db | {report['settings']['sqlite_db']} |",
        f"| row_count | {report['settings']['row_count']} |",
        f"| top_k | {report['settings']['top_k']} |",
        f"| candidate_k | {report['settings']['candidate_k']} |",
        f"| max_docs | {report['settings'].get('max_docs')} |",
        "",
        "## Aggregate",
        "",
        "| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_keyword | avg_source_mrr | avg_source_ndcg |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in report["method_order"]:
        item = report[key]
        lines.append(
            f"| {item['label']} | {item['avg_latency_ms']} | {item['p95_latency_ms']} | "
            f"{item['topk_book_hit_rate']} | {item['topk_chapter_hit_rate']} | "
            f"{item['topk_keyword_hit_rate']} | {item['avg_source_mrr']} | {item['avg_source_ndcg']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _method_requested(methods: set[str], method: str) -> bool:
    return "all" in methods or method in methods


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    cases = _load_cases(args.dataset)
    if args.limit_cases and args.limit_cases > 0:
        cases = cases[: args.limit_cases]
    rows = _load_classic_rows(args.sqlite_db, max_docs=args.max_docs)
    if not rows:
        raise RuntimeError("classic_rows_empty")

    methods = {method.strip().lower() for method in args.methods.split(",") if method.strip()}
    method_order: list[str] = []
    report: dict[str, Any] = {
        "settings": {
            "dataset_path": str(args.dataset),
            "sqlite_db": str(args.sqlite_db),
            "cache_dir": str(args.cache_dir),
            "row_count": len(rows),
            "top_k": max(1, int(args.top_k)),
            "candidate_k": max(1, int(args.candidate_k)),
            "max_docs": args.max_docs,
            "limit_cases": args.limit_cases,
            "llamaindex_similarity": args.llamaindex_similarity,
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "run_classics_framework_baselines.py",
                "dataset_path": str(args.dataset),
                "sqlite_db": str(args.sqlite_db),
                "cache_dir": str(args.cache_dir),
                "row_count": len(rows),
                "latency_semantics": "single-run wall-clock per case after framework/index setup; setup time is reported separately",
                "vectorization": "reuses existing vector_rows.dense_blob; no corpus re-embedding",
            }
        ),
        "method_order": method_order,
    }

    if _method_requested(methods, "llamaindex"):
        engine = _build_engine(vector_enabled=False, files_first_dense_fallback_enabled=False)
        setup_started = time.perf_counter()
        matrix, norms = _build_or_load_dense_cache(
            args.sqlite_db,
            rows=rows,
            cache_dir=args.cache_dir,
            max_docs=args.max_docs,
            rebuild=bool(args.rebuild_cache),
        )
        llama = LlamaIndexSQLiteDenseBaseline(
            rows=rows,
            matrix=matrix,
            norms=norms,
            embedding_client=engine.embedding_client,
            embedding_model=engine.settings.embedding_model,
            similarity=args.llamaindex_similarity,
        )
        setup_latency_ms = round((time.perf_counter() - setup_started) * 1000.0, 1)
        block = _run_method(
            label="llamaindex_sqlite_dense",
            cases=cases,
            top_k=max(1, int(args.top_k)),
            candidate_k=max(1, int(args.candidate_k)),
            search_fn=lambda query, top_k, candidate_k: llama.search(
                query=_prepare_query(query),
                top_k=top_k,
                candidate_k=candidate_k,
            ),
        )
        block["setup_latency_ms"] = setup_latency_ms
        report["llamaindex"] = block
        method_order.append("llamaindex")

    if _method_requested(methods, "haystack"):
        setup_started = time.perf_counter()
        haystack = HaystackBM25Baseline(rows=rows)
        setup_latency_ms = round((time.perf_counter() - setup_started) * 1000.0, 1)
        block = _run_method(
            label="haystack_inmemory_bm25",
            cases=cases,
            top_k=max(1, int(args.top_k)),
            candidate_k=max(1, int(args.candidate_k)),
            search_fn=lambda query, top_k, candidate_k: haystack.search(
                query=_prepare_query(query),
                top_k=top_k,
                candidate_k=candidate_k,
            ),
        )
        block["setup_latency_ms"] = setup_latency_ms
        report["haystack"] = block
        method_order.append("haystack")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real LlamaIndex and Haystack framework baselines on existing classics assets.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_DB)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--methods", default="all", help="Comma-separated: all,llamaindex,haystack")
    parser.add_argument("--llamaindex-similarity", choices=("cosine", "dot"), default="cosine")
    parser.add_argument("--max-docs", type=int, default=None, help="Limit indexed documents for smoke tests only.")
    parser.add_argument("--limit-cases", type=int, default=None, help="Limit cases for smoke tests only.")
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = run_experiment(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "summary": {
                    key: {
                        "setup_latency_ms": report[key].get("setup_latency_ms"),
                        "avg_latency_ms": report[key]["avg_latency_ms"],
                        "topk_book_hit_rate": report[key]["topk_book_hit_rate"],
                        "topk_keyword_hit_rate": report[key]["topk_keyword_hit_rate"],
                        "avg_source_mrr": report[key]["avg_source_mrr"],
                    }
                    for key in report["method_order"]
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
