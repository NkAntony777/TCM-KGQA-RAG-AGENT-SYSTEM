from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "services" / "graph_service" / "data"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze facts present in backup runtime DB but missing from rebuilt runtime DB.")
    parser.add_argument("--current-db", type=Path, default=DATA_DIR / "graph_runtime.db")
    parser.add_argument("--backup-db", type=Path, required=True)
    parser.add_argument("--top", type=int, default=20)
    return parser.parse_args()


def _fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    args = _parse_args()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS current_db", (str(args.current_db),))
    conn.execute("ATTACH DATABASE ? AS backup_db", (str(args.backup_db),))

    missing_where = (
        "b.dataset_scope = 'runtime' "
        "AND c.signature IS NULL"
    )

    payload = {
        "current_db": str(args.current_db),
        "backup_db": str(args.backup_db),
        "missing_runtime_facts": int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM backup_db.facts AS b
                LEFT JOIN current_db.facts AS c ON c.signature = b.signature
                WHERE b.dataset_scope = 'runtime' AND c.signature IS NULL
                """
            ).fetchone()[0]
        ),
        "top_books": _fetch_all(
            conn,
            f"""
            SELECT b.source_book, COUNT(*) AS count
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {missing_where}
            GROUP BY b.source_book
            ORDER BY count DESC, b.source_book
            LIMIT ?
            """,
            (args.top,),
        ),
        "top_predicates": _fetch_all(
            conn,
            f"""
            SELECT b.predicate, COUNT(*) AS count
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {missing_where}
            GROUP BY b.predicate
            ORDER BY count DESC, b.predicate
            LIMIT ?
            """,
            (args.top,),
        ),
        "top_book_predicates": _fetch_all(
            conn,
            f"""
            SELECT b.source_book, b.predicate, COUNT(*) AS count
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {missing_where}
            GROUP BY b.source_book, b.predicate
            ORDER BY count DESC, b.source_book, b.predicate
            LIMIT ?
            """,
            (args.top,),
        ),
        "top_entity_types": _fetch_all(
            conn,
            f"""
            SELECT b.subject_type, b.object_type, COUNT(*) AS count
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {missing_where}
            GROUP BY b.subject_type, b.object_type
            ORDER BY count DESC, b.subject_type, b.object_type
            LIMIT ?
            """,
            (args.top,),
        ),
        "sample_rows": _fetch_all(
            conn,
            f"""
            SELECT
                b.subject,
                b.predicate,
                b.object,
                b.subject_type,
                b.object_type,
                b.source_book,
                b.source_chapter,
                b.fact_id
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {missing_where}
            ORDER BY b.source_book, b.subject, b.predicate, b.object
            LIMIT ?
            """,
            (args.top,),
        ),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
