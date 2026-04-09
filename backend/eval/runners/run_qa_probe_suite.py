from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.runners.run_qa_weakness_probe import DEFAULT_BASE_URL, load_dataset, run_probe


DEFAULT_SUITES: dict[str, list[Path]] = {
    "full": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json",
        BACKEND_ROOT / "eval" / "datasets" / "qa_graph_agent_diagnostic_6.json",
    ],
    "graph_source": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_origin_source_probe_4.json",
        BACKEND_ROOT / "eval" / "datasets" / "qa_graph_agent_diagnostic_6.json",
    ],
    "user": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json",
    ],
    "diagnostic": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_graph_agent_diagnostic_6.json",
    ],
}


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _format_joined(items: list[str]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    return ", ".join(values) if values else "-"


def _format_failure_line(item: dict[str, Any]) -> str:
    issue_text = _format_joined([str(issue) for issue in item.get("issues", [])])
    books_text = _format_joined([str(book) for book in item.get("books", [])])
    return (
        f"- {item.get('dataset', '-') }::{item.get('id', '-')}"
        f"[{item.get('mode', '-')}] route={item.get('route', '-')}"
        f" issues={issue_text} books={books_text}"
    )


def render_probe_suite_markdown(summary: dict[str, Any]) -> str:
    datasets = summary.get("datasets", []) if isinstance(summary.get("datasets"), list) else []
    failures = summary.get("failures", []) if isinstance(summary.get("failures"), list) else []
    top_issues = summary.get("top_issues", []) if isinstance(summary.get("top_issues"), list) else []

    lines = [
        f"# QA probe suite report — {summary.get('suite', '-')}",
        "",
        "## Gate summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| generated_at | {summary.get('generated_at', '-')} |",
        f"| suite | {summary.get('suite', '-')} |",
        f"| gate_passed | {'yes' if summary.get('gate_passed') else 'no'} |",
        f"| base_url | {summary.get('base_url', '-')} |",
        f"| modes | {_format_joined([str(item) for item in summary.get('modes', [])])} |",
        f"| top_k | {summary.get('top_k', '-')} |",
        f"| timeout_s | {summary.get('timeout_s', '-')} |",
        f"| total | {summary.get('total', '-')} |",
        f"| passed | {summary.get('passed', '-')} |",
        f"| failed | {summary.get('failed', '-')} |",
        "",
        "## Dataset summary",
        "",
        "| Dataset | Passed | Failed | Total |",
        "| --- | --- | --- | --- |",
    ]

    for dataset in datasets:
        lines.append(
            f"| {dataset.get('dataset', '-')} | {dataset.get('passed', '-')} | {dataset.get('failed', '-')} | {dataset.get('total', '-')} |"
        )

    lines.extend(["", "## Top issues", ""])
    if top_issues:
        for issue, count in top_issues[:10]:
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")

    for dataset in datasets:
        lines.extend(["", f"## {dataset.get('dataset', '-')}", ""])
        by_category = dataset.get("by_category", {}) if isinstance(dataset.get("by_category"), dict) else {}
        if by_category:
            lines.extend(["### Category summary", "", "| Category | Failed | Total | Avg latency ms |", "| --- | --- | --- | --- |"])
            for category, item in by_category.items():
                lines.append(
                    f"| {category} | {item.get('failed', '-')} | {item.get('total', '-')} | {item.get('avg_latency_ms', '-')} |"
                )
        dataset_failures = dataset.get("failures", []) if isinstance(dataset.get("failures"), list) else []
        lines.extend(["", "### Failing cases", ""])
        if dataset_failures:
            for item in dataset_failures:
                lines.append(_format_failure_line({"dataset": dataset.get("dataset", "-"), **item}))
                query = str(item.get("query", "")).strip()
                if query:
                    lines.append(f"  - Query: {query}")
        else:
            lines.append("- none")

    lines.extend(["", "## Aggregate failing cases", ""])
    if failures:
        for item in failures:
            lines.append(_format_failure_line(item))
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def run_suite(*, suite_name: str, base_url: str, modes: list[str], top_k: int, timeout: float) -> dict[str, Any]:
    dataset_paths = DEFAULT_SUITES[suite_name]
    dataset_summaries: list[dict[str, Any]] = []
    aggregate_total = 0
    aggregate_passed = 0
    aggregate_failed = 0
    all_failures: list[dict[str, Any]] = []

    for dataset_path in dataset_paths:
        summary = run_probe(
            dataset=load_dataset(dataset_path),
            base_url=base_url,
            modes=modes,
            top_k=top_k,
            timeout=timeout,
        )
        dataset_summary = {
            "dataset": dataset_path.name,
            "total": summary["total"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "top_issues": summary["top_issues"],
            "by_category": summary["by_category"],
            "failures": summary["failures"],
        }
        dataset_summaries.append(dataset_summary)
        aggregate_total += summary["total"]
        aggregate_passed += summary["passed"]
        aggregate_failed += summary["failed"]
        for item in summary["failures"]:
            failure = dict(item)
            failure["dataset"] = dataset_path.name
            all_failures.append(failure)

    return {
        "generated_at": _utc_now_text(),
        "suite": suite_name,
        "gate_passed": aggregate_failed == 0,
        "base_url": base_url,
        "total": aggregate_total,
        "passed": aggregate_passed,
        "failed": aggregate_failed,
        "modes": modes,
        "top_k": top_k,
        "timeout_s": timeout,
        "datasets": dataset_summaries,
        "failures": all_failures,
        "top_issues": Counter(
            issue for item in all_failures for issue in item.get("issues", [])
        ).most_common(20),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run user-facing and system-diagnostic QA probe suites.")
    parser.add_argument("--suite", choices=sorted(DEFAULT_SUITES), default="full")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--modes", nargs="+", default=["quick", "deep"])
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    args = parser.parse_args()

    summary = run_suite(
        suite_name=args.suite,
        base_url=args.base_url,
        modes=args.modes,
        top_k=args.top_k,
        timeout=args.timeout,
    )

    if args.output_json:
        args.output_json.resolve().write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        args.output_md.resolve().write_text(render_probe_suite_markdown(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"QA probe suite `{summary['suite']}`: {summary['passed']}/{summary['total']} passed")
        for dataset in summary["datasets"]:
            print(f"- {dataset['dataset']}: {dataset['passed']}/{dataset['total']} passed")
            for issue, count in dataset["top_issues"][:5]:
                print(f"  - {issue}: {count}")
        if summary["failures"]:
            print("Failures:")
            for item in summary["failures"]:
                print(f"- {item['dataset']}::{item['id']}[{item['mode']}] route={item['route']} issues={item['issues']}")
        if args.output_json:
            print(f"JSON: {args.output_json.resolve()}")
        if args.output_md:
            print(f"Markdown: {args.output_md.resolve()}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
