from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.graph_service.nebulagraph_store import NebulaGraphStore


def default_graph_path() -> Path:
    return BACKEND_ROOT / "services" / "graph_service" / "data" / "graph_runtime.json"


def default_evidence_path() -> Path:
    return BACKEND_ROOT / "services" / "graph_service" / "data" / "graph_runtime.evidence.jsonl"


def default_output_path() -> Path:
    return BACKEND_ROOT / "storage" / "graph_service" / "graph_runtime.nebula.ngql"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export runtime graph JSON into NebulaGraph nGQL statements.")
    parser.add_argument("--graph-path", type=Path, default=default_graph_path(), help="Path to graph_runtime.json")
    parser.add_argument("--evidence-path", type=Path, default=default_evidence_path(), help="Path to graph_runtime.evidence.jsonl")
    parser.add_argument("--output", type=Path, default=default_output_path(), help="Where to write the generated .ngql file")
    parser.add_argument("--apply", action="store_true", help="Apply the generated nGQL file to a live NebulaGraph instance")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    store = NebulaGraphStore()
    summary = store.export_ngql(args.graph_path, args.evidence_path if args.evidence_path.exists() else None, args.output)

    if args.apply:
        apply_summary = store.apply_ngql_file(args.output)
        summary["apply"] = apply_summary

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Graph: {summary['graph_path']}")
        print(f"Evidence: {summary['evidence_path']}")
        print(f"Output: {summary['output_path']}")
        print(f"Space: {summary['space']}")
        print(f"Triples: {summary['triples']}")
        print(f"Statements: {summary['statements']}")
        if "apply" in summary:
            print(f"Applied: {summary['apply']['executed']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
