from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_JSON = BACKEND_ROOT / "eval" / "paper" / "traceable_classics_benchmark_debug_eval.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent / "docs" / "Traceable_Classics_Benchmark_Debug_Expert_Review.md"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool_text(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "-"


def _row_block(rows: list[dict[str, Any]], *, title: str) -> list[str]:
    lines = [f"### {title}"]
    if not rows:
        lines.append("No rows.")
        lines.append("")
        return lines
    for index, row in enumerate(rows[:3], start=1):
        lines.append(f"#### Top {index}")
        lines.append(f"- Book: `{row.get('book_name', '')}`")
        lines.append(f"- Chapter: `{row.get('chapter_title', '')}`")
        lines.append(f"- Score: `{row.get('score', '')}`")
        snippet = str(row.get("match_snippet", "") or "").strip()
        if snippet:
            lines.append("- Snippet:")
            lines.append("")
            lines.append("```text")
            lines.append(snippet)
            lines.append("```")
    lines.append("")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    files_map = {item["case"]["case_id"]: item for item in report["files_first"]["cases"]}
    vector_map = {item["case"]["case_id"]: item for item in report["vector"]["cases"]}
    case_ids = list(files_map)
    lines = [
        "# Traceable Classics Debug Expert Review",
        "",
        "本文件用于人工复核 benchmark 的 `debug` 子集结果，判断当前系统返回是否属于：",
        "",
        "- 真错",
        "- 证据不足",
        "- 命中不同书/不同章节但仍可接受",
        "",
        "## Aggregate",
        "",
        f"- Files-first avg latency: `{report['files_first']['avg_latency_ms']} ms`",
        f"- Files-first topk provenance hit: `{report['files_first']['topk_provenance_hit_rate']}`",
        f"- Files-first topk answer+provenance hit: `{report['files_first']['topk_answer_provenance_hit_rate']}`",
        f"- Vector avg latency: `{report['vector']['avg_latency_ms']} ms`",
        f"- Vector topk provenance hit: `{report['vector']['topk_provenance_hit_rate']}`",
        f"- Vector topk answer+provenance hit: `{report['vector']['topk_answer_provenance_hit_rate']}`",
        "",
    ]
    for case_id in case_ids:
        files_row = files_map[case_id]
        vector_row = vector_map.get(case_id, {})
        case = files_row["case"]
        lines.extend(
            [
                f"## {case_id}",
                "",
                f"- Category: `{case.get('category', '')}`",
                f"- Task Family: `{case.get('task_family', '')}`",
                f"- Difficulty: `{case.get('difficulty', '')}`",
                f"- Query: `{case.get('query', '')}`",
                f"- Expected Books: `{', '.join(case.get('expected_books_any', []))}`",
                f"- Expected Chapters: `{', '.join(case.get('expected_chapters_any', []))}`",
                f"- Gold Answer Outline: `{', '.join(case.get('gold_answer_outline', []))}`",
                "",
                "### Gold Evidence",
                "",
            ]
        )
        for evidence in case.get("gold_evidence_any", []):
            lines.append("```text")
            lines.append(str(evidence))
            lines.append("```")
        lines.append("")
        lines.extend(
            [
                "### Files-first Metrics",
                f"- topk book hit: `{_bool_text(files_row['metrics'].get('topk_book_hit'))}`",
                f"- topk chapter hit: `{_bool_text(files_row['metrics'].get('topk_chapter_hit'))}`",
                f"- topk evidence hit: `{_bool_text(files_row['metrics'].get('topk_evidence_hit'))}`",
                f"- topk provenance hit: `{_bool_text(files_row['metrics'].get('topk_provenance_hit'))}`",
                f"- topk answer hit: `{_bool_text(files_row['metrics'].get('topk_answer_hit'))}`",
                f"- topk answer+provenance hit: `{_bool_text(files_row['metrics'].get('topk_answer_provenance_hit'))}`",
                "",
            ]
        )
        lines.extend(_row_block(files_row.get("rows", []), title="Files-first Top Rows"))
        lines.extend(
            [
                "### Vector Metrics",
                f"- topk book hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_book_hit'))}`",
                f"- topk chapter hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_chapter_hit'))}`",
                f"- topk evidence hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_evidence_hit'))}`",
                f"- topk provenance hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_provenance_hit'))}`",
                f"- topk answer hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_answer_hit'))}`",
                f"- topk answer+provenance hit: `{_bool_text(vector_row.get('metrics', {}).get('topk_answer_provenance_hit'))}`",
                "",
            ]
        )
        lines.extend(_row_block(vector_row.get("rows", []), title="Vector Top Rows"))
        lines.extend(
            [
                "### Expert Notes",
                "",
                "- Is files-first answer acceptable even if not in gold chapter/book?",
                "- Is vector answer acceptable even if not in gold chapter/book?",
                "- Should this case's gold set be expanded?",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render expert review markdown for traceable classics debug evaluation.")
    parser.add_argument("--eval-json", type=Path, default=DEFAULT_EVAL_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = _load(args.eval_json)
    markdown = render_markdown(report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "eval_json": str(args.eval_json),
                "output_md": str(args.output_md),
                "cases": len(report["files_first"]["cases"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
