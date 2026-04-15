from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.runners.run_eval import DEFAULT_DATASET as ROUTER_DATASET
from eval.runners.run_eval import evaluate_router, load_dataset as load_router_dataset
from eval.runners.run_graph_regression import evaluate_graph_regression, load_dataset as load_graph_regression_dataset
from eval.runners.run_graph_regression import select_cases as select_graph_regression_cases
from eval.runners.run_qa_weakness_probe import load_dataset as load_probe_dataset
from eval.runners.run_qa_weakness_probe import run_probe
from eval.runners.run_smoke_suite import check_health


DEFAULT_BASE_URL = "http://127.0.0.1:8002"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "release_gate_20260409.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent.parent / "docs" / "Batch4_Release_Gate_20260409.md"
DOC_QA_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_origin_source_probe_4.json"
COMPLEX_QA_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_agent_hard_probe_10.json"
GRAPH_REGRESSION_DATASET = BACKEND_ROOT / "eval" / "datasets" / "graph_regression_12.json"
DEFAULT_DOCTORAL_BASELINE_JSON = BACKEND_ROOT / "eval" / "doctoral_hard_probe_quick_deep_20260410_deep_quality_tuned.json"
ROUTER_MIN_ACCURACY = 0.80
DEEP_MIN_ANSWER_CHARS = 400
DEEP_DISALLOWED_BACKENDS = {"planner_deterministic_fallback"}


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _render_failures(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items[:20]:
        lines.append(
            f"- {item.get('id', '-')}"  # noqa: E501
            f"[{item.get('mode', '-')}] route={item.get('route', '-')}"
            f" issues={','.join(str(x) for x in item.get('issues', [])) or '-'}"
        )
    return lines or ["- none"]


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def summarize_doctoral_baseline(path: Path) -> dict[str, Any]:
    payload = _load_optional_json(path)
    if not payload:
        return {"available": False, "path": str(path), "complete": False, "quick_ok": 0, "deep_ok": 0, "total_questions": 0}
    questions = payload.get("questions", [])
    if not isinstance(questions, list):
        return {"available": True, "path": str(path), "complete": False, "quick_ok": 0, "deep_ok": 0, "total_questions": 0}
    quick_ok = 0
    deep_ok = 0
    deep_fallback_count = 0
    deep_short_answer_count = 0
    complete = True
    for row in questions:
        if not isinstance(row, dict):
            complete = False
            continue
        quick = row.get("quick")
        deep = row.get("deep")
        if not (isinstance(quick, dict) and quick.get("ok") is True and quick.get("answer")):
            complete = False
        else:
            quick_ok += 1
        if not (isinstance(deep, dict) and deep.get("ok") is True and deep.get("answer")):
            complete = False
        else:
            deep_ok += 1
            deep_backend = str(deep.get("generation_backend", "") or "").strip()
            if deep_backend in DEEP_DISALLOWED_BACKENDS:
                deep_fallback_count += 1
                complete = False
            if len(str(deep.get("answer", "") or "").strip()) < DEEP_MIN_ANSWER_CHARS:
                deep_short_answer_count += 1
                complete = False
    return {
        "available": True,
        "path": str(path),
        "complete": complete,
        "quick_ok": quick_ok,
        "deep_ok": deep_ok,
        "deep_fallback_count": deep_fallback_count,
        "deep_short_answer_count": deep_short_answer_count,
        "total_questions": len(questions),
        "summary": payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {},
    }


def render_markdown(summary: dict[str, Any]) -> str:
    router = summary["router"]
    docqa = summary["docqa"]
    complexqa = summary["complexqa"]
    graph_regression = summary["graph_regression"]
    doctoral = summary["doctoral_baseline"]
    health = summary["health"]
    probe_skipped = bool(summary.get("probe_skipped"))
    lines = [
        "# Batch 4 Release Gate Report",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| generated_at | {summary['generated_at']} |",
        f"| base_url | {summary['base_url']} |",
        f"| gate_passed | {'yes' if summary['gate_passed'] else 'no'} |",
        f"| strict_mode | {'yes' if summary.get('strict_mode') else 'no'} |",
        f"| probe_skipped | {'yes' if probe_skipped else 'no'} |",
        f"| block_reason | {summary.get('block_reason', '-')} |",
        "",
        "## Gate thresholds",
        "",
        f"- main backend health must be **OK**",
        "- graph runtime is evaluated under the current SQLite-primary online architecture",
        f"- router smoke accuracy must be **>= {summary.get('router_min_accuracy', ROUTER_MIN_ACCURACY):.2f}**",
        "- fast graph regression failed count must be **0**",
        "- Doc-QA probe failed count must be **0**",
        "- Complex-QA probe failed count must be **0**",
        "- strict mode additionally requires a complete doctoral baseline artifact",
        "",
        "## Health",
        "",
        "| Service | OK | Status |",
        "| --- | --- | --- |",
    ]
    for name, item in health.items():
        lines.append(f"| {name} | {'yes' if item.get('ok') else 'no'} | {item.get('status_code') or item.get('error') or '-'} |")

    lines.extend(
        [
            "",
            "## Router smoke",
            "",
            f"- accuracy: {router['correct']}/{router['total']} = {router['accuracy']:.2%}",
            f"- mismatches: {len(router.get('mismatches', []))}",
            "",
            "## Fast Graph Regression",
            "",
            f"- passed: {graph_regression['passed']}/{graph_regression['total']}",
            f"- failed: {graph_regression['failed']}",
            f"- top issues: {graph_regression['top_issues'][:5]}",
            "",
            "## Doctoral Baseline",
            "",
            f"- available: {'yes' if doctoral['available'] else 'no'}",
            f"- complete: {'yes' if doctoral['complete'] else 'no'}",
            f"- quick_ok: {doctoral['quick_ok']}/{doctoral['total_questions']}",
            f"- deep_ok: {doctoral['deep_ok']}/{doctoral['total_questions']}",
            f"- deep_fallback_count: {doctoral['deep_fallback_count']}",
            f"- deep_short_answer_count: {doctoral['deep_short_answer_count']}",
            f"- path: {doctoral['path']}",
            "",
            "## Doc-QA probe",
            "",
            f"- passed: {docqa['passed']}/{docqa['total']}",
            f"- failed: {docqa['failed']}",
            f"- top issues: {docqa['top_issues'][:5]}",
            "",
            "## Complex-QA probe",
            "",
            f"- passed: {complexqa['passed']}/{complexqa['total']}",
            f"- failed: {complexqa['failed']}",
            f"- top issues: {complexqa['top_issues'][:5]}",
            "",
            "## Failing Doc-QA cases",
            "",
            *_render_failures(docqa.get("failures", [])),
            "",
            "## Failing Complex-QA cases",
            "",
            *_render_failures(complexqa.get("failures", [])),
            "",
            "## Notes",
            "",
            f"- skip_reason: {summary.get('skip_reason', '-')}",
            "- Graph backend baseline now assumes SQLite runtime graph as the primary online engine; Nebula is treated as fallback capacity.",
            f"- This gate is a release-facing aggregation layer. A failed/blocked report is still a valid and useful artifact.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_release_gate(*, base_url: str, top_k: int, timeout: float, strict_mode: bool, doctoral_json: Path) -> dict[str, Any]:
    health = check_health({"main_backend": f"{base_url}/health"}, timeout)
    router_summary = evaluate_router(load_router_dataset(ROUTER_DATASET))
    graph_regression_summary = evaluate_graph_regression(
        select_graph_regression_cases(load_graph_regression_dataset(GRAPH_REGRESSION_DATASET), include_heavy=False)
    )
    doctoral_baseline = summarize_doctoral_baseline(doctoral_json)
    main_backend_ok = bool(health.get("main_backend", {}).get("ok"))
    probe_skipped = not main_backend_ok
    if probe_skipped:
        docqa_summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "top_issues": [("skipped:main_backend_unhealthy", 1)],
            "by_category": {},
            "failures": [],
        }
        complexqa_summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "top_issues": [("skipped:main_backend_unhealthy", 1)],
            "by_category": {},
            "failures": [],
        }
    else:
        docqa_summary = run_probe(
            dataset=load_probe_dataset(DOC_QA_DATASET),
            base_url=base_url,
            modes=["quick", "deep"],
            top_k=top_k,
            timeout=timeout,
        )
        complexqa_summary = run_probe(
            dataset=load_probe_dataset(COMPLEX_QA_DATASET),
            base_url=base_url,
            modes=["quick", "deep"],
            top_k=top_k,
            timeout=timeout,
        )

    gate_passed = (
        main_backend_ok
        and router_summary["accuracy"] >= ROUTER_MIN_ACCURACY
        and graph_regression_summary["failed"] == 0
        and docqa_summary["failed"] == 0
        and complexqa_summary["failed"] == 0
        and ((not strict_mode) or doctoral_baseline["complete"])
    )
    skip_reason = "main_backend_unhealthy" if probe_skipped else ""
    if not main_backend_ok:
        block_reason = "main_backend_health_failed"
    elif router_summary["accuracy"] < ROUTER_MIN_ACCURACY:
        block_reason = "router_smoke_below_threshold"
    elif graph_regression_summary["failed"] > 0:
        block_reason = "graph_regression_failed"
    elif docqa_summary["failed"] > 0:
        block_reason = "docqa_probe_failed"
    elif complexqa_summary["failed"] > 0:
        block_reason = "complexqa_probe_failed"
    elif strict_mode and not doctoral_baseline["complete"]:
        block_reason = "doctoral_baseline_incomplete"
    else:
        block_reason = ""
    return {
        "generated_at": _utc_now_text(),
        "base_url": base_url,
        "gate_passed": gate_passed,
        "probe_skipped": probe_skipped,
        "strict_mode": strict_mode,
        "skip_reason": skip_reason,
        "block_reason": block_reason or "-",
        "router_min_accuracy": ROUTER_MIN_ACCURACY,
        "health": health,
        "router": router_summary,
        "graph_regression": graph_regression_summary,
        "doctoral_baseline": doctoral_baseline,
        "docqa": docqa_summary,
        "complexqa": complexqa_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Batch 4 release gate.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--doctoral-json", type=Path, default=DEFAULT_DOCTORAL_BASELINE_JSON)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = run_release_gate(
        base_url=args.base_url,
        top_k=args.top_k,
        timeout=args.timeout,
        strict_mode=bool(args.strict),
        doctoral_json=args.doctoral_json,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"gate_passed={summary['gate_passed']}")
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
