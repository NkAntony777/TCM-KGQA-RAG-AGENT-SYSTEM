from __future__ import annotations

import time
import traceback
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from services.triple_pipeline_models import TripleRecord


@dataclass
class ExtractionJobContext:
    current_job: dict[str, Any]
    run_lock: Any
    job_cancelled: Any
    build_pipeline: Any
    load_completed_chunk_keys: Any
    count_jsonl_rows: Any
    derive_retry_parallel_workers: Any
    now_iso: Any
    provider_to_dict: Any
    write_state: Any
    log: Any
    load_existing_triple_records: Any
    clear_books_force_unprocessed: Any
    evaluate_chunk_attempt: Any
    build_raw_chunk_record: Any
    append_checkpoint: Any
    update_runtime_metrics: Any
    is_low_yield_retry_error: Any
    enqueue_publish_task: Any
    cleanup_job_log_file: Any
    describe_exception: Any
    job_state: Any
    extraction_state: Any
    extraction_planning: Any
    chunk_execution: Any
    extraction_finalizers: Any
    extraction_completion: Any


def _context_from_pipeline_server() -> ExtractionJobContext:
    from scripts import pipeline_server as server

    return ExtractionJobContext(
        current_job=server._current_job,
        run_lock=server._run_lock,
        job_cancelled=server._job_cancelled,
        build_pipeline=server._build_pipeline,
        load_completed_chunk_keys=server._load_completed_chunk_keys,
        count_jsonl_rows=server._count_jsonl_rows,
        derive_retry_parallel_workers=server._derive_retry_parallel_workers,
        now_iso=server._now_iso,
        provider_to_dict=server._provider_to_dict,
        write_state=server._write_state,
        log=server._log,
        load_existing_triple_records=server._load_existing_triple_records,
        clear_books_force_unprocessed=server._clear_books_force_unprocessed,
        evaluate_chunk_attempt=server._evaluate_chunk_attempt,
        build_raw_chunk_record=server._build_raw_chunk_record,
        append_checkpoint=server._append_checkpoint,
        update_runtime_metrics=server._update_runtime_metrics,
        is_low_yield_retry_error=server._is_low_yield_retry_error,
        enqueue_publish_task=server._enqueue_publish_task,
        cleanup_job_log_file=server._cleanup_job_log_file,
        describe_exception=server._describe_exception,
        job_state=server.job_state,
        extraction_state=server.extraction_state,
        extraction_planning=server.extraction_planning,
        chunk_execution=server.chunk_execution,
        extraction_finalizers=server.extraction_finalizers,
        extraction_completion=server.extraction_completion,
    )


def run_extraction_job(
    *,
    job_id: str,
    selected_books: list[Path],
    label: str,
    dry_run: bool,
    cfg_override: dict[str, Any],
    chapter_excludes: list[str],
    max_chunks_per_book: int | None,
    skip_initial_chunks: int,
    chunk_strategy: str,
    auto_clean: bool,
    auto_publish: bool,
    max_chunk_retries: int = 2,
    resume_run_dir: Path | None = None,
    cleanup_job_log_file: bool = True,
    context: ExtractionJobContext | None = None,
) -> None:
    """在独立线程中运行完整的提取→清洗→发布流程，实时更新 _current_job。"""

    context = context or _context_from_pipeline_server()

    _current_job = context.current_job
    _run_lock = context.run_lock
    _job_cancelled = context.job_cancelled
    _build_pipeline = context.build_pipeline
    _load_completed_chunk_keys = context.load_completed_chunk_keys
    _count_jsonl_rows = context.count_jsonl_rows
    _derive_retry_parallel_workers = context.derive_retry_parallel_workers
    _now_iso = context.now_iso
    _provider_to_dict = context.provider_to_dict
    _write_state = context.write_state
    _log = context.log
    _load_existing_triple_records = context.load_existing_triple_records
    _clear_books_force_unprocessed = context.clear_books_force_unprocessed
    _evaluate_chunk_attempt = context.evaluate_chunk_attempt
    _build_raw_chunk_record = context.build_raw_chunk_record
    _append_checkpoint = context.append_checkpoint
    _update_runtime_metrics = context.update_runtime_metrics
    _is_low_yield_retry_error = context.is_low_yield_retry_error
    _enqueue_publish_task = context.enqueue_publish_task
    _cleanup_job_log_file = context.cleanup_job_log_file
    _describe_exception = context.describe_exception
    job_state = context.job_state
    extraction_state = context.extraction_state
    extraction_planning = context.extraction_planning
    chunk_execution = context.chunk_execution
    extraction_finalizers = context.extraction_finalizers
    extraction_completion = context.extraction_completion
    pipeline = _build_pipeline(cfg_override)
    resume_mode = resume_run_dir is not None
    run_dir = resume_run_dir or pipeline.create_run_dir(label=label)
    run_dir.mkdir(parents=True, exist_ok=True)

    start_ts = time.time()
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    triples_jsonl = run_dir / "triples.normalized.jsonl"
    raw_jsonl = run_dir / "triples.raw.jsonl"
    state_path = run_dir / "state.json"
    completed_chunk_keys = _load_completed_chunk_keys(run_dir) if resume_mode else set()
    total_chunks_done = len(completed_chunk_keys)
    session_chunks_done = 0
    total_chunks_all = 0
    total_triples = _count_jsonl_rows(triples_jsonl)
    chunk_errors = 0
    retry_parallel_workers = _derive_retry_parallel_workers(pipeline.config.parallel_workers)
    completed_book_stems: set[str] = set()
    incomplete_books: list[str] = []

    state = extraction_state.build_initial_state(
        job_id=job_id,
        selected_books=selected_books,
        run_dir=run_dir,
        dry_run=dry_run,
        pipeline=pipeline,
        resume_mode=resume_mode,
        completed_chunk_count=len(completed_chunk_keys),
        retry_parallel_workers=retry_parallel_workers,
        now_iso=_now_iso,
        provider_to_dict=_provider_to_dict,
    )

    def refresh_provider_monitor(*, force_log: bool = False) -> None:
        metrics = pipeline.get_provider_metrics()
        state["provider_metrics"] = metrics
        if force_log:
            return

    def sync_state() -> None:
        job_state.sync_current_job_state(
            lock=_run_lock,
            current_job=_current_job,
            state_path=state_path,
            state=state,
            write_state=_write_state,
        )

    def update_current_job_only() -> None:
        with _run_lock:
            _current_job.update(state)

    def metrics_snapshot() -> dict[str, Any]:
        return {
            "session_chunks_done": session_chunks_done,
            "total_triples": total_triples,
        }

    sync_state()
    refresh_provider_monitor(force_log=True)

    _log("info", f"任务启动 job_id={job_id}，共 {len(selected_books)} 本书")

    # 新任务写 manifest；续跑必须保留原 run 的 manifest，避免固定配置被污染
    if not resume_mode:
        pipeline.save_manifest(
            run_dir,
            extraction_state.build_manifest_payload(
                job_id=job_id,
                selected_books=selected_books,
                pipeline=pipeline,
                dry_run=dry_run,
                resume_run_dir=resume_run_dir,
                chapter_excludes=chapter_excludes,
                skip_initial_chunks=skip_initial_chunks,
                chunk_strategy=chunk_strategy,
                max_chunks_per_book=max_chunks_per_book,
                max_chunk_retries=max_chunk_retries,
                now_iso=lambda: datetime.now().isoformat(),
                provider_to_dict=_provider_to_dict,
            ),
        )
    all_rows = _load_existing_triple_records(triples_jsonl) if resume_mode else []
    cancel_logged = False
    results: dict[tuple[str, int], dict[str, Any]] = {}

    def result_key(task: Any) -> tuple[str, int]:
        return extraction_planning.task_key(task)

    def note_cancelling() -> None:
        nonlocal cancel_logged
        state["status"] = "cancelling"
        state["phase"] = "cancelling"
        sync_state()
        if not cancel_logged:
            _log("warn", "收到取消信号，等待当前进行中的请求结束并停止后续调度")
            cancel_logged = True

    def persist_chunk_attempt(
        result: dict[str, Any],
        *,
        task: Any,
        payload: dict[str, Any],
        error: str | None,
        attempt: int,
    ) -> tuple[list[TripleRecord], str | None]:
        nonlocal total_triples, total_chunks_done, session_chunks_done

        rows, effective_error = _evaluate_chunk_attempt(
            pipeline,
            task=task,
            payload=payload,
            error=error,
        )
        result.update(
            {
                "task": task,
                "payload": payload,
                "error": effective_error,
                "rows": rows,
            }
        )
        result.setdefault("_written", False)
        if effective_error is None and not result.get("_written"):
            for row in rows:
                pipeline.append_jsonl(triples_jsonl, asdict(row))
            result["_written"] = True
            total_triples += len(rows)
            state["total_triples"] = total_triples
        if result["error"] is None:
            completed_chunk_keys.add(result_key(task))
        pipeline.append_jsonl(
            raw_jsonl,
            _build_raw_chunk_record(
                task=task,
                payload=payload,
                error=result["error"],
                rows_count=len(rows),
            ),
        )
        _append_checkpoint(
            checkpoint_path,
            task=task,
            error=result["error"],
            payload=payload,
            attempt=attempt,
            resumed=resume_mode,
            triples_count=len(rows),
        )
        total_chunks_done += 1
        session_chunks_done += 1
        _update_runtime_metrics(
            state,
            start_ts=start_ts,
            session_chunks_done=session_chunks_done,
            total_chunks_done=total_chunks_done,
            total_chunks_all=total_chunks_all,
        )
        refresh_provider_monitor()
        sync_state()
        return rows, effective_error

    def run_retry_batch(failed_items: list[dict[str, Any]], retry_count: int) -> None:
        chunk_execution.run_retry_batch(
            failed_items,
            retry_count,
            pipeline=pipeline,
            dry_run=dry_run,
            retry_parallel_workers=retry_parallel_workers,
            job_cancelled=_job_cancelled,
            state=state,
            note_cancelling=note_cancelling,
            persist_chunk_attempt=persist_chunk_attempt,
            metrics_snapshot=metrics_snapshot,
            update_current_job=update_current_job_only,
            log=_log,
        )

    def finalize_exhausted_low_yield_chunks(results: dict[tuple[str, int], dict[str, Any]]) -> int:
        finalized = extraction_finalizers.finalize_exhausted_low_yield_chunks(
            results=results,
            completed_chunk_keys=completed_chunk_keys,
            max_chunk_retries=max_chunk_retries,
            checkpoint_path=checkpoint_path,
            resume_mode=resume_mode,
            append_checkpoint=_append_checkpoint,
            is_low_yield_retry_error=_is_low_yield_retry_error,
            log=_log,
        )

        if finalized > 0:
            sync_state()
        return finalized

    def finalize_exhausted_failed_chunks(results: dict[tuple[str, int], dict[str, Any]]) -> int:
        finalized = extraction_finalizers.finalize_exhausted_failed_chunks(
            results=results,
            completed_chunk_keys=completed_chunk_keys,
            max_chunk_retries=max_chunk_retries,
            checkpoint_path=checkpoint_path,
            resume_mode=resume_mode,
            append_checkpoint=_append_checkpoint,
            is_low_yield_retry_error=_is_low_yield_retry_error,
            log=_log,
        )

        if finalized > 0:
            sync_state()
        return finalized

    def finalize_any_remaining_unresolved_chunks() -> int:
        finalized = extraction_finalizers.finalize_any_remaining_unresolved_chunks(
            all_tasks_per_book=all_tasks_per_book,
            results=results,
            completed_chunk_keys=completed_chunk_keys,
            checkpoint_path=checkpoint_path,
            resume_mode=resume_mode,
            append_checkpoint=_append_checkpoint,
            log=_log,
        )

        if finalized > 0:
            sync_state()
        return finalized

    try:
        # ── 第一阶段：分块调度（跨书交错，统一送入全局并行池） ─────────────────────
        all_tasks_per_book, total_chunks_all = extraction_planning.schedule_book_tasks(
            pipeline,
            selected_books=selected_books,
            chapter_excludes=chapter_excludes,
            max_chunks_per_book=max_chunks_per_book,
            skip_initial_chunks=skip_initial_chunks,
            chunk_strategy=chunk_strategy,
        )

        if resume_mode:
            completed_chunk_keys = extraction_planning.restrict_completed_to_scheduled(
                completed_chunk_keys,
                all_tasks_per_book,
            )
            total_chunks_done = len(completed_chunk_keys)
            state["resume_skipped_chunks"] = total_chunks_done

        pending_tasks_per_book: list[tuple[Path, list[Any]]] = []
        pending_candidates = extraction_planning.pending_tasks_by_book(
            all_tasks_per_book,
            completed_chunk_keys=completed_chunk_keys,
        )
        for book_index, ((book_path, scheduled_tasks), (_, pending_tasks)) in enumerate(zip(all_tasks_per_book, pending_candidates), start=1):
            skipped_completed = len(scheduled_tasks) - len(pending_tasks)
            if not pending_tasks:
                completed_book_stems.add(book_path.stem)
                state["books_completed"] = len(completed_book_stems)
                _clear_books_force_unprocessed([book_path.stem])
                if resume_mode and skipped_completed == len(scheduled_tasks):
                    _log("info", f"{book_path.stem} 本次续跑无需处理：{skipped_completed} 个 chunk 已在当前 run 完成，已自动跳过")
                else:
                    _log("warn", f"{book_path.stem} 无可处理 chunk（全部被过滤）")
                continue
            pending_tasks_per_book.append((book_path, pending_tasks))
            _log(
                "info",
                f"纳入全局队列 [{book_index}/{len(selected_books)}] {book_path.stem}，"
                f"{len(pending_tasks)} chunks | parallel={pipeline.config.parallel_workers} "
                f"retry_parallel={retry_parallel_workers} dry_run={dry_run}",
            )

        interleaved_tasks = extraction_planning.interleave_tasks(pending_tasks_per_book)

        state["chunks_total"] = total_chunks_all
        state["chunks_completed"] = total_chunks_done
        state["total_triples"] = total_triples
        state["phase"] = "extracting"
        _update_runtime_metrics(
            state,
            start_ts=start_ts,
            session_chunks_done=session_chunks_done,
            total_chunks_done=total_chunks_done,
            total_chunks_all=total_chunks_all,
        )
        refresh_provider_monitor()
        sync_state()
        _log("info", f"调度完成，共 {total_chunks_all} 个 chunk，全局队列待处理 {len(interleaved_tasks)} 个")
        if _job_cancelled.is_set():
            note_cancelling()

        if not _job_cancelled.is_set() and (dry_run or pipeline.config.parallel_workers <= 1 or len(interleaved_tasks) <= 1):
            chunk_errors += chunk_execution.run_serial_initial_chunks(
                interleaved_tasks,
                pipeline=pipeline,
                dry_run=dry_run,
                job_cancelled=_job_cancelled,
                state=state,
                results=results,
                result_key=result_key,
                note_cancelling=note_cancelling,
                persist_chunk_attempt=persist_chunk_attempt,
                update_current_job=update_current_job_only,
                log=_log,
            )
        elif not _job_cancelled.is_set():
            chunk_errors += chunk_execution.run_parallel_initial_chunks(
                interleaved_tasks,
                pipeline=pipeline,
                job_cancelled=_job_cancelled,
                state=state,
                results=results,
                result_key=result_key,
                note_cancelling=note_cancelling,
                persist_chunk_attempt=persist_chunk_attempt,
                metrics_snapshot=metrics_snapshot,
                log=_log,
            )
            if _job_cancelled.is_set():
                note_cancelling()

        retry_count = 0
        while retry_count < max_chunk_retries:
            if _job_cancelled.is_set():
                note_cancelling()
                break
            failed_tasks = [r for r in results.values() if r["error"] is not None and r.get("_retried", 0) < max_chunk_retries]
            if not failed_tasks:
                break
            retry_count += 1
            _log("warn", f"  开始第 {retry_count} 轮重试，{len(failed_tasks)} 个 chunk 待重试")
            state["chunk_retries"] = retry_count
            run_retry_batch(failed_tasks, retry_count)
            if _job_cancelled.is_set():
                break

        finalize_exhausted_low_yield_chunks(results)
        finalize_exhausted_failed_chunks(results)
        if not _job_cancelled.is_set():
            finalize_any_remaining_unresolved_chunks()

        incomplete_books = extraction_finalizers.summarize_book_completion(
            all_tasks_per_book=all_tasks_per_book,
            completed_book_stems=completed_book_stems,
            completed_chunk_keys=completed_chunk_keys,
            state=state,
            total_triples=total_triples,
            clear_books_force_unprocessed=_clear_books_force_unprocessed,
            log=_log,
        )

        all_rows.extend(extraction_planning.collect_success_rows(all_tasks_per_book, results=results))

        # ── 写出 CSV + graph_import ─────────────────────────────────────
        pipeline.write_csv(run_dir / "triples.normalized.csv", all_rows)
        pipeline.write_graph_import(run_dir / "graph_import.json", all_rows)

        was_cancelled = _job_cancelled.is_set() or state.get("status") == "cancelling"
        pending_chunk_count = extraction_planning.pending_chunk_count(
            all_tasks_per_book,
            completed_chunk_keys=completed_chunk_keys,
        )
        extraction_completion.apply_done_state(
            state=state,
            start_ts=start_ts,
            was_cancelled=was_cancelled,
            pending_chunk_count=pending_chunk_count,
            total_triples=total_triples,
            completed_book_count=len(completed_book_stems),
            incomplete_books=incomplete_books,
            now_iso=_now_iso,
            refresh_provider_monitor=refresh_provider_monitor,
            sync_state=sync_state,
        )
        extraction_completion.log_done_summary(
            was_cancelled=was_cancelled,
            pending_chunk_count=pending_chunk_count,
            total_triples=total_triples,
            chunk_errors=chunk_errors,
            log=_log,
        )
        extraction_completion.maybe_auto_clean(
            auto_clean=auto_clean,
            state=state,
            triples_jsonl=triples_jsonl,
            total_triples=total_triples,
            pipeline=pipeline,
            run_dir=run_dir,
            sync_state=sync_state,
            log=_log,
        )
        extraction_completion.maybe_auto_publish(
            auto_publish=auto_publish,
            state=state,
            run_dir=run_dir,
            enqueue_publish=lambda run_name: _enqueue_publish_task(run_name, kind="json", replace=False),
            sync_state=sync_state,
            log=_log,
        )
        extraction_completion.mark_finished(
            state=state,
            refresh_provider_monitor=refresh_provider_monitor,
            sync_state=sync_state,
        )
        if cleanup_job_log_file:
            _cleanup_job_log_file()

    except Exception as exc:
        extraction_completion.mark_error(
            state=state,
            exc=exc,
            describe_exception=_describe_exception,
            now_iso=_now_iso,
            refresh_provider_monitor=refresh_provider_monitor,
            sync_state=sync_state,
        )
        _log("error", f"任务异常: {state['error']}")
        _log("error", traceback.format_exc().rstrip())
        if cleanup_job_log_file:
            _cleanup_job_log_file()
