from __future__ import annotations

import re

from services.retrieval_service import files_first_build_rows
from services.retrieval_service import files_first_schema
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


def test_build_doc_index_rows_derives_classic_metadata() -> None:
    payload = files_first_build_rows.build_doc_index_rows(
        {
            "chunk_id": "leaf-1",
            "text": "古籍：伤寒论\n篇名：卷上\n小柴胡汤功效在和解少阳。",
            "filename": "伤寒论.txt",
            "file_path": "classic://伤寒论/0001",
            "page_number": 1,
            "chunk_idx": 2,
            "chunk_level": 3,
            "parent_chunk_id": "parent-1",
            "root_chunk_id": "root-1",
        },
        tokenizer=FakeTokenizer(),
        resolve_section_metadata=lambda **_: {
            "section_summary": "小柴胡汤功效在和解少阳",
            "topic_tags": ["功效"],
            "entity_tags": ["小柴胡汤"],
        },
    )

    assert payload is not None
    docs_row, fts_row = payload
    assert docs_row == (
        "leaf-1",
        "古籍：伤寒论\n篇名：卷上\n小柴胡汤功效在和解少阳。",
        "伤寒论.txt",
        "TXT",
        "classic://伤寒论/0001",
        1,
        2,
        "parent-1",
        "root-1",
        3,
        "伤寒论",
        "卷上",
        "伤寒论::0001",
        "小柴胡汤功效在和解少阳",
        "功效",
        "小柴胡汤",
    )
    assert fts_row[0] == "leaf-1"
    assert "小柴胡汤功效在和解少阳" in fts_row[1]
    assert fts_row[2:4] == ("伤寒论", "卷上")


def test_insert_doc_index_rows_writes_docs_and_fts() -> None:
    tmp_path = make_test_dir("files_first_build_rows")
    db_path = tmp_path / "files_first.db"
    try:
        payload = files_first_build_rows.build_doc_index_rows(
            {"chunk_id": "leaf-1", "text": "古籍：伤寒论\n篇名：卷上\n小柴胡汤。", "filename": "伤寒论.txt", "file_path": "classic://伤寒论/0001"},
            tokenizer=FakeTokenizer(),
            resolve_section_metadata=lambda **_: {"section_summary": "小柴胡汤", "topic_tags": [], "entity_tags": []},
        )
        assert payload is not None
        docs_row, fts_row = payload

        with connect_test_sqlite(db_path) as conn:
            files_first_schema.initialize_build_db(conn)
            files_first_build_rows.insert_doc_index_rows(conn, docs_rows=[docs_row], fts_rows=[fts_row])
            conn.commit()
            docs_count = conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0]
            fts_count = conn.execute("SELECT COUNT(1) FROM docs_fts").fetchone()[0]

        assert docs_count == 1
        assert fts_count == 1
    finally:
        cleanup_test_dir(tmp_path)
