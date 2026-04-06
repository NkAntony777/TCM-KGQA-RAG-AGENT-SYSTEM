@echo off
setlocal
cd /d "%~dp0..\backend"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] backend\.venv\Scripts\python.exe not found
  pause
  exit /b 1
)
echo [INFO] Using project env: "%PYTHON_EXE%"
"%PYTHON_EXE%" -m uvicorn app:app --reload --host 0.0.0.0 --port 8002
