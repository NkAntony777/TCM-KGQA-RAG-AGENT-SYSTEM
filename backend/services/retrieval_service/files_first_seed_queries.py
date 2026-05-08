from __future__ import annotations

import sqlite3
from typing import Any, Callable

SqliteInClauseBuilder = Callable[[list[str], str, str], tuple[str, tuple[Any, ...]]]


def run_direct_seed_queries(
    conn: sqlite3.Connection,
    *,
    direct_terms: list[str],
    leaf_level: int,
    effective_top_k: int,
    target_books: list[str],
    build_sqlite_in_clause: SqliteInClauseBuilder,
    is_noisy_term: Callable[[str], bool],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    direct_seed_map: dict[str, dict[str, Any]] = {}
    unique_sections: set[str] = set()
    docs_book_filter_sql = ""
    docs_book_filter_params: tuple[Any, ...] = ()
    if target_books:
        docs_book_filter_sql, docs_book_filter_params = build_sqlite_in_clause(target_books, "d", "book_name")
    for direct_term in direct_terms[:10]:
        normalized_term = str(direct_term or "").strip()
        if len(normalized_term) < 2 or is_noisy_term(normalized_term):
            continue
        try:
            current_direct = conn.execute(
                f"""
                SELECT
                    d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                    '[]' AS representative_passages,
                    substr(d.text, 1, 180) AS match_snippet,
                    -40.0 AS rank_score
                FROM docs d
                WHERE d.chunk_level = ?
                  AND (
                        d.chapter_title = ?
                     OR instr(d.chapter_title, ?) > 0
                     OR instr(d.entity_tags, ?) > 0
                     OR (? != '' AND length(?) >= 3 AND instr(d.text, ?) > 0)
                  ){docs_book_filter_sql}
                ORDER BY
                    CASE WHEN d.chapter_title = ? THEN 0 ELSE 1 END,
                    CASE WHEN instr(d.chapter_title, ?) > 0 THEN 0 ELSE 1 END,
                    CASE WHEN instr(d.entity_tags, ?) > 0 THEN 0 ELSE 1 END,
                    d.book_name ASC,
                    d.page_number ASC,
                    d.chunk_idx ASC
                LIMIT ?
                """,
                (
                    leaf_level,
                    normalized_term,
                    normalized_term,
                    normalized_term,
                    normalized_term,
                    normalized_term,
                    normalized_term,
                    *docs_book_filter_params,
                    normalized_term,
                    normalized_term,
                    normalized_term,
                    max(effective_top_k * 2, 8),
                ),
            ).fetchall()
        except sqlite3.OperationalError:
            current_direct = []
        for row in current_direct:
            payload = dict(row)
            payload["_plan_rank"] = 0
            payload["_direct_clause_hits"] = 0
            direct_seed_map[str(payload.get("chunk_id") or "")] = payload
            section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
            if section_key:
                unique_sections.add(section_key)
    return direct_seed_map, unique_sections


def run_clause_seed_queries(
    conn: sqlite3.Connection,
    *,
    descriptive_clauses: list[str],
    leaf_level: int,
    effective_top_k: int,
    target_books: list[str],
    direct_seed_map: dict[str, dict[str, Any]],
    unique_sections: set[str],
    build_sqlite_in_clause: SqliteInClauseBuilder,
    compact_phrase: Callable[[str], str],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    clause_book_filter_sql = ""
    clause_book_filter_params: tuple[Any, ...] = ()
    if target_books:
        clause_book_filter_sql, clause_book_filter_params = build_sqlite_in_clause(target_books, "d", "book_name")
    for clause in descriptive_clauses[:8]:
        normalized_clause = str(clause or "").strip()
        if len(normalized_clause) < 3:
            continue
        compact_clause = compact_phrase(normalized_clause)
        try:
            clause_rows = conn.execute(
                f"""
                SELECT
                    d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                    '[]' AS representative_passages,
                    substr(d.text, 1, 180) AS match_snippet,
                    -35.0 AS rank_score
                FROM docs d
                WHERE d.chunk_level = ?
                  AND (
                        instr(d.chapter_title, ?) > 0
                     OR instr(d.section_summary, ?) > 0
                     OR instr(d.text, ?) > 0
                     OR (? != '' AND length(?) >= 4 AND instr(
                            replace(replace(replace(replace(replace(replace(replace(d.text, '，', ''), '。', ''), '、', ''), ' ', ''), '：', ''), '；', ''), '（', ''),
                            ?
                        ) > 0)
                  ){clause_book_filter_sql}
                LIMIT ?
                """,
                (
                    leaf_level,
                    normalized_clause,
                    normalized_clause,
                    normalized_clause,
                    compact_clause,
                    compact_clause,
                    compact_clause,
                    *clause_book_filter_params,
                    max(effective_top_k * 2, 8),
                ),
            ).fetchall()
        except sqlite3.OperationalError:
            clause_rows = []
        for row in clause_rows:
            payload = dict(row)
            chunk_id = str(payload.get("chunk_id") or "").strip()
            if not chunk_id:
                continue
            existing_payload = direct_seed_map.get(chunk_id)
            if existing_payload is None:
                payload["_plan_rank"] = 0
                payload["_direct_clause_hits"] = 1
                direct_seed_map[chunk_id] = payload
            else:
                existing_payload["_direct_clause_hits"] = int(existing_payload.get("_direct_clause_hits", 0) or 0) + 1
            section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
            if section_key:
                unique_sections.add(section_key)
    return direct_seed_map, unique_sections
