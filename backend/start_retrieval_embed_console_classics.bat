@echo off
setlocal

set "BACKEND_DIR=%~dp0"
set "SESSION_NAME=classics-vector"
set "WORKERS=8"
set "BATCH_SIZE=64"
set "EXTRA_ARGS=--exclude-sample --exclude-modern --target-store local_json"
set "CLI_ARGS=%*"

cd /d "%BACKEND_DIR%"
if errorlevel 1 goto :cd_failed

set "PYTHONPATH=%BACKEND_DIR%"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "GIT_HTTP_PROXY="
set "GIT_HTTPS_PROXY="

echo.
echo ============================================================
echo   Classics Retrieval Embed Console
echo   Backend    : %BACKEND_DIR%
echo   Session    : %SESSION_NAME%
echo   Workers    : %WORKERS%
echo   Batch Size : %BATCH_SIZE%
echo   Extra Args : %EXTRA_ARGS%
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

"%BACKEND_DIR%\.venv\Scripts\python.exe" scripts\retrieval_embed_console.py --session %SESSION_NAME% --workers %WORKERS% --batch-size %BATCH_SIZE% %EXTRA_ARGS% %CLI_ARGS%

echo.
echo [INFO] Classics embed console exited.
pause
exit /b 0

:cd_failed
echo [ERROR] Failed to enter backend directory: %BACKEND_DIR%
pause
exit /b 1
