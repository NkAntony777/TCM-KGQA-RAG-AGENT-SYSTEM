
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator, TypeVar

FACT_IDS_SEP = "\x1f"
SQLITE_PARAM_BATCH = 800
T = TypeVar("T")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            value = _normalize_text(item)
            if value and value not in fact_ids:
                fact_ids.append(value)
    raw_fact_id = _normalize_text(row.get("fact_id"))
    if raw_fact_id and raw_fact_id not in fact_ids:
        fact_ids.append(raw_fact_id)
    return fact_ids


def _fact_signature(row: dict[str, Any]) -> str:
    return "||".join([
        _normalize_text(row.get("subject")),
        _normalize_text(row.get("predicate")),
        _normalize_text(row.get("object")),
        _normalize_text(row.get("source_book")),
        _normalize_text(row.get("source_chapter")),
    ])


def _iter_json_array_rows(path: Path) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as f:
        buffer = ""
        pos = 0
        started = False
        eof = False
        while True:
            if not eof and len(buffer) - pos < 1024 * 256:
                tail = buffer[pos:]
                chunk = f.read(1024 * 1024)
                if chunk:
                    buffer = tail + chunk
                    pos = 0
                else:
                    buffer = tail
                    pos = 0
                    eof = True
            while pos < len(buffer) and buffer[pos].isspace():
                pos += 1
            if not started:
                if pos >= len(buffer):
                    if eof:
                        return
                    break
                if buffer[pos] != "[":
                    raise ValueError(f"json_array_expected: {path}")
                started = True
                pos += 1
                continue
            while pos < len(buffer) and buffer[pos].isspace():
                pos += 1
            if pos >= len(buffer):
                if eof:
                    return
                break
            marker = buffer[pos]
            if marker == "]":
                return
            if marker == ",":
                pos += 1
                continue
            try:
                payload, next_pos = decoder.raw_decode(buffer, pos)
            except json.JSONDecodeError:
                if eof:
                    raise
                break
            pos = next_pos
            if isinstance(payload, dict):
                yield payload


def _iter_jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line.lstrip("\ufeff"))
            if isinstance(payload, dict):
                yield payload


def _iter_graph_rows(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        yield from _iter_jsonl_rows(path)
        return
    yield from _iter_json_array_rows(path)


def _chunked(items: list[T], size: int = SQLITE_PARAM_BATCH) -> Iterator[list[T]]:
    for start in range(0, len(items), max(1, size)):
        yield items[start : start + max(1, size)]

def _import_legacy_sources(self, conn: sqlite3.Connection) -> None:
    sources: list[tuple[Path | None, Path | None, str]] = [
        (self.settings.sample_graph_path, self.settings.sample_evidence_path, "sample"),
        (self.settings.graph_path, self.settings.evidence_path, "runtime"),
        (self.settings.modern_graph_path, self.settings.modern_evidence_path, "modern_graph"),
    ]
    changed_signatures: set[str] = set()
    for graph_path, evidence_path, scope in sources:
        if evidence_path and evidence_path.exists():
            self._import_evidence_rows(conn, _iter_jsonl_rows(evidence_path))
        if graph_path and graph_path.exists():
            changed_signatures.update(
                self._import_fact_rows(conn, _iter_graph_rows(graph_path), dataset_scope=scope)
            )
    self._refresh_fact_metadata(conn, changed_signatures)
    self._rebuild_entities(conn)
    conn.commit()

def _import_evidence_rows(self, conn: sqlite3.Connection, rows: Iterator[dict[str, Any]]) -> int:
    payload: list[tuple[Any, ...]] = []
    inserted = 0
    for row in rows:
        fact_id = _normalize_text(row.get("fact_id"))
        if not fact_id:
            continue
        payload.append(
            (
                fact_id,
                _normalize_text(row.get("source_book")),
                _normalize_text(row.get("source_chapter")),
                _normalize_text(row.get("source_text")),
                float(row.get("confidence", 0.0) or 0.0),
            )
        )
        if len(payload) >= 2000:
            inserted += self._flush_evidence_batch(conn, payload)
            payload = []
    if payload:
        inserted += self._flush_evidence_batch(conn, payload)
    return inserted

def _flush_evidence_batch(self, conn: sqlite3.Connection, payload: list[tuple[Any, ...]]) -> int:
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO evidence (
            fact_id, source_book, source_chapter, source_text, confidence
        ) VALUES (?, ?, ?, ?, ?)
        """,
        payload,
    )
    return conn.total_changes - before

def _import_fact_rows(
    self,
    conn: sqlite3.Connection,
    rows: Iterator[dict[str, Any]],
    *,
    dataset_scope: str,
) -> set[str]:
    signatures: set[str] = set()
    fact_payload: list[tuple[Any, ...]] = []
    member_payload: list[tuple[str, str]] = []
    entity_payload: list[tuple[str, str]] = []

    def flush() -> None:
        if fact_payload:
            conn.executemany(
                """
                INSERT INTO facts (
                    signature, subject, predicate, object, subject_type, object_type,
                    source_book, source_chapter, dataset_scope
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signature) DO UPDATE SET
                    subject_type = CASE
                        WHEN facts.subject_type IN ('', 'entity', 'other') AND excluded.subject_type NOT IN ('', 'entity', 'other')
                        THEN excluded.subject_type ELSE facts.subject_type END,
                    object_type = CASE
                        WHEN facts.object_type IN ('', 'entity', 'other') AND excluded.object_type NOT IN ('', 'entity', 'other')
                        THEN excluded.object_type ELSE facts.object_type END,
                    dataset_scope = CASE
                        WHEN facts.dataset_scope = 'sample' AND excluded.dataset_scope = 'runtime'
                        THEN 'runtime' ELSE facts.dataset_scope END
                """,
                fact_payload,
            )
            fact_payload.clear()
        if member_payload:
            conn.executemany(
                "INSERT OR IGNORE INTO fact_members (signature, fact_id) VALUES (?, ?)",
                member_payload,
            )
            member_payload.clear()
        if entity_payload:
            conn.executemany(
                """
                INSERT INTO entities (name, entity_type) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    entity_type = CASE
                        WHEN entities.entity_type IN ('', 'entity', 'other') AND excluded.entity_type NOT IN ('', 'entity', 'other')
                        THEN excluded.entity_type ELSE entities.entity_type END
                """,
                entity_payload,
            )
            entity_payload.clear()

    for row in rows:
        subject = _normalize_text(row.get("subject"))
        predicate = _normalize_text(row.get("predicate"))
        obj = _normalize_text(row.get("object"))
        if not subject or not predicate or not obj:
            continue
        signature = _fact_signature(row)
        signatures.add(signature)
        fact_payload.append(
            (
                signature,
                subject,
                predicate,
                obj,
                _normalize_text(row.get("subject_type")) or "other",
                _normalize_text(row.get("object_type")) or "other",
                _normalize_text(row.get("source_book")),
                _normalize_text(row.get("source_chapter")),
                dataset_scope,
            )
        )
        entity_payload.append((subject, _normalize_text(row.get("subject_type")) or "other"))
        entity_payload.append((obj, _normalize_text(row.get("object_type")) or "other"))
        for fact_id in _extract_fact_ids(row):
            member_payload.append((signature, fact_id))
        if len(fact_payload) >= 2000:
            flush()

    flush()
    return signatures

def _refresh_fact_metadata(self, conn: sqlite3.Connection, signatures: set[str]) -> None:
    if not signatures:
        return
    conn.execute("DROP TABLE IF EXISTS temp_changed_signatures")
    conn.execute("CREATE TEMP TABLE temp_changed_signatures (signature TEXT PRIMARY KEY)")
    conn.executemany(
        "INSERT INTO temp_changed_signatures (signature) VALUES (?)",
        [(signature,) for signature in signatures],
    )
    conn.execute(
        f"""
        UPDATE facts
        SET fact_ids_text = COALESCE((
            SELECT group_concat(fact_id, '{FACT_IDS_SEP}')
            FROM fact_members
            WHERE fact_members.signature = facts.signature
            ORDER BY fact_id
        ), ''),
            fact_id = COALESCE((
                SELECT fm.fact_id
                FROM fact_members fm
                LEFT JOIN evidence e ON e.fact_id = fm.fact_id
                WHERE fm.signature = facts.signature
                ORDER BY COALESCE(e.confidence, 0.0) DESC, fm.fact_id ASC
                LIMIT 1
            ), ''),
            best_source_text = COALESCE((
                SELECT e.source_text
                FROM fact_members fm
                JOIN evidence e ON e.fact_id = fm.fact_id
                WHERE fm.signature = facts.signature
                ORDER BY COALESCE(e.confidence, 0.0) DESC, fm.fact_id ASC
                LIMIT 1
            ), ''),
            best_confidence = COALESCE((
                SELECT e.confidence
                FROM fact_members fm
                JOIN evidence e ON e.fact_id = fm.fact_id
                WHERE fm.signature = facts.signature
                ORDER BY COALESCE(e.confidence, 0.0) DESC, fm.fact_id ASC
                LIMIT 1
            ), 0.0)
        WHERE signature IN (SELECT signature FROM temp_changed_signatures)
        """
    )
    conn.execute("DROP TABLE temp_changed_signatures")

def _upsert_entities_for_signatures(self, conn: sqlite3.Connection, signatures: set[str]) -> None:
    if not signatures:
        return
    entity_rows: list[tuple[str, str]] = []
    for signature_batch in _chunked(sorted(signatures)):
        placeholders = ",".join("?" for _ in signature_batch)
        rows = conn.execute(
            f"""
            SELECT subject AS name, subject_type AS entity_type
            FROM facts
            WHERE signature IN ({placeholders})
            UNION ALL
            SELECT object AS name, object_type AS entity_type
            FROM facts
            WHERE signature IN ({placeholders})
            """,
            tuple(signature_batch) + tuple(signature_batch),
        ).fetchall()
        entity_rows.extend(
            (row["name"], row["entity_type"])
            for row in rows
            if _normalize_text(row["name"])
        )
    conn.executemany(
        """
        INSERT INTO entities (name, entity_type) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            entity_type = CASE
                WHEN entities.entity_type IN ('', 'entity', 'other') AND excluded.entity_type NOT IN ('', 'entity', 'other')
                THEN excluded.entity_type ELSE entities.entity_type END
        """,
        entity_rows,
    )

def _rebuild_entities(self, conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM entities")
    conn.execute(
        """
        INSERT INTO entities (name, entity_type)
        SELECT name, entity_type
        FROM (
            SELECT subject AS name, subject_type AS entity_type FROM facts
            UNION ALL
            SELECT object AS name, object_type AS entity_type FROM facts
        )
        WHERE name <> ''
        GROUP BY name
        """
    )
