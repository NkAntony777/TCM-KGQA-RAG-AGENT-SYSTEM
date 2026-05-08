from __future__ import annotations

from pathlib import Path

from services.retrieval_service import files_first_build_state as state
from tests.test_temp_utils import make_test_dir


def test_build_state_resume_ready_requires_matching_temp_path_and_total_rows() -> None:
    tmp_path = make_test_dir("files_first_build_state")
    temp_path = tmp_path / "index.db.tmp"
    temp_path.write_text("", encoding="utf-8")
    payload = state.new_build_state(temp_path=temp_path, target_path=tmp_path / "index.db", total_rows=3)
    payload["docs_processed"] = 2

    assert state.is_resume_ready(state=payload, temp_path=temp_path, total_rows=3) is True
    assert state.is_resume_ready(state=payload, temp_path=temp_path, total_rows=4) is False
    assert state.is_resume_ready(state={**payload, "status": "completed"}, temp_path=temp_path, total_rows=3) is False
    assert state.is_resume_ready(state=payload, temp_path=tmp_path / "other.tmp", total_rows=3) is False


def test_build_state_patch_and_completion_round_trip() -> None:
    tmp_path = make_test_dir("files_first_build_state")
    state_path = tmp_path / "index.db.state.json"
    payload = state.new_build_state(temp_path=tmp_path / "index.db.tmp", target_path=tmp_path / "index.db", total_rows=5)
    state.write_json(state_path, payload)

    state.mark_docs_progress(state_path, payload, 3)
    state.mark_nav_groups_running(state_path, payload, docs_processed=5, nav_groups_built=2)
    state.mark_completed(state_path, payload, docs_processed=5, nav_groups_built=2)

    loaded = state.load_state(state_path)
    assert loaded["status"] == "completed"
    assert loaded["docs_processed"] == 5
    assert loaded["nav_groups_built"] == 2
    assert "completed_at" in loaded


def test_build_state_rebuild_result_keeps_legacy_payload_shape() -> None:
    tmp_path = make_test_dir("files_first_build_state")
    result = state.rebuild_result(
        rows_count=7,
        nav_groups_built=4,
        store_path=Path("retrieval_local_index.fts.db"),
        state_path=tmp_path / "state.json",
        resumed=True,
        reused_existing_docs=True,
    )

    assert result == {
        "indexed_files_first_docs": 7,
        "indexed_nav_groups": 4,
        "indexed_sections": 4,
        "files_first_index_path": "retrieval_local_index.fts.db",
        "state_path": str(tmp_path / "state.json"),
        "resumed": True,
        "reused_existing_docs": True,
    }
