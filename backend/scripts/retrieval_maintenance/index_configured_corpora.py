from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import get_retrieval_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintenance: index configured retrieval corpora, including optional HERB2 artifacts.")
    parser.add_argument("--reset", action="store_true", help="Drop the target collection before re-indexing.")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted files-first build from its temp DB/state.")
    parser.add_argument("--status", action="store_true", help="Print files-first build state and exit.")
    parser.add_argument("--exclude-sample", action="store_true", help="Skip the bundled sample corpus.")
    parser.add_argument("--exclude-modern", action="store_true", help="Skip the optional HERB2 modern corpus.")
    parser.add_argument("--exclude-classic", action="store_true", help="Skip the optional classic books corpus.")
    parser.add_argument("--files-first", action="store_true", help="Build the local files-first SQLite FTS index instead of dense hybrid vectors.")
    parser.add_argument("--embed-workers", type=int, default=1, help="Number of concurrent embedding request workers.")
    parser.add_argument("--show-progress", action="store_true", help="Print embedding batch progress during indexing.")
    parser.add_argument("--files-first-state-path", type=Path, default=None, help="Optional state json for files-first progress/resume.")
    parser.add_argument("--files-first-batch-size", type=int, default=512, help="Batch size for files-first SQLite rebuild.")
    args = parser.parse_args()

    os.environ["RETRIEVAL_EMBED_WORKERS"] = str(max(1, int(args.embed_workers)))
    os.environ["RETRIEVAL_EMBED_PROGRESS"] = "true" if args.show_progress else "false"

    engine = get_retrieval_engine()
    if args.status and args.files_first:
        state_path = args.files_first_state_path or engine.files_first_store._default_state_path()
        payload = {"state_path": str(state_path)}
        if state_path.exists():
            payload["state"] = json.loads(state_path.read_text(encoding="utf-8"))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    result = engine.index_configured_corpora(
        reset_collection=args.reset,
        include_sample=not args.exclude_sample,
        include_modern=not args.exclude_modern,
        include_classic=not args.exclude_classic,
        index_mode="files_first" if args.files_first else "hybrid",
        files_first_state_path=args.files_first_state_path,
        files_first_resume=bool(args.resume),
        files_first_show_progress=bool(args.show_progress),
        files_first_batch_size=max(64, int(args.files_first_batch_size)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
