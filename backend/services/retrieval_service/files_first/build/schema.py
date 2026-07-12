from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from . import rows as build_rows

FILES_FIRST_SCHEMA_VERSION = 5
REQUIRED_DOC_COLUMNS = {
    "chunk_id",
    "text",
    "filename",
    "file_type",
    "file_path",
    "page_number",
    "chunk_idx",
    "parent_chunk_id",
    "root_chunk_id",
    "chunk_level",
    "book_name",
    "chapter_title",
    "section_key",
    "section_summary",
    "topic_tags",
    "entity_tags",
}

ResolveSectionMetadataFn = Callable[..., dict[str, Any]]
RebuildNavGroupsFn = Callable[[sqlite3.Connection], dict[str, Any]]


def initialize_build_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")
    conn.execute("CREATE TABLE IF NOT EXISTS files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT, section_summary TEXT, topic_tags TEXT, entity_tags TEXT)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nav_groups (group_key TEXT PRIMARY KEY, book_name TEXT, archetype TEXT, group_title TEXT, group_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, question_types_supported TEXT, section_count INTEGER, leaf_count INTEGER, start_section_key TEXT, end_section_key TEXT, section_index_range TEXT, page_range TEXT, child_section_keys TEXT, child_titles TEXT)"
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS nav_groups_fts USING fts5(group_key UNINDEXED, search_text)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS book_outlines (book_name TEXT PRIMARY KEY, archetype TEXT, book_summary TEXT, major_topics TEXT, major_entities TEXT, group_count INTEGER, section_count INTEGER, leaf_count INTEGER, group_keys TEXT, query_types_supported TEXT)"
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS book_outlines_fts USING fts5(book_name UNINDEXED, search_text)")
    conn.commit()


def ensure_post_docs_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_section_order ON docs(section_key, chunk_idx, page_number, chunk_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_book_chapter ON docs(book_name, chapter_title, section_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nav_groups_book ON nav_groups(book_name, group_key)")
    conn.commit()


def count_rows_in_db(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"docs": 0, "nav_groups": 0, "book_outlines": 0}
    with closing(sqlite3.connect(path)) as conn:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            "docs": int(conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0]) if "docs" in tables else 0,
            "nav_groups": int(conn.execute("SELECT COUNT(1) FROM nav_groups").fetchone()[0]) if "nav_groups" in tables else 0,
            "book_outlines": int(conn.execute("SELECT COUNT(1) FROM book_outlines").fetchone()[0]) if "book_outlines" in tables else 0,
        }


def schema_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "compatible": False, "version": 0}
    try:
        with closing(sqlite3.connect(path)) as conn:
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "docs" not in tables:
                return {"exists": True, "compatible": False, "version": 0}
            doc_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
            meta_version = 0
            if "files_first_meta" in tables:
                try:
                    row = conn.execute("SELECT value FROM files_first_meta WHERE key = 'schema_version' LIMIT 1").fetchone()
                    meta_version = int(row[0]) if row and row[0] is not None else 0
                except Exception:
                    meta_version = 0
            compatible = (
                doc_columns >= REQUIRED_DOC_COLUMNS
                and "nav_groups" in tables
                and "nav_groups_fts" in tables
                and "book_outlines" in tables
                and "book_outlines_fts" in tables
                and meta_version >= FILES_FIRST_SCHEMA_VERSION
            )
            return {"exists": True, "compatible": compatible, "version": meta_version}
    except Exception:
        return {"exists": True, "compatible": False, "version": 0}


def load_legacy_doc_rows(path: Path) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key
            FROM docs
            """
        ).fetchall()
    return [dict(row) for row in rows if isinstance(row, sqlite3.Row)]


def write_schema_version(conn: sqlite3.Connection, version: int = FILES_FIRST_SCHEMA_VERSION) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(version)),
    )


def _initialize_legacy_migration_tables(conn: sqlite3.Connection) -> None:
    existing_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
    for column in ("section_summary", "topic_tags", "entity_tags"):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE docs ADD COLUMN {column} TEXT")
    conn.execute("CREATE TABLE IF NOT EXISTS files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("DROP TABLE IF EXISTS docs_fts")
    conn.execute("DROP TABLE IF EXISTS sections")
    conn.execute("DROP TABLE IF EXISTS sections_fts")
    conn.execute(
        "CREATE VIRTUAL TABLE docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nav_groups (group_key TEXT PRIMARY KEY, book_name TEXT, archetype TEXT, group_title TEXT, group_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, question_types_supported TEXT, section_count INTEGER, leaf_count INTEGER, start_section_key TEXT, end_section_key TEXT, section_index_range TEXT, page_range TEXT, child_section_keys TEXT, child_titles TEXT)"
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS nav_groups_fts USING fts5(group_key UNINDEXED, search_text)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS book_outlines (book_name TEXT PRIMARY KEY, archetype TEXT, book_summary TEXT, major_topics TEXT, major_entities TEXT, group_count INTEGER, section_count INTEGER, leaf_count INTEGER, group_keys TEXT, query_types_supported TEXT)"
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS book_outlines_fts USING fts5(book_name UNINDEXED, search_text)")


def migrate_legacy_schema_in_place(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    tokenizer: Any,
    resolve_section_metadata: ResolveSectionMetadataFn,
    rebuild_nav_groups: RebuildNavGroupsFn,
) -> None:
    with closing(sqlite3.connect(path)) as conn:
        _initialize_legacy_migration_tables(conn)
        docs_rows: list[tuple[Any, ...]] = []
        fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
        for row in rows:
            payload = build_rows.build_doc_index_rows(
                row,
                tokenizer=tokenizer,
                resolve_section_metadata=resolve_section_metadata,
            )
            if payload is None:
                continue
            docs_row, fts_row = payload
            docs_rows.append(docs_row)
            fts_rows.append(fts_row)
        build_rows.insert_doc_index_rows(
            conn,
            docs_rows=docs_rows,
            fts_rows=fts_rows,
        )
        ensure_post_docs_indexes(conn)
        rebuild_nav_groups(conn)
        write_schema_version(conn)
        conn.commit()
