$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:NO_PROXY = "127.0.0.1,localhost"
$env:UV_CACHE_DIR = Join-Path $backendRoot ".uv-cache"

Write-Host "[doctoral] start"
& ".\.venv\Scripts\python.exe" ".\scripts\run_doctoral_hard_probe.py" `
  --backend-url "http://127.0.0.1:8002" `
  --output (Join-Path $backendRoot "eval\doctoral_hard_probe_quick_deep_20260420_paper.json") `
  --top-k 12 `
  --timeout-sec 900
Write-Host "[doctoral] finished"
