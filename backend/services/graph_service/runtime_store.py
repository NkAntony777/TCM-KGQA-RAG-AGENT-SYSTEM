from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, TypeVar

FACT_IDS_SEP = "\x1f"
_RUNTIME_STORE_LOCK = threading.RLock()
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
    return "||".join(
        [
            _normalize_text(row.get("subject")),
            _normalize_text(row.get("predicate")),
            _normalize_text(row.get("object")),
            _normalize_text(row.get("source_book")),
            _normalize_text(row.get("source_chapter")),
        ]
    )


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


def _chunked(items: list[T], size: int = SQLITE_PARAM_BATCH) -> Iterator[list[T]]:
    for start in range(0, len(items), max(1, size)):
        yield items[start : start + max(1, size)]


@dataclass(frozen=True)
class RuntimeGraphStoreSettings:
    graph_path: Path
    evidence_path: Path
    db_path: Path
    sample_graph_path: Path | None = None
    sample_evidence_path: Path | None = None
    modern_graph_path: Path | None = None
    modern_evidence_path: Path | None = None


def _iter_graph_rows(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        yield from _iter_jsonl_rows(path)
        return
    yield from _iter_json_array_rows(path)


class RuntimeGraphStore:
    def __init__(self, settings: RuntimeGraphStoreSettings):
        self.settings = settings

    @classmethod
    def from_graph_paths(
        cls,
        *,
        graph_path: Path,
        evidence_path: Path,
        sample_graph_path: Path | None = None,
        sample_evidence_path: Path | None = None,
        modern_graph_path: Path | None = None,
        modern_evidence_path: Path | None = None,
    ) -> "RuntimeGraphStore":
        return cls(
            RuntimeGraphStoreSettings(
                graph_path=graph_path,
                evidence_path=evidence_path,
                db_path=graph_path.with_suffix(".db"),
                sample_graph_path=sample_graph_path,
                sample_evidence_path=sample_evidence_path,
                modern_graph_path=modern_graph_path,
                modern_evidence_path=modern_evidence_path,
            )
        )

    def _connect(self) -> sqlite3.Connection:
        self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.settings.db_path, timeout=120.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def ensure_ready(self) -> None:
        with _RUNTIME_STORE_LOCK:
            with closing(self._connect()) as conn:
                self._ensure_schema(conn)
                facts_count = int(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0])
                if facts_count > 0:
                    modern_graph_count = int(
                        conn.execute("SELECT COUNT(*) FROM facts WHERE dataset_scope = 'modern_graph'").fetchone()[0]
                    )
                    if modern_graph_count <= 0 and self.settings.modern_graph_path and self.settings.modern_graph_path.exists():
                        changed_signatures: set[str] = set()
                        if self.settings.modern_evidence_path and self.settings.modern_evidence_path.exists():
                            self._import_evidence_rows(conn, _iter_jsonl_rows(self.settings.modern_evidence_path))
                        changed_signatures.update(
                            self._import_fact_rows(
                                conn,
                                _iter_graph_rows(self.settings.modern_graph_path),
                                dataset_scope="modern_graph",
                            )
                        )
                        self._refresh_fact_metadata(conn, changed_signatures)
                        self._upsert_entities_for_signatures(conn, changed_signatures)
                        conn.commit()
                    return
                self._import_legacy_sources(conn)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                signature TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                subject_type TEXT NOT NULL DEFAULT 'other',
                object_type TEXT NOT NULL DEFAULT 'other',
                source_book TEXT NOT NULL DEFAULT '',
                source_chapter TEXT NOT NULL DEFAULT '',
                dataset_scope TEXT NOT NULL DEFAULT 'runtime',
                fact_id TEXT NOT NULL DEFAULT '',
                fact_ids_text TEXT NOT NULL DEFAULT '',
                best_source_text TEXT NOT NULL DEFAULT '',
                best_confidence REAL NOT NULL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS fact_members (
                signature TEXT NOT NULL,
                fact_id TEXT NOT NULL,
                PRIMARY KEY (signature, fact_id),
                FOREIGN KEY (signature) REFERENCES facts(signature) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evidence (
                fact_id TEXT PRIMARY KEY,
                source_book TEXT NOT NULL DEFAULT '',
                source_chapter TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS entities (
                name TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL DEFAULT 'other'
            );
            CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
            CREATE INDEX IF NOT EXISTS idx_facts_object ON facts(object);
            CREATE INDEX IF NOT EXISTS idx_facts_book ON facts(source_book);
            CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(predicate);
            CREATE INDEX IF NOT EXISTS idx_fact_members_fact_id ON fact_members(fact_id);
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            """
        )
        conn.commit()

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

    def import_run(
        self,
        *,
        graph_path: Path,
        evidence_path: Path | None = None,
        dataset_scope: str = "runtime",
    ) -> dict[str, Any]:
        self.ensure_ready()
        with _RUNTIME_STORE_LOCK:
            with closing(self._connect()) as conn:
                if evidence_path and evidence_path.exists():
                    self._import_evidence_rows(conn, _iter_jsonl_rows(evidence_path))
                changed = self._import_fact_rows(conn, _iter_graph_rows(graph_path), dataset_scope=dataset_scope)
                self._refresh_fact_metadata(conn, changed)
                self._upsert_entities_for_signatures(conn, changed)
                conn.commit()
                return self.stats(conn=conn)

    def delete_books(self, book_names: list[str]) -> dict[str, Any]:
        self.ensure_ready()
        books = sorted({_normalize_text(name) for name in book_names if _normalize_text(name)})
        if not books:
            raise ValueError("book_names_required")
        with _RUNTIME_STORE_LOCK:
            with closing(self._connect()) as conn:
                removed_rows = self.fetch_rows_for_books(conn, books)
                removed_fact_ids = {
                    fact_id
                    for row in removed_rows
                    for fact_id in row.get("fact_ids", [])
                    if _normalize_text(fact_id)
                }
                removed_entities = {
                    _normalize_text(row.get(key))
                    for row in removed_rows
                    for key in ("subject", "object")
                    if _normalize_text(row.get(key))
                }
                for book_batch in _chunked(books):
                    placeholders = ",".join("?" for _ in book_batch)
                    conn.execute(f"DELETE FROM facts WHERE source_book IN ({placeholders})", book_batch)
                conn.execute(
                    "DELETE FROM evidence WHERE fact_id NOT IN (SELECT DISTINCT fact_id FROM fact_members)"
                )
                self._rebuild_entities(conn)
                conn.commit()
                remaining_entities = {
                    row["name"]
                    for row in conn.execute("SELECT name FROM entities")
                }
                orphan_entities = sorted(removed_entities - remaining_entities)
                stats = self.stats(conn=conn)
                return {
                    "books": books,
                    "removed_rows": removed_rows,
                    "removed_triples": len(removed_rows),
                    "remaining_triples": stats["total_triples"],
                    "removed_evidence": len(removed_fact_ids),
                    "remaining_evidence": stats["evidence_count"],
                    "orphan_entities": orphan_entities,
                }

    def stats(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        if conn is None:
            self.ensure_ready()
        managed = conn is None
        conn = conn or self._connect()
        try:
            total_triples = int(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0])
            runtime_triples = int(
                conn.execute("SELECT COUNT(*) FROM facts WHERE dataset_scope = 'runtime'").fetchone()[0]
            )
            sample_triples = int(
                conn.execute("SELECT COUNT(*) FROM facts WHERE dataset_scope = 'sample'").fetchone()[0]
            )
            modern_graph_triples = int(
                conn.execute("SELECT COUNT(*) FROM facts WHERE dataset_scope = 'modern_graph'").fetchone()[0]
            )
            evidence_count = int(conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0])
            node_count = int(conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0])
            predicate_dist = [
                {"predicate": row["predicate"], "count": int(row["count"])}
                for row in conn.execute(
                    "SELECT predicate, COUNT(*) AS count FROM facts GROUP BY predicate ORDER BY count DESC, predicate ASC LIMIT 15"
                )
            ]
            book_dist = [
                {"name": row["source_book"], "count": int(row["count"])}
                for row in conn.execute(
                    "SELECT source_book, COUNT(*) AS count FROM facts WHERE source_book <> '' GROUP BY source_book ORDER BY count DESC, source_book ASC LIMIT 10"
                )
            ]
            return {
                "exists": total_triples > 0,
                "db_path": str(self.settings.db_path),
                "graph_path": str(self.settings.graph_path),
                "evidence_path": str(self.settings.evidence_path),
                "total_triples": total_triples,
                "runtime_triples": runtime_triples,
                "sample_triples": sample_triples,
                "modern_graph_triples": modern_graph_triples,
                "evidence_count": evidence_count,
                "node_count": node_count,
                "predicate_dist": predicate_dist,
                "book_dist": book_dist,
            }
        finally:
            if managed:
                conn.close()

    def list_books(self, *, limit: int, keyword: str = "") -> list[dict[str, Any]]:
        self.ensure_ready()
        params: list[Any] = []
        where = "WHERE source_book <> ''"
        if keyword:
            where += " AND lower(source_book) LIKE ?"
            params.append(f"%{keyword.lower()}%")
        params.append(max(1, limit))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT source_book, COUNT(*) AS triple_count
                FROM facts
                {where}
                GROUP BY source_book
                ORDER BY triple_count DESC, source_book ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [{"name": row["source_book"], "triple_count": int(row["triple_count"])} for row in rows]

    def total_books(self, keyword: str = "") -> int:
        self.ensure_ready()
        params: list[Any] = []
        where = "WHERE source_book <> ''"
        if keyword:
            where += " AND lower(source_book) LIKE ?"
            params.append(f"%{keyword.lower()}%")
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM (SELECT 1 FROM facts {where} GROUP BY source_book)",
                params,
            ).fetchone()
        return int(row[0] if row else 0)

    def book_total(self, book_name: str) -> int:
        self.ensure_ready()
        query = _normalize_text(book_name)
        with closing(self._connect()) as conn:
            exact = int(conn.execute("SELECT COUNT(*) FROM facts WHERE source_book = ?", (query,)).fetchone()[0])
            if exact > 0:
                return exact
            return int(conn.execute("SELECT COUNT(*) FROM facts WHERE source_book LIKE ?", (f"%{query}%",)).fetchone()[0])

    def book_triples(self, book_name: str, *, limit: int) -> list[dict[str, Any]]:
        self.ensure_ready()
        query = _normalize_text(book_name)
        sql = self._relation_projection_sql(where_clause="source_book = ?")
        params: tuple[Any, ...] = (query, max(1, limit))
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
            if rows:
                return [self._row_to_relation_dict(row) for row in rows]
            fuzzy_rows = conn.execute(
                self._relation_projection_sql(where_clause="source_book LIKE ?"),
                (f"%{query}%", max(1, limit)),
            ).fetchall()
        return [self._row_to_relation_dict(row) for row in fuzzy_rows]

    def resolve_entities(self, query: str, preferred_types: set[str] | None = None, *, limit: int = 20) -> list[str]:
        self.ensure_ready()
        normalized = _normalize_text(query)
        if not normalized:
            return []
        params: list[Any] = [normalized]
        type_filter = ""
        if preferred_types:
            placeholders = ",".join("?" for _ in preferred_types)
            type_filter = f" AND entity_type IN ({placeholders})"
            params.extend(sorted(preferred_types))
        with closing(self._connect()) as conn:
            exact_rows = conn.execute(
                f"SELECT name FROM entities WHERE name = ?{type_filter} ORDER BY name ASC LIMIT ?",
                (*params, max(1, limit)),
            ).fetchall()
            exact = [row["name"] for row in exact_rows]
            if len(exact) >= max(1, limit):
                return exact
            contains_rows = conn.execute(
                f"""
                SELECT name
                FROM entities
                WHERE length(name) >= 2
                  AND (name LIKE ? OR ? LIKE '%' || name || '%'){type_filter}
                ORDER BY length(name) ASC, name ASC
                LIMIT ?
                """,
                (f"%{normalized}%", normalized, *params[1:], max(1, limit)),
            ).fetchall()
        ordered: list[str] = []
        seen: set[str] = set()
        for name in exact + [row["name"] for row in contains_rows]:
            if name in seen:
                continue
            seen.add(name)
            ordered.append(name)
        return ordered[: max(1, limit)]

    def entity_type(self, entity_name: str) -> str:
        self.ensure_ready()
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT entity_type FROM entities WHERE name = ?", (_normalize_text(entity_name),)).fetchone()
        return _normalize_text(row["entity_type"]) if row else "entity"

    def collect_relations(self, entity_name: str) -> list[dict[str, Any]]:
        self.ensure_ready()
        entity = _normalize_text(entity_name)
        with closing(self._connect()) as conn:
            outgoing = conn.execute(
                self._relation_projection_sql(where_clause="subject = ?", direction="out"),
                (entity, 1000),
            ).fetchall()
            incoming = conn.execute(
                self._relation_projection_sql(where_clause="object = ?", direction="in"),
                (entity, 1000),
            ).fetchall()
        rows: list[dict[str, Any]] = []
        for row in outgoing:
            item = self._row_to_relation_dict(row)
            item["direction"] = "out"
            rows.append(item)
        for row in incoming:
            item = self._row_to_relation_dict(row)
            item["direction"] = "in"
            rows.append(item)
        return rows

    def adjacent_names(self, entity_name: str) -> list[str]:
        self.ensure_ready()
        entity = _normalize_text(entity_name)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT object AS neighbor_name FROM facts WHERE subject = ?
                UNION
                SELECT subject AS neighbor_name FROM facts WHERE object = ?
                ORDER BY neighbor_name ASC
                """,
                (entity, entity),
            ).fetchall()
        return [row["neighbor_name"] for row in rows if _normalize_text(row["neighbor_name"])]

    def first_edge_between(self, source: str, target: str) -> dict[str, Any] | None:
        self.ensure_ready()
        with closing(self._connect()) as conn:
            row = conn.execute(
                self._relation_projection_sql(where_clause="subject = ? AND object = ?", direction="edge"),
                (_normalize_text(source), _normalize_text(target), 1),
            ).fetchone()
        return self._row_to_edge_dict(row) if row else None

    def recommended_formulas(self, syndrome_name: str) -> list[str]:
        self.ensure_ready()
        syndrome = _normalize_text(syndrome_name)
        with closing(self._connect()) as conn:
            out_rows = conn.execute(
                """
                SELECT object
                FROM facts
                WHERE subject = ? AND predicate = '推荐方剂' AND object_type = 'formula'
                ORDER BY object ASC
                """,
                (syndrome,),
            ).fetchall()
            in_rows = conn.execute(
                """
                SELECT subject
                FROM facts
                WHERE object = ? AND predicate = '治疗证候' AND subject_type = 'formula'
                ORDER BY subject ASC
                """,
                (syndrome,),
            ).fetchall()
        formulas = {_normalize_text(row[0]) for row in out_rows + in_rows if _normalize_text(row[0])}
        return sorted(formulas)

    def syndromes_for_symptom(self, symptom_name: str) -> list[dict[str, Any]]:
        self.ensure_ready()
        symptom = _normalize_text(symptom_name)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                self._relation_projection_sql(
                    where_clause="object = ? AND subject_type = 'syndrome'",
                    direction="symptom",
                ),
                (symptom, 1000),
            ).fetchall()
        return [self._row_to_relation_dict(row) for row in rows]

    def fetch_rows_for_books(self, conn: sqlite3.Connection, books: list[str]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for book_batch in _chunked(books):
            placeholders = ",".join("?" for _ in book_batch)
            rows = conn.execute(
                self._relation_projection_sql(where_clause=f"source_book IN ({placeholders})", direction="edge"),
                (*book_batch, 5000000),
            ).fetchall()
            payload.extend(self._row_to_edge_dict(row) for row in rows)
        return payload

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

    def _relation_projection_sql(self, *, where_clause: str, direction: str = "edge") -> str:
        if direction in {"in", "symptom"}:
            target_expr = "subject"
        else:
            target_expr = "object"
        return f"""
            SELECT
                signature,
                subject,
                predicate,
                object,
                subject_type,
                object_type,
                source_book,
                source_chapter,
                fact_id,
                fact_ids_text,
                best_source_text,
                best_confidence,
                {target_expr} AS target
            FROM facts
            WHERE {where_clause}
            ORDER BY best_confidence DESC, signature ASC
            LIMIT ?
        """

    def _row_to_relation_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        target_type = _normalize_text(row["object_type"])
        if _normalize_text(row["target"]) == _normalize_text(row["subject"]):
            target_type = _normalize_text(row["subject_type"])
        payload = {
            "predicate": _normalize_text(row["predicate"]),
            "target": _normalize_text(row["target"]),
            "target_type": target_type or "other",
            "source_book": _normalize_text(row["source_book"]),
            "source_chapter": _normalize_text(row["source_chapter"]),
        }
        payload.update(self._evidence_payload_from_row(row))
        return payload

    def _row_to_edge_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = {
            "subject": _normalize_text(row["subject"]),
            "predicate": _normalize_text(row["predicate"]),
            "object": _normalize_text(row["object"]),
            "subject_type": _normalize_text(row["subject_type"]) or "other",
            "object_type": _normalize_text(row["object_type"]) or "other",
            "source_book": _normalize_text(row["source_book"]),
            "source_chapter": _normalize_text(row["source_chapter"]),
        }
        payload.update(self._evidence_payload_from_row(row))
        return payload

    def _evidence_payload_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        fact_ids = [item for item in _normalize_text(row["fact_ids_text"]).split(FACT_IDS_SEP) if item]
        payload: dict[str, Any] = {}
        fact_id = _normalize_text(row["fact_id"])
        if fact_id:
            payload["fact_id"] = fact_id
        if fact_ids:
            payload["fact_ids"] = fact_ids
        source_text = _normalize_text(row["best_source_text"])
        if source_text:
            payload["source_text"] = source_text
        confidence = row["best_confidence"]
        if confidence not in (None, ""):
            payload["confidence"] = float(confidence or 0.0)
        return payload
