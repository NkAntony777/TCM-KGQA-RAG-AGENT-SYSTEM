from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from graph.memory_indexer import memory_indexer
from services.app_context import require_backend_dir
from services.qa_service.skill_registry import clear_runtime_skills_cache, get_runtime_skills
from tools.skills_scanner import refresh_snapshot, scan_skills

router = APIRouter()

ALLOWED_PREFIXES = ("workspace/", "memory/", "skills/", "knowledge/")
ALLOWED_ROOT_FILES = {"SKILLS_SNAPSHOT.md"}


class SaveFileRequest(BaseModel):
    path: str = Field(..., min_length=1)
    content: str


class SkillRecord(BaseModel):
    name: str
    description: str
    path: str
    preferred_tools: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    output_focus: list[str] = Field(default_factory=list)
    stop_rules: list[str] = Field(default_factory=list)


def _resolve_path(relative_path: str) -> Path:
    base_dir = _backend_dir_or_503()

    normalized = relative_path.replace("\\", "/").strip("/")
    if normalized not in ALLOWED_ROOT_FILES and not normalized.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail="Path is not in the editable whitelist")

    candidate = (base_dir / normalized).resolve()
    resolved_base_dir = base_dir.resolve()
    if resolved_base_dir not in candidate.parents and candidate != resolved_base_dir:
        raise HTTPException(status_code=400, detail="Path traversal detected")
    return candidate


@router.get("/files")
async def read_file(path: str = Query(..., min_length=1)) -> dict[str, str]:
    file_path = _resolve_path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "path": path.replace("\\", "/"),
        "content": file_path.read_text(encoding="utf-8"),
    }


@router.post("/files")
async def save_file(payload: SaveFileRequest) -> dict[str, Any]:
    file_path = _resolve_path(payload.path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(payload.content, encoding="utf-8")

    normalized = payload.path.replace("\\", "/")
    if normalized == "memory/MEMORY.md":
        memory_indexer.rebuild_index()
    if normalized.startswith("skills/"):
        refresh_snapshot(_backend_dir_or_503())
        clear_runtime_skills_cache()

    return {"ok": True, "path": normalized}


@router.get("/skills", response_model=list[SkillRecord])
async def list_skills() -> list[SkillRecord]:
    base_dir = _backend_dir_or_503()
    runtime_skills = get_runtime_skills()
    records: list[SkillRecord] = []
    for skill in scan_skills(base_dir):
        runtime_skill = runtime_skills.get(skill.name)
        records.append(
            SkillRecord(
                name=skill.name,
                description=skill.description,
                path=skill.path,
                preferred_tools=list(runtime_skill.preferred_tools) if runtime_skill else [],
                workflow_steps=list(runtime_skill.workflow_steps) if runtime_skill else [],
                output_focus=list(runtime_skill.output_focus) if runtime_skill else [],
                stop_rules=list(runtime_skill.stop_rules) if runtime_skill else [],
            )
        )
    return records


def _backend_dir_or_503() -> Path:
    try:
        return require_backend_dir()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Application context is not initialized") from exc
