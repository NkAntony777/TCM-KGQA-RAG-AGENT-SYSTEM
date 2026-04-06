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
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_uvicorn_service.ps1" ^
  -BackendDir "%CD%" ^
  -PythonExe "%PYTHON_EXE%" ^
  -Module "app:app" ^
  -Port 8002
