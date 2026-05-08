from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from services.retrieval_service import files_first_schema
from services.retrieval_service import files_first_search
from services.retrieval_service.files_first_support import LocalFilesFirstStore
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


class MissingContext:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.tokenizer = FakeTokenizer()
        self.ensure_calls = 0

    def ensure_schema(self) -> dict[str, Any]:
        self.ensure_calls += 1
        return {"exists": False}


def _row() -> dict[str, Any]:
    return {
        "chunk_id": "leaf-1",
        "text": "古籍：伤寒论\n篇名：卷上\n小柴胡汤功效在和解少阳。",
        "filename": "伤寒论.txt",
        "file_path": "classic://伤寒论/0001",
        "page_number": 1,
        "chunk_idx": 1,
        "chunk_level": 3,
        "parent_chunk_id": "",
        "root_chunk_id": "",
    }


def test_files_first_search_returns_missing_when_store_absent() -> None:
    context = MissingContext(Path("missing-files-first.db"))

    rows, mode = files_first_search.search(
        context,
        query="小柴胡汤",
        top_k=3,
        candidate_k=6,
        leaf_level=3,
    )

    assert rows == []
    assert mode == "fts_missing"
    assert context.ensure_calls == 1


def test_files_first_search_returns_empty_for_unusable_query() -> None:
    tmp_path = make_test_dir("files_first_search")
    try:
        db_path = tmp_path / "files_first.db"
        with connect_test_sqlite(db_path) as conn:
            files_first_schema.initialize_build_db(conn)
        context = MissingContext(db_path)

        rows, mode = files_first_search.search(
            context,
            query="。",
            top_k=3,
            candidate_k=6,
            leaf_level=3,
        )

        assert rows == []
        assert mode == "fts_query_empty"
    finally:
        cleanup_test_dir(tmp_path)


def test_local_files_first_store_search_delegates_to_search_module() -> None:
    tmp_path = make_test_dir("files_first_search")
    try:
        store = LocalFilesFirstStore(tmp_path / "files_first.db", tokenizer=FakeTokenizer())
        store.rebuild([_row()], reset=True)

        rows, mode = store.search(
            query="小柴胡汤 功效 和解少阳",
            top_k=3,
            candidate_k=6,
            leaf_level=3,
        )

        assert mode == "fts_local"
        assert rows
        assert rows[0]["file_type"] == "SECTION"
        assert rows[0]["book_name"] == "伤寒论"
    finally:
        cleanup_test_dir(tmp_path)
