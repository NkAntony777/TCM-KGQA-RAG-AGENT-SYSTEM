from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.run_classics_vector_vs_filesfirst import _build_engine, _load_cases, _metrics, _prepare_query, _trim_rows


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "paper" / "classics_vector_vs_filesfirst_seed_20.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "ablations" / "files_first_ablation_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent.parent / "docs" / "Files_First_Ablation_Latest.md"

ABLATIONS: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("baseline", "完整 files-first", {}),
    ("direct_recall_off", "关闭 direct recall", {"FILES_FIRST_DIRECT_RECALL_ENABLED": "false"}),
    ("lexical_sanity_off", "关闭 lexical sanity", {"FILES_FIRST_LEXICAL_SANITY_ENABLED": "false"}),
    ("query_rewrite_off", "关闭 query rewrite", {"FILES_FIRST_QUERY_REWRITE_ENABLED": "false"}),
    ("rerank_bonus_off", "关闭 chapter/book rerank bonus", {"FILES_FIRST_RERANK_BONUS_ENABLED": "false"}),
)


@contextmanager
def _temporary_env(values: dict[str, str]) -> Any:
    snapshot = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = str(value)
        yield
    finally:
        for key, previous in snapshot.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def _search_condition(
    *,
    label: str,
    description: str,
    env_overrides: dict[str, str],
    dataset: Path,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    with _temporary_env(env_overrides):
        engine = _build_engine(vector_enabled=False, files_first_dense_fallback_enabled=False)
        cases = _load_cases(dataset)
        rows: list[dict[str, Any]] = []
        for idx, case in enumerate(cases, start=1):
            started = time.perf_counter()
            result = engine.search_hybrid(
                query=_prepare_query(case.query),
                top_k=top_k,
                candidate_k=candidate_k,
                enable_rerank=False,
                search_mode="files_first",
                allowed_file_path_prefixes=["classic://"],
            )
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
                f"[files-first-ablation] {label} {idx:02d}/{len(cases)} {case.case_id} "
                f"book_hit={metrics['topk_book_hit']} keyword_hit={metrics['topk_keyword_hit']} latency={latency_ms:.1f}ms",
                flush=True,
            )
    return {
        "label": label,
        "description": description,
        "env_overrides": env_overrides,
        "cases": rows,
        "avg_latency_ms": round(statistics.mean(float(item["latency_ms"]) for item in rows), 1) if rows else None,
        "top1_book_hit_rate": round(sum(1 for item in rows if item["metrics"]["top1_book_hit"]) / max(1, len(rows)), 4),
        "top1_keyword_hit_rate": round(sum(1 for item in rows if item["metrics"]["top1_keyword_hit"]) / max(1, len(rows)), 4),
        "topk_book_hit_rate": round(sum(1 for item in rows if item["metrics"]["topk_book_hit"]) / max(1, len(rows)), 4),
        "topk_keyword_hit_rate": round(sum(1 for item in rows if item["metrics"]["topk_keyword_hit"]) / max(1, len(rows)), 4),
        "avg_book_hit_rate_case": round(
            statistics.mean(
                float(item["metrics"]["book_hit_rate_case"] or 0.0)
                for item in rows
                if item["metrics"]["book_hit_rate_case"] is not None
            ),
            4,
        )
        if rows
        else None,
        "avg_keyword_hit_rate_case": round(
            statistics.mean(
                float(item["metrics"]["keyword_hit_rate_case"] or 0.0)
                for item in rows
                if item["metrics"]["keyword_hit_rate_case"] is not None
            ),
            4,
        )
        if rows
        else None,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    baseline = payload["conditions"][0]
    lines = [
        "# Files-First Internal Ablation",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {payload['settings']['dataset']} |",
        f"| top_k | {payload['settings']['top_k']} |",
        f"| candidate_k | {payload['settings']['candidate_k']} |",
        "",
        "## Aggregate",
        "",
        "| Condition | avg_latency_ms | top1_book | top1_keyword | topk_book | topk_keyword | avg_book_case | avg_keyword_case |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition in payload["conditions"]:
        lines.append(
            f"| {condition['description']} | {condition['avg_latency_ms']} | {condition['top1_book_hit_rate']} | "
            f"{condition['top1_keyword_hit_rate']} | {condition['topk_book_hit_rate']} | {condition['topk_keyword_hit_rate']} | "
            f"{condition['avg_book_hit_rate_case']} | {condition['avg_keyword_hit_rate_case']} |"
        )
    lines.extend(
        [
            "",
            "## Delta vs Baseline",
            "",
            "| Condition | delta_latency_ms | delta_topk_book | delta_topk_keyword |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for condition in payload["conditions"][1:]:
        lines.append(
            f"| {condition['description']} | "
            f"{round(float(condition['avg_latency_ms'] or 0.0) - float(baseline['avg_latency_ms'] or 0.0), 1)} | "
            f"{round(float(condition['topk_book_hit_rate'] or 0.0) - float(baseline['topk_book_hit_rate'] or 0.0), 4)} | "
            f"{round(float(condition['topk_keyword_hit_rate'] or 0.0) - float(baseline['topk_keyword_hit_rate'] or 0.0), 4)} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Files-first internal ablation on the official classics paper dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    conditions = [
        _search_condition(
            label=label,
            description=description,
            env_overrides=env_overrides,
            dataset=args.dataset,
            top_k=max(1, int(args.top_k)),
            candidate_k=max(1, int(args.candidate_k)),
        )
        for label, description, env_overrides in ABLATIONS
    ]
    payload = {
        "settings": {
            "dataset": str(args.dataset),
            "top_k": max(1, int(args.top_k)),
            "candidate_k": max(1, int(args.candidate_k)),
        },
        "conditions": conditions,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "baseline": {
                    "avg_latency_ms": conditions[0]["avg_latency_ms"],
                    "topk_book_hit_rate": conditions[0]["topk_book_hit_rate"],
                    "topk_keyword_hit_rate": conditions[0]["topk_keyword_hit_rate"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
