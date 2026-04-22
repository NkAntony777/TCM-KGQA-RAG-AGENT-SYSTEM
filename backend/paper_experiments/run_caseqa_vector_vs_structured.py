from __future__ import annotations

import argparse
import json
import os
import math
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import RetrievalEngine
from services.retrieval_service.settings import load_settings
from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings
from paper_experiments.experiment_env import collect_experiment_environment


DEFAULT_INDEX_PATH = BACKEND_ROOT / "storage" / "qa_structured_index.sqlite"
DEFAULT_QA_INPUT = BACKEND_ROOT / "services" / "retrieval_service" / "data" / "case_qa_clean" / "qa_fts_ready.jsonl"
DEFAULT_CASE_INPUT = BACKEND_ROOT / "services" / "retrieval_service" / "data" / "case_qa_clean" / "case_fts_ready.jsonl"
DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "paper" / "caseqa_vector_vs_structured_seed_12.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "caseqa_vector_vs_structured_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "CaseQA_Vector_vs_Structured_Latest.md"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    mode: str
    query: str
    expected_keywords: tuple[str, ...]
    preferred_terms: tuple[str, ...]
    gold_answer_outline: tuple[str, ...]


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
        expected_keywords = tuple(
            str(part).strip()
            for part in item.get("expected_keywords", [])
            if str(part).strip()
        )
        preferred_terms = tuple(
            str(part).strip()
            for part in item.get("preferred_terms", [])
            if str(part).strip()
        )
        gold_answer_outline = tuple(
            str(part).strip()
            for part in item.get("gold_answer_outline", [])
            if str(part).strip()
        )
        if not case_id or not query or not expected_keywords:
            continue
        cases.append(
            EvalCase(
                case_id=case_id,
                category=str(item.get("category", "custom")).strip() or "custom",
                mode=str(item.get("mode", "case")).strip() or "case",
                query=query,
                expected_keywords=expected_keywords,
                preferred_terms=preferred_terms,
                gold_answer_outline=gold_answer_outline,
            )
        )
    return cases


def _structured_search(index: StructuredQAIndex, case: EvalCase, *, top_k: int) -> list[dict[str, Any]]:
    if case.mode == "qa":
        return index.search_qa(case.query, top_k=top_k)
    return index.search_case(case.query, top_k=top_k)


def _build_vector_engine() -> RetrievalEngine:
    os.environ["RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED"] = "true"
    os.environ["CASE_QA_VECTOR_FALLBACK_ENABLED"] = "true"
    os.environ["FILES_FIRST_DENSE_FALLBACK_ENABLED"] = "true"
    settings = load_settings()
    return RetrievalEngine(settings)


def _vector_search(engine: RetrievalEngine, case: EvalCase, *, top_k: int, candidate_k: int) -> dict[str, Any]:
    if not engine.embedding_client.is_ready():
        return {
            "available": False,
            "retrieval_mode": "embedding_unconfigured",
            "chunks": [],
            "total": 0,
            "warnings": ["embedding_client_not_configured"],
        }
    case_qa_store = engine.case_qa
    if case_qa_store is None:
        return {
            "available": False,
            "retrieval_mode": "case_qa_vector_store_unavailable",
            "chunks": [],
            "total": 0,
            "warnings": ["case_qa_vector_store_unavailable"],
        }
    dense_vector = engine.embedding_client.embed(
        [case.query],
        engine.settings.case_qa_embedding_model,
        dimensions=engine.settings.case_qa_embedding_dimensions,
    )[0]
    return case_qa_store.search(
        query=case.query,
        query_embedding=dense_vector,
        top_k=top_k,
        candidate_k=candidate_k,
    )


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(row.get("question", "") or ""),
            str(row.get("answer", "") or ""),
            str(row.get("document", "") or ""),
            str(row.get("text", "") or ""),
            str(row.get("formula_text", "") or ""),
            str(row.get("symptom_text", "") or ""),
            str(row.get("syndrome_text", "") or ""),
            str(row.get("chief_complaint", "") or ""),
            str(row.get("history", "") or ""),
            str(row.get("tongue", "") or ""),
            str(row.get("pulse", "") or ""),
        ]
    )


def _trim_rows(rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for row in rows[:top_k]:
        trimmed.append(
            {
                "record_id": row.get("record_id") or row.get("embedding_id") or row.get("chunk_id"),
                "collection": row.get("collection"),
                "bucket": row.get("bucket"),
                "question_type": row.get("question_type"),
                "question": row.get("question") or row.get("document"),
                "answer": row.get("answer") or row.get("text"),
                "formula_text": row.get("formula_text"),
                "symptom_text": row.get("symptom_text"),
                "syndrome_text": row.get("syndrome_text"),
                "chief_complaint": row.get("chief_complaint"),
                "tongue": row.get("tongue"),
                "pulse": row.get("pulse"),
                "score": row.get("score"),
                "rerank_score": row.get("rerank_score"),
                "rank_score": row.get("rank_score"),
            }
        )
    return trimmed


FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方)")
TERM_SPLIT_PATTERN = re.compile(r"[；;，,、/\n|（）()\[\]\s]+")
TERM_SPAN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,12}")
TERM_STOPWORDS = {
    "患者",
    "治疗",
    "症状",
    "表现",
    "主要",
    "包括",
    "什么",
    "为何",
    "为什么",
    "关系",
    "作用",
    "配伍",
    "古籍",
    "出处",
    "原文",
    "方剂",
    "证候",
}


def _normalize_term(value: str) -> str:
    return "".join(str(value or "").strip().split())


def _term_match(left: str, right: str) -> bool:
    a = _normalize_term(left)
    b = _normalize_term(right)
    if len(a) < 2 or len(b) < 2:
        return False
    return a == b or a in b or b in a


def _target_keypoints(case: EvalCase) -> list[str]:
    base = list(case.gold_answer_outline or ())
    if not base:
        base.extend(case.preferred_terms)
    base.extend(case.expected_keywords)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in base:
        normalized = _normalize_term(item)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def _extract_predicted_terms(rows: list[dict[str, Any]], *, top_k: int) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for row in rows[:top_k]:
        for field in ("formula_text", "syndrome_text", "symptom_text", "chief_complaint", "question", "answer", "document", "text"):
            text = str(row.get(field, "") or "")
            if not text:
                continue
            for match in FORMULA_PATTERN.findall(text):
                normalized = _normalize_term(match)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    terms.append(match)
            for part in TERM_SPLIT_PATTERN.split(text):
                cleaned = str(part or "").strip("：:，,。；;、 ")
                normalized = _normalize_term(cleaned)
                if len(normalized) < 2 or len(normalized) > 16 or normalized in seen or normalized in TERM_STOPWORDS:
                    continue
                seen.add(normalized)
                terms.append(cleaned)
            for match in TERM_SPAN_PATTERN.findall(text):
                normalized = _normalize_term(match)
                if len(normalized) < 2 or len(normalized) > 10 or normalized in seen or normalized in TERM_STOPWORDS:
                    continue
                seen.add(normalized)
                terms.append(match)
            if len(terms) >= 24:
                return terms[:24]
    return terms[:24]


def _keypoint_scores(rows: list[dict[str, Any]], case: EvalCase, *, top_k: int) -> dict[str, Any]:
    targets = _target_keypoints(case)
    if not targets:
        return {
            "targets": [],
            "predicted_terms": [],
            "matched_keypoints": [],
            "keypoint_precision": None,
            "keypoint_recall": None,
            "keypoint_f1": None,
        }
    predicted_terms = _extract_predicted_terms(rows, top_k=top_k)
    joined = "\n".join(_row_text(row) for row in rows[:top_k])
    matched_keypoints = [
        target
        for target in targets
        if any(_term_match(target, predicted) for predicted in predicted_terms) or target in joined
    ]
    matched_predicted = [
        predicted
        for predicted in predicted_terms
        if any(_term_match(predicted, target) for target in targets)
    ]
    precision = len(matched_predicted) / max(1, len(predicted_terms)) if predicted_terms else 0.0
    recall = len(matched_keypoints) / max(1, len(targets))
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "targets": targets,
        "predicted_terms": predicted_terms,
        "matched_keypoints": matched_keypoints,
        "keypoint_precision": round(precision, 4),
        "keypoint_recall": round(recall, 4),
        "keypoint_f1": round(f1, 4),
    }


def _coverage_metrics(rows: list[dict[str, Any]], case: EvalCase, *, top_k: int) -> dict[str, Any]:
    selected = rows[:top_k]
    if not selected:
        return {
            "top1_hit": False,
            "topk_hit": False,
            "coverage_any": 0.0,
            "preferred_hit": False,
            "matched_keywords_any": [],
            "matched_preferred_any": [],
            "keypoint_precision": 0.0,
            "keypoint_recall": 0.0,
            "keypoint_f1": 0.0,
            "matched_keypoints": [],
            "target_keypoints": _target_keypoints(case),
        }
    top1_text = _row_text(selected[0])
    joined = "\n".join(_row_text(row) for row in selected)
    matched_keywords_any = [keyword for keyword in case.expected_keywords if keyword in joined]
    matched_preferred_any = [keyword for keyword in case.preferred_terms if keyword in joined]
    keypoint_scores = _keypoint_scores(selected, case, top_k=top_k)
    return {
        "top1_hit": any(keyword in top1_text for keyword in case.expected_keywords),
        "topk_hit": bool(matched_keywords_any),
        "coverage_any": round(len(matched_keywords_any) / max(1, len(case.expected_keywords)), 4),
        "preferred_hit": bool(matched_preferred_any) if case.preferred_terms else None,
        "matched_keywords_any": matched_keywords_any,
        "matched_preferred_any": matched_preferred_any,
        "keypoint_precision": keypoint_scores["keypoint_precision"],
        "keypoint_recall": keypoint_scores["keypoint_recall"],
        "keypoint_f1": keypoint_scores["keypoint_f1"],
        "matched_keypoints": keypoint_scores["matched_keypoints"],
        "target_keypoints": keypoint_scores["targets"],
        "predicted_terms": keypoint_scores["predicted_terms"],
    }


def _p95_latency(blocks: list[dict[str, Any]]) -> float | None:
    if not blocks:
        return None
    values = sorted(float(block.get("latency_ms", 0.0) or 0.0) for block in blocks)
    index = max(0, math.ceil(len(values) * 0.95) - 1)
    return round(values[index], 1)


def _run_structured(index: StructuredQAIndex, case: EvalCase, *, top_k: int) -> dict[str, Any]:
    started = time.perf_counter()
    rows = _structured_search(index, case, top_k=top_k)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
    metrics = _coverage_metrics(rows, case, top_k=top_k)
    return {
        "available": True,
        "latency_ms": latency_ms,
        "retrieval_mode": "structured_nonvector",
        "metrics": metrics,
        "rows": _trim_rows(rows, top_k=top_k),
    }


def _run_vector(engine: RetrievalEngine, case: EvalCase, *, top_k: int, candidate_k: int) -> dict[str, Any]:
    started = time.perf_counter()
    result = _vector_search(engine, case, top_k=top_k, candidate_k=candidate_k)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
    rows = [item for item in result.get("chunks", []) if isinstance(item, dict)]
    metrics = _coverage_metrics(rows, case, top_k=top_k)
    return {
        "available": bool(result.get("available", True)),
        "latency_ms": latency_ms,
        "retrieval_mode": result.get("retrieval_mode"),
        "warnings": result.get("warnings", []),
        "metrics": metrics,
        "rows": _trim_rows(rows, top_k=top_k),
    }


def _aggregate(cases_report: list[dict[str, Any]], key: str) -> dict[str, Any]:
    blocks = [item[key] for item in cases_report if isinstance(item.get(key), dict) and item[key].get("available")]
    if not blocks:
        return {
            "cases": 0,
            "top1_hit_rate": None,
            "topk_hit_rate": None,
            "avg_coverage_any": None,
            "preferred_hit_rate": None,
            "avg_keypoint_precision": None,
            "avg_keypoint_recall": None,
            "avg_keypoint_f1": None,
            "avg_latency_ms": None,
            "p95_latency_ms": None,
        }
    top1_hits = sum(1 for block in blocks if block["metrics"].get("top1_hit"))
    topk_hits = sum(1 for block in blocks if block["metrics"].get("topk_hit"))
    preferred_values = [block["metrics"].get("preferred_hit") for block in blocks if block["metrics"].get("preferred_hit") is not None]
    return {
        "cases": len(blocks),
        "top1_hit_rate": round(top1_hits / len(blocks), 4),
        "topk_hit_rate": round(topk_hits / len(blocks), 4),
        "avg_coverage_any": round(statistics.mean(float(block["metrics"].get("coverage_any", 0.0) or 0.0) for block in blocks), 4),
        "preferred_hit_rate": round(sum(1 for value in preferred_values if value) / len(preferred_values), 4) if preferred_values else None,
        "avg_keypoint_precision": round(statistics.mean(float(block["metrics"].get("keypoint_precision", 0.0) or 0.0) for block in blocks), 4),
        "avg_keypoint_recall": round(statistics.mean(float(block["metrics"].get("keypoint_recall", 0.0) or 0.0) for block in blocks), 4),
        "avg_keypoint_f1": round(statistics.mean(float(block["metrics"].get("keypoint_f1", 0.0) or 0.0) for block in blocks), 4),
        "avg_latency_ms": round(statistics.mean(float(block.get("latency_ms", 0.0) or 0.0) for block in blocks), 1),
        "p95_latency_ms": _p95_latency(blocks),
    }


def _aggregate_by_category(cases_report: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in cases_report:
        grouped.setdefault(str(item["case"]["category"]), []).append(item)
    summary: dict[str, Any] = {}
    for category, rows in grouped.items():
        summary[category] = {
            "structured": _aggregate(rows, "structured"),
            "vector": _aggregate(rows, "vector"),
        }
    return summary


def _render_markdown(report: dict[str, Any]) -> str:
    structured = report["summary"]["structured"]
    vector = report["summary"]["vector"]
    lines = [
        "# Case QA Vector vs Structured Experiment",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {report['settings']['dataset_path']} |",
        f"| top_k | {report['settings']['top_k']} |",
        f"| candidate_k | {report['settings']['candidate_k']} |",
        f"| structured_index | {report['settings']['index_path']} |",
        "",
        "## Aggregate",
        "",
        "| Method | cases | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_precision | avg_keypoint_recall | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms | p95_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| structured_nonvector | {structured['cases']} | {structured['top1_hit_rate']} | {structured['topk_hit_rate']} | {structured['avg_coverage_any']} | {structured['avg_keypoint_precision']} | {structured['avg_keypoint_recall']} | {structured['avg_keypoint_f1']} | {structured['preferred_hit_rate']} | {structured['avg_latency_ms']} | {structured['p95_latency_ms']} |",
        f"| vector_caseqa | {vector['cases']} | {vector['top1_hit_rate']} | {vector['topk_hit_rate']} | {vector['avg_coverage_any']} | {vector['avg_keypoint_precision']} | {vector['avg_keypoint_recall']} | {vector['avg_keypoint_f1']} | {vector['preferred_hit_rate']} | {vector['avg_latency_ms']} | {vector['p95_latency_ms']} |",
        "",
        "## By Category",
        "",
        "| Category | Method | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category, block in sorted(report["category_summary"].items()):
        for method in ("structured", "vector"):
            item = block[method]
            lines.append(
                f"| {category} | {method} | {item['top1_hit_rate']} | {item['topk_hit_rate']} | {item['avg_coverage_any']} | {item['avg_keypoint_f1']} | {item['preferred_hit_rate']} | {item['avg_latency_ms']} |"
            )

    lines.extend(
        [
            "",
            "## Per Case",
            "",
            "| case_id | category | mode | structured_topk_hit | structured_keypoint_f1 | vector_topk_hit | vector_keypoint_f1 | structured_latency | vector_latency |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["cases"]:
        lines.append(
            f"| {row['case']['case_id']} | {row['case']['category']} | {row['case']['mode']} | "
            f"{row['structured']['metrics']['topk_hit']} | {row['structured']['metrics']['keypoint_f1']} | "
            f"{row['vector']['metrics']['topk_hit']} | {row['vector']['metrics']['keypoint_f1']} | "
            f"{row['structured']['latency_ms']} | {row['vector']['latency_ms']} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_experiment(
    *,
    dataset_path: Path,
    index_path: Path,
    qa_input_path: Path,
    case_input_path: Path,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    cases = _load_cases(dataset_path)
    index = StructuredQAIndex(
        StructuredQAIndexSettings(
            index_path=index_path,
            qa_input_path=qa_input_path,
            case_input_path=case_input_path,
        )
    )
    vector_engine = _build_vector_engine()
    engine_health = vector_engine.health()
    cases_report: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        structured = _run_structured(index, case, top_k=top_k)
        vector = _run_vector(vector_engine, case, top_k=top_k, candidate_k=candidate_k)
        row = {
            "case": {
                "case_id": case.case_id,
                "category": case.category,
                "mode": case.mode,
                "query": case.query,
                "expected_keywords": list(case.expected_keywords),
                "preferred_terms": list(case.preferred_terms),
                "gold_answer_outline": list(case.gold_answer_outline),
            },
            "structured": structured,
            "vector": vector,
        }
        cases_report.append(row)
        print(
            f"[caseqa-paper] {idx:02d}/{len(cases)} {case.case_id} "
            f"structured_hit={structured['metrics']['topk_hit']} vector_hit={vector['metrics']['topk_hit']} "
            f"structured_latency={structured['latency_ms']:.1f}ms vector_latency={vector['latency_ms']:.1f}ms",
            flush=True,
        )
    report = {
        "settings": {
            "dataset_path": str(dataset_path),
            "index_path": str(index_path),
            "qa_input_path": str(qa_input_path),
            "case_input_path": str(case_input_path),
            "top_k": top_k,
            "candidate_k": candidate_k,
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "run_caseqa_vector_vs_structured.py",
                "dataset_path": str(dataset_path),
                "index_path": str(index_path),
                "top_k": top_k,
                "candidate_k": candidate_k,
                "latency_semantics": "single-run wall-clock per case on the current local machine; intended for relative comparison within the same rerun",
                "cache_state": "warm process, local structured index and vector backend reused, no explicit cold-start reset between cases",
                "concurrency": "single-process sequential case execution",
            }
        ),
        "health": {
            "structured": index.health(),
            "retrieval_engine": engine_health,
        },
        "summary": {
            "structured": _aggregate(cases_report, "structured"),
            "vector": _aggregate(cases_report, "vector"),
        },
        "category_summary": _aggregate_by_category(cases_report),
        "cases": cases_report,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper experiment: case QA vector retrieval vs structured non-vector retrieval.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--qa-input", type=Path, default=DEFAULT_QA_INPUT)
    parser.add_argument("--case-input", type=Path, default=DEFAULT_CASE_INPUT)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = run_experiment(
        dataset_path=args.dataset,
        index_path=args.index_path,
        qa_input_path=args.qa_input,
        case_input_path=args.case_input,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "structured_summary": report["summary"]["structured"],
                "vector_summary": report["summary"]["vector"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
