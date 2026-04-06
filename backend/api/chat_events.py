from __future__ import annotations

import json
from typing import Any

CHAT_EVENT_TOKEN = "token"
CHAT_EVENT_TOOL_START = "tool_start"
CHAT_EVENT_TOOL_END = "tool_end"
CHAT_EVENT_ROUTE = "route"
CHAT_EVENT_EVIDENCE = "evidence"
CHAT_EVENT_PLANNER_STEP = "planner_step"
CHAT_EVENT_DEEP_TRACE_STEP = "deep_trace_step"
CHAT_EVENT_EVIDENCE_BUNDLE = "evidence_bundle"
CHAT_EVENT_NOTES = "notes"
CHAT_EVENT_CITATIONS = "citations"
CHAT_EVENT_QA_MODE = "qa_mode"
CHAT_EVENT_NEW_RESPONSE = "new_response"
CHAT_EVENT_DONE = "done"


def new_segment() -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [],
        "route": None,
        "evidence": [],
        "planner_steps": [],
        "deep_trace": [],
        "evidence_bundle": None,
        "notes": [],
        "citations": [],
        "qa_mode": "quick",
    }


def _segment_has_content(segment: dict[str, Any]) -> bool:
    return bool(
        segment["content"].strip()
        or segment["tool_calls"]
        or segment["route"]
        or segment["evidence"]
        or segment["planner_steps"]
        or segment["deep_trace"]
        or segment["notes"]
        or segment["citations"]
    )


def _append_segment(segments: list[dict[str, Any]], segment: dict[str, Any]) -> dict[str, Any]:
    if _segment_has_content(segment):
        segments.append(segment)
    return new_segment()


def apply_event_to_segments(
    *,
    event: dict[str, Any],
    segments: list[dict[str, Any]],
    current_segment: dict[str, Any],
) -> dict[str, Any]:
    event_type = event["type"]

    if event_type == CHAT_EVENT_TOKEN:
        current_segment["content"] += event.get("content", "")
    elif event_type == CHAT_EVENT_TOOL_START:
        current_segment["tool_calls"].append(
            {
                "tool": event.get("tool", "tool"),
                "input": event.get("input", ""),
                "output": "",
            }
        )
    elif event_type == CHAT_EVENT_TOOL_END:
        if current_segment["tool_calls"]:
            current_segment["tool_calls"][-1]["output"] = event.get("output", "")
            meta = event.get("meta")
            if isinstance(meta, dict) and meta:
                current_segment["tool_calls"][-1]["meta"] = meta
    elif event_type == CHAT_EVENT_ROUTE:
        current_segment["route"] = {
            "route": event.get("route"),
            "reason": event.get("reason", ""),
            "status": event.get("status", "ok"),
            "final_route": event.get("final_route"),
            "executed_routes": event.get("executed_routes", []),
        }
    elif event_type == CHAT_EVENT_EVIDENCE:
        items = event.get("items")
        if isinstance(items, list):
            current_segment["evidence"].extend(items)
    elif event_type == CHAT_EVENT_PLANNER_STEP:
        step = event.get("step")
        if isinstance(step, dict):
            current_segment["planner_steps"].append(step)
    elif event_type == CHAT_EVENT_DEEP_TRACE_STEP:
        step = event.get("step")
        if isinstance(step, dict):
            current_segment["deep_trace"].append(step)
    elif event_type == CHAT_EVENT_EVIDENCE_BUNDLE:
        bundle = event.get("bundle")
        if isinstance(bundle, dict):
            current_segment["evidence_bundle"] = bundle
    elif event_type == CHAT_EVENT_NOTES:
        items = event.get("items")
        if isinstance(items, list):
            current_segment["notes"] = [str(item) for item in items if str(item).strip()]
    elif event_type == CHAT_EVENT_CITATIONS:
        items = event.get("items")
        if isinstance(items, list):
            current_segment["citations"] = [str(item) for item in items if str(item).strip()]
    elif event_type == CHAT_EVENT_QA_MODE:
        current_segment["qa_mode"] = str(event.get("mode", "quick"))
    elif event_type == CHAT_EVENT_NEW_RESPONSE:
        return _append_segment(segments, current_segment)
    elif event_type == CHAT_EVENT_DONE:
        if not current_segment["content"].strip() and event.get("content"):
            current_segment["content"] = str(event["content"])
        return _append_segment(segments, current_segment)

    return current_segment


def apply_result_to_segments(*, result: dict[str, Any], segments: list[dict[str, Any]]) -> None:
    if not segments:
        return
    target = segments[-1]
    deep_trace = result.get("deep_trace")
    evidence_bundle = result.get("evidence_bundle")
    if isinstance(deep_trace, list):
        target["deep_trace"] = deep_trace
    if isinstance(evidence_bundle, dict):
        target["evidence_bundle"] = evidence_bundle


def _tool_input_from_meta(tool_name: str, meta: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for key in ("query", "path", "reason", "count"):
        value = meta.get(key)
        if value not in (None, "", [], {}):
            payload[key] = value
    if tool_name == "tcm_route_search" and "final_route" in meta:
        payload["final_route"] = meta["final_route"]
    return json.dumps(payload, ensure_ascii=False) if payload else ""


def _tool_output_from_meta(meta: dict[str, Any]) -> str:
    compact = {key: value for key, value in meta.items() if value not in (None, "", [], {})}
    return json.dumps(compact, ensure_ascii=False) if compact else ""


def result_to_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.append({"type": CHAT_EVENT_QA_MODE, "mode": result.get("mode", "quick")})

    planner_steps = result.get("planner_steps", [])
    if isinstance(planner_steps, list):
        for step in planner_steps:
            if isinstance(step, dict):
                events.append({"type": CHAT_EVENT_PLANNER_STEP, "step": step})

    deep_trace = result.get("deep_trace", [])
    if isinstance(deep_trace, list):
        for step in deep_trace:
            if isinstance(step, dict):
                events.append({"type": CHAT_EVENT_DEEP_TRACE_STEP, "step": step})

    tool_trace = result.get("tool_trace", [])
    if isinstance(tool_trace, list):
        for item in tool_trace:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool", "tool")).strip() or "tool"
            meta = item.get("meta", {}) if isinstance(item.get("meta"), dict) else {}
            events.append(
                {
                    "type": CHAT_EVENT_TOOL_START,
                    "tool": tool_name,
                    "input": _tool_input_from_meta(tool_name, meta),
                }
            )
            events.append(
                {
                    "type": CHAT_EVENT_TOOL_END,
                    "tool": tool_name,
                    "output": _tool_output_from_meta(meta),
                    "meta": meta,
                }
            )

    route = result.get("route")
    if isinstance(route, dict) and route:
        events.append({"type": CHAT_EVENT_ROUTE, **route})

    evidence: list[dict[str, Any]] = []
    factual = result.get("factual_evidence", [])
    cases = result.get("case_references", [])
    if isinstance(factual, list):
        evidence.extend(item for item in factual if isinstance(item, dict))
    if isinstance(cases, list):
        evidence.extend(item for item in cases if isinstance(item, dict))
    if evidence:
        events.append({"type": CHAT_EVENT_EVIDENCE, "items": evidence})

    notes = result.get("notes", [])
    if isinstance(notes, list) and notes:
        events.append({"type": CHAT_EVENT_NOTES, "items": notes})

    citations = result.get("citations", [])
    if isinstance(citations, list) and citations:
        events.append({"type": CHAT_EVENT_CITATIONS, "items": citations})

    evidence_bundle = result.get("evidence_bundle")
    if isinstance(evidence_bundle, dict) and evidence_bundle:
        events.append({"type": CHAT_EVENT_EVIDENCE_BUNDLE, "bundle": evidence_bundle})

    answer = str(result.get("answer", "") or "")
    if answer:
        events.append({"type": CHAT_EVENT_TOKEN, "content": answer})
    events.append({"type": CHAT_EVENT_DONE, "content": answer})
    return events
