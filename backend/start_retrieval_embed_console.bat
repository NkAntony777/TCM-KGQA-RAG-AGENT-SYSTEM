@echo off
setlocal

set "BACKEND_DIR=%~dp0"
set "SESSION_NAME=herb2-modern"
set "WORKERS=4"
set "BATCH_SIZE=64"
set "EXTRA_ARGS=--exclude-sample"
set "CLI_ARGS=%*"
set "USE_UV=0"
set "RUNNER_LABEL="

cd /d "%BACKEND_DIR%"
if errorlevel 1 goto :cd_failed

if not exist ".uv-cache-local" mkdir ".uv-cache-local"
if not exist ".tmp-tests" mkdir ".tmp-tests"

set "UV_CACHE_DIR=%BACKEND_DIR%.uv-cache-local"
set "TMP=%BACKEND_DIR%.tmp-tests"
set "TEMP=%TMP%"
set "PYTHONPATH=%BACKEND_DIR%"

where uv >nul 2>&1
if not errorlevel 1 (
  set "USE_UV=1"
  set "RUNNER_LABEL=uv run"
  goto :launch
)

if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
  set "USE_UV=0"
  set "RUNNER_LABEL=.venv python"
  goto :launch
)

goto :missing_runtime

:launch
echo.
echo ============================================================
echo   Retrieval Embed Console
echo   Backend    : %BACKEND_DIR%
echo   Session    : %SESSION_NAME%
echo   Workers    : %WORKERS%
echo   Batch Size : %BATCH_SIZE%
echo   Extra Args : %EXTRA_ARGS%
echo   Runner     : %RUNNER_LABEL%
echo ============================================================
echo.
echo Commands after startup:
echo   status
echo   resume
echo   set workers 8
echo   set batch 96
echo   finalize
echo   quit
echo.

if "%USE_UV%"=="1" (
  uv run python scripts\retrieval_embed_console.py --session %SESSION_NAME% --workers %WORKERS% --batch-size %BATCH_SIZE% %EXTRA_ARGS% %CLI_ARGS%
) else (
  "%BACKEND_DIR%\.venv\Scripts\python.exe" scripts\retrieval_embed_console.py --session %SESSION_NAME% --workers %WORKERS% --batch-size %BATCH_SIZE% %EXTRA_ARGS% %CLI_ARGS%
)

echo.
echo [INFO] Embed console exited.
pause
exit /b 0

:missing_runtime
echo [ERROR] uv and project .venv are both unavailable.
echo [ERROR] Please run "uv sync" in the backend directory first.
pause
exit /b 1

:cd_failed
echo [ERROR] Failed to enter backend directory: %BACKEND_DIR%
pause
exit /b 1
