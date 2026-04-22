from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8002"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("dataset must be a list")
    return [item for item in data if isinstance(item, dict)]


def _flatten_books(response_data: dict[str, Any]) -> set[str]:
    books: set[str] = set()
    for item in response_data.get("factual_evidence", []) or []:
        if not isinstance(item, dict):
            continue
        source_book = str(item.get("source_book", "")).strip()
        if source_book:
            books.add(_normalize_book(source_book))
    for text in response_data.get("citations", []) or []:
        value = str(text).strip()
        if value:
            books.add(_normalize_book(value.split("/", 1)[0]))
    return books


def _normalize_book(value: str) -> str:
    text = str(value or "").strip()
    if "-" in text and text.split("-", 1)[0].isdigit():
        text = text.split("-", 1)[1].strip()
    return text


def _flatten_predicates(response_data: dict[str, Any]) -> set[str]:
    predicates: set[str] = set()
    for item in response_data.get("factual_evidence", []) or []:
        if not isinstance(item, dict):
            continue
        predicate = str(item.get("predicate", "")).strip()
        if predicate:
            predicates.add(predicate)
    return predicates


def _evaluate_case(
    case: dict[str, Any],
    *,
    mode: str,
    response_data: dict[str, Any],
    latency_ms: float,
    warning_issue_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    answer = str(response_data.get("answer", "") or "")
    route_meta = response_data.get("route", {}) if isinstance(response_data.get("route"), dict) else {}
    final_route = str(route_meta.get("final_route", "") or "")
    executed_routes = [str(item).strip() for item in (route_meta.get("executed_routes", []) or []) if str(item).strip()] if isinstance(route_meta.get("executed_routes", []), list) else []
    predicates = _flatten_predicates(response_data)
    books = _flatten_books(response_data)
    tool_trace = response_data.get("tool_trace", []) if isinstance(response_data.get("tool_trace"), list) else []

    expected_route = str(case.get("expected_route", "")).strip()
    expected_routes_any = [str(item).strip() for item in (case.get("expected_routes_any", []) or []) if str(item).strip()]
    if expected_routes_any:
        if final_route not in expected_routes_any:
            issues.append(f"route_mismatch:{final_route or 'missing'}!={'|'.join(expected_routes_any)}")
    elif expected_route and final_route != expected_route:
        issues.append(f"route_mismatch:{final_route or 'missing'}!=${expected_route}".replace("$", ""))

    executed_routes_contains_any = [str(item).strip() for item in (case.get("executed_routes_contains_any", []) or []) if str(item).strip()]
    if executed_routes_contains_any and not any(item in executed_routes for item in executed_routes_contains_any):
        issues.append("executed_route_missing_any:" + "|".join(executed_routes_contains_any))

    for token in case.get("answer_contains_all", []) or []:
        token_text = str(token).strip()
        if token_text and token_text not in answer:
            issues.append(f"answer_missing_all:{token_text}")

    normalized_answer_letters = "".join(ch for ch in answer.upper() if "A" <= ch <= "Z")
    expected_option_letters = [
        "".join(ch for ch in str(token).upper() if "A" <= ch <= "Z")
        for token in (case.get("answer_option_letters_any", []) or [])
        if "".join(ch for ch in str(token).upper() if "A" <= ch <= "Z")
    ]
    if expected_option_letters:
        letter_sets = [set(token) for token in expected_option_letters if token]
        normalized_answer_set = set(normalized_answer_letters)
        if not any(letter_set and letter_set.issubset(normalized_answer_set) for letter_set in letter_sets):
            issues.append("answer_option_letters_missing_any:" + "|".join(expected_option_letters))

    any_tokens = [str(token).strip() for token in (case.get("answer_contains_any", []) or []) if str(token).strip()]
    if any_tokens and not any(token in answer for token in any_tokens):
        issues.append("answer_missing_any:" + "|".join(any_tokens))

    forbid_tokens = [str(token).strip() for token in (case.get("answer_forbid", []) or []) if str(token).strip()]
    for token in forbid_tokens:
        if token in answer:
            issues.append(f"answer_contains_forbidden:{token}")

    predicate_any = [str(token).strip() for token in (case.get("evidence_predicates_any", []) or []) if str(token).strip()]
    if predicate_any and not predicates.intersection(predicate_any):
        issues.append("predicate_missing_any:" + "|".join(predicate_any))

    books_any = [str(token).strip() for token in (case.get("evidence_source_books_any", []) or []) if str(token).strip()]
    if books_any and not any(book in books for book in books_any):
        issues.append("book_missing_any:" + "|".join(books_any))

    if mode == "deep" and case.get("expected_route") == "hybrid" and len(tool_trace) < 2:
        issues.append("deep_trace_too_shallow")

    case_warning_prefixes = [
        str(item).strip()
        for item in (case.get("warning_issue_prefixes_any", []) or [])
        if str(item).strip()
    ]
    mode_warning_prefixes = []
    raw_mode_warning = case.get("warning_issue_prefixes_by_mode", {})
    if isinstance(raw_mode_warning, dict):
        mode_warning_prefixes = [
            str(item).strip()
            for item in (raw_mode_warning.get(mode, []) or [])
            if str(item).strip()
        ]
    warning_prefixes = tuple(
        str(item)
        for item in [*(warning_issue_prefixes or []), *case_warning_prefixes, *mode_warning_prefixes]
        if str(item).strip()
    )
    hard_issues: list[str] = []
    soft_issues: list[str] = []
    for issue in issues:
        if warning_prefixes and any(issue.startswith(prefix) for prefix in warning_prefixes):
            soft_issues.append(issue)
        else:
            hard_issues.append(issue)

    return {
        "id": case["id"],
        "category": case.get("category", "unknown"),
        "mode": mode,
        "query": case["query"],
        "latency_ms": round(latency_ms, 1),
        "route": final_route,
        "issues": issues,
        "hard_issues": hard_issues,
        "soft_issues": soft_issues,
        "answer": answer,
        "predicates": sorted(predicates),
        "books": sorted(books),
        "executed_routes": executed_routes,
        "tool_count": len(tool_trace),
        "passed": not hard_issues,
    }


def _request_failure_case(case: dict[str, Any], *, mode: str, latency_ms: float, issue: str) -> dict[str, Any]:
    return {
        "id": case.get("id", "unknown"),
        "category": case.get("category", "unknown"),
        "mode": mode,
        "query": case.get("query", ""),
        "latency_ms": round(latency_ms, 1),
        "route": "",
        "issues": [issue],
        "hard_issues": [issue],
        "soft_issues": [],
        "answer": "",
        "predicates": [],
        "books": [],
        "executed_routes": [],
        "tool_count": 0,
        "passed": False,
    }


def _run_single_case(
    case: dict[str, Any],
    *,
    mode: str,
    base_url: str,
    top_k: int,
    timeout: float,
    warning_issue_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    query = str(case.get("query", "")).strip()
    started = time.perf_counter()
    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            response = client.post(
                f"/api/qa/answer?mode={mode}",
                json={"query": query, "mode": mode, "top_k": top_k},
            )
        latency_ms = (time.perf_counter() - started) * 1000
    except httpx.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return _request_failure_case(
            case,
            mode=mode,
            latency_ms=latency_ms,
            issue=f"request_error:{exc.__class__.__name__}",
        )

    try:
        payload = response.json()
    except ValueError:
        return _request_failure_case(
            case,
            mode=mode,
            latency_ms=latency_ms,
            issue="response_error:invalid_json",
        )

    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return _request_failure_case(
            case,
            mode=mode,
            latency_ms=latency_ms,
            issue="response_error:missing_data",
        )

    return _evaluate_case(
        case,
        mode=mode,
        response_data=data,
        latency_ms=latency_ms,
        warning_issue_prefixes=warning_issue_prefixes,
    )


def run_probe(
    *,
    dataset: list[dict[str, Any]],
    base_url: str,
    modes: list[str],
    top_k: int,
    timeout: float,
    warning_issue_prefixes: list[str] | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    effective_cases = [case for case in dataset if str(case.get("query", "")).strip()]
    total_cases = len(effective_cases)
    total_runs = total_cases * max(1, len(modes))
    requested_jobs: list[tuple[dict[str, Any], str]] = [
        (case, mode)
        for case in effective_cases
        for mode in modes
    ]
    completed_runs = 0
    passed_runs = 0

    if max(1, int(workers)) <= 1:
        for case, mode in requested_jobs:
            completed_runs += 1
            print(
                f"[qa-probe] {completed_runs:04d}/{total_runs:04d} "
                f"({completed_runs / max(1, total_runs):.1%}) {case.get('id', 'unknown')} {mode} start",
                flush=True,
            )
            evaluated = _run_single_case(
                case,
                mode=mode,
                base_url=base_url,
                top_k=top_k,
                timeout=timeout,
                warning_issue_prefixes=warning_issue_prefixes,
            )
            results.append(evaluated)
            if evaluated["passed"]:
                passed_runs += 1
            issue_text = ",".join(evaluated["issues"]) if evaluated["issues"] else "ok"
            print(
                f"[qa-probe] {completed_runs:04d}/{total_runs:04d} "
                f"({completed_runs / max(1, total_runs):.1%}) {case.get('id', 'unknown')} {mode} "
                f"done route={evaluated['route'] or '-'} latency_ms={evaluated['latency_ms']:.1f} "
                f"passed={passed_runs}/{completed_runs} issues={issue_text}",
                flush=True,
            )
    else:
        print(
            f"[qa-probe] parallel mode enabled: workers={max(1, int(workers))}, total_runs={total_runs}",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
            future_map = {
                executor.submit(
                    _run_single_case,
                    case,
                    mode=mode,
                    base_url=base_url,
                    top_k=top_k,
                    timeout=timeout,
                    warning_issue_prefixes=warning_issue_prefixes,
                ): (case, mode)
                for case, mode in requested_jobs
            }
            for future in as_completed(future_map):
                case, mode = future_map[future]
                completed_runs += 1
                evaluated = future.result()
                results.append(evaluated)
                if evaluated["passed"]:
                    passed_runs += 1
                issue_text = ",".join(evaluated["issues"]) if evaluated["issues"] else "ok"
                print(
                    f"[qa-probe] {completed_runs:04d}/{total_runs:04d} "
                    f"({completed_runs / max(1, total_runs):.1%}) {case.get('id', 'unknown')} {mode} "
                    f"done route={evaluated['route'] or '-'} latency_ms={evaluated['latency_ms']:.1f} "
                    f"passed={passed_runs}/{completed_runs} issues={issue_text}",
                    flush=True,
                )

    failures = [item for item in results if not item["passed"]]
    soft_issue_counter = Counter()
    by_category: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["category"]].append(item)
    for category, items in grouped.items():
        by_category[category] = {
            "total": len(items),
            "failed": sum(1 for item in items if not item["passed"]),
            "avg_latency_ms": round(sum(item["latency_ms"] for item in items) / max(1, len(items)), 1),
        }

    issue_counter = Counter()
    for item in failures:
        for issue in item["hard_issues"]:
            issue_counter[issue] += 1
    for item in results:
        for issue in item.get("soft_issues", []):
            soft_issue_counter[issue] += 1

    return {
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "modes": modes,
        "top_issues": issue_counter.most_common(20),
        "soft_top_issues": soft_issue_counter.most_common(20),
        "by_category": by_category,
        "results": sorted(
            results,
            key=lambda item: (
                str(item.get("category", "")),
                str(item.get("id", "")),
                str(item.get("mode", "")),
            ),
        ),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe QA weak spots across quick/deep modes.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--modes", nargs="+", default=["quick", "deep"])
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = run_probe(
        dataset=load_dataset(args.dataset),
        base_url=args.base_url,
        modes=args.modes,
        top_k=args.top_k,
        timeout=args.timeout,
        workers=max(1, int(args.workers)),
    )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"QA weakness probe: {summary['passed']}/{summary['total']} passed")
        print("Top issues:")
        for issue, count in summary["top_issues"]:
            print(f"- {issue}: {count}")
        print("Category summary:")
        for category, item in summary["by_category"].items():
            print(f"- {category}: failed={item['failed']}/{item['total']}, avg_latency_ms={item['avg_latency_ms']}")
        if summary["failures"]:
            print("Failures:")
            for item in summary["failures"]:
                print(f"- {item['id']}[{item['mode']}] route={item['route']} issues={item['issues']}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
