from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.app_context import require_session_manager, summarize_history

router = APIRouter()


@router.post("/sessions/{session_id}/compress")
async def compress_session(session_id: str) -> dict[str, int]:
    try:
        session_manager = require_session_manager()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Application context is not initialized") from exc

    record = session_manager.get_history(session_id)
    messages = record.get("messages", [])
    if len(messages) < 4:
        raise HTTPException(status_code=400, detail="At least 4 messages are required")

    n_messages = max(4, len(messages) // 2)
    summary = await summarize_history(messages[:n_messages])
    result = session_manager.compress_history(session_id, summary, n_messages)
    return result
