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
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "herb_to_herb_dirty_subtypes_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "herb_to_herb_dirty_subtypes_latest.md"


PROCESSING_KEYWORDS = ("造法", "制法", "炼", "煅", "研", "为末", "为细末", "面糊", "炼膏", "作末", "升炼", "烧灰")
COMPOSITION_KEYWORDS = ("所合", "各", "一两", "二两", "三钱", "四钱", "七分", "八分", "丸", "散", "汤", "膏", "饮")
PAIRING_KEYWORDS = ("同捣", "同煎", "合煎", "外用", "并用", "和匀", "调敷", "调涂")


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def classify_subtype(source_text: str) -> str:
    text = str(source_text or "").strip()
    if any(keyword in text for keyword in PROCESSING_KEYWORDS):
        return "processing_or_preparation"
    if any(keyword in text for keyword in PAIRING_KEYWORDS):
        return "pairing_or_external_mix"
    if any(keyword in text for keyword in COMPOSITION_KEYWORDS):
        return "formula_component_listing"
    return "other_uncertain"


def run_analysis(*, db_path: Path, sample_per_subtype: int = 10) -> dict[str, Any]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                signature,
                fact_id,
                subject,
                object,
                source_book,
                source_chapter,
                best_source_text,
                best_confidence
            FROM facts
            WHERE predicate = '使用药材'
              AND subject_type = 'herb'
              AND object_type = 'herb'
            ORDER BY best_confidence DESC, source_book ASC, signature ASC
            """
        ).fetchall()

    subtype_counter: Counter[str] = Counter()
    books_by_subtype: dict[str, Counter[str]] = defaultdict(Counter)
    samples_by_subtype: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        source_text = str(row["best_source_text"] or "").strip()
        subtype = classify_subtype(source_text)
        subtype_counter[subtype] += 1
        books_by_subtype[subtype][str(row["source_book"] or "").strip()] += 1
        if len(samples_by_subtype[subtype]) < sample_per_subtype:
            samples_by_subtype[subtype].append(
                {
                    "signature": str(row["signature"] or "").strip(),
                    "fact_id": str(row["fact_id"] or "").strip(),
                    "subject": str(row["subject"] or "").strip(),
                    "object": str(row["object"] or "").strip(),
                    "source_book": str(row["source_book"] or "").strip(),
                    "source_chapter": str(row["source_chapter"] or "").strip(),
                    "source_text_preview": source_text[:240],
                    "confidence": float(row["best_confidence"] or 0.0),
                }
            )

    return {
        "generated_at": _utc_now_text(),
        "db_path": str(db_path),
        "summary": {
            "total_rows": sum(subtype_counter.values()),
            "subtype_counts": dict(subtype_counter),
        },
        "subtypes": {
            subtype: {
                "count": count,
                "top_books": [{"source_book": book, "count": value} for book, value in books_by_subtype[subtype].most_common(10)],
                "samples": samples_by_subtype[subtype],
            }
            for subtype, count in subtype_counter.items()
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Herb-to-Herb Dirty Subtypes")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    lines.append(f"- 数据库：`{payload.get('db_path', '')}`")
    summary = payload.get("summary", {})
    lines.append(f"- 总行数：`{summary.get('total_rows', 0)}`")
    lines.append("")
    for subtype, item in payload.get("subtypes", {}).items():
        lines.append(f"## {subtype}")
        lines.append("")
        lines.append(f"- count：`{item.get('count', 0)}`")
        books = item.get("top_books", [])
        if books:
            lines.append("来源书籍 Top:")
            for book in books[:6]:
                lines.append(f"- `{book['source_book']}`: `{book['count']}`")
        samples = item.get("samples", [])
        if samples:
            lines.append("")
            lines.append("代表样本:")
            for sample in samples[:6]:
                lines.append(
                    f"- `{sample['subject']} -> {sample['object']}` "
                    f"@ `{sample['source_book']}` `fact_id={sample['fact_id']}`"
                )
                if sample.get("source_text_preview"):
                    lines.append(f"  证据预览：`{sample['source_text_preview']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze remaining 使用药材 herb->herb dirty rows into coarse semantic subtypes without modifying the DB.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--sample-per-subtype", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run_analysis(db_path=args.db_path, sample_per_subtype=max(1, int(args.sample_per_subtype)))
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
