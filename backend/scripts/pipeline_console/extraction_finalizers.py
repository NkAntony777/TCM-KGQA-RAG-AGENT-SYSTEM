from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from scripts.pipeline_console import extraction_planning


AppendCheckpointFn = Callable[..., None]
LogFn = Callable[[str, str], None]
IsLowYieldFn = Callable[[str | None], bool]
ClearBooksFn = Callable[[list[str]], dict[str, list[str]]]


def finalize_exhausted_low_yield_chunks(
    *,
    results: dict[tuple[str, int], dict[str, Any]],
    completed_chunk_keys: set[tuple[str, int]],
    max_chunk_retries: int,
    checkpoint_path: Path,
    resume_mode: bool,
    append_checkpoint: AppendCheckpointFn,
    is_low_yield_retry_error: IsLowYieldFn,
    log: LogFn,
) -> int:
    finalized = 0
    for result in results.values():
        error = result.get("error")
        if not is_low_yield_retry_error(error):
            continue
        if int(result.get("_retried", 0) or 0) < max_chunk_retries:
            continue

        task = result["task"]
        drop_error = f"dropped_after_low_yield_retries: {error}"
        result["error"] = None
        result["rows"] = []
        result["_written"] = True
        completed_chunk_keys.add(extraction_planning.task_key(task))
        append_checkpoint(
            checkpoint_path,
            task=task,
            error=drop_error,
            payload=result.get("payload") or {"triples": []},
            attempt=int(result.get("_retried", 0) or 0),
            resumed=resume_mode,
            triples_count=0,
            success_override=True,
        )
        log("info", f"  chunk {task.chunk_index} 低产出重试耗尽，按空结果完成 | triples=0")
        finalized += 1
    return finalized


def finalize_exhausted_failed_chunks(
    *,
    results: dict[tuple[str, int], dict[str, Any]],
    completed_chunk_keys: set[tuple[str, int]],
    max_chunk_retries: int,
    checkpoint_path: Path,
    resume_mode: bool,
    append_checkpoint: AppendCheckpointFn,
    is_low_yield_retry_error: IsLowYieldFn,
    log: LogFn,
) -> int:
    finalized = 0
    for result in results.values():
        error = str(result.get("error") or "").strip()
        if not error:
            continue
        if is_low_yield_retry_error(error):
            continue
        if int(result.get("_retried", 0) or 0) < max_chunk_retries:
            continue

        task = result["task"]
        payload = result.get("payload") or {"triples": []}
        rows = result.get("rows") or []
        drop_error = f"dropped_after_retries: {error}"
        result["error"] = None
        result["rows"] = []
        result["_written"] = True
        completed_chunk_keys.add(extraction_planning.task_key(task))
        append_checkpoint(
            checkpoint_path,
            task=task,
            error=drop_error,
            payload=payload,
            attempt=int(result.get("_retried", 0) or 0),
            resumed=resume_mode,
            triples_count=len(rows),
            success_override=True,
        )
        log("warn", f"  chunk {task.chunk_index} 重试耗尽，已丢弃并按完成处理 | error={error[:80]}")
        finalized += 1
    return finalized


def finalize_any_remaining_unresolved_chunks(
    *,
    all_tasks_per_book: list[tuple[Path, list[Any]]],
    results: dict[tuple[str, int], dict[str, Any]],
    completed_chunk_keys: set[tuple[str, int]],
    checkpoint_path: Path,
    resume_mode: bool,
    append_checkpoint: AppendCheckpointFn,
    log: LogFn,
) -> int:
    finalized = 0
    for _, tasks in all_tasks_per_book:
        for task in tasks:
            key = extraction_planning.task_key(task)
            if key in completed_chunk_keys:
                continue
            result = results.get(key)
            payload = (result or {}).get("payload") or {"triples": []}
            error = str((result or {}).get("error") or "unresolved_after_retries").strip()
            attempt = int((result or {}).get("_retried", 0) or 0)
            if result is not None:
                result["error"] = None
                result["rows"] = []
                result["_written"] = True
            else:
                results[key] = {
                    "task": task,
                    "payload": payload,
                    "error": None,
                    "rows": [],
                    "_retried": attempt,
                    "_written": True,
                }
            completed_chunk_keys.add(key)
            append_checkpoint(
                checkpoint_path,
                task=task,
                error=f"dropped_after_retries: {error}",
                payload=payload,
                attempt=attempt,
                resumed=resume_mode,
                triples_count=0,
                success_override=True,
            )
            log("warn", f"  chunk {task.chunk_index} 收尾兜底丢弃并按完成处理 | error={error[:80]}")
            finalized += 1
    return finalized


def summarize_book_completion(
    *,
    all_tasks_per_book: list[tuple[Path, list[Any]]],
    completed_book_stems: set[str],
    completed_chunk_keys: set[tuple[str, int]],
    state: dict[str, Any],
    total_triples: int,
    clear_books_force_unprocessed: ClearBooksFn,
    log: LogFn,
) -> list[str]:
    incomplete_books: list[str] = []
    for book_path, scheduled_tasks in all_tasks_per_book:
        book_all_completed = bool(scheduled_tasks) and all(
            extraction_planning.task_key(task) in completed_chunk_keys
            for task in scheduled_tasks
        )
        if book_all_completed:
            if book_path.stem not in completed_book_stems:
                log("info", f"  完成 {book_path.stem}，累计三元组: {total_triples}")
            clear_books_force_unprocessed([book_path.stem])
            completed_book_stems.add(book_path.stem)
            state["books_completed"] = len(completed_book_stems)
        else:
            pending_for_book = sum(
                1
                for task in scheduled_tasks
                if extraction_planning.task_key(task) not in completed_chunk_keys
            )
            if pending_for_book > 0:
                incomplete_books.append(book_path.stem)
                log("warn", f"  {book_path.stem} 仍有 {pending_for_book} 个 chunk 未完成，当前 run 保留为未完成状态")
    return incomplete_books
