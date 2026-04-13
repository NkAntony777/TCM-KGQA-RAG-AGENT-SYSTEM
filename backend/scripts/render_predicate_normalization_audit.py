from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("audit payload must be a JSON object")
    return payload


def _grouped_candidates(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    candidates = payload.get("candidates", [])
    grouped = {
        "alias_to_existing_predicate": [],
        "family_only": [],
        "manual_review_required": [],
        "keep": [],
    }
    if not isinstance(candidates, list):
        return grouped
    for item in candidates:
        if not isinstance(item, dict):
            continue
        action = str(item.get("proposed_action", "")).strip()
        if action not in grouped:
            grouped.setdefault(action, [])
        grouped[action].append(item)
    return grouped


def _render_type_distribution(item: dict[str, Any]) -> list[str]:
    rows = item.get("type_distribution", [])
    if not isinstance(rows, list) or not rows:
        return ["- -"]
    lines: list[str] = []
    for row in rows[:6]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('subject_type', '-')}` -> `{row.get('object_type', '-')}`: {row.get('count', 0)}"
        )
    return lines or ["- -"]


def _render_examples(item: dict[str, Any]) -> list[str]:
    rows = item.get("examples", [])
    if not isinstance(rows, list) or not rows:
        return ["- -"]
    lines: list[str] = []
    for row in rows[:4]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "- `{subject}` --{predicate}--> `{object}` "
            "(`{subject_type}` -> `{object_type}`, {source_book})".format(
                subject=row.get("subject", "-"),
                predicate=row.get("predicate", "-"),
                object=row.get("object", "-"),
                subject_type=row.get("subject_type", "-"),
                object_type=row.get("object_type", "-"),
                source_book=row.get("source_book", "-"),
            )
        )
    return lines or ["- -"]


def _render_candidate_block(item: dict[str, Any]) -> list[str]:
    predicate = str(item.get("predicate", "")).strip()
    count = item.get("count", 0)
    target = str(item.get("proposed_target_predicate", "") or "").strip() or "-"
    risk = str(item.get("risk", "") or "-").strip()
    books = item.get("source_books", [])
    top_books = ", ".join(
        f"{row.get('source_book', '-')}: {row.get('count', 0)}"
        for row in books[:5]
        if isinstance(row, dict)
    ) if isinstance(books, list) and books else "-"
    return [
        f"### `{predicate}`",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| count | {count} |",
        f"| proposed_target | {target} |",
        f"| risk | {risk} |",
        f"| top_books | {top_books} |",
        "",
        "**类型分布**",
        "",
        *_render_type_distribution(item),
        "",
        "**样例**",
        "",
        *_render_examples(item),
        "",
    ]


def render_markdown(payload: dict[str, Any]) -> str:
    grouped = _grouped_candidates(payload)
    lines = [
        "# Predicate Normalization Audit",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| generated_at | {payload.get('generated_at', '-')} |",
        f"| db_path | {payload.get('db_path', '-')} |",
        f"| candidate_count | {payload.get('candidate_count', 0)} |",
        f"| action_summary | {json.dumps(payload.get('action_summary', {}), ensure_ascii=False)} |",
        f"| risk_summary | {json.dumps(payload.get('risk_summary', {}), ensure_ascii=False)} |",
        "",
        "## 审核建议",
        "",
        "- `alias_to_existing_predicate`：仅在语义、类型分布、下游用途均一致时才考虑直接归一。",
        "- `family_only`：只建议归入同一关系族，不建议直接物理改写原始 predicate。",
        "- `manual_review_required`：必须逐条人工审核，不应自动归一。",
        "- `keep`：建议保持独立关系，不做归一化写回。",
        "",
        "## 可直接归一候选",
        "",
    ]

    alias_group = grouped.get("alias_to_existing_predicate", [])
    if alias_group:
        for item in alias_group:
            lines.extend(_render_candidate_block(item))
    else:
        lines.extend(["- none", ""])

    lines.extend(["## 仅建议归入关系族", ""])
    family_group = grouped.get("family_only", [])
    if family_group:
        for item in family_group:
            lines.extend(_render_candidate_block(item))
    else:
        lines.extend(["- none", ""])

    lines.extend(["## 必须人工审核", ""])
    manual_group = grouped.get("manual_review_required", [])
    if manual_group:
        for item in manual_group:
            lines.extend(_render_candidate_block(item))
    else:
        lines.extend(["- none", ""])

    lines.extend(["## 建议保持独立", ""])
    keep_group = grouped.get("keep", [])
    if keep_group:
        for item in keep_group[:20]:
            lines.extend(_render_candidate_block(item))
    else:
        lines.extend(["- none", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render predicate normalization audit JSON into markdown.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output else input_path.with_suffix(".md")
    payload = _load_payload(input_path)
    markdown = render_markdown(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
