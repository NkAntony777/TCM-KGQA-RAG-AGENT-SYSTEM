from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


JsonLoader = Callable[[Path, Any], Any]
PublishStatusLoader = Callable[[Path], dict[str, Any]]


def _safe_positive_int(value: int | str | None, default: int) -> int:
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return default


def list_runs_payload(
    *,
    output_dir: Path,
    load_json_file: JsonLoader,
    load_publish_status: PublishStatusLoader,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page = _safe_positive_int(page, 1)
    page_size = min(_safe_positive_int(page_size, 20), 100)
    if not output_dir.exists():
        return {"runs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    runs = sorted((path for path in output_dir.iterdir() if path.is_dir()), reverse=True)
    total = len(runs)
    total_pages = (total + page_size - 1) // page_size if total else 0
    start = (page - 1) * page_size
    end = start + page_size

    result = []
    for run_dir in runs[start:end]:
        state = load_json_file(run_dir / "state.json", {})
        manifest = load_json_file(run_dir / "manifest.json", {})
        result.append(
            {
                "run_dir": run_dir.name,
                "status": state.get("status", "unknown"),
                "books_total": state.get("books_total", 0),
                "books_completed": state.get("books_completed", 0),
                "total_triples": state.get("total_triples", 0),
                "chunk_errors": state.get("chunk_errors", 0),
                "model": manifest.get("model", ""),
                "created_at": manifest.get("created_at", ""),
                "dry_run": manifest.get("dry_run", False),
                "publish_status": load_publish_status(run_dir),
            }
        )
    return {
        "runs": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def resume_config_payload(
    *,
    run_name: str,
    run_dir: Path,
    load_json_file: JsonLoader,
    resume_fixed_fields: set[str],
) -> dict[str, Any]:
    manifest = load_json_file(run_dir / "manifest.json", {})
    state = load_json_file(run_dir / "state.json", {})
    manifest_cfg = manifest.get("config", {}) if isinstance(manifest.get("config", {}), dict) else {}

    return {
        "run_dir": run_name,
        "status": state.get("status", "unknown"),
        "dry_run": bool(manifest.get("dry_run", False)),
        "progress": {
            "chunks_completed": int(state.get("chunks_completed", 0) or 0),
            "chunks_total": int(state.get("chunks_total", 0) or 0),
            "books_completed": int(state.get("books_completed", 0) or 0),
            "books_total": int(state.get("books_total", 0) or 0),
            "total_triples": int(state.get("total_triples", 0) or 0),
            "chunk_errors": int(state.get("chunk_errors", 0) or 0),
        },
        "api_config": {
            "model": str(manifest.get("model", "") or ""),
            "base_url": str(manifest.get("base_url", "") or ""),
            "request_timeout": float(manifest_cfg.get("request_timeout", 314.0) or 314.0),
            "max_retries": int(manifest_cfg.get("max_retries", 2) or 2),
            "request_delay": float(manifest_cfg.get("request_delay", 1.1) or 1.1),
            "retry_backoff_base": float(manifest_cfg.get("retry_backoff_base", 2.0) or 2.0),
            "parallel_workers": int(manifest_cfg.get("parallel_workers", 11) or 11),
            "max_chunk_retries": int(manifest_cfg.get("max_chunk_retries", 2) or 2),
        },
        "notes": {
            "publish_json": "import_sqlite_runtime_graph",
            "publish_nebula": "import_sqlite_runtime_graph_then_write_nebulagraph",
            "resume_safe_fields": [
                "model",
                "base_url",
                "api_key",
                "request_timeout",
                "max_retries",
                "request_delay",
                "retry_backoff_base",
                "parallel_workers",
                "max_chunk_retries",
                "auto_clean",
                "auto_publish",
            ],
            "resume_fixed_fields": sorted(resume_fixed_fields),
        },
    }


def run_triples_payload(*, run_name: str, run_dir: Path, limit: int = 50) -> dict[str, Any]:
    jsonl = run_dir / "triples.cleaned.jsonl"
    source_kind = "cleaned"
    if not jsonl.exists():
        jsonl = run_dir / "triples.normalized.jsonl"
        source_kind = "normalized"

    rows = []
    if jsonl.exists():
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line.lstrip("\ufeff")))
                if len(rows) >= limit:
                    break
    return {
        "run_dir": run_name,
        "rows": rows,
        "count": len(rows),
        "source_kind": source_kind,
        "source_path": str(jsonl),
    }
