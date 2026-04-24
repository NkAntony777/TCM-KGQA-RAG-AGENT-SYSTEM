from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


ResolveSelectedFn = Callable[[Any, list[str]], list[Path]]
SelectAutoFn = Callable[[Any], tuple[list[Path], list[str]]]


def prepare_start_selection(
    *,
    pipeline: Any,
    raw_selected_books: list[str],
    default_auto_batch_size: int,
    resolve_selected_books: ResolveSelectedFn,
    select_auto_start_books: SelectAutoFn,
) -> tuple[list[Path], list[str], bool, int]:
    auto_chain_mode = not raw_selected_books
    selected = resolve_selected_books(pipeline, raw_selected_books)
    auto_skipped_processed_books: list[str] = []
    if auto_chain_mode:
        selected, auto_skipped_processed_books = select_auto_start_books(pipeline)
    return selected, auto_skipped_processed_books, auto_chain_mode, default_auto_batch_size


def enabled_provider_has_api_key(pipeline: Any) -> bool:
    return any(provider.api_key for provider in pipeline.config.providers if provider.enabled)


def selected_books_from_manifest(manifest: dict[str, Any]) -> list[Path]:
    selected = [Path(item) for item in manifest.get("books", []) if str(item).strip()]
    return [path for path in selected if path.exists()]


def merge_resume_config(
    *,
    manifest: dict[str, Any],
    request_api_config: dict[str, Any],
    fixed_fields: set[str],
) -> dict[str, Any]:
    cfg_override = dict(manifest.get("config", {}))
    if manifest.get("model"):
        cfg_override["model"] = manifest.get("model")
    if manifest.get("base_url"):
        cfg_override["base_url"] = manifest.get("base_url")
    for key, value in request_api_config.items():
        if key in fixed_fields:
            continue
        if isinstance(value, str):
            if value.strip():
                cfg_override[key] = value
        elif value is not None:
            cfg_override[key] = value
    return cfg_override


def start_thread_kwargs(
    *,
    job_id: str,
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
    auto_chain_mode: bool,
    selected_books: list[Path],
    auto_batch_size: int,
) -> dict[str, Any]:
    thread_kwargs: dict[str, Any] = {
        "job_id": job_id,
        "label": label or "extraction",
        "dry_run": dry_run,
        "cfg_override": cfg_override,
        "chapter_excludes": chapter_excludes,
        "max_chunks_per_book": max_chunks_per_book,
        "skip_initial_chunks": skip_initial_chunks,
        "chunk_strategy": chunk_strategy,
        "auto_clean": auto_clean,
        "auto_publish": auto_publish,
        "max_chunk_retries": max_chunk_retries,
    }
    if auto_chain_mode:
        thread_kwargs["initial_selected_books"] = selected_books
        thread_kwargs["batch_size"] = auto_batch_size
    else:
        thread_kwargs["selected_books"] = selected_books
    return thread_kwargs


def resume_thread_kwargs(
    *,
    job_id: str,
    run_name: str,
    dry_run: bool,
    cfg_override: dict[str, Any],
    manifest_cfg: dict[str, Any],
    auto_clean: bool,
    auto_publish: bool,
    max_chunk_retries: int,
    auto_chain_mode: bool,
    selected_books: list[Path],
    run_dir: Path,
    default_auto_batch_size: int,
) -> dict[str, Any]:
    thread_kwargs: dict[str, Any] = {
        "job_id": job_id,
        "label": run_name,
        "dry_run": dry_run,
        "cfg_override": cfg_override,
        "chapter_excludes": list(manifest_cfg.get("chapter_excludes", [])),
        "max_chunks_per_book": manifest_cfg.get("max_chunks_per_book"),
        "skip_initial_chunks": int(manifest_cfg.get("skip_initial_chunks_per_book", 0) or 0),
        "chunk_strategy": str(manifest_cfg.get("chunk_strategy", "body_first")),
        "auto_clean": auto_clean,
        "auto_publish": auto_publish,
        "max_chunk_retries": max_chunk_retries,
    }
    if auto_chain_mode:
        thread_kwargs["initial_selected_books"] = selected_books
        thread_kwargs["initial_resume_run_dir"] = run_dir
        thread_kwargs["batch_size"] = default_auto_batch_size
    else:
        thread_kwargs["selected_books"] = selected_books
        thread_kwargs["resume_run_dir"] = run_dir
    return thread_kwargs


def start_response(
    *,
    job_id: str,
    selected_books: list[Path],
    auto_skipped_processed_books: list[str],
    auto_chain_mode: bool,
    auto_batch_size: int,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "selected_books": [book.stem for book in selected_books],
        "auto_skipped_processed_books": auto_skipped_processed_books,
        "auto_chain_mode": auto_chain_mode,
        "auto_batch_size": auto_batch_size if auto_chain_mode else 0,
        "message": "任务已启动",
    }


def resume_response(
    *,
    job_id: str,
    run_name: str,
    selected_books: list[Path],
    auto_chain_mode: bool,
    default_auto_batch_size: int,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "run_dir": run_name,
        "selected_books": [book.stem for book in selected_books],
        "auto_chain_mode": auto_chain_mode,
        "auto_batch_size": default_auto_batch_size if auto_chain_mode else 0,
        "message": "resume_started",
    }
