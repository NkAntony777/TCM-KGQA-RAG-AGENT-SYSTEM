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


def _candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("candidates", [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _format_examples(item: dict[str, Any], *, limit: int = 6) -> list[str]:
    rows = item.get("examples", [])
    if not isinstance(rows, list) or not rows:
        return ["- -"]
    lines: list[str] = []
    for row in rows[:limit]:
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


def _format_type_distribution(item: dict[str, Any], *, limit: int = 6) -> list[str]:
    rows = item.get("type_distribution", [])
    if not isinstance(rows, list) or not rows:
        return ["- -"]
    lines: list[str] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('subject_type', '-')}` -> `{row.get('object_type', '-')}`: {row.get('count', 0)}"
        )
    return lines or ["- -"]


def _render_candidate(item: dict[str, Any]) -> list[str]:
    predicate = str(item.get("predicate", "")).strip() or "-"
    count = item.get("count", 0)
    action = str(item.get("proposed_action", "") or "-").strip()
    target = str(item.get("proposed_target_predicate", "") or "").strip() or "-"
    risk = str(item.get("risk", "") or "-").strip()
    return [
        f"### `{predicate}`",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| count | {count} |",
        f"| proposed_action | {action} |",
        f"| proposed_target | {target} |",
        f"| risk | {risk} |",
        "",
        "**类型分布**",
        "",
        *_format_type_distribution(item),
        "",
        "**样本条目**",
        "",
        *_format_examples(item),
        "",
    ]


def render_markdown(payload: dict[str, Any]) -> str:
    candidates = _candidates(payload)
    manual_or_high = [
        item
        for item in candidates
        if str(item.get("proposed_action", "")).strip() == "manual_review_required"
        or str(item.get("risk", "")).strip() == "high"
    ]
    all_candidates = sorted(candidates, key=lambda item: (-int(item.get("count", 0) or 0), str(item.get("predicate", ""))))

    lines = [
        "# Predicate Review Samples",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| generated_at | {payload.get('generated_at', '-')} |",
        f"| source_json | predicate_normalization_candidates_latest.json |",
        f"| candidate_count | {payload.get('candidate_count', 0)} |",
        "",
        "## 审阅优先级建议",
        "",
        "- 先审 `manual_review_required` 与 `risk=high`。",
        "- 再审 `family_only` 是否只是查询层归族，不触发物理改写。",
        "- 最后确认低风险直接归一项是否真的满足值域与类型一致性。",
        "",
        "## 高风险 / 人工审核样本",
        "",
    ]

    if manual_or_high:
        for item in manual_or_high:
            lines.extend(_render_candidate(item))
    else:
        lines.extend(["- none", ""])

    lines.extend(
        [
            "## 全量关系样本摘要",
            "",
            "| predicate | count | action | target | risk |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    for item in all_candidates:
        lines.append(
            "| {predicate} | {count} | {action} | {target} | {risk} |".format(
                predicate=str(item.get("predicate", "")).replace("|", "/"),
                count=int(item.get("count", 0) or 0),
                action=str(item.get("proposed_action", "") or "-"),
                target=str(item.get("proposed_target_predicate", "") or "-") or "-",
                risk=str(item.get("risk", "") or "-"),
            )
        )

    lines.extend(["", "## 全量关系样本明细", ""])
    for item in all_candidates:
        lines.extend(_render_candidate(item))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render predicate normalization review samples into markdown.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output else input_path.with_name(f"{input_path.stem}.samples.md")
    payload = _load_payload(input_path)
    markdown = render_markdown(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
