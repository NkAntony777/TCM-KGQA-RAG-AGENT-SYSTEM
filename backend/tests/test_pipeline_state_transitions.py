from __future__ import annotations

from pathlib import Path

from scripts.pipeline_console import state_transitions
from tests.test_temp_utils import make_test_dir


def test_mark_cancel_requested_updates_job_and_persists_state() -> None:
    run_dir = make_test_dir("pipeline_state_transitions")
    writes: list[tuple[Path, dict]] = []
    job = {"status": "running", "phase": "extracting", "run_dir": str(run_dir)}

    changed = state_transitions.mark_cancel_requested(
        current_job=job,
        write_state=lambda path, payload: writes.append((path, payload)),
        now_iso=lambda: "2026-05-08T12:00:00",
    )

    assert changed is True
    assert job["status"] == "cancelling"
    assert job["phase"] == "cancelling"
    assert job["cancel_requested_at"] == "2026-05-08T12:00:00"
    assert writes == [(run_dir / "state.json", dict(job))]


def test_mark_cancel_requested_is_noop_without_current_job() -> None:
    writes: list[tuple[Path, dict]] = []

    changed = state_transitions.mark_cancel_requested(
        current_job={},
        write_state=lambda path, payload: writes.append((path, payload)),
        now_iso=lambda: "2026-05-08T12:00:00",
    )

    assert changed is False
    assert writes == []


def test_mark_done_sets_completed_partial_and_cancelled_shapes() -> None:
    completed: dict = {}
    state_transitions.mark_done(
        state=completed,
        was_cancelled=False,
        pending_chunk_count=0,
        total_triples=8,
        completed_book_count=2,
        incomplete_books=[],
        elapsed_secs=12,
        now_iso=lambda: "2026-05-08T12:00:00",
    )
    assert completed["status"] == "completed"
    assert completed["phase"] == "done"
    assert completed["eta"] == "完成"
    assert completed["total_triples"] == 8

    partial: dict = {}
    state_transitions.mark_done(
        state=partial,
        was_cancelled=False,
        pending_chunk_count=3,
        total_triples=5,
        completed_book_count=1,
        incomplete_books=["伤寒论"],
        elapsed_secs=20,
        now_iso=lambda: "2026-05-08T12:01:00",
    )
    assert partial["status"] == "partial"
    assert partial["eta"] == "未完成"
    assert partial["books_incomplete"] == 1

    cancelled: dict = {}
    state_transitions.mark_done(
        state=cancelled,
        was_cancelled=True,
        pending_chunk_count=3,
        total_triples=5,
        completed_book_count=1,
        incomplete_books=["伤寒论"],
        elapsed_secs=20,
        now_iso=lambda: "2026-05-08T12:02:00",
    )
    assert cancelled["status"] == "cancelled"
    assert cancelled["eta"] == "已取消"


def test_mark_error_sets_terminal_error_state() -> None:
    state = {"status": "running", "phase": "extracting"}

    state_transitions.mark_error(
        state=state,
        error="boom",
        now_iso=lambda: "2026-05-08T12:00:00",
    )

    assert state == {
        "status": "error",
        "phase": "error",
        "error": "boom",
        "finished_at": "2026-05-08T12:00:00",
    }


def test_mark_started_normalizes_initial_running_phase() -> None:
    state = {"status": "queued", "phase": "created", "job_id": "job-1"}

    state_transitions.mark_started(state)

    assert state == {"status": "running", "phase": "scheduling", "job_id": "job-1"}


def test_phase_only_transitions_keep_other_state_fields() -> None:
    state = {"status": "completed", "total_triples": 3}

    state_transitions.mark_cleaning(state)
    assert state == {"status": "completed", "total_triples": 3, "phase": "cleaning"}
    state_transitions.mark_publishing(state)
    assert state["phase"] == "publishing"
    state_transitions.mark_finished(state)
    assert state["phase"] == "finished"


def test_mark_extracting_sets_queue_progress_without_changing_status() -> None:
    state = {"status": "running", "phase": "scheduling"}

    state_transitions.mark_extracting(
        state=state,
        chunks_total=10,
        chunks_completed=3,
        total_triples=7,
    )

    assert state == {
        "status": "running",
        "phase": "extracting",
        "chunks_total": 10,
        "chunks_completed": 3,
        "total_triples": 7,
    }


def test_progress_transitions_update_resume_books_and_local_cancel() -> None:
    state = {"status": "running", "phase": "extracting"}

    state_transitions.mark_resume_progress(state=state, skipped_chunks=4)
    state_transitions.mark_book_completed(state=state, completed_book_count=2)
    state_transitions.mark_total_triples(state=state, total_triples=12)
    state_transitions.mark_chunk_retries(state=state, retry_count=1)
    state_transitions.mark_provider_metrics(state=state, metrics={"provider": {"ok": 1}})
    state_transitions.mark_publish_status(state=state, publish_status={"json": {"status": "queued"}})
    assert state["resume_skipped_chunks"] == 4
    assert state["books_completed"] == 2
    assert state["total_triples"] == 12
    assert state["chunk_retries"] == 1
    assert state["provider_metrics"] == {"provider": {"ok": 1}}
    assert state["publish_status"] == {"json": {"status": "queued"}}

    state_transitions.mark_local_cancelling(state)
    assert state["status"] == "cancelling"
    assert state["phase"] == "cancelling"


def test_current_task_and_chunk_error_transitions() -> None:
    state = {"chunk_errors": 1}

    state_transitions.mark_current_task(
        state=state,
        book_name="伤寒论",
        chapter_name="卷上",
        chunk_index=3,
    )
    state_transitions.increment_chunk_errors(state)

    assert state["current_book"] == "伤寒论"
    assert state["current_chapter"] == "卷上"
    assert state["current_chunk_index"] == 3
    assert state["chunk_errors"] == 2

    state_transitions.mark_current_task(
        state=state,
        chapter_name="卷下",
        chunk_index=4,
    )
    assert state["current_book"] == "伤寒论"
    assert state["current_chapter"] == "卷下"
    assert state["current_chunk_index"] == 4
