from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_DB = BACKEND_ROOT / "storage" / "benchmark_traceable_classics_candidates.sqlite"
DEFAULT_EVAL_JSON = BACKEND_ROOT / "eval" / "paper" / "traceable_classics_benchmark_test_eval_relaxed.json"
DEFAULT_DATASET_JSON = BACKEND_ROOT / "eval" / "datasets" / "paper" / "traceable_classics_benchmark_test.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "paper" / "traceable_classics_benchmark_test_regraded.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Traceable_Classics_Benchmark_Test_Regraded.md"


def _normalize_loose_text(value: str) -> str:
    return (
        str(value or "")
        .replace("《", "")
        .replace("》", "")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .replace("'", "")
        .replace("，", "")
        .replace(",", "")
        .replace("。", "")
        .replace("：", "")
        .replace(":", "")
        .replace("；", "")
        .replace(";", "")
        .replace("、", "")
        .replace("（", "")
        .replace("）", "")
        .replace("(", "")
        .replace(")", "")
        .replace("\n", "")
        .replace("\r", "")
        .replace("\t", "")
        .replace(" ", "")
        .strip()
    )


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(row.get("match_snippet", "") or ""),
            str(row.get("section_summary", "") or ""),
            str(row.get("book_name", "") or ""),
            str(row.get("chapter_title", "") or ""),
        ]
    )


def _subject_hit(row: dict[str, Any], subject: str) -> bool:
    normalized_subject = _normalize_loose_text(subject)
    chapter = _normalize_loose_text(str(row.get("chapter_title", "") or ""))
    text = _normalize_loose_text(_row_text(row))
    return bool(normalized_subject) and (normalized_subject in chapter or normalized_subject in text)


def _answer_hit(row: dict[str, Any], acceptable_answers: list[str]) -> bool:
    text = _normalize_loose_text(_row_text(row))
    return any(_normalize_loose_text(answer) in text for answer in acceptable_answers if _normalize_loose_text(answer))


def _book_hit(row: dict[str, Any], acceptable_books: list[str]) -> bool:
    book_name = _normalize_loose_text(str(row.get("book_name", "") or ""))
    return any(_normalize_loose_text(book) == book_name for book in acceptable_books if _normalize_loose_text(book))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset_case_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    return {str(item["case_id"]).strip(): item for item in payload if isinstance(item, dict) and str(item.get("case_id", "")).strip()}


def _acceptable_map(candidate_db: Path, dataset_cases: dict[str, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    conn = sqlite3.connect(candidate_db)
    conn.row_factory = sqlite3.Row
    try:
        pairs = {
            (str(case["subject"]).strip(), str(case["predicate"]).strip())
            for case in dataset_cases.values()
        }
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for subject, predicate in pairs:
            rows = conn.execute(
                """
                SELECT object, source_book, source_book_clean, source_chapter
                FROM triples
                WHERE subject = ? AND predicate = ?
                """,
                (subject, predicate),
            ).fetchall()
            answers: list[str] = []
            books: list[str] = []
            chapters: list[str] = []
            seen_answers: set[str] = set()
            seen_books: set[str] = set()
            seen_chapters: set[str] = set()
            for row in rows:
                answer = str(row["object"] or "").strip()
                if answer and answer not in seen_answers:
                    seen_answers.add(answer)
                    answers.append(answer)
                for field in ("source_book", "source_book_clean"):
                    book = str(row[field] or "").strip()
                    if book and book not in seen_books:
                        seen_books.add(book)
                        books.append(book)
                chapter = str(row["source_chapter"] or "").strip()
                if chapter and chapter not in seen_chapters:
                    seen_chapters.add(chapter)
                    chapters.append(chapter)
            result[(subject, predicate)] = {
                "answers": answers,
                "books": books,
                "chapters": chapters,
            }
        return result
    finally:
        conn.close()


def _regrade_case(
    case_payload: dict[str, Any],
    dataset_case: dict[str, Any],
    acceptable: dict[str, Any],
) -> dict[str, Any]:
    subject = str(dataset_case["subject"]).strip()
    task_family = str(dataset_case["task_family"]).strip()
    rows = case_payload.get("rows", [])
    top1 = rows[:1]
    topk = rows[:3]

    top1_subject = any(_subject_hit(row, subject) for row in top1)
    topk_subject = any(_subject_hit(row, subject) for row in topk)
    top1_answer = any(_answer_hit(row, acceptable["answers"]) for row in top1)
    topk_answer = any(_answer_hit(row, acceptable["answers"]) for row in topk)
    top1_book = any(_book_hit(row, acceptable["books"]) for row in top1)
    topk_book = any(_book_hit(row, acceptable["books"]) for row in topk)

    if task_family == "source_locate":
        top1_success = top1_subject
        topk_success = topk_subject
    else:
        top1_success = top1_subject and top1_answer
        topk_success = topk_subject and topk_answer

    return {
        "top1_subject_hit": top1_subject,
        "topk_subject_hit": topk_subject,
        "top1_answer_asset_hit": top1_answer,
        "topk_answer_asset_hit": topk_answer,
        "top1_book_asset_hit": top1_book,
        "topk_book_asset_hit": topk_book,
        "top1_regraded_success": top1_success,
        "topk_regraded_success": topk_success,
    }


def _rate(cases: list[dict[str, Any]], field: str) -> float | None:
    if not cases:
        return None
    return round(sum(1 for case in cases if case["regraded_metrics"].get(field)) / len(cases), 4)


def _summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "top1_subject_hit_rate": _rate(cases, "top1_subject_hit"),
        "topk_subject_hit_rate": _rate(cases, "topk_subject_hit"),
        "top1_answer_asset_hit_rate": _rate(cases, "top1_answer_asset_hit"),
        "topk_answer_asset_hit_rate": _rate(cases, "topk_answer_asset_hit"),
        "top1_book_asset_hit_rate": _rate(cases, "top1_book_asset_hit"),
        "topk_book_asset_hit_rate": _rate(cases, "topk_book_asset_hit"),
        "top1_regraded_success_rate": _rate(cases, "top1_regraded_success"),
        "topk_regraded_success_rate": _rate(cases, "topk_regraded_success"),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Traceable Classics Benchmark Regraded",
        "",
        "本报告基于项目资产中的 `subject + predicate` 可接受答案集合，对已有评测结果重新判分。",
        "",
    ]
    for method_name in ("files_first", "vector"):
        summary = report[method_name]["summary"]
        lines.extend(
            [
                f"## {method_name}",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
            ]
        )
        for key, value in summary.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Regrade existing traceable eval outputs against asset-supported acceptable answers.")
    parser.add_argument("--candidate-db", type=Path, default=DEFAULT_CANDIDATE_DB)
    parser.add_argument("--eval-json", type=Path, default=DEFAULT_EVAL_JSON)
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    eval_report = _load_json(args.eval_json)
    dataset_cases = _dataset_case_map(args.dataset_json)
    acceptable_map = _acceptable_map(args.candidate_db, dataset_cases)

    output: dict[str, Any] = {"settings": {"eval_json": str(args.eval_json), "dataset_json": str(args.dataset_json)}}
    for method_key in ("files_first", "vector"):
        regraded_cases: list[dict[str, Any]] = []
        for case_payload in eval_report[method_key]["cases"]:
            case_id = str(case_payload["case"]["case_id"]).strip()
            dataset_case = dataset_cases[case_id]
            acceptable = acceptable_map[(str(dataset_case["subject"]).strip(), str(dataset_case["predicate"]).strip())]
            regraded_cases.append(
                {
                    "case": case_payload["case"],
                    "rows": case_payload.get("rows", []),
                    "original_metrics": case_payload.get("metrics", {}),
                    "acceptable_assets": acceptable,
                    "regraded_metrics": _regrade_case(case_payload, dataset_case, acceptable),
                }
            )
        output[method_key] = {
            "summary": _summarize_cases(regraded_cases),
            "cases": regraded_cases,
        }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(output), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "files_first": output["files_first"]["summary"],
                "vector": output["vector"]["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
