from __future__ import annotations

import argparse
import json
import sqlite3
import sys
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

from services.common.evidence_payloads import normalize_source_chapter_label


DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "ontology_likely_dirty_batch1_candidates_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "ontology_likely_dirty_batch1_candidates_latest.md"

BATCH1_TARGETS: tuple[dict[str, str], ...] = (
    {
        "predicate": "归经",
        "subject_type": "channel",
        "object_type": "channel",
        "action": "delete_or_retype_relation",
        "reason": "经脉到经脉/穴位关系不应挂在归经主边上",
    },
    {
        "predicate": "使用药材",
        "subject_type": "herb",
        "object_type": "herb",
        "action": "delete_or_retype_relation",
        "reason": "药到药组合更像配伍/列举，不应挂在使用药材主边上",
    },
    {
        "predicate": "使用药材",
        "subject_type": "category",
        "object_type": "herb",
        "action": "retype_relation",
        "reason": "分类条目列举药物，不应继续使用使用药材主边",
    },
    {
        "predicate": "治疗症状",
        "subject_type": "book",
        "object_type": "symptom",
        "action": "delete_or_retype_relation",
        "reason": "书籍论及症状，不等于书籍治疗症状",
    },
    {
        "predicate": "治疗症状",
        "subject_type": "chapter",
        "object_type": "symptom",
        "action": "delete_or_retype_relation",
        "reason": "篇章描述症状，不等于篇章治疗症状",
    },
)


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_target_payload(conn: sqlite3.Connection, target: dict[str, str]) -> dict[str, Any]:
    predicate = target["predicate"]
    subject_type = target["subject_type"]
    object_type = target["object_type"]
    total_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM facts
        WHERE predicate = ? AND subject_type = ? AND object_type = ?
        """,
        (predicate, subject_type, object_type),
    ).fetchone()
    books = conn.execute(
        """
        SELECT source_book, COUNT(*) AS count
        FROM facts
        WHERE predicate = ? AND subject_type = ? AND object_type = ?
        GROUP BY source_book
        ORDER BY count DESC, source_book ASC
        LIMIT 12
        """,
        (predicate, subject_type, object_type),
    ).fetchall()
    rows = conn.execute(
        """
        SELECT
            signature,
            subject,
            object,
            subject_type,
            object_type,
            source_book,
            source_chapter,
            fact_id,
            best_source_text,
            best_confidence
        FROM facts
        WHERE predicate = ? AND subject_type = ? AND object_type = ?
        ORDER BY best_confidence DESC, source_book ASC, signature ASC
        LIMIT 30
        """,
        (predicate, subject_type, object_type),
    ).fetchall()
    examples: list[dict[str, Any]] = []
    for row in rows:
        source_book = str(row["source_book"] or "").strip()
        source_chapter = normalize_source_chapter_label(
            source_book=source_book,
            source_chapter=str(row["source_chapter"] or "").strip(),
        )
        examples.append(
            {
                "signature": str(row["signature"] or "").strip(),
                "fact_id": str(row["fact_id"] or "").strip(),
                "subject": str(row["subject"] or "").strip(),
                "object": str(row["object"] or "").strip(),
                "subject_type": str(row["subject_type"] or "").strip(),
                "object_type": str(row["object_type"] or "").strip(),
                "source_book": source_book,
                "source_chapter": source_chapter or None,
                "source_text_preview": str(row["best_source_text"] or "").strip()[:220],
                "confidence": float(row["best_confidence"] or 0.0),
            }
        )
    return {
        **target,
        "count_total": int(total_row["count"] or 0) if total_row else 0,
        "top_books": [{"source_book": str(row["source_book"] or "").strip(), "count": int(row["count"] or 0)} for row in books],
        "examples": examples,
    }


def build_payload(*, db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        targets = [_fetch_target_payload(conn, target) for target in BATCH1_TARGETS]
    return {
        "generated_at": _utc_now_text(),
        "db_path": str(db_path),
        "target_count": len(targets),
        "targets": targets,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Ontology Likely-Dirty Batch 1 Candidates")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    lines.append(f"- 数据库：`{payload.get('db_path', '')}`")
    lines.append(f"- 目标组合数：`{payload.get('target_count', 0)}`")
    for item in payload.get("targets", []):
        lines.append("")
        lines.append(f"## {item['predicate']} | {item['subject_type']} -> {item['object_type']}")
        lines.append("")
        lines.append(f"- count_total：`{item.get('count_total', 0)}`")
        lines.append(f"- 建议动作：`{item.get('action', '')}`")
        lines.append(f"- 原因：{item.get('reason', '')}")
        books = item.get("top_books", [])
        if books:
            lines.append("")
            lines.append("来源书籍 Top:")
            for book in books[:8]:
                lines.append(f"- `{book['source_book']}`: `{book['count']}`")
        examples = item.get("examples", [])
        if examples:
            lines.append("")
            lines.append("代表样本:")
            for example in examples[:8]:
                chapter = example.get("source_chapter") or "正文/未规范化"
                lines.append(
                    f"- `{example['subject']} -> {example['object']}` "
                    f"@ `{example['source_book']}/{chapter}` "
                    f"`fact_id={example['fact_id']}`"
                )
                preview = str(example.get("source_text_preview", "")).strip()
                if preview:
                    lines.append(f"  证据预览：`{preview}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export exact batch-1 likely-dirty candidate rows for manual review and patch planning.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_payload(db_path=args.db_path)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
