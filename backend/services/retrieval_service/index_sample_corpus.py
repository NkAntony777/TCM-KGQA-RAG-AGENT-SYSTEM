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
    parser = argparse.ArgumentParser(description="Index bundled retrieval corpora into Milvus/local hybrid store.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the target Milvus collection before indexing documents.",
    )
    parser.add_argument("--sample-only", action="store_true", help="Only index the bundled sample corpus.")
    parser.add_argument("--modern-only", action="store_true", help="Only index the optional HERB2 modern corpus.")
    args = parser.parse_args()

    engine = get_retrieval_engine()
    if args.sample_only and args.modern_only:
        raise SystemExit("sample-only and modern-only cannot be used together")
    if args.sample_only:
        result = engine.index_sample_corpus(reset_collection=args.reset)
    elif args.modern_only:
        result = engine.index_corpus_files([engine.settings.modern_corpus_path], reset_collection=args.reset)
    else:
        result = engine.index_configured_corpora(reset_collection=args.reset)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
