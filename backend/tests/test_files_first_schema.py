from __future__ import annotations

import re
import sqlite3

from services.retrieval_service.files_first.build import schema as files_first_schema
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


def _metadata(**kwargs) -> dict[str, object]:
    text = str(kwargs.get("section_text", ""))
    return {
        "section_summary": text[:20],
        "topic_tags": ["功效"] if "功效" in text else [],
        "entity_tags": ["小柴胡汤"] if "小柴胡汤" in text else [],
        "representative_passages": [text[:40]] if text else [],
    }


def test_schema_status_reports_missing_and_current_schema() -> None:
    tmp_path = make_test_dir("files_first_schema")
    db_path = tmp_path / "retrieval_local_index.fts.db"
    try:
        assert files_first_schema.schema_status(db_path) == {"exists": False, "compatible": False, "version": 0}

        with connect_test_sqlite(db_path) as conn:
            files_first_schema.initialize_build_db(conn)
            files_first_schema.write_schema_version(conn)
            conn.commit()

        status = files_first_schema.schema_status(db_path)
        assert status["exists"] is True
        assert status["compatible"] is True
        assert status["version"] == files_first_schema.FILES_FIRST_SCHEMA_VERSION
    finally:
        cleanup_test_dir(tmp_path)


def test_migrate_legacy_schema_in_place_adds_metadata_and_fts() -> None:
    tmp_path = make_test_dir("files_first_schema")
    db_path = tmp_path / "retrieval_local_index.fts.db"
    try:
        with connect_test_sqlite(db_path) as conn:
            conn.execute(
                "CREATE TABLE docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT)"
            )
            conn.execute(
                "INSERT INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("leaf-1", "古籍：伤寒论\n篇名：卷上\n小柴胡汤功效在和解少阳。", "伤寒论.txt", "TXT", "classic://伤寒论/0001", 1, 0, "", "", 3, "", "", ""),
            )
            conn.commit()

        rows = files_first_schema.load_legacy_doc_rows(db_path)
        nav_rebuilt = {"called": False}

        def rebuild_nav_groups(conn: sqlite3.Connection) -> dict[str, int]:
            nav_rebuilt["called"] = True
            return files_first_schema.count_rows_in_db(db_path)

        files_first_schema.migrate_legacy_schema_in_place(
            db_path,
            rows,
            tokenizer=FakeTokenizer(),
            resolve_section_metadata=_metadata,
            rebuild_nav_groups=rebuild_nav_groups,
        )

        assert nav_rebuilt["called"] is True
        assert files_first_schema.schema_status(db_path)["compatible"] is True
        with connect_test_sqlite(db_path) as conn:
            row = conn.execute("SELECT book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags FROM docs").fetchone()
            fts_count = conn.execute("SELECT COUNT(1) FROM docs_fts").fetchone()[0]

        assert tuple(row[:3]) == ("伤寒论", "卷上", "伤寒论::0001")
        assert row[3].startswith("古籍：伤寒论")
        assert tuple(row[4:]) == ("功效", "小柴胡汤")
        assert fts_count == 1
    finally:
        cleanup_test_dir(tmp_path)
