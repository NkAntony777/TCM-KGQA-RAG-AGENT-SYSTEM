@echo off
setlocal
if "%EVAL_WORKERS%"=="" set "EVAL_WORKERS=2"
echo [INFO] Evaluation backend workers=%EVAL_WORKERS%
call "%~dp0scripts\start_backend_8002_eval.bat"
