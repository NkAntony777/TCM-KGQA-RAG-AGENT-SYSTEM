from __future__ import annotations

import sqlite3
from typing import Any, Callable

SqliteInClauseBuilder = Callable[[list[str], str, str], tuple[str, tuple[Any, ...]]]


def _add_section_key(unique_sections: set[str], payload: dict[str, Any]) -> None:
    section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
    if section_key:
        unique_sections.add(section_key)


def run_match_queries(
    conn: sqlite3.Connection,
    *,
    match_queries: list[str],
    leaf_level: int,
    candidate_sections: list[str],
    candidate_books: list[str],
    candidate_groups: list[str],
    candidate_k: int,
    effective_top_k: int,
    build_sqlite_in_clause: SqliteInClauseBuilder,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], str | None]:
    section_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    unique_sections: set[str] = set()
    section_limit = max(6, min(candidate_k * 2, max(effective_top_k * 2, 12)))
    leaf_limit = max(candidate_k * 2, effective_top_k * 2)

    for plan_rank, match_query in enumerate(match_queries):
        section_filter_sql = ""
        section_filter_params: tuple[Any, ...] = ()
        docs_filter_sql = ""
        docs_filter_params: tuple[Any, ...] = ()
        if candidate_sections:
            docs_filter_sql, docs_filter_params = build_sqlite_in_clause(candidate_sections[:96], "d", "section_key")
        elif candidate_books:
            docs_filter_sql, docs_filter_params = build_sqlite_in_clause(candidate_books[:8], "d", "book_name")
        if candidate_groups:
            section_filter_sql, section_filter_params = build_sqlite_in_clause(candidate_groups[:96], "n", "group_key")
        elif candidate_books:
            section_filter_sql, section_filter_params = build_sqlite_in_clause(candidate_books[:8], "n", "book_name")
        try:
            current_sections = conn.execute(
                f"""
                SELECT
                    n.group_key AS chunk_id,
                    trim(COALESCE(n.group_summary, '') || ' ' || COALESCE(n.representative_passages, '')) AS text,
                    n.book_name AS filename,'NAV_GROUP' AS file_type,'classic://' || n.book_name || '/nav-group-' || replace(substr(n.group_key, instr(n.group_key, '::nav::') + 7), '::', '-') AS file_path,0 AS page_number,
                    0 AS chunk_idx,'' AS parent_chunk_id,'' AS root_chunk_id,1 AS chunk_level,
                    n.book_name,n.group_title AS chapter_title,n.group_key AS section_key,n.group_summary AS section_summary,n.topic_tags,n.entity_tags,n.representative_passages,
                    substr(COALESCE(n.group_summary, n.group_title, ''), 1, 160) AS match_snippet,
                    bm25(nav_groups_fts) AS rank_score
                FROM nav_groups_fts
                JOIN nav_groups n ON n.group_key = nav_groups_fts.group_key
                WHERE nav_groups_fts MATCH ?{section_filter_sql}
                ORDER BY rank_score
                LIMIT ?
                """,
                (match_query, *section_filter_params, section_limit),
            ).fetchall()
        except sqlite3.OperationalError:
            current_sections = []
        try:
            current_rows = conn.execute(
                f"""
                SELECT
                    d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                    '[]' AS representative_passages,
                    snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                    bm25(docs_fts, 2.5, 3.4, 2.6, 1.0, 0.25, 0.2, 1.4, 1.2, 1.2) AS rank_score
                FROM docs_fts
                JOIN docs d ON d.chunk_id = docs_fts.chunk_id
                WHERE docs_fts MATCH ? AND d.chunk_level = ?{docs_filter_sql}
                ORDER BY rank_score
                LIMIT ?
                """,
                (match_query, leaf_level, *docs_filter_params, leaf_limit),
            ).fetchall()
        except sqlite3.OperationalError:
            current_rows = []
        if not current_sections and not current_rows and plan_rank == 0 and len(match_queries) == 1:
            return section_rows, rows, unique_sections, "fts_query_error"
        for row in current_sections:
            payload = dict(row)
            payload["_plan_rank"] = plan_rank
            section_rows.append(payload)
            _add_section_key(unique_sections, payload)
        for row in current_rows:
            payload = dict(row)
            payload["_plan_rank"] = plan_rank
            rows.append(payload)
            _add_section_key(unique_sections, payload)
        if plan_rank == 0 and len(unique_sections) >= max(effective_top_k * 2, min(candidate_k * 2, effective_top_k * 2)):
            break
        if len(unique_sections) >= max(effective_top_k * 2, candidate_k * 2):
            break
    return section_rows, rows, unique_sections, None
