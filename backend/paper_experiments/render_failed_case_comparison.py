from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REEVAL_JSON = BACKEND_ROOT / "eval" / "paper" / "traceable_classics_benchmark_test_regraded.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Traceable_Classics_Benchmark_Test_Failed_Case_Comparison.md"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_rows(rows: list[dict[str, Any]], *, title: str) -> list[str]:
    lines = [f"### {title}", ""]
    if not rows:
        lines.append("No rows returned.")
        lines.append("")
        return lines
    for index, row in enumerate(rows[:3], start=1):
        lines.extend(
            [
                f"#### Top {index}",
                f"- Book: `{row.get('book_name', '')}`",
                f"- Chapter: `{row.get('chapter_title', '')}`",
                "```text",
                str(row.get("match_snippet", "") or ""),
                "```",
                "",
            ]
        )
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    files_first_map = {item["case"]["case_id"]: item for item in report["files_first"]["cases"]}
    vector_map = {item["case"]["case_id"]: item for item in report["vector"]["cases"]}
    failed_ids = [
        item["case"]["case_id"]
        for item in report["files_first"]["cases"]
        if not item["regraded_metrics"].get("topk_regraded_success")
    ]

    lines = [
        "# Files-first Failed Case Comparison",
        "",
        "本文件收录 `files-first` 在重判分后仍失败的题目，并并排给出 `files-first` 与 `vector` 的返回内容，供人工审核是否真的回答错误。",
        "",
        f"Total failed cases: `{len(failed_ids)}`",
        "",
    ]

    for case_id in failed_ids:
        files_row = files_first_map[case_id]
        vector_row = vector_map.get(case_id, {})
        case = files_row["case"]
        acceptable = files_row.get("acceptable_assets", {})
        lines.extend(
            [
                f"## {case_id}",
                "",
                f"- Category: `{case.get('category', '')}`",
                f"- Task Family: `{case.get('task_family', '')}`",
                f"- Query: `{case.get('query', '')}`",
                f"- Acceptable Answers: `{', '.join(acceptable.get('answers', [])[:16])}`",
                f"- Acceptable Books: `{', '.join(acceptable.get('books', [])[:16])}`",
                "",
                "### Files-first Regraded Metrics",
                f"- top1 success: `{files_row['regraded_metrics'].get('top1_regraded_success')}`",
                f"- topk success: `{files_row['regraded_metrics'].get('topk_regraded_success')}`",
                f"- topk subject hit: `{files_row['regraded_metrics'].get('topk_subject_hit')}`",
                f"- topk answer asset hit: `{files_row['regraded_metrics'].get('topk_answer_asset_hit')}`",
                f"- topk book asset hit: `{files_row['regraded_metrics'].get('topk_book_asset_hit')}`",
                "",
            ]
        )
        lines.extend(_render_rows(files_row.get("rows", []), title="Files-first Top Rows"))
        lines.extend(
            [
                "### Vector Regraded Metrics",
                f"- top1 success: `{vector_row.get('regraded_metrics', {}).get('top1_regraded_success')}`",
                f"- topk success: `{vector_row.get('regraded_metrics', {}).get('topk_regraded_success')}`",
                f"- topk subject hit: `{vector_row.get('regraded_metrics', {}).get('topk_subject_hit')}`",
                f"- topk answer asset hit: `{vector_row.get('regraded_metrics', {}).get('topk_answer_asset_hit')}`",
                f"- topk book asset hit: `{vector_row.get('regraded_metrics', {}).get('topk_book_asset_hit')}`",
                "",
            ]
        )
        lines.extend(_render_rows(vector_row.get("rows", []), title="Vector Top Rows"))
        lines.extend(
            [
                "### Human Review",
                "",
                "- Files-first should be counted as correct? `Yes / No / Partial`",
                "- Vector should be counted as correct? `Yes / No / Partial`",
                "- If either should count, what is the supporting rationale?",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render markdown comparison for files-first failed cases.")
    parser.add_argument("--regraded-json", type=Path, default=DEFAULT_REEVAL_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = _load(args.regraded_json)
    markdown = render_markdown(report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "regraded_json": str(args.regraded_json),
                "output_md": str(args.output_md),
                "failed_cases": len(
                    [
                        item
                        for item in report["files_first"]["cases"]
                        if not item["regraded_metrics"].get("topk_regraded_success")
                    ]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
