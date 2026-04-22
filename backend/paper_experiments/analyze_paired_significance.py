from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.experiment_env import collect_experiment_environment


@dataclass(frozen=True)
class MetricSpec:
    name: str
    extractor: Callable[[dict[str, Any]], float | None]
    higher_is_better: bool = True


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except Exception:
        return None


def _bootstrap_ci(diffs: list[float], *, iterations: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means: list[float] = []
    size = len(diffs)
    for _ in range(iterations):
        sample = [diffs[rng.randrange(size)] for _ in range(size)]
        means.append(statistics.mean(sample))
    means.sort()
    lower_idx = max(0, int(iterations * 0.025) - 1)
    upper_idx = min(iterations - 1, int(iterations * 0.975))
    return (round(means[lower_idx], 6), round(means[upper_idx], 6))


def _two_sided_sign_test_pvalue(diffs: list[float]) -> float | None:
    wins = sum(1 for value in diffs if value > 0)
    losses = sum(1 for value in diffs if value < 0)
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    cumulative = 0.0
    for i in range(0, k + 1):
        cumulative += math.comb(n, i)
    p = min(1.0, 2.0 * cumulative / (2**n))
    return round(p, 6)


def _compare_metric(
    left_rows: dict[str, dict[str, Any]],
    right_rows: dict[str, dict[str, Any]],
    metric: MetricSpec,
    *,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    paired_ids = sorted(set(left_rows).intersection(right_rows))
    left_values: list[float] = []
    right_values: list[float] = []
    diffs: list[float] = []
    skipped = 0

    for case_id in paired_ids:
        left_value = metric.extractor(left_rows[case_id])
        right_value = metric.extractor(right_rows[case_id])
        if left_value is None or right_value is None:
            skipped += 1
            continue
        left_values.append(left_value)
        right_values.append(right_value)
        diffs.append(left_value - right_value)

    if not diffs:
        return {
            "metric": metric.name,
            "paired_cases": 0,
            "skipped_cases": skipped,
            "left_mean": None,
            "right_mean": None,
            "delta_mean": None,
            "delta_ci95": None,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "sign_test_pvalue": None,
            "higher_is_better": metric.higher_is_better,
        }

    wins = sum(1 for value in diffs if value > 0)
    losses = sum(1 for value in diffs if value < 0)
    ties = len(diffs) - wins - losses
    return {
        "metric": metric.name,
        "paired_cases": len(diffs),
        "skipped_cases": skipped,
        "left_mean": round(statistics.mean(left_values), 6),
        "right_mean": round(statistics.mean(right_values), 6),
        "delta_mean": round(statistics.mean(diffs), 6),
        "delta_ci95": list(_bootstrap_ci(diffs, iterations=iterations, seed=seed)),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "sign_test_pvalue": _two_sided_sign_test_pvalue(diffs),
        "higher_is_better": metric.higher_is_better,
    }


def _classics_pair_metrics() -> list[MetricSpec]:
    return [
        MetricSpec("topk_book_hit", lambda row: _as_float(row.get("metrics", {}).get("topk_book_hit"))),
        MetricSpec("topk_provenance_hit", lambda row: _as_float(row.get("metrics", {}).get("topk_provenance_hit"))),
        MetricSpec("topk_answer_provenance_hit", lambda row: _as_float(row.get("metrics", {}).get("topk_answer_provenance_hit"))),
        MetricSpec("answer_keypoint_recall", lambda row: _as_float(row.get("metrics", {}).get("answer_keypoint_recall"))),
        MetricSpec("source_mrr", lambda row: _as_float(row.get("metrics", {}).get("source_mrr"))),
        MetricSpec("latency_ms", lambda row: _as_float(row.get("latency_ms")), higher_is_better=False),
    ]


def _caseqa_pair_metrics() -> list[MetricSpec]:
    return [
        MetricSpec("top1_hit", lambda row: _as_float(row.get("metrics", {}).get("top1_hit"))),
        MetricSpec("topk_hit", lambda row: _as_float(row.get("metrics", {}).get("topk_hit"))),
        MetricSpec("coverage_any", lambda row: _as_float(row.get("metrics", {}).get("coverage_any"))),
        MetricSpec("keypoint_recall", lambda row: _as_float(row.get("metrics", {}).get("keypoint_recall"))),
        MetricSpec("keypoint_f1", lambda row: _as_float(row.get("metrics", {}).get("keypoint_f1"))),
        MetricSpec("preferred_hit", lambda row: _as_float(row.get("metrics", {}).get("preferred_hit"))),
        MetricSpec("latency_ms", lambda row: _as_float(row.get("latency_ms")), higher_is_better=False),
    ]


def _extract_classics_pair(payload: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]], str, dict[str, dict[str, Any]], list[MetricSpec]]:
    left_rows = {row["case"]["case_id"]: row for row in payload["files_first"]["cases"] if isinstance(row, dict)}
    right_rows = {row["case"]["case_id"]: row for row in payload["vector"]["cases"] if isinstance(row, dict)}
    return ("files_first", left_rows, "vector", right_rows, _classics_pair_metrics())


def _extract_caseqa_pair(payload: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]], str, dict[str, dict[str, Any]], list[MetricSpec]]:
    left_rows = {row["case"]["case_id"]: row["structured"] for row in payload["cases"] if isinstance(row, dict)}
    right_rows = {row["case"]["case_id"]: row["vector"] for row in payload["cases"] if isinstance(row, dict)}
    return ("structured", left_rows, "vector", right_rows, _caseqa_pair_metrics())


def _extract_baseline_matrix(
    payload: dict[str, Any], *, left_key: str, right_key: str
) -> tuple[str, dict[str, dict[str, Any]], str, dict[str, dict[str, Any]], list[MetricSpec]]:
    left_rows = {row["case"]["case_id"]: row for row in payload[left_key]["cases"] if isinstance(row, dict)}
    right_rows = {row["case"]["case_id"]: row for row in payload[right_key]["cases"] if isinstance(row, dict)}
    return (left_key, left_rows, right_key, right_rows, _classics_pair_metrics())


def _detect_format(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("files_first"), dict) and isinstance(payload.get("vector"), dict):
        return "classics_pair"
    if isinstance(payload.get("cases"), list):
        return "caseqa_pair"
    if all(isinstance(payload.get(key), dict) for key in ("files_first", "external_bm25", "vector_sqlite", "external_dense")):
        return "baseline_matrix"
    raise ValueError("unsupported_report_format")


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Paired Significance Analysis",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| input_json | {report['settings']['input_json']} |",
        f"| format | {report['settings']['format']} |",
        f"| left | {report['settings']['left_label']} |",
        f"| right | {report['settings']['right_label']} |",
        f"| bootstrap_iterations | {report['settings']['bootstrap_iterations']} |",
        "",
        "## Metrics",
        "",
        "| Metric | Paired Cases | Left Mean | Right Mean | Delta Mean | 95% CI | Wins | Losses | Ties | Sign Test p | Better Direction |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report["metrics"]:
        ci = item["delta_ci95"]
        ci_text = "-" if not ci else f"[{ci[0]}, {ci[1]}]"
        better = "higher" if item["higher_is_better"] else "lower"
        lines.append(
            f"| {item['metric']} | {item['paired_cases']} | {item['left_mean']} | {item['right_mean']} | {item['delta_mean']} | {ci_text} | {item['wins']} | {item['losses']} | {item['ties']} | {item['sign_test_pvalue']} | {better} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paired bootstrap/sign-test analysis on paper experiment JSON.")
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--left-key", default="files_first")
    parser.add_argument("--right-key", default="vector_sqlite")
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260420)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input_json_must_be_object")

    format_name = _detect_format(payload)
    if format_name == "classics_pair":
        left_label, left_rows, right_label, right_rows, metrics = _extract_classics_pair(payload)
    elif format_name == "caseqa_pair":
        left_label, left_rows, right_label, right_rows, metrics = _extract_caseqa_pair(payload)
    else:
        left_label, left_rows, right_label, right_rows, metrics = _extract_baseline_matrix(
            payload, left_key=str(args.left_key), right_key=str(args.right_key)
        )

    report = {
        "settings": {
            "input_json": str(args.input_json),
            "format": format_name,
            "left_label": left_label,
            "right_label": right_label,
            "bootstrap_iterations": int(args.bootstrap_iterations),
            "seed": int(args.seed),
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "analyze_paired_significance.py",
                "input_json": str(args.input_json),
                "format": format_name,
                "left_label": left_label,
                "right_label": right_label,
            }
        ),
        "metrics": [
            _compare_metric(
                left_rows,
                right_rows,
                metric,
                iterations=max(100, int(args.bootstrap_iterations)),
                seed=int(args.seed) + idx,
            )
            for idx, metric in enumerate(metrics)
        ],
    }

    output_json = args.output_json or (
        BACKEND_ROOT / "eval" / "paper" / f"{args.input_json.stem}_paired_significance.json"
    )
    output_md = args.output_md or (
        BACKEND_ROOT.parent / "docs" / f"{args.input_json.stem}_paired_significance.md"
    )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_render_markdown(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"paired_significance: {left_label} vs {right_label}")
        print(f"json={output_json}")
        print(f"md={output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
