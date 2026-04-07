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
    parser = argparse.ArgumentParser(description="Index configured retrieval corpora, including optional HERB2 artifacts.")
    parser.add_argument("--reset", action="store_true", help="Drop the target collection before re-indexing.")
    parser.add_argument("--exclude-sample", action="store_true", help="Skip the bundled sample corpus.")
    parser.add_argument("--exclude-modern", action="store_true", help="Skip the optional HERB2 modern corpus.")
    parser.add_argument("--exclude-classic", action="store_true", help="Skip the optional classic books corpus.")
    parser.add_argument("--files-first", action="store_true", help="Build the local files-first SQLite FTS index instead of dense hybrid vectors.")
    args = parser.parse_args()

    result = get_retrieval_engine().index_configured_corpora(
        reset_collection=args.reset,
        include_sample=not args.exclude_sample,
        include_modern=not args.exclude_modern,
        include_classic=not args.exclude_classic,
        index_mode="files_first" if args.files_first else "hybrid",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
