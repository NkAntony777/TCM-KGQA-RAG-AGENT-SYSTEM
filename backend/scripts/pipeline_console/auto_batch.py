from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable


PipelineFactory = Callable[[dict[str, Any] | None], Any]
RunExtractionJob = Callable[..., None]
LogFn = Callable[[str, str], None]
CleanupFn = Callable[[], None]
CompletedChunkLoader = Callable[[Path], set[tuple[str, int]]]
BookOverridesProvider = Callable[[], dict[str, list[str]]]


def manifest_has_full_book_scope(manifest_cfg: dict[str, Any]) -> bool:
    if manifest_cfg.get("max_chunks_per_book") not in (None, "", 0):
        return False
    if int(manifest_cfg.get("skip_initial_chunks_per_book", 0) or 0) != 0:
        return False
    if any(str(item).strip() for item in (manifest_cfg.get("chapter_excludes") or [])):
        return False
    return True


def is_full_completed_run(manifest: dict[str, Any], state: dict[str, Any]) -> bool:
    if bool(manifest.get("dry_run", False)):
        return False
    if str(state.get("status", "")).strip().lower() != "completed":
        return False

    manifest_cfg = manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}
    return manifest_has_full_book_scope(manifest_cfg)


def collect_completed_book_stems_from_run(
    manifest: dict[str, Any],
    state: dict[str, Any],
    run_dir: Path,
    *,
    pipeline_cls: type,
    pipeline_config_cls: type,
    default_books_dir: Path,
    load_completed_chunk_keys: CompletedChunkLoader,
) -> set[str]:
    processed: set[str] = set()
    if bool(manifest.get("dry_run", False)):
        return processed

    manifest_cfg = manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}
    if not manifest_has_full_book_scope(manifest_cfg):
        return processed

    book_paths = [Path(item) for item in manifest.get("books", []) if str(item).strip()]
    if not book_paths:
        return processed

    run_status = str(state.get("status", "")).strip().lower()
    if run_status == "completed":
        return {path.stem for path in book_paths}
    if run_status not in {"partial", "completed"}:
        return processed

    completed_chunk_keys = load_completed_chunk_keys(run_dir)
    if not completed_chunk_keys:
        return processed

    pipeline = pipeline_cls(
        pipeline_config_cls(
            books_dir=book_paths[0].parent if book_paths else default_books_dir,
            output_dir=run_dir,
            model=str(manifest.get("model", "") or "mimo-v2-pro"),
            api_key="dummy_for_processed_scan",
            base_url=str(manifest.get("base_url", "") or "https://api.siliconflow.cn/v1"),
            max_chunk_chars=int(manifest_cfg.get("max_chunk_chars", 800) if manifest_cfg.get("max_chunk_chars", None) is not None else 800),
            chunk_overlap=int(manifest_cfg.get("chunk_overlap", 200) if manifest_cfg.get("chunk_overlap", None) is not None else 200),
            chunk_strategy=str(manifest_cfg.get("chunk_strategy", "body_first")),
            parallel_workers=1,
            request_delay=0.0,
            max_retries=0,
        )
    )

    chapter_excludes = list(manifest_cfg.get("chapter_excludes", []))
    skip_initial_chunks = int(manifest_cfg.get("skip_initial_chunks_per_book", 0) or 0)
    chunk_strategy = str(manifest_cfg.get("chunk_strategy", "body_first"))

    for book_path in book_paths:
        if not book_path.exists():
            continue
        try:
            tasks = pipeline.schedule_book_chunks(
                book_path=book_path,
                chapter_excludes=chapter_excludes or None,
                max_chunks_per_book=None,
                skip_initial_chunks_per_book=skip_initial_chunks,
                chunk_strategy=chunk_strategy,
            )
        except Exception:
            continue
        if tasks and all((task.book_name, task.chunk_index) in completed_chunk_keys for task in tasks):
            processed.add(book_path.stem)
    return processed


def get_processed_book_stems(
    *,
    output_dir: Path,
    load_book_status_overrides: BookOverridesProvider,
    pipeline_cls: type,
    pipeline_config_cls: type,
    default_books_dir: Path,
    load_completed_chunk_keys: CompletedChunkLoader,
) -> set[str]:
    processed: set[str] = set()
    if not output_dir.exists():
        return processed
    for run_dir in output_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        state_path = run_dir / "state.json"
        if not manifest_path.exists() or not state_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            processed.update(
                collect_completed_book_stems_from_run(
                    manifest,
                    state,
                    run_dir,
                    pipeline_cls=pipeline_cls,
                    pipeline_config_cls=pipeline_config_cls,
                    default_books_dir=default_books_dir,
                    load_completed_chunk_keys=load_completed_chunk_keys,
                )
            )
        except Exception:
            continue
    processed -= set(load_book_status_overrides().get("force_unprocessed", []))
    return processed


def resolve_start_selected_books(pipeline: Any, raw_selected_books: list[str]) -> list[Path]:
    books = pipeline.discover_books()
    selected: list[Path] = []
    if raw_selected_books:
        for token in raw_selected_books:
            token = token.strip()
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(books):
                    selected.append(books[idx - 1])
            else:
                selected.extend([book for book in books if token in book.stem])
        seen: set[Path] = set()
        deduped = []
        for path in selected:
            if path not in seen:
                seen.add(path)
                deduped.append(path)
        return deduped
    return books


def exclude_processed_books_for_new_run(
    selected_books: list[Path],
    *,
    processed_stems: set[str],
) -> tuple[list[Path], list[str]]:
    skipped = [path.stem for path in selected_books if path.stem in processed_stems]
    kept = [path for path in selected_books if path.stem not in processed_stems]
    return kept, skipped


def sanitize_auto_batch_size(batch_size: int | None, *, default_batch_size: int) -> int:
    try:
        value = int(batch_size or default_batch_size)
    except (TypeError, ValueError):
        value = default_batch_size
    return max(1, value)


def ordered_unprocessed_books_for_new_run(
    pipeline: Any,
    *,
    processed_stems: set[str],
    batch_size: int | None,
    default_batch_size: int,
) -> tuple[list[Path], list[str]]:
    books = pipeline.discover_books()
    skipped = [path.stem for path in books if path.stem in processed_stems]
    remaining = [path for path in books if path.stem not in processed_stems]
    if not remaining:
        return [], skipped

    ordered: list[Path] = []
    seen: set[Path] = set()
    sanitized_batch_size = sanitize_auto_batch_size(batch_size, default_batch_size=default_batch_size)
    recommended = pipeline.recommend_books(limit=max(len(books), sanitized_batch_size))
    for path in recommended:
        if path.stem in processed_stems or path in seen:
            continue
        ordered.append(path)
        seen.add(path)
    for path in remaining:
        if path in seen:
            continue
        ordered.append(path)
        seen.add(path)
    return ordered, skipped


def select_auto_start_books(
    pipeline: Any,
    *,
    processed_stems: set[str],
    batch_size: int,
    default_batch_size: int,
) -> tuple[list[Path], list[str]]:
    ordered, skipped = ordered_unprocessed_books_for_new_run(
        pipeline,
        processed_stems=processed_stems,
        batch_size=batch_size,
        default_batch_size=default_batch_size,
    )
    sanitized_batch_size = sanitize_auto_batch_size(batch_size, default_batch_size=default_batch_size)
    return ordered[:sanitized_batch_size], skipped


def run_auto_extraction_batches(
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
    batch_size: int,
    default_batch_size: int,
    build_pipeline: PipelineFactory,
    run_extraction_job: RunExtractionJob,
    select_auto_start_books_fn: Callable[..., tuple[list[Path], list[str]]],
    job_cancelled: threading.Event,
    run_lock: threading.Lock,
    current_job: dict[str, Any],
    log: LogFn,
    cleanup_job_log_file: CleanupFn,
) -> None:
    selected_books = list(initial_selected_books)
    batch_index = 1
    sanitized_batch_size = sanitize_auto_batch_size(batch_size, default_batch_size=default_batch_size)
    try:
        while selected_books:
            batch_job_id = job_id if batch_index == 1 else f"{job_id}-b{batch_index}"
            resume_run_dir = initial_resume_run_dir if batch_index == 1 else None
            if batch_index > 1:
                log("info", f"自动续批启动 [{batch_index}]，共 {len(selected_books)} 本书")
            run_extraction_job(
                job_id=batch_job_id,
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
                cleanup_job_log_file=False,
            )
            if job_cancelled.is_set():
                return
            with run_lock:
                last_status = current_job.get("status")
            if last_status != "completed":
                return

            pipeline = build_pipeline(cfg_override)
            next_books, _ = select_auto_start_books_fn(pipeline, batch_size=sanitized_batch_size)
            if not next_books:
                log("info", "自动批处理完成，已无剩余未处理书籍")
                return

            batch_index += 1
            with run_lock:
                current_job.update(
                    {
                        "status": "running",
                        "phase": "preparing_next_batch",
                        "current_book": "",
                        "current_chapter": "",
                        "auto_chain_mode": True,
                        "auto_batch_index": batch_index,
                        "auto_batch_size": sanitized_batch_size,
                        "next_batch_books": [path.stem for path in next_books],
                    }
                )
            log("info", f"当前批次完成，准备自动开启下一批，共 {len(next_books)} 本书")
            selected_books = next_books
    finally:
        cleanup_job_log_file()
