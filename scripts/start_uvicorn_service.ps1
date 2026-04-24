param(
    [Parameter(Mandatory = $true)]
    [string]$BackendDir,

    [Parameter(Mandatory = $true)]
    [string]$Module,

    [Parameter(Mandatory = $true)]
    [int]$Port,

    [string]$PythonExe = "",

    [switch]$UseUvRun,

    [int]$Workers = 1,

    [switch]$DisableReload,

    [switch]$EvalMode
)

$ErrorActionPreference = "Stop"

function Add-TargetPid {
    param(
        [System.Collections.Generic.HashSet[int]]$Set,
        [int]$ProcessId
    )
    if ($ProcessId -gt 0 -and $ProcessId -ne $PID) {
        [void]$Set.Add($ProcessId)
    }
}

function Get-ListeningProcessIds {
    param(
        [int]$TargetPort
    )
    $ids = [System.Collections.Generic.HashSet[int]]::new()
    try {
        Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction Stop |
            ForEach-Object {
                Add-TargetPid -Set $ids -ProcessId ([int]$_.OwningProcess)
            }
    } catch {
    }
    return $ids
}

if (-not (Test-Path -LiteralPath $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}

$targets = [System.Collections.Generic.HashSet[int]]::new()
$modulePattern = "*$Module*"
$portPattern = "*--port*$Port*"

try {
    Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like $modulePattern -and
            $_.CommandLine -like $portPattern
        } |
        ForEach-Object {
            Add-TargetPid -Set $targets -ProcessId ([int]$_.ProcessId)
        }
} catch {
    Write-Warning ("Failed to enumerate Win32_Process for stale process cleanup: {0}" -f $_.Exception.Message)
}

try {
    foreach ($listeningPid in (Get-ListeningProcessIds -TargetPort $Port)) {
        Add-TargetPid -Set $targets -ProcessId $listeningPid
    }
} catch {}

foreach ($targetPid in $targets) {
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction Stop
        Write-Host "[INFO] Stopped stale process $targetPid for $Module on port $Port"
    } catch {
        Write-Warning ("Failed to stop stale process {0}: {1}" -f $targetPid, $_.Exception.Message)
    }
}

$portCleared = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $remaining = @(Get-ListeningProcessIds -TargetPort $Port)
    if ($remaining.Count -eq 0) {
        $portCleared = $true
        break
    }
    if ($attempt -eq 0) {
        Write-Host "[INFO] Waiting for port $Port to be released..."
    }
    Start-Sleep -Milliseconds 500
}

if (-not $portCleared) {
    $remainingText = ((Get-ListeningProcessIds -TargetPort $Port) | ForEach-Object { "$_" }) -join ","
    throw "Port $Port is still occupied after cleanup. Remaining PIDs: $remainingText"
}

Set-Location -LiteralPath $BackendDir
Start-Sleep -Seconds 1

$effectiveWorkers = [Math]::Max(1, $Workers)
$useReload = (-not $DisableReload) -and ($effectiveWorkers -le 1)
if ((-not $DisableReload) -and ($effectiveWorkers -gt 1)) {
    Write-Warning "[INFO] workers > 1 detected, forcing no-reload mode for uvicorn."
}

if ($EvalMode) {
    $env:SKIP_MEMORY_INDEX_STARTUP_REBUILD = "1"
    Write-Host "[INFO] Eval mode enabled: SKIP_MEMORY_INDEX_STARTUP_REBUILD=1"
}

Write-Host "[INFO] Starting $Module on port $Port (workers=$effectiveWorkers reload=$useReload eval_mode=$EvalMode)"

$uvicornArgs = @($Module, "--host", "0.0.0.0", "--port", "$Port")
if ($useReload) {
    $uvicornArgs += "--reload"
}
if ($effectiveWorkers -gt 1) {
    $uvicornArgs += @("--workers", "$effectiveWorkers")
}

if ($UseUvRun) {
    $uv = Get-Command uv -ErrorAction Stop
    $env:UV_CACHE_DIR = Join-Path (Split-Path -Parent $BackendDir) ".uv-cache"
    & $uv.Source run uvicorn @uvicornArgs
    exit $LASTEXITCODE
}

if (-not $PythonExe) {
    throw "PythonExe is required when UseUvRun is not set."
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

& $PythonExe -m uvicorn @uvicornArgs
exit $LASTEXITCODE
