from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts.tcm_triple_console import (
    DEFAULT_OUTPUT_DIR,
    PipelineConfig,
    TCMTriplePipeline,
    TripleRecord,
    _extract_json_block,
    _extract_payload_triples,
    _first_env,
    _load_json_file,
)


def _load_run_manifest(run_name: str) -> tuple[Path, dict[str, Any]]:
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest_not_found: {manifest_path}")
    return run_dir, _load_json_file(manifest_path, {})


def _build_pipeline_from_manifest(manifest: dict[str, Any]) -> TCMTriplePipeline:
    config = manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}
    model = manifest.get("model") or _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="deepseek-ai/DeepSeek-V3.2")
    base_url = manifest.get("base_url") or _first_env(
        "TRIPLE_LLM_BASE_URL",
        "LLM_BASE_URL",
        "OPENAI_BASE_URL",
        default="https://api.siliconflow.cn/v1",
    )
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY", default="offline-repair")
    return TCMTriplePipeline(
        PipelineConfig(
            books_dir=Path(config.get("books_dir") or manifest.get("books_dir") or Path.cwd()),
            output_dir=DEFAULT_OUTPUT_DIR,
            model=str(model),
            api_key=api_key,
            base_url=str(base_url),
            request_timeout=float(config.get("request_timeout", 90.0)),
            max_chunk_chars=int(config.get("max_chunk_chars", 800)),
            chunk_overlap=int(config.get("chunk_overlap", 200)),
            max_retries=int(config.get("max_retries", 2)),
            request_delay=float(config.get("request_delay", 0.0)),
            parallel_workers=max(1, int(config.get("parallel_workers", 4))),
            retry_backoff_base=float(config.get("retry_backoff_base", 2.0)),
            chunk_strategy=str(config.get("chunk_strategy", "body_first")),
        )
    )


def _record_signature(row: TripleRecord) -> tuple[str, ...]:
    return (
        row.subject,
        row.predicate,
        row.object,
        row.subject_type,
        row.object_type,
        row.source_book,
        row.source_chapter,
        row.source_text,
        f"{row.confidence:.6f}",
        row.raw_predicate,
        row.raw_subject_type,
        row.raw_object_type,
    )


def _load_existing_rows(path: Path) -> list[TripleRecord]:
    rows: list[TripleRecord] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            rows.append(
                TripleRecord(
                    subject=str(payload.get("subject", "")),
                    predicate=str(payload.get("predicate", "")),
                    object=str(payload.get("object", "")),
                    subject_type=str(payload.get("subject_type", "")),
                    object_type=str(payload.get("object_type", "")),
                    source_book=str(payload.get("source_book", "")),
                    source_chapter=str(payload.get("source_chapter", "")),
                    source_text=str(payload.get("source_text", "")),
                    confidence=float(payload.get("confidence", 0.0)),
                    raw_predicate=str(payload.get("raw_predicate", payload.get("predicate", ""))),
                    raw_subject_type=str(payload.get("raw_subject_type", payload.get("subject_type", ""))),
                    raw_object_type=str(payload.get("raw_object_type", payload.get("object_type", ""))),
                )
            )
    return rows


def _load_latest_checkpoint_rows(run_dir: Path) -> dict[tuple[str, int], dict[str, Any]]:
    latest: dict[tuple[str, int], dict[str, Any]] = {}
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    if not checkpoint_path.exists():
        return latest
    with checkpoint_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = (str(row.get("book", "")), int(row.get("chunk_index", 0)))
            latest[key] = row
    return latest


def _load_raw_history(run_dir: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    history: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    raw_jsonl = run_dir / "triples.raw.jsonl"
    if not raw_jsonl.exists():
        return history
    with raw_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = (str(row.get("book", "")), int(row.get("chunk_index", 0)))
            history[key].append(row)
    return history


def _append_checkpoint_success(
    checkpoint_path: Path,
    *,
    latest_row: dict[str, Any],
    triples_count: int,
    note: str,
) -> None:
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "book": str(latest_row.get("book", "")),
        "chapter": str(latest_row.get("chapter", "")),
        "chunk_index": int(latest_row.get("chunk_index", 0)),
        "sequence": latest_row.get("sequence"),
        "success": True,
        "error": None,
        "triples_count": triples_count,
        "attempt": note,
        "resumed": True,
    }
    with checkpoint_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _candidate_texts_from_raw_history(raw_rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for index, row in enumerate(raw_rows, start=1):
        raw_text = str(row.get("llm_raw_text", "") or "").strip()
        if raw_text:
            candidates.append((f"raw_jsonl#{index}", raw_text))
    return candidates


def _candidate_texts_from_diagnostics(run_dir: Path, book_name: str, chunk_index: int) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    pattern = f"diagnostics_{book_name}_{chunk_index}_*"
    for diag_dir in sorted(run_dir.glob(pattern)):
        for raw_file in sorted(diag_dir.glob("*.raw.txt")):
            candidates.append((f"{diag_dir.name}/{raw_file.name}", raw_file.read_text(encoding="utf-8")))
    return candidates


def _recover_best_rows_for_chunk(
    pipeline: TCMTriplePipeline,
    *,
    run_dir: Path,
    book_name: str,
    chapter_name: str,
    chunk_index: int,
    raw_rows: list[dict[str, Any]],
) -> tuple[list[TripleRecord], dict[str, Any] | None]:
    best_rows: list[TripleRecord] = []
    best_meta: dict[str, Any] | None = None
    candidates = _candidate_texts_from_raw_history(raw_rows) + _candidate_texts_from_diagnostics(run_dir, book_name, chunk_index)
    for source_name, raw_text in candidates:
        try:
            payload = _extract_json_block(raw_text)
        except Exception as exc:
            current_count = 0
            current_error = f"{type(exc).__name__}: {exc}"
            rows: list[TripleRecord] = []
        else:
            rows = pipeline.normalize_triples(payload=payload, book_name=book_name, chapter_name=chapter_name)
            current_count = len(rows)
            current_error = ""
        if current_count > len(best_rows):
            best_rows = rows
            best_meta = {
                "source": source_name,
                "candidate_triples": current_count,
                "parse_error": current_error,
                "raw_subject_tokens": raw_text.count('"subject"'),
                "raw_chars": len(raw_text),
            }
    return best_rows, best_meta


def _rewrite_state_and_graph(
    pipeline: TCMTriplePipeline,
    *,
    run_dir: Path,
) -> dict[str, Any]:
    triples_jsonl = run_dir / "triples.normalized.jsonl"
    state_path = run_dir / "state.json"
    latest_checkpoint = _load_latest_checkpoint_rows(run_dir)
    all_rows = _load_existing_rows(triples_jsonl)
    pipeline.write_graph_import(run_dir / "graph_import.json", all_rows)

    state = _load_json_file(state_path, {})
    success_count = sum(1 for row in latest_checkpoint.values() if row.get("success") is True)
    state["total_triples"] = len(all_rows)
    state["chunks_completed"] = success_count
    state["last_reconciled_at"] = datetime.now().isoformat(timespec="seconds")
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "total_triples": len(all_rows),
        "chunks_completed": success_count,
    }


def repair_run(run_name: str, *, dry_run: bool = False) -> dict[str, Any]:
    run_dir, manifest = _load_run_manifest(run_name)
    pipeline = _build_pipeline_from_manifest(manifest)
    latest_checkpoint = _load_latest_checkpoint_rows(run_dir)
    raw_history = _load_raw_history(run_dir)

    triples_jsonl = run_dir / "triples.normalized.jsonl"
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    existing_rows = _load_existing_rows(triples_jsonl)
    existing_signatures = {_record_signature(row) for row in existing_rows}

    repairs: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    for (book_name, chunk_index), latest_row in sorted(latest_checkpoint.items(), key=lambda item: (item[0][0], item[0][1])):
        error = str(latest_row.get("error") or "")
        if not error.startswith("marked_incomplete_low_yield"):
            continue
        chapter_name = str(latest_row.get("chapter", "") or "")
        best_rows, best_meta = _recover_best_rows_for_chunk(
            pipeline,
            run_dir=run_dir,
            book_name=book_name,
            chapter_name=chapter_name,
            chunk_index=chunk_index,
            raw_rows=raw_history.get((book_name, chunk_index), []),
        )
        if len(best_rows) <= 1:
            pending.append(
                {
                    "book": book_name,
                    "chunk_index": chunk_index,
                    "chapter": chapter_name,
                    "recovery_source": best_meta["source"] if best_meta else None,
                    "recovered_triples": len(best_rows),
                }
            )
            continue

        new_rows: list[TripleRecord] = []
        for row in best_rows:
            signature = _record_signature(row)
            if signature in existing_signatures:
                continue
            existing_signatures.add(signature)
            new_rows.append(row)

        repairs.append(
            {
                "book": book_name,
                "chunk_index": chunk_index,
                "chapter": chapter_name,
                "recovery_source": best_meta["source"] if best_meta else None,
                "recovered_triples": len(best_rows),
                "appended_triples": len(new_rows),
            }
        )

        if dry_run:
            continue

        with triples_jsonl.open("a", encoding="utf-8") as f:
            for row in new_rows:
                f.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
        _append_checkpoint_success(
            checkpoint_path,
            latest_row=latest_row,
            triples_count=len(best_rows),
            note="repair_from_saved_raw",
        )

    snapshot = _rewrite_state_and_graph(pipeline, run_dir=run_dir) if not dry_run else {
        "total_triples": len(existing_rows) + sum(item["appended_triples"] for item in repairs),
        "chunks_completed": sum(1 for row in latest_checkpoint.values() if row.get("success") is True) + len(repairs),
    }
    report = {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "dry_run": dry_run,
        "repaired_chunks": len(repairs),
        "pending_low_yield_chunks": len(pending),
        "appended_triples": sum(item["appended_triples"] for item in repairs),
        "snapshot": snapshot,
        "repairs": repairs,
        "pending": pending,
    }
    report_path = run_dir / "low_yield_repair.report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair low-yield chunks from saved raw LLM responses.")
    parser.add_argument("--run-name", required=True, help="Run directory name under storage/triple_pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only without modifying files")
    args = parser.parse_args()

    report = repair_run(args.run_name, dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
