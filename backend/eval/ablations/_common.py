from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    return [item for item in payload if isinstance(item, dict)]


def post_json(url: str, payload: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("response_not_object")
    return parsed


def get_json(url: str, *, timeout_s: int) -> dict[str, Any]:
    request = Request(url=url, method="GET")
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("response_not_object")
    return parsed


def wait_health(base_url: str, *, timeout_s: int = 60) -> bool:
    started = time.time()
    while time.time() - started <= timeout_s:
        try:
            payload = get_json(f"{base_url.rstrip('/')}/health", timeout_s=5)
            if payload.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def start_backend(*, port: int, env_overrides: dict[str, str] | None = None, stdout_path: Path | None = None, stderr_path: Path | None = None) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    if env_overrides:
        env.update({key: str(value) for key, value in env_overrides.items()})
    stdout_handle = open(stdout_path, "w", encoding="utf-8") if stdout_path is not None else subprocess.DEVNULL
    stderr_handle = open(stderr_path, "w", encoding="utf-8") if stderr_path is not None else subprocess.DEVNULL
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    return proc


def stop_backend(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def safe_request_case(*, base_url: str, query: str, mode: str, top_k: int, timeout_s: int) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {"query": query, "mode": mode, "top_k": top_k}
    try:
        response = post_json(f"{base_url.rstrip('/')}/api/qa/answer", payload, timeout_s=timeout_s)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        data = response.get("data", {}) if isinstance(response.get("data"), dict) else {}
        return {"ok": True, "latency_ms": latency_ms, "data": data}
    except HTTPError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        return {"ok": False, "latency_ms": latency_ms, "error": f"http_{exc.code}"}
    except URLError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        return {"ok": False, "latency_ms": latency_ms, "error": f"url_error:{exc}"}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        return {"ok": False, "latency_ms": latency_ms, "error": f"{type(exc).__name__}:{exc}"}


def write_outputs(*, output_json: Path, output_md: Path, payload: dict[str, Any], markdown: str) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")


def render_simple_table(title: str, overview_rows: list[tuple[str, Any]], headers: list[str], rows: list[list[Any]]) -> str:
    lines = [f"# {title}", "", "## Overview", "", "| Field | Value |", "| --- | --- |"]
    for key, value in overview_rows:
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Results", "", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines).rstrip() + "\n"
