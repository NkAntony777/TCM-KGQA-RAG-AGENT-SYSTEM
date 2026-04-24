from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


NowFn = Callable[[], str]
ProviderToDictFn = Callable[[Any], dict[str, Any]]


def build_initial_state(
    *,
    job_id: str,
    selected_books: list[Path],
    run_dir: Path,
    dry_run: bool,
    pipeline: Any,
    resume_mode: bool,
    completed_chunk_count: int,
    retry_parallel_workers: int,
    now_iso: NowFn,
    provider_to_dict: ProviderToDictFn,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "running",
        "phase": "scheduling",
        "books_total": len(selected_books),
        "books_completed": 0,
        "chunks_total": 0,
        "chunks_completed": 0,
        "total_triples": 0,
        "chunk_errors": 0,
        "chunk_retries": 0,
        "current_book": "",
        "current_chapter": "",
        "elapsed_secs": 0,
        "eta": "",
        "run_dir": str(run_dir),
        "started_at": now_iso(),
        "finished_at": None,
        "dry_run": dry_run,
        "model": pipeline.config.model,
        "speed_chunks_per_min": 0.0,
        "resumed": resume_mode,
        "resumed_run_dir": run_dir.name if resume_mode else "",
        "resume_skipped_chunks": completed_chunk_count,
        "retry_parallel_workers": retry_parallel_workers,
        "providers": [provider_to_dict(provider) for provider in pipeline.config.providers],
        "provider_metrics": pipeline.get_provider_metrics(),
    }


def build_manifest_payload(
    *,
    job_id: str,
    selected_books: list[Path],
    pipeline: Any,
    dry_run: bool,
    resume_run_dir: Path | None,
    chapter_excludes: list[str],
    skip_initial_chunks: int,
    chunk_strategy: str,
    max_chunks_per_book: int | None,
    max_chunk_retries: int,
    now_iso: NowFn,
    provider_to_dict: ProviderToDictFn,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "created_at": now_iso(),
        "books": [str(path) for path in selected_books],
        "model": pipeline.config.model,
        "base_url": pipeline.config.base_url,
        "dry_run": dry_run,
        "resume_run_dir": str(resume_run_dir) if resume_run_dir else "",
        "config": {
            "providers": [provider_to_dict(provider) for provider in pipeline.config.providers],
            "max_chunk_chars": pipeline.config.max_chunk_chars,
            "chunk_overlap": pipeline.config.chunk_overlap,
            "chapter_excludes": chapter_excludes,
            "skip_initial_chunks_per_book": skip_initial_chunks,
            "chunk_strategy": chunk_strategy,
            "parallel_workers": pipeline.config.parallel_workers,
            "request_timeout": pipeline.config.request_timeout,
            "max_retries": pipeline.config.max_retries,
            "request_delay": pipeline.config.request_delay,
            "retry_backoff_base": pipeline.config.retry_backoff_base,
            "max_chunks_per_book": max_chunks_per_book,
            "max_chunk_retries": max_chunk_retries,
        },
    }
