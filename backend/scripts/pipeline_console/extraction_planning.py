from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any


def task_key(task: Any) -> tuple[str, int]:
    return (str(task.book_name), int(task.chunk_index))


def schedule_book_tasks(
    pipeline: Any,
    *,
    selected_books: list[Path],
    chapter_excludes: list[str],
    max_chunks_per_book: int | None,
    skip_initial_chunks: int,
    chunk_strategy: str,
) -> tuple[list[tuple[Path, list[Any]]], int]:
    all_tasks_per_book: list[tuple[Path, list[Any]]] = []
    total_chunks_all = 0
    for book_path in selected_books:
        tasks = pipeline.schedule_book_chunks(
            book_path=book_path,
            chapter_excludes=chapter_excludes or None,
            max_chunks_per_book=max_chunks_per_book,
            skip_initial_chunks_per_book=skip_initial_chunks,
            chunk_strategy=chunk_strategy,
        )
        all_tasks_per_book.append((book_path, tasks))
        total_chunks_all += len(tasks)
    return all_tasks_per_book, total_chunks_all


def scheduled_chunk_keys(all_tasks_per_book: list[tuple[Path, list[Any]]]) -> set[tuple[str, int]]:
    return {task_key(task) for _, tasks in all_tasks_per_book for task in tasks}


def restrict_completed_to_scheduled(
    completed_chunk_keys: set[tuple[str, int]],
    all_tasks_per_book: list[tuple[Path, list[Any]]],
) -> set[tuple[str, int]]:
    scheduled = scheduled_chunk_keys(all_tasks_per_book)
    return {key for key in completed_chunk_keys if key in scheduled}


def pending_tasks_by_book(
    all_tasks_per_book: list[tuple[Path, list[Any]]],
    *,
    completed_chunk_keys: set[tuple[str, int]],
) -> list[tuple[Path, list[Any]]]:
    return [
        (book_path, [task for task in scheduled_tasks if task_key(task) not in completed_chunk_keys])
        for book_path, scheduled_tasks in all_tasks_per_book
    ]


def interleave_tasks(pending_tasks_per_book: list[tuple[Path, list[Any]]]) -> list[Any]:
    task_queues = [deque(tasks) for _, tasks in pending_tasks_per_book]
    interleaved_tasks: list[Any] = []
    while True:
        appended = False
        for queue in task_queues:
            if queue:
                interleaved_tasks.append(queue.popleft())
                appended = True
        if not appended:
            break
    return interleaved_tasks


def pending_chunk_count(
    all_tasks_per_book: list[tuple[Path, list[Any]]],
    *,
    completed_chunk_keys: set[tuple[str, int]],
) -> int:
    return sum(
        1
        for _, tasks in all_tasks_per_book
        for task in tasks
        if task_key(task) not in completed_chunk_keys
    )


def collect_success_rows(
    all_tasks_per_book: list[tuple[Path, list[Any]]],
    *,
    results: dict[tuple[str, int], dict[str, Any]],
) -> list[Any]:
    rows: list[Any] = []
    for _, tasks in all_tasks_per_book:
        for task in tasks:
            result = results.get(task_key(task), {"task": task, "payload": {"triples": []}, "error": "missing", "rows": []})
            if result.get("error") is not None:
                continue
            rows.extend(result.get("rows") or [])
    return rows
