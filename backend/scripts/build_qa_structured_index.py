from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings


DEFAULT_QA_INPUT = (
    BACKEND_ROOT
    / "services"
    / "retrieval_service"
    / "data"
    / "case_qa_clean"
    / "qa_fts_ready.jsonl"
)
DEFAULT_CASE_INPUT = (
    BACKEND_ROOT
    / "services"
    / "retrieval_service"
    / "data"
    / "case_qa_clean"
    / "case_fts_ready.jsonl"
)
DEFAULT_INDEX_PATH = BACKEND_ROOT / "storage" / "qa_structured_index.sqlite"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build structured non-vector QA index from cleaned JSONL files.")
    parser.add_argument("--qa-input", type=Path, default=DEFAULT_QA_INPUT)
    parser.add_argument("--case-input", type=Path, default=DEFAULT_CASE_INPUT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--batch-size", type=int, default=2000)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    index = StructuredQAIndex(
        StructuredQAIndexSettings(
            index_path=args.index_path,
            qa_input_path=args.qa_input,
            case_input_path=args.case_input,
        )
    )
    result = index.rebuild(batch_size=max(100, int(args.batch_size)))
    result["health"] = index.health()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
