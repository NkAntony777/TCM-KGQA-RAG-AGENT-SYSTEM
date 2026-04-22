from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _safe_run(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception:
        return ""
    output = (completed.stdout or completed.stderr or "").strip()
    return output[:4000]


def _powershell_output(script: str) -> str:
    if os.name != "nt":
        return ""
    output = _safe_run(["powershell", "-NoProfile", "-Command", script])
    if "拒绝访问" in output or "PermissionDenied" in output:
        return ""
    return output


def collect_experiment_environment(*, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "captured_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version.split()[0],
        },
        "runtime": {
            "cwd": str(Path.cwd()),
            "pid": os.getpid(),
            "cpu_count": os.cpu_count(),
        },
        "env_flags": {
            "files_first_dense_fallback_enabled": os.getenv("FILES_FIRST_DENSE_FALLBACK_ENABLED"),
            "vector_compatibility_enabled": os.getenv("VECTOR_COMPATIBILITY_ENABLED"),
            "path_query_execution_mode": os.getenv("PATH_QUERY_EXECUTION_MODE"),
            "openai_model": os.getenv("OPENAI_MODEL"),
            "embedding_model": os.getenv("EMBEDDING_MODEL"),
        },
    }

    if os.name == "nt":
        sysinfo = _powershell_output(
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress"
        )
        cpu = _powershell_output(
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"
        )
        osinfo = _powershell_output(
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Compress"
        )
        gpu = _powershell_output(
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
        )
        windows_payload = {
            "computer_system": sysinfo,
            "cpu": cpu,
            "os": osinfo,
            "gpu": gpu,
        }
        windows_payload = {key: value for key, value in windows_payload.items() if value}
        if windows_payload:
            manifest["windows"] = windows_payload

    if extra:
        manifest["experiment"] = dict(extra)
    return manifest
