from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.graph_service.runtime_store import RuntimeGraphStore, RuntimeGraphStoreSettings, _iter_json_array_rows, _iter_jsonl_rows


DATA_DIR = BACKEND_DIR / "services" / "graph_service" / "data"
DEFAULT_GRAPH_PATH = DATA_DIR / "graph_runtime.json"
DEFAULT_EVIDENCE_PATH = DATA_DIR / "graph_runtime.evidence.jsonl"
DEFAULT_DB_PATH = DATA_DIR / "graph_runtime.db"
DEFAULT_SAMPLE_GRAPH_PATH = DATA_DIR / "sample_graph.json"
DEFAULT_SAMPLE_EVIDENCE_PATH = DATA_DIR / "sample_graph.evidence.jsonl"
DEFAULT_MODERN_GRAPH_PATH = DATA_DIR / "modern_graph_runtime.jsonl"
DEFAULT_MODERN_EVIDENCE_PATH = DATA_DIR / "modern_graph_runtime.evidence.jsonl"

BATCH1_DELETE_RULES: tuple[dict[str, str], ...] = (
    {
        "predicate": "归经",
        "subject_type": "channel",
        "object_type": "channel",
        "label": "DELETE:归经[channel->channel]",
    },
    {
        "predicate": "治疗症状",
        "subject_type": "book",
        "object_type": "symptom",
        "label": "DELETE:治疗症状[book->symptom]",
    },
    {
        "predicate": "治疗症状",
        "subject_type": "chapter",
        "object_type": "symptom",
        "label": "DELETE:治疗症状[chapter->symptom]",
    },
)


def _progress(stage: str, detail: str) -> None:
    print(f"[governance-batch1] {stage}: {detail}", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply batch-1 likely-dirty governance deletes with dry-run support.")
    parser.add_argument("--graph-path", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--sample-graph-path", type=Path, default=DEFAULT_SAMPLE_GRAPH_PATH)
    parser.add_argument("--sample-evidence-path", type=Path, default=DEFAULT_SAMPLE_EVIDENCE_PATH)
    parser.add_argument("--modern-graph-path", type=Path, default=DEFAULT_MODERN_GRAPH_PATH)
    parser.add_argument("--modern-evidence-path", type=Path, default=DEFAULT_MODERN_EVIDENCE_PATH)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _row_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            text = str(item or "").strip()
            if text and text not in fact_ids:
                fact_ids.append(text)
    fact_id = str(row.get("fact_id", "")).strip()
    if fact_id and fact_id not in fact_ids:
        fact_ids.append(fact_id)
    return fact_ids


def _match_rule(row: dict[str, Any]) -> dict[str, str] | None:
    predicate = str(row.get("predicate", "")).strip()
    subject_type = str(row.get("subject_type", "")).strip()
    object_type = str(row.get("object_type", "")).strip()
    for rule in BATCH1_DELETE_RULES:
        if predicate == rule["predicate"] and subject_type == rule["subject_type"] and object_type == rule["object_type"]:
            return rule
    return None


def _transform_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    matched = _match_rule(row)
    if matched is None:
        return row, []
    row["_delete"] = True
    return row, [matched["label"]]


def _rewrite_graph_array(
    path: Path,
    output_path: Path,
    *,
    deleted_fact_ids: set[str],
    kept_fact_ids: set[str],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    stats: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        for row in _iter_json_array_rows(path):
            new_row, changes = _transform_row(dict(row))
            fact_ids = _row_fact_ids(new_row)
            if changes:
                for change in changes:
                    stats[change] += 1
                deleted_fact_ids.update(fact_ids)
                if len(samples) < 40:
                    samples.append(
                        {
                            "subject": new_row.get("subject", ""),
                            "predicate": new_row.get("predicate", ""),
                            "object": new_row.get("object", ""),
                            "subject_type": new_row.get("subject_type", ""),
                            "object_type": new_row.get("object_type", ""),
                            "source_book": new_row.get("source_book", ""),
                            "source_chapter": new_row.get("source_chapter", ""),
                            "changes": changes,
                        }
                    )
            else:
                kept_fact_ids.update(fact_ids)
            if new_row.get("_delete"):
                continue
            new_row.pop("_delete", None)
            if not first:
                fout.write(",\n")
            fout.write("  ")
            json.dump(new_row, fout, ensure_ascii=False)
            first = False
        fout.write("\n]\n")
    return dict(stats), samples


def _rewrite_graph_jsonl(
    path: Path,
    output_path: Path,
    *,
    deleted_fact_ids: set[str],
    kept_fact_ids: set[str],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    stats: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as fout:
        for row in _iter_jsonl_rows(path):
            new_row, changes = _transform_row(dict(row))
            fact_ids = _row_fact_ids(new_row)
            if changes:
                for change in changes:
                    stats[change] += 1
                deleted_fact_ids.update(fact_ids)
                if len(samples) < 40:
                    samples.append(
                        {
                            "subject": new_row.get("subject", ""),
                            "predicate": new_row.get("predicate", ""),
                            "object": new_row.get("object", ""),
                            "subject_type": new_row.get("subject_type", ""),
                            "object_type": new_row.get("object_type", ""),
                            "source_book": new_row.get("source_book", ""),
                            "source_chapter": new_row.get("source_chapter", ""),
                            "changes": changes,
                        }
                    )
            else:
                kept_fact_ids.update(fact_ids)
            if new_row.get("_delete"):
                continue
            new_row.pop("_delete", None)
            fout.write(json.dumps(new_row, ensure_ascii=False) + "\n")
    return dict(stats), samples


def _rewrite_evidence(
    path: Path,
    output_path: Path,
    *,
    deleted_fact_ids: set[str],
    kept_fact_ids: set[str],
) -> int:
    skip_fact_ids = deleted_fact_ids - kept_fact_ids
    kept = 0
    with output_path.open("w", encoding="utf-8") as fout:
        for row in _iter_jsonl_rows(path):
            fact_id = str(row.get("fact_id", "")).strip()
            if fact_id in skip_fact_ids:
                continue
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1
    return kept


def _rebuild_runtime_db(
    *,
    graph_path: Path,
    evidence_path: Path,
    db_path: Path,
    sample_graph_path: Path,
    sample_evidence_path: Path,
    modern_graph_path: Path,
    modern_evidence_path: Path,
) -> tuple[Path, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="graph-runtime-batch1-", dir=str(db_path.parent)))
    rebuilt_db_path = temp_dir / db_path.name
    store = RuntimeGraphStore(
        RuntimeGraphStoreSettings(
            graph_path=graph_path,
            evidence_path=evidence_path,
            db_path=rebuilt_db_path,
            sample_graph_path=sample_graph_path if sample_graph_path.exists() else None,
            sample_evidence_path=sample_evidence_path if sample_evidence_path.exists() else None,
            modern_graph_path=modern_graph_path if modern_graph_path.exists() else None,
            modern_evidence_path=modern_evidence_path if modern_evidence_path.exists() else None,
        )
    )
    store.ensure_ready()
    return rebuilt_db_path, temp_dir


def _replace_with_backup(current_path: Path, replacement_path: Path, *, stamp: str) -> str:
    backup_path = current_path.with_name(f"{current_path.stem}.{stamp}.bak{current_path.suffix}")
    if current_path.exists():
        shutil.move(str(current_path), str(backup_path))
    shutil.move(str(replacement_path), str(current_path))
    return str(backup_path) if backup_path.exists() else ""


def _cleanup_temp_dir(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    args = _parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _progress("start", f"stamp={stamp}; apply={bool(args.apply)}")

    deleted_fact_ids: set[str] = set()
    kept_fact_ids: set[str] = set()

    temp_graph = args.graph_path.with_name(f"{args.graph_path.stem}.{stamp}.batch1.json")
    temp_evidence = args.evidence_path.with_name(f"{args.evidence_path.stem}.{stamp}.batch1{args.evidence_path.suffix}")
    temp_modern_graph = args.modern_graph_path.with_name(f"{args.modern_graph_path.stem}.{stamp}.batch1{args.modern_graph_path.suffix}")
    temp_modern_evidence = args.modern_evidence_path.with_name(f"{args.modern_evidence_path.stem}.{stamp}.batch1{args.modern_evidence_path.suffix}")

    _progress("rewrite", f"runtime graph -> {temp_graph.name}")
    runtime_stats, runtime_samples = _rewrite_graph_array(
        args.graph_path,
        temp_graph,
        deleted_fact_ids=deleted_fact_ids,
        kept_fact_ids=kept_fact_ids,
    )
    modern_stats: dict[str, int] = {}
    modern_samples: list[dict[str, Any]] = []
    if args.modern_graph_path.exists():
        _progress("rewrite", f"modern graph -> {temp_modern_graph.name}")
        modern_stats, modern_samples = _rewrite_graph_jsonl(
            args.modern_graph_path,
            temp_modern_graph,
            deleted_fact_ids=deleted_fact_ids,
            kept_fact_ids=kept_fact_ids,
        )

    _progress("rewrite", f"runtime evidence -> {temp_evidence.name}")
    evidence_rows = _rewrite_evidence(
        args.evidence_path,
        temp_evidence,
        deleted_fact_ids=deleted_fact_ids,
        kept_fact_ids=kept_fact_ids,
    )
    modern_evidence_rows = 0
    if args.modern_evidence_path.exists():
        _progress("rewrite", f"modern evidence -> {temp_modern_evidence.name}")
        modern_evidence_rows = _rewrite_evidence(
            args.modern_evidence_path,
            temp_modern_evidence,
            deleted_fact_ids=deleted_fact_ids,
            kept_fact_ids=kept_fact_ids,
        )

    merged_stats = Counter(runtime_stats)
    merged_stats.update(modern_stats)
    shared_fact_ids = sorted((deleted_fact_ids & kept_fact_ids))
    effective_deleted_fact_ids = sorted(deleted_fact_ids - kept_fact_ids)

    payload: dict[str, Any] = {
        "generated_at": _utc_now_text(),
        "graph_path": str(args.graph_path),
        "evidence_path": str(args.evidence_path),
        "db_path": str(args.db_path),
        "apply": bool(args.apply),
        "stats": dict(merged_stats),
        "runtime_sample_changes": runtime_samples,
        "modern_sample_changes": modern_samples,
        "deleted_fact_ids_count": len(deleted_fact_ids),
        "shared_fact_ids_count": len(shared_fact_ids),
        "effective_deleted_fact_ids_count": len(effective_deleted_fact_ids),
        "shared_fact_ids_preview": shared_fact_ids[:30],
        "evidence_rows_after_rewrite": evidence_rows,
        "modern_evidence_rows_after_rewrite": modern_evidence_rows,
        "backups": {},
    }

    if not args.apply:
        _progress("dry-run", f"stats={dict(merged_stats)}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    rebuilt_temp_dir: Path | None = None
    try:
        _progress("rebuild", "rebuilding runtime sqlite db")
        rebuilt_db, rebuilt_temp_dir = _rebuild_runtime_db(
            graph_path=temp_graph,
            evidence_path=temp_evidence,
            db_path=args.db_path,
            sample_graph_path=args.sample_graph_path,
            sample_evidence_path=args.sample_evidence_path,
            modern_graph_path=temp_modern_graph if args.modern_graph_path.exists() else args.modern_graph_path,
            modern_evidence_path=temp_modern_evidence if args.modern_evidence_path.exists() else args.modern_evidence_path,
        )
        _progress("replace", "swapping graph/evidence/db with backups")
        payload["backups"]["graph_path"] = _replace_with_backup(args.graph_path, temp_graph, stamp=stamp)
        payload["backups"]["evidence_path"] = _replace_with_backup(args.evidence_path, temp_evidence, stamp=stamp)
        if args.modern_graph_path.exists():
            payload["backups"]["modern_graph_path"] = _replace_with_backup(args.modern_graph_path, temp_modern_graph, stamp=stamp)
        if args.modern_evidence_path.exists():
            payload["backups"]["modern_evidence_path"] = _replace_with_backup(args.modern_evidence_path, temp_modern_evidence, stamp=stamp)
        payload["backups"]["db_path"] = _replace_with_backup(args.db_path, rebuilt_db, stamp=stamp)
    finally:
        _cleanup_temp_dir(rebuilt_temp_dir)

    manifest_path = DATA_DIR / f"graph_runtime.governance_batch1_likely_dirty.{stamp}.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _progress("done", f"manifest={manifest_path.name}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
