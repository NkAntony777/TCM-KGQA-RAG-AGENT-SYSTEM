from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import get_retrieval_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the bundled sample corpus into Milvus.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the target Milvus collection before indexing sample documents.",
    )
    args = parser.parse_args()

    result = get_retrieval_engine().index_sample_corpus(reset_collection=args.reset)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
