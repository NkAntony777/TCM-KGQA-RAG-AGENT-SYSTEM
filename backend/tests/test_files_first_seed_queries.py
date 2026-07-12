from __future__ import annotations

import sqlite3

from services.retrieval_service.files_first.search import seed as files_first_seed_queries
from services.retrieval_service.files_first.build import schema as files_first_schema
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


def _in_clause(values: list[str], alias: str, column: str):
    placeholders = ",".join("?" for _ in values)
    return f" AND {alias}.{column} IN ({placeholders})", tuple(values)


def _compact(text: str) -> str:
    return text.replace("，", "").replace("。", "").replace(" ", "")


def _insert_doc(conn: sqlite3.Connection, *, chunk_id: str, book_name: str, chapter_title: str, text: str, entity_tags: str = "") -> None:
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
            chapter_title,
            f"{book_name}::0001",
            text[:30],
            "",
            entity_tags,
        ),
    )


def test_direct_seed_queries_collect_matching_rows_and_sections() -> None:
    tmp_path = make_test_dir("files_first_seed_queries")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        _insert_doc(conn, chunk_id="leaf-1", book_name="伤寒论", chapter_title="卷上", text="小柴胡汤功效在和解少阳。", entity_tags="小柴胡汤")
        _insert_doc(conn, chunk_id="leaf-2", book_name="金匮要略", chapter_title="卷下", text="桂枝汤。")
        conn.commit()

        rows, sections = files_first_seed_queries.run_direct_seed_queries(
            conn,
            direct_terms=["小柴胡汤"],
            leaf_level=3,
            effective_top_k=3,
            target_books=["伤寒论"],
            build_sqlite_in_clause=_in_clause,
            is_noisy_term=lambda _: False,
        )

    assert list(rows) == ["leaf-1"]
    assert sections == {"伤寒论::0001"}
    assert rows["leaf-1"]["_direct_clause_hits"] == 0


def test_clause_seed_queries_merge_hits_into_existing_seed_map() -> None:
    tmp_path = make_test_dir("files_first_seed_queries")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        _insert_doc(conn, chunk_id="leaf-1", book_name="伤寒论", chapter_title="卷上", text="小柴胡汤功效在和解少阳。")
        conn.commit()

        seed_map = {"leaf-1": {"chunk_id": "leaf-1", "section_key": "伤寒论::0001", "_direct_clause_hits": 0}}
        rows, sections = files_first_seed_queries.run_clause_seed_queries(
            conn,
            descriptive_clauses=["和解少阳"],
            leaf_level=3,
            effective_top_k=3,
            target_books=[],
            direct_seed_map=seed_map,
            unique_sections=set(),
            build_sqlite_in_clause=_in_clause,
            compact_phrase=_compact,
        )

    assert rows["leaf-1"]["_direct_clause_hits"] == 1
    assert sections == {"伤寒论::0001"}
