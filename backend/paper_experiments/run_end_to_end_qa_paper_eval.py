from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.runners.run_qa_weakness_probe import DEFAULT_BASE_URL, load_dataset, run_probe
from paper_experiments.experiment_env import collect_experiment_environment


DEFAULT_DATASETS = [
    BACKEND_ROOT / "eval" / "datasets" / "qa_origin_source_probe_4.json",
    BACKEND_ROOT / "eval" / "datasets" / "qa_agent_hard_probe_10.json",
]
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_qa_eval_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "End_to_End_QA_Eval_Latest.md"


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(content, encoding=encoding)
    os.replace(temp_path, path)


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# End-to-End QA Paper Evaluation",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| base_url | {report['settings']['base_url']} |",
        f"| modes | {', '.join(report['settings']['modes'])} |",
        f"| top_k | {report['settings']['top_k']} |",
        f"| timeout_s | {report['settings']['timeout_s']} |",
        f"| workers | {report['settings']['workers']} |",
        f"| total | {summary['total']} |",
        f"| passed | {summary['passed']} |",
        f"| failed | {summary['failed']} |",
        f"| pass_rate | {summary['pass_rate']} |",
        "",
        "## Dataset Summary",
        "",
        "| Dataset | Passed | Failed | Total |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["datasets"]:
        lines.append(f"| {item['dataset']} | {item['passed']} | {item['failed']} | {item['total']} |")

    lines.extend(["", "## Top Issues", ""])
    if summary["top_issues"]:
        for issue, count in summary["top_issues"]:
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Failed Cases", ""])
    if summary["failures"]:
        for item in summary["failures"]:
            lines.append(f"- {item['dataset']}::{item['id']}[{item['mode']}] route={item['route']} issues={','.join(item['issues'])}")
            lines.append(f"  - Query: {item['query']}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the paper-facing end-to-end QA evaluation suite.")
    parser.add_argument("--datasets", type=Path, nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--modes", nargs="+", default=["quick", "deep"])
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dataset_reports: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()
    total = 0
    passed = 0

    for dataset_path in args.datasets:
        summary = run_probe(
            dataset=load_dataset(dataset_path),
            base_url=args.base_url,
            modes=list(args.modes),
            top_k=max(1, int(args.top_k)),
            timeout=float(args.timeout),
            workers=max(1, int(args.workers)),
            warning_issue_prefixes=[
                "route_mismatch:",
                "executed_route_missing_any:",
            ],
        )
        dataset_report = {
            "dataset": dataset_path.name,
            "total": summary["total"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "by_category": summary["by_category"],
            "top_issues": summary["top_issues"],
            "soft_top_issues": summary.get("soft_top_issues", []),
            "failures": summary["failures"],
        }
        dataset_reports.append(dataset_report)
        for item in summary.get("results", []):
            row = dict(item)
            row["dataset"] = dataset_path.name
            all_results.append(row)
        total += int(summary["total"])
        passed += int(summary["passed"])
        for item in summary["failures"]:
            failure = dict(item)
            failure["dataset"] = dataset_path.name
            failures.append(failure)
            for issue in failure.get("issues", []):
                issue_counter[str(issue)] += 1

    report = {
        "settings": {
            "datasets": [str(path) for path in args.datasets],
            "base_url": args.base_url,
            "modes": list(args.modes),
            "top_k": max(1, int(args.top_k)),
            "timeout_s": float(args.timeout),
            "workers": max(1, int(args.workers)),
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "run_end_to_end_qa_paper_eval.py",
                "base_url": args.base_url,
                "datasets": [str(path) for path in args.datasets],
                "modes": list(args.modes),
                "workers": max(1, int(args.workers)),
                "evaluation_scope": "HTTP end-to-end QA answers, route metadata, evidence books, and tool traces",
            }
        ),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(1, total), 4),
            "top_issues": issue_counter.most_common(20),
            "soft_top_issues": [
                item
                for dataset in dataset_reports
                for item in dataset.get("soft_top_issues", [])
            ],
            "failures": failures,
        },
        "datasets": dataset_reports,
        "all_results": sorted(
            all_results,
            key=lambda item: (
                str(item.get("dataset", "")),
                str(item.get("category", "")),
                str(item.get("id", "")),
                str(item.get("mode", "")),
            ),
        ),
    }

    _atomic_write_text(args.output_json, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _atomic_write_text(args.output_md, _render_markdown(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"end_to_end_qa_eval: {passed}/{total} passed")
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0 if (total - passed) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
