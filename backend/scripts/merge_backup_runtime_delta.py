from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.graph_service.runtime_store import (
    FACT_IDS_SEP,
    RuntimeGraphStore,
    RuntimeGraphStoreSettings,
    _iter_json_array_rows,
    _iter_jsonl_rows,
)

DATA_DIR = BACKEND_DIR / "services" / "graph_service" / "data"
DEFAULT_GRAPH_PATH = DATA_DIR / "graph_runtime.json"
DEFAULT_EVIDENCE_PATH = DATA_DIR / "graph_runtime.evidence.jsonl"
DEFAULT_DB_PATH = DATA_DIR / "graph_runtime.db"
DEFAULT_SAMPLE_GRAPH_PATH = DATA_DIR / "sample_graph.json"
DEFAULT_SAMPLE_EVIDENCE_PATH = DATA_DIR / "sample_graph.evidence.jsonl"
DEFAULT_MODERN_GRAPH_PATH = DATA_DIR / "modern_graph_runtime.jsonl"
DEFAULT_MODERN_EVIDENCE_PATH = DATA_DIR / "modern_graph_runtime.evidence.jsonl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge backup-only runtime facts/evidence into current graph runtime files and rebuild DB.")
    parser.add_argument("--current-db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--backup-db", type=Path, required=True)
    parser.add_argument("--graph-path", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--sample-graph-path", type=Path, default=DEFAULT_SAMPLE_GRAPH_PATH)
    parser.add_argument("--sample-evidence-path", type=Path, default=DEFAULT_SAMPLE_EVIDENCE_PATH)
    parser.add_argument("--modern-graph-path", type=Path, default=DEFAULT_MODERN_GRAPH_PATH)
    parser.add_argument("--modern-evidence-path", type=Path, default=DEFAULT_MODERN_EVIDENCE_PATH)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _connect_pair(current_db: Path, backup_db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS current_db", (str(current_db),))
    conn.execute("ATTACH DATABASE ? AS backup_db", (str(backup_db),))
    return conn


DELTA_WHERE = """
    b.dataset_scope = 'runtime'
    AND c.signature IS NULL
    AND NOT EXISTS (
        SELECT 1
        FROM backup_db.fact_members AS bm
        JOIN current_db.fact_members AS cm ON cm.fact_id = bm.fact_id
        WHERE bm.signature = b.signature
    )
"""


def _iter_delta_graph_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        f"""
        SELECT
            b.signature,
            b.subject,
            b.predicate,
            b.object,
            b.subject_type,
            b.object_type,
            b.source_book,
            b.source_chapter,
            b.fact_id,
            b.fact_ids_text
        FROM backup_db.facts AS b
        LEFT JOIN current_db.facts AS c ON c.signature = b.signature
        WHERE {DELTA_WHERE}
        ORDER BY b.rowid
        """
    )
    for row in cursor:
        fact_ids = [item for item in str(row["fact_ids_text"] or "").split(FACT_IDS_SEP) if item]
        fact_id = str(row["fact_id"] or "").strip()
        if fact_id and fact_id not in fact_ids:
            fact_ids.append(fact_id)
        yield {
            "subject": str(row["subject"] or "").strip(),
            "predicate": str(row["predicate"] or "").strip(),
            "object": str(row["object"] or "").strip(),
            "subject_type": str(row["subject_type"] or "").strip(),
            "object_type": str(row["object_type"] or "").strip(),
            "source_book": str(row["source_book"] or "").strip(),
            "source_chapter": str(row["source_chapter"] or "").strip(),
            "fact_id": fact_id,
            "fact_ids": fact_ids,
        }


def _iter_delta_evidence_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        f"""
        SELECT DISTINCT
            e.fact_id,
            e.source_book,
            e.source_chapter,
            e.source_text,
            e.confidence
        FROM backup_db.facts AS b
        LEFT JOIN current_db.facts AS c ON c.signature = b.signature
        JOIN backup_db.fact_members AS bm ON bm.signature = b.signature
        JOIN backup_db.evidence AS e ON e.fact_id = bm.fact_id
        LEFT JOIN current_db.evidence AS ce ON ce.fact_id = e.fact_id
        WHERE {DELTA_WHERE}
          AND ce.fact_id IS NULL
        ORDER BY e.fact_id
        """
    )
    for row in cursor:
        yield {
            "fact_id": str(row["fact_id"] or "").strip(),
            "source_book": str(row["source_book"] or "").strip(),
            "source_chapter": str(row["source_chapter"] or "").strip(),
            "source_text": str(row["source_text"] or "").strip(),
            "confidence": float(row["confidence"] or 0.0),
        }


def _count_delta(conn: sqlite3.Connection) -> dict[str, int]:
    facts = int(
        conn.execute(
            f"""
            SELECT COUNT(*)
            FROM backup_db.facts AS b
            LEFT JOIN current_db.facts AS c ON c.signature = b.signature
            WHERE {DELTA_WHERE}
            """
        ).fetchone()[0]
    )
    evidence = int(
        conn.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT e.fact_id
                FROM backup_db.facts AS b
                LEFT JOIN current_db.facts AS c ON c.signature = b.signature
                JOIN backup_db.fact_members AS bm ON bm.signature = b.signature
                JOIN backup_db.evidence AS e ON e.fact_id = bm.fact_id
                LEFT JOIN current_db.evidence AS ce ON ce.fact_id = e.fact_id
                WHERE {DELTA_WHERE}
                  AND ce.fact_id IS NULL
            )
            """
        ).fetchone()[0]
    )
    return {"facts": facts, "evidence": evidence}


def _write_merged_graph(current_graph: Path, output_path: Path, conn: sqlite3.Connection) -> int:
    total = 0
    with output_path.open("w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        for row in _iter_json_array_rows(current_graph):
            if not first:
                fout.write(",\n")
            fout.write("  ")
            json.dump(row, fout, ensure_ascii=False)
            first = False
            total += 1
        for row in _iter_delta_graph_rows(conn):
            if not first:
                fout.write(",\n")
            fout.write("  ")
            json.dump(row, fout, ensure_ascii=False)
            first = False
            total += 1
        fout.write("\n]\n")
    return total


def _write_merged_evidence(current_evidence: Path, output_path: Path, conn: sqlite3.Connection) -> int:
    total = 0
    with output_path.open("w", encoding="utf-8") as fout:
        for row in _iter_jsonl_rows(current_evidence):
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            total += 1
        for row in _iter_delta_evidence_rows(conn):
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            total += 1
    return total


def _rebuild_runtime_db(
    *,
    graph_path: Path,
    evidence_path: Path,
    db_path: Path,
    sample_graph_path: Path,
    sample_evidence_path: Path,
    modern_graph_path: Path,
    modern_evidence_path: Path,
) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="graph-runtime-merge-", dir=str(db_path.parent)))
    rebuilt_db_path = temp_dir / db_path.name
    store = RuntimeGraphStore(
        RuntimeGraphStoreSettings(
            graph_path=graph_path,
            evidence_path=evidence_path,
            db_path=rebuilt_db_path,
            sample_graph_path=sample_graph_path if sample_graph_path.exists() else None,
            sample_evidence_path=sample_evidence_path if sample_evidence_path.exists() else None,
            modern_graph_path=modern_graph_path if modern_graph_path.exists() else None,
            modern_evidence_path=modern_evidence_path if modern_evidence_path.exists() else None,
        )
    )
    store.ensure_ready()
    return rebuilt_db_path, temp_dir


def _cleanup_temp_dir(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    shutil.rmtree(path, ignore_errors=True)


def _replace_with_backup(current_path: Path, replacement_path: Path, *, stamp: str) -> str:
    backup_path = current_path.with_name(f"{current_path.stem}.{stamp}.bak{current_path.suffix}")
    if current_path.exists():
        shutil.move(str(current_path), str(backup_path))
    shutil.move(str(replacement_path), str(current_path))
    return str(backup_path) if backup_path.exists() else ""


def main() -> int:
    args = _parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = _connect_pair(args.current_db, args.backup_db)
    try:
        delta = _count_delta(conn)
        payload: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "current_db": str(args.current_db),
            "backup_db": str(args.backup_db),
            "graph_path": str(args.graph_path),
            "evidence_path": str(args.evidence_path),
            "apply": bool(args.apply),
            "delta": delta,
            "backups": {},
        }
        if not args.apply:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        temp_graph = args.graph_path.with_name(f"{args.graph_path.stem}.{stamp}.merging.json")
        temp_evidence = args.evidence_path.with_name(f"{args.evidence_path.stem}.{stamp}.merging{args.evidence_path.suffix}")
        payload["merged_graph_rows"] = _write_merged_graph(args.graph_path, temp_graph, conn)
        payload["merged_evidence_rows"] = _write_merged_evidence(args.evidence_path, temp_evidence, conn)
        rebuilt_db_temp_dir: Path | None = None
        try:
            rebuilt_db, rebuilt_db_temp_dir = _rebuild_runtime_db(
                graph_path=temp_graph,
                evidence_path=temp_evidence,
                db_path=args.current_db,
                sample_graph_path=args.sample_graph_path,
                sample_evidence_path=args.sample_evidence_path,
                modern_graph_path=args.modern_graph_path,
                modern_evidence_path=args.modern_evidence_path,
            )

            payload["backups"]["graph_path"] = _replace_with_backup(args.graph_path, temp_graph, stamp=stamp)
            payload["backups"]["evidence_path"] = _replace_with_backup(args.evidence_path, temp_evidence, stamp=stamp)
            payload["backups"]["db_path"] = _replace_with_backup(args.current_db, rebuilt_db, stamp=stamp)
        finally:
            _cleanup_temp_dir(rebuilt_db_temp_dir)

        manifest = DATA_DIR / f"graph_runtime.merge_backup_delta.{stamp}.json"
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
