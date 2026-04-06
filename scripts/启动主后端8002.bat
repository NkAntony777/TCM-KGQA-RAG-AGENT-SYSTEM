@echo off
setlocal
cd /d "%~dp0..\backend"
set "UV_CACHE_DIR=%~dp0..\.uv-cache"
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8002
