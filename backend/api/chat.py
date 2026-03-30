from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from graph.agent import agent_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str
    stream: bool = True


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _new_segment() -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [],
        "route": None,
        "evidence": [],
    }


def _segment_has_content(segment: dict[str, Any]) -> bool:
    return bool(
        segment["content"].strip()
        or segment["tool_calls"]
        or segment["route"]
        or segment["evidence"]
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
            "degradation": event.get("degradation", []),
            "service_health": event.get("service_health", {}),
            "service_trace_ids": event.get("service_trace_ids", {}),
            "service_backends": event.get("service_backends", {}),
        }
    elif event_type == "evidence":
        items = event.get("items")
        if isinstance(items, list):
            current_segment["evidence"].extend(items)
    elif event_type == "new_response":
        return _append_segment(segments, current_segment)
    elif event_type == "done":
        if not current_segment["content"].strip() and event.get("content"):
            current_segment["content"] = event["content"]
        return _append_segment(segments, current_segment)

    return current_segment


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
            },
        )


@router.post("/chat")
async def chat(payload: ChatRequest):
    session_manager = agent_manager.session_manager
    if session_manager is None:
        raise HTTPException(status_code=503, detail="Agent manager is not initialized")

    history_record = session_manager.load_session_record(payload.session_id)
    history = session_manager.load_session_for_agent(payload.session_id)
    is_first_user_message = not any(
        message.get("role") == "user"
        for message in history_record.get("messages", [])
    )

    async def event_generator():
        segments: list[dict[str, Any]] = []
        current_segment = _new_segment()

        try:
            async for event in agent_manager.astream(payload.message, history):
                event_type = event["type"]
                current_segment = _apply_event_to_segments(
                    event=event,
                    segments=segments,
                    current_segment=current_segment,
                )
                if event_type == "done":
                    _persist_segments(
                        session_manager=session_manager,
                        session_id=payload.session_id,
                        user_message=payload.message,
                        segments=segments,
                    )

                data = {key: value for key, value in event.items() if key != "type"}
                yield _sse(event_type, data)

                if event_type == "done" and is_first_user_message:
                    title = await agent_manager.generate_title(payload.message)
                    session_manager.set_title(payload.session_id, title)
                    yield _sse(
                        "title",
                        {"session_id": payload.session_id, "title": title},
                    )
        except Exception as exc:
            yield _sse("error", {"error": str(exc)})

    if payload.stream:
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    segments: list[dict[str, Any]] = []
    current_segment = _new_segment()
    final_content = ""
    title: str | None = None

    try:
        async for event in agent_manager.astream(payload.message, history):
            event_type = event["type"]
            current_segment = _apply_event_to_segments(
                event=event,
                segments=segments,
                current_segment=current_segment,
            )
            if event_type == "done":
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

    return JSONResponse(
        {
            "content": final_content,
            "segments": segments,
            "title": title,
        }
    )
