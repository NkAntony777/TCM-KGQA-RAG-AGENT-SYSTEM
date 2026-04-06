param(
    [Parameter(Mandatory = $true)]
    [string]$BackendDir,

    [Parameter(Mandatory = $true)]
    [string]$Module,

    [Parameter(Mandatory = $true)]
    [int]$Port,

    [string]$PythonExe = "",

    [switch]$UseUvRun
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

if (-not (Test-Path -LiteralPath $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}

$targets = [System.Collections.Generic.HashSet[int]]::new()
$modulePattern = "*$Module*"
$portPattern = "*--port*$Port*"

Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like $modulePattern -and
        $_.CommandLine -like $portPattern
    } |
    ForEach-Object {
        Add-TargetPid -Set $targets -ProcessId ([int]$_.ProcessId)
    }

try {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
        ForEach-Object {
            Add-TargetPid -Set $targets -ProcessId ([int]$_.OwningProcess)
        }
} catch {
}

foreach ($targetPid in $targets) {
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction Stop
        Write-Host "[INFO] Stopped stale process $targetPid for $Module on port $Port"
    } catch {
        Write-Warning ("Failed to stop stale process {0}: {1}" -f $targetPid, $_.Exception.Message)
    }
}

Set-Location -LiteralPath $BackendDir
Start-Sleep -Seconds 1

Write-Host "[INFO] Starting $Module on port $Port"

if ($UseUvRun) {
    $uv = Get-Command uv -ErrorAction Stop
    $env:UV_CACHE_DIR = Join-Path (Split-Path -Parent $BackendDir) ".uv-cache"
    & $uv.Source run uvicorn $Module --reload --host 0.0.0.0 --port $Port
    exit $LASTEXITCODE
}

if (-not $PythonExe) {
    throw "PythonExe is required when UseUvRun is not set."
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

& $PythonExe -m uvicorn $Module --reload --host 0.0.0.0 --port $Port
exit $LASTEXITCODE
