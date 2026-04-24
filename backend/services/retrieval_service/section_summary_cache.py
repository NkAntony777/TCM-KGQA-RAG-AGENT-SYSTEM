from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Any


class SectionSummaryCache:
    def __init__(self, cache_path: Path | None = None):
        self.legacy_json_path: Path | None = None
        if cache_path is not None and cache_path.suffix.lower() == ".json":
            self.legacy_json_path = cache_path
            self.cache_path = cache_path.with_suffix(".sqlite")
        else:
            self.cache_path = cache_path
            if cache_path is not None:
                legacy_candidate = cache_path.with_suffix(".json")
                if legacy_candidate.exists():
                    self.legacy_json_path = legacy_candidate
        self._initialized = False
        self._init_lock = Lock()
        if self.cache_path is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        if self.cache_path is None:
            raise RuntimeError("section_summary_cache_not_configured")
        conn = sqlite3.connect(self.cache_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized or self.cache_path is None:
            return
        with self._init_lock:
            if self._initialized:
                return
            with closing(self._connect()) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS section_summaries (
                        section_key TEXT PRIMARY KEY,
                        section_summary TEXT NOT NULL DEFAULT '',
                        topic_tags TEXT NOT NULL DEFAULT '[]',
                        entity_tags TEXT NOT NULL DEFAULT '[]',
                        representative_passages TEXT NOT NULL DEFAULT '[]',
                        updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                    )
                    """
                )
                count_row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
                existing_count = int(count_row[0]) if count_row and count_row[0] is not None else 0
                if existing_count <= 0 and self.legacy_json_path is not None and self.legacy_json_path.exists():
                    self._import_legacy_json(conn)
                conn.commit()
            self._initialized = True

    def _import_legacy_json(self, conn: sqlite3.Connection) -> None:
        if self.legacy_json_path is None:
            return
        try:
            payload = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict) or not payload:
            return

        rows = []
        for section_key, item in payload.items():
            if not isinstance(item, dict):
                continue
            rows.append(
                (
                    str(section_key).strip(),
                    str(item.get("section_summary", "")),
                    _json_list(item.get("topic_tags", [])),
                    _json_list(item.get("entity_tags", [])),
                    _json_list(item.get("representative_passages", [])),
                )
            )
        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO section_summaries
                (section_key, section_summary, topic_tags, entity_tags, representative_passages)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def load(self) -> dict[str, dict[str, Any]]:
        self._ensure_initialized()
        if self.cache_path is None:
            return {}
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT section_key, section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                """
            ).fetchall()
        return {str(row["section_key"]): _metadata_from_row(row) for row in rows}

    def get(self, section_key: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        if self.cache_path is None:
            return None
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                WHERE section_key = ?
                LIMIT 1
                """,
                (section_key,),
            ).fetchone()
        return None if row is None else _metadata_from_row(row)

    def has(self, section_key: str) -> bool:
        self._ensure_initialized()
        if self.cache_path is None:
            return False
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM section_summaries WHERE section_key = ? LIMIT 1",
                (section_key,),
            ).fetchone()
        return row is not None

    def count(self) -> int:
        self._ensure_initialized()
        if self.cache_path is None:
            return 0
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def set(self, section_key: str, metadata: dict[str, Any]) -> None:
        if self.cache_path is None:
            return
        self._ensure_initialized()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO section_summaries
                (section_key, section_summary, topic_tags, entity_tags, representative_passages, updated_at)
                VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                """,
                (
                    section_key,
                    str(metadata.get("section_summary", "")),
                    _json_list(metadata.get("topic_tags", [])),
                    _json_list(metadata.get("entity_tags", [])),
                    _json_list(metadata.get("representative_passages", [])),
                ),
            )
            conn.commit()


def _json_list(value: Any) -> str:
    return json.dumps(list(value) if isinstance(value, list) else [], ensure_ascii=False)


def _loads_list(value: Any) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _metadata_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "section_summary": str(row["section_summary"] or ""),
        "topic_tags": _loads_list(row["topic_tags"]),
        "entity_tags": _loads_list(row["entity_tags"]),
        "representative_passages": _loads_list(row["representative_passages"]),
    }
