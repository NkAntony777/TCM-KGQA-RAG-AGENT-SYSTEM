from __future__ import annotations

import argparse
import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BACKEND_ROOT))

from scripts.benchmark_path_query_backends import main as benchmark_main


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrapper for path backend ablation using existing benchmark.")
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "path_backend_ablation_latest.json")
    args, unknown = parser.parse_known_args()
    __import__("sys").argv = [
        "benchmark_path_query_backends.py",
        "--output",
        str(args.output_json),
        *unknown,
    ]
    benchmark_main()


if __name__ == "__main__":
    main()
