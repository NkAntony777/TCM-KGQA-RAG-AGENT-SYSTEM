"""File and artifact helpers for triple extraction runs."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        temp_path.write_text(content, encoding=encoding)
        last_error: OSError | None = None
        for attempt in range(20):
            try:
                os.replace(temp_path, path)
                return
            except OSError as exc:
                if not isinstance(exc, PermissionError) and getattr(exc, "winerror", None) not in {5, 32}:
                    raise
                last_error = exc
                if attempt == 19:
                    break
                time.sleep(min(1.0, 0.05 * (attempt + 1)))
        if last_error is not None:
            raise last_error
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            raw_sig = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
            return json.loads(raw_sig) if raw_sig else default
        except json.JSONDecodeError:
            return default


def load_json_file_strict(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"json_file_not_found: {path}")
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        raise ValueError(f"json_file_empty: {path}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw_sig = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
        if not raw_sig:
            raise ValueError(f"json_file_empty: {path}")
        return json.loads(raw_sig)


def extract_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            value = str(item).strip()
            if value and value not in fact_ids:
                fact_ids.append(value)

    raw_fact_id = str(row.get("fact_id", "")).strip()
    if raw_fact_id and raw_fact_id not in fact_ids:
        fact_ids.append(raw_fact_id)
    return fact_ids


def dedupe_graph_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_index: dict[tuple[str, str, str, str, str], int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject", "")).strip()
        predicate = str(row.get("predicate", "")).strip()
        obj = str(row.get("object", "")).strip()
        source_book = str(row.get("source_book", "")).strip()
        source_chapter = str(row.get("source_chapter", "")).strip()
        if not subject or not predicate or not obj:
            continue
        signature = (subject, predicate, obj, source_book, source_chapter)
        fact_ids = extract_fact_ids(row)
        existing_index = seen_index.get(signature)
        if existing_index is not None:
            existing = deduped[existing_index]
            merged_fact_ids = extract_fact_ids(existing)
            for fact_id in fact_ids:
                if fact_id not in merged_fact_ids:
                    merged_fact_ids.append(fact_id)
            if merged_fact_ids:
                existing["fact_ids"] = merged_fact_ids
                existing["fact_id"] = merged_fact_ids[0]
            continue

        payload = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "subject_type": str(row.get("subject_type", "other")).strip() or "other",
            "object_type": str(row.get("object_type", "other")).strip() or "other",
            "source_book": source_book,
            "source_chapter": source_chapter,
        }
        if fact_ids:
            payload["fact_ids"] = fact_ids
            payload["fact_id"] = fact_ids[0]
        seen_index[signature] = len(deduped)
        deduped.append(payload)

    deduped.sort(
        key=lambda item: (
            item["subject"],
            item["predicate"],
            item["object"],
            item["source_book"],
            item["source_chapter"],
        )
    )
    return deduped


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line.lstrip("\ufeff"))
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def dedupe_evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        fact_id = str(row.get("fact_id", "")).strip()
        if not fact_id or fact_id in seen:
            continue
        seen.add(fact_id)
        deduped.append(
            {
                "fact_id": fact_id,
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                "source_text": str(row.get("source_text", "")).strip(),
                "confidence": float(row.get("confidence", 0.0)),
            }
        )
    deduped.sort(key=lambda item: item["fact_id"])
    return deduped


def derive_evidence_target_path(graph_target_path: Path) -> Path:
    if graph_target_path.suffix.lower() == ".json":
        return graph_target_path.with_name(f"{graph_target_path.stem}.evidence.jsonl")
    return graph_target_path.parent / f"{graph_target_path.name}.evidence.jsonl"
