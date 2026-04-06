@echo off
setlocal
cd /d "%~dp0..\backend"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_uvicorn_service.ps1" ^
  -BackendDir "%CD%" ^
  -Module "services.retrieval_service.app:app" ^
  -Port 8102 ^
  -UseUvRun
