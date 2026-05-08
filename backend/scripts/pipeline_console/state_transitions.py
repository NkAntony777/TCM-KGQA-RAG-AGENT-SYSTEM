from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

NowFn = Callable[[], str]
WriteStateFn = Callable[[Path, dict[str, Any]], None]


def mark_started(state: dict[str, Any]) -> None:
    state["status"] = "running"
    state["phase"] = "scheduling"


def mark_local_cancelling(state: dict[str, Any]) -> None:
    state["status"] = "cancelling"
    state["phase"] = "cancelling"


def mark_extracting(
    *,
    state: dict[str, Any],
    chunks_total: int,
    chunks_completed: int,
    total_triples: int,
) -> None:
    state["chunks_total"] = chunks_total
    state["chunks_completed"] = chunks_completed
    state["total_triples"] = total_triples
    state["phase"] = "extracting"


def mark_resume_progress(*, state: dict[str, Any], skipped_chunks: int) -> None:
    state["resume_skipped_chunks"] = skipped_chunks


def mark_book_completed(*, state: dict[str, Any], completed_book_count: int) -> None:
    state["books_completed"] = completed_book_count


def mark_total_triples(*, state: dict[str, Any], total_triples: int) -> None:
    state["total_triples"] = total_triples


def mark_chunk_retries(*, state: dict[str, Any], retry_count: int) -> None:
    state["chunk_retries"] = retry_count


def mark_provider_metrics(*, state: dict[str, Any], metrics: Any) -> None:
    state["provider_metrics"] = metrics


def mark_publish_status(*, state: dict[str, Any], publish_status: dict[str, Any]) -> None:
    state["publish_status"] = publish_status


def mark_current_task(
    *,
    state: dict[str, Any],
    book_name: str | None = None,
    chapter_name: str,
    chunk_index: int,
) -> None:
    if book_name is not None:
        state["current_book"] = book_name
    state["current_chapter"] = chapter_name
    state["current_chunk_index"] = chunk_index


def increment_chunk_errors(state: dict[str, Any]) -> None:
    state["chunk_errors"] = int(state.get("chunk_errors", 0) or 0) + 1


def mark_cancel_requested(
    *,
    current_job: dict[str, Any],
    write_state: WriteStateFn,
    now_iso: NowFn,
) -> bool:
    if not current_job:
        return False
    current_job["status"] = "cancelling"
    current_job["phase"] = "cancelling"
    current_job["cancel_requested_at"] = now_iso()
    run_dir = current_job.get("run_dir")
    if run_dir:
        try:
            write_state(Path(str(run_dir)) / "state.json", dict(current_job))
        except Exception:
            pass
    return True


def mark_done(
    *,
    state: dict[str, Any],
    was_cancelled: bool,
    pending_chunk_count: int,
    total_triples: int,
    completed_book_count: int,
    incomplete_books: list[str],
    elapsed_secs: int,
    now_iso: NowFn,
) -> None:
    state["phase"] = "done"
    if was_cancelled:
        state["status"] = "cancelled"
    elif pending_chunk_count > 0:
        state["status"] = "partial"
    else:
        state["status"] = "completed"
    state["finished_at"] = now_iso()
    state["elapsed_secs"] = elapsed_secs
    state["eta"] = "已取消" if was_cancelled else ("未完成" if pending_chunk_count > 0 else "完成")
    state["total_triples"] = total_triples
    state["books_completed"] = completed_book_count
    state["pending_chunks"] = pending_chunk_count
    state["books_incomplete"] = len(incomplete_books)
    state["incomplete_books"] = incomplete_books


def mark_cleaning(state: dict[str, Any]) -> None:
    state["phase"] = "cleaning"


def mark_publishing(state: dict[str, Any]) -> None:
    state["phase"] = "publishing"


def mark_finished(state: dict[str, Any]) -> None:
    state["phase"] = "finished"


def mark_error(
    *,
    state: dict[str, Any],
    error: str,
    now_iso: NowFn,
) -> None:
    state["status"] = "error"
    state["phase"] = "error"
    state["error"] = error
    state["finished_at"] = now_iso()
