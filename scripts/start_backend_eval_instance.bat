@echo off
setlocal

if "%~1"=="" (
  echo [ERROR] Port is required. Usage: start_backend_eval_instance.bat 8002
  exit /b 1
)

set "PORT=%~1"
cd /d "%~dp0..\backend"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] backend\.venv\Scripts\python.exe not found
  pause
  exit /b 1
)

echo [INFO] Using project env: "%PYTHON_EXE%"
echo [INFO] Starting evaluation backend on %PORT% with single worker
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_uvicorn_service.ps1" ^
  -BackendDir "%CD%" ^
  -PythonExe "%PYTHON_EXE%" ^
  -Module "app:app" ^
  -Port %PORT% ^
  -Workers 1 ^
  -DisableReload ^
  -EvalMode
