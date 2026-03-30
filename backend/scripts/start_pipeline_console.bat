@echo off
setlocal

set "PORT=7800"
set "HOST=127.0.0.1"
set "BACKEND_DIR=%~dp0.."
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "UVICORN_APP=scripts.pipeline_server:app"
set "UVICORN_ARGS=--host %HOST% --port %PORT% --log-level info"

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

where uv >nul 2>&1
if not errorlevel 1 goto :run_with_uv

if exist "%VENV_PYTHON%" goto :run_with_venv

echo [ERROR] Neither uv nor project .venv is available.
echo [ERROR] Please run "uv sync" in the backend directory first.
pause
exit /b 1

:run_with_uv
echo [INFO] Python Runner: uv run
uv run python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 goto :missing_deps
uv run python -c "import sys; print('[INFO] sys.executable = ' + sys.executable); print('[INFO] sys.prefix     = ' + sys.prefix)"
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://%HOST%:%PORT%"
echo [INFO] Starting server without reload. Press Ctrl+C to stop.
echo.
uv run python -m uvicorn %UVICORN_APP% %UVICORN_ARGS%
goto :done

:run_with_venv
echo [INFO] Python Runner: .venv
"%VENV_PYTHON%" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 goto :missing_deps
"%VENV_PYTHON%" -c "import sys; print('[INFO] sys.executable = ' + sys.executable); print('[INFO] sys.prefix     = ' + sys.prefix)"
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://%HOST%:%PORT%"
echo [INFO] Starting server without reload. Press Ctrl+C to stop.
echo.
"%VENV_PYTHON%" -m uvicorn %UVICORN_APP% %UVICORN_ARGS%
goto :done

:missing_deps
echo [ERROR] Missing fastapi or uvicorn in the project environment.
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
where uv >nul 2>&1
if not errorlevel 1 goto :run_with_uv
if exist "%VENV_PYTHON%" goto :run_with_venv
goto :missing_deps

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
