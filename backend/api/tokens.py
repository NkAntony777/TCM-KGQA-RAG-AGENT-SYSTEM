from __future__ import annotations

from typing import Any

import tiktoken
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import runtime_config
from graph.prompt_builder import build_system_prompt
from services.app_context import require_backend_dir, require_session_manager

router = APIRouter()

ENCODER = tiktoken.get_encoding("cl100k_base")


class FileTokensRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)


def _count_tokens(text: str) -> int:
    return len(ENCODER.encode(text or ""))


@router.get("/tokens/session/{session_id}")
async def session_tokens(session_id: str) -> dict[str, int]:
    session_manager = _session_manager_or_503()
    base_dir = _backend_dir_or_503()

    record = session_manager.get_history(session_id)
    system_prompt = build_system_prompt(base_dir, runtime_config.get_rag_mode())
    message_text = []
    for item in record.get("messages", []):
        message_text.append(str(item.get("content", "")))
        for tool_call in item.get("tool_calls", []) or []:
            message_text.append(str(tool_call))

    system_tokens = _count_tokens(system_prompt)
    message_tokens = _count_tokens("\n".join(message_text))
    return {
        "system_tokens": system_tokens,
        "message_tokens": message_tokens,
        "total_tokens": system_tokens + message_tokens,
    }


@router.post("/tokens/files")
async def file_tokens(payload: FileTokensRequest) -> dict[str, Any]:
    base_dir = _backend_dir_or_503()

    files: list[dict[str, Any]] = []
    total = 0
    for relative_path in payload.paths:
        path = (base_dir / relative_path).resolve()
        if not path.exists() or path.is_dir():
            continue
        count = _count_tokens(path.read_text(encoding="utf-8"))
        total += count
        files.append({"path": relative_path, "tokens": count})

    return {"files": files, "total_tokens": total}


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
