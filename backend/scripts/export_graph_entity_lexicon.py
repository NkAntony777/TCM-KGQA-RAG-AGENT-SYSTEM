from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT = BACKEND_DIR / "storage" / "runtime_entity_lexicon.json"


def _normalize_entity_type(entity_type: str) -> str:
    normalized = str(entity_type or "").strip().lower()
    mapping = {
        "formula": "formula",
        "方剂": "formula",
        "herb": "herb",
        "中药": "herb",
        "药物": "herb",
        "symptom": "symptom",
        "症状": "symptom",
        "syndrome": "syndrome",
        "证候": "syndrome",
        "证型": "syndrome",
        "therapy": "therapy",
        "治法": "therapy",
        "source_book": "source_book",
        "古籍": "source_book",
        "医书": "source_book",
    }
    return mapping.get(normalized, "other")


def export_lexicon(db_path: Path, output_path: Path) -> dict[str, object]:
    grouped: dict[str, list[str]] = defaultdict(list)
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT name, entity_type
            FROM entities
            WHERE length(name) BETWEEN 2 AND 24
            ORDER BY length(name) DESC, name ASC
            """
        ).fetchall()
    for name, entity_type in rows:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            continue
        grouped[_normalize_entity_type(str(entity_type or ""))].append(normalized_name)

    lexicon = {
        key: list(dict.fromkeys(values))
        for key, values in sorted(grouped.items())
        if values
    }
    payload = {
        "db_path": str(db_path),
        "output_path": str(output_path),
        "entity_type_count": len(lexicon),
        "total_terms": sum(len(items) for items in lexicon.values()),
        "lexicon": lexicon,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Export runtime graph entities as a reusable lexicon JSON.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = export_lexicon(args.db_path, args.output)
    summary = {
        "db_path": payload["db_path"],
        "output_path": payload["output_path"],
        "entity_type_count": payload["entity_type_count"],
        "total_terms": payload["total_terms"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
