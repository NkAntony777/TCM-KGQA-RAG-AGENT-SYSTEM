"""Metadata candidate collection for files-first retrieval."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from services.retrieval_service import files_first_methods as ffm


def gather_metadata_candidates(
    conn: sqlite3.Connection,
    *,
    query: str,
    focus_entities: list[str],
    query_terms: list[str],
    books_in_query: list[str],
    flags: dict[str, bool],
    limit: int,
) -> dict[str, list[str]]:
    candidate_books: list[str] = []
    candidate_sections: list[str] = []
    candidate_groups: list[str] = []
    seen_books: set[str] = set()
    seen_sections: set[str] = set()
    seen_groups: set[str] = set()

    def push_book(book_name: str) -> None:
        normalized = str(book_name or "").strip()
        if not normalized or normalized in seen_books:
            return
        seen_books.add(normalized)
        candidate_books.append(normalized)

    def push_section(section_key: str) -> None:
        normalized = str(section_key or "").strip()
        if not normalized or normalized in seen_sections:
            return
        seen_sections.add(normalized)
        candidate_sections.append(normalized)

    def push_group(group_key: str) -> None:
        normalized = str(group_key or "").strip()
        if not normalized or normalized in seen_groups:
            return
        seen_groups.add(normalized)
        candidate_groups.append(normalized)

    conn.row_factory = sqlite3.Row
    for book in ffm._db_books_in_query(conn, query=query, focus_entities=focus_entities, limit=max(8, limit // 2)):
        push_book(book)
    if ffm._is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
        rows = conn.execute(
            """
            SELECT book_name
            FROM book_outlines
            WHERE instr(book_name, '本草') > 0
            LIMIT ?
            """,
            (max(8, limit),),
        ).fetchall()
        for row in rows:
            push_book(str(row["book_name"] or ""))
    for book in books_in_query:
        push_book(book)
        rows = conn.execute(
            """
            SELECT DISTINCT book_name
            FROM book_outlines
            WHERE book_name = ? OR instr(book_name, ?) > 0
            LIMIT ?
            """,
            (book, book, max(4, limit // 2)),
        ).fetchall()
        for row in rows:
            push_book(str(row["book_name"] or ""))
        rows = conn.execute(
            """
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE book_name = ? OR instr(book_name, ?) > 0
            LIMIT ?
            """,
            (book, book, max(4, limit // 2)),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:24]:
                push_section(str(item))

    entity_limit = max(4, min(limit, 24))
    for entity in focus_entities[:4]:
        rows = conn.execute(
            """
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE group_title = ?
               OR instr(group_title, ?) > 0
               OR instr(entity_tags, ?) > 0
               OR instr(topic_tags, ?) > 0
               OR instr(group_summary, ?) > 0
            LIMIT ?
            """,
            (entity, entity, entity, entity, entity, entity_limit),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:24]:
                push_section(str(item))
        if ffm._is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
            rows = conn.execute(
                """
                SELECT DISTINCT section_key, book_name
                FROM docs
                WHERE chunk_level = 3
                  AND instr(book_name, '本草') > 0
                  AND (
                        chapter_title = ?
                     OR instr(chapter_title, ?) > 0
                     OR instr(text, ?) > 0
                  )
                LIMIT ?
                """,
                (entity, entity, entity, max(10, limit)),
            ).fetchall()
            for row in rows:
                push_section(str(row["section_key"] or ""))
                push_book(str(row["book_name"] or ""))
        if not books_in_query and len(entity) >= 2:
            rows = conn.execute(
                """
                SELECT DISTINCT section_key, book_name
                FROM docs
                WHERE chunk_level = 3
                  AND (
                        chapter_title = ?
                     OR instr(chapter_title, ?) > 0
                  )
                LIMIT ?
                """,
                (entity, entity, max(8, limit)),
            ).fetchall()
            for row in rows:
                push_section(str(row["section_key"] or ""))
                push_book(str(row["book_name"] or ""))

    direct_terms = list(dict.fromkeys([*focus_entities, *query_terms[:8]]))
    book_filter_values = candidate_books[:8]
    book_filter_sql = ""
    if book_filter_values:
        placeholders = ",".join("?" for _ in book_filter_values)
        book_filter_sql = f" AND book_name IN ({placeholders})"
    for term in direct_terms[:10]:
        normalized = str(term or "").strip()
        if len(normalized) < 2 or ffm._is_noisy_term(normalized):
            continue
        params: list[Any] = []
        params.extend(book_filter_values)
        params.extend([normalized, normalized, normalized, normalized, normalized, entity_limit])
        rows = conn.execute(
            f"""
            SELECT DISTINCT section_key, book_name
            FROM docs
            WHERE chunk_level = 3
              AND trim(COALESCE(section_key, '')) <> ''
              {book_filter_sql}
              AND (
                    chapter_title = ?
                 OR instr(chapter_title, ?) > 0
                 OR instr(section_summary, ?) > 0
                 OR instr(entity_tags, ?) > 0
                 OR instr(text, ?) > 0
              )
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        for row in rows:
            push_section(str(row["section_key"] or ""))
            push_book(str(row["book_name"] or ""))

    if flags.get("source_query") and candidate_books:
        rows = conn.execute(
            f"""
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE book_name IN ({",".join("?" for _ in candidate_books[:8])})
            ORDER BY group_key ASC
            LIMIT ?
            """,
            (*candidate_books[:8], max(8, limit)),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:16]:
                push_section(str(item))

    return {
        "candidate_books": candidate_books[:8],
        "candidate_groups": candidate_groups[:32],
        "candidate_sections": candidate_sections[: max(8, min(limit, 96))],
    }
