from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import runtime_config
from graph.prompt_builder import build_system_prompt
from services.app_context import generate_title as generate_session_title
from services.app_context import require_backend_dir, require_session_manager

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str = "新会话"


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class GenerateTitleRequest(BaseModel):
    message: str | None = None


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    session_manager = _session_manager_or_503()
    return session_manager.list_sessions()


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest) -> dict[str, Any]:
    session_manager = _session_manager_or_503()
    return session_manager.create_session(title=payload.title)


@router.put("/sessions/{session_id}")
async def rename_session(session_id: str, payload: RenameSessionRequest) -> dict[str, Any]:
    session_manager = _session_manager_or_503()
    return session_manager.rename_session(session_id, payload.title)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, bool]:
    session_manager = _session_manager_or_503()
    session_manager.delete_session(session_id)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str) -> dict[str, Any]:
    session_manager = _session_manager_or_503()
    base_dir = _backend_dir_or_503()
    return {
        "system_prompt": build_system_prompt(base_dir, runtime_config.get_rag_mode()),
        "messages": session_manager.load_session(session_id),
    }


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> dict[str, Any]:
    session_manager = _session_manager_or_503()
    return session_manager.get_history(session_id)


@router.post("/sessions/{session_id}/generate-title")
async def generate_title(session_id: str, payload: GenerateTitleRequest) -> dict[str, str]:
    session_manager = _session_manager_or_503()
    if payload.message:
        seed = payload.message
    else:
        messages = session_manager.load_session(session_id)
        first_user = next((item["content"] for item in messages if item.get("role") == "user"), "")
        seed = first_user
    title = await generate_session_title(seed or "新会话")
    session_manager.set_title(session_id, title)
    return {"session_id": session_id, "title": title}


def _session_manager_or_503():
    try:
        return require_session_manager()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Application context is not initialized") from exc


def _backend_dir_or_503():
    try:
        return require_backend_dir()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Application context is not initialized") from exc
