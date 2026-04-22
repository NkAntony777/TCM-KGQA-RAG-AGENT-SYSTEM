from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.classics_vector_sqlite_store import blob_to_dense
from paper_experiments.experiment_env import collect_experiment_environment
from paper_experiments.run_classics_vector_vs_filesfirst import (
    DEFAULT_SQLITE_DB,
    _build_engine,
    _load_cases,
    _metrics,
    _prepare_query,
    _trim_rows,
)


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "paper" / "classics_vector_vs_filesfirst_seed_20.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "classics_baseline_matrix_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Classics_Baseline_Matrix_Latest.md"


def _fts_quote(term: str) -> str:
    return '"' + str(term or "").replace('"', " ").strip() + '"'


def _query_terms(engine, query: str, *, limit: int = 8) -> list[str]:
    tokens = engine.lexicon.tokenize(query)
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        normalized = str(token or "").strip()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _normalize_docs_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "chunk_id": row["chunk_id"],
        "text": row["text"],
        "filename": row["filename"],
        "file_type": row["file_type"],
        "file_path": row["file_path"],
        "page_number": row["page_number"],
        "chunk_idx": row["chunk_idx"],
        "parent_chunk_id": row["parent_chunk_id"],
        "root_chunk_id": row["root_chunk_id"],
        "chunk_level": row["chunk_level"],
        "book_name": row["book_name"],
        "chapter_title": row["chapter_title"],
        "section_key": row["section_key"],
        "section_summary": row["section_summary"],
        "topic_tags": row["topic_tags"],
        "entity_tags": row["entity_tags"],
        "match_snippet": row["match_snippet"],
        "score": float(-(row["rank_score"])),
        "rrf_rank": 0,
    }


def _dedupe_by_section(rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    best_by_section: dict[str, dict[str, Any]] = {}
    for row in rows:
        section_key = str(row.get("section_key") or row.get("chunk_id") or "").strip()
        if not section_key:
            section_key = str(row.get("chunk_id") or "").strip()
        existing = best_by_section.get(section_key)
        if existing is None or float(row.get("score", 0.0) or 0.0) > float(existing.get("score", 0.0) or 0.0):
            best_by_section[section_key] = row
    deduped = sorted(best_by_section.values(), key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)[:top_k]
    for idx, item in enumerate(deduped, start=1):
        item["rrf_rank"] = idx
    return deduped


def _external_bm25_search(engine, *, query: str, top_k: int, candidate_k: int) -> dict[str, Any]:
    store_path = engine.files_first_store.store_path
    if not store_path.exists():
        return {"retrieval_mode": "external_bm25_missing", "chunks": [], "total": 0, "warnings": ["fts_missing"]}
    terms = _query_terms(engine, query, limit=10)
    if not terms:
        return {"retrieval_mode": "external_bm25_empty_query", "chunks": [], "total": 0, "warnings": ["query_terms_empty"]}
    match_expression = " OR ".join(_fts_quote(term) for term in terms)
    with closing(sqlite3.connect(store_path)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT
                    d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,
                    d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                    snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                    bm25(docs_fts) AS rank_score
                FROM docs_fts
                JOIN docs d ON d.chunk_id = docs_fts.chunk_id
                WHERE docs_fts MATCH ? AND d.chunk_level = ? AND d.file_path LIKE 'classic://%'
                ORDER BY rank_score
                LIMIT ?
                """,
                (match_expression, engine.settings.leaf_retrieve_level, max(candidate_k * 4, top_k * 4, 20)),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            return {"retrieval_mode": "external_bm25_error", "chunks": [], "total": 0, "warnings": [str(exc)]}
    normalized = [_normalize_docs_row(row) for row in rows]
    chunks = _dedupe_by_section(normalized, top_k=top_k)
    return {
        "retrieval_mode": "external_bm25_docs",
        "chunks": chunks,
        "total": len(chunks),
        "warnings": [],
    }


def _dense_dot(left: list[float], right_blob: bytes) -> float:
    right = blob_to_dense(right_blob)
    return float(sum(a * b for a, b in zip(left, right)))


def _external_dense_search(engine, *, sqlite_db: Path, query: str, top_k: int, candidate_k: int) -> dict[str, Any]:
    if not sqlite_db.exists():
        return {"retrieval_mode": "external_dense_missing", "chunks": [], "total": 0, "warnings": ["sqlite_db_missing"]}
    if not engine.embedding_client.is_ready():
        return {"retrieval_mode": "external_dense_unconfigured", "chunks": [], "total": 0, "warnings": ["embedding_client_not_configured"]}
    query_terms = _query_terms(engine, query, limit=10)
    if not query_terms:
        return {"retrieval_mode": "external_dense_empty_query", "chunks": [], "total": 0, "warnings": ["query_terms_empty"]}
    match_expression = " OR ".join(_fts_quote(term) for term in query_terms)
    query_embedding = engine.embedding_client.embed([query], engine.settings.embedding_model)[0]
    with closing(sqlite3.connect(sqlite_db)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            candidate_rows = conn.execute(
                """
                SELECT vr.chunk_id, vr.file_path, vr.filename, vr.file_type, vr.page_number, vr.chunk_idx,
                       vr.parent_chunk_id, vr.root_chunk_id, vr.chunk_level, vr.book_name, vr.chapter_title,
                       vr.text, vr.dense_blob
                FROM vector_rows_fts f
                JOIN vector_rows vr ON vr.chunk_id = f.chunk_id
                WHERE vector_rows_fts MATCH ? AND vr.file_path LIKE 'classic://%'
                LIMIT ?
                """,
                (match_expression, max(candidate_k * 8, top_k * 8, 64)),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            return {"retrieval_mode": "external_dense_error", "chunks": [], "total": 0, "warnings": [str(exc)]}
    scored: list[dict[str, Any]] = []
    for row in candidate_rows:
        payload = dict(row)
        payload["section_key"] = f"{payload.get('book_name','')}::{payload.get('chapter_title','')}"
        payload["section_summary"] = ""
        payload["topic_tags"] = ""
        payload["entity_tags"] = ""
        payload["match_snippet"] = str(payload.get("text", "") or "")[:180]
        payload["score"] = _dense_dot(query_embedding, payload.get("dense_blob", b""))
        payload.pop("dense_blob", None)
        scored.append(payload)
    scored.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
    chunks = _dedupe_by_section(scored, top_k=top_k)
    return {
        "retrieval_mode": "external_dense_candidates",
        "chunks": chunks,
        "total": len(chunks),
        "warnings": [],
    }


def _run_method(*, label: str, cases: list[Any], top_k: int, candidate_k: int, search_fn) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        started = time.perf_counter()
        result = search_fn(case.query, top_k=top_k, candidate_k=candidate_k)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        chunks = [item for item in result.get("chunks", []) if isinstance(item, dict)]
        metrics = _metrics(chunks, case, top_k=top_k)
        rows.append(
            {
                "case": {
                    "case_id": case.case_id,
                    "category": case.category,
                    "query": case.query,
                    "expected_books_any": list(case.expected_books_any),
                    "expected_chapters_any": list(case.expected_chapters_any),
                    "expected_keywords_any": list(case.expected_keywords_any),
                },
                "latency_ms": latency_ms,
                "retrieval_mode": result.get("retrieval_mode"),
                "warnings": result.get("warnings", []),
                "metrics": metrics,
                "rows": _trim_rows(chunks, top_k=top_k),
            }
        )
        print(
            f"[classics-baselines] {label} {idx:02d}/{len(cases)} {case.case_id} "
            f"book_hit={metrics['topk_book_hit']} keyword_hit={metrics['topk_keyword_hit']} latency={latency_ms:.1f}ms",
            flush=True,
        )
    latencies = [float(item["latency_ms"]) for item in rows]
    latencies_sorted = sorted(latencies)
    p95 = round(latencies_sorted[max(0, int(len(latencies_sorted) * 0.95 + 0.9999) - 1)], 1) if latencies_sorted else None
    return {
        "label": label,
        "cases": rows,
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "p95_latency_ms": p95,
        "top1_book_hit_rate": round(sum(1 for item in rows if item["metrics"]["top1_book_hit"]) / max(1, len(rows)), 4),
        "top1_chapter_hit_rate": round(
            sum(1 for item in rows if item["metrics"].get("top1_chapter_hit"))
            / max(1, sum(1 for item in rows if item["metrics"].get("top1_chapter_hit") is not None)),
            4,
        )
        if any(item["metrics"].get("top1_chapter_hit") is not None for item in rows)
        else None,
        "top1_keyword_hit_rate": round(sum(1 for item in rows if item["metrics"]["top1_keyword_hit"]) / max(1, len(rows)), 4),
        "topk_book_hit_rate": round(sum(1 for item in rows if item["metrics"]["topk_book_hit"]) / max(1, len(rows)), 4),
        "topk_chapter_hit_rate": round(
            sum(1 for item in rows if item["metrics"].get("topk_chapter_hit"))
            / max(1, sum(1 for item in rows if item["metrics"].get("topk_chapter_hit") is not None)),
            4,
        )
        if any(item["metrics"].get("topk_chapter_hit") is not None for item in rows)
        else None,
        "topk_keyword_hit_rate": round(sum(1 for item in rows if item["metrics"]["topk_keyword_hit"]) / max(1, len(rows)), 4),
        "avg_source_mrr": round(statistics.mean(float(item["metrics"]["source_mrr"]) for item in rows), 4) if rows else None,
        "avg_source_ndcg": round(statistics.mean(float(item["metrics"]["source_ndcg"]) for item in rows), 4) if rows else None,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Classics Baseline Matrix",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {report['settings']['dataset_path']} |",
        f"| top_k | {report['settings']['top_k']} |",
        f"| candidate_k | {report['settings']['candidate_k']} |",
        "",
        "## Aggregate",
        "",
        "| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ("files_first", "external_bm25", "vector_sqlite", "external_dense"):
        item = report[key]
        lines.append(
            f"| {item['label']} | {item['avg_latency_ms']} | {item['p95_latency_ms']} | {item['topk_book_hit_rate']} | {item['topk_chapter_hit_rate']} | {item.get('topk_evidence_hit_rate')} | {item.get('topk_provenance_hit_rate')} | {item.get('topk_answer_hit_rate')} | {item.get('topk_answer_provenance_hit_rate')} | {item.get('avg_answer_keypoint_recall')} | {item['avg_source_mrr']} | {item['avg_source_ndcg']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare internal methods with simple external-style lexical and dense baselines.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_DB)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    cases = _load_cases(args.dataset)
    files_first_engine = _build_engine(vector_enabled=False, files_first_dense_fallback_enabled=False)
    vector_engine = _build_engine(vector_enabled=False, files_first_dense_fallback_enabled=False)

    files_first = _run_method(
        label="files_first_internal",
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
        search_fn=lambda query, top_k, candidate_k: files_first_engine.search_hybrid(
            query=_prepare_query(query),
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=False,
            search_mode="files_first",
            allowed_file_path_prefixes=["classic://"],
        ),
    )
    external_bm25 = _run_method(
        label="external_bm25_docs",
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
        search_fn=lambda query, top_k, candidate_k: _external_bm25_search(
            files_first_engine,
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        ),
    )
    from paper_experiments.classics_vector_sqlite_store import ClassicsVectorSQLiteStore

    store = ClassicsVectorSQLiteStore(args.sqlite_db)
    vector_sqlite = _run_method(
        label="vector_sqlite_internal",
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
        search_fn=lambda query, top_k, candidate_k: store.search_hybrid(
            engine=vector_engine,
            query=_prepare_query(query),
            top_k=top_k,
            candidate_k=candidate_k,
        ),
    )
    external_dense = _run_method(
        label="external_dense_candidates",
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
        search_fn=lambda query, top_k, candidate_k: _external_dense_search(
            vector_engine,
            sqlite_db=args.sqlite_db,
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        ),
    )

    report = {
        "settings": {
            "dataset_path": str(args.dataset),
            "sqlite_db": str(args.sqlite_db),
            "top_k": max(1, int(args.top_k)),
            "candidate_k": max(1, int(args.candidate_k)),
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "run_classics_baseline_matrix.py",
                "dataset_path": str(args.dataset),
                "sqlite_db": str(args.sqlite_db),
                "top_k": max(1, int(args.top_k)),
                "candidate_k": max(1, int(args.candidate_k)),
                "latency_semantics": "single-run wall-clock per case on the current local machine; intended for relative comparison within the same rerun",
                "cache_state": "warm process, prebuilt local indexes reused, no explicit cold-start reset between methods",
                "concurrency": "single-process sequential method and case execution",
            }
        ),
        "files_first": files_first,
        "external_bm25": external_bm25,
        "vector_sqlite": vector_sqlite,
        "external_dense": external_dense,
    }
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
                        "avg_latency_ms": report[key]["avg_latency_ms"],
                        "topk_book_hit_rate": report[key]["topk_book_hit_rate"],
                        "topk_keyword_hit_rate": report[key]["topk_keyword_hit_rate"],
                        "avg_source_mrr": report[key]["avg_source_mrr"],
                    }
                    for key in ("files_first", "external_bm25", "vector_sqlite", "external_dense")
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
