param(
    [int[]]$Ports = @(3000, 8002, 8101, 8102),
    [int]$WaitAttempts = 40,
    [int]$WaitMilliseconds = 500
)

$ErrorActionPreference = "Stop"

function Get-ListeningProcessIds {
    param(
        [int[]]$TargetPorts
    )

    $ids = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($port in $TargetPorts) {
        try {
            Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                ForEach-Object {
                    $pidValue = [int]$_.OwningProcess
                    if ($pidValue -gt 0 -and $pidValue -ne $PID) {
                        [void]$ids.Add($pidValue)
                    }
                }
        } catch {
        }
    }
    return $ids
}

function Get-ChildProcessTreeIds {
    param(
        [int]$RootProcessId
    )

    $childrenByParent = @{}
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop |
            ForEach-Object {
                $parentId = [int]$_.ParentProcessId
                $childId = [int]$_.ProcessId
                if (-not $childrenByParent.ContainsKey($parentId)) {
                    $childrenByParent[$parentId] = [System.Collections.Generic.List[int]]::new()
                }
                $childrenByParent[$parentId].Add($childId)
            }
    } catch {
        return @()
    }

    $result = [System.Collections.Generic.List[int]]::new()
    $stack = [System.Collections.Generic.Stack[int]]::new()
    $stack.Push($RootProcessId)
    while ($stack.Count -gt 0) {
        $current = $stack.Pop()
        if (-not $childrenByParent.ContainsKey($current)) {
            continue
        }
        foreach ($childId in $childrenByParent[$current]) {
            if ($childId -gt 0 -and $childId -ne $PID) {
                $result.Add($childId)
                $stack.Push($childId)
            }
        }
    }
    return $result.ToArray()
}

function Stop-TargetProcessTree {
    param(
        [int]$RootProcessId
    )

    $treeIds = [System.Collections.Generic.List[int]]::new()
    foreach ($childId in (Get-ChildProcessTreeIds -RootProcessId $RootProcessId)) {
        if ($childId -gt 0 -and $childId -ne $PID) {
            $treeIds.Add($childId)
        }
    }
    if ($RootProcessId -gt 0 -and $RootProcessId -ne $PID) {
        $treeIds.Add($RootProcessId)
    }

    foreach ($targetPid in $treeIds.ToArray()) {
        try {
            Stop-Process -Id $targetPid -Force -ErrorAction Stop
        } catch {
        }
    }

    try {
        & taskkill.exe /PID $RootProcessId /T /F 2>$null | Out-Null
    } catch {
    }
}

$targets = @(Get-ListeningProcessIds -TargetPorts $Ports)
if ($targets.Count -eq 0) {
    Write-Host "[INFO] No stale QA processes found on ports: $($Ports -join ', ')"
    exit 0
}

foreach ($targetPid in $targets) {
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction Stop
        Write-Host "[INFO] Stopping PID ${targetPid}: $($process.CommandLine)"
    } catch {
        Write-Host "[INFO] Stopping PID $targetPid"
    }

    try {
        Stop-TargetProcessTree -RootProcessId $targetPid
    } catch {
        Write-Warning ("Failed to stop PID {0}: {1}" -f $targetPid, $_.Exception.Message)
    }
}

for ($attempt = 0; $attempt -lt $WaitAttempts; $attempt++) {
    $remaining = @(Get-ListeningProcessIds -TargetPorts $Ports)
    if ($remaining.Count -eq 0) {
        Write-Host "[INFO] QA ports released: $($Ports -join ', ')"
        exit 0
    }
    if ($attempt -eq 0) {
        Write-Host "[INFO] Waiting for QA ports to be released..."
    }
    foreach ($remainingPid in $remaining) {
        Stop-TargetProcessTree -RootProcessId $remainingPid
    }
    Start-Sleep -Milliseconds $WaitMilliseconds
}

$remaining = @(Get-ListeningProcessIds -TargetPorts $Ports)
throw "QA ports are still occupied after cleanup. Remaining PIDs: $($remaining -join ', ')"
