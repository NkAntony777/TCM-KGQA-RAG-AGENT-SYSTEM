from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


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
