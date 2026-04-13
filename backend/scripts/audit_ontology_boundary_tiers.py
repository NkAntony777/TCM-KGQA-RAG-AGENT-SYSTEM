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

from services.graph_service.relation_governance import ACCEPTABLE_POLYSEMY as ACCEPTABLE
from services.graph_service.relation_governance import IN_SCHEMA
from services.graph_service.relation_governance import LIKELY_DIRTY as DIRTY
from services.graph_service.relation_governance import RELATION_GOVERNANCE_RULES
from services.graph_service.relation_governance import REVIEW_NEEDED as REVIEW
from services.graph_service.relation_governance import ontology_boundary_tier


DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "ontology_boundary_tiers_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "ontology_boundary_tiers_latest.md"


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def classify_boundary_tier(predicate: str, subject_type: str, object_type: str) -> str:
    return (
        ontology_boundary_tier(
            predicate=predicate,
            direction="out",
            anchor_entity_type=str(subject_type or "").strip(),
            target_type=str(object_type or "").strip(),
        )
        or IN_SCHEMA
    )


def _predicate_rows(conn: sqlite3.Connection, predicate: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT subject, object, subject_type, object_type, source_book
        FROM facts
        WHERE predicate = ?
        """,
        (predicate,),
    ).fetchall()


def run_audit(*, db_path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": _utc_now_text(),
        "db_path": str(db_path),
        "predicates": {},
        "summary": {
            "predicate_count": 0,
            "in_schema_rows": 0,
            "acceptable_polysemy_rows": 0,
            "review_needed_rows": 0,
            "likely_dirty_rows": 0,
        },
    }
    with _connect(db_path) as conn:
        for predicate, rule in RELATION_GOVERNANCE_RULES.items():
            if not rule.expected_subject_types or not rule.expected_object_types:
                continue
            rows = _predicate_rows(conn, predicate)
            tier_counter: Counter[str] = Counter()
            combo_counter: Counter[tuple[str, str, str]] = Counter()
            book_counter: dict[str, Counter[str]] = defaultdict(Counter)
            examples: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in rows:
                subject_type = str(row["subject_type"] or "").strip()
                object_type = str(row["object_type"] or "").strip()
                tier = classify_boundary_tier(predicate, subject_type, object_type)
                tier_counter[tier] += 1
                if tier == IN_SCHEMA:
                    continue
                combo_counter[(tier, subject_type, object_type)] += 1
                book_counter[tier][str(row["source_book"] or "").strip()] += 1
                if len(examples[tier]) < 6:
                    examples[tier].append(
                        {
                            "subject": str(row["subject"] or "").strip(),
                            "object": str(row["object"] or "").strip(),
                            "subject_type": subject_type,
                            "object_type": object_type,
                            "source_book": str(row["source_book"] or "").strip(),
                        }
                    )

            payload["predicates"][predicate] = {
                "expected_subject_types": sorted(rule.expected_subject_types or []),
                "expected_object_types": sorted(rule.expected_object_types or []),
                "tier_counts": dict(tier_counter),
                "top_combos": [
                    {
                        "tier": tier,
                        "subject_type": subject_type,
                        "object_type": object_type,
                        "count": count,
                    }
                    for (tier, subject_type, object_type), count in combo_counter.most_common(15)
                ],
                "top_books_by_tier": {
                    tier: [{"source_book": book, "count": count} for book, count in counter.most_common(10)]
                    for tier, counter in book_counter.items()
                },
                "examples_by_tier": dict(examples),
            }
            payload["summary"]["predicate_count"] += 1
            payload["summary"]["in_schema_rows"] += int(tier_counter.get(IN_SCHEMA, 0))
            payload["summary"]["acceptable_polysemy_rows"] += int(tier_counter.get(ACCEPTABLE, 0))
            payload["summary"]["review_needed_rows"] += int(tier_counter.get(REVIEW, 0))
            payload["summary"]["likely_dirty_rows"] += int(tier_counter.get(DIRTY, 0))
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Ontology Boundary Tier Audit")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    lines.append(f"- 数据库：`{payload.get('db_path', '')}`")
    summary = payload.get("summary", {})
    lines.append(f"- 受审谓词数：`{summary.get('predicate_count', 0)}`")
    lines.append(f"- in-schema：`{summary.get('in_schema_rows', 0)}`")
    lines.append(f"- acceptable_polysemy：`{summary.get('acceptable_polysemy_rows', 0)}`")
    lines.append(f"- review_needed：`{summary.get('review_needed_rows', 0)}`")
    lines.append(f"- likely_dirty：`{summary.get('likely_dirty_rows', 0)}`")
    lines.append("")
    for predicate, item in payload.get("predicates", {}).items():
        lines.append(f"## {predicate}")
        tier_counts = item.get("tier_counts", {})
        lines.append("")
        lines.append(f"- 期望 subject types：`{', '.join(item.get('expected_subject_types', []))}`")
        lines.append(f"- 期望 object types：`{', '.join(item.get('expected_object_types', []))}`")
        lines.append(f"- in-schema：`{tier_counts.get(IN_SCHEMA, 0)}`")
        lines.append(f"- acceptable_polysemy：`{tier_counts.get(ACCEPTABLE, 0)}`")
        lines.append(f"- review_needed：`{tier_counts.get(REVIEW, 0)}`")
        lines.append(f"- likely_dirty：`{tier_counts.get(DIRTY, 0)}`")
        combos = item.get("top_combos", [])
        if combos:
            lines.append("")
            lines.append("| tier | subject_type | object_type | count |")
            lines.append("| --- | --- | --- | ---: |")
            for combo in combos[:10]:
                lines.append(
                    f"| {combo['tier']} | {combo['subject_type']} | {combo['object_type']} | {combo['count']} |"
                )
        for tier in (ACCEPTABLE, REVIEW, DIRTY):
            examples = item.get("examples_by_tier", {}).get(tier, [])
            if not examples:
                continue
            lines.append("")
            lines.append(f"### {tier}")
            for example in examples[:5]:
                lines.append(
                    f"- `{example['subject_type']} -> {example['object_type']}`: "
                    f"`{example['subject']} -> {example['object']}` "
                    f"@ `{example['source_book']}`"
                )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tier ontology boundary anomalies into acceptable, review-needed, and likely-dirty groups.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run_audit(db_path=args.db_path)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
