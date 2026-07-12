from __future__ import annotations

import sqlite3
from pathlib import Path

from services.retrieval_service.files_first.search import reader as files_first_reader
from services.retrieval_service.files_first.utils import metadata as files_first_metadata
from services.retrieval_service.files_first.build import schema as files_first_schema
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


class MemorySummaryCache:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        return self.rows.get(key)


class ReaderContext:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.summary_cache = MemorySummaryCache()
        self.strip_classic_headers = files_first_metadata.strip_classic_headers
        self.merge_section_bodies = files_first_metadata.merge_section_bodies
        self.resolved: list[dict] = []

    def ensure_schema(self) -> dict:
        return files_first_schema.schema_status(self.store_path)

    def resolve_section_metadata(self, **kwargs) -> dict:
        self.resolved.append(kwargs)
        return {
            "section_summary": "generated summary",
            "topic_tags": ["功效"],
            "entity_tags": ["小柴胡汤"],
            "representative_passages": ["generated passage"],
        }


def _insert_doc(conn: sqlite3.Connection, *, chunk_id: str, text: str, chunk_idx: int) -> None:
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
            "伤寒论.txt",
            "TXT",
            "classic://伤寒论/0001",
            1,
            chunk_idx,
            "",
            "",
            3,
            "伤寒论",
            "卷上",
            "伤寒论::0001",
            "",
            "",
            "",
        ),
    )


def test_files_first_reader_uses_explicit_context_for_section_metadata() -> None:
    tmp_path = make_test_dir("files_first_reader")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        _insert_doc(conn, chunk_id="leaf-1", text="古籍：伤寒论\n篇名：卷上\n小柴胡汤功效在和解少阳。", chunk_idx=1)
        _insert_doc(conn, chunk_id="leaf-2", text="古籍：伤寒论\n篇名：卷上\n方后注可见加减。", chunk_idx=2)
        conn.commit()

    context = ReaderContext(db_path)
    result = files_first_reader.read_section(context, path="chapter://伤寒论/卷上")

    assert result["status"] == "ok"
    assert result["section"]["section_summary"] == "generated summary"
    assert result["section"]["topic_tags"] == ["功效"]
    assert "古籍：" not in result["section"]["text"]
    assert context.resolved
    assert context.resolved[0]["section_key"] == "伤寒论::0001"


def test_files_first_reader_get_docs_by_chunk_ids_uses_context_store_path() -> None:
    tmp_path = make_test_dir("files_first_reader")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        _insert_doc(conn, chunk_id="leaf-1", text="古籍：伤寒论\n篇名：卷上\n小柴胡汤。", chunk_idx=1)
        conn.commit()

    rows = files_first_reader.get_docs_by_chunk_ids(ReaderContext(db_path), ["leaf-1", "", "missing"])

    assert len(rows) == 1
    assert rows[0]["chunk_id"] == "leaf-1"
