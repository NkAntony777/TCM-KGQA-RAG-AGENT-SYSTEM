from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


JsonLoader = Callable[[Path, Any], Any]
WriteTextFn = Callable[[Path, str], None]


def normalize_overrides(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        payload = {}
    force_unprocessed: list[str] = []
    raw_items = payload.get("force_unprocessed", [])
    for item in raw_items if isinstance(raw_items, list) else []:
        value = str(item).strip()
        if value and value not in force_unprocessed:
            force_unprocessed.append(value)
    return {"force_unprocessed": sorted(force_unprocessed)}


def load_overrides(*, lock: Any, path: Path, load_json_file: JsonLoader) -> dict[str, list[str]]:
    with lock:
        return normalize_overrides(load_json_file(path, {}))


def write_overrides(
    *,
    lock: Any,
    path: Path,
    payload: dict[str, list[str]],
    write_text: WriteTextFn,
) -> dict[str, list[str]]:
    with lock:
        normalized = normalize_overrides(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2))
        return normalized


def mark_force_unprocessed(
    *,
    lock: Any,
    path: Path,
    book_names: list[str],
    load_json_file: JsonLoader,
    write_text: WriteTextFn,
) -> dict[str, list[str]]:
    with lock:
        payload = normalize_overrides(load_json_file(path, {}))
        merged = sorted(
            set(payload.get("force_unprocessed", []))
            | {str(name).strip() for name in book_names if str(name).strip()}
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = {"force_unprocessed": merged}
        write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2))
        return normalized


def clear_force_unprocessed(
    *,
    lock: Any,
    path: Path,
    book_names: list[str],
    load_json_file: JsonLoader,
    write_text: WriteTextFn,
) -> dict[str, list[str]]:
    with lock:
        to_remove = {str(name).strip() for name in book_names if str(name).strip()}
        payload = normalize_overrides(load_json_file(path, {}))
        kept = [name for name in payload.get("force_unprocessed", []) if name not in to_remove]
        normalized = {"force_unprocessed": kept}
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2))
        return normalized
