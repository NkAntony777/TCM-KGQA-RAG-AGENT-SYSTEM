"""
pipeline_server.py  —  TCM 三元组提取流水线 Web 控制台（后端）
启动: python pipeline_server.py --port 7800
访问: http://127.0.0.1:7800
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time  # noqa: F401 - dynamic helper/test compatibility for runtime_metrics patching
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# ── 路径修正：让 pipeline_server.py 能 import tcm_triple_console ──────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(_BACKEND_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from scripts.pipeline_console import auto_batch
from scripts.pipeline_console import book_status
from scripts.pipeline_console import books_api
from scripts.pipeline_console import chunk_execution  # noqa: F401 - used dynamically by extraction_job_runner
from scripts.pipeline_console import chunk_attempts
from scripts.pipeline_console import diagnostics_api
from scripts.pipeline_console import extraction_completion  # noqa: F401 - used dynamically by extraction_job_runner
from scripts.pipeline_console import extraction_finalizers  # noqa: F401 - used dynamically by extraction_job_runner
from scripts.pipeline_console import extraction_job_runner
from scripts.pipeline_console import extraction_planning  # noqa: F401 - used dynamically by extraction_job_runner
from scripts.pipeline_console import extraction_state  # noqa: F401 - used dynamically by extraction_job_runner
from scripts.pipeline_console import graph_admin
from scripts.pipeline_console import job_requests
from scripts.pipeline_console import job_state
from scripts.pipeline_console import pipeline_factory
from scripts.pipeline_console import run_artifacts
from scripts.pipeline_console import runtime_metrics
from scripts.pipeline_console import runs_api
from scripts.pipeline_console.models import GraphBookDeleteRequest, ResumeRunRequest, StartJobRequest
from scripts.pipeline_console.publish_queue import PublishQueueRuntime
from services.triple_pipeline_service import (
    DEFAULT_BOOKS_DIR,
    DEFAULT_GRAPH_BASE,
    DEFAULT_GRAPH_TARGET,
    DEFAULT_OUTPUT_DIR,
    PipelineConfig,
    TCMTriplePipeline,
    TripleRecord,
    _extract_payload_triples,
    _load_json_file,
    _normalize_provider_configs,
    _provider_to_dict,
    _write_text_atomic,
    _first_env,
)
from services.graph_service.runtime_store import RuntimeGraphStore
from scripts.chunk_size_benchmark_lab import router as chunk_benchmark_router
from scripts.triple_benchmark_lab import router as benchmark_router

# ─────────────────────────────────────────────────────────────────────────────
# 全局状态
# ─────────────────────────────────────────────────────────────────────────────

def _pipeline_cors_origins() -> list[str]:
    configured = os.getenv("PIPELINE_CORS_ORIGINS", "").strip()
    if configured:
        return [item.strip().rstrip("/") for item in configured.split(",") if item.strip()]
    return [
        "http://localhost:7800",
        "http://127.0.0.1:7800",
    ]


app = FastAPI(title="TCM Triple Pipeline Console", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_pipeline_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(benchmark_router)
app.include_router(chunk_benchmark_router)
app.mount(
    "/static/pipeline_console",
    StaticFiles(directory=_SCRIPTS_DIR / "pipeline_console" / "assets"),
    name="pipeline_console_static",
)

# 当前运行状态（单例任务模型）
_run_lock = threading.Lock()
_current_job: dict[str, Any] = {}          # 当前运行元数据
_job_log: list[dict[str, Any]] = []        # 实时日志队列（线程安全追加）
_job_log_file: Path | None = None          # 实时日志磁盘文件，任务结束时清理
_job_log_file_path: Path | None = None     # 日志文件路径（用于任务结束后删除）
_job_thread: threading.Thread | None = None
_job_cancelled = threading.Event()         # 用于取消信号
_publish_lock = threading.RLock()
_nebula_publish_threads: dict[str, threading.Thread] = {}
_publish_queue: deque[dict[str, Any]] = deque()
_publish_worker_wakeup = threading.Event()
_active_publish_task: dict[str, Any] | None = None
_book_status_lock = threading.RLock()
_runtime_graph_mutation_lock = threading.RLock()

DEFAULT_AUTO_BOOK_BATCH_SIZE = 7
LOW_YIELD_RETRY_TRIPLE_THRESHOLD = 1
PROVIDER_MONITOR_LOG_INTERVAL = 10


def _log(level: str, msg: str, **extra: Any) -> None:
    job_state.append_job_log(
        lock=_run_lock,
        job_log=_job_log,
        log_file=_job_log_file,
        level=level,
        msg=msg,
        extra=extra,
    )


def _cleanup_job_log_file() -> None:
    global _job_log_file, _job_log_file_path
    _job_log_file, _job_log_file_path = job_state.cleanup_job_log_file(
        lock=_run_lock,
        log_file_path=_job_log_file_path,
    )


def _is_job_thread_alive() -> bool:
    thread = _job_thread
    return bool(thread and thread.is_alive())


def _book_status_override_path() -> Path:
    return DEFAULT_OUTPUT_DIR / "book_status_overrides.json"


def _graph_evidence_path(target: Path | None = None) -> Path:
    graph_path = target or DEFAULT_GRAPH_TARGET
    return graph_path.parent / f"{graph_path.stem}.evidence.jsonl"


def _runtime_graph_store() -> RuntimeGraphStore:
    return RuntimeGraphStore.from_graph_paths(
        graph_path=DEFAULT_GRAPH_TARGET,
        evidence_path=_graph_evidence_path(DEFAULT_GRAPH_TARGET),
        sample_graph_path=DEFAULT_GRAPH_BASE,
    )


_publish_runtime = PublishQueueRuntime(
    output_dir_provider=lambda: DEFAULT_OUTPUT_DIR,
    load_json_file=_load_json_file,
    write_json_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    runtime_graph_store=_runtime_graph_store,
    runtime_graph_mutation_lock=_runtime_graph_mutation_lock,
    resolve_run_publish_source=lambda run_dir: _resolve_run_publish_source(run_dir),
    now_iso=lambda: _now_iso(),
    describe_exception=lambda exc: _describe_exception(exc),
    nebula_health_detail=lambda health: _nebula_health_detail(health),
)
_publish_lock = _publish_runtime.lock
_nebula_publish_threads = _publish_runtime.nebula_publish_threads
_publish_queue = _publish_runtime.queue
_publish_worker_wakeup = _publish_runtime.worker_wakeup


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _describe_exception(exc: Exception) -> str:
    message = str(exc).strip()
    exc_type = type(exc).__name__
    if message:
        return f"{exc_type}: {message}"
    exc_repr = repr(exc).strip()
    if exc_repr and exc_repr != f"{exc_type}()":
        return f"{exc_type}: {exc_repr}"
    return exc_type


def _publish_status_path(run_dir: Path) -> Path:
    return _publish_runtime.publish_status_path(run_dir)


def _normalize_publish_status(payload: Any) -> dict[str, Any]:
    return _publish_runtime.normalize_status(payload)


def _load_publish_status(run_dir: Path) -> dict[str, Any]:
    return _publish_runtime.load_status(run_dir)


def _write_publish_status(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _publish_runtime.write_status(run_dir, payload)


def _update_publish_status(run_dir: Path, section: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _publish_runtime.update_status(run_dir, section, patch)


def _publish_task_covers(task_kind: str, requested_kind: str) -> bool:
    return _publish_runtime.task_covers(task_kind, requested_kind)


def _set_json_publish_queued(run_dir: Path) -> dict[str, Any]:
    return _publish_runtime.set_json_queued(run_dir)


def _set_nebula_publish_queued(run_dir: Path) -> dict[str, Any]:
    return _publish_runtime.set_nebula_queued(run_dir)


def _reset_json_publish_to_idle_if_unpublished(run_dir: Path) -> dict[str, Any]:
    return _publish_runtime.reset_json_to_idle_if_unpublished(run_dir)


def _publish_worker_loop() -> None:
    _publish_runtime.worker_loop()


def _ensure_publish_worker_locked() -> None:
    _publish_runtime.ensure_worker_locked()


def _enqueue_publish_task(run_name: str, *, kind: str, replace: bool = False) -> tuple[bool, dict[str, Any]]:
    return _publish_runtime.enqueue(run_name, kind=kind, replace=replace)


def _iter_run_dirs_desc() -> list[Path]:
    return _publish_runtime.iter_run_dirs_desc()


def _eligible_for_bulk_publish(run_dir: Path, *, kind: str) -> bool:
    return _publish_runtime.eligible_for_bulk_publish(run_dir, kind=kind)


def _bulk_enqueue_unpublished_runs(kind: str) -> dict[str, Any]:
    return _publish_runtime.bulk_enqueue_unpublished(kind)


def _mark_cancel_requested() -> None:
    job_state.mark_cancel_requested(
        lock=_run_lock,
        current_job=_current_job,
        write_state=_write_state,
    )


def _append_checkpoint(
    checkpoint_path: Path,
    *,
    task: Any,
    error: str | None,
    payload: dict[str, Any],
    attempt: int,
    resumed: bool,
    triples_count: int | None = None,
    success_override: bool | None = None,
) -> None:
    run_artifacts.append_checkpoint(
        checkpoint_path,
        task=task,
        error=error,
        payload=payload,
        attempt=attempt,
        resumed=resumed,
        extract_payload_triples=_extract_payload_triples,
        now_iso=_now_iso,
        triples_count=triples_count,
        success_override=success_override,
    )


def _count_jsonl_rows(path: Path) -> int:
    return run_artifacts.count_jsonl_rows(path)


def _load_book_status_overrides() -> dict[str, list[str]]:
    return book_status.load_overrides(
        lock=_book_status_lock,
        path=_book_status_override_path(),
        load_json_file=_load_json_file,
    )


def _write_book_status_overrides(payload: dict[str, list[str]]) -> dict[str, list[str]]:
    return book_status.write_overrides(
        lock=_book_status_lock,
        path=_book_status_override_path(),
        payload=payload,
        write_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    )


def _mark_books_force_unprocessed(book_names: list[str]) -> dict[str, list[str]]:
    return book_status.mark_force_unprocessed(
        lock=_book_status_lock,
        path=_book_status_override_path(),
        book_names=book_names,
        load_json_file=_load_json_file,
        write_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    )


def _clear_books_force_unprocessed(book_names: list[str]) -> dict[str, list[str]]:
    return book_status.clear_force_unprocessed(
        lock=_book_status_lock,
        path=_book_status_override_path(),
        book_names=book_names,
        load_json_file=_load_json_file,
        write_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    )


def _publish_queue_busy_marker() -> str | None:
    active = _active_publish_task or _publish_runtime.active_task or {}
    active_run = str(active.get("run_name", "") or "").strip()
    active_kind = str(active.get("kind", "") or "").strip()
    if active_run and active_kind:
        return f"{active_run}:{active_kind}"
    return _publish_runtime.publish_queue_busy_marker()


def _delete_books_from_runtime_graph(
    book_names: list[str],
    *,
    sync_nebula: bool = True,
    mark_unprocessed: bool = True,
) -> dict[str, Any]:
    return graph_admin.delete_books_from_runtime_graph(
        book_names,
        runtime_graph_store=_runtime_graph_store,
        runtime_graph_mutation_lock=_runtime_graph_mutation_lock,
        publish_busy_marker=_publish_queue_busy_marker,
        load_book_status_overrides=_load_book_status_overrides,
        mark_books_force_unprocessed=_mark_books_force_unprocessed,
        sync_nebula=sync_nebula,
        mark_unprocessed=mark_unprocessed,
    )


def _load_existing_triple_records(path: Path) -> list[TripleRecord]:
    return run_artifacts.load_existing_triple_records(path, triple_record_cls=TripleRecord)


def _load_completed_chunk_keys(run_dir: Path) -> set[tuple[str, int]]:
    return run_artifacts.load_completed_chunk_keys(run_dir)


def _low_yield_retry_error(triples_count: int) -> str:
    return chunk_attempts.low_yield_retry_error(triples_count)


def _is_low_yield_retry_error(error: str | None) -> bool:
    return chunk_attempts.is_low_yield_retry_error(error)


def _extract_payload_meta(payload: Any) -> dict[str, Any]:
    return chunk_attempts.extract_payload_meta(payload)


def _build_raw_chunk_record(
    *,
    task: Any,
    payload: Any,
    error: str | None,
    rows_count: int,
) -> dict[str, Any]:
    return chunk_attempts.build_raw_chunk_record(
        task=task,
        payload=payload,
        error=error,
        rows_count=rows_count,
    )


def _should_accept_empty_chunk(task: Any, rows: list[TripleRecord], error: str | None) -> bool:
    return chunk_attempts.should_accept_empty_chunk(task, rows, error)


def _evaluate_chunk_attempt(
    pipeline: TCMTriplePipeline,
    *,
    task: Any,
    payload: dict[str, Any],
    error: str | None,
) -> tuple[list[TripleRecord], str | None]:
    rows, attempt_error = chunk_attempts.evaluate_chunk_attempt(
        pipeline,
        task=task,
        payload=payload,
        error=error,
        low_yield_retry_triple_threshold=LOW_YIELD_RETRY_TRIPLE_THRESHOLD,
    )
    return rows, attempt_error


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _build_pipeline(cfg_override: dict[str, Any] | None = None) -> TCMTriplePipeline:
    return pipeline_factory.build_pipeline(
        cfg_override=cfg_override,
        pipeline_config_cls=PipelineConfig,
        pipeline_cls=TCMTriplePipeline,
        default_books_dir=DEFAULT_BOOKS_DIR,
        default_output_dir=DEFAULT_OUTPUT_DIR,
        first_env=_first_env,
        normalize_provider_configs=_normalize_provider_configs,
    )


def _is_full_completed_run(manifest: dict[str, Any], state: dict[str, Any]) -> bool:
    return auto_batch.is_full_completed_run(manifest, state)


def _manifest_has_full_book_scope(manifest_cfg: dict[str, Any]) -> bool:
    return auto_batch.manifest_has_full_book_scope(manifest_cfg)


def _collect_completed_book_stems_from_run(manifest: dict[str, Any], state: dict[str, Any], run_dir: Path) -> set[str]:
    return auto_batch.collect_completed_book_stems_from_run(
        manifest,
        state,
        run_dir,
        pipeline_cls=TCMTriplePipeline,
        pipeline_config_cls=PipelineConfig,
        default_books_dir=DEFAULT_BOOKS_DIR,
        load_completed_chunk_keys=_load_completed_chunk_keys,
    )


def _get_processed_book_stems() -> set[str]:
    """扫描历史 run，收集已完整处理过的书目 stems。"""
    return auto_batch.get_processed_book_stems(
        output_dir=DEFAULT_OUTPUT_DIR,
        load_book_status_overrides=_load_book_status_overrides,
        pipeline_cls=TCMTriplePipeline,
        pipeline_config_cls=PipelineConfig,
        default_books_dir=DEFAULT_BOOKS_DIR,
        load_completed_chunk_keys=_load_completed_chunk_keys,
    )


def _resolve_start_selected_books(pipeline: TCMTriplePipeline, raw_selected_books: list[str]) -> list[Path]:
    return auto_batch.resolve_start_selected_books(pipeline, raw_selected_books)


def _exclude_processed_books_for_new_run(selected_books: list[Path]) -> tuple[list[Path], list[str]]:
    return auto_batch.exclude_processed_books_for_new_run(
        selected_books,
        processed_stems=_get_processed_book_stems(),
    )


def _sanitize_auto_batch_size(batch_size: int | None) -> int:
    return auto_batch.sanitize_auto_batch_size(batch_size, default_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE)


def _ordered_unprocessed_books_for_new_run(
    pipeline: TCMTriplePipeline,
    *,
    batch_size: int | None = None,
) -> tuple[list[Path], list[str]]:
    return auto_batch.ordered_unprocessed_books_for_new_run(
        pipeline,
        processed_stems=_get_processed_book_stems(),
        batch_size=batch_size,
        default_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
    )


def _select_auto_start_books(
    pipeline: TCMTriplePipeline,
    *,
    batch_size: int = DEFAULT_AUTO_BOOK_BATCH_SIZE,
) -> tuple[list[Path], list[str]]:
    return auto_batch.select_auto_start_books(
        pipeline,
        processed_stems=_get_processed_book_stems(),
        batch_size=batch_size,
        default_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
    )


def _resolve_run_publish_source(run_dir: Path) -> tuple[Path, Path | None]:
    return run_artifacts.resolve_run_publish_source(run_dir)


def _record_json_publish_status(
    run_dir: Path,
    *,
    target: Path,
    graph_triples: int,
    evidence_count: int,
) -> dict[str, Any]:
    return _publish_runtime.record_json_publish_status(
        run_dir,
        target=target,
        graph_triples=graph_triples,
        evidence_count=evidence_count,
    )


def _publish_json_for_run(run_dir: Path, *, replace: bool = False) -> dict[str, Any]:
    return _publish_runtime.publish_json_for_run(run_dir, replace=replace)


def _run_json_publish_job(run_name: str, *, replace: bool = False) -> dict[str, Any]:
    return _publish_runtime.run_json_publish_job(run_name, replace=replace)


def _run_nebula_publish_job(run_name: str) -> None:
    _publish_runtime.run_nebula_publish_job(run_name)


def _nebula_health_detail(health: dict[str, Any]) -> str:
    warning = str(health.get("warning", "") or "").strip()
    host = str(health.get("host", "") or "").strip()
    port = health.get("port")
    space = str(health.get("space", "") or "").strip()
    base = f"NebulaGraph not reachable: host={host} port={port} space={space}"
    return f"{base} | {warning}" if warning else base


def _fmt_eta(remaining_secs: float) -> str:
    return runtime_metrics.fmt_eta(remaining_secs)


def _update_runtime_metrics(
    state: dict[str, Any],
    *,
    start_ts: float,
    session_chunks_done: int,
    total_chunks_done: int,
    total_chunks_all: int,
) -> None:
    runtime_metrics.update_runtime_metrics(
        state,
        start_ts=start_ts,
        session_chunks_done=session_chunks_done,
        total_chunks_done=total_chunks_done,
        total_chunks_all=total_chunks_all,
    )


def _derive_retry_parallel_workers(parallel_workers: Any) -> int:
    return runtime_metrics.derive_retry_parallel_workers(parallel_workers)


RESUME_FIXED_FIELDS = {
    "chapter_excludes",
    "skip_initial_chunks_per_book",
    "chunk_strategy",
    "max_chunk_chars",
    "chunk_overlap",
    "max_chunks_per_book",
}


# ─────────────────────────────────────────────────────────────────────────────
# 核心后台任务
# ─────────────────────────────────────────────────────────────────────────────

def _build_extraction_job_context() -> extraction_job_runner.ExtractionJobContext:
    return extraction_job_runner.ExtractionJobContext(
        current_job=_current_job,
        run_lock=_run_lock,
        job_cancelled=_job_cancelled,
        build_pipeline=_build_pipeline,
        load_completed_chunk_keys=_load_completed_chunk_keys,
        count_jsonl_rows=_count_jsonl_rows,
        derive_retry_parallel_workers=_derive_retry_parallel_workers,
        now_iso=_now_iso,
        provider_to_dict=_provider_to_dict,
        write_state=_write_state,
        log=_log,
        load_existing_triple_records=_load_existing_triple_records,
        clear_books_force_unprocessed=_clear_books_force_unprocessed,
        evaluate_chunk_attempt=_evaluate_chunk_attempt,
        build_raw_chunk_record=_build_raw_chunk_record,
        append_checkpoint=_append_checkpoint,
        update_runtime_metrics=_update_runtime_metrics,
        is_low_yield_retry_error=_is_low_yield_retry_error,
        enqueue_publish_task=_enqueue_publish_task,
        cleanup_job_log_file=_cleanup_job_log_file,
        describe_exception=_describe_exception,
        job_state=job_state,
        extraction_state=extraction_state,
        extraction_planning=extraction_planning,
        chunk_execution=chunk_execution,
        extraction_finalizers=extraction_finalizers,
        extraction_completion=extraction_completion,
    )


def _run_extraction_job(
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
) -> None:
    return extraction_job_runner.run_extraction_job(
        job_id=job_id,
        selected_books=selected_books,
        label=label,
        dry_run=dry_run,
        cfg_override=cfg_override,
        chapter_excludes=chapter_excludes,
        max_chunks_per_book=max_chunks_per_book,
        skip_initial_chunks=skip_initial_chunks,
        chunk_strategy=chunk_strategy,
        auto_clean=auto_clean,
        auto_publish=auto_publish,
        max_chunk_retries=max_chunk_retries,
        resume_run_dir=resume_run_dir,
        cleanup_job_log_file=cleanup_job_log_file,
        context=_build_extraction_job_context(),
    )


def _run_auto_extraction_batches(
    *,
    job_id: str,
    initial_selected_books: list[Path],
    initial_resume_run_dir: Path | None = None,
    label: str,
    dry_run: bool,
    cfg_override: dict[str, Any],
    chapter_excludes: list[str],
    max_chunks_per_book: int | None,
    skip_initial_chunks: int,
    chunk_strategy: str,
    auto_clean: bool,
    auto_publish: bool,
    max_chunk_retries: int,
    batch_size: int = DEFAULT_AUTO_BOOK_BATCH_SIZE,
) -> None:
    auto_batch.run_auto_extraction_batches(
        job_id=job_id,
        initial_selected_books=initial_selected_books,
        initial_resume_run_dir=initial_resume_run_dir,
        label=label,
        dry_run=dry_run,
        cfg_override=cfg_override,
        chapter_excludes=chapter_excludes,
        max_chunks_per_book=max_chunks_per_book,
        skip_initial_chunks=skip_initial_chunks,
        chunk_strategy=chunk_strategy,
        auto_clean=auto_clean,
        auto_publish=auto_publish,
        max_chunk_retries=max_chunk_retries,
        batch_size=batch_size,
        default_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
        build_pipeline=lambda cfg: _build_pipeline(cfg),
        run_extraction_job=_run_extraction_job,
        select_auto_start_books_fn=_select_auto_start_books,
        job_cancelled=_job_cancelled,
        run_lock=_run_lock,
        current_job=_current_job,
        log=lambda level, msg: _log(level, msg),
        cleanup_job_log_file=_cleanup_job_log_file,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/books")
def list_books():
    """列出所有书目"""
    try:
        pipeline = _build_pipeline()
        return books_api.list_books_payload(
            pipeline,
            processed_stems=_get_processed_book_stems(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/books/{book_name}/chapters")
def list_chapters(book_name: str, limit: int = 50):
    """查看某本书的章节"""
    try:
        pipeline = _build_pipeline()
        return books_api.chapters_payload(pipeline, book_name=book_name, limit=limit)
    except LookupError:
        raise HTTPException(status_code=404, detail="book_not_found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/job/start")
def start_job(req: StartJobRequest):
    """启动一次提取任务"""
    global _job_thread, _job_log_file, _job_log_file_path

    with _run_lock:
        if _current_job.get("status") == "running":
            raise HTTPException(status_code=409, detail="已有任务运行中，请等待完成或先取消")

    pipeline = _build_pipeline(req.api_config.model_dump())
    selected, auto_skipped_processed_books, auto_chain_mode, auto_batch_size = job_requests.prepare_start_selection(
        pipeline=pipeline,
        raw_selected_books=req.selected_books,
        default_auto_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
        resolve_selected_books=_resolve_start_selected_books,
        select_auto_start_books=lambda current_pipeline: _select_auto_start_books(
            current_pipeline,
            batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
        ),
    )

    if not selected:
        detail = "没有剩余未处理书籍；如需重跑历史书籍，请手动选择具体书目"
        raise HTTPException(status_code=400, detail=detail)

    if not req.dry_run and not job_requests.enabled_provider_has_api_key(pipeline):
        raise HTTPException(status_code=400, detail="未配置 API Key，请在 API 配置中填写或在 .env 中设置 TRIPLE_LLM_API_KEY")

    job_id = str(uuid4())[:8]
    _job_log_file, _job_log_file_path = job_state.initialize_job_context(
        lock=_run_lock,
        current_job=_current_job,
        job_log=_job_log,
        cancel_event=_job_cancelled,
        output_dir=DEFAULT_OUTPUT_DIR,
        job_id=job_id,
        write_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    )

    target = _run_auto_extraction_batches if auto_chain_mode else _run_extraction_job
    thread_kwargs = job_requests.start_thread_kwargs(
        job_id=job_id,
        label=req.label or "extraction",
        dry_run=req.dry_run,
        cfg_override=req.api_config.model_dump(),
        chapter_excludes=req.chapter_excludes,
        max_chunks_per_book=req.max_chunks_per_book,
        skip_initial_chunks=req.skip_initial_chunks,
        chunk_strategy=req.chunk_strategy,
        auto_clean=req.auto_clean,
        auto_publish=req.auto_publish,
        max_chunk_retries=req.api_config.max_chunk_retries,
        auto_chain_mode=auto_chain_mode,
        selected_books=selected,
        auto_batch_size=auto_batch_size,
    )

    _job_thread = threading.Thread(
        target=target,
        kwargs=thread_kwargs,
        daemon=True,
    )
    _job_thread.start()
    return job_requests.start_response(
        job_id=job_id,
        selected_books=selected,
        auto_skipped_processed_books=auto_skipped_processed_books,
        auto_chain_mode=auto_chain_mode,
        auto_batch_size=auto_batch_size,
    )


@app.post("/api/runs/{run_name}/resume")
def resume_run(run_name: str, req: ResumeRunRequest):
    global _job_thread, _job_log_file, _job_log_file_path

    with _run_lock:
        if _current_job.get("status") == "running":
            raise HTTPException(status_code=409, detail="existing_job_running")

    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    manifest = _load_json_file(run_dir / "manifest.json", {})
    selected = job_requests.selected_books_from_manifest(manifest)
    if not selected:
        raise HTTPException(status_code=400, detail="run_books_not_found")

    cfg_override = job_requests.merge_resume_config(
        manifest=manifest,
        request_api_config=req.api_config.model_dump(exclude_unset=True),
        fixed_fields=RESUME_FIXED_FIELDS,
    )

    dry_run = bool(manifest.get("dry_run", False))
    if not dry_run:
        resumed_pipeline = _build_pipeline(cfg_override)
        if not job_requests.enabled_provider_has_api_key(resumed_pipeline):
            raise HTTPException(status_code=400, detail="missing_llm_api_key")

    manifest_cfg = manifest.get("config", {})
    job_id = str(uuid4())[:8]
    _job_log_file, _job_log_file_path = job_state.initialize_job_context(
        lock=_run_lock,
        current_job=_current_job,
        job_log=_job_log,
        cancel_event=_job_cancelled,
        output_dir=DEFAULT_OUTPUT_DIR,
        job_id=job_id,
        write_text=lambda path, text: _write_text_atomic(path, text, encoding="utf-8"),
    )

    auto_chain_mode = bool(req.continue_next_batches)
    target = _run_auto_extraction_batches if auto_chain_mode else _run_extraction_job
    thread_kwargs = job_requests.resume_thread_kwargs(
        job_id=job_id,
        run_name=run_name,
        dry_run=dry_run,
        cfg_override=cfg_override,
        manifest_cfg=manifest_cfg,
        auto_clean=req.auto_clean,
        auto_publish=req.auto_publish,
        max_chunk_retries=int(cfg_override.get("max_chunk_retries", req.api_config.max_chunk_retries)),
        auto_chain_mode=auto_chain_mode,
        selected_books=selected,
        run_dir=run_dir,
        default_auto_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
    )

    _job_thread = threading.Thread(
        target=target,
        kwargs=thread_kwargs,
        daemon=True,
    )
    _job_thread.start()
    return job_requests.resume_response(
        job_id=job_id,
        run_name=run_name,
        selected_books=selected,
        auto_chain_mode=auto_chain_mode,
        default_auto_batch_size=DEFAULT_AUTO_BOOK_BATCH_SIZE,
    )


@app.post("/api/job/cancel")
def cancel_job():
    """取消当前运行中的任务"""
    already_set = _job_cancelled.is_set()
    _job_cancelled.set()
    if not already_set:
        _mark_cancel_requested()
        _log("warn", "收到用户取消请求")
    return {"message": "取消信号已发送", "status": "cancelling" if _current_job else "idle"}


@app.get("/api/job/status")
def job_status():
    """获取当前任务状态快照"""
    return job_state.job_status_snapshot(lock=_run_lock, current_job=_current_job)


@app.get("/api/job/log")
def job_log(since: int = 0):
    """获取日志（since=起始序号）"""
    return job_state.job_log_slice(lock=_run_lock, job_log=_job_log, since=since)


@app.get("/api/job/stream")
async def job_stream():
    """SSE 实时推送状态 + 日志"""
    async def generator():
        async for payload in job_state.iter_job_stream_events(
            lock=_run_lock,
            current_job=_current_job,
            job_log=_job_log,
            get_log_file=lambda: _job_log_file,
            is_job_thread_alive=_is_job_thread_alive,
        ):
            yield payload
    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/api/runs")
def list_runs(page: int = 1, page_size: int = 20):
    """列出历史运行记录"""
    return runs_api.list_runs_payload(
        output_dir=DEFAULT_OUTPUT_DIR,
        load_json_file=_load_json_file,
        load_publish_status=_load_publish_status,
        page=page,
        page_size=page_size,
    )


@app.get("/api/runs/{run_name}/resume-config")
def run_resume_config(run_name: str):
    """返回指定 run 的续跑默认配置。"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    return runs_api.resume_config_payload(
        run_name=run_name,
        run_dir=run_dir,
        load_json_file=_load_json_file,
        resume_fixed_fields=RESUME_FIXED_FIELDS,
    )


@app.get("/api/runs/{run_name}/triples")
def run_triples(run_name: str, limit: int = 50):
    """查看某次运行的三元组样本"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    return runs_api.run_triples_payload(run_name=run_name, run_dir=run_dir, limit=limit)


@app.post("/api/runs/{run_name}/clean")
def run_clean(run_name: str):
    """清洗指定运行"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        pipeline = _build_pipeline()
        report = pipeline.clean_run_dir(run_dir)
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_name}/publish")
def run_publish(run_name: str, replace: bool = False):
    """将指定运行加入 SQLite 运行时图谱同步队列"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        enqueued, publish_status = _enqueue_publish_task(run_name, kind="json", replace=replace)
        return JSONResponse(
            status_code=202,
            content={
                "run_dir": run_name,
                "enqueued": enqueued,
                "publish_status": publish_status,
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run_not_found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/runs/{run_name}/publish-status")
def run_publish_status(run_name: str):
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    return {
        "run_dir": run_name,
        "publish_status": _load_publish_status(run_dir),
    }


@app.post("/api/runs/{run_name}/publish-nebula")
def run_publish_nebula(run_name: str):
    """将指定运行加入 Nebula 发布队列（自动先同步 SQLite 运行时图谱）"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    try:
        enqueued, publish_status = _enqueue_publish_task(run_name, kind="nebula", replace=False)
        return JSONResponse(
            status_code=202,
            content={
                "run_dir": run_name,
                "enqueued": enqueued,
                "publish_status": publish_status,
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run_not_found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/publish-unpublished")
def publish_unpublished_runs():
    try:
        return _bulk_enqueue_unpublished_runs("json")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/publish-nebula-unpublished")
def publish_unpublished_runs_nebula():
    try:
        return _bulk_enqueue_unpublished_runs("nebula")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/publish/stop-all")
def stop_all_publish_tasks():
    return _publish_runtime.stop_all()


@app.get("/api/graph/stats")
def graph_stats():
    """当前 runtime 图谱的统计信息"""
    try:
        return graph_admin.graph_stats_payload(_runtime_graph_store)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/graph/books")
def graph_books(limit: int = 200, q: str = ""):
    try:
        return graph_admin.graph_books_payload(
            runtime_graph_store=_runtime_graph_store,
            processed_books_provider=_get_processed_book_stems,
            book_overrides_provider=_load_book_status_overrides,
            limit=limit,
            keyword=q,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/graph/books/{book_name}/triples")
def graph_book_triples(book_name: str, limit: int = 200):
    try:
        return graph_admin.graph_book_triples_payload(
            runtime_graph_store=_runtime_graph_store,
            book_name=book_name,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/graph/books/delete")
def graph_delete_books(req: GraphBookDeleteRequest):
    try:
        result = _delete_books_from_runtime_graph(
            req.books,
            sync_nebula=req.sync_nebula,
            mark_unprocessed=req.mark_unprocessed,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        detail = str(exc)
        if detail.startswith("publish_queue_busy:"):
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=500, detail=detail)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/config/env")
def get_env_config():
    """返回当前从环境变量读取的配置（隐藏 key）"""
    model = _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="mimo-v2-pro")
    base_url = _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    providers = _normalize_provider_configs(
        [],
        fallback_model=model,
        fallback_api_key=api_key,
        fallback_base_url=base_url,
    )
    return diagnostics_api.env_config_payload(
        model=model,
        base_url=base_url,
        api_key=api_key,
        providers=providers,
        provider_to_dict=_provider_to_dict,
    )


@app.post("/api/job/test-call")
def test_api_call(req: StartJobRequest):
    """诊断接口：拿第一本书的第一个 chunk 测试 API，返回原始 LLM 响应和解析结果"""
    try:
        pipeline = _build_pipeline(req.api_config.model_dump())
        return diagnostics_api.test_api_call_payload(
            pipeline,
            chapter_excludes=req.chapter_excludes,
            chunk_strategy=req.chunk_strategy,
            provider_to_dict=_provider_to_dict,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 内嵌前端（单文件 SPA）
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = _SCRIPTS_DIR / "pipeline_console.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>pipeline_console.html not found</h1>")


# ─────────────────────────────────────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="TCM Triple Pipeline Console Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7800)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print("🚀 TCM Pipeline Console 启动中...")
    print(f"   访问地址: http://{args.host}:{args.port}")
    print(f"   书库路径: {DEFAULT_BOOKS_DIR}")
    print(f"   输出目录: {DEFAULT_OUTPUT_DIR}")
    print(f"   图谱目标: {DEFAULT_GRAPH_TARGET}")
    uvicorn.run(
        "scripts.pipeline_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(_BACKEND_DIR),
    )
