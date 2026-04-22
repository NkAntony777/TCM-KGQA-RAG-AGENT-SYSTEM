from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.experiment_env import collect_experiment_environment
from services.common.medical_guard import assess_query


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "paper" / "medical_guard_eval_12.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "medical_guard_eval_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Medical_Guard_Eval_Latest.md"


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    return [item for item in payload if isinstance(item, dict)]


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    query = str(case.get("query", "") or "").strip()
    result = assess_query(query)
    expected_risk_level = str(case.get("expected_risk_level", "") or "").strip()
    expected_should_refuse = bool(case.get("expected_should_refuse", False))
    expected_disclaimer_contains = [str(item).strip() for item in case.get("expected_disclaimer_contains", []) or [] if str(item).strip()]
    expected_refuse_contains = [str(item).strip() for item in case.get("expected_refuse_contains", []) or [] if str(item).strip()]

    issues: list[str] = []
    if result.risk_level.value != expected_risk_level:
        issues.append(f"risk_level:{result.risk_level.value}!={expected_risk_level}")
    if bool(result.should_refuse) != expected_should_refuse:
        issues.append(f"should_refuse:{result.should_refuse}!={expected_should_refuse}")
    for token in expected_disclaimer_contains:
        if token not in result.disclaimer:
            issues.append(f"disclaimer_missing:{token}")
    for token in expected_refuse_contains:
        if token not in result.refuse_response:
            issues.append(f"refuse_missing:{token}")

    return {
        "id": str(case.get("id", "") or "").strip(),
        "category": str(case.get("category", "unknown") or "unknown").strip(),
        "query": query,
        "expected_risk_level": expected_risk_level,
        "expected_should_refuse": expected_should_refuse,
        "actual_risk_level": result.risk_level.value,
        "actual_should_refuse": bool(result.should_refuse),
        "matched_patterns": list(result.matched_patterns),
        "disclaimer": result.disclaimer,
        "refuse_response": result.refuse_response,
        "issues": issues,
        "passed": not issues,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in rows if not row["passed"]]
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    risk_counter: Counter[str] = Counter()
    refuse_counter: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()

    for row in rows:
        by_category[row["category"]].append(row)
        risk_counter[row["actual_risk_level"]] += 1
        refuse_counter["refuse" if row["actual_should_refuse"] else "non_refuse"] += 1
        for issue in row["issues"]:
            issue_counter[issue] += 1

    category_summary: dict[str, Any] = {}
    for category, items in sorted(by_category.items()):
        category_summary[category] = {
            "total": len(items),
            "passed": sum(1 for item in items if item["passed"]),
            "failed": sum(1 for item in items if not item["passed"]),
            "pass_rate": round(sum(1 for item in items if item["passed"]) / max(1, len(items)), 4),
        }

    return {
        "total": len(rows),
        "passed": len(rows) - len(failures),
        "failed": len(failures),
        "pass_rate": round((len(rows) - len(failures)) / max(1, len(rows)), 4),
        "risk_distribution": dict(risk_counter),
        "refusal_distribution": dict(refuse_counter),
        "category_summary": category_summary,
        "top_issues": issue_counter.most_common(20),
        "failures": failures,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Medical Guard Evaluation",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {report['settings']['dataset_path']} |",
        f"| total | {summary['total']} |",
        f"| passed | {summary['passed']} |",
        f"| failed | {summary['failed']} |",
        f"| pass_rate | {summary['pass_rate']} |",
        "",
        "## Risk Distribution",
        "",
        "| Risk Level | Count |",
        "| --- | ---: |",
    ]
    for risk_level, count in sorted(summary["risk_distribution"].items()):
        lines.append(f"| {risk_level} | {count} |")

    lines.extend(["", "## By Category", "", "| Category | Passed | Failed | Total | Pass Rate |", "| --- | ---: | ---: | ---: | ---: |"])
    for category, item in summary["category_summary"].items():
        lines.append(f"| {category} | {item['passed']} | {item['failed']} | {item['total']} | {item['pass_rate']} |")

    lines.extend(["", "## Top Issues", ""])
    if summary["top_issues"]:
        for issue, count in summary["top_issues"]:
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Failed Cases", ""])
    if summary["failures"]:
        for item in summary["failures"]:
            lines.append(f"- {item['id']}[{item['category']}] issues={','.join(item['issues'])}")
            lines.append(f"  - Query: {item['query']}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run the formal paper-facing medical guard evaluation.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = [_evaluate_case(case) for case in _load_dataset(args.dataset)]
    report = {
        "settings": {
            "dataset_path": str(args.dataset),
        },
        "environment": collect_experiment_environment(
            extra={
                "script": "run_medical_guard_eval.py",
                "dataset_path": str(args.dataset),
                "evaluation_scope": "deterministic pre-answer medical boundary rules",
            }
        ),
        "summary": _summarize(rows),
        "cases": rows,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"medical_guard_eval: {report['summary']['passed']}/{report['summary']['total']} passed")
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
