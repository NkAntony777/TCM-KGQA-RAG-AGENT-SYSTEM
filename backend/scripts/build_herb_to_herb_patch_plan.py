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


DEFAULT_SUBTYPE_JSON = BACKEND_DIR / "eval" / "herb_to_herb_dirty_subtypes_latest.json"
DEFAULT_LLM_JSON = BACKEND_DIR / "eval" / "batch2_llm_adjudication_latest.json"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "herb_to_herb_patch_plan_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "herb_to_herb_patch_plan_latest.md"


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_plan(*, subtype_payload: dict[str, Any], llm_payload: dict[str, Any]) -> dict[str, Any]:
    llm_rows = llm_payload.get("targets", {}).get("composition_herb_to_herb", {}).get("decisions", [])
    delete_rows = [row for row in llm_rows if row.get("action") == "delete"]
    retype_rows = [row for row in llm_rows if row.get("action") == "retype"]
    keep_rows = [row for row in llm_rows if row.get("action") == "keep"]

    summary = subtype_payload.get("summary", {})
    subtypes = subtype_payload.get("subtypes", {})
    return {
        "generated_at": _utc_now_text(),
        "source_subtype_generated_at": subtype_payload.get("generated_at", ""),
        "source_llm_generated_at": llm_payload.get("generated_at", ""),
        "summary": {
            "total_rows": int(summary.get("total_rows", 0) or 0),
            "subtype_counts": summary.get("subtype_counts", {}),
            "llm_delete_count": len(delete_rows),
            "llm_retype_count": len(retype_rows),
            "llm_keep_count": len(keep_rows),
        },
        "safe_delete_candidates": delete_rows,
        "retype_candidates": retype_rows,
        "keep_candidates": keep_rows,
        "next_step_recommendations": [
            "对 processing_or_preparation 与 formula_component_listing 子类继续扩大多书样本判定，优先形成 delete 候选池。",
            "对被 LLM 判为 retype -> 配伍禁忌 的样本单独抽取更多跨书样本，判断是否需要新建专门的配伍/配方关系族，而不是直接并到配伍禁忌。",
            "对 other_uncertain 子类不要直接 apply，先继续做二次分层。",
        ],
        "subtype_book_focus": {
            subtype: item.get("top_books", [])[:8]
            for subtype, item in subtypes.items()
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Herb-to-Herb Patch Plan")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    summary = payload.get("summary", {})
    lines.append(f"- 总剩余行数：`{summary.get('total_rows', 0)}`")
    lines.append(f"- LLM delete 样本：`{summary.get('llm_delete_count', 0)}`")
    lines.append(f"- LLM retype 样本：`{summary.get('llm_retype_count', 0)}`")
    lines.append(f"- LLM keep 样本：`{summary.get('llm_keep_count', 0)}`")
    lines.append("")
    lines.append("## 子类分布")
    for subtype, count in (summary.get("subtype_counts", {}) or {}).items():
        lines.append(f"- `{subtype}`: `{count}`")
    lines.append("")
    lines.append("## 当前可直接作为 delete 候选的 LLM 样本")
    for row in payload.get("safe_delete_candidates", [])[:12]:
        lines.append(
            f"- `{row['subject']} -> {row['object']}` @ `{row['source_book']}` "
            f"`fact_id={row['fact_id']}`"
        )
        if row.get("reason"):
            lines.append(f"  理由：`{row['reason']}`")
    lines.append("")
    lines.append("## 当前可直接作为 retype 候选的 LLM 样本")
    for row in payload.get("retype_candidates", [])[:12]:
        lines.append(
            f"- `{row['subject']} -> {row['object']}` => `{row['target_predicate']}` "
            f"@ `{row['source_book']}` `fact_id={row['fact_id']}`"
        )
        if row.get("reason"):
            lines.append(f"  理由：`{row['reason']}`")
    lines.append("")
    lines.append("## 下一步建议")
    for item in payload.get("next_step_recommendations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a no-rebuild herb->herb patch plan from subtype analysis and LLM adjudication outputs.")
    parser.add_argument("--subtype-json", type=Path, default=DEFAULT_SUBTYPE_JSON)
    parser.add_argument("--llm-json", type=Path, default=DEFAULT_LLM_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_plan(
        subtype_payload=_load_json(args.subtype_json),
        llm_payload=_load_json(args.llm_json),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
