from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from services.graph_service.runtime_store import _iter_json_array_rows, _iter_jsonl_rows

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "services" / "graph_service" / "data"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify runtime graph source_chapter repair results.")
    parser.add_argument("--current-db", type=Path, default=DATA_DIR / "graph_runtime.db")
    parser.add_argument("--backup-db", type=Path, required=True)
    parser.add_argument("--current-evidence", type=Path, default=DATA_DIR / "graph_runtime.evidence.jsonl")
    parser.add_argument("--backup-graph", type=Path, default=DATA_DIR / "graph_runtime.20260408_144757.bak.json")
    parser.add_argument("--current-graph", type=Path, default=DATA_DIR / "graph_runtime.json")
    parser.add_argument("--backup-evidence", type=Path, default=DATA_DIR / "graph_runtime.evidence.20260408_144757.bak.jsonl")
    parser.add_argument(
        "--fact-id",
        action="append",
        default=[],
        help="Specific fact_id to inspect in current evidence.",
    )
    return parser.parse_args()


def _db_stats(path: Path, *, books: list[str]) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        scope_dist = {
            str(row["dataset_scope"]): int(row["count"])
            for row in conn.execute(
                "SELECT dataset_scope, COUNT(*) AS count FROM facts GROUP BY dataset_scope ORDER BY dataset_scope"
            ).fetchall()
        }
        stats = {
            "db_path": str(path),
            "facts": int(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]),
            "runtime_facts": int(conn.execute("SELECT COUNT(*) FROM facts WHERE dataset_scope = 'runtime'").fetchone()[0]),
            "evidence": int(conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]),
            "nodes": int(conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]),
            "scope_dist": scope_dist,
            "tcm_mkg": {
                "facts_runtime_scope": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM facts WHERE dataset_scope = 'runtime' AND source_book = 'TCM-MKG'"
                    ).fetchone()[0]
                ),
                "facts_modern_scope": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM facts WHERE dataset_scope = 'modern_graph' AND source_book = 'TCM-MKG'"
                    ).fetchone()[0]
                ),
                "evidence": int(
                    conn.execute("SELECT COUNT(*) FROM evidence WHERE source_book = 'TCM-MKG'").fetchone()[0]
                ),
            },
            "books": {},
        }
        for book in books:
            stats["books"][book] = {
                "facts": int(conn.execute("SELECT COUNT(*) FROM facts WHERE source_book = ?", (book,)).fetchone()[0]),
                "evidence": int(conn.execute("SELECT COUNT(*) FROM evidence WHERE source_book = ?", (book,)).fetchone()[0]),
            }
        return stats
    finally:
        conn.close()


def _inspect_fact_ids(evidence_path: Path, fact_ids: list[str]) -> list[dict[str, Any]]:
    wanted = {fact_id.strip() for fact_id in fact_ids if fact_id.strip()}
    if not wanted:
        return []
    found: list[dict[str, Any]] = []
    for row in _iter_jsonl_rows(evidence_path):
        fact_id = str(row.get("fact_id", "")).strip()
        if fact_id not in wanted:
            continue
        found.append(
            {
                "fact_id": fact_id,
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                "source_text_preview": str(row.get("source_text", "")).strip()[:120],
            }
        )
        wanted.discard(fact_id)
        if not wanted:
            break
    return found


def _count_graph_rows(path: Path) -> int:
    return sum(1 for _ in _iter_json_array_rows(path))


def _count_evidence_rows(path: Path) -> int:
    return sum(1 for _ in _iter_jsonl_rows(path))


def main() -> int:
    args = _parse_args()
    books = ["697-止园医话", "669-名师垂教", "221-余无言"]
    current = _db_stats(args.current_db, books=books)
    backup = _db_stats(args.backup_db, books=books)
    fact_rows = _inspect_fact_ids(args.current_evidence, args.fact_id)
    payload = {
        "current": current,
        "backup": backup,
        "delta": {
            "facts": current["facts"] - backup["facts"],
            "runtime_facts": current["runtime_facts"] - backup["runtime_facts"],
            "evidence": current["evidence"] - backup["evidence"],
            "nodes": current["nodes"] - backup["nodes"],
            "books": {
                book: {
                    "facts": current["books"][book]["facts"] - backup["books"][book]["facts"],
                    "evidence": current["books"][book]["evidence"] - backup["books"][book]["evidence"],
                }
                for book in books
            },
        },
        "files": {
            "current_graph_rows": _count_graph_rows(args.current_graph),
            "backup_graph_rows": _count_graph_rows(args.backup_graph),
            "current_evidence_rows": _count_evidence_rows(args.current_evidence),
            "backup_evidence_rows": _count_evidence_rows(args.backup_evidence),
        },
        "inspected_fact_ids": fact_rows,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
