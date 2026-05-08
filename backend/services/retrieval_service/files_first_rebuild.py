from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Protocol

from services.retrieval_service import files_first_build_rows
from services.retrieval_service import files_first_build_state
from services.retrieval_service import files_first_schema


class FilesFirstRebuildContext(Protocol):
    store_path: Path
    tokenizer: Any

    def _default_state_path(self) -> Path:
        ...

    def _count_rows_in_db(self, path: Path) -> dict[str, int]:
        ...

    def _initialize_build_db(self, conn: sqlite3.Connection) -> None:
        ...

    def _ensure_post_docs_indexes(self, conn: sqlite3.Connection) -> None:
        ...

    def _rebuild_nav_groups(self, conn: sqlite3.Connection, *, show_progress: bool) -> dict[str, Any]:
        ...

    def _unlink_with_retry(self, path: Path) -> None:
        ...

    def _replace_file(self, target_path: Path, replacement_path: Path) -> None:
        ...

    def _print_stage_banner(self, *, stage: str, detail: str) -> None:
        ...

    def _print_build_progress(self, *, stage: str, done: int, total: int, started_at: float) -> None:
        ...

    def resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        ...


def _reuse_existing_docs(
    context: FilesFirstRebuildContext,
    *,
    rows: list[dict[str, Any]],
    state_path: Path,
    show_progress: bool,
    existing_docs: int,
) -> dict[str, Any]:
    state = files_first_build_state.reuse_existing_docs_state(target_path=context.store_path, total_rows=len(rows))
    files_first_build_state.write_json(state_path, state)
    with closing(sqlite3.connect(context.store_path)) as conn:
        context._initialize_build_db(conn)
        if show_progress:
            context._print_stage_banner(stage="docs", detail=f"reusing existing docs rows={existing_docs}")
            context._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
        context._ensure_post_docs_indexes(conn)
        nav_manifest = context._rebuild_nav_groups(conn, show_progress=show_progress)
        files_first_build_state.mark_nav_groups_running(state_path, state, nav_groups_built=int(nav_manifest.get("nav_groups", 0)))
        files_first_schema.write_schema_version(conn)
        conn.commit()
    files_first_build_state.mark_completed(
        state_path,
        state,
        docs_processed=len(rows),
        nav_groups_built=int(nav_manifest.get("nav_groups", 0)),
        reused_existing_docs=True,
    )
    return files_first_build_state.rebuild_result(
        rows_count=len(rows),
        nav_groups_built=int(nav_manifest.get("nav_groups", 0)),
        store_path=context.store_path,
        state_path=state_path,
        resumed=True,
        reused_existing_docs=True,
    )


def _insert_doc_batches(
    context: FilesFirstRebuildContext,
    *,
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    state_path: Path,
    state: dict[str, Any],
    docs_processed: int,
    batch_size: int,
    show_progress: bool,
    started_at: float,
) -> int:
    payload_rows: list[files_first_build_rows.DocsRow] = []
    fts_rows: list[files_first_build_rows.FtsRow] = []
    for index in range(docs_processed, len(rows)):
        payload = files_first_build_rows.build_doc_index_rows(
            rows[index],
            tokenizer=context.tokenizer,
            resolve_section_metadata=context.resolve_section_metadata,
        )
        if payload is None:
            continue
        docs_row, fts_row = payload
        payload_rows.append(docs_row)
        fts_rows.append(fts_row)
        if len(payload_rows) >= batch_size:
            files_first_build_rows.insert_doc_index_rows(conn, docs_rows=payload_rows, fts_rows=fts_rows)
            conn.commit()
            docs_processed = index + 1
            files_first_build_state.mark_docs_progress(state_path, state, docs_processed)
            if show_progress:
                context._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=started_at)
            payload_rows = []
            fts_rows = []
    if payload_rows:
        files_first_build_rows.insert_doc_index_rows(conn, docs_rows=payload_rows, fts_rows=fts_rows)
        conn.commit()
        docs_processed = len(rows)
        files_first_build_state.mark_docs_progress(state_path, state, docs_processed)
        if show_progress:
            context._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=started_at)
    return docs_processed


def rebuild(
    context: FilesFirstRebuildContext,
    rows: list[dict[str, Any]],
    *,
    state_path: Path | None = None,
    reset: bool = False,
    show_progress: bool = False,
    batch_size: int = 512,
) -> dict[str, Any]:
    target_path = context.store_path
    temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
    state_path = state_path or context._default_state_path()
    existing_target_counts = context._count_rows_in_db(target_path)
    reuse_existing_docs = (
        not reset
        and existing_target_counts["docs"] >= len(rows)
        and existing_target_counts["nav_groups"] <= 0
    )
    if reuse_existing_docs:
        return _reuse_existing_docs(
            context,
            rows=rows,
            state_path=state_path,
            show_progress=show_progress,
            existing_docs=existing_target_counts["docs"],
        )

    if reset:
        if temp_path.exists():
            context._unlink_with_retry(temp_path)
        if state_path.exists():
            context._unlink_with_retry(state_path)
    state = files_first_build_state.load_state(state_path)
    resume_ready = files_first_build_state.is_resume_ready(state=state, temp_path=temp_path, total_rows=len(rows))
    if not resume_ready and temp_path.exists():
        context._unlink_with_retry(temp_path)
    if not resume_ready:
        with closing(sqlite3.connect(temp_path)) as conn:
            context._initialize_build_db(conn)
        state = files_first_build_state.new_build_state(temp_path=temp_path, target_path=target_path, total_rows=len(rows))
        files_first_build_state.write_json(state_path, state)

    batch_size = max(64, int(batch_size or 512))
    docs_started_at = time.perf_counter()
    try:
        with closing(sqlite3.connect(temp_path)) as conn:
            context._initialize_build_db(conn)
            docs_processed = int(state.get("docs_processed", 0) or 0)
            if docs_processed < len(rows):
                docs_processed = _insert_doc_batches(
                    context,
                    conn=conn,
                    rows=rows,
                    state_path=state_path,
                    state=state,
                    docs_processed=docs_processed,
                    batch_size=batch_size,
                    show_progress=show_progress,
                    started_at=docs_started_at,
                )

            if show_progress:
                context._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
            context._ensure_post_docs_indexes(conn)
            files_first_build_state.mark_nav_groups_running(state_path, state, docs_processed=len(rows))
            nav_manifest = context._rebuild_nav_groups(conn, show_progress=show_progress)
            files_first_build_state.mark_nav_groups_running(state_path, state, nav_groups_built=int(nav_manifest.get("nav_groups", 0)))
            files_first_schema.write_schema_version(conn)
            conn.commit()
    except KeyboardInterrupt:
        files_first_build_state.mark_interrupted(state_path, state)
        raise
    except Exception as exc:
        files_first_build_state.mark_failed(state_path, state, exc)
        raise
    context._replace_file(target_path, temp_path)
    nav_groups_built = int(nav_manifest.get("nav_groups", 0) if "nav_manifest" in locals() else 0)
    files_first_build_state.mark_completed(
        state_path,
        state,
        docs_processed=len(rows),
        nav_groups_built=nav_groups_built,
    )
    return files_first_build_state.rebuild_result(
        rows_count=len(rows),
        nav_groups_built=nav_groups_built,
        store_path=context.store_path,
        state_path=state_path,
        resumed=bool(resume_ready),
    )
