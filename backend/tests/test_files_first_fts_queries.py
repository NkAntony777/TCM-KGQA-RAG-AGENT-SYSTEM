from __future__ import annotations

import sqlite3
from typing import Any

from services.retrieval_service.files_first.search import fts as files_first_fts_queries
from services.retrieval_service.files_first.build import schema as files_first_schema
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


def _in_clause(values: list[str], alias: str, column: str) -> tuple[str, tuple[Any, ...]]:
    placeholders = ",".join("?" for _ in values)
    return f" AND {alias}.{column} IN ({placeholders})", tuple(values)


def _insert_doc(conn: sqlite3.Connection, *, chunk_id: str, book_name: str, section_key: str, text: str) -> None:
    conn.execute(
        """
        INSERT INTO docs (
            chunk_id, text, filename, file_type, file_path, page_number, chunk_idx,
            parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title,
            section_key, section_summary, topic_tags, entity_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            text,
            f"{book_name}.txt",
            "TXT",
            f"classic://{book_name}/0001",
            1,
            1,
            "",
            "",
            3,
            book_name,
            "卷上",
            section_key,
            "小柴胡汤功效",
            "功效",
            "小柴胡汤",
        ),
    )
    conn.execute(
        """
        INSERT INTO docs_fts (
            chunk_id, search_text, book_name, chapter_title, text, filename, file_path,
            section_summary, topic_tags, entity_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            f"{book_name} 小柴胡汤 功效 和解少阳",
            book_name,
            "卷上",
            text,
            f"{book_name}.txt",
            f"classic://{book_name}/0001",
            "小柴胡汤功效",
            "功效",
            "小柴胡汤",
        ),
    )


def _insert_nav_group(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO nav_groups (
            group_key, book_name, archetype, group_title, group_summary, topic_tags, entity_tags,
            representative_passages, question_types_supported, section_count, leaf_count,
            start_section_key, end_section_key, section_index_range, page_range, child_section_keys, child_titles
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "伤寒论::nav::0001",
            "伤寒论",
            "classic",
            "卷上",
            "小柴胡汤功效在和解少阳",
            '["功效"]',
            '["小柴胡汤"]',
            '["小柴胡汤主治往来寒热"]',
            '["source_quote"]',
            1,
            1,
            "伤寒论::0001",
            "伤寒论::0001",
            "[1, 1]",
            "[1, 1]",
            '["伤寒论::0001"]',
            '["卷上"]',
        ),
    )
    conn.execute(
        "INSERT INTO nav_groups_fts (group_key, search_text) VALUES (?, ?)",
        ("伤寒论::nav::0001", "伤寒论 小柴胡汤 功效 和解少阳"),
    )


def test_run_match_queries_returns_section_and_leaf_rows() -> None:
    tmp_path = make_test_dir("files_first_fts_queries")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        _insert_doc(conn, chunk_id="leaf-1", book_name="伤寒论", section_key="伤寒论::0001", text="小柴胡汤功效在和解少阳。")
        _insert_nav_group(conn)
        conn.commit()

        section_rows, rows, sections, error = files_first_fts_queries.run_match_queries(
            conn,
            match_queries=["小柴胡汤"],
            leaf_level=3,
            candidate_sections=[],
            candidate_books=["伤寒论"],
            candidate_groups=[],
            candidate_k=6,
            effective_top_k=5,
            build_sqlite_in_clause=_in_clause,
        )

    assert error is None
    assert [row["chunk_id"] for row in rows] == ["leaf-1"]
    assert [row["chunk_id"] for row in section_rows] == ["伤寒论::nav::0001"]
    assert sections == {"伤寒论::0001", "伤寒论::nav::0001"}
    assert rows[0]["_plan_rank"] == 0


def test_run_match_queries_reports_single_query_error_for_invalid_match() -> None:
    tmp_path = make_test_dir("files_first_fts_queries")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        section_rows, rows, sections, error = files_first_fts_queries.run_match_queries(
            conn,
            match_queries=['"unterminated'],
            leaf_level=3,
            candidate_sections=[],
            candidate_books=[],
            candidate_groups=[],
            candidate_k=6,
            effective_top_k=5,
            build_sqlite_in_clause=_in_clause,
        )

    assert section_rows == []
    assert rows == []
    assert sections == set()
    assert error == "fts_query_error"
