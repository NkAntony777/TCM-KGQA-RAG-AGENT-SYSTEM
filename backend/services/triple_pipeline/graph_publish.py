from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Any

from services.triple_pipeline_models import TripleRecord

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent.parent
DEFAULT_GRAPH_BASE = BACKEND_DIR / "services" / "graph_service" / "data" / "sample_graph.json"
DEFAULT_GRAPH_TARGET = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.json"
GRAPH_RUNTIME_IO_LOCK = RLock()


def _write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding=encoding, dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _load_json_file_strict(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"json_file_not_found: {path}")
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        raise ValueError(f"json_file_empty: {path}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw_sig = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
        if not raw_sig:
            raise ValueError(f"json_file_empty: {path}")
        return json.loads(raw_sig)


def _extract_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            value = str(item).strip()
            if value and value not in fact_ids:
                fact_ids.append(value)
    raw_fact_id = str(row.get("fact_id", "")).strip()
    if raw_fact_id and raw_fact_id not in fact_ids:
        fact_ids.append(raw_fact_id)
    return fact_ids


def _dedupe_graph_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_index: dict[tuple[str, str, str, str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject", "")).strip()
        predicate = str(row.get("predicate", "")).strip()
        obj = str(row.get("object", "")).strip()
        source_book = str(row.get("source_book", "")).strip()
        source_chapter = str(row.get("source_chapter", "")).strip()
        if not subject or not predicate or not obj:
            continue
        signature = (subject, predicate, obj, source_book, source_chapter)
        fact_ids = _extract_fact_ids(row)
        existing_index = seen_index.get(signature)
        if existing_index is not None:
            existing = deduped[existing_index]
            merged_fact_ids = _extract_fact_ids(existing)
            for fact_id in fact_ids:
                if fact_id not in merged_fact_ids:
                    merged_fact_ids.append(fact_id)
            if merged_fact_ids:
                existing["fact_ids"] = merged_fact_ids
                existing["fact_id"] = merged_fact_ids[0]
            continue

        payload = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "subject_type": str(row.get("subject_type", "other")).strip() or "other",
            "object_type": str(row.get("object_type", "other")).strip() or "other",
            "source_book": source_book,
            "source_chapter": source_chapter,
        }
        if fact_ids:
            payload["fact_ids"] = fact_ids
            payload["fact_id"] = fact_ids[0]
        seen_index[signature] = len(deduped)
        deduped.append(payload)
    deduped.sort(
        key=lambda item: (
            item["subject"],
            item["predicate"],
            item["object"],
            item["source_book"],
            item["source_chapter"],
        )
    )
    return deduped


def _load_jsonl_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line.lstrip("\ufeff"))
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _dedupe_evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        fact_ids = _extract_fact_ids(row)
        key = "||".join([
            ",".join(fact_ids),
            str(row.get("source_book", "")).strip(),
            str(row.get("source_chapter", "")).strip(),
            str(row.get("source_text", "")).strip(),
        ])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _derive_evidence_target_path(graph_target_path: Path) -> Path:
    return graph_target_path.with_suffix(".evidence.jsonl")

def save_manifest(self, run_dir: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(
        run_dir / "manifest.json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def write_csv(self, path: Path, rows: list[TripleRecord]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "subject",
                "predicate",
                "object",
                "subject_type",
                "object_type",
                "source_book",
                "source_chapter",
                "source_text",
                "confidence",
                "raw_predicate",
                "raw_subject_type",
                "raw_object_type",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

def write_graph_import(self, path: Path, rows: list[TripleRecord]) -> None:
    payload = [
        {
            "subject": row.subject,
            "predicate": row.predicate,
            "object": row.object,
            "subject_type": row.subject_type,
            "object_type": row.object_type,
            "source_book": row.source_book,
            "source_chapter": row.source_chapter,
        }
        for row in rows
    ]
    _write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def publish_graph(
    self,
    *,
    graph_import_path: Path | None = None,
    run_dir: Path | None = None,
    target_path: Path | None = None,
    replace: bool = False,
) -> Path:
    evidence_source_path: Path | None = None
    if graph_import_path is None:
        chosen_run_dir = run_dir or self.latest_run()
        if chosen_run_dir is None:
            raise FileNotFoundError("no_run_dir_available")
        cleaned_graph_path = chosen_run_dir / "graph_facts.cleaned.json"
        graph_import_path = cleaned_graph_path if cleaned_graph_path.exists() else chosen_run_dir / "graph_import.json"
        candidate_evidence_path = chosen_run_dir / "evidence_metadata.jsonl"
        if candidate_evidence_path.exists():
            evidence_source_path = candidate_evidence_path
    else:
        candidate_evidence_path = graph_import_path.parent / "evidence_metadata.jsonl"
        if candidate_evidence_path.exists():
            evidence_source_path = candidate_evidence_path

    if not graph_import_path.exists():
        raise FileNotFoundError(f"graph_import_not_found: {graph_import_path}")

    target = target_path or DEFAULT_GRAPH_TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    evidence_target_path = _derive_evidence_target_path(target)

    with GRAPH_RUNTIME_IO_LOCK:
        incoming = _load_json_file_strict(graph_import_path)
        if not isinstance(incoming, list):
            raise ValueError("graph_import_invalid")

        base_rows: list[dict[str, Any]] = []
        if not replace and target.exists():
            existing = _load_json_file_strict(target)
            if isinstance(existing, list):
                base_rows = existing
        elif not replace and target == DEFAULT_GRAPH_TARGET and DEFAULT_GRAPH_BASE.exists():
            base_graph = _load_json_file_strict(DEFAULT_GRAPH_BASE)
            if isinstance(base_graph, list):
                base_rows = base_graph

        merged = _dedupe_graph_rows(base_rows + incoming)
        _write_text_atomic(target, json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

        base_evidence_rows: list[dict[str, Any]] = []
        if not replace and evidence_target_path.exists():
            base_evidence_rows = _load_jsonl_rows(evidence_target_path)

        incoming_evidence_rows = _load_jsonl_rows(evidence_source_path) if evidence_source_path else []
        if base_evidence_rows or incoming_evidence_rows:
            merged_evidence_rows = _dedupe_evidence_rows(base_evidence_rows + incoming_evidence_rows)
            _write_text_atomic(
                evidence_target_path,
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged_evidence_rows),
                encoding="utf-8",
            )
    return target
