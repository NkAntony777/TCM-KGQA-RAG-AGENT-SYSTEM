from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from paper_experiments.classics_vector_sqlite_store import ClassicsVectorSQLiteStore, count_rows, load_first_valid_row, read_json, write_json


DEFAULT_ROWS_PATH = BACKEND_ROOT / "storage" / "retrieval_embed_sessions" / "classics-vector.rows.jsonl"
DEFAULT_DB_PATH = BACKEND_ROOT / "storage" / "classics_vector_store.sqlite"
DEFAULT_STATE_PATH = BACKEND_ROOT / "storage" / "paper_sqlite_import_sessions" / "classics-vector-sqlite.state.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import classics-vector rows.jsonl into a SQLite experiment backend with progress and resume.")
    parser.add_argument("--rows-path", type=Path, default=DEFAULT_ROWS_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        state = read_json(args.state_path, {})
        if not isinstance(state, dict):
            state = {}
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    store = ClassicsVectorSQLiteStore(args.db_path)
    report = store.import_rows_jsonl(
        rows_path=args.rows_path,
        state_path=args.state_path,
        batch_size=max(1, int(args.batch_size)),
        reset=bool(args.reset),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

