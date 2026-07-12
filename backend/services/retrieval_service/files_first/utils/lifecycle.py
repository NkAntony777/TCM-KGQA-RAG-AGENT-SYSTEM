from __future__ import annotations

import gc
import time
from pathlib import Path


def unlink_with_retry(path: Path, *, attempts: int = 5, delay_secs: float = 0.1) -> None:
    last_error: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError as exc:
            last_error = exc
            gc.collect()
            time.sleep(delay_secs)
    if last_error is not None:
        raise last_error


def replace_file(target_path: Path, replacement_path: Path, *, attempts: int = 5, delay_secs: float = 0.1) -> None:
    last_error: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            replacement_path.replace(target_path)
            return
        except PermissionError as exc:
            last_error = exc
            gc.collect()
            time.sleep(delay_secs)
    if last_error is not None:
        raise last_error


def progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def print_build_progress(*, stage: str, done: int, total: int, started_at: float) -> None:
    elapsed = max(0.1, time.perf_counter() - started_at)
    rate = done / elapsed if done > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    print(
        f"[files-first:{stage}] {progress_bar(done, total)} "
        f"{done}/{total} ({done * 100.0 / max(1, total):.1f}%) "
        f"rate={rate:.1f}/s eta={format_seconds(eta)}",
        flush=True,
    )


def print_stage_banner(*, stage: str, detail: str) -> None:
    print(f"[files-first:{stage}] {detail}", flush=True)
