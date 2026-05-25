@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo TCM QA System Startup
echo ========================================
echo.

if not exist ".\backend\pyproject.toml" (
  echo [ERROR] backend\pyproject.toml not found
  pause
  exit /b 1
)

if not exist ".\frontend\package.json" (
  echo [ERROR] frontend\package.json not found
  pause
  exit /b 1
)

echo Stopping existing QA processes on ports 3000, 8002, 8101, 8102...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_qa_ports.ps1"
if errorlevel 1 (
  echo [ERROR] Failed to release QA ports
  pause
  exit /b 1
)
echo.

echo Starting graph-service 8101...
start "TCM Graph Service 8101" "%~dp0scripts\start_graph_8101.bat"

echo Starting retrieval-service 8102...
start "TCM Retrieval Service 8102" "%~dp0scripts\start_retrieval_8102.bat"

echo Starting main backend 8002...
start "TCM Main Backend 8002" "%~dp0scripts\start_backend_8002.bat"

echo Starting frontend 3000...
start "TCM Frontend 3000" "%~dp0scripts\start_frontend_3000.bat"

echo.
echo Startup commands dispatched.
echo Open after services are ready:
echo   http://127.0.0.1:3000
echo.
pause
