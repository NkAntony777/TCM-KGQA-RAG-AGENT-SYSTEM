from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import RetrievalEngine, load_settings


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "section_summary_ablation_10.json"


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    return [item for item in payload if isinstance(item, dict)]


def _build_temp_engine(*, root: Path, use_summary_cache: bool) -> RetrievalEngine:
    settings = load_settings()
    summary_cache_path = settings.section_summary_cache_path if use_summary_cache else (root / "empty_section_summary_cache.sqlite")
    temp_settings = replace(
        settings,
        sparse_lexicon_path=root / "retrieval_sparse_lexicon.json",
        parent_chunk_store_path=root / "retrieval_parent_chunks.json",
        local_index_path=root / "retrieval_local_index.json",
        section_summary_cache_path=summary_cache_path,
    )
    engine = RetrievalEngine(temp_settings)
    return engine


def _rebuild_index(engine: RetrievalEngine) -> dict[str, Any]:
    started = time.perf_counter()
    result = engine.index_configured_corpora(
        reset_collection=True,
        include_sample=True,
        include_modern=True,
        include_classic=True,
        index_mode="files_first",
    )
    result["rebuild_latency_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
    return result


def _keyword_hits(*, text: str, keywords: list[str]) -> int:
    normalized = str(text or "")
    return sum(1 for keyword in keywords if keyword and keyword in normalized)


def _evaluate_hits(query_case: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    expected_book = str(query_case.get("expected_book", "") or "").strip()
    expected_keywords = [str(item).strip() for item in query_case.get("expected_keywords", []) if str(item).strip()] if isinstance(query_case.get("expected_keywords", []), list) else []

    def _haystack(item: dict[str, Any]) -> str:
        parts = [
            str(item.get("book_name", "")),
            str(item.get("chapter_title", "")),
            str(item.get("section_summary", "")),
            str(item.get("topic_tags", "")),
            str(item.get("entity_tags", "")),
            str(item.get("text", "")),
            str(item.get("match_snippet", "")),
        ]
        return "\n".join(parts)

    top1 = chunks[0] if chunks else {}
    top3 = chunks[:3]
    top1_book_match = bool(expected_book and str(top1.get("book_name", "")).strip() == expected_book)
    top3_book_match = any(expected_book and str(item.get("book_name", "")).strip() == expected_book for item in top3)
    top1_section = str(top1.get("file_type", "")).strip() == "SECTION"
    top3_section = any(str(item.get("file_type", "")).strip() == "SECTION" for item in top3)
    top1_keyword_hits = _keyword_hits(text=_haystack(top1), keywords=expected_keywords)
    top3_keyword_hits = max((_keyword_hits(text=_haystack(item), keywords=expected_keywords) for item in top3), default=0)
    score = 0.0
    score += 1.5 if top1_book_match else 0.0
    score += 1.0 if top3_book_match else 0.0
    score += 1.0 if top1_section else 0.0
    score += 0.5 if top3_section else 0.0
    score += min(top1_keyword_hits, 4) * 0.75
    score += min(top3_keyword_hits, 4) * 0.5
    return {
        "top1_book_match": top1_book_match,
        "top3_book_match": top3_book_match,
        "top1_section": top1_section,
        "top3_section": top3_section,
        "top1_keyword_hits": top1_keyword_hits,
        "top3_keyword_hits": top3_keyword_hits,
        "score": round(score, 2),
    }


def _run_condition(*, label: str, engine: RetrievalEngine, dataset: list[dict[str, Any]], top_k: int, candidate_k: int) -> dict[str, Any]:
    query_results: list[dict[str, Any]] = []
    total = len(dataset)
    for index, case in enumerate(dataset, start=1):
        query = str(case.get("query", "")).strip()
        started = time.perf_counter()
        result = engine.search_hybrid(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=False,
            search_mode="files_first",
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        chunks = result.get("chunks", []) if isinstance(result.get("chunks"), list) else []
        hit_metrics = _evaluate_hits(case, chunks)
        row = {
            "id": str(case.get("id", f"case_{index:03d}")),
            "query": query,
            "retrieval_mode": result.get("retrieval_mode"),
            "total": result.get("total", 0),
            "latency_ms": latency_ms,
            "warnings": result.get("warnings", []),
            "top1": chunks[0] if chunks else {},
            "metrics": hit_metrics,
        }
        query_results.append(row)
        print(
            f"[summary-ablation] {label} {index:02d}/{total} "
            f"latency={latency_ms:.1f}ms score={hit_metrics['score']:.2f} "
            f"top1_book={hit_metrics['top1_book_match']} top1_section={hit_metrics['top1_section']}",
            flush=True,
        )

    avg_latency = round(sum(float(item.get("latency_ms", 0.0) or 0.0) for item in query_results) / max(len(query_results), 1), 1)
    avg_score = round(sum(float((item.get("metrics") or {}).get("score", 0.0) or 0.0) for item in query_results) / max(len(query_results), 1), 2)
    return {
        "label": label,
        "avg_latency_ms": avg_latency,
        "avg_score": avg_score,
        "top1_book_match_rate": round(sum(1 for item in query_results if (item.get("metrics") or {}).get("top1_book_match")) / max(len(query_results), 1), 4),
        "top3_book_match_rate": round(sum(1 for item in query_results if (item.get("metrics") or {}).get("top3_book_match")) / max(len(query_results), 1), 4),
        "top1_section_rate": round(sum(1 for item in query_results if (item.get("metrics") or {}).get("top1_section")) / max(len(query_results), 1), 4),
        "top3_section_rate": round(sum(1 for item in query_results if (item.get("metrics") or {}).get("top3_section")) / max(len(query_results), 1), 4),
        "queries": query_results,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    baseline = summary["baseline"]
    enhanced = summary["enhanced"]
    lines = [
        "# Section Summary Ablation Benchmark",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {summary['dataset']} |",
        f"| total_queries | {summary['total_queries']} |",
        f"| baseline_index | {summary['baseline_build'].get('files_first_index_path', '-')} |",
        f"| enhanced_index | {summary['enhanced_build'].get('files_first_index_path', '-')} |",
        "",
        "## Aggregate",
        "",
        "| Condition | avg_latency_ms | avg_score | top1_book | top3_book | top1_section | top3_section | rebuild_latency_ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| baseline_no_llm_summary | {baseline['avg_latency_ms']} | {baseline['avg_score']} | {baseline['top1_book_match_rate']:.2%} | {baseline['top3_book_match_rate']:.2%} | {baseline['top1_section_rate']:.2%} | {baseline['top3_section_rate']:.2%} | {summary['baseline_build'].get('rebuild_latency_ms', '-')} |",
        f"| enhanced_llm_summary | {enhanced['avg_latency_ms']} | {enhanced['avg_score']} | {enhanced['top1_book_match_rate']:.2%} | {enhanced['top3_book_match_rate']:.2%} | {enhanced['top1_section_rate']:.2%} | {enhanced['top3_section_rate']:.2%} | {summary['enhanced_build'].get('rebuild_latency_ms', '-')} |",
        "",
        "## Per Query",
        "",
        "| ID | baseline_latency | baseline_score | enhanced_latency | enhanced_score | delta_score |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    baseline_rows = {item["id"]: item for item in baseline["queries"]}
    enhanced_rows = {item["id"]: item for item in enhanced["queries"]}
    for query_id in baseline_rows:
        left = baseline_rows[query_id]
        right = enhanced_rows.get(query_id, {})
        delta = round(float((right.get("metrics") or {}).get("score", 0.0) or 0.0) - float((left.get("metrics") or {}).get("score", 0.0) or 0.0), 2)
        lines.append(
            f"| {query_id} | {left.get('latency_ms', '-')} | {(left.get('metrics') or {}).get('score', '-')} | {right.get('latency_ms', '-')} | {(right.get('metrics') or {}).get('score', '-')} | {delta} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the impact of section summary cache on files-first retrieval.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "section_summary_ablation_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent / "docs" / "Section_Summary_Ablation_Latest.md")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=12)
    parser.add_argument("--work-root", type=Path, default=BACKEND_ROOT / "storage" / "section_summary_ablation")
    args = parser.parse_args()

    dataset = _load_dataset(args.dataset)
    args.work_root.mkdir(parents=True, exist_ok=True)

    tmp_root = args.work_root / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        baseline_root = tmp_root / "baseline"
        enhanced_root = tmp_root / "enhanced"
        baseline_root.mkdir(parents=True, exist_ok=True)
        enhanced_root.mkdir(parents=True, exist_ok=True)

        baseline_engine = _build_temp_engine(root=baseline_root, use_summary_cache=False)
        enhanced_engine = _build_temp_engine(root=enhanced_root, use_summary_cache=True)

        print("[summary-ablation] rebuild baseline_no_llm_summary", flush=True)
        baseline_build = _rebuild_index(baseline_engine)
        print("[summary-ablation] rebuild enhanced_llm_summary", flush=True)
        enhanced_build = _rebuild_index(enhanced_engine)

        baseline = _run_condition(
            label="baseline",
            engine=baseline_engine,
            dataset=dataset,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
        )
        enhanced = _run_condition(
            label="enhanced",
            engine=enhanced_engine,
            dataset=dataset,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
        )

        summary = {
            "dataset": str(args.dataset),
            "total_queries": len(dataset),
            "baseline_build": baseline_build,
            "enhanced_build": enhanced_build,
            "baseline": baseline,
            "enhanced": enhanced,
        }

        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        args.output_md.write_text(_render_markdown(summary), encoding="utf-8")
        print(json.dumps({"output_json": str(args.output_json), "output_md": str(args.output_md)}, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
