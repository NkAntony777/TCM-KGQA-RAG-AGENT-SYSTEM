$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

Write-Host "[warmup] start"
& ".\.venv\Scripts\python.exe" -c "import httpx; payload={'query':'六味地黄丸的组成是什么？','mode':'quick','top_k':12}; r=httpx.post('http://127.0.0.1:8002/api/qa/answer?mode=quick', json=payload, timeout=240.0); print('[warmup] status=', r.status_code)"
Write-Host "[warmup] done"

Write-Host "[eval] start end-to-end 24"
$env:UV_CACHE_DIR = Join-Path $backendRoot ".uv-cache"
& ".\.venv\Scripts\python.exe" ".\paper_experiments\run_end_to_end_qa_paper_eval.py" `
  --datasets (Join-Path $backendRoot "eval\datasets\paper\end_to_end_qa_paper_eval_24.json") `
  --base-url "http://127.0.0.1:8002" `
  --modes quick deep `
  --top-k 12 `
  --timeout 240 `
  --workers 0 `
  --auto-workers 8
Write-Host "[eval] finished"
