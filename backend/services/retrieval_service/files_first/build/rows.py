from __future__ import annotations

import sqlite3
from typing import Any, Callable

from ..utils.metadata import extract_book_name, extract_chapter_title, build_section_key

DocsRow = tuple[Any, ...]
FtsRow = tuple[str, str, str, str, str, str, str, str, str, str]
ResolveSectionMetadataFn = Callable[..., dict[str, Any]]

INSERT_DOCS_SQL = (
    "INSERT OR REPLACE INTO docs "
    "(chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, "
    "book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
INSERT_DOCS_FTS_SQL = (
    "INSERT INTO docs_fts "
    "(chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def build_doc_index_rows(
    row: dict[str, Any],
    *,
    tokenizer: Any,
    resolve_section_metadata: ResolveSectionMetadataFn,
) -> tuple[DocsRow, FtsRow] | None:
    chunk_id = str(row.get("chunk_id", "")).strip()
    if not chunk_id:
        return None
    text = str(row.get("text", ""))
    filename = str(row.get("filename", ""))
    file_path = str(row.get("file_path", ""))
    page_number = int(row.get("page_number", 0) or 0)
    book_name = str(row.get("book_name", "")).strip() or extract_book_name(
        text=text,
        filename=filename,
        file_path=file_path,
    )
    chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(
        text=text,
        page_number=page_number,
        file_path=file_path,
    )
    section_key = str(row.get("section_key", "")).strip() or build_section_key(
        book_name=book_name,
        chapter_title=chapter_title,
        page_number=page_number,
        file_path=file_path,
    )
    metadata = resolve_section_metadata(
        section_key=section_key or chunk_id,
        book_name=book_name,
        chapter_title=chapter_title,
        section_text=text,
    )
    topic_tags_text = " ".join(metadata["topic_tags"])
    entity_tags_text = " ".join(metadata["entity_tags"])
    docs_row = (
        chunk_id,
        text,
        filename,
        str(row.get("file_type", "TXT")),
        file_path,
        page_number,
        int(row.get("chunk_idx", 0) or 0),
        str(row.get("parent_chunk_id", "")),
        str(row.get("root_chunk_id", "")),
        int(row.get("chunk_level", 0) or 0),
        book_name,
        chapter_title,
        section_key,
        metadata["section_summary"],
        topic_tags_text,
        entity_tags_text,
    )
    search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
    fts_row = (
        chunk_id,
        " ".join(tokenizer.tokenize(search_basis)),
        book_name,
        chapter_title,
        text,
        filename,
        file_path,
        metadata["section_summary"],
        topic_tags_text,
        entity_tags_text,
    )
    return docs_row, fts_row


def insert_doc_index_rows(conn: sqlite3.Connection, *, docs_rows: list[DocsRow], fts_rows: list[FtsRow]) -> None:
    if not docs_rows:
        return
    conn.executemany(INSERT_DOCS_SQL, docs_rows)
    conn.executemany(INSERT_DOCS_FTS_SQL, fts_rows)
