from __future__ import annotations

import argparse
import json
import sys
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
    "user": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json",
    ],
    "diagnostic": [
        BACKEND_ROOT / "eval" / "datasets" / "qa_graph_agent_diagnostic_6.json",
    ],
}


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
        "suite": suite_name,
        "total": aggregate_total,
        "passed": aggregate_passed,
        "failed": aggregate_failed,
        "modes": modes,
        "datasets": dataset_summaries,
        "failures": all_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run user-facing and system-diagnostic QA probe suites.")
    parser.add_argument("--suite", choices=sorted(DEFAULT_SUITES), default="full")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--modes", nargs="+", default=["quick", "deep"])
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = run_suite(
        suite_name=args.suite,
        base_url=args.base_url,
        modes=args.modes,
        top_k=args.top_k,
        timeout=args.timeout,
    )

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

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
