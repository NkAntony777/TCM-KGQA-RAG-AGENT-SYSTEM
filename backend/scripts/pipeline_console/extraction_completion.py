from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable


NowFn = Callable[[], str]
SyncFn = Callable[[], None]
LogFn = Callable[[str, str], None]
RefreshFn = Callable[..., None]
DescribeExceptionFn = Callable[[Exception], str]
EnqueuePublishFn = Callable[[str], tuple[bool, dict[str, Any]]]


def apply_done_state(
    *,
    state: dict[str, Any],
    start_ts: float,
    was_cancelled: bool,
    pending_chunk_count: int,
    total_triples: int,
    completed_book_count: int,
    incomplete_books: list[str],
    now_iso: NowFn,
    refresh_provider_monitor: RefreshFn,
    sync_state: SyncFn,
) -> None:
    state["phase"] = "done"
    if was_cancelled:
        state["status"] = "cancelled"
    elif pending_chunk_count > 0:
        state["status"] = "partial"
    else:
        state["status"] = "completed"
    state["finished_at"] = now_iso()
    state["elapsed_secs"] = int(time.time() - start_ts)
    state["eta"] = "已取消" if was_cancelled else ("未完成" if pending_chunk_count > 0 else "完成")
    state["total_triples"] = total_triples
    state["books_completed"] = completed_book_count
    state["pending_chunks"] = pending_chunk_count
    state["books_incomplete"] = len(incomplete_books)
    state["incomplete_books"] = incomplete_books
    refresh_provider_monitor(force_log=True)
    sync_state()


def log_done_summary(
    *,
    was_cancelled: bool,
    pending_chunk_count: int,
    total_triples: int,
    chunk_errors: int,
    log: LogFn,
) -> None:
    if was_cancelled:
        log("warn", f"任务已取消，已保留当前进度：{total_triples} 条三元组，错误 {chunk_errors} 个")
    elif pending_chunk_count > 0:
        log("warn", f"提取结束，但仍有 {pending_chunk_count} 个 chunk 未完成，run 标记为 partial")
    else:
        log("info", f"提取完成，共 {total_triples} 条三元组，错误 {chunk_errors} 个")


def maybe_auto_clean(
    *,
    auto_clean: bool,
    state: dict[str, Any],
    triples_jsonl: Path,
    total_triples: int,
    pipeline: Any,
    run_dir: Path,
    sync_state: SyncFn,
    log: LogFn,
) -> None:
    if not auto_clean or state.get("status") != "completed":
        return
    if not triples_jsonl.exists() or triples_jsonl.stat().st_size == 0:
        log("warn", f"跳过清洗: {triples_jsonl} 为空或不存在（{total_triples} 条三元组）")
        return
    state["phase"] = "cleaning"
    sync_state()
    log("info", "开始自动清洗...")
    report = pipeline.clean_run_dir(run_dir)
    log("info", f"清洗完成: 保留 {report['kept_total']} 条，丢弃 {report['dropped_total']} 条")


def maybe_auto_publish(
    *,
    auto_publish: bool,
    state: dict[str, Any],
    run_dir: Path,
    enqueue_publish: EnqueuePublishFn,
    sync_state: SyncFn,
    log: LogFn,
) -> None:
    if not auto_publish or state.get("status") != "completed":
        return
    state["phase"] = "publishing"
    sync_state()
    log("info", "开始自动发布到图谱队列...")
    enqueued, publish_status = enqueue_publish(run_dir.name)
    state["publish_status"] = publish_status
    sync_state()
    if enqueued:
        log("info", f"已加入自动发布队列: {run_dir.name}")
        return
    json_status = publish_status.get("json", {}) if isinstance(publish_status, dict) else {}
    log("info", f"自动发布未重复入队，当前状态: {json_status.get('status', 'unknown')}")


def mark_finished(
    *,
    state: dict[str, Any],
    refresh_provider_monitor: RefreshFn,
    sync_state: SyncFn,
) -> None:
    state["phase"] = "finished"
    refresh_provider_monitor(force_log=True)
    sync_state()


def mark_error(
    *,
    state: dict[str, Any],
    exc: Exception,
    describe_exception: DescribeExceptionFn,
    now_iso: NowFn,
    refresh_provider_monitor: RefreshFn,
    sync_state: SyncFn,
) -> None:
    state["status"] = "error"
    state["phase"] = "error"
    state["error"] = describe_exception(exc)
    state["finished_at"] = now_iso()
    refresh_provider_monitor(force_log=True)
    sync_state()
