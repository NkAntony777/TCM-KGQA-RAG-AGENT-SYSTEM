@echo off
setlocal

set "PORT=7800"
set "HOST=127.0.0.1"
set "BACKEND_DIR=%~dp0.."
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "ENV_FILE=%BACKEND_DIR%\.env"
set "UVICORN_APP=scripts.pipeline_server:app"
set "UVICORN_ARGS=--host %HOST% --port %PORT% --log-level info"
set "PYTHON_BIN="
set "RUNNER_LABEL="
set "USE_UV=0"

cd /d "%BACKEND_DIR%"
if errorlevel 1 goto :cd_failed

echo.
echo ============================================================
echo   TCM Pipeline Console
echo   Backend: %BACKEND_DIR%
echo   URL    : http://%HOST%:%PORT%
echo ============================================================
echo.

call :check_port_in_use
if defined PORT_PID goto :restart_existing

call :select_runner
if errorlevel 1 goto :missing_runtime
call :show_runtime_info
goto :launch_server

:select_runner
if exist "%VENV_PYTHON%" (
  set "PYTHON_BIN=%VENV_PYTHON%"
  set "RUNNER_LABEL=.venv"
  set "USE_UV=0"
  exit /b 0
)
where uv >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_BIN=python"
  set "RUNNER_LABEL=uv run"
  set "USE_UV=1"
  exit /b 0
)
exit /b 1

:show_runtime_info
echo [INFO] Python Runner: %RUNNER_LABEL%
call :run_python "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 goto :missing_deps
call :run_python "import sys; print('[INFO] sys.executable = ' + sys.executable); print('[INFO] sys.prefix     = ' + sys.prefix)"
if exist "%ENV_FILE%" (
  call :run_python "from scripts.pipeline_server import _build_pipeline; p=_build_pipeline({}); print('[INFO] Loaded providers = ' + str(len(p.config.providers))); print('[INFO] Provider names   = ' + ', '.join(x.name for x in p.config.providers))"
) else (
  echo [WARN] Missing .env file: %ENV_FILE%
)
exit /b 0

:launch_server
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://%HOST%:%PORT%"
echo [INFO] Starting server without reload. Press Ctrl+C to stop.
echo.
if "%USE_UV%"=="1" (
  uv run python -m uvicorn %UVICORN_APP% %UVICORN_ARGS%
) else (
  "%PYTHON_BIN%" -m uvicorn %UVICORN_APP% %UVICORN_ARGS%
)
goto :done

:run_python
if "%USE_UV%"=="1" (
  uv run python -c "%~1"
) else (
  "%PYTHON_BIN%" -c "%~1"
)
exit /b %errorlevel%

:missing_deps
echo [ERROR] Missing fastapi or uvicorn in the project environment.
echo [ERROR] Please run "uv sync" in the backend directory first.
pause
exit /b 1

:missing_runtime
echo [ERROR] Neither project .venv nor uv is available.
echo [ERROR] Please run "uv sync" in the backend directory first.
pause
exit /b 1

:check_port_in_use
set "PORT_PID="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess; if ($c) { Write-Output $c }"`) do set "PORT_PID=%%i"
exit /b 0

:restart_existing
echo [WARN] Port %PORT% is already in use.
echo [WARN] Stopping the existing process before restart.
powershell -NoProfile -Command "$pidValue=%PORT_PID%; Get-CimInstance Win32_Process -Filter \"ProcessId = $pidValue\" | Select-Object ProcessId, Name, ExecutablePath, CommandLine | Format-List"
powershell -NoProfile -Command "$pidValue=%PORT_PID%; Stop-Process -Id $pidValue -Force"
if errorlevel 1 goto :stop_failed
timeout /t 2 /nobreak >nul
set "PORT_PID="
call :check_port_in_use
if defined PORT_PID goto :stop_failed
echo [INFO] Existing process stopped.
echo.
call :select_runner
if errorlevel 1 goto :missing_runtime
call :show_runtime_info
goto :launch_server

:stop_failed
echo [ERROR] Failed to stop the process using port %PORT%.
echo [ERROR] Please close it manually and try again.
pause
exit /b 1

:cd_failed
echo [ERROR] Failed to enter backend directory: %BACKEND_DIR%
pause
exit /b 1

:done
echo.
echo [INFO] Server stopped.
pause
