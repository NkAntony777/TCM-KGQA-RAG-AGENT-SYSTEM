from __future__ import annotations

import gc
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from services.retrieval_service.files_first.build import state as files_first_build_state
from services.retrieval_service.files_first.build import pipeline as files_first_rebuild
from services.retrieval_service.files_first.build import schema as files_first_schema
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import make_test_dir


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


class RebuildContext:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.tokenizer = FakeTokenizer()
        self.nav_calls = 0

    def _default_state_path(self) -> Path:
        return files_first_build_state.default_state_path(self.store_path)

    def _count_rows_in_db(self, path: Path) -> dict[str, int]:
        return files_first_schema.count_rows_in_db(path)

    def _initialize_build_db(self, conn: sqlite3.Connection) -> None:
        files_first_schema.initialize_build_db(conn)

    def _ensure_post_docs_indexes(self, conn: sqlite3.Connection) -> None:
        files_first_schema.ensure_post_docs_indexes(conn)

    def _rebuild_nav_groups(self, conn: sqlite3.Connection, *, show_progress: bool) -> dict[str, Any]:
        self.nav_calls += 1
        return {"nav_groups": int(conn.execute("SELECT COUNT(DISTINCT section_key) FROM docs").fetchone()[0])}

    def _unlink_with_retry(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def _replace_file(self, target_path: Path, replacement_path: Path) -> None:
        replacement_path.replace(target_path)

    def _print_stage_banner(self, *, stage: str, detail: str) -> None:
        return None

    def _print_build_progress(self, *, stage: str, done: int, total: int, started_at: float) -> None:
        return None

    def resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        return {
            "section_summary": section_text[:20],
            "topic_tags": ["功效"] if "功效" in section_text else [],
            "entity_tags": ["小柴胡汤"] if "小柴胡汤" in section_text else [],
            "representative_passages": [section_text[:40]],
        }


def _rows() -> list[dict[str, Any]]:
    return [
        {
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
    ]


def test_files_first_rebuild_builds_index_and_state_payload() -> None:
    tmp_path = make_test_dir("files_first_rebuild")
    try:
        context = RebuildContext(tmp_path / "files_first.db")

        result = files_first_rebuild.rebuild(context, _rows(), reset=True, batch_size=64)

        assert result["indexed_files_first_docs"] == 1
        assert result["indexed_nav_groups"] == 1
        assert result["resumed"] is False
        assert context.nav_calls == 1
        state = files_first_build_state.load_state(Path(result["state_path"]))
        assert state["status"] == "completed"
        assert state["docs_processed"] == 1
        with sqlite3.connect(context.store_path) as conn:
            assert conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(1) FROM docs_fts").fetchone()[0] == 1
    finally:
        gc.collect()
        time.sleep(0.05)
        cleanup_test_dir(tmp_path)


def test_files_first_rebuild_reuses_existing_docs_when_nav_groups_missing() -> None:
    tmp_path = make_test_dir("files_first_rebuild")
    try:
        context = RebuildContext(tmp_path / "files_first.db")
        files_first_rebuild.rebuild(context, _rows(), reset=True, batch_size=64)
        with sqlite3.connect(context.store_path) as conn:
            conn.execute("DELETE FROM nav_groups")
            conn.commit()

        result = files_first_rebuild.rebuild(context, _rows(), reset=False, batch_size=64)

        assert result["resumed"] is True
        assert result["reused_existing_docs"] is True
        assert context.nav_calls == 2
    finally:
        gc.collect()
        time.sleep(0.05)
        cleanup_test_dir(tmp_path)
