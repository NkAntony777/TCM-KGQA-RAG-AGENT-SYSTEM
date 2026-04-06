from __future__ import annotations

import json
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from graph.agent import agent_manager
from services.qa_service.engine import get_qa_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str
    stream: bool = True
    mode: Literal["quick", "deep"] = Field(default="quick")
    top_k: int = Field(default=12, ge=1, le=20)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _new_segment() -> dict[str, Any]:
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
    return _new_segment()


def _apply_event_to_segments(
    *,
    event: dict[str, Any],
    segments: list[dict[str, Any]],
    current_segment: dict[str, Any],
) -> dict[str, Any]:
    event_type = event["type"]

    if event_type == "token":
        current_segment["content"] += event.get("content", "")
    elif event_type == "tool_start":
        current_segment["tool_calls"].append(
            {
                "tool": event.get("tool", "tool"),
                "input": event.get("input", ""),
                "output": "",
            }
        )
    elif event_type == "tool_end":
        if current_segment["tool_calls"]:
            current_segment["tool_calls"][-1]["output"] = event.get("output", "")
            meta = event.get("meta")
            if isinstance(meta, dict) and meta:
                current_segment["tool_calls"][-1]["meta"] = meta
    elif event_type == "route":
        current_segment["route"] = {
            "route": event.get("route"),
            "reason": event.get("reason", ""),
            "status": event.get("status", "ok"),
            "final_route": event.get("final_route"),
            "executed_routes": event.get("executed_routes", []),
        }
    elif event_type == "evidence":
        items = event.get("items")
        if isinstance(items, list):
            current_segment["evidence"].extend(items)
    elif event_type == "planner_step":
        step = event.get("step")
        if isinstance(step, dict):
            current_segment["planner_steps"].append(step)
    elif event_type == "notes":
        items = event.get("items")
        if isinstance(items, list):
            current_segment["notes"] = [str(item) for item in items if str(item).strip()]
    elif event_type == "citations":
        items = event.get("items")
        if isinstance(items, list):
            current_segment["citations"] = [str(item) for item in items if str(item).strip()]
    elif event_type == "qa_mode":
        current_segment["qa_mode"] = str(event.get("mode", "quick"))
    elif event_type == "new_response":
        return _append_segment(segments, current_segment)
    elif event_type == "done":
        if not current_segment["content"].strip() and event.get("content"):
            current_segment["content"] = str(event["content"])
        return _append_segment(segments, current_segment)

    return current_segment


def _apply_result_to_segments(*, result: dict[str, Any], segments: list[dict[str, Any]]) -> None:
    if not segments:
        return
    target = segments[-1]
    deep_trace = result.get("deep_trace")
    evidence_bundle = result.get("evidence_bundle")
    if isinstance(deep_trace, list):
        target["deep_trace"] = deep_trace
    if isinstance(evidence_bundle, dict):
        target["evidence_bundle"] = evidence_bundle


def _persist_segments(
    *,
    session_manager,
    session_id: str,
    user_message: str,
    segments: list[dict[str, Any]],
) -> None:
    session_manager.save_message(session_id, "user", user_message)
    for segment in segments:
        session_manager.save_message(
            session_id,
            "assistant",
            segment["content"],
            tool_calls=segment["tool_calls"] or None,
            meta={
                "route": segment["route"],
                "evidence": segment["evidence"],
                "planner_steps": segment["planner_steps"],
                "deep_trace": segment["deep_trace"],
                "evidence_bundle": segment["evidence_bundle"],
                "notes": segment["notes"],
                "citations": segment["citations"],
                "qa_mode": segment["qa_mode"],
            },
        )


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


def _result_to_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.append({"type": "qa_mode", "mode": result.get("mode", "quick")})

    planner_steps = result.get("planner_steps", [])
    if isinstance(planner_steps, list):
        for step in planner_steps:
            if isinstance(step, dict):
                events.append({"type": "planner_step", "step": step})

    tool_trace = result.get("tool_trace", [])
    if isinstance(tool_trace, list):
        for item in tool_trace:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool", "tool")).strip() or "tool"
            meta = item.get("meta", {}) if isinstance(item.get("meta"), dict) else {}
            events.append(
                {
                    "type": "tool_start",
                    "tool": tool_name,
                    "input": _tool_input_from_meta(tool_name, meta),
                }
            )
            events.append(
                {
                    "type": "tool_end",
                    "tool": tool_name,
                    "output": _tool_output_from_meta(meta),
                    "meta": meta,
                }
            )

    route = result.get("route")
    if isinstance(route, dict) and route:
        events.append({"type": "route", **route})

    evidence: list[dict[str, Any]] = []
    factual = result.get("factual_evidence", [])
    cases = result.get("case_references", [])
    if isinstance(factual, list):
        evidence.extend(item for item in factual if isinstance(item, dict))
    if isinstance(cases, list):
        evidence.extend(item for item in cases if isinstance(item, dict))
    if evidence:
        events.append({"type": "evidence", "items": evidence})

    notes = result.get("notes", [])
    if isinstance(notes, list) and notes:
        events.append({"type": "notes", "items": notes})

    citations = result.get("citations", [])
    if isinstance(citations, list) and citations:
        events.append({"type": "citations", "items": citations})

    answer = str(result.get("answer", "") or "")
    if answer:
        events.append({"type": "token", "content": answer})
    events.append({"type": "done", "content": answer})
    return events


async def _generate_chat_result(payload: ChatRequest) -> dict[str, Any]:
    result = await get_qa_service().answer(
        payload.message,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return result


async def _event_sequence(payload: ChatRequest) -> AsyncIterator[dict[str, Any]]:
    service = get_qa_service()
    if hasattr(service, "stream_answer"):
        async for event in service.stream_answer(
            payload.message,
            mode=payload.mode,
            top_k=payload.top_k,
        ):
            yield event
        return

    result = await _generate_chat_result(payload)
    for event in _result_to_events(result):
        yield event
    yield {"type": "result", "result": result}


@router.post("/chat")
async def chat(payload: ChatRequest):
    session_manager = agent_manager.session_manager
    if session_manager is None:
        raise HTTPException(status_code=503, detail="Agent manager is not initialized")

    history_record = session_manager.load_session_record(payload.session_id)
    is_first_user_message = not any(
        message.get("role") == "user" for message in history_record.get("messages", [])
    )

    async def event_generator():
        segments: list[dict[str, Any]] = []
        current_segment = _new_segment()
        final_result: dict[str, Any] | None = None

        try:
            async for event in _event_sequence(payload):
                if event["type"] == "result":
                    result = event.get("result")
                    if isinstance(result, dict):
                        final_result = result
                        _apply_result_to_segments(result=result, segments=segments)
                    continue
                current_segment = _apply_event_to_segments(
                    event=event,
                    segments=segments,
                    current_segment=current_segment,
                )

                data = {key: value for key, value in event.items() if key != "type"}
                yield _sse(event["type"], data)
        except Exception as exc:
            yield _sse("error", {"error": str(exc)})
            return

        _persist_segments(
            session_manager=session_manager,
            session_id=payload.session_id,
            user_message=payload.message,
            segments=segments,
        )
        if is_first_user_message:
            title = await agent_manager.generate_title(payload.message)
            session_manager.set_title(payload.session_id, title)
            yield _sse("title", {"session_id": payload.session_id, "title": title})

    if payload.stream:
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    segments: list[dict[str, Any]] = []
    current_segment = _new_segment()
    final_content = ""
    title: str | None = None
    final_result: dict[str, Any] | None = None

    try:
        async for event in _event_sequence(payload):
            if event["type"] == "result":
                result = event.get("result")
                if isinstance(result, dict):
                    final_result = result
                    _apply_result_to_segments(result=result, segments=segments)
                continue
            current_segment = _apply_event_to_segments(
                event=event,
                segments=segments,
                current_segment=current_segment,
            )
            if event["type"] == "done":
                final_content = str(event.get("content", "") or "")
        _persist_segments(
            session_manager=session_manager,
            session_id=payload.session_id,
            user_message=payload.message,
            segments=segments,
        )
        if is_first_user_message:
            title = await agent_manager.generate_title(payload.message)
            session_manager.set_title(payload.session_id, title)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({"content": final_content, "segments": segments, "title": title})
