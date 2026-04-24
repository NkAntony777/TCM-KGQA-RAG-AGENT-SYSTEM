from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.nav_group_builder import build_nav_group_artifacts
from services.retrieval_service.settings import load_settings


def _progress(stage: str, detail: str) -> None:
    print(f"[nav-group:{stage}] {detail}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintenance: build adaptive nav-group and book-outline caches from classic corpus + section summaries.")
    parser.add_argument("--corpus", type=Path, default=None, help="Classic corpus json path.")
    parser.add_argument("--summary-cache", type=Path, default=None, help="Section summary cache sqlite path.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for nav-group artifacts.")
    args = parser.parse_args()

    settings = load_settings()
    corpus_path = args.corpus or settings.classic_corpus_path
    summary_cache_path = args.summary_cache or settings.section_summary_cache_path
    output_dir = args.output_dir or (BACKEND_ROOT / "storage" / "nav_group_cache")

    started = time.perf_counter()
    _progress("start", f"corpus={corpus_path.name} summary_cache={summary_cache_path.name}")
    report = build_nav_group_artifacts(
        corpus_path=corpus_path,
        summary_cache_path=summary_cache_path,
        output_dir=output_dir,
    )
    elapsed = time.perf_counter() - started
    _progress("done", f"books={report['books']} nav_groups={report['nav_groups']} outlines={report['book_outlines']} elapsed={elapsed:.1f}s")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
