from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_state_path(store_path: Path) -> Path:
    return store_path.with_suffix(f"{store_path.suffix}.state.json")


def reuse_existing_docs_state(*, target_path: Path, total_rows: int) -> dict[str, Any]:
    return {
        "status": "running_nav_groups",
        "temp_path": str(target_path),
        "target_path": str(target_path),
        "total_rows": total_rows,
        "docs_processed": total_rows,
        "nav_groups_built": 0,
        "updated_at": time.time(),
        "reused_existing_docs": True,
    }


def new_build_state(*, temp_path: Path, target_path: Path, total_rows: int) -> dict[str, Any]:
    return {
        "status": "running_docs",
        "temp_path": str(temp_path),
        "target_path": str(target_path),
        "total_rows": total_rows,
        "docs_processed": 0,
        "nav_groups_built": 0,
        "updated_at": time.time(),
    }


def load_state(path: Path) -> dict[str, Any]:
    state = read_json(path, {})
    return state if isinstance(state, dict) else {}


def is_resume_ready(*, state: dict[str, Any], temp_path: Path, total_rows: int) -> bool:
    return (
        bool(state)
        and str(state.get("temp_path", "")) == str(temp_path)
        and temp_path.exists()
        and state.get("status") in {"running_docs", "running_nav_groups", "interrupted", "failed"}
        and int(state.get("total_rows", 0) or 0) == total_rows
    )


def patch_state(path: Path, state: dict[str, Any], **patch: Any) -> dict[str, Any]:
    state.update({**patch, "updated_at": time.time()})
    write_json(path, state)
    return state


def mark_docs_progress(path: Path, state: dict[str, Any], docs_processed: int) -> dict[str, Any]:
    return patch_state(path, state, status="running_docs", docs_processed=docs_processed)


def mark_nav_groups_running(path: Path, state: dict[str, Any], *, docs_processed: int | None = None, nav_groups_built: int | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {"status": "running_nav_groups"}
    if docs_processed is not None:
        patch["docs_processed"] = docs_processed
    if nav_groups_built is not None:
        patch["nav_groups_built"] = nav_groups_built
    return patch_state(path, state, **patch)


def mark_interrupted(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    return patch_state(path, state, status="interrupted")


def mark_failed(path: Path, state: dict[str, Any], error: Exception) -> dict[str, Any]:
    return patch_state(path, state, status="failed", last_error=str(error))


def mark_completed(
    path: Path,
    state: dict[str, Any],
    *,
    docs_processed: int,
    nav_groups_built: int,
    reused_existing_docs: bool | None = None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "status": "completed",
        "docs_processed": docs_processed,
        "nav_groups_built": nav_groups_built,
        "completed_at": time.time(),
    }
    if reused_existing_docs is not None:
        patch["reused_existing_docs"] = reused_existing_docs
    return patch_state(path, state, **patch)


def rebuild_result(
    *,
    rows_count: int,
    nav_groups_built: int,
    store_path: Path,
    state_path: Path,
    resumed: bool,
    reused_existing_docs: bool = False,
) -> dict[str, Any]:
    result = {
        "indexed_files_first_docs": rows_count,
        "indexed_nav_groups": nav_groups_built,
        "indexed_sections": nav_groups_built,
        "files_first_index_path": str(store_path),
        "state_path": str(state_path),
        "resumed": resumed,
    }
    if reused_existing_docs:
        result["reused_existing_docs"] = True
    return result
