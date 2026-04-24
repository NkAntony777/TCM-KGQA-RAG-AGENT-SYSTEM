from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chat import router as chat_router
from api.compress import router as compress_router
from api.config_api import router as config_router
from api.files import router as files_router
from api.qa import router as qa_router
from api.sessions import router as sessions_router
from api.tokens import router as tokens_router
from config import get_settings
from graph.memory_indexer import memory_indexer
from services.app_context import initialize_app_context
from services.qa_service.skill_registry import clear_runtime_skills_cache
from tools.skills_scanner import refresh_snapshot


def _env_enabled(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _parse_cors_origins() -> tuple[list[str], bool]:
    configured = os.getenv("BACKEND_CORS_ORIGINS", "").strip()
    if configured:
        origins = [item.strip().rstrip("/") for item in configured.split(",") if item.strip()]
    else:
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    allow_credentials = _env_enabled("BACKEND_CORS_ALLOW_CREDENTIALS", default=True)
    if "*" in origins and allow_credentials:
        allow_credentials = False
    return origins, allow_credentials


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    refresh_snapshot(settings.backend_dir)
    clear_runtime_skills_cache()
    initialize_app_context(settings.backend_dir)
    memory_indexer.configure(settings.backend_dir)
    if not _env_enabled("SKIP_MEMORY_INDEX_STARTUP_REBUILD", default=False):
        memory_indexer.rebuild_index()
    yield


app = FastAPI(
    title="Mini-OpenClaw API",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins, cors_allow_credentials = _parse_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(qa_router, prefix="/api", tags=["qa"])
app.include_router(sessions_router, prefix="/api", tags=["sessions"])
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(tokens_router, prefix="/api", tags=["tokens"])
app.include_router(compress_router, prefix="/api", tags=["compress"])
app.include_router(config_router, prefix="/api", tags=["config"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
