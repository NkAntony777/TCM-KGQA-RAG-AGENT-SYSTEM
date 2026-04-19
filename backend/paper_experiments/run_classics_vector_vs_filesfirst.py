from __future__ import annotations

import argparse
import json
import os
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.classics_vector_sqlite_store import ClassicsVectorSQLiteStore
from services.qa_service.alias_service import get_runtime_alias_service
from services.retrieval_service.engine import RetrievalEngine
from services.retrieval_service.settings import load_settings


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "paper" / "classics_vector_vs_filesfirst_seed_20.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "classics_vector_vs_filesfirst_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Classics_Vector_vs_FilesFirst_Latest.md"
DEFAULT_SQLITE_DB = BACKEND_ROOT / "storage" / "classics_vector_store.sqlite"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    task_family: str
    difficulty: str
    query: str
    expected_books_any: tuple[str, ...]
    expected_chapters_any: tuple[str, ...]
    expected_keywords_any: tuple[str, ...]
    preferred_terms: tuple[str, ...]
    gold_answer_outline: tuple[str, ...]
    gold_evidence_any: tuple[str, ...]


def _load_cases(path: Path) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    cases: list[EvalCase] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id", "")).strip()
        query = str(item.get("query", "")).strip()
        books = tuple(str(part).strip() for part in item.get("expected_books_any", []) if str(part).strip())
        chapters = tuple(str(part).strip() for part in item.get("expected_chapters_any", []) if str(part).strip())
        keywords = tuple(str(part).strip() for part in item.get("expected_keywords_any", []) if str(part).strip())
        preferred_terms = tuple(str(part).strip() for part in item.get("preferred_terms", []) if str(part).strip())
        gold_answer_outline = tuple(str(part).strip() for part in item.get("gold_answer_outline", []) if str(part).strip())
        gold_evidence_any = tuple(str(part).strip() for part in item.get("gold_evidence_any", []) if str(part).strip())
        if not case_id or not query or not (books or chapters or keywords):
            continue
        cases.append(
            EvalCase(
                case_id=case_id,
                category=str(item.get("category", "custom")).strip() or "custom",
                task_family=str(item.get("task_family", "retrieval")).strip() or "retrieval",
                difficulty=str(item.get("difficulty", "unknown")).strip() or "unknown",
                query=query,
                expected_books_any=books,
                expected_chapters_any=chapters,
                expected_keywords_any=keywords,
                preferred_terms=preferred_terms,
                gold_answer_outline=gold_answer_outline,
                gold_evidence_any=gold_evidence_any,
            )
        )
    return cases


def _build_engine(*, vector_enabled: bool, files_first_dense_fallback_enabled: bool) -> RetrievalEngine:
    os.environ["RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED"] = "true" if vector_enabled else "false"
    os.environ["FILES_FIRST_DENSE_FALLBACK_ENABLED"] = "true" if files_first_dense_fallback_enabled else "false"
    settings = load_settings()
    return RetrievalEngine(settings)


def _prepare_query(query: str) -> str:
    normalized = str(query or "").strip()
    if not normalized:
        return ""
    alias_service = get_runtime_alias_service()
    if not alias_service.is_available():
        return normalized
    focus_entities = alias_service.detect_entities(normalized, limit=3)
    return alias_service.expand_query_with_aliases(
        normalized,
        focus_entities=focus_entities,
        max_aliases_per_entity=3,
        max_entities=2,
    )


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(row.get("text", "") or ""),
            str(row.get("filename", "") or ""),
            str(row.get("file_path", "") or ""),
            str(row.get("book_name", "") or ""),
            str(row.get("chapter_title", "") or ""),
            str(row.get("match_snippet", "") or ""),
            str(row.get("section_summary", "") or ""),
            str(row.get("topic_tags", "") or ""),
            str(row.get("entity_tags", "") or ""),
        ]
    )


def _trim_rows(rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for row in rows[:top_k]:
        trimmed.append(
            {
                "chunk_id": row.get("chunk_id"),
                "filename": row.get("filename"),
                "file_path": row.get("file_path"),
                "page_number": row.get("page_number"),
                "book_name": row.get("book_name"),
                "chapter_title": row.get("chapter_title"),
                "score": row.get("score"),
                "rrf_rank": row.get("rrf_rank"),
                "match_snippet": row.get("match_snippet"),
                "section_summary": row.get("section_summary"),
            }
        )
    return trimmed


def _normalize_text(value: str) -> str:
    return "".join(str(value or "").strip().split())


def _normalize_loose_text(value: str) -> str:
    return (
        str(value or "")
        .replace("《", "")
        .replace("》", "")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .replace("'", "")
        .replace("，", "")
        .replace(",", "")
        .replace("。", "")
        .replace("：", "")
        .replace(":", "")
        .replace("；", "")
        .replace(";", "")
        .replace("、", "")
        .replace("（", "")
        .replace("）", "")
        .replace("(", "")
        .replace(")", "")
        .replace("\n", "")
        .replace("\r", "")
        .replace("\t", "")
        .replace(" ", "")
        .strip()
    )


def _matches_expected(value: str, expected_values: tuple[str, ...]) -> bool:
    normalized_value = _normalize_text(value)
    if not normalized_value:
        return False
    for expected in expected_values:
        normalized_expected = _normalize_text(expected)
        if not normalized_expected:
            continue
        if normalized_value == normalized_expected or normalized_expected in normalized_value or normalized_value in normalized_expected:
            return True
    return False


def _row_matches_book(row: dict[str, Any], expected_books: tuple[str, ...]) -> bool:
    if not expected_books:
        return False
    values = (
        str(row.get("book_name", "") or ""),
        str(row.get("filename", "") or ""),
        str(row.get("file_path", "") or ""),
    )
    return any(_matches_expected(value, expected_books) for value in values)


def _row_matches_chapter(row: dict[str, Any], expected_chapters: tuple[str, ...]) -> bool:
    if not expected_chapters:
        return False
    values = (
        str(row.get("chapter_title", "") or ""),
        str(row.get("section_key", "") or ""),
        str(row.get("match_snippet", "") or ""),
    )
    return any(_matches_expected(value, expected_chapters) for value in values)


def _row_matches_evidence(row: dict[str, Any], expected_evidence: tuple[str, ...]) -> bool:
    if not expected_evidence:
        return False
    row_text = _normalize_loose_text(_row_text(row))
    if not row_text:
        return False
    for evidence in expected_evidence:
        snippet = _normalize_loose_text(str(evidence or ""))[:24]
        if len(snippet) < 8:
            continue
        if snippet in row_text:
            return True
    return False


def _reciprocal_rank(relevances: list[int]) -> float:
    for index, value in enumerate(relevances, start=1):
        if value > 0:
            return round(1.0 / index, 4)
    return 0.0


def _ndcg_at_k(relevances: list[int]) -> float:
    if not relevances:
        return 0.0

    def _dcg(values: list[int]) -> float:
        score = 0.0
        for index, rel in enumerate(values, start=1):
            if rel <= 0:
                continue
            score += float(rel) / math.log2(index + 1)
        return score

    ideal = sorted(relevances, reverse=True)
    ideal_dcg = _dcg(ideal)
    if ideal_dcg <= 0:
        return 0.0
    return round(_dcg(relevances) / ideal_dcg, 4)


def _term_match(left: str, right: str) -> bool:
    a = _normalize_loose_text(left)
    b = _normalize_loose_text(right)
    if len(a) < 2 or len(b) < 2:
        return False
    return a == b or a in b or b in a


def _answer_keypoints(case: EvalCase) -> list[str]:
    merged = list(case.gold_answer_outline or ()) + list(case.preferred_terms or ()) + list(case.expected_keywords_any or ())
    deduped: list[str] = []
    seen: set[str] = set()
    for item in merged:
        normalized = _normalize_loose_text(item)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(str(item).strip())
    return deduped


def _answer_metrics(rows: list[dict[str, Any]], case: EvalCase, *, top_k: int) -> dict[str, Any]:
    targets = _answer_keypoints(case)
    if not targets:
        return {
            "top1_answer_hit": None,
            "topk_answer_hit": None,
            "matched_answer_keypoints": [],
            "answer_keypoint_precision": None,
            "answer_keypoint_recall": None,
            "answer_keypoint_f1": None,
        }
    selected = rows[:top_k]
    top1_text = _normalize_loose_text(_row_text(selected[0])) if selected else ""
    joined = _normalize_loose_text("\n".join(_row_text(row) for row in selected))
    matched = [target for target in targets if _normalize_loose_text(target) in joined]
    top1_hit = any(_normalize_loose_text(target) in top1_text for target in targets)
    predicted_units = [
        _normalize_loose_text(str(row.get("match_snippet", "") or _row_text(row)))
        for row in selected
        if _normalize_loose_text(str(row.get("match_snippet", "") or _row_text(row)))
    ]
    matched_predicted = [
        item
        for item in predicted_units
        if any(_term_match(item, target) for target in targets)
    ]
    precision = len(matched_predicted) / max(1, len(predicted_units)) if predicted_units else 0.0
    recall = len(matched) / max(1, len(targets))
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "top1_answer_hit": top1_hit,
        "topk_answer_hit": bool(matched),
        "matched_answer_keypoints": matched,
        "answer_keypoint_precision": round(precision, 4),
        "answer_keypoint_recall": round(recall, 4),
        "answer_keypoint_f1": round(f1, 4),
    }


def _metrics(rows: list[dict[str, Any]], case: EvalCase, *, top_k: int) -> dict[str, Any]:
    selected = rows[:top_k]
    joined = "\n".join(_row_text(row) for row in selected)
    top1 = selected[0] if selected else {}
    top1_text = _row_text(top1) if top1 else ""
    matched_books = [
        book
        for book in case.expected_books_any
        if book and any(_matches_expected(str(row.get("book_name", "") or ""), (book,)) for row in selected)
    ]
    matched_chapters = [
        chapter
        for chapter in case.expected_chapters_any
        if chapter and any(_row_matches_chapter(row, (chapter,)) for row in selected)
    ]
    matched_keywords = [keyword for keyword in case.expected_keywords_any if keyword and keyword in joined]
    matched_evidence = [
        evidence
        for evidence in case.gold_evidence_any
        if evidence and any(_row_matches_evidence(row, (evidence,)) for row in selected)
    ]
    top1_book_hit = _row_matches_book(top1, case.expected_books_any)
    top1_chapter_hit = _row_matches_chapter(top1, case.expected_chapters_any)
    top1_keyword_hit = any(keyword and keyword in top1_text for keyword in case.expected_keywords_any)
    top1_evidence_hit = _row_matches_evidence(top1, case.gold_evidence_any)
    source_relevances = [
        1
        if (
            _row_matches_chapter(row, case.expected_chapters_any)
            if case.expected_chapters_any
            else _row_matches_book(row, case.expected_books_any)
        )
        else 0
        for row in selected
    ]
    answer_metrics = _answer_metrics(selected, case, top_k=top_k)
    top1_provenance_hit = top1_book_hit and (
        top1_chapter_hit if case.expected_chapters_any else True
    )
    topk_provenance_hit = bool(matched_books) and (
        bool(matched_chapters) if case.expected_chapters_any else True
    )
    metrics = {
        "top1_book_hit": top1_book_hit,
        "top1_chapter_hit": top1_chapter_hit if case.expected_chapters_any else None,
        "top1_keyword_hit": top1_keyword_hit,
        "top1_evidence_hit": top1_evidence_hit if case.gold_evidence_any else None,
        "topk_book_hit": bool(matched_books),
        "topk_chapter_hit": bool(matched_chapters) if case.expected_chapters_any else None,
        "topk_keyword_hit": bool(matched_keywords),
        "topk_evidence_hit": bool(matched_evidence) if case.gold_evidence_any else None,
        "top1_provenance_hit": top1_provenance_hit,
        "topk_provenance_hit": topk_provenance_hit,
        "book_hit_rate_case": round(len(matched_books) / max(1, len(case.expected_books_any)), 4) if case.expected_books_any else None,
        "chapter_hit_rate_case": round(len(matched_chapters) / max(1, len(case.expected_chapters_any)), 4) if case.expected_chapters_any else None,
        "keyword_hit_rate_case": round(len(matched_keywords) / max(1, len(case.expected_keywords_any)), 4) if case.expected_keywords_any else None,
        "evidence_hit_rate_case": round(len(matched_evidence) / max(1, len(case.gold_evidence_any)), 4) if case.gold_evidence_any else None,
        "source_mrr": _reciprocal_rank(source_relevances),
        "source_ndcg": _ndcg_at_k(source_relevances),
        "matched_books": matched_books,
        "matched_chapters": matched_chapters,
        "matched_keywords": matched_keywords,
        "matched_evidence": matched_evidence,
    }
    metrics.update(answer_metrics)
    metrics["top1_answer_provenance_hit"] = (
        top1_provenance_hit and bool(answer_metrics["top1_answer_hit"])
        if answer_metrics["top1_answer_hit"] is not None
        else None
    )
    metrics["topk_answer_provenance_hit"] = (
        topk_provenance_hit and bool(answer_metrics["topk_answer_hit"])
        if answer_metrics["topk_answer_hit"] is not None
        else None
    )
    return metrics


def _p95_latency(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    latencies = sorted(float(item["latency_ms"]) for item in rows)
    index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    return round(latencies[index], 1)


def _rate(
    rows: list[dict[str, Any]],
    field: str,
) -> float | None:
    present = [item for item in rows if item["metrics"].get(field) is not None]
    if not present:
        return None
    return round(sum(1 for item in present if item["metrics"].get(field)) / max(1, len(present)), 4)


def _average_metric(rows: list[dict[str, Any]], field: str) -> float | None:
    present = [float(item["metrics"][field] or 0.0) for item in rows if item["metrics"].get(field) is not None]
    if not present:
        return None
    return round(statistics.mean(present), 4)


def _summarize_condition_rows(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": label,
        "cases": rows,
        "avg_latency_ms": round(statistics.mean(float(item["latency_ms"]) for item in rows), 1) if rows else None,
        "p95_latency_ms": _p95_latency(rows),
        "top1_book_hit_rate": _rate(rows, "top1_book_hit"),
        "top1_chapter_hit_rate": _rate(rows, "top1_chapter_hit"),
        "top1_keyword_hit_rate": _rate(rows, "top1_keyword_hit"),
        "top1_evidence_hit_rate": _rate(rows, "top1_evidence_hit"),
        "topk_book_hit_rate": _rate(rows, "topk_book_hit"),
        "topk_chapter_hit_rate": _rate(rows, "topk_chapter_hit"),
        "topk_keyword_hit_rate": _rate(rows, "topk_keyword_hit"),
        "topk_evidence_hit_rate": _rate(rows, "topk_evidence_hit"),
        "top1_provenance_hit_rate": _rate(rows, "top1_provenance_hit"),
        "topk_provenance_hit_rate": _rate(rows, "topk_provenance_hit"),
        "top1_answer_hit_rate": _rate(rows, "top1_answer_hit"),
        "topk_answer_hit_rate": _rate(rows, "topk_answer_hit"),
        "top1_answer_provenance_hit_rate": _rate(rows, "top1_answer_provenance_hit"),
        "topk_answer_provenance_hit_rate": _rate(rows, "topk_answer_provenance_hit"),
        "avg_source_mrr": _average_metric(rows, "source_mrr"),
        "avg_source_ndcg": _average_metric(rows, "source_ndcg"),
        "avg_book_hit_rate_case": _average_metric(rows, "book_hit_rate_case"),
        "avg_chapter_hit_rate_case": _average_metric(rows, "chapter_hit_rate_case"),
        "avg_keyword_hit_rate_case": _average_metric(rows, "keyword_hit_rate_case"),
        "avg_evidence_hit_rate_case": _average_metric(rows, "evidence_hit_rate_case"),
        "avg_answer_keypoint_precision": _average_metric(rows, "answer_keypoint_precision"),
        "avg_answer_keypoint_recall": _average_metric(rows, "answer_keypoint_recall"),
        "avg_answer_keypoint_f1": _average_metric(rows, "answer_keypoint_f1"),
    }


def _search(
    engine: RetrievalEngine,
    *,
    query: str,
    top_k: int,
    candidate_k: int,
    mode: str,
) -> dict[str, Any]:
    prepared_query = _prepare_query(query)
    if mode == "files_first":
        return engine.search_hybrid(
            query=prepared_query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=False,
            search_mode="files_first",
            allowed_file_path_prefixes=["classic://"],
        )
    return engine.search_hybrid(
        query=prepared_query,
        top_k=top_k,
        candidate_k=candidate_k,
        enable_rerank=False,
        search_mode="hybrid",
        allowed_file_path_prefixes=["classic://"],
    )


def _search_vector_sqlite(
    store: ClassicsVectorSQLiteStore,
    engine: RetrievalEngine,
    *,
    query: str,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    prepared_query = _prepare_query(query)
    return store.search_hybrid(
        engine=engine,
        query=prepared_query,
        top_k=top_k,
        candidate_k=candidate_k,
    )


def _run_condition(
    *,
    label: str,
    engine: RetrievalEngine,
    mode: str,
    cases: list[EvalCase],
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        started = time.perf_counter()
        result = _search(engine, query=case.query, top_k=top_k, candidate_k=candidate_k, mode=mode)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        chunks = [item for item in result.get("chunks", []) if isinstance(item, dict)]
        metrics = _metrics(chunks, case, top_k=top_k)
        row = {
            "case": {
                "case_id": case.case_id,
                "category": case.category,
                "task_family": case.task_family,
                "difficulty": case.difficulty,
                "query": case.query,
                "expected_books_any": list(case.expected_books_any),
                "expected_chapters_any": list(case.expected_chapters_any),
                "expected_keywords_any": list(case.expected_keywords_any),
                "preferred_terms": list(case.preferred_terms),
                "gold_answer_outline": list(case.gold_answer_outline),
                "gold_evidence_any": list(case.gold_evidence_any),
            },
            "latency_ms": latency_ms,
            "retrieval_mode": result.get("retrieval_mode"),
            "warnings": result.get("warnings", []),
            "metrics": metrics,
            "rows": _trim_rows(chunks, top_k=top_k),
        }
        rows.append(row)
        print(
            f"[classics-paper] {label} {idx:02d}/{len(cases)} {case.case_id} "
            f"prov_hit={metrics['topk_provenance_hit']} answer_hit={metrics.get('topk_answer_hit')} latency={latency_ms:.1f}ms",
            flush=True,
        )
    return _summarize_condition_rows(label, rows)


def _run_vector_sqlite_condition(
    *,
    label: str,
    engine: RetrievalEngine,
    store: ClassicsVectorSQLiteStore,
    cases: list[EvalCase],
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        started = time.perf_counter()
        result = _search_vector_sqlite(store, engine, query=case.query, top_k=top_k, candidate_k=candidate_k)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        chunks = [item for item in result.get("chunks", []) if isinstance(item, dict)]
        metrics = _metrics(chunks, case, top_k=top_k)
        row = {
            "case": {
                "case_id": case.case_id,
                "category": case.category,
                "task_family": case.task_family,
                "difficulty": case.difficulty,
                "query": case.query,
                "expected_books_any": list(case.expected_books_any),
                "expected_chapters_any": list(case.expected_chapters_any),
                "expected_keywords_any": list(case.expected_keywords_any),
                "preferred_terms": list(case.preferred_terms),
                "gold_answer_outline": list(case.gold_answer_outline),
                "gold_evidence_any": list(case.gold_evidence_any),
            },
            "latency_ms": latency_ms,
            "retrieval_mode": result.get("retrieval_mode"),
            "warnings": result.get("warnings", []),
            "metrics": metrics,
            "rows": _trim_rows(chunks, top_k=top_k),
        }
        rows.append(row)
        print(
            f"[classics-paper] {label} {idx:02d}/{len(cases)} {case.case_id} "
            f"prov_hit={metrics['topk_provenance_hit']} answer_hit={metrics.get('topk_answer_hit')} latency={latency_ms:.1f}ms",
            flush=True,
        )
    return _summarize_condition_rows(label, rows)


def _render_markdown(report: dict[str, Any]) -> str:
    files_first = report["files_first"]
    vector = report["vector"]
    lines = [
        "# Classics Vector vs Files-First Experiment",
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
        "| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| files_first_nonvector | {files_first['avg_latency_ms']} | {files_first['p95_latency_ms']} | {files_first['top1_book_hit_rate']} | {files_first['topk_book_hit_rate']} | {files_first['top1_chapter_hit_rate']} | {files_first['topk_chapter_hit_rate']} | {files_first['top1_evidence_hit_rate']} | {files_first['topk_evidence_hit_rate']} | {files_first['topk_provenance_hit_rate']} | {files_first['topk_answer_hit_rate']} | {files_first['topk_answer_provenance_hit_rate']} | {files_first['avg_answer_keypoint_recall']} | {files_first['avg_source_mrr']} | {files_first['avg_source_ndcg']} |",
        f"| classics_vector_hybrid | {vector['avg_latency_ms']} | {vector['p95_latency_ms']} | {vector['top1_book_hit_rate']} | {vector['topk_book_hit_rate']} | {vector['top1_chapter_hit_rate']} | {vector['topk_chapter_hit_rate']} | {vector['top1_evidence_hit_rate']} | {vector['topk_evidence_hit_rate']} | {vector['topk_provenance_hit_rate']} | {vector['topk_answer_hit_rate']} | {vector['topk_answer_provenance_hit_rate']} | {vector['avg_answer_keypoint_recall']} | {vector['avg_source_mrr']} | {vector['avg_source_ndcg']} |",
        "",
        "## Per Case",
        "",
        "| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    files_map = {item["case"]["case_id"]: item for item in files_first["cases"]}
    vector_map = {item["case"]["case_id"]: item for item in vector["cases"]}
    for case_id, files_row in files_map.items():
        vector_row = vector_map.get(case_id, {})
        lines.append(
            f"| {case_id} | {files_row['case']['category']} | {files_row['case'].get('task_family', '-')} | "
            f"{files_row['metrics']['topk_book_hit']} | {files_row['metrics'].get('topk_evidence_hit', '-')} | {files_row['metrics'].get('topk_provenance_hit', '-')} | {files_row['metrics'].get('topk_answer_hit', '-')} | "
            f"{vector_row.get('metrics', {}).get('topk_book_hit', '-')} | {vector_row.get('metrics', {}).get('topk_evidence_hit', '-')} | {vector_row.get('metrics', {}).get('topk_provenance_hit', '-')} | {vector_row.get('metrics', {}).get('topk_answer_hit', '-')} | "
            f"{files_row['latency_ms']} | {vector_row.get('latency_ms', '-')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper experiment: classics vector retrieval vs files-first retrieval.")
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
    sqlite_store = ClassicsVectorSQLiteStore(args.sqlite_db)
    sqlite_health = sqlite_store.health()
    if not sqlite_health.get("available"):
        raise RuntimeError(f"sqlite_vector_store_unavailable: {args.sqlite_db}")

    files_first_report = _run_condition(
        label="files_first",
        engine=files_first_engine,
        mode="files_first",
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
    )
    vector_report = _run_vector_sqlite_condition(
        label="vector_sqlite",
        engine=vector_engine,
        store=sqlite_store,
        cases=cases,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
    )

    report = {
        "settings": {
            "dataset_path": str(args.dataset),
            "sqlite_db": str(args.sqlite_db),
            "top_k": max(1, int(args.top_k)),
            "candidate_k": max(1, int(args.candidate_k)),
        },
        "sqlite_health": sqlite_health,
        "files_first": files_first_report,
        "vector": vector_report,
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
                "files_first": {
                    "avg_latency_ms": files_first_report["avg_latency_ms"],
                    "topk_provenance_hit_rate": files_first_report["topk_provenance_hit_rate"],
                    "topk_answer_provenance_hit_rate": files_first_report["topk_answer_provenance_hit_rate"],
                },
                "vector": {
                    "avg_latency_ms": vector_report["avg_latency_ms"],
                    "topk_provenance_hit_rate": vector_report["topk_provenance_hit_rate"],
                    "topk_answer_provenance_hit_rate": vector_report["topk_answer_provenance_hit_rate"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
