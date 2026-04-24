from __future__ import annotations

from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from typing import Any, Callable


LogFn = Callable[[str, str], None]
NoteCancellingFn = Callable[[], None]
PersistAttemptFn = Callable[..., tuple[list[Any], str | None]]
MetricsSnapshotFn = Callable[[], dict[str, Any]]
UpdateCurrentJobFn = Callable[[], None]


def run_retry_batch(
    failed_items: list[dict[str, Any]],
    retry_count: int,
    *,
    pipeline: Any,
    dry_run: bool,
    retry_parallel_workers: int,
    job_cancelled: Any,
    state: dict[str, Any],
    note_cancelling: NoteCancellingFn,
    persist_chunk_attempt: PersistAttemptFn,
    metrics_snapshot: MetricsSnapshotFn,
    update_current_job: UpdateCurrentJobFn,
    log: LogFn,
) -> None:
    if retry_parallel_workers <= 1 or len(failed_items) <= 1:
        for result in failed_items:
            if job_cancelled.is_set():
                note_cancelling()
                break
            task = result["task"]
            result["_retried"] = result.get("_retried", 0) + 1
            state["current_chapter"] = task.chapter_name
            state["current_chunk_index"] = task.chunk_index
            update_current_job()
            try:
                payload = pipeline.extract_chunk_payload(task, dry_run=dry_run)
                result["payload"] = payload
                result["error"] = None
                log("ok", f"  chunk {task.chunk_index} 重试成功 ✓")
            except Exception as exc:
                payload = {"triples": []}
                result["payload"] = payload
                result["error"] = str(exc)
                log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
            persist_chunk_attempt(
                result,
                task=task,
                payload=payload,
                error=result["error"],
                attempt=result.get("_retried", 0),
            )
        return

    worker_count = min(retry_parallel_workers, len(failed_items))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {}
        for result in failed_items:
            result["_retried"] = result.get("_retried", 0) + 1
            future_map[executor.submit(pipeline.extract_chunk_payload, result["task"], dry_run)] = result
        log("info", f"  [retry] 第 {retry_count} 轮提交 {len(failed_items)} 个 chunk，retry_parallel_workers={worker_count}")

        for future in as_completed(future_map):
            if job_cancelled.is_set():
                note_cancelling()
                executor.shutdown(wait=False, cancel_futures=True)
                break
            result = future_map[future]
            task = result["task"]
            state["current_chapter"] = task.chapter_name
            state["current_chunk_index"] = task.chunk_index
            try:
                payload = future.result()
                result["payload"] = payload
                result["error"] = None
                log("ok", f"  chunk {task.chunk_index} 重试成功 ✓")
            except Exception as exc:
                payload = {"triples": []}
                result["payload"] = payload
                result["error"] = str(exc)
                log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
            rows, _ = persist_chunk_attempt(
                result,
                task=task,
                payload=payload,
                error=result["error"],
                attempt=result.get("_retried", 0),
            )
            metrics = metrics_snapshot()
            log(
                "info",
                f"  [retry] progress {metrics['session_chunks_done']} session_done | chunk={task.chunk_index} | "
                f"triples={len(rows)} | total_triples={metrics['total_triples']} | error={result['error'] or '-'}",
            )


def run_serial_initial_chunks(
    interleaved_tasks: list[Any],
    *,
    pipeline: Any,
    dry_run: bool,
    job_cancelled: Any,
    state: dict[str, Any],
    results: dict[tuple[str, int], dict[str, Any]],
    result_key: Callable[[Any], tuple[str, int]],
    note_cancelling: NoteCancellingFn,
    persist_chunk_attempt: PersistAttemptFn,
    update_current_job: UpdateCurrentJobFn,
    log: LogFn,
) -> int:
    chunk_errors = 0
    for task in interleaved_tasks:
        if job_cancelled.is_set():
            note_cancelling()
            break
        state["current_book"] = task.book_name
        state["current_chapter"] = task.chapter_name
        state["current_chunk_index"] = task.chunk_index
        update_current_job()
        log("info", f"  -> 处理 {task.book_name} chunk {task.chunk_index}/{len(interleaved_tasks)}")
        try:
            payload = pipeline.extract_chunk_payload(task, dry_run=dry_run)
            error = None
            log("ok", f"  chunk {task.chunk_index}/{len(interleaved_tasks)} ✓ {task.book_name}")
        except Exception as exc:
            payload = {"triples": []}
            error = str(exc)
            chunk_errors += 1
            state["chunk_errors"] = int(state.get("chunk_errors", 0) or 0) + 1
            log("error", f"  chunk {task.chunk_index} 失败: {str(exc)[:80]}")
        result = {
            "task": task,
            "payload": payload,
            "error": error,
            "rows": [],
            "_retried": 0,
            "_written": False,
        }
        rows, effective_error = persist_chunk_attempt(
            result,
            task=task,
            payload=payload,
            error=error,
            attempt=0,
        )
        results[result_key(task)] = result
        if effective_error is not None and error is None:
            log("warn", f"  chunk {task.chunk_index} low_yield | triples={len(rows)} | queued_for_retry")
    return chunk_errors


def run_parallel_initial_chunks(
    interleaved_tasks: list[Any],
    *,
    pipeline: Any,
    job_cancelled: Any,
    state: dict[str, Any],
    results: dict[tuple[str, int], dict[str, Any]],
    result_key: Callable[[Any], tuple[str, int]],
    note_cancelling: NoteCancellingFn,
    persist_chunk_attempt: PersistAttemptFn,
    metrics_snapshot: MetricsSnapshotFn,
    log: LogFn,
) -> int:
    chunk_errors = 0
    with ThreadPoolExecutor(max_workers=pipeline.config.parallel_workers) as executor:
        future_map: dict[Any, Any] = {}
        pending_queue: deque[Any] = deque(interleaved_tasks)
        future_index = 0

        def submit_available_tasks() -> None:
            while (
                pending_queue
                and len(future_map) < pipeline.config.parallel_workers
                and not job_cancelled.is_set()
            ):
                task = pending_queue.popleft()
                future_map[executor.submit(pipeline.extract_chunk_payload, task, False)] = task

        submit_available_tasks()
        log(
            "info",
            f"  [全局并行] 已启动 {len(future_map)} 个 worker，"
            f"队列总量={len(interleaved_tasks)} parallel_workers={pipeline.config.parallel_workers}",
        )
        while future_map:
            if job_cancelled.is_set():
                note_cancelling()
                executor.shutdown(wait=False, cancel_futures=True)
                break
            done, _ = wait(tuple(future_map), return_when=FIRST_COMPLETED)
            for future in done:
                future_index += 1
                task = future_map.pop(future)
                state["current_book"] = task.book_name
                state["current_chapter"] = task.chapter_name
                state["current_chunk_index"] = task.chunk_index
                try:
                    payload = future.result()
                    error = None
                except Exception as exc:
                    payload = {"triples": []}
                    error = str(exc)
                    chunk_errors += 1
                    state["chunk_errors"] = int(state.get("chunk_errors", 0) or 0) + 1
                    log("error", f"  chunk {task.chunk_index} 失败: {str(exc)[:80]}")
                result = {
                    "task": task,
                    "payload": payload,
                    "error": error,
                    "rows": [],
                    "_retried": 0,
                    "_written": False,
                }
                rows, effective_error = persist_chunk_attempt(
                    result,
                    task=task,
                    payload=payload,
                    error=error,
                    attempt=0,
                )
                results[result_key(task)] = result
                if error is None and effective_error is not None:
                    log("warn", f"  chunk {task.chunk_index} low_yield | triples={len(rows)} | queued_for_retry")
                if error is not None:
                    log("warn", f"  chunk {task.chunk_index} 无三元组 | error={error} | is_dict={isinstance(payload,dict)}")
                metrics = metrics_snapshot()
                log(
                    "info",
                    f"  [parallel] progress {future_index}/{len(interleaved_tasks)} | "
                    f"book={task.book_name} | chunk={task.chunk_index} | triples={len(rows)} | "
                    f"total_triples={metrics['total_triples']} | error={effective_error or '-'}",
                )
            submit_available_tasks()
    return chunk_errors
