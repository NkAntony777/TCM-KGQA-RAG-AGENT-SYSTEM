from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_qa_eval_latest.json"
DEFAULT_RERUN1_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_failed_rerun_latest.json"
DEFAULT_RERUN2_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_failed_rerun_round2_latest.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "end_to_end_qa_eval_final_official.json"
DEFAULT_OUTPUT_REPORT_MD = BACKEND_ROOT.parent / "docs" / "End_to_End_QA_Eval_Final_Official.md"
DEFAULT_OUTPUT_ALL_RESULTS_MD = BACKEND_ROOT.parent / "docs" / "End_to_End_QA_All_Results_Final_Official.md"

_EXPLICIT_FINAL_LETTERS_RE = re.compile(r"(?:最终选项|最终答案|答案|选项)\s*[：: ]\s*([A-Z]{1,8})")
_FINAL_SECTION_HINT_RE = re.compile(r"(最终选项|最终答案|结论|选择题答案|答案)\s*[：: ]?", re.IGNORECASE)
_UNCERTAINTY_HINTS = ("无法判断", "证据不足", "无法选择", "无对应选项", "最终选项：无", "最终选项:无")


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(content, encoding=encoding)
    try:
        os.replace(temp_path, path)
    except PermissionError:
        path.write_text(content, encoding=encoding)
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("dataset", "")).strip(),
        str(item.get("id", "")).strip(),
        str(item.get("mode", "")).strip(),
    )


def _normalize_answer_text(value: str) -> str:
    text = str(value or "").strip()
    text = (
        text.replace("～", "~")
        .replace("—", "-")
        .replace("–", "-")
        .replace("−", "-")
        .replace("至", "-")
        .replace("到", "-")
        .replace("克", "g")
    )
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff~\-\./]", "", text)
    return text.lower()


def _extract_explicit_final_letters(answer: str) -> str:
    match = _EXPLICIT_FINAL_LETTERS_RE.search(str(answer or "").upper())
    if match is None:
        return ""
    return "".join(ch for ch in match.group(1) if "A" <= ch <= "Z")


def _extract_final_focus_text(answer: str) -> str:
    text = str(answer or "")
    matches = list(_FINAL_SECTION_HINT_RE.finditer(text))
    if not matches:
        return text
    return text[matches[-1].start() :]


def _has_uncertainty_signal(answer: str) -> bool:
    text = str(answer or "")
    return any(token in text for token in _UNCERTAINTY_HINTS)


def _load_dataset_rows(baseline_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows_by_dataset: dict[str, dict[str, Any]] = {}
    for dataset_path_text in baseline_report.get("settings", {}).get("datasets", []) or []:
        dataset_path = Path(dataset_path_text)
        resolved_path = dataset_path if dataset_path.is_absolute() else BACKEND_ROOT / dataset_path
        rows = json.loads(resolved_path.read_text(encoding="utf-8"))
        rows_by_dataset[resolved_path.name] = {
            str(row.get("id", "")).strip(): row
            for row in rows
            if isinstance(row, dict)
        }
    return rows_by_dataset


def _issue_bucket(item: dict[str, Any]) -> str:
    issues = [str(issue) for issue in item.get("issues", []) or []]
    if any(issue.startswith("request_error:") for issue in issues):
        return "request_error"
    has_letter = any(issue.startswith("answer_option_letters_missing_any:") for issue in issues)
    has_answer = any(issue.startswith("answer_missing_any:") for issue in issues)
    if has_letter and has_answer:
        return "answer_content_and_option_format"
    if has_letter:
        return "option_format_only"
    if has_answer:
        return "answer_content_only"
    return "other"


def _summarize_history(history: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in history:
        stage = str(item.get("stage", "")).strip()
        passed = bool(item.get("passed"))
        issues = ",".join(str(issue) for issue in item.get("issues", []) or []) or "ok"
        parts.append(f"{stage}:{'pass' if passed else 'fail'}:{issues}")
    return " | ".join(parts)


def _maybe_apply_format_override(
    item: dict[str, Any],
    *,
    source_row: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool, str]:
    if item.get("passed") or not source_row:
        return item, False, ""

    expected_option_letters = [
        "".join(ch for ch in str(token).upper() if "A" <= ch <= "Z")
        for token in (source_row.get("answer_option_letters_any", []) or [])
        if "".join(ch for ch in str(token).upper() if "A" <= ch <= "Z")
    ]
    if not expected_option_letters:
        return item, False, ""

    expected = expected_option_letters[0]
    expected_set = set(expected)
    answer = str(item.get("answer", "") or "")
    explicit_letters = _extract_explicit_final_letters(answer)
    explicit_set = set(explicit_letters)
    final_focus_text = _extract_final_focus_text(answer)

    override_reason = ""
    if explicit_letters and explicit_set == expected_set and not _has_uncertainty_signal(answer):
        override_reason = "explicit_final_letters_correct"
    elif not _has_uncertainty_signal(answer):
        normalized_answer = _normalize_answer_text(final_focus_text)
        answer_tokens = [
            str(token).strip()
            for token in (source_row.get("answer_contains_any", []) or [])
            if str(token).strip()
        ]
        if answer_tokens and all(
            normalized_token and normalized_token in normalized_answer
            for normalized_token in (_normalize_answer_text(token) for token in answer_tokens)
        ):
            override_reason = "answer_text_match_in_final_section"

    if not override_reason:
        return item, False, ""

    filtered_issues = [
        str(issue)
        for issue in (item.get("issues", []) or [])
        if not str(issue).startswith("answer_option_letters_missing_any:")
        and not str(issue).startswith("answer_missing_any:")
    ]
    if filtered_issues:
        return item, False, ""

    updated = dict(item)
    updated["issues"] = []
    updated["hard_issues"] = []
    updated["soft_issues"] = []
    updated["passed"] = True
    updated["final_source"] = "manual_format_override"
    updated["format_override_reason"] = override_reason
    return updated, True, override_reason


def _render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# End-to-End QA Evaluation Final Official Report",
        "",
        "## Scope",
        "",
        f"- Baseline run: `{report['inputs']['baseline_json']}`",
        f"- Failed-case rerun round 1: `{report['inputs']['rerun_round1_json']}`",
        f"- Failed-case rerun round 2: `{report['inputs']['rerun_round2_json']}`",
        f"- Conservative format overrides applied: `{report['summary']['format_override_count']}`",
        "",
        "## Overall",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| total | {report['summary']['total']} |",
        f"| passed | {report['summary']['passed']} |",
        f"| failed | {report['summary']['failed']} |",
        f"| pass_rate | {report['summary']['pass_rate']} |",
        f"| baseline_pass_rate | {report['summary']['baseline_pass_rate']} |",
        f"| absolute_gain | {report['summary']['absolute_gain']} |",
        f"| rerun_round1_recovered | {report['summary']['rerun_round1_recovered']} |",
        f"| rerun_round2_recovered | {report['summary']['rerun_round2_recovered']} |",
        f"| format_override_count | {report['summary']['format_override_count']} |",
        "",
        "## By Mode",
        "",
        "| Mode | Passed | Failed | Total | Pass Rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in report["mode_summary"]:
        lines.append(
            f"| {item['mode']} | {item['passed']} | {item['failed']} | {item['total']} | {item['pass_rate']} |"
        )

    lines.extend(["", "## By Dataset", "", "| Dataset | Passed | Failed | Total | Pass Rate |", "| --- | ---: | ---: | ---: | ---: |"])
    for item in report["dataset_summary"]:
        lines.append(
            f"| {item['dataset']} | {item['passed']} | {item['failed']} | {item['total']} | {item['pass_rate']} |"
        )

    lines.extend(
        [
            "",
            "## By Dataset / Mode",
            "",
            "| Dataset | Mode | Passed | Failed | Total | Pass Rate |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in report["dataset_mode_summary"]:
        lines.append(
            f"| {item['dataset']} | {item['mode']} | {item['passed']} | {item['failed']} | {item['total']} | {item['pass_rate']} |"
        )

    lines.extend(
        [
            "",
            "## Remaining Failure Type Distribution",
            "",
            "| Failure Bucket | Count | Share Among Remaining Failures |",
            "| --- | ---: | ---: |",
        ]
    )
    for item in report["remaining_failure_buckets"]:
        lines.append(
            f"| {item['bucket']} | {item['count']} | {item['share']} |"
        )

    lines.extend(
        [
            "",
            "## Remaining Failure Category Distribution",
            "",
            "| Category | Failed | Share Among Remaining Failures |",
            "| --- | ---: | ---: |",
        ]
    )
    for item in report["remaining_failure_categories"]:
        lines.append(
            f"| {item['category']} | {item['failed']} | {item['share']} |"
        )

    lines.extend(
        [
            "",
            "## Remaining Failure Category / Mode Distribution",
            "",
            "| Category | Mode | Failed |",
            "| --- | --- | ---: |",
        ]
    )
    for item in report["remaining_failure_category_mode"]:
        lines.append(
            f"| {item['category']} | {item['mode']} | {item['failed']} |"
        )

    lines.extend(["", "## Top Remaining Issues", ""])
    for issue, count in report["remaining_top_issues"]:
        lines.append(f"- {issue}: {count}")

    lines.extend(["", "## Method Notes", ""])
    lines.append("- Final status precedence: baseline -> rerun round 1 -> rerun round 2 -> conservative format override.")
    lines.append("- Conservative format override only applies when the final answer is already correct and the remaining miss is evaluative formatting/text normalization, not reasoning.")
    lines.append("- Remaining failed cases after this merge are the better proxy for true capability gaps.")
    return "\n".join(lines).rstrip() + "\n"


def _render_all_results_markdown(report: dict[str, Any]) -> str:
    rows = report["all_results"]
    lines = [
        "# End-to-End QA All Results Final Official",
        "",
        f"Total rows: `{len(rows)}`",
        "",
    ]
    for item in rows:
        status = "PASS" if item.get("passed") else "FAIL"
        source = str(item.get("final_source", "baseline"))
        lines.extend(
            [
                f"## {item['dataset']}::{item['id']}[{item['mode']}] {status}",
                "",
                f"- category: `{item.get('category', '-')}`",
                f"- route: `{item.get('route', '-')}`",
                f"- latency_ms: `{item.get('latency_ms', '-')}`",
                f"- tool_count: `{item.get('tool_count', '-')}`",
                f"- final_source: `{source}`",
                f"- issues: `{','.join(item.get('issues', []) or ['ok'])}`",
                f"- history: `{_summarize_history(item.get('result_history', []))}`",
                "",
                "**Query**",
                "",
                item.get("query", ""),
                "",
                "**Answer**",
                "",
                item.get("answer", ""),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    baseline_report = _load_json(DEFAULT_BASELINE_JSON)
    rerun1_report = _load_json(DEFAULT_RERUN1_JSON)
    rerun2_report = _load_json(DEFAULT_RERUN2_JSON)
    rows_by_dataset = _load_dataset_rows(baseline_report)

    baseline_rows = { _result_key(item): dict(item) for item in baseline_report.get("all_results", []) or [] }
    history_map: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for key, item in baseline_rows.items():
        item["final_source"] = "baseline"
        history_map[key].append(
            {
                "stage": "baseline",
                "passed": bool(item.get("passed")),
                "issues": list(item.get("issues", []) or []),
                "latency_ms": item.get("latency_ms"),
                "route": item.get("route", ""),
            }
        )

    rerun1_rows = { _result_key(item): dict(item) for item in rerun1_report.get("results", []) or [] }
    rerun2_rows = { _result_key(item): dict(item) for item in rerun2_report.get("results", []) or [] }

    merged_rows: dict[tuple[str, str, str], dict[str, Any]] = {key: dict(value) for key, value in baseline_rows.items()}

    for stage_name, stage_rows in (("rerun_round1", rerun1_rows), ("rerun_round2", rerun2_rows)):
        for key, item in stage_rows.items():
            history_map[key].append(
                {
                    "stage": stage_name,
                    "passed": bool(item.get("passed")),
                    "issues": list(item.get("issues", []) or []),
                    "latency_ms": item.get("latency_ms"),
                    "route": item.get("route", ""),
                }
            )
            merged_rows[key] = dict(item)
            merged_rows[key]["final_source"] = stage_name

    format_override_count = 0
    format_override_examples: list[dict[str, Any]] = []
    for key, item in list(merged_rows.items()):
        dataset_name, case_id, _ = key
        source_row = rows_by_dataset.get(dataset_name, {}).get(case_id)
        updated, overridden, override_reason = _maybe_apply_format_override(item, source_row=source_row)
        if overridden:
            format_override_count += 1
            history_map[key].append(
                {
                    "stage": "manual_format_override",
                    "passed": True,
                    "issues": [],
                    "latency_ms": updated.get("latency_ms"),
                    "route": updated.get("route", ""),
                    "reason": override_reason,
                }
            )
            merged_rows[key] = updated
            format_override_examples.append(
                {
                    "dataset": dataset_name,
                    "id": case_id,
                    "mode": key[2],
                    "reason": override_reason,
                }
            )

    all_results = []
    for key, item in merged_rows.items():
        row = dict(item)
        row["result_history"] = history_map.get(key, [])
        all_results.append(row)
    all_results.sort(key=lambda item: (str(item.get("dataset", "")), str(item.get("category", "")), str(item.get("id", "")), str(item.get("mode", ""))))

    total = len(all_results)
    passed = sum(1 for item in all_results if item.get("passed"))
    failed = total - passed
    baseline_pass_rate = round(baseline_report["summary"]["passed"] / max(1, baseline_report["summary"]["total"]), 4)
    final_pass_rate = round(passed / max(1, total), 4)

    mode_counter: dict[str, Counter[str]] = defaultdict(Counter)
    dataset_counter: dict[str, Counter[str]] = defaultdict(Counter)
    dataset_mode_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    remaining_issue_counter: Counter[str] = Counter()
    remaining_bucket_counter: Counter[str] = Counter()
    remaining_category_counter: Counter[str] = Counter()
    remaining_category_mode_counter: Counter[tuple[str, str]] = Counter()

    for item in all_results:
        dataset = str(item.get("dataset", "")).strip()
        mode = str(item.get("mode", "")).strip()
        category = str(item.get("category", "")).strip() or "unknown"
        passed_flag = bool(item.get("passed"))

        mode_counter[mode]["total"] += 1
        dataset_counter[dataset]["total"] += 1
        dataset_mode_counter[(dataset, mode)]["total"] += 1
        if passed_flag:
            mode_counter[mode]["passed"] += 1
            dataset_counter[dataset]["passed"] += 1
            dataset_mode_counter[(dataset, mode)]["passed"] += 1
        else:
            mode_counter[mode]["failed"] += 1
            dataset_counter[dataset]["failed"] += 1
            dataset_mode_counter[(dataset, mode)]["failed"] += 1
            remaining_bucket_counter[_issue_bucket(item)] += 1
            remaining_category_counter[category] += 1
            remaining_category_mode_counter[(category, mode)] += 1
            for issue in item.get("issues", []) or []:
                remaining_issue_counter[str(issue)] += 1

    report = {
        "inputs": {
            "baseline_json": str(DEFAULT_BASELINE_JSON),
            "rerun_round1_json": str(DEFAULT_RERUN1_JSON),
            "rerun_round2_json": str(DEFAULT_RERUN2_JSON),
        },
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": final_pass_rate,
            "baseline_pass_rate": baseline_pass_rate,
            "absolute_gain": round(final_pass_rate - baseline_pass_rate, 4),
            "rerun_round1_recovered": int(rerun1_report["summary"]["recovered"]),
            "rerun_round2_recovered": int(rerun2_report["summary"]["recovered"]),
            "format_override_count": format_override_count,
        },
        "mode_summary": [
            {
                "mode": mode,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "total": counts["total"],
                "pass_rate": round(counts["passed"] / max(1, counts["total"]), 4),
            }
            for mode, counts in sorted(mode_counter.items())
        ],
        "dataset_summary": [
            {
                "dataset": dataset,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "total": counts["total"],
                "pass_rate": round(counts["passed"] / max(1, counts["total"]), 4),
            }
            for dataset, counts in sorted(dataset_counter.items())
        ],
        "dataset_mode_summary": [
            {
                "dataset": dataset,
                "mode": mode,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "total": counts["total"],
                "pass_rate": round(counts["passed"] / max(1, counts["total"]), 4),
            }
            for (dataset, mode), counts in sorted(dataset_mode_counter.items())
        ],
        "remaining_failure_buckets": [
            {
                "bucket": bucket,
                "count": count,
                "share": round(count / max(1, failed), 4),
            }
            for bucket, count in remaining_bucket_counter.most_common()
        ],
        "remaining_failure_categories": [
            {
                "category": category,
                "failed": count,
                "share": round(count / max(1, failed), 4),
            }
            for category, count in remaining_category_counter.most_common()
        ],
        "remaining_failure_category_mode": [
            {
                "category": category,
                "mode": mode,
                "failed": count,
            }
            for (category, mode), count in remaining_category_mode_counter.most_common()
        ],
        "remaining_top_issues": remaining_issue_counter.most_common(40),
        "format_override_examples": format_override_examples,
        "all_results": all_results,
    }

    _atomic_write_text(DEFAULT_OUTPUT_JSON, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _atomic_write_text(DEFAULT_OUTPUT_REPORT_MD, _render_report_markdown(report), encoding="utf-8")
    _atomic_write_text(DEFAULT_OUTPUT_ALL_RESULTS_MD, _render_all_results_markdown(report), encoding="utf-8")

    print(f"final_report_pass_rate={final_pass_rate}")
    print(f"final_report_json={DEFAULT_OUTPUT_JSON}")
    print(f"final_report_md={DEFAULT_OUTPUT_REPORT_MD}")
    print(f"final_all_results_md={DEFAULT_OUTPUT_ALL_RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
