from __future__ import annotations

import json
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api.chat_events import apply_event_to_segments, apply_result_to_segments, new_segment, result_to_events
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
    for event in result_to_events(result):
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
        current_segment = new_segment()
        final_result: dict[str, Any] | None = None

        try:
            async for event in _event_sequence(payload):
                if event["type"] == "result":
                    result = event.get("result")
                    if isinstance(result, dict):
                        final_result = result
                        apply_result_to_segments(result=result, segments=segments)
                    continue
                current_segment = apply_event_to_segments(
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
    current_segment = new_segment()
    final_content = ""
    title: str | None = None
    final_result: dict[str, Any] | None = None

    try:
        async for event in _event_sequence(payload):
            if event["type"] == "result":
                result = event.get("result")
                if isinstance(result, dict):
                    final_result = result
                    apply_result_to_segments(result=result, segments=segments)
                continue
            current_segment = apply_event_to_segments(
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
