from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_INPUT_JSON = BACKEND_DIR / "eval" / "ontology_boundary_tiers_latest.json"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "ontology_likely_dirty_shortlist_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "ontology_likely_dirty_shortlist_latest.md"


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_shortlist(payload: dict[str, Any], *, combo_limit: int = 12, book_limit: int = 8) -> dict[str, Any]:
    predicates_payload: dict[str, Any] = {}
    global_candidates: list[dict[str, Any]] = []
    for predicate, item in payload.get("predicates", {}).items():
        likely_dirty_count = int(item.get("tier_counts", {}).get("likely_dirty", 0) or 0)
        if likely_dirty_count <= 0:
            continue
        dirty_combos = [combo for combo in item.get("top_combos", []) if combo.get("tier") == "likely_dirty"][:combo_limit]
        dirty_books = item.get("top_books_by_tier", {}).get("likely_dirty", [])[:book_limit]
        examples = item.get("examples_by_tier", {}).get("likely_dirty", [])[:6]
        predicates_payload[predicate] = {
            "likely_dirty_count": likely_dirty_count,
            "top_dirty_combos": dirty_combos,
            "top_dirty_books": dirty_books,
            "examples": examples,
            "suggested_action": "candidate_for_small_batch_cleanup",
        }
        for combo in dirty_combos:
            global_candidates.append(
                {
                    "predicate": predicate,
                    "subject_type": str(combo.get("subject_type", "")).strip(),
                    "object_type": str(combo.get("object_type", "")).strip(),
                    "count": int(combo.get("count", 0) or 0),
                    "tier": "likely_dirty",
                    "suggested_action": "candidate_for_small_batch_cleanup",
                }
            )
    global_candidates.sort(key=lambda item: (-int(item["count"]), item["predicate"], item["subject_type"], item["object_type"]))
    return {
        "generated_at": _utc_now_text(),
        "source_audit_generated_at": payload.get("generated_at", ""),
        "source_audit_path": str(DEFAULT_INPUT_JSON),
        "summary": {
            "predicate_count": len(predicates_payload),
            "total_likely_dirty_rows": int(payload.get("summary", {}).get("likely_dirty_rows", 0) or 0),
            "top_global_candidates": global_candidates[:20],
        },
        "predicates": predicates_payload,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Ontology Likely-Dirty Shortlist")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    lines.append(f"- 来源审计时间：`{payload.get('source_audit_generated_at', '')}`")
    summary = payload.get("summary", {})
    lines.append(f"- 涉及谓词数：`{summary.get('predicate_count', 0)}`")
    lines.append(f"- likely_dirty 总量：`{summary.get('total_likely_dirty_rows', 0)}`")
    lines.append("")
    lines.append("## 全局优先处理组合")
    lines.append("")
    lines.append("| predicate | subject_type | object_type | count |")
    lines.append("| --- | --- | --- | ---: |")
    for item in summary.get("top_global_candidates", [])[:12]:
        lines.append(
            f"| {item['predicate']} | {item['subject_type']} | {item['object_type']} | {item['count']} |"
        )
    for predicate, item in payload.get("predicates", {}).items():
        lines.append("")
        lines.append(f"## {predicate}")
        lines.append("")
        lines.append(f"- likely_dirty：`{item.get('likely_dirty_count', 0)}`")
        lines.append(f"- 建议动作：`{item.get('suggested_action', '')}`")
        combos = item.get("top_dirty_combos", [])
        if combos:
            lines.append("")
            lines.append("| subject_type | object_type | count |")
            lines.append("| --- | --- | ---: |")
            for combo in combos[:8]:
                lines.append(f"| {combo['subject_type']} | {combo['object_type']} | {combo['count']} |")
        books = item.get("top_dirty_books", [])
        if books:
            lines.append("")
            lines.append("来源书籍 Top:")
            for book in books[:5]:
                lines.append(f"- `{book['source_book']}`: `{book['count']}`")
        examples = item.get("examples", [])
        if examples:
            lines.append("")
            lines.append("代表样本:")
            for example in examples[:5]:
                lines.append(
                    f"- `{example['subject_type']} -> {example['object_type']}`: "
                    f"`{example['subject']} -> {example['object']}` @ `{example['source_book']}`"
                )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the first likely-dirty ontology cleanup shortlist from the latest tier audit.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    shortlist = build_shortlist(_load_json(args.input_json))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(shortlist, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(shortlist), encoding="utf-8")
    if args.json:
        print(json.dumps(shortlist, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
