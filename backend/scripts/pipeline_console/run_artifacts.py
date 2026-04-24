from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


PayloadTriplesExtractor = Callable[[dict[str, Any]], list[Any]]
NowFn = Callable[[], str]


def append_checkpoint(
    checkpoint_path: Path,
    *,
    task: Any,
    error: str | None,
    payload: dict[str, Any],
    attempt: int,
    resumed: bool,
    extract_payload_triples: PayloadTriplesExtractor,
    now_iso: NowFn,
    triples_count: int | None = None,
    success_override: bool | None = None,
) -> None:
    row = {
        "ts": now_iso(),
        "book": task.book_name,
        "chapter": task.chapter_name,
        "chunk_index": task.chunk_index,
        "sequence": task.sequence,
        "success": (error is None) if success_override is None else bool(success_override),
        "error": error,
        "triples_count": triples_count if triples_count is not None else len(extract_payload_triples(payload)),
        "attempt": attempt,
        "resumed": resumed,
    }
    with checkpoint_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def load_existing_triple_records(path: Path, *, triple_record_cls: type) -> list[Any]:
    rows: list[Any] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line.lstrip("\ufeff"))
            rows.append(
                triple_record_cls(
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


def load_completed_chunk_keys(run_dir: Path) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    if checkpoint_path.exists():
        latest_status: dict[tuple[str, int], bool] = {}
        with checkpoint_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line.lstrip("\ufeff"))
                key = (str(row.get("book", "")), int(row.get("chunk_index", 0)))
                latest_status[key] = row.get("success") is True
        for key, is_success in latest_status.items():
            if is_success:
                completed.add(key)
        return completed

    raw_jsonl = run_dir / "triples.raw.jsonl"
    if not raw_jsonl.exists():
        return completed

    with raw_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line.lstrip("\ufeff"))
            error = row.get("error")
            if "error" in row and error not in (None, ""):
                continue
            completed.add((str(row.get("book", "")), int(row.get("chunk_index", 0))))
    return completed


def resolve_run_publish_source(run_dir: Path) -> tuple[Path, Path | None]:
    cleaned_graph_jsonl_path = run_dir / "graph_facts.cleaned.jsonl"
    if cleaned_graph_jsonl_path.exists():
        evidence_path = run_dir / "evidence_metadata.jsonl"
        return cleaned_graph_jsonl_path, evidence_path if evidence_path.exists() else None
    cleaned_graph_path = run_dir / "graph_facts.cleaned.json"
    if cleaned_graph_path.exists():
        evidence_path = run_dir / "evidence_metadata.jsonl"
        return cleaned_graph_path, evidence_path if evidence_path.exists() else None
    graph_import_path = run_dir / "graph_import.json"
    if not graph_import_path.exists():
        raise FileNotFoundError("graph_import.json not found in run dir")
    evidence_path = run_dir / "evidence_metadata.jsonl"
    return graph_import_path, evidence_path if evidence_path.exists() else None
