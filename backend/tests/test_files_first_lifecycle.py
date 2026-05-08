from __future__ import annotations

import time

from services.retrieval_service import files_first_lifecycle as lifecycle
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import make_test_dir


def test_progress_helpers_format_stable_console_output(capsys) -> None:
    started_at = time.perf_counter() - 2.0

    assert lifecycle.progress_bar(5, 10, width=10) == "[#####-----]"
    assert lifecycle.format_seconds(65) == "01:05"
    assert lifecycle.format_seconds(3661) == "01:01:01"

    lifecycle.print_stage_banner(stage="docs", detail="building")
    lifecycle.print_build_progress(stage="docs", done=5, total=10, started_at=started_at)

    output = capsys.readouterr().out
    assert "[files-first:docs] building" in output
    assert "[files-first:docs] [##############--------------] 5/10" in output


def test_file_lifecycle_helpers_unlink_and_replace_inside_project_tmp() -> None:
    tmp_path = make_test_dir("files_first_lifecycle")
    try:
        target = tmp_path / "target.db"
        replacement = tmp_path / "replacement.db"
        target.write_text("old", encoding="utf-8")
        replacement.write_text("new", encoding="utf-8")

        lifecycle.replace_file(target, replacement)
        assert target.read_text(encoding="utf-8") == "new"
        assert not replacement.exists()

        lifecycle.unlink_with_retry(target)
        assert not target.exists()
    finally:
        cleanup_test_dir(tmp_path)
