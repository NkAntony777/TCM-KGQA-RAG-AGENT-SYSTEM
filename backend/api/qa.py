from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from graph.agent import agent_manager
from services.common.models import success
from services.qa_service.engine import get_qa_service

router = APIRouter()


class QAAnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User TCM question")
    mode: Literal["quick", "deep"] = Field(default="quick", description="QA execution mode")
    top_k: int = Field(default=12, ge=1, le=20, description="Evidence selection size")
    session_id: str | None = Field(default=None, description="Optional session id for persistence")


def _tool_calls_from_trace(tool_trace: list[dict[str, object]] | object) -> list[dict[str, object]]:
    if not isinstance(tool_trace, list):
        return []
    calls: list[dict[str, object]] = []
    for item in tool_trace:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool", "tool")).strip() or "tool"
        meta = item.get("meta", {}) if isinstance(item.get("meta"), dict) else {}
        calls.append(
            {
                "tool": tool_name,
                "input": "",
                "output": json.dumps(meta, ensure_ascii=False) if meta else "",
                "meta": meta or None,
            }
        )
    return calls


@router.post("/qa/answer")
async def answer_question(
    payload: QAAnswerRequest,
    mode: Literal["quick", "deep"] | None = Query(default=None, description="Optional query-string override for QA mode"),
):
    try:
        resolved_mode = mode or payload.mode
        data = await get_qa_service().answer(
            payload.query,
            mode=resolved_mode,
            top_k=payload.top_k,
        )
        if payload.session_id:
            session_manager = agent_manager.session_manager
            if session_manager is None:
                raise HTTPException(status_code=503, detail="Agent manager is not initialized")
            session_manager.save_message(payload.session_id, "user", payload.query)
            session_manager.save_message(
                payload.session_id,
                "assistant",
                str(data.get("answer", "") or ""),
                tool_calls=_tool_calls_from_trace(data.get("tool_trace")),
                meta={
                    "route": data.get("route"),
                    "evidence": [*data.get("factual_evidence", []), *data.get("case_references", [])],
                    "planner_steps": data.get("planner_steps"),
                    "deep_trace": data.get("deep_trace"),
                    "evidence_bundle": data.get("evidence_bundle"),
                    "qa_mode": data.get("mode", resolved_mode),
                    "citations": data.get("citations"),
                    "tool_trace": data.get("tool_trace"),
                    "notes": data.get("notes"),
                },
            )
            history = session_manager.load_session_record(payload.session_id).get("messages", [])
            is_first_user_message = len([item for item in history if item.get("role") == "user"]) == 1
            if is_first_user_message:
                title = await agent_manager.generate_title(payload.query)
                session_manager.set_title(payload.session_id, title)
                data["session_title"] = title
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return success(data)
