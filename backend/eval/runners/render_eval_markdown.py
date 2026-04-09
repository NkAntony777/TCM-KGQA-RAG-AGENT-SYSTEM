from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation payload must be a JSON object")
    return payload


def _format_latency_ms(value: Any) -> str:
    try:
        return f"{float(value) / 1000:.1f}s"
    except (TypeError, ValueError):
        return "-"


def _format_scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.1f}"
    text = str(value).strip()
    return text or "-"


def _format_joined(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "-"
    values = [str(item).strip() for item in items if str(item).strip()]
    return ", ".join(values) if values else "-"


def _tool_trace_entries(mode_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = mode_payload.get("tool_trace")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _tool_trace_tools(mode_payload: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in _tool_trace_entries(mode_payload):
        tool = str(item.get("tool", "")).strip()
        if tool:
            result.append(tool)
    return result


def _fallback_detected(mode_payload: dict[str, Any]) -> bool:
    backend = str(mode_payload.get("generation_backend", "") or "").lower()
    if "fallback" in backend:
        return True

    notes = mode_payload.get("notes")
    if isinstance(notes, list) and any("fallback" in str(item).lower() for item in notes):
        return True

    for item in _tool_trace_entries(mode_payload):
        if "fallback" in json.dumps(item, ensure_ascii=False).lower():
            return True

    return False


def summarize_mode_observability(mode_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": mode_payload.get("status"),
        "final_route": mode_payload.get("final_route"),
        "generation_backend": mode_payload.get("generation_backend"),
        "tool_trace_tools": _tool_trace_tools(mode_payload),
        "fallback_detected": _fallback_detected(mode_payload),
        "trace_id": mode_payload.get("trace_id"),
        "latency_ms": mode_payload.get("latency_ms"),
    }


def _normalize_lines(items: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            result.append(text)
    if limit is not None:
        return result[:limit]
    return result


def _render_bullets(items: Any, *, limit: int | None = None) -> list[str]:
    lines = _normalize_lines(items, limit=limit)
    return [f"- {line}" for line in lines] if lines else ["- -"]


def _render_tool_trace(mode_payload: dict[str, Any]) -> list[str]:
    rows = _tool_trace_entries(mode_payload)
    if not rows:
        return ["- -"]

    rendered: list[str] = []
    for item in rows[:8]:
        tool = str(item.get("tool", "")).strip() or "unknown_tool"
        meta = item.get("meta")
        if isinstance(meta, dict):
            highlights: list[str] = []
            for key in ("final_route", "route", "status", "backend", "warning"):
                value = meta.get(key)
                if value not in (None, "", [], {}):
                    highlights.append(f"{key}={value}")
            if not highlights and meta:
                first_key = next(iter(meta.keys()))
                highlights.append(f"{first_key}={meta[first_key]}")
            rendered.append(f"- {tool}: {'; '.join(highlights) if highlights else 'meta'}")
        else:
            rendered.append(f"- {tool}")
    return rendered


def _render_mode_section(mode_name: str, mode_payload: dict[str, Any]) -> list[str]:
    answer = str(mode_payload.get("answer", "") or "").strip()
    citations = _render_bullets(mode_payload.get("citations"), limit=6)
    evidence_preview = _render_bullets(mode_payload.get("factual_evidence_preview"), limit=3)
    case_preview = _render_bullets(mode_payload.get("case_reference_preview"), limit=2)
    planner_steps = _render_bullets(mode_payload.get("planner_steps"), limit=12)
    notes = _render_bullets(mode_payload.get("notes"), limit=8)
    tool_trace = _render_tool_trace(mode_payload)
    observability = summarize_mode_observability(mode_payload)

    lines = [
        f"### {mode_name}",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| ok | {_format_scalar(mode_payload.get('ok'))} |",
        f"| latency | {_format_latency_ms(mode_payload.get('latency_ms'))} |",
        f"| status | {_format_scalar(mode_payload.get('status'))} |",
        f"| final_route | {_format_scalar(mode_payload.get('final_route'))} |",
        f"| executed_routes | {_format_joined(mode_payload.get('executed_routes'))} |",
        f"| generation_backend | {_format_scalar(mode_payload.get('generation_backend'))} |",
        f"| tool_trace_tools | {_format_joined(observability.get('tool_trace_tools'))} |",
        f"| fallback_detected | {_format_scalar(observability.get('fallback_detected'))} |",
        f"| trace_id | {_format_scalar(mode_payload.get('trace_id'))} |",
        f"| factual_evidence_count | {_format_scalar(mode_payload.get('factual_evidence_count'))} |",
        f"| case_reference_count | {_format_scalar(mode_payload.get('case_reference_count'))} |",
        "",
        "**答案正文**",
        "",
        answer if answer else "（空）",
        "",
        "**依据来源**",
        "",
        *citations,
        "",
        "**事实证据摘要**",
        "",
        *evidence_preview,
        "",
        "**案例证据摘要**",
        "",
        *case_preview,
        "",
        "**规划/执行摘要**",
        "",
        *planner_steps,
        "",
        "**Tool Trace**",
        "",
        *tool_trace,
        "",
        "**备注**",
        "",
        *notes,
        "",
    ]
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("payload.questions must be a list")

    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}

    lines = [
        "# 博士级中医难题 Quick/Deep 评测报告",
        "",
        "## 评测概览",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| generated_at | {_format_scalar(payload.get('generated_at'))} |",
        f"| backend_url | {_format_scalar(payload.get('backend_url'))} |",
        f"| source | {_format_scalar(payload.get('source'))} |",
        f"| topic_kept_in_output_only | {_format_scalar(payload.get('topic_kept_in_output_only'))} |",
        f"| top_k | {_format_scalar(payload.get('top_k'))} |",
        f"| total_questions | {_format_scalar(summary.get('total_questions'))} |",
        f"| quick_ok | {_format_scalar(summary.get('quick_ok'))} |",
        f"| deep_ok | {_format_scalar(summary.get('deep_ok'))} |",
        f"| quick_avg_latency | {_format_latency_ms(summary.get('quick_avg_latency_ms'))} |",
        f"| deep_avg_latency | {_format_latency_ms(summary.get('deep_avg_latency_ms'))} |",
        "",
        "## 按题目总览",
        "",
        "| ID | Topic | Quick 路由/后端 | Quick 工具/回退 | Quick 延迟 | Deep 路由/后端 | Deep 工具/回退 | Deep 延迟 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in questions:
        if not isinstance(item, dict):
            continue
        quick = item.get("quick", {}) if isinstance(item.get("quick"), dict) else {}
        deep = item.get("deep", {}) if isinstance(item.get("deep"), dict) else {}
        quick_obs = summarize_mode_observability(quick)
        deep_obs = summarize_mode_observability(deep)
        lines.append(
            "| {id} | {topic} | {q_route} / {q_backend} | {q_tools} / fb={q_fallback} | {q_latency} | {d_route} / {d_backend} | {d_tools} / fb={d_fallback} | {d_latency} |".format(
                id=_format_scalar(item.get("id")),
                topic=str(item.get("topic", "")).replace("|", "/"),
                q_route=_format_scalar(quick.get("final_route")),
                q_backend=_format_scalar(quick.get("generation_backend")),
                q_tools=_format_joined(quick_obs.get("tool_trace_tools")),
                q_fallback=_format_scalar(quick_obs.get("fallback_detected")),
                q_latency=_format_latency_ms(quick.get("latency_ms")),
                d_route=_format_scalar(deep.get("final_route")),
                d_backend=_format_scalar(deep.get("generation_backend")),
                d_tools=_format_joined(deep_obs.get("tool_trace_tools")),
                d_fallback=_format_scalar(deep_obs.get("fallback_detected")),
                d_latency=_format_latency_ms(deep.get("latency_ms")),
            )
        )

    for item in questions:
        if not isinstance(item, dict):
            continue
        question_id = _format_scalar(item.get("id"))
        topic = _format_scalar(item.get("topic"))
        question = str(item.get("question", "") or "").strip()
        quick = item.get("quick", {}) if isinstance(item.get("quick"), dict) else {}
        deep = item.get("deep", {}) if isinstance(item.get("deep"), dict) else {}
        lines.extend(
            [
                "",
                f"## {question_id} {topic}",
                "",
                "**题目**",
                "",
                question if question else "（空）",
                "",
                "### 对比摘要",
                "",
                "| 模式 | status | final_route | generation_backend | latency | factual | case |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| quick | {status} | {route} | {backend} | {latency} | {factual} | {case} |".format(
                    status=_format_scalar(quick.get("status")),
                    route=_format_scalar(quick.get("final_route")),
                    backend=_format_scalar(quick.get("generation_backend")),
                    latency=_format_latency_ms(quick.get("latency_ms")),
                    factual=_format_scalar(quick.get("factual_evidence_count")),
                    case=_format_scalar(quick.get("case_reference_count")),
                ),
                "| deep | {status} | {route} | {backend} | {latency} | {factual} | {case} |".format(
                    status=_format_scalar(deep.get("status")),
                    route=_format_scalar(deep.get("final_route")),
                    backend=_format_scalar(deep.get("generation_backend")),
                    latency=_format_latency_ms(deep.get("latency_ms")),
                    factual=_format_scalar(deep.get("factual_evidence_count")),
                    case=_format_scalar(deep.get("case_reference_count")),
                ),
                "",
            ]
        )
        lines.extend(_render_mode_section("Quick", quick))
        lines.extend(_render_mode_section("Deep", deep))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render eval JSON into expert-friendly Markdown.")
    parser.add_argument("input", type=Path, help="Path to the eval JSON file.")
    parser.add_argument("--output", type=Path, default=None, help="Path to the output Markdown file.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output else input_path.with_suffix(".md")
    payload = _load_payload(input_path)
    markdown = render_markdown(payload)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
