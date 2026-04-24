
from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from typing import Any, TypeVar, Iterator

FACT_IDS_SEP = "\x1f"
SQLITE_PARAM_BATCH = 800
T = TypeVar("T")
FORMULA_SUFFIXES = ("丸", "散", "汤", "饮", "膏", "丹", "方", "颗粒", "胶囊")
PATH_PRIORITY_ORDER: tuple[str, ...] = (
    "治疗证候", "功效", "使用药材", "治疗症状", "治法", "治疗疾病", "推荐方剂", "归经", "药性", "别名", "属于范畴", "常见症状",
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


def _chunked(items: list[T], size: int = SQLITE_PARAM_BATCH) -> Iterator[list[T]]:
    for start in range(0, len(items), max(1, size)):
        yield items[start : start + max(1, size)]

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
    merged_names = exact + [row["name"] for row in contains_rows]
    scored_names = sorted(
        merged_names,
        key=lambda name: self._entity_match_sort_key(normalized, str(name)),
    )
    for name in scored_names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered[: max(1, limit)]

def exact_entities(self, query: str, preferred_types: set[str] | None = None, *, limit: int = 20) -> list[str]:
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
        rows = conn.execute(
            f"SELECT name FROM entities WHERE name = ?{type_filter} ORDER BY name ASC LIMIT ?",
            (*params, max(1, limit)),
        ).fetchall()
    return [row["name"] for row in rows if _normalize_text(row["name"])]

def _entity_match_sort_key(self, query: str, name: str) -> tuple[float, int, str]:
    normalized_query = _normalize_text(query)
    candidate = _normalize_text(name)
    if not candidate:
        return (float("inf"), 0, "")
    exact = candidate == normalized_query
    query_contains = candidate and candidate in normalized_query
    candidate_contains = normalized_query and normalized_query in candidate
    starts = normalized_query.startswith(candidate) or candidate.startswith(normalized_query)
    formula_bonus = (
        1
        if any(candidate.endswith(suffix) and normalized_query.endswith(suffix) for suffix in FORMULA_SUFFIXES)
        else 0
    )
    length_gap = abs(len(normalized_query) - len(candidate))
    overlap = len(candidate) / max(1, len(normalized_query)) if query_contains else 0.0
    score = 0.0
    if exact:
        score += 100.0
    if query_contains:
        score += 60.0 + overlap * 20.0
    if candidate_contains:
        score += 25.0 - min(length_gap, 12)
    if starts:
        score += 8.0
    if formula_bonus:
        score += 6.0
    score += min(len(candidate), 24) * 0.4
    score -= math.log1p(max(0, length_gap)) * 2.0
    return (-score, -len(candidate), candidate)

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

def path_neighbors(self, entity_name: str, *, limit: int = 24) -> list[dict[str, Any]]:
    self.ensure_ready()
    entity = _normalize_text(entity_name)
    if not entity:
        return []
    priority_case = _path_priority_case_sql("predicate")
    with closing(self._connect()) as conn:
        rows = conn.execute(
            f"""
            WITH candidates AS (
                SELECT
                    predicate,
                    object AS target,
                    object_type AS target_type,
                    'out' AS direction,
                    source_book,
                    source_chapter,
                    fact_id,
                    fact_ids_text,
                    best_source_text AS source_text,
                    best_confidence AS confidence,
                    {priority_case} AS predicate_priority
                FROM facts
                WHERE subject = ?
                UNION ALL
                SELECT
                    predicate,
                    subject AS target,
                    subject_type AS target_type,
                    'in' AS direction,
                    source_book,
                    source_chapter,
                    fact_id,
                    fact_ids_text,
                    best_source_text AS source_text,
                    best_confidence AS confidence,
                    {priority_case} AS predicate_priority
                FROM facts
                WHERE object = ?
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY target
                        ORDER BY predicate_priority DESC, confidence DESC, direction ASC, predicate ASC
                    ) AS rn
                FROM candidates
                WHERE target <> ''
            )
            SELECT
                predicate,
                target AS object,
                target_type AS object_type,
                direction,
                source_book,
                source_chapter,
                fact_id,
                fact_ids_text,
                source_text,
                confidence
            FROM ranked
            WHERE rn = 1
            ORDER BY predicate_priority DESC, confidence DESC, target ASC
            LIMIT ?
            """,
            (entity, entity, max(1, limit)),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "predicate": _normalize_text(row["predicate"]),
            "target": _normalize_text(row["object"]),
            "target_type": _normalize_text(row["object_type"]) or "other",
            "direction": _normalize_text(row["direction"]) or "out",
            "source_book": _normalize_text(row["source_book"]),
            "source_chapter": _normalize_text(row["source_chapter"]),
            "fact_id": _normalize_text(row["fact_id"]),
            "fact_ids": [item for item in _normalize_text(row["fact_ids_text"]).split(FACT_IDS_SEP) if item],
            "source_text": _normalize_text(row["source_text"]),
            "confidence": float(row["confidence"] or 0.0),
        }
        items.append(item)
    return items

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

def two_hop_bridges(self, start: str, end: str, *, limit: int = 8) -> list[str]:
    start_entity = _normalize_text(start)
    end_entity = _normalize_text(end)
    if not start_entity or not end_entity:
        return []
    start_neighbors = self.adjacent_names(start_entity)
    end_neighbors = set(self.adjacent_names(end_entity))
    bridges: list[str] = []
    seen = set()
    for target in start_neighbors:
        if not target or target in {start_entity, end_entity} or target not in end_neighbors or target in seen:
            continue
        seen.add(target)
        bridges.append(target)
        if len(bridges) >= max(1, limit):
            break
    return bridges

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
