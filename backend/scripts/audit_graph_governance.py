from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.common.evidence_payloads import normalize_book_label
from services.common.evidence_payloads import normalize_source_chapter_label
from services.graph_service.relation_governance import RELATION_GOVERNANCE_RULES


DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "graph_governance_audit_latest.json"

CANONICAL_RELATIONS = {
    "常见症状",
    "表现症状",
    "相关症状",
    "推荐方剂",
    "治疗证候",
    "治疗症状",
    "治疗疾病",
    "功效",
    "治法",
    "归经",
    "使用药材",
    "别名",
    "属于范畴",
}

BOUNDARY_PREDICATES: tuple[str, ...] = tuple(
    predicate
    for predicate, rule in RELATION_GOVERNANCE_RULES.items()
    if rule.expected_subject_types and rule.expected_object_types
)


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _alias_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT subject, object, COUNT(*) AS support
        FROM facts
        WHERE predicate = '别名'
        GROUP BY subject, object
        """
    ).fetchall()
    adjacency: dict[str, set[str]] = {}
    for row in rows:
        left = str(row["subject"] or "").strip()
        right = str(row["object"] or "").strip()
        if not left or not right or left == right:
            continue
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    visited: set[str] = set()
    component_sizes: list[int] = []
    for node in adjacency:
        if node in visited:
            continue
        stack = [node]
        size = 0
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            size += 1
            stack.extend(neighbor for neighbor in adjacency.get(current, set()) if neighbor not in visited)
        component_sizes.append(size)
    return {
        "alias_edge_pairs": len(rows),
        "alias_nodes": len(adjacency),
        "component_count": len(component_sizes),
        "largest_components": sorted(component_sizes, reverse=True)[:10],
    }


def _relation_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT predicate, COUNT(*) AS count
        FROM facts
        GROUP BY predicate
        ORDER BY count DESC, predicate ASC
        """
    ).fetchall()
    suspicious = [
        {"predicate": str(row["predicate"]), "count": int(row["count"])}
        for row in rows
        if str(row["predicate"] or "").strip() not in CANONICAL_RELATIONS
    ]
    return {
        "predicate_count": len(rows),
        "top_predicates": [{"predicate": str(row["predicate"]), "count": int(row["count"])} for row in rows[:20]],
        "non_canonical_predicates": suspicious[:50],
    }


def _ontology_boundary_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for predicate in BOUNDARY_PREDICATES:
        rule = RELATION_GOVERNANCE_RULES[predicate]
        expected_subject_types = set(rule.expected_subject_types or set())
        expected_object_types = set(rule.expected_object_types or set())
        rows = conn.execute(
            """
            SELECT subject, object, subject_type, object_type, source_book
            FROM facts
            WHERE predicate = ?
            """,
            (predicate,),
        ).fetchall()
        mismatches = [
            row
            for row in rows
            if str(row["subject_type"] or "").strip() not in expected_subject_types
            or str(row["object_type"] or "").strip() not in expected_object_types
        ]
        if not mismatches:
            continue
        issues.append(
            {
                "predicate": predicate,
                "expected_subject_types": sorted(expected_subject_types),
                "expected_object_types": sorted(expected_object_types),
                "count_total": len(mismatches),
                "count_sampled": min(len(mismatches), 20),
                "examples": [
                    {
                        "subject": str(row["subject"]),
                        "object": str(row["object"]),
                        "subject_type": str(row["subject_type"]),
                        "object_type": str(row["object_type"]),
                        "source_book": str(row["source_book"] or ""),
                    }
                    for row in mismatches[:5]
                ],
            }
        )
    return {"boundary_issue_groups": issues}


def _source_chapter_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT fact_id, source_book, source_chapter
        FROM evidence
        WHERE source_chapter <> ''
        """
    ).fetchall()
    polluted = 0
    body_slug_rows = 0
    readable_prefixed_rows = 0
    polluted_examples: list[dict[str, Any]] = []
    body_slug_examples: list[dict[str, Any]] = []
    for row in rows:
        source_book = str(row["source_book"] or "").strip()
        source_chapter = str(row["source_chapter"] or "").strip()
        normalized_book = normalize_book_label(source_book)
        is_polluted = ("\n" in source_chapter) or ("\r" in source_chapter) or len(source_chapter) >= 120
        if is_polluted:
            polluted += 1
            if len(polluted_examples) < 10:
                polluted_examples.append(
                    {
                        "fact_id": str(row["fact_id"] or ""),
                        "source_book": source_book,
                        "source_chapter_preview": source_chapter[:160],
                    }
                )
        normalized_chapter = normalize_source_chapter_label(source_book=source_book, source_chapter=source_chapter)
        if normalized_book and (
            source_chapter.startswith(f"{source_book}_") or source_chapter.startswith(f"{normalized_book}_")
        ):
            if not normalized_chapter:
                body_slug_rows += 1
                if len(body_slug_examples) < 10:
                    body_slug_examples.append(
                        {
                            "fact_id": str(row["fact_id"] or ""),
                            "source_book": source_book,
                            "source_chapter": source_chapter,
                        }
                    )
            else:
                readable_prefixed_rows += 1
    return {
        "polluted_source_chapter_rows": polluted,
        "book_prefixed_body_slug_rows": body_slug_rows,
        "book_prefixed_readable_rows": readable_prefixed_rows,
        "polluted_examples": polluted_examples,
        "body_slug_examples": body_slug_examples,
    }


def _backup_residue_summary(data_dir: Path) -> dict[str, Any]:
    backup_files = sorted(str(path.name) for path in data_dir.glob("graph_runtime*.bak*"))
    repair_manifests = sorted(str(path.name) for path in data_dir.glob("graph_runtime.source_chapter_repair.*.json"))
    merge_manifests = sorted(str(path.name) for path in data_dir.glob("graph_runtime.merge_backup_delta.*.json"))
    return {
        "backup_files_count": len(backup_files),
        "repair_manifest_count": len(repair_manifests),
        "merge_manifest_count": len(merge_manifests),
        "backup_files_preview": backup_files[:20],
        "repair_manifests_preview": repair_manifests[:20],
        "merge_manifests_preview": merge_manifests[:20],
    }


def run_audit(*, db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        return {
            "generated_at": _utc_now_text(),
            "db_path": str(db_path),
            "alias": _alias_summary(conn),
            "relations": _relation_summary(conn),
            "ontology": _ontology_boundary_summary(conn),
            "source_chapter": _source_chapter_summary(conn),
            "backups": _backup_residue_summary(db_path.parent),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit graph governance surfaces for alias, relations, ontology, and source chapters.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run_audit(db_path=args.db_path)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
