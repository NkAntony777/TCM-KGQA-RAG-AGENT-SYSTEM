@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Evaluation Backend Cluster Startup
echo ========================================
echo.

for %%P in (8002 8003 8004 8005) do (
  echo Starting evaluation backend %%P...
  start "Eval Backend %%P" "%~dp0scripts\start_backend_eval_instance.bat" %%P
)

echo.
echo Evaluation backend cluster start commands dispatched.
echo Backend pool:
echo   http://127.0.0.1:8002
echo   http://127.0.0.1:8003
echo   http://127.0.0.1:8004
echo   http://127.0.0.1:8005
echo.
pause
