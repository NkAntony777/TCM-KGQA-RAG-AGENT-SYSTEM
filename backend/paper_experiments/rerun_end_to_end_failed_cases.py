from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.runners.run_qa_weakness_probe import (  # noqa: E402
    DEFAULT_BASE_URL,
    _ThreadLocalClientPool,
    _resolve_base_urls,
    _run_single_case_with_pool,
    load_dataset,
)


DEFAULT_REPORT_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_qa_eval_latest.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_failed_rerun_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "End_to_End_QA_Failed_Rerun_Latest.md"


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(content, encoding=encoding)
    os.replace(temp_path, path)


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_dataset_map(report: dict[str, Any]) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    dataset_paths = [Path(item) for item in report.get("settings", {}).get("datasets", []) if str(item).strip()]
    rows_by_dataset: dict[str, dict[str, Any]] = {}
    paths_by_name: dict[str, Path] = {}
    for dataset_path in dataset_paths:
        resolved_path = dataset_path if dataset_path.is_absolute() else BACKEND_ROOT / dataset_path
        rows = load_dataset(resolved_path)
        rows_by_dataset[resolved_path.name] = {str(row.get("id", "")).strip(): row for row in rows}
        paths_by_name[resolved_path.name] = resolved_path
    return paths_by_name, rows_by_dataset


def _load_base_dataset_report(report: dict[str, Any]) -> dict[str, Any]:
    dataset_paths = report.get("settings", {}).get("datasets", []) if isinstance(report.get("settings"), dict) else []
    if dataset_paths:
        return report
    source_report = str(report.get("source_report", "")).strip()
    if source_report:
        source_path = Path(source_report)
        if source_path.exists():
            return _load_report(source_path)
    return report


def _select_failure_jobs(
    report: dict[str, Any],
    *,
    rows_by_dataset: dict[str, dict[str, Any]],
    issue_prefixes: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in report.get("summary", {}).get("failures", []) or []:
        if not isinstance(item, dict):
            continue
        dataset_name = str(item.get("dataset", "")).strip()
        case_id = str(item.get("id", "")).strip()
        mode = str(item.get("mode", "")).strip()
        issues = [str(issue) for issue in (item.get("issues", []) or [])]
        if issue_prefixes and not any(any(issue.startswith(prefix) for prefix in issue_prefixes) for issue in issues):
            continue
        case = rows_by_dataset.get(dataset_name, {}).get(case_id)
        if case is None:
            continue
        selected.append(
            {
                "dataset": dataset_name,
                "id": case_id,
                "mode": mode,
                "case": case,
                "original_issues": issues,
                "original_route": str(item.get("route", "") or ""),
            }
        )
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def _select_failed_rerun_jobs(
    report: dict[str, Any],
    *,
    rows_by_dataset: dict[str, dict[str, Any]],
    issue_prefixes: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in report.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("passed"):
            continue
        dataset_name = str(item.get("dataset", "")).strip()
        case_id = str(item.get("id", "")).strip()
        mode = str(item.get("mode", "")).strip()
        issues = [str(issue) for issue in (item.get("issues", []) or [])]
        if issue_prefixes and not any(any(issue.startswith(prefix) for prefix in issue_prefixes) for issue in issues):
            continue
        case = rows_by_dataset.get(dataset_name, {}).get(case_id)
        if case is None:
            continue
        selected.append(
            {
                "dataset": dataset_name,
                "id": case_id,
                "mode": mode,
                "case": case,
                "original_issues": issues,
                "original_route": str(item.get("route", "") or ""),
            }
        )
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# End-to-End QA Failed Case Rerun",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| source_report | {report['source_report']} |",
        f"| timeout_s | {report['settings']['timeout_s']} |",
        f"| workers | {report['settings']['workers']} |",
        f"| total_rerun | {report['summary']['total']} |",
        f"| recovered | {report['summary']['recovered']} |",
        f"| still_failed | {report['summary']['still_failed']} |",
        f"| recovered_rate | {report['summary']['recovered_rate']} |",
        "",
        "## By Dataset",
        "",
        "| Dataset | Total | Recovered | Still Failed |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["datasets"]:
        lines.append(
            f"| {item['dataset']} | {item['total']} | {item['recovered']} | {item['still_failed']} |"
        )
    lines.extend(["", "## Top Remaining Issues", ""])
    top_issues = report["summary"].get("top_remaining_issues", [])
    if top_issues:
        for issue, count in top_issues:
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Results", ""])
    for item in report["results"]:
        status = "recovered" if item.get("passed") else "still_failed"
        lines.append(
            f"- {item['dataset']}::{item['id']}[{item['mode']}] {status} "
            f"route={item.get('route', '')} original={','.join(item.get('original_issues', []))} "
            f"rerun={','.join(item.get('issues', [])) or 'ok'} latency_ms={item.get('latency_ms', '-')}"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun failed end-to-end QA cases from the latest paper report.")
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--base-urls", nargs="+", default=None)
    parser.add_argument("--timeout", type=float, default=0.0, help="Override timeout. Use 0 to reuse the source report value.")
    parser.add_argument("--workers", type=int, default=0, help="Parallel workers. Use 0 to reuse the source report value.")
    parser.add_argument("--issue-prefix", action="append", default=[], help="Only rerun failures whose issue starts with this prefix.")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on rerun job count.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_report = _load_report(args.report_json)
    base_dataset_report = _load_base_dataset_report(source_report)
    _, rows_by_dataset = _resolve_dataset_map(base_dataset_report)
    normalized_issue_prefixes = [str(item).strip() for item in args.issue_prefix if str(item).strip()]
    if source_report.get("summary", {}).get("failures"):
        selected_jobs = _select_failure_jobs(
            source_report,
            rows_by_dataset=rows_by_dataset,
            issue_prefixes=normalized_issue_prefixes,
            limit=max(0, int(args.limit)),
        )
    else:
        selected_jobs = _select_failed_rerun_jobs(
            source_report,
            rows_by_dataset=rows_by_dataset,
            issue_prefixes=normalized_issue_prefixes,
            limit=max(0, int(args.limit)),
        )
    if not selected_jobs:
        raise SystemExit("no_failed_jobs_selected")

    source_settings = base_dataset_report.get("settings", {}) if isinstance(base_dataset_report.get("settings"), dict) else {}
    timeout = float(args.timeout) if float(args.timeout) > 0 else float(source_settings.get("timeout_s", 120.0))
    workers = int(args.workers) if int(args.workers) > 0 else int(source_settings.get("workers", 1) or 1)
    resolved_base_urls = _resolve_base_urls(
        base_url=args.base_url,
        base_urls=[str(item).strip() for item in (args.base_urls or source_settings.get("base_urls", [])) if str(item).strip()],
    )

    results: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()
    dataset_counter: dict[str, Counter[str]] = defaultdict(Counter)
    total_jobs = len(selected_jobs)
    completed_jobs = 0

    client_pools = {base_url: _ThreadLocalClientPool(base_url=base_url, timeout=timeout) for base_url in resolved_base_urls}
    try:
        print(
            f"[failed-rerun] parallel mode enabled: workers={max(1, workers)}, "
            f"total_jobs={total_jobs}, timeout_s={timeout}, backends={len(resolved_base_urls)}",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {}
            for index, job in enumerate(selected_jobs):
                job_base_url = resolved_base_urls[index % len(resolved_base_urls)]
                futures[
                    executor.submit(
                        _run_single_case_with_pool,
                        client_pools[job_base_url],
                        job["case"],
                        mode=job["mode"],
                        base_url=job_base_url,
                        top_k=max(1, int(source_settings.get("top_k", 12) or 12)),
                        timeout=timeout,
                        warning_issue_prefixes=[
                            "route_mismatch:",
                            "executed_route_missing_any:",
                        ],
                    )
                ] = (job, job_base_url)
            for future in as_completed(futures):
                job, job_base_url = futures[future]
                row = dict(future.result())
                row["dataset"] = job["dataset"]
                row["base_url"] = job_base_url
                row["original_issues"] = list(job["original_issues"])
                row["original_route"] = job["original_route"]
                results.append(row)
                completed_jobs += 1
                dataset_counter[job["dataset"]]["total"] += 1
                if row.get("passed"):
                    dataset_counter[job["dataset"]]["recovered"] += 1
                else:
                    dataset_counter[job["dataset"]]["still_failed"] += 1
                    for issue in row.get("issues", []) or []:
                        issue_counter[str(issue)] += 1
                issues_text = ",".join(row.get("issues", []) or ["ok"])
                print(
                    f"[failed-rerun] {completed_jobs:04d}/{total_jobs:04d} "
                    f"({completed_jobs / max(1, total_jobs):.1%}) "
                    f"{job['dataset']}::{job['id']}[{job['mode']}] "
                    f"base={job_base_url} recovered={int(bool(row.get('passed')))} "
                    f"latency_ms={row.get('latency_ms', '-')} issues={issues_text}",
                    flush=True,
                )
    finally:
        for pool in client_pools.values():
            pool.close()

    total = len(results)
    recovered = sum(1 for item in results if item.get("passed"))
    report = {
        "source_report": str(args.report_json),
        "settings": {
            "base_url": args.base_url,
            "base_urls": resolved_base_urls,
            "timeout_s": timeout,
            "workers": max(1, workers),
            "issue_prefixes": normalized_issue_prefixes,
            "limit": max(0, int(args.limit)),
        },
        "summary": {
            "total": total,
            "recovered": recovered,
            "still_failed": total - recovered,
            "recovered_rate": round(recovered / max(1, total), 4),
            "top_remaining_issues": issue_counter.most_common(20),
        },
        "datasets": [
            {
                "dataset": dataset,
                "total": counts["total"],
                "recovered": counts["recovered"],
                "still_failed": counts["still_failed"],
            }
            for dataset, counts in sorted(dataset_counter.items())
        ],
        "results": sorted(
            results,
            key=lambda item: (
                str(item.get("dataset", "")),
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
        print(f"failed_rerun: recovered={recovered}/{total}")
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0 if recovered == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
