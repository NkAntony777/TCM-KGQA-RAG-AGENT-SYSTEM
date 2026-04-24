from __future__ import annotations

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".pytest_cache",
    ".ruff_cache",
    ".test_tmp",
    ".uv-cache",
    ".venv",
    "__pycache__",
    "_tmp_test",
    "eval",
    "logs",
    "storage",
    "workspace",
}


def test_production_code_does_not_import_common_mock_data() -> None:
    offenders: list[str] = []
    pending = [BACKEND_ROOT]
    while pending:
        current = pending.pop()
        for child in current.iterdir():
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if is_dir:
                if child.name not in SKIP_DIRS and child.name != "tests":
                    pending.append(child)
                continue
            if child.suffix != ".py":
                continue
            relative = child.relative_to(BACKEND_ROOT)
            text = child.read_text(encoding="utf-8", errors="ignore")
            if "services.common.mock_data" in text or "common.mock_data" in text:
                offenders.append(str(relative))

    assert offenders == []
