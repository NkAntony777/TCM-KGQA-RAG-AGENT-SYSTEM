from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from scripts.tcm_triple_console import (
    BACKEND_DIR,
    DEFAULT_BOOKS_DIR,
    DEFAULT_GRAPH_BASE,
    DEFAULT_GRAPH_TARGET,
    DEFAULT_OUTPUT_DIR,
    PipelineConfig,
    TCMTriplePipeline,
    _derive_evidence_target_path,
    _load_json_file,
    _write_text_atomic,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild graph_runtime.json from historical published runs")
    parser.add_argument("--target", type=Path, default=DEFAULT_GRAPH_TARGET)
    parser.add_argument("--published-before", default="", help="Only include runs published at or before this ISO timestamp")
    parser.add_argument("--include-run", action="append", default=[], help="Extra run_name to include even if not marked published")
    parser.add_argument("--exclude-run", action="append", default=[], help="run_name to exclude")
    parser.add_argument("--apply", action="store_true", help="Write rebuilt files back to the target path")
    return parser.parse_args()


def _load_publish_status(run_dir: Path) -> dict[str, Any]:
    return _load_json_file(run_dir / "publish_status.json", {})


def _select_runs(
    *,
    published_before: str,
    include_runs: list[str],
    exclude_runs: list[str],
) -> list[dict[str, Any]]:
    cutoff = None
    if published_before.strip():
        cutoff = datetime.fromisoformat(published_before.strip())

    selected: list[dict[str, Any]] = []
    include_set = {item.strip() for item in include_runs if item.strip()}
    exclude_set = {item.strip() for item in exclude_runs if item.strip()}

    for run_dir in sorted([p for p in DEFAULT_OUTPUT_DIR.iterdir() if p.is_dir()]):
        if run_dir.name in exclude_set:
            continue
        status = _load_publish_status(run_dir)
        json_status = status.get("json", {}) if isinstance(status, dict) else {}
        published_at = str(json_status.get("published_at", "") or "").strip()
        published = bool(json_status.get("published"))
        include = published
        if include and cutoff and published_at:
            try:
                include = datetime.fromisoformat(published_at) <= cutoff
            except ValueError:
                include = False
        if run_dir.name in include_set:
            include = True
        if not include:
            continue
        selected.append(
            {
                "run_name": run_dir.name,
                "run_dir": run_dir,
                "published_at": published_at,
            }
        )

    selected.sort(key=lambda item: (item.get("published_at", ""), item["run_name"]))
    return selected


def _backup_path(path: Path, stamp: str) -> Path:
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / f"{path.stem}.{stamp}{path.suffix}"


def _copy_if_exists(source: Path, target: Path) -> str:
    if not source.exists():
        return ""
    target.write_bytes(source.read_bytes())
    return str(target)


def main() -> int:
    args = _parse_args()
    selected_runs = _select_runs(
        published_before=args.published_before,
        include_runs=args.include_run,
        exclude_runs=args.exclude_run,
    )
    if not selected_runs:
        raise SystemExit("no_runs_selected")

    pipeline = TCMTriplePipeline(
        PipelineConfig(
            books_dir=DEFAULT_BOOKS_DIR,
            output_dir=DEFAULT_OUTPUT_DIR,
            model="mimo-v2-pro",
            api_key="rebuild-placeholder",
            base_url="https://example.invalid/v1",
            request_delay=0.0,
            max_retries=0,
        )
    )

    with TemporaryDirectory(prefix="graph-runtime-rebuild-") as tmpdir:
        temp_root = Path(tmpdir)
        staged_target = temp_root / args.target.name
        staged_evidence = _derive_evidence_target_path(staged_target)

        if args.target == DEFAULT_GRAPH_TARGET and DEFAULT_GRAPH_BASE.exists():
            _write_text_atomic(
                staged_target,
                json.dumps(_load_json_file(DEFAULT_GRAPH_BASE, []), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        replay_results: list[dict[str, Any]] = []
        for item in selected_runs:
            pipeline.publish_graph(run_dir=item["run_dir"], target_path=staged_target, replace=False)
            graph_rows = _load_json_file(staged_target, [])
            replay_results.append(
                {
                    "run_name": item["run_name"],
                    "published_at": item["published_at"],
                    "graph_triples_after_run": len(graph_rows) if isinstance(graph_rows, list) else 0,
                }
            )

        final_graph = _load_json_file(staged_target, [])
        final_evidence_count = 0
        if staged_evidence.exists():
            final_evidence_count = sum(1 for line in staged_evidence.read_text(encoding="utf-8").splitlines() if line.strip())

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_evidence = _derive_evidence_target_path(args.target)
        backup_graph = ""
        backup_evidence = ""
        if args.apply:
            backup_graph = _copy_if_exists(args.target, _backup_path(args.target, stamp))
            backup_evidence = _copy_if_exists(target_evidence, _backup_path(target_evidence, stamp))
            _write_text_atomic(args.target, staged_target.read_text(encoding="utf-8"), encoding="utf-8")
            if staged_evidence.exists():
                _write_text_atomic(target_evidence, staged_evidence.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                _write_text_atomic(target_evidence, "", encoding="utf-8")

        manifest = {
            "rebuilt_at": datetime.now().isoformat(timespec="seconds"),
            "target": str(args.target),
            "applied": bool(args.apply),
            "published_before": args.published_before,
            "include_runs": args.include_run,
            "exclude_runs": args.exclude_run,
            "selected_runs": replay_results,
            "final_graph_triples": len(final_graph) if isinstance(final_graph, list) else 0,
            "final_evidence_count": final_evidence_count,
            "backup_graph": backup_graph,
            "backup_evidence": backup_evidence,
        }
        manifest_path = BACKEND_DIR / "services" / "graph_service" / "data" / f"graph_runtime.rebuild_manifest.{stamp}.json"
        _write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
