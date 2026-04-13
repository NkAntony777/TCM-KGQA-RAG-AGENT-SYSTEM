from __future__ import annotations

import argparse
import json
import sqlite3
import sys
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
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "predicate_dispute_samples_latest.md"
DEFAULT_PREDICATES = [
    "药材基源",
    "药性特征",
    "利水化饮",
    "理气活血",
    "配伍禁忌",
    "食忌",
    "适应证",
    "功效",
]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _query_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return _rows_to_dicts(conn.execute(sql, params).fetchall())


def _predicate_payload(conn: sqlite3.Connection, predicate: str) -> dict[str, Any]:
    total = int(conn.execute("SELECT COUNT(*) FROM facts WHERE predicate = ?", (predicate,)).fetchone()[0])
    type_distribution = _query_rows(
        conn,
        """
        SELECT subject_type, object_type, COUNT(*) AS count
        FROM facts
        WHERE predicate = ?
        GROUP BY subject_type, object_type
        ORDER BY count DESC, subject_type ASC, object_type ASC
        LIMIT 12
        """,
        (predicate,),
    )
    top_objects = _query_rows(
        conn,
        """
        SELECT object, COUNT(*) AS count
        FROM facts
        WHERE predicate = ?
        GROUP BY object
        ORDER BY count DESC, object ASC
        LIMIT 15
        """,
        (predicate,),
    )
    top_books = _query_rows(
        conn,
        """
        SELECT source_book, COUNT(*) AS count
        FROM facts
        WHERE predicate = ? AND source_book <> ''
        GROUP BY source_book
        ORDER BY count DESC, source_book ASC
        LIMIT 12
        """,
        (predicate,),
    )
    object_equals_predicate = _query_rows(
        conn,
        """
        SELECT subject, object, subject_type, object_type, source_book, source_chapter
        FROM facts
        WHERE predicate = ? AND object = ?
        ORDER BY source_book ASC, subject ASC
        LIMIT 20
        """,
        (predicate, predicate),
    )
    examples = _query_rows(
        conn,
        """
        SELECT subject, predicate, object, subject_type, object_type, source_book, source_chapter
        FROM facts
        WHERE predicate = ?
        ORDER BY source_book ASC, subject ASC, object ASC
        LIMIT 20
        """,
        (predicate,),
    )
    cross_type_examples = _query_rows(
        conn,
        """
        SELECT subject, predicate, object, subject_type, object_type, source_book, source_chapter
        FROM facts
        WHERE predicate = ?
        ORDER BY subject_type ASC, object_type ASC, source_book ASC, subject ASC
        LIMIT 20
        """,
        (predicate,),
    )
    return {
        "predicate": predicate,
        "total": total,
        "type_distribution": type_distribution,
        "top_objects": top_objects,
        "top_books": top_books,
        "object_equals_predicate_examples": object_equals_predicate,
        "examples": examples,
        "cross_type_examples": cross_type_examples,
    }


def _render_rows(rows: list[dict[str, Any]], *, columns: list[str], limit: int) -> list[str]:
    if not rows:
        return ["- -"]
    rendered: list[str] = []
    for row in rows[:limit]:
        parts = [f"{column}={row.get(column, '-')}" for column in columns]
        rendered.append("- " + " | ".join(parts))
    return rendered


def render_markdown(payloads: list[dict[str, Any]], *, db_path: Path) -> str:
    lines = [
        "# Predicate Dispute Samples",
        "",
        f"- db_path: `{db_path}`",
        f"- predicates: `{', '.join(item['predicate'] for item in payloads)}`",
        "",
        "## 审阅重点",
        "",
        "- 先看 `type_distribution` 是否支持你的归一化假设。",
        "- 再看 `top_objects` 是否暴露出“谓词=宾语”或对象值域漂移。",
        "- 再看 `top_books`，判断该谓词是否其实只在某个来源体系中成立。",
        "- 如果同一谓词跨多个 `subject_type/object_type` 语义空间，就不应直接物理归一。",
        "",
    ]
    for payload in payloads:
        predicate = payload["predicate"]
        lines.extend(
            [
                f"## `{predicate}`",
                "",
                f"- total: `{payload['total']}`",
                "",
                "**类型分布**",
                "",
                *_render_rows(payload["type_distribution"], columns=["subject_type", "object_type", "count"], limit=12),
                "",
                "**高频对象值**",
                "",
                *_render_rows(payload["top_objects"], columns=["object", "count"], limit=15),
                "",
                "**主要来源书**",
                "",
                *_render_rows(payload["top_books"], columns=["source_book", "count"], limit=12),
                "",
                "**object = predicate 样本**",
                "",
                *_render_rows(
                    payload["object_equals_predicate_examples"],
                    columns=["subject", "subject_type", "object_type", "source_book", "source_chapter"],
                    limit=20,
                ),
                "",
                "**常规样本**",
                "",
                *_render_rows(
                    payload["examples"],
                    columns=["subject", "predicate", "object", "subject_type", "object_type", "source_book"],
                    limit=12,
                ),
                "",
                "**跨类型样本**",
                "",
                *_render_rows(
                    payload["cross_type_examples"],
                    columns=["subject", "predicate", "object", "subject_type", "object_type", "source_book"],
                    limit=12,
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render extended review samples for disputed predicates.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--predicates", nargs="*", default=DEFAULT_PREDICATES)
    args = parser.parse_args()

    with _connect(args.db_path) as conn:
        payloads = [_predicate_payload(conn, predicate) for predicate in args.predicates]
    markdown = render_markdown(payloads, db_path=args.db_path)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    print(args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
