from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, AsyncIterator


NowFn = Callable[[], str]
WriteStateFn = Callable[[Path, dict[str, Any]], None]
JobAliveFn = Callable[[], bool]
LogFileProvider = Callable[[], Path | None]
WriteTextFn = Callable[[Path, str], None]


def default_now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_job_log(
    *,
    lock: Any,
    job_log: list[dict[str, Any]],
    log_file: Path | None,
    level: str,
    msg: str,
    extra: dict[str, Any] | None = None,
    now_iso: NowFn = default_now_iso,
) -> None:
    entry = {"ts": now_iso(), "level": level, "msg": msg, **(extra or {})}
    with lock:
        job_log.append(entry)
        if log_file is not None:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cleanup_job_log_file(
    *,
    lock: Any,
    log_file_path: Path | None,
) -> tuple[None, None]:
    with lock:
        try:
            if log_file_path and log_file_path.exists():
                log_file_path.unlink()
        except Exception:
            pass
    return None, None


def initialize_job_context(
    *,
    lock: Any,
    current_job: dict[str, Any],
    job_log: list[dict[str, Any]],
    cancel_event: Any,
    output_dir: Path,
    job_id: str,
    write_text: WriteTextFn,
) -> tuple[Path, Path]:
    log_file_path = output_dir / f"current_job_{job_id}.log"
    with lock:
        current_job.clear()
        job_log.clear()
        cancel_event.clear()
        write_text(log_file_path, "")
    return log_file_path, log_file_path


def mark_cancel_requested(
    *,
    lock: Any,
    current_job: dict[str, Any],
    write_state: WriteStateFn,
    now_iso: NowFn = default_now_iso,
) -> bool:
    run_dir = None
    state_snapshot: dict[str, Any] | None = None
    with lock:
        if not current_job:
            return False
        current_job["status"] = "cancelling"
        current_job["phase"] = "cancelling"
        current_job["cancel_requested_at"] = now_iso()
        run_dir = current_job.get("run_dir")
        state_snapshot = dict(current_job)
    if run_dir and state_snapshot:
        state_path = Path(str(run_dir)) / "state.json"
        try:
            write_state(state_path, state_snapshot)
        except Exception:
            pass
    return True


def job_status_snapshot(*, lock: Any, current_job: dict[str, Any]) -> dict[str, Any]:
    with lock:
        return dict(current_job)


def sync_current_job_state(
    *,
    lock: Any,
    current_job: dict[str, Any],
    state_path: Path,
    state: dict[str, Any],
    write_state: WriteStateFn,
) -> None:
    with lock:
        current_job.update(state)
    write_state(state_path, state)


def job_log_slice(
    *,
    lock: Any,
    job_log: list[dict[str, Any]],
    since: int = 0,
) -> dict[str, Any]:
    with lock:
        entries = job_log[since:]
        total = len(job_log)
    return {"entries": entries, "total": total}


def _read_jsonl_log(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line.lstrip("\ufeff")))
    return rows


async def iter_job_stream_events(
    *,
    lock: Any,
    current_job: dict[str, Any],
    job_log: list[dict[str, Any]],
    get_log_file: LogFileProvider,
    is_job_thread_alive: JobAliveFn,
    sleep_seconds: float = 1.0,
) -> AsyncIterator[str]:
    sent_log_idx = 0
    replayed_from_disk = False
    while True:
        disk_logs: list[dict[str, Any]] = []
        with lock:
            state = dict(current_job)
            log_file = get_log_file()
            if not replayed_from_disk and log_file is not None and log_file.exists():
                try:
                    disk_rows = _read_jsonl_log(log_file)
                    if disk_rows and len(disk_rows) > sent_log_idx:
                        disk_logs = disk_rows[sent_log_idx:]
                        sent_log_idx = len(disk_rows)
                except Exception:
                    pass
                replayed_from_disk = True
            memory_logs = job_log[sent_log_idx:]
            sent_log_idx += len(memory_logs)
        payload = json.dumps({"state": state, "logs": [*disk_logs, *memory_logs]}, ensure_ascii=False)
        yield f"data: {payload}\n\n"
        if (
            state.get("status") in ("completed", "error", "cancelled")
            and state.get("phase") == "finished"
            and not is_job_thread_alive()
        ):
            break
        await asyncio.sleep(sleep_seconds)
