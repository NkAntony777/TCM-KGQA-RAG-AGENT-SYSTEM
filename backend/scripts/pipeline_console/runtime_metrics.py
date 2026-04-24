from __future__ import annotations

import time
from datetime import timedelta
from typing import Any


def fmt_eta(remaining_secs: float) -> str:
    if remaining_secs <= 0:
        return "完成"
    td = timedelta(seconds=int(remaining_secs))
    h, rem = divmod(td.seconds, 3600)
    m, s = divmod(rem, 60)
    if td.days > 0:
        return f"{td.days}天{h}小时{m}分"
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def update_runtime_metrics(
    state: dict[str, Any],
    *,
    start_ts: float,
    session_chunks_done: int,
    total_chunks_done: int,
    total_chunks_all: int,
    now_ts: float | None = None,
) -> None:
    elapsed = (time.time() if now_ts is None else now_ts) - start_ts
    state["elapsed_secs"] = int(elapsed)
    state["chunks_completed"] = total_chunks_done
    if session_chunks_done <= 0 or total_chunks_all <= 0:
        state["speed_chunks_per_min"] = 0.0
        state["eta"] = ""
        return
    rate = session_chunks_done / max(elapsed, 1)
    remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
    state["eta"] = fmt_eta(remaining)
    state["speed_chunks_per_min"] = round(rate * 60, 1)


def derive_retry_parallel_workers(parallel_workers: Any) -> int:
    try:
        workers = int(parallel_workers)
    except (TypeError, ValueError):
        workers = 1
    workers = max(1, workers)
    return max(1, workers // 2)
