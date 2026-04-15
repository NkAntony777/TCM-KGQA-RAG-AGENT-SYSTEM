from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import get_settings


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_section_summary_ablation_8.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8002"


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    return [item for item in payload if isinstance(item, dict)]


def _post_json(url: str, payload: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("qa_response_not_object")
    return parsed


def _books_from_answer(data: dict[str, Any]) -> set[str]:
    books: set[str] = set()
    for item in data.get("factual_evidence", []) or []:
        if not isinstance(item, dict):
            continue
        source_book = str(item.get("source_book", "")).strip()
        if source_book:
            books.add(source_book)
    for item in data.get("book_citations", []) or []:
        text = str(item).strip()
        if not text:
            continue
        books.add(text.split("/", 1)[0])
    return books


def _eval_answer(case: dict[str, Any], mode: str, response_data: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    answer = str(response_data.get("answer", "") or "")
    books = _books_from_answer(response_data)
    expected_books = [str(item).strip() for item in case.get("expected_books_any", []) if str(item).strip()] if isinstance(case.get("expected_books_any", []), list) else []
    expected_tokens = [str(item).strip() for item in case.get("expected_answer_any", []) if str(item).strip()] if isinstance(case.get("expected_answer_any", []), list) else []
    generation_backend = str(response_data.get("generation_backend", "") or "")
    route = response_data.get("route", {}) if isinstance(response_data.get("route"), dict) else {}
    notes = response_data.get("notes", []) if isinstance(response_data.get("notes"), list) else []
    diagnostics = response_data.get("generation_diagnostics", {}) if isinstance(response_data.get("generation_diagnostics"), dict) else {}

    book_hit = any(book in books for book in expected_books) if expected_books else False
    token_hits = sum(1 for token in expected_tokens if token in answer)
    answer_len = len(answer.strip())
    fallback_detected = "fallback" in generation_backend.lower() or any("fallback" in str(note).lower() for note in notes)
    score = 0.0
    score += 2.0 if answer_len >= 300 else (1.0 if answer_len >= 120 else 0.0)
    score += 1.5 if book_hit else 0.0
    score += min(token_hits, 4) * 0.75
    score -= 0.5 if fallback_detected else 0.0
    return {
        "id": str(case.get("id", "")),
        "mode": mode,
        "latency_ms": round(latency_ms, 1),
        "status": response_data.get("status"),
        "final_route": route.get("final_route"),
        "generation_backend": generation_backend,
        "fallback_detected": fallback_detected,
        "answer_len": answer_len,
        "book_hit": book_hit,
        "token_hits": token_hits,
        "score": round(score, 2),
        "books": sorted(books),
        "notes": notes[:8],
        "generation_diagnostics": diagnostics,
    }


def _run_condition(*, label: str, dataset: list[dict[str, Any]], base_url: str, top_k: int, timeout_s: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = sum(len(case.get("mode_expectations", ["quick", "deep"])) if isinstance(case.get("mode_expectations"), list) else 2 for case in dataset)
    completed = 0
    for case in dataset:
        modes = case.get("mode_expectations", ["quick", "deep"])
        if not isinstance(modes, list) or not modes:
            modes = ["quick", "deep"]
        for mode in modes:
            completed += 1
            query = str(case.get("query", "")).strip()
            started = time.perf_counter()
            request_payload = {"query": query, "mode": mode, "top_k": top_k}
            try:
                response = _post_json(f"{base_url}/api/qa/answer", request_payload, timeout_s=timeout_s)
                latency_ms = (time.perf_counter() - started) * 1000.0
                data = response.get("data", {}) if isinstance(response.get("data"), dict) else {}
                row = _eval_answer(case, mode, data, latency_ms)
            except HTTPError as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                row = {
                    "id": str(case.get("id", "")),
                    "mode": mode,
                    "latency_ms": round(latency_ms, 1),
                    "status": "request_error",
                    "final_route": "",
                    "generation_backend": "",
                    "fallback_detected": False,
                    "answer_len": 0,
                    "book_hit": False,
                    "token_hits": 0,
                    "score": 0.0,
                    "books": [],
                    "notes": [f"http_{exc.code}"],
                    "generation_diagnostics": {},
                }
            except URLError as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                row = {
                    "id": str(case.get("id", "")),
                    "mode": mode,
                    "latency_ms": round(latency_ms, 1),
                    "status": "request_error",
                    "final_route": "",
                    "generation_backend": "",
                    "fallback_detected": False,
                    "answer_len": 0,
                    "book_hit": False,
                    "token_hits": 0,
                    "score": 0.0,
                    "books": [],
                    "notes": [f"url_error:{exc}"],
                    "generation_diagnostics": {},
                }
            rows.append(row)
            print(
                f"[qa-summary-ablation] {label} {completed:02d}/{total} "
                f"{row['id']}[{mode}] latency={row['latency_ms']:.1f}ms score={row['score']:.2f} "
                f"book_hit={row['book_hit']} fallback={row['fallback_detected']}",
                flush=True,
            )
    avg_latency = round(sum(float(item.get("latency_ms", 0.0) or 0.0) for item in rows) / max(len(rows), 1), 1)
    avg_score = round(sum(float(item.get("score", 0.0) or 0.0) for item in rows) / max(len(rows), 1), 2)
    return {
        "label": label,
        "avg_latency_ms": avg_latency,
        "avg_score": avg_score,
        "book_hit_rate": round(sum(1 for item in rows if item.get("book_hit")) / max(len(rows), 1), 4),
        "fallback_rate": round(sum(1 for item in rows if item.get("fallback_detected")) / max(len(rows), 1), 4),
        "rows": rows,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    baseline = summary["baseline"]
    enhanced = summary["enhanced"]
    lines = [
        "# QA Section Summary Ablation",
        "",
        "## Aggregate",
        "",
        "| Condition | avg_latency_ms | avg_score | book_hit_rate | fallback_rate |",
        "| --- | --- | --- | --- | --- |",
        f"| baseline_no_summary_cache | {baseline['avg_latency_ms']} | {baseline['avg_score']} | {baseline['book_hit_rate']:.2%} | {baseline['fallback_rate']:.2%} |",
        f"| enhanced_with_summary_cache | {enhanced['avg_latency_ms']} | {enhanced['avg_score']} | {enhanced['book_hit_rate']:.2%} | {enhanced['fallback_rate']:.2%} |",
        "",
        "## Per Case",
        "",
        "| ID | Mode | baseline_latency | baseline_score | enhanced_latency | enhanced_score | delta_score |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    baseline_rows = {(row["id"], row["mode"]): row for row in baseline["rows"]}
    enhanced_rows = {(row["id"], row["mode"]): row for row in enhanced["rows"]}
    for key, left in baseline_rows.items():
        right = enhanced_rows.get(key, {})
        delta = round(float(right.get("score", 0.0) or 0.0) - float(left.get("score", 0.0) or 0.0), 2)
        lines.append(
            f"| {left['id']} | {left['mode']} | {left['latency_ms']} | {left['score']} | {right.get('latency_ms', '-')} | {right.get('score', '-')} | {delta} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end QA ablation for section summary cache.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "qa_section_summary_ablation_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent / "docs" / "QA_Section_Summary_Ablation_Latest.md")
    args = parser.parse_args()

    dataset = _load_dataset(args.dataset)
    settings = get_settings()
    cache_path = settings.backend_dir / "storage" / "section_summary_cache.sqlite"
    backup_path = cache_path.with_suffix(".sqlite.bak_ablation")

    baseline = {}
    enhanced = {}
    try:
        if cache_path.exists():
            shutil.copy2(cache_path, backup_path)
            cache_path.unlink()
        baseline = _run_condition(
            label="baseline",
            dataset=dataset,
            base_url=args.base_url.rstrip("/"),
            top_k=args.top_k,
            timeout_s=args.timeout,
        )
    finally:
        if backup_path.exists():
            shutil.move(backup_path, cache_path)

    enhanced = _run_condition(
        label="enhanced",
        dataset=dataset,
        base_url=args.base_url.rstrip("/"),
        top_k=args.top_k,
        timeout_s=args.timeout,
    )

    summary = {
        "dataset": str(args.dataset),
        "total_cases": len(dataset),
        "baseline": baseline,
        "enhanced": enhanced,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps({"output_json": str(args.output_json), "output_md": str(args.output_md)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
