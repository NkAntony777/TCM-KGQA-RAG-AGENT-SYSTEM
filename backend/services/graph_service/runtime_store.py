from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, TypeVar

from services.graph_service import runtime_importer, runtime_queries, runtime_schema

FACT_IDS_SEP = "\x1f"
_RUNTIME_STORE_LOCK = threading.RLock()
SQLITE_PARAM_BATCH = 800
T = TypeVar("T")
FORMULA_SUFFIXES = ("丸", "散", "汤", "饮", "膏", "丹", "方", "颗粒", "胶囊")
PATH_PRIORITY_ORDER: tuple[str, ...] = (
    "治疗证候",
    "功效",
    "使用药材",
    "治疗症状",
    "治法",
    "治疗疾病",
    "推荐方剂",
    "归经",
    "药性",
    "别名",
    "属于范畴",
    "常见症状",
)


def _path_priority_case_sql(column: str = "predicate") -> str:
    parts = ["CASE"]
    remaining = len(PATH_PRIORITY_ORDER)
    for index, predicate in enumerate(PATH_PRIORITY_ORDER):
        parts.append(f" WHEN {column} = '{predicate}' THEN {remaining - index}")
    parts.append(" ELSE 0 END")
    return "".join(parts)


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
        return runtime_schema._ensure_schema(self, conn)

    def _import_legacy_sources(self, conn: sqlite3.Connection) -> None:
        return runtime_importer._import_legacy_sources(self, conn)

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
        return runtime_queries.stats(self, conn=conn)

    def list_books(self, *, limit: int, keyword: str = "") -> list[dict[str, Any]]:
        return runtime_queries.list_books(self, limit=limit, keyword=keyword)

    def total_books(self, keyword: str = "") -> int:
        return runtime_queries.total_books(self, keyword)

    def book_total(self, book_name: str) -> int:
        return runtime_queries.book_total(self, book_name)

    def book_triples(self, book_name: str, *, limit: int) -> list[dict[str, Any]]:
        return runtime_queries.book_triples(self, book_name, limit=limit)

    def resolve_entities(self, query: str, preferred_types: set[str] | None = None, *, limit: int = 20) -> list[str]:
        return runtime_queries.resolve_entities(self, query, preferred_types=preferred_types, limit=limit)

    def exact_entities(self, query: str, preferred_types: set[str] | None = None, *, limit: int = 20) -> list[str]:
        return runtime_queries.exact_entities(self, query, preferred_types=preferred_types, limit=limit)

    def _entity_match_sort_key(self, query: str, name: str) -> tuple[float, int, str]:
        return runtime_queries._entity_match_sort_key(self, query, name)

    def entity_type(self, entity_name: str) -> str:
        return runtime_queries.entity_type(self, entity_name)

    def collect_relations(self, entity_name: str) -> list[dict[str, Any]]:
        return runtime_queries.collect_relations(self, entity_name)

    def path_neighbors(self, entity_name: str, *, limit: int = 24) -> list[dict[str, Any]]:
        return runtime_queries.path_neighbors(self, entity_name, limit=limit)

    def adjacent_names(self, entity_name: str) -> list[str]:
        return runtime_queries.adjacent_names(self, entity_name)

    def two_hop_bridges(self, start: str, end: str, *, limit: int = 8) -> list[str]:
        return runtime_queries.two_hop_bridges(self, start, end, limit=limit)

    def first_edge_between(self, source: str, target: str) -> dict[str, Any] | None:
        return runtime_queries.first_edge_between(self, source, target)

    def recommended_formulas(self, syndrome_name: str) -> list[str]:
        return runtime_queries.recommended_formulas(self, syndrome_name)

    def syndromes_for_symptom(self, symptom_name: str) -> list[dict[str, Any]]:
        return runtime_queries.syndromes_for_symptom(self, symptom_name)

    def fetch_rows_for_books(self, conn: sqlite3.Connection, books: list[str]) -> list[dict[str, Any]]:
        return runtime_queries.fetch_rows_for_books(self, conn, books)

    def _import_evidence_rows(self, conn: sqlite3.Connection, rows: Iterator[dict[str, Any]]) -> int:
        return runtime_importer._import_evidence_rows(self, conn, rows)

    def _flush_evidence_batch(self, conn: sqlite3.Connection, payload: list[tuple[Any, ...]]) -> int:
        return runtime_importer._flush_evidence_batch(self, conn, payload)

    def _import_fact_rows(self, conn: sqlite3.Connection, rows: Iterator[dict[str, Any]], *, dataset_scope: str) -> set[str]:
        return runtime_importer._import_fact_rows(self, conn, rows, dataset_scope=dataset_scope)

    def _refresh_fact_metadata(self, conn: sqlite3.Connection, signatures: set[str]) -> None:
        return runtime_importer._refresh_fact_metadata(self, conn, signatures)

    def _upsert_entities_for_signatures(self, conn: sqlite3.Connection, signatures: set[str]) -> None:
        return runtime_importer._upsert_entities_for_signatures(self, conn, signatures)

    def _rebuild_entities(self, conn: sqlite3.Connection) -> None:
        return runtime_importer._rebuild_entities(self, conn)

    def _relation_projection_sql(self, *, where_clause: str, direction: str = "edge") -> str:
        return runtime_queries._relation_projection_sql(self, where_clause=where_clause, direction=direction)

    def _row_to_relation_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return runtime_queries._row_to_relation_dict(self, row)

    def _row_to_edge_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        return runtime_queries._row_to_edge_dict(self, row)

    def _evidence_payload_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return runtime_queries._evidence_payload_from_row(self, row)
