from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
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


DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "predicate_normalization_candidates_latest.json"

CANONICAL_PREDICATES = {
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

PROPOSED_RULES: dict[str, dict[str, Any]] = {
    "表现症状": {"action": "alias_to_existing_predicate", "target": "常见症状", "risk": "low"},
    "相关症状": {"action": "alias_to_existing_predicate", "target": "常见症状", "risk": "low"},
    "药性特征": {"action": "family_only", "target": "药性", "risk": "medium"},
    "药味": {"action": "family_only", "target": "五味", "risk": "medium"},
    "适应证": {"action": "family_only", "target": "现代适应证", "risk": "medium"},
    "现代适应证": {"action": "keep", "target": "", "risk": "medium"},
    "作用靶点": {"action": "keep", "target": "", "risk": "medium"},
    "关联靶点": {"action": "keep", "target": "", "risk": "medium"},
    "含有成分": {"action": "keep", "target": "", "risk": "medium"},
    "用法": {"action": "keep", "target": "", "risk": "low"},
    "药材基源": {"action": "keep", "target": "", "risk": "medium"},
    "五味": {"action": "keep", "target": "", "risk": "low"},
    "出处": {"action": "manual_review_required", "target": "", "risk": "high"},
    "利水化饮": {"action": "manual_review_required", "target": "", "risk": "high"},
    "理气活血": {"action": "manual_review_required", "target": "", "risk": "high"},
    "欲解时": {"action": "keep", "target": "", "risk": "high"},
}


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _default_rule(predicate: str) -> dict[str, Any]:
    if predicate in CANONICAL_PREDICATES:
        return {"action": "keep", "target": "", "risk": "low"}
    return PROPOSED_RULES.get(predicate, {"action": "manual_review_required", "target": "", "risk": "high"})


def _fetch_summary_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT predicate, COUNT(*) AS count
        FROM facts
        GROUP BY predicate
        ORDER BY count DESC, predicate ASC
        """
    ).fetchall()


def _fetch_type_distribution(conn: sqlite3.Connection, predicate: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT subject_type, object_type, COUNT(*) AS count
        FROM facts
        WHERE predicate = ?
        GROUP BY subject_type, object_type
        ORDER BY count DESC, subject_type ASC, object_type ASC
        LIMIT 10
        """,
        (predicate,),
    ).fetchall()
    return [
        {"subject_type": str(row["subject_type"] or ""), "object_type": str(row["object_type"] or ""), "count": int(row["count"])}
        for row in rows
    ]


def _fetch_source_books(conn: sqlite3.Connection, predicate: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT source_book, COUNT(*) AS count
        FROM facts
        WHERE predicate = ? AND source_book <> ''
        GROUP BY source_book
        ORDER BY count DESC, source_book ASC
        LIMIT 10
        """,
        (predicate,),
    ).fetchall()
    return [{"source_book": str(row["source_book"] or ""), "count": int(row["count"])} for row in rows]


def _fetch_examples(conn: sqlite3.Connection, predicate: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT subject, predicate, object, subject_type, object_type, source_book, source_chapter
        FROM facts
        WHERE predicate = ?
        ORDER BY best_confidence DESC, source_book ASC, subject ASC
        LIMIT 8
        """,
        (predicate,),
    ).fetchall()
    return [
        {
            "subject": str(row["subject"] or ""),
            "predicate": str(row["predicate"] or ""),
            "object": str(row["object"] or ""),
            "subject_type": str(row["subject_type"] or ""),
            "object_type": str(row["object_type"] or ""),
            "source_book": str(row["source_book"] or ""),
            "source_chapter": str(row["source_chapter"] or ""),
        }
        for row in rows
    ]


def run_audit(*, db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        summary_rows = _fetch_summary_rows(conn)
        candidates: list[dict[str, Any]] = []
        action_counter: Counter[str] = Counter()
        risk_counter: Counter[str] = Counter()
        for row in summary_rows:
            predicate = str(row["predicate"] or "").strip()
            count = int(row["count"] or 0)
            rule = _default_rule(predicate)
            action_counter[rule["action"]] += 1
            risk_counter[rule["risk"]] += 1
            candidates.append(
                {
                    "predicate": predicate,
                    "count": count,
                    "canonical": predicate in CANONICAL_PREDICATES,
                    "proposed_action": rule["action"],
                    "proposed_target_predicate": rule["target"],
                    "risk": rule["risk"],
                    "type_distribution": _fetch_type_distribution(conn, predicate),
                    "source_books": _fetch_source_books(conn, predicate),
                    "examples": _fetch_examples(conn, predicate),
                }
            )
    return {
        "generated_at": _utc_now_text(),
        "db_path": str(db_path),
        "candidate_count": len(candidates),
        "action_summary": dict(action_counter),
        "risk_summary": dict(risk_counter),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit predicate normalization candidates without modifying graph data.")
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
