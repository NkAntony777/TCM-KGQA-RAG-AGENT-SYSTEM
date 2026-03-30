"""
pipeline_server.py  —  TCM 三元组提取流水线 Web 控制台（后端）
启动: python pipeline_server.py --port 7800
访问: http://127.0.0.1:7800
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

# ── 路径修正：让 pipeline_server.py 能 import tcm_triple_console ──────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(_BACKEND_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from scripts.tcm_triple_console import (
    DEFAULT_BOOKS_DIR,
    DEFAULT_GRAPH_TARGET,
    DEFAULT_OUTPUT_DIR,
    PipelineConfig,
    TCMTriplePipeline,
    TripleRecord,
    _extract_payload_triples,
    _load_json_file,
    _first_env,
)

# ─────────────────────────────────────────────────────────────────────────────
# 全局状态
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="TCM Triple Pipeline Console", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 当前运行状态（单例任务模型）
_run_lock = threading.Lock()
_current_job: dict[str, Any] = {}          # 当前运行元数据
_job_log: list[dict[str, Any]] = []        # 实时日志队列（线程安全追加）
_job_log_file: Path | None = None          # 实时日志磁盘文件，任务结束时清理
_job_log_file_path: Path | None = None     # 日志文件路径（用于任务结束后删除）
_job_thread: threading.Thread | None = None
_job_cancelled = threading.Event()         # 用于取消信号
_publish_lock = threading.Lock()
_nebula_publish_threads: dict[str, threading.Thread] = {}

LOW_YIELD_RETRY_TRIPLE_THRESHOLD = 1


def _log(level: str, msg: str, **extra: Any) -> None:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "msg": msg, **extra}
    with _run_lock:
        _job_log.append(entry)
        if _job_log_file is not None:
            with _job_log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _publish_status_path(run_dir: Path) -> Path:
    return run_dir / "publish_status.json"


def _normalize_publish_status(payload: Any) -> dict[str, Any]:
    base = payload if isinstance(payload, dict) else {}
    json_status = base.get("json")
    nebula_status = base.get("nebula")
    if not isinstance(json_status, dict):
        json_status = {}
    if not isinstance(nebula_status, dict):
        nebula_status = {}
    return {
        "json": {
            "status": str(json_status.get("status", "idle") or "idle"),
            "published": bool(json_status.get("published", False)),
            "published_at": str(json_status.get("published_at", "") or ""),
            "updated_at": str(json_status.get("updated_at", "") or ""),
            "target": str(json_status.get("target", "") or ""),
            "graph_triples": int(json_status.get("graph_triples", 0) or 0),
            "evidence_count": int(json_status.get("evidence_count", 0) or 0),
        },
        "nebula": {
            "status": str(nebula_status.get("status", "idle") or "idle"),
            "published": bool(nebula_status.get("published", False)),
            "published_at": str(nebula_status.get("published_at", "") or ""),
            "updated_at": str(nebula_status.get("updated_at", "") or ""),
            "started_at": str(nebula_status.get("started_at", "") or ""),
            "finished_at": str(nebula_status.get("finished_at", "") or ""),
            "target": str(nebula_status.get("target", "") or ""),
            "source_path": str(nebula_status.get("source_path", "") or ""),
            "space": str(nebula_status.get("space", "") or ""),
            "graph_triples": int(nebula_status.get("graph_triples", 0) or 0),
            "progress_current": int(nebula_status.get("progress_current", 0) or 0),
            "progress_total": int(nebula_status.get("progress_total", 0) or 0),
            "progress_pct": float(nebula_status.get("progress_pct", 0.0) or 0.0),
            "ok_count": int(nebula_status.get("ok_count", 0) or 0),
            "fail_count": int(nebula_status.get("fail_count", 0) or 0),
            "error": str(nebula_status.get("error", "") or ""),
        },
    }


def _load_publish_status(run_dir: Path) -> dict[str, Any]:
    path = _publish_status_path(run_dir)
    payload = _load_json_file(path, {}) if path.exists() else {}
    return _normalize_publish_status(payload)


def _write_publish_status(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_publish_status(payload)
    _publish_status_path(run_dir).write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized


def _update_publish_status(run_dir: Path, section: str, patch: dict[str, Any]) -> dict[str, Any]:
    if section not in {"json", "nebula"}:
        raise ValueError(f"unsupported_publish_section: {section}")
    with _publish_lock:
        payload = _load_publish_status(run_dir)
        section_payload = payload.get(section, {})
        if not isinstance(section_payload, dict):
            section_payload = {}
        section_payload.update(patch)
        section_payload["updated_at"] = _now_iso()
        payload[section] = section_payload
        return _write_publish_status(run_dir, payload)


def _mark_cancel_requested() -> None:
    run_dir = None
    state_snapshot: dict[str, Any] | None = None
    with _run_lock:
        if not _current_job:
            return
        _current_job["status"] = "cancelling"
        _current_job["phase"] = "cancelling"
        _current_job["cancel_requested_at"] = datetime.now().isoformat(timespec="seconds")
        run_dir = _current_job.get("run_dir")
        state_snapshot = dict(_current_job)
    if run_dir and state_snapshot:
        state_path = Path(str(run_dir)) / "state.json"
        try:
            _write_state(state_path, state_snapshot)
        except Exception:
            pass


def _append_checkpoint(
    checkpoint_path: Path,
    *,
    task: Any,
    error: str | None,
    payload: dict[str, Any],
    attempt: int,
    resumed: bool,
    triples_count: int | None = None,
) -> None:
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "book": task.book_name,
        "chapter": task.chapter_name,
        "chunk_index": task.chunk_index,
        "sequence": task.sequence,
        "success": error is None,
        "error": error,
        "triples_count": triples_count if triples_count is not None else len(_extract_payload_triples(payload)),
        "attempt": attempt,
        "resumed": resumed,
    }
    with checkpoint_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _load_existing_triple_records(path: Path) -> list[TripleRecord]:
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


def _load_completed_chunk_keys(run_dir: Path) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    if checkpoint_path.exists():
        latest_status: dict[tuple[str, int], bool] = {}
        with checkpoint_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
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
            row = json.loads(line)
            error = row.get("error")
            if "error" in row and error not in (None, ""):
                continue
            completed.add((str(row.get("book", "")), int(row.get("chunk_index", 0))))
    return completed


def _low_yield_retry_error(triples_count: int) -> str:
    return f"low_yield_retry: triples_count={triples_count}"


def _extract_payload_meta(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    meta = payload.get("__meta__")
    return meta if isinstance(meta, dict) else {}


def _build_raw_chunk_record(
    *,
    task: Any,
    payload: Any,
    error: str | None,
    rows_count: int,
) -> dict[str, Any]:
    meta = _extract_payload_meta(payload)
    usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    record = {
        "book": task.book_name,
        "chapter": task.chapter_name,
        "chunk_index": task.chunk_index,
        "payload": payload,
        "error": error,
        "llm_raw_text": str(meta.get("raw_text", "")) if meta else "",
        "llm_usage": usage,
        "llm_finish_reason": meta.get("finish_reason"),
        "llm_response_format_mode": meta.get("response_format_mode"),
    }
    if completion_tokens >= 1000 and rows_count <= 1:
        record["diagnostic"] = "high_completion_low_yield"
    return record


def _evaluate_chunk_attempt(
    pipeline: TCMTriplePipeline,
    *,
    task: Any,
    payload: dict[str, Any],
    error: str | None,
) -> tuple[list[TripleRecord], str | None]:
    rows = pipeline.normalize_triples(
        payload=payload,
        book_name=task.book_name,
        chapter_name=task.chapter_name,
    )
    if error is None and len(rows) <= LOW_YIELD_RETRY_TRIPLE_THRESHOLD:
        return rows, _low_yield_retry_error(len(rows))
    return rows, error


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _build_pipeline(cfg_override: dict[str, Any] | None = None) -> TCMTriplePipeline:
    cfg = cfg_override or {}
    # 前端显式传入的值优先；只有为空时才 fallback 到环境变量
    model = cfg.get("model") or _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="deepseek-ai/DeepSeek-V3.2")
    api_key_raw = cfg.get("api_key")
    if not api_key_raw:
        api_key_raw = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    api_key = api_key_raw
    base_url = cfg.get("base_url") or _first_env(
        "TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL",
        default="https://api.siliconflow.cn/v1"
    )
    config = PipelineConfig(
        books_dir=Path(cfg.get("books_dir") or DEFAULT_BOOKS_DIR),
        output_dir=Path(cfg.get("output_dir") or DEFAULT_OUTPUT_DIR),
        model=model,
        api_key=api_key or "dummy_for_dry_run",
        base_url=base_url,
        request_timeout=float(cfg.get("request_timeout", 90.0)),
        max_chunk_chars=int(cfg.get("max_chunk_chars", 800)),
        chunk_overlap=int(cfg.get("chunk_overlap", 200)),
        max_retries=int(cfg.get("max_retries", 2)),
        request_delay=float(cfg.get("request_delay", 0.8)),
        parallel_workers=max(1, int(cfg.get("parallel_workers", 4))),
        retry_backoff_base=float(cfg.get("retry_backoff_base", 2.0)),
        chunk_strategy=str(cfg.get("chunk_strategy", "body_first")),
    )
    return TCMTriplePipeline(config)


def _is_full_completed_run(manifest: dict[str, Any], state: dict[str, Any]) -> bool:
    if bool(manifest.get("dry_run", False)):
        return False
    if str(state.get("status", "")).strip().lower() != "completed":
        return False

    manifest_cfg = manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}
    if manifest_cfg.get("max_chunks_per_book") not in (None, "", 0):
        return False
    if int(manifest_cfg.get("skip_initial_chunks_per_book", 0) or 0) != 0:
        return False
    if any(str(item).strip() for item in (manifest_cfg.get("chapter_excludes") or [])):
        return False
    return True


def _get_processed_book_stems() -> set[str]:
    """扫描历史 run，收集已完整处理过的书目 stems。"""
    processed: set[str] = set()
    output_dir = DEFAULT_OUTPUT_DIR
    if not output_dir.exists():
        return processed
    for run_dir in output_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        state_path = run_dir / "state.json"
        if not manifest_path.exists() or not state_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if not _is_full_completed_run(manifest, state):
                continue
            for book_str in manifest.get("books", []):
                processed.add(Path(book_str).stem)
        except Exception:
            continue
    return processed


def _resolve_start_selected_books(pipeline: TCMTriplePipeline, raw_selected_books: list[str]) -> list[Path]:
    books = pipeline.discover_books()
    selected: list[Path] = []
    if raw_selected_books:
        for token in raw_selected_books:
            token = token.strip()
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(books):
                    selected.append(books[idx - 1])
            else:
                selected.extend([b for b in books if token in b.stem])
        seen: set[Path] = set()
        deduped = []
        for path in selected:
            if path not in seen:
                seen.add(path)
                deduped.append(path)
        return deduped
    return books


def _exclude_processed_books_for_new_run(selected_books: list[Path]) -> tuple[list[Path], list[str]]:
    processed_stems = _get_processed_book_stems()
    skipped = [path.stem for path in selected_books if path.stem in processed_stems]
    kept = [path for path in selected_books if path.stem not in processed_stems]
    return kept, skipped


def _resolve_run_publish_source(run_dir: Path) -> tuple[Path, Path | None]:
    cleaned_graph_path = run_dir / "graph_facts.cleaned.json"
    if cleaned_graph_path.exists():
        evidence_path = run_dir / "evidence_metadata.jsonl"
        return cleaned_graph_path, evidence_path if evidence_path.exists() else None
    graph_import_path = run_dir / "graph_import.json"
    if not graph_import_path.exists():
        raise FileNotFoundError("graph_import.json not found in run dir")
    evidence_path = run_dir / "evidence_metadata.jsonl"
    return graph_import_path, evidence_path if evidence_path.exists() else None


def _record_json_publish_status(
    run_dir: Path,
    *,
    target: Path,
    graph_triples: int,
    evidence_count: int,
) -> dict[str, Any]:
    return _update_publish_status(
        run_dir,
        "json",
        {
            "status": "completed",
            "published": True,
            "published_at": _now_iso(),
            "target": str(target),
            "graph_triples": graph_triples,
            "evidence_count": evidence_count,
        },
    )


def _run_nebula_publish_job(run_name: str) -> None:
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    try:
        if not run_dir.exists():
            raise FileNotFoundError("run_not_found")

        pipeline = _build_pipeline()
        target = pipeline.publish_graph(run_dir=run_dir, replace=False)
        graph_data = json.loads(target.read_text(encoding="utf-8"))
        evidence_path = target.parent / f"{target.stem}.evidence.jsonl"
        evidence_count = 0
        if evidence_path.exists():
            evidence_count = sum(1 for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip())
        _record_json_publish_status(
            run_dir,
            target=target,
            graph_triples=len(graph_data),
            evidence_count=evidence_count,
        )

        graph_import_path, evidence_path = _resolve_run_publish_source(run_dir)
        from services.graph_service.nebulagraph_store import NebulaGraphStore, load_graph_rows

        rows_with_evidence = load_graph_rows(graph_import_path, evidence_path)
        store = NebulaGraphStore()
        health = store.health()
        if not store.client_available():
            raise RuntimeError(_nebula_health_detail(health))

        stmts = store.build_schema_statements() + store.build_import_statements(rows_with_evidence)
        total = len(stmts)
        _update_publish_status(
            run_dir,
            "nebula",
            {
                "status": "running",
                "published": False,
                "target": str(target),
                "source_path": str(graph_import_path),
                "space": store.settings.space,
                "graph_triples": len(graph_data),
                "progress_current": 0,
                "progress_total": total,
                "progress_pct": 0.0,
                "ok_count": 0,
                "fail_count": 0,
                "error": "",
            },
        )

        from nebula3.gclient.net import ConnectionPool
        from nebula3.Config import Config as NebulaConfig

        config = NebulaConfig()
        config.max_connection_pool_size = 2
        config.timeout = 30000
        pool = ConnectionPool()
        pool.init([(store.settings.host, store.settings.port)], config)
        session = pool.get_session(store.settings.user, store.settings.password)

        ok_count = 0
        fail_count = 0
        last_error = ""
        try:
            for idx, stmt in enumerate(stmts, start=1):
                result = session.execute(f"USE `{store.settings.space}`; {stmt}")
                if result.is_succeeded():
                    ok_count += 1
                else:
                    fail_count += 1
                    last_error = str(result.error_msg() or "")

                if idx == 1 or idx == total or idx % 10 == 0:
                    _update_publish_status(
                        run_dir,
                        "nebula",
                        {
                            "status": "running",
                            "progress_current": idx,
                            "progress_total": total,
                            "progress_pct": round((idx / total) * 100, 1) if total else 100.0,
                            "ok_count": ok_count,
                            "fail_count": fail_count,
                            "error": last_error if fail_count else "",
                        },
                    )
        finally:
            session.release()
            pool.close()

        final_status = "completed" if fail_count == 0 else "error"
        _update_publish_status(
            run_dir,
            "nebula",
            {
                "status": final_status,
                "published": fail_count == 0,
                "published_at": _now_iso() if fail_count == 0 else "",
                "finished_at": _now_iso(),
                "progress_current": total,
                "progress_total": total,
                "progress_pct": 100.0,
                "ok_count": ok_count,
                "fail_count": fail_count,
                "error": "" if fail_count == 0 else (last_error or f"nebula_fail_count={fail_count}"),
            },
        )
    except Exception as exc:
        if run_dir.exists():
            _update_publish_status(
                run_dir,
                "nebula",
                {
                    "status": "error",
                    "published": False,
                    "finished_at": _now_iso(),
                    "error": str(exc),
                },
            )
    finally:
        with _publish_lock:
            _nebula_publish_threads.pop(run_name, None)


def _nebula_health_detail(health: dict[str, Any]) -> str:
    warning = str(health.get("warning", "") or "").strip()
    host = str(health.get("host", "") or "").strip()
    port = health.get("port")
    space = str(health.get("space", "") or "").strip()
    base = f"NebulaGraph not reachable: host={host} port={port} space={space}"
    return f"{base} | {warning}" if warning else base


def _fmt_eta(remaining_secs: float) -> str:
    if remaining_secs <= 0:
        return "完成"
    td = timedelta(seconds=int(remaining_secs))
    h, rem = divmod(td.seconds, 3600)
    m, s = divmod(rem, 60)
    if td.days > 0:
        return f"{td.days}天{h}小时{m}分"
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def _update_runtime_metrics(
    state: dict[str, Any],
    *,
    start_ts: float,
    session_chunks_done: int,
    total_chunks_done: int,
    total_chunks_all: int,
) -> None:
    elapsed = time.time() - start_ts
    state["elapsed_secs"] = int(elapsed)
    state["chunks_completed"] = total_chunks_done
    if session_chunks_done <= 0 or total_chunks_all <= 0:
        state["speed_chunks_per_min"] = 0.0
        state["eta"] = ""
        return
    rate = session_chunks_done / max(elapsed, 1)
    remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
    state["eta"] = _fmt_eta(remaining)
    state["speed_chunks_per_min"] = round(rate * 60, 1)


def _derive_retry_parallel_workers(parallel_workers: Any) -> int:
    try:
        workers = int(parallel_workers)
    except (TypeError, ValueError):
        workers = 1
    workers = max(1, workers)
    return max(1, workers // 2)


# ─────────────────────────────────────────────────────────────────────────────
# 核心后台任务
# ─────────────────────────────────────────────────────────────────────────────

def _run_extraction_job(
    *,
    job_id: str,
    selected_books: list[Path],
    label: str,
    dry_run: bool,
    cfg_override: dict[str, Any],
    chapter_excludes: list[str],
    max_chunks_per_book: int | None,
    skip_initial_chunks: int,
    chunk_strategy: str,
    auto_clean: bool,
    auto_publish: bool,
    max_chunk_retries: int = 2,
    resume_run_dir: Path | None = None,
) -> None:
    """在独立线程中运行完整的提取→清洗→发布流程，实时更新 _current_job。"""
    global _current_job

    pipeline = _build_pipeline(cfg_override)
    resume_mode = resume_run_dir is not None
    run_dir = resume_run_dir or pipeline.create_run_dir(label=label)
    run_dir.mkdir(parents=True, exist_ok=True)

    start_ts = time.time()
    checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
    triples_jsonl = run_dir / "triples.normalized.jsonl"
    raw_jsonl = run_dir / "triples.raw.jsonl"
    state_path = run_dir / "state.json"
    completed_chunk_keys = _load_completed_chunk_keys(run_dir) if resume_mode else set()
    total_chunks_done = len(completed_chunk_keys)
    session_chunks_done = 0
    total_chunks_all = 0
    total_triples = _count_jsonl_rows(triples_jsonl)
    chunk_errors = 0
    retry_parallel_workers = _derive_retry_parallel_workers(pipeline.config.parallel_workers)

    state: dict[str, Any] = {
        "job_id": job_id,
        "status": "running",
        "phase": "scheduling",
        "books_total": len(selected_books),
        "books_completed": 0,
        "chunks_total": 0,
        "chunks_completed": 0,
        "total_triples": 0,
        "chunk_errors": 0,
        "chunk_retries": 0,
        "current_book": "",
        "current_chapter": "",
        "elapsed_secs": 0,
        "eta": "",
        "run_dir": str(run_dir),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "dry_run": dry_run,
        "model": pipeline.config.model,
        "speed_chunks_per_min": 0.0,
        "resumed": resume_mode,
        "resumed_run_dir": run_dir.name if resume_mode else "",
        "resume_skipped_chunks": len(completed_chunk_keys),
        "retry_parallel_workers": retry_parallel_workers,
    }
    with _run_lock:
        _current_job.update(state)
    _write_state(state_path, state)

    _log("info", f"任务启动 job_id={job_id}，共 {len(selected_books)} 本书")

    # 保存 manifest
    pipeline.save_manifest(run_dir, {
        "job_id": job_id,
        "created_at": datetime.now().isoformat(),
        "books": [str(p) for p in selected_books],
        "model": pipeline.config.model,
        "base_url": pipeline.config.base_url,
        "dry_run": dry_run,
        "resume_run_dir": str(resume_run_dir) if resume_run_dir else "",
        "config": {
            "max_chunk_chars": pipeline.config.max_chunk_chars,
            "chunk_overlap": pipeline.config.chunk_overlap,
            "chapter_excludes": chapter_excludes,
            "skip_initial_chunks_per_book": skip_initial_chunks,
            "chunk_strategy": chunk_strategy,
            "parallel_workers": pipeline.config.parallel_workers,
            "request_timeout": pipeline.config.request_timeout,
            "max_retries": pipeline.config.max_retries,
            "request_delay": pipeline.config.request_delay,
            "retry_backoff_base": pipeline.config.retry_backoff_base,
            "max_chunks_per_book": max_chunks_per_book,
            "max_chunk_retries": max_chunk_retries,
        },
    })
    all_rows = _load_existing_triple_records(triples_jsonl) if resume_mode else []
    cancel_logged = False

    def note_cancelling() -> None:
        nonlocal cancel_logged
        state["status"] = "cancelling"
        state["phase"] = "cancelling"
        with _run_lock:
            _current_job.update(state)
        _write_state(state_path, state)
        if not cancel_logged:
            _log("warn", "收到取消信号，等待当前进行中的请求结束并停止后续调度")
            cancel_logged = True

    def run_retry_batch(failed_items: list[dict[str, Any]], retry_count: int) -> None:
        nonlocal total_triples, total_chunks_done, session_chunks_done

        if retry_parallel_workers <= 1 or len(failed_items) <= 1:
            for result in failed_items:
                if _job_cancelled.is_set():
                    note_cancelling()
                    break
                task = result["task"]
                result["_retried"] = result.get("_retried", 0) + 1
                state["current_chapter"] = task.chapter_name
                state["current_chunk_index"] = task.chunk_index
                with _run_lock:
                    _current_job.update(state)
                try:
                    payload = pipeline.extract_chunk_payload(task, dry_run=dry_run)
                    result["payload"] = payload
                    result["error"] = None
                    _log("ok", f"  chunk {task.chunk_index} 重试成功 ✓")
                except Exception as exc:
                    payload = {"triples": []}
                    result["payload"] = payload
                    result["error"] = str(exc)
                    _log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
                rows, effective_error = _evaluate_chunk_attempt(
                    pipeline,
                    task=task,
                    payload=payload,
                    error=result["error"],
                )
                result["error"] = effective_error
                result["rows"] = rows
                if effective_error is None and not result.get("_written"):
                    for row in rows:
                        pipeline.append_jsonl(triples_jsonl, asdict(row))
                    result["_written"] = True
                    total_triples += len(rows)
                    state["total_triples"] = total_triples
                if result["error"] is None:
                    completed_chunk_keys.add((task.book_name, task.chunk_index))
                pipeline.append_jsonl(
                    raw_jsonl,
                    _build_raw_chunk_record(
                        task=task,
                        payload=payload,
                        error=result["error"],
                        rows_count=len(rows),
                    ),
                )
                _append_checkpoint(
                    checkpoint_path,
                    task=task,
                    error=result["error"],
                    payload=payload,
                    attempt=result.get("_retried", 0),
                    resumed=resume_mode,
                    triples_count=len(rows),
                )
                total_chunks_done += 1
                session_chunks_done += 1
                _update_runtime_metrics(
                    state,
                    start_ts=start_ts,
                    session_chunks_done=session_chunks_done,
                    total_chunks_done=total_chunks_done,
                    total_chunks_all=total_chunks_all,
                )
                with _run_lock:
                    _current_job.update(state)
                _write_state(state_path, state)
            return

        worker_count = min(retry_parallel_workers, len(failed_items))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {}
            for result in failed_items:
                result["_retried"] = result.get("_retried", 0) + 1
                future_map[executor.submit(pipeline.extract_chunk_payload, result["task"], dry_run)] = result
            _log("info", f"  [retry] 第 {retry_count} 轮提交 {len(failed_items)} 个 chunk，retry_parallel_workers={worker_count}")

            for future in as_completed(future_map):
                if _job_cancelled.is_set():
                    note_cancelling()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                result = future_map[future]
                task = result["task"]
                state["current_chapter"] = task.chapter_name
                state["current_chunk_index"] = task.chunk_index
                try:
                    payload = future.result()
                    result["payload"] = payload
                    result["error"] = None
                    _log("ok", f"  chunk {task.chunk_index} 重试成功 ✓")
                except Exception as exc:
                    payload = {"triples": []}
                    result["payload"] = payload
                    result["error"] = str(exc)
                    _log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
                rows, effective_error = _evaluate_chunk_attempt(
                    pipeline,
                    task=task,
                    payload=payload,
                    error=result["error"],
                )
                result["error"] = effective_error
                result["rows"] = rows
                if effective_error is None and not result.get("_written"):
                    for row in rows:
                        pipeline.append_jsonl(triples_jsonl, asdict(row))
                    result["_written"] = True
                    total_triples += len(rows)
                    state["total_triples"] = total_triples
                if result["error"] is None:
                    completed_chunk_keys.add((task.book_name, task.chunk_index))
                pipeline.append_jsonl(
                    raw_jsonl,
                    _build_raw_chunk_record(
                        task=task,
                        payload=payload,
                        error=result["error"],
                        rows_count=len(rows),
                    ),
                )
                _append_checkpoint(
                    checkpoint_path,
                    task=task,
                    error=result["error"],
                    payload=payload,
                    attempt=result.get("_retried", 0),
                    resumed=resume_mode,
                    triples_count=len(rows),
                )
                total_chunks_done += 1
                session_chunks_done += 1
                _update_runtime_metrics(
                    state,
                    start_ts=start_ts,
                    session_chunks_done=session_chunks_done,
                    total_chunks_done=total_chunks_done,
                    total_chunks_all=total_chunks_all,
                )
                _log(
                    "info",
                    f"  [retry] progress {session_chunks_done} session_done | chunk={task.chunk_index} | "
                    f"triples={len(rows)} | total_triples={total_triples} | error={result['error'] or '-'}",
                )
                with _run_lock:
                    _current_job.update(state)
                _write_state(state_path, state)

    try:
        # ── 第一阶段：分块调度 ──────────────────────────────────────────
        all_tasks_per_book: list[tuple[Path, list]] = []
        for book_path in selected_books:
            tasks = pipeline.schedule_book_chunks(
                book_path=book_path,
                chapter_excludes=chapter_excludes or None,
                max_chunks_per_book=max_chunks_per_book,
                skip_initial_chunks_per_book=skip_initial_chunks,
                chunk_strategy=chunk_strategy,
            )
            all_tasks_per_book.append((book_path, tasks))
            total_chunks_all += len(tasks)
        state["chunks_total"] = total_chunks_all
        state["chunks_completed"] = total_chunks_done
        state["total_triples"] = total_triples
        state["phase"] = "extracting"
        _update_runtime_metrics(
            state,
            start_ts=start_ts,
            session_chunks_done=session_chunks_done,
            total_chunks_done=total_chunks_done,
            total_chunks_all=total_chunks_all,
        )
        with _run_lock:
            _current_job.update(state)
        _write_state(state_path, state)
        _log("info", f"调度完成，共 {total_chunks_all} 个 chunk")

        # ── 第二阶段：逐书提取 ──────────────────────────────────────────
        for book_index, (book_path, tasks) in enumerate(all_tasks_per_book, start=1):
            scheduled_tasks = list(tasks)
            skipped_completed = 0
            if _job_cancelled.is_set():
                note_cancelling()
                break
            if resume_mode:
                pending_tasks = []
                for task in scheduled_tasks:
                    if (task.book_name, task.chunk_index) in completed_chunk_keys:
                        skipped_completed += 1
                    else:
                        pending_tasks.append(task)
                tasks = pending_tasks

            state["current_book"] = book_path.stem
            state["books_completed"] = book_index - 1
            with _run_lock:
                _current_job.update(state)
            _write_state(state_path, state)
            _log("info", f"开始处理 [{book_index}/{len(selected_books)}] {book_path.stem}，{len(tasks)} chunks | parallel={pipeline.config.parallel_workers} retry_parallel={retry_parallel_workers} dry_run={dry_run}")

            if not tasks:
                if scheduled_tasks:
                    state["books_completed"] = book_index
                with _run_lock:
                    _current_job.update(state)
                _write_state(state_path, state)
                _log("warn", f"{book_path.stem} 无可处理 chunk（全部被过滤）")
                continue

            results: dict[int, dict[str, Any]] = {}

            if dry_run or pipeline.config.parallel_workers <= 1 or len(tasks) == 1:
                for task in tasks:
                    if _job_cancelled.is_set():
                        note_cancelling()
                        break
                    state["current_chapter"] = task.chapter_name
                    with _run_lock:
                        _current_job.update(state)
                    _log("info", f"  -> 处理 chunk {task.chunk_index}/{len(tasks)} {task.chapter_name[:20]}")
                    try:
                        payload = pipeline.extract_chunk_payload(task, dry_run=dry_run)
                        error = None
                        _log("ok", f"  chunk {task.chunk_index}/{len(tasks)} ✓ {task.chapter_name[:30]}")
                    except Exception as exc:
                        payload = {"triples": []}
                        error = str(exc)
                        chunk_errors += 1
                        state["chunk_errors"] = chunk_errors
                        _log("error", f"  chunk {task.chunk_index} 失败: {str(exc)[:80]}")
                    rows, effective_error = _evaluate_chunk_attempt(
                        pipeline,
                        task=task,
                        payload=payload,
                        error=error,
                    )
                    results[task.sequence] = {
                        "task": task,
                        "payload": payload,
                        "error": effective_error,
                        "rows": rows,
                        "_retried": 0,
                    }
                    result = results[task.sequence]
                    result["_written"] = False
                    if effective_error is not None and error is None:
                        _log("warn", f"  chunk {task.chunk_index} low_yield | triples={len(rows)} | queued_for_retry")
                    if effective_error is None:
                        for row in rows:
                            pipeline.append_jsonl(triples_jsonl, asdict(row))
                        result["_written"] = True
                    if error is None and False:
                        _log("warn", f"  chunk {task.chunk_index} 无三元组 | triple_count={len(rows)} | error={error} | payload_keys={list(payload.keys()) if isinstance(payload, dict) else 'not_dict'}")
                    if effective_error is None:
                        total_triples += len(rows)
                        state["total_triples"] = total_triples
                        completed_chunk_keys.add((task.book_name, task.chunk_index))
                    pipeline.append_jsonl(
                        raw_jsonl,
                        _build_raw_chunk_record(
                            task=task,
                            payload=payload,
                            error=effective_error,
                            rows_count=len(rows),
                        ),
                    )
                    _append_checkpoint(
                        checkpoint_path,
                        task=task,
                        error=effective_error,
                        payload=payload,
                        attempt=0,
                        resumed=resume_mode,
                        triples_count=len(rows),
                    )
                    total_chunks_done += 1
                    session_chunks_done += 1
                    _update_runtime_metrics(
                        state,
                        start_ts=start_ts,
                        session_chunks_done=session_chunks_done,
                        total_chunks_done=total_chunks_done,
                        total_chunks_all=total_chunks_all,
                    )
                    with _run_lock:
                        _current_job.update(state)
                    _write_state(state_path, state)
                if _job_cancelled.is_set():
                    break

            # Retry failed chunks (serial path)
            retry_count = 0
            while retry_count < max_chunk_retries:
                if _job_cancelled.is_set():
                    note_cancelling()
                    break
                failed_tasks = [r for r in results.values() if r["error"] is not None and r.get("_retried", 0) < max_chunk_retries]
                if not failed_tasks:
                    break
                retry_count += 1
                _log("warn", f"  开始第 {retry_count} 轮重试，{len(failed_tasks)} 个 chunk 待重试")
                state["chunk_retries"] = retry_count
                run_retry_batch(failed_tasks, retry_count)
                if _job_cancelled.is_set():
                    break
            if not (dry_run or pipeline.config.parallel_workers <= 1 or len(tasks) == 1):
                with ThreadPoolExecutor(max_workers=pipeline.config.parallel_workers) as executor:
                    future_map = {
                        executor.submit(pipeline.extract_chunk_payload, task, False): task
                        for task in tasks
                    }
                    _log("info", f"  [并行] 已提交 {len(tasks)} 个 chunk 到线程池，parallel_workers={pipeline.config.parallel_workers}")
                    for future in as_completed(future_map):
                        if _job_cancelled.is_set():
                            note_cancelling()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        task = future_map[future]
                        state["current_chapter"] = task.chapter_name
                        try:
                            payload = future.result()
                            error = None
                            if task.chunk_index == 1:
                                _log("info", f"  chunk1结果 payload_keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)} triples={len(payload.get('triples',[])) if isinstance(payload,dict) else 'N/A'}")
                        except Exception as exc:
                            payload = {"triples": []}
                            error = str(exc)
                            chunk_errors += 1
                            state["chunk_errors"] = chunk_errors
                            _log("error", f"  chunk {task.chunk_index} 失败: {str(exc)[:80]}")
                        rows, effective_error = _evaluate_chunk_attempt(
                            pipeline,
                            task=task,
                            payload=payload,
                            error=error,
                        )
                        results[task.sequence] = {
                            "task": task,
                            "payload": payload,
                            "error": effective_error,
                            "rows": rows,
                            "_retried": 0,
                        }
                        if error is None and effective_error is not None:
                            results[task.sequence]["_written"] = False
                            _log("warn", f"  chunk {task.chunk_index} low_yield | triples={len(rows)} | queued_for_retry")
                        if effective_error is None:
                            for row in rows:
                                pipeline.append_jsonl(triples_jsonl, asdict(row))
                            results[task.sequence]["_written"] = True
                        if error is not None:
                            results[task.sequence]["_written"] = False
                            _log("warn", f"  chunk {task.chunk_index} 无三元组 | error={error} | is_dict={isinstance(payload,dict)}")
                        if effective_error is None:
                            total_triples += len(rows)
                            state["total_triples"] = total_triples
                        if effective_error is None:
                            completed_chunk_keys.add((task.book_name, task.chunk_index))
                        pipeline.append_jsonl(
                            raw_jsonl,
                            _build_raw_chunk_record(
                                task=task,
                                payload=payload,
                                error=effective_error,
                                rows_count=len(rows),
                            ),
                        )
                        _append_checkpoint(
                            checkpoint_path,
                            task=task,
                            error=effective_error,
                            payload=payload,
                            attempt=0,
                            resumed=resume_mode,
                            triples_count=len(rows),
                        )
                        total_chunks_done += 1
                        session_chunks_done += 1
                        _update_runtime_metrics(
                            state,
                            start_ts=start_ts,
                            session_chunks_done=session_chunks_done,
                            total_chunks_done=total_chunks_done,
                            total_chunks_all=total_chunks_all,
                        )
                        book_chunks_done = len(results)
                        _log(
                            "info",
                            f"  [parallel] progress {book_chunks_done}/{len(tasks)} | chunk={task.chunk_index} | "
                            f"triples={len(rows)} | total_triples={total_triples} | error={effective_error or '-'}",
                        )
                        with _run_lock:
                            _current_job.update(state)
                        _write_state(state_path, state)
                if _job_cancelled.is_set():
                    note_cancelling()

                # Retry failed chunks (parallel path)
                retry_count = 0
                while retry_count < max_chunk_retries:
                    if _job_cancelled.is_set():
                        note_cancelling()
                        break
                    failed_tasks = [r for r in results.values() if r["error"] is not None and r.get("_retried", 0) < max_chunk_retries]
                    if not failed_tasks:
                        break
                    retry_count += 1
                    _log("warn", f"  开始第 {retry_count} 轮重试，{len(failed_tasks)} 个 chunk 待重试")
                    state["chunk_retries"] = retry_count
                    run_retry_batch(failed_tasks, retry_count)
                    if _job_cancelled.is_set():
                        break

            # 按序收集 all_rows（triples_jsonl 已在 per-chunk 循环中实时写入，不再重复 normalize_triples）
            book_triples = 0
            for task in tasks:
                result = results.get(task.sequence, {"task": task, "payload": {"triples": []}, "error": "missing", "rows": []})
                rows = result.get("rows") or []
                if result.get("error") is not None:
                    continue
                book_triples += len(rows)
                all_rows.extend(rows)
            # 仅当该书所有调度 chunk 都已有成功 checkpoint，才标记为已完成
            book_all_completed = bool(scheduled_tasks) and all(
                (task.book_name, task.chunk_index) in completed_chunk_keys
                for task in scheduled_tasks
            )
            if book_all_completed:
                state["books_completed"] = book_index
            with _run_lock:
                _current_job.update(state)
            _log("info", f"  完成 {book_path.stem}，累计三元组: {total_triples}")
            if _job_cancelled.is_set():
                note_cancelling()
                break

        # ── 写出 CSV + graph_import ─────────────────────────────────────
        pipeline.write_csv(run_dir / "triples.normalized.csv", all_rows)
        pipeline.write_graph_import(run_dir / "graph_import.json", all_rows)

        was_cancelled = _job_cancelled.is_set() or state.get("status") == "cancelling"
        state["phase"] = "done"
        if was_cancelled:
            state["status"] = "cancelled"
        else:
            state["status"] = "completed"
        state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        state["elapsed_secs"] = int(time.time() - start_ts)
        state["eta"] = "已取消" if was_cancelled else "完成"
        state["total_triples"] = total_triples
        with _run_lock:
            _current_job.update(state)
        _write_state(state_path, state)
        if was_cancelled:
            _log("warn", f"任务已取消，已保留当前进度：{total_triples} 条三元组，错误 {chunk_errors} 个")
        else:
            _log("info", f"提取完成，共 {total_triples} 条三元组，错误 {chunk_errors} 个")

        # ── 可选：自动清洗 ──────────────────────────────────────────────
        if auto_clean and state.get("status") == "completed":
            if not triples_jsonl.exists() or triples_jsonl.stat().st_size == 0:
                _log("warn", f"跳过清洗: {triples_jsonl} 为空或不存在（{total_triples} 条三元组）")
            else:
                state["phase"] = "cleaning"
                with _run_lock:
                    _current_job.update(state)
                _log("info", "开始自动清洗...")
                report = pipeline.clean_run_dir(run_dir)
                _log("info", f"清洗完成: 保留 {report['kept_total']} 条，丢弃 {report['dropped_total']} 条")

        # ── 可选：自动发布 ──────────────────────────────────────────────
        if auto_publish and state.get("status") == "completed":
            state["phase"] = "publishing"
            with _run_lock:
                _current_job.update(state)
            _log("info", "开始自动发布到图谱...")
            target = pipeline.publish_graph(run_dir=run_dir)
            graph_data = json.loads(target.read_text(encoding="utf-8"))
            evidence_path = target.parent / f"{target.stem}.evidence.jsonl"
            evidence_count = 0
            if evidence_path.exists():
                evidence_count = sum(1 for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip())
            _record_json_publish_status(
                run_dir,
                target=target,
                graph_triples=len(graph_data),
                evidence_count=evidence_count,
            )
            _log("info", f"发布完成: {target}")

        state["phase"] = "finished"
        with _run_lock:
            _current_job.update(state)
            _job_log_file = None
            try:
                if _job_log_file_path and _job_log_file_path.exists():
                    _job_log_file_path.unlink()
            except Exception:
                pass
        _write_state(state_path, state)

    except Exception as exc:
        state["status"] = "error"
        state["error"] = str(exc)
        state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        with _run_lock:
            _current_job.update(state)
            _job_log_file = None
            try:
                if _job_log_file_path and _job_log_file_path.exists():
                    _job_log_file_path.unlink()
            except Exception:
                pass
        _log("error", f"任务异常: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# API 模型
# ─────────────────────────────────────────────────────────────────────────────

class APIConfig(BaseModel):
    model: str = Field(default="", description="LLM 模型名")
    api_key: str = Field(default="", description="API Key")
    base_url: str = Field(default="", description="API Base URL")
    request_timeout: float = Field(default=90.0)
    max_retries: int = Field(default=2)
    request_delay: float = Field(default=0.8)
    retry_backoff_base: float = Field(default=2.0)
    parallel_workers: int = Field(default=4)
    max_chunk_chars: int = Field(default=800)
    chunk_overlap: int = Field(default=200)
    chunk_strategy: str = Field(default="body_first")
    max_chunk_retries: int = Field(default=2, description="Chunk 失败后最大重试次数")


class StartJobRequest(BaseModel):
    selected_books: list[str] = Field(default=[], description="书名关键词或序号列表")
    label: str = Field(default="", description="任务标签")
    dry_run: bool = Field(default=False)
    chapter_excludes: list[str] = Field(default=[])
    max_chunks_per_book: int | None = Field(default=None)
    skip_initial_chunks: int = Field(default=0)
    chunk_strategy: str = Field(default="body_first")
    auto_clean: bool = Field(default=True)
    auto_publish: bool = Field(default=False)
    api_config: APIConfig = Field(default_factory=APIConfig)


class ResumeRunRequest(BaseModel):
    auto_clean: bool = Field(default=False)
    auto_publish: bool = Field(default=False)
    api_config: APIConfig = Field(default_factory=APIConfig)


# ─────────────────────────────────────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/books")
def list_books():
    """列出所有书目"""
    try:
        pipeline = _build_pipeline()
        books = pipeline.discover_books()
        recommended = {str(p) for p in pipeline.recommend_books(limit=12)}
        result = []
        for i, b in enumerate(books, start=1):
            size_kb = round(b.stat().st_size / 1024, 1)
            result.append({
                "index": i,
                "name": b.stem,
                "path": str(b),
                "size_kb": size_kb,
                "recommended": str(b) in recommended,
            })
        return {"books": result, "total": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/books/{book_name}/chapters")
def list_chapters(book_name: str, limit: int = 50):
    """查看某本书的章节"""
    try:
        pipeline = _build_pipeline()
        books = pipeline.discover_books()
        matched = [b for b in books if book_name in b.stem]
        if not matched:
            raise HTTPException(status_code=404, detail="book_not_found")
        sections = pipeline.split_book(matched[0])[:limit]
        return {
            "book": matched[0].stem,
            "total_sections": len(sections),
            "sections": [{"title": s["title"], "chars": len(s["content"])} for s in sections],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/job/start")
def start_job(req: StartJobRequest):
    """启动一次提取任务"""
    global _job_thread, _current_job, _job_log

    with _run_lock:
        if _current_job.get("status") == "running":
            raise HTTPException(status_code=409, detail="已有任务运行中，请等待完成或先取消")

    # 解析书目
    pipeline = _build_pipeline(req.api_config.model_dump())
    selected = _resolve_start_selected_books(pipeline, req.selected_books)
    auto_skipped_processed_books: list[str] = []
    if not req.selected_books:
        selected, auto_skipped_processed_books = _exclude_processed_books_for_new_run(selected)

    if not selected:
        detail = "没有剩余未处理书籍；如需重跑历史书籍，请手动选择具体书目"
        raise HTTPException(status_code=400, detail=detail)

    if not req.dry_run:
        api_key = req.api_config.api_key or _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="未配置 API Key，请在 API 配置中填写或在 .env 中设置 TRIPLE_LLM_API_KEY")

    job_id = str(uuid4())[:8]
    with _run_lock:
        _current_job = {}
        _job_log.clear()
        _job_cancelled.clear()
        log_file_path = DEFAULT_OUTPUT_DIR / f"current_job_{job_id}.log"
        log_file_path.write_text("", encoding="utf-8")
        global _job_log_file, _job_log_file_path
        _job_log_file = log_file_path
        _job_log_file_path = log_file_path

    _job_thread = threading.Thread(
        target=_run_extraction_job,
        kwargs=dict(
            job_id=job_id,
            selected_books=selected,
            label=req.label or "extraction",
            dry_run=req.dry_run,
            cfg_override=req.api_config.model_dump(),
            chapter_excludes=req.chapter_excludes,
            max_chunks_per_book=req.max_chunks_per_book,
            skip_initial_chunks=req.skip_initial_chunks,
            chunk_strategy=req.chunk_strategy,
            auto_clean=req.auto_clean,
            auto_publish=req.auto_publish,
            max_chunk_retries=req.api_config.max_chunk_retries,
        ),
        daemon=True,
    )
    _job_thread.start()
    return {
        "job_id": job_id,
        "selected_books": [b.stem for b in selected],
        "auto_skipped_processed_books": auto_skipped_processed_books,
        "message": "任务已启动",
    }


@app.post("/api/runs/{run_name}/resume")
def resume_run(run_name: str, req: ResumeRunRequest):
    global _job_thread, _current_job, _job_log

    with _run_lock:
        if _current_job.get("status") == "running":
            raise HTTPException(status_code=409, detail="existing_job_running")

    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    manifest = _load_json_file(run_dir / "manifest.json", {})
    selected = [Path(item) for item in manifest.get("books", []) if str(item).strip()]
    selected = [path for path in selected if path.exists()]
    if not selected:
        raise HTTPException(status_code=400, detail="run_books_not_found")

    cfg_override = dict(manifest.get("config", {}))
    if manifest.get("model"):
        cfg_override["model"] = manifest.get("model")
    if manifest.get("base_url"):
        cfg_override["base_url"] = manifest.get("base_url")
    for key, value in req.api_config.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            if value.strip():
                cfg_override[key] = value
        elif value is not None:
            cfg_override[key] = value

    dry_run = bool(manifest.get("dry_run", False))
    if not dry_run:
        api_key = cfg_override.get("api_key") or _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="missing_llm_api_key")

    manifest_cfg = manifest.get("config", {})
    job_id = str(uuid4())[:8]
    with _run_lock:
        _current_job = {}
        _job_log.clear()
        _job_cancelled.clear()
        log_file_path = DEFAULT_OUTPUT_DIR / f"current_job_{job_id}.log"
        log_file_path.write_text("", encoding="utf-8")
        global _job_log_file, _job_log_file_path
        _job_log_file = log_file_path
        _job_log_file_path = log_file_path

    _job_thread = threading.Thread(
        target=_run_extraction_job,
        kwargs=dict(
            job_id=job_id,
            selected_books=selected,
            label=run_name,
            dry_run=dry_run,
            cfg_override=cfg_override,
            chapter_excludes=list(manifest_cfg.get("chapter_excludes", [])),
            max_chunks_per_book=manifest_cfg.get("max_chunks_per_book"),
            skip_initial_chunks=int(manifest_cfg.get("skip_initial_chunks_per_book", 0) or 0),
            chunk_strategy=str(manifest_cfg.get("chunk_strategy", "body_first")),
            auto_clean=req.auto_clean,
            auto_publish=req.auto_publish,
            max_chunk_retries=int(cfg_override.get("max_chunk_retries", req.api_config.max_chunk_retries)),
            resume_run_dir=run_dir,
        ),
        daemon=True,
    )
    _job_thread.start()
    return {"job_id": job_id, "run_dir": run_name, "selected_books": [b.stem for b in selected], "message": "resume_started"}


@app.post("/api/job/cancel")
def cancel_job():
    """取消当前运行中的任务"""
    already_set = _job_cancelled.is_set()
    _job_cancelled.set()
    if not already_set:
        _mark_cancel_requested()
        _log("warn", "收到用户取消请求")
    return {"message": "取消信号已发送", "status": "cancelling" if _current_job else "idle"}


@app.get("/api/job/status")
def job_status():
    """获取当前任务状态快照"""
    with _run_lock:
        return dict(_current_job)


@app.get("/api/job/log")
def job_log(since: int = 0):
    """获取日志（since=起始序号）"""
    with _run_lock:
        entries = _job_log[since:]
    return {"entries": entries, "total": len(_job_log)}


@app.get("/api/job/stream")
async def job_stream():
    """SSE 实时推送状态 + 日志"""
    async def generator():
        sent_log_idx = 0
        replayed_from_disk = False
        while True:
            with _run_lock:
                state = dict(_current_job)
                # Replay from disk log file on first fetch (handles page refresh reconnect)
                if not replayed_from_disk and _job_log_file is not None and _job_log_file.exists():
                    try:
                        disk_lines = _job_log_file.read_text(encoding="utf-8").splitlines()
                        existing_logs = [json.loads(line) for line in disk_lines if line.strip()]
                        if existing_logs and len(existing_logs) > sent_log_idx:
                            new_logs = existing_logs[sent_log_idx:]
                            sent_log_idx = len(existing_logs)
                    except Exception:
                        pass
                    replayed_from_disk = True
                new_logs = _job_log[sent_log_idx:]
                sent_log_idx += len(new_logs)
            payload = json.dumps({
                "state": state,
                "logs": new_logs,
            }, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            if state.get("status") in ("completed", "error", "cancelled") and state.get("phase") == "finished":
                break
            await asyncio.sleep(1.0)
    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/api/runs")
def list_runs():
    """列出历史运行记录"""
    output_dir = DEFAULT_OUTPUT_DIR
    if not output_dir.exists():
        return {"runs": []}
    runs = sorted((p for p in output_dir.iterdir() if p.is_dir()), reverse=True)
    result = []
    for run_dir in runs[:20]:
        state_path = run_dir / "state.json"
        manifest_path = run_dir / "manifest.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        publish_status = _load_publish_status(run_dir)
        result.append({
            "run_dir": run_dir.name,
            "status": state.get("status", "unknown"),
            "books_total": state.get("books_total", 0),
            "books_completed": state.get("books_completed", 0),
            "total_triples": state.get("total_triples", 0),
            "chunk_errors": state.get("chunk_errors", 0),
            "model": manifest.get("model", ""),
            "created_at": manifest.get("created_at", ""),
            "dry_run": manifest.get("dry_run", False),
            "publish_status": publish_status,
        })
    return {"runs": result}


@app.get("/api/runs/{run_name}/resume-config")
def run_resume_config(run_name: str):
    """返回指定 run 的续跑默认配置。"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    manifest = _load_json_file(run_dir / "manifest.json", {})
    state = _load_json_file(run_dir / "state.json", {})
    manifest_cfg = manifest.get("config", {}) if isinstance(manifest.get("config", {}), dict) else {}

    return {
        "run_dir": run_name,
        "status": state.get("status", "unknown"),
        "dry_run": bool(manifest.get("dry_run", False)),
        "progress": {
            "chunks_completed": int(state.get("chunks_completed", 0) or 0),
            "chunks_total": int(state.get("chunks_total", 0) or 0),
            "books_completed": int(state.get("books_completed", 0) or 0),
            "books_total": int(state.get("books_total", 0) or 0),
            "total_triples": int(state.get("total_triples", 0) or 0),
            "chunk_errors": int(state.get("chunk_errors", 0) or 0),
        },
        "api_config": {
            "model": str(manifest.get("model", "") or ""),
            "base_url": str(manifest.get("base_url", "") or ""),
            "request_timeout": float(manifest_cfg.get("request_timeout", 90.0) or 90.0),
            "max_retries": int(manifest_cfg.get("max_retries", 2) or 2),
            "request_delay": float(manifest_cfg.get("request_delay", 0.8) or 0.8),
            "retry_backoff_base": float(manifest_cfg.get("retry_backoff_base", 2.0) or 2.0),
            "parallel_workers": int(manifest_cfg.get("parallel_workers", 4) or 4),
            "max_chunk_retries": int(manifest_cfg.get("max_chunk_retries", 2) or 2),
        },
        "notes": {
            "publish_json": "append_graph_runtime_json",
            "publish_nebula": "append_graph_runtime_json_then_write_nebulagraph",
            "resume_safe_fields": [
                "model",
                "base_url",
                "api_key",
                "request_timeout",
                "max_retries",
                "request_delay",
                "retry_backoff_base",
                "parallel_workers",
                "max_chunk_retries",
                "auto_clean",
                "auto_publish",
            ],
            "resume_fixed_fields": [
                "chapter_excludes",
                "skip_initial_chunks_per_book",
                "chunk_strategy",
                "max_chunk_chars",
                "chunk_overlap",
                "max_chunks_per_book",
            ],
        },
    }


@app.get("/api/runs/{run_name}/triples")
def run_triples(run_name: str, limit: int = 50):
    """查看某次运行的三元组样本"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    # 优先用 cleaned，没有则用 normalized
    jsonl = run_dir / "triples.cleaned.jsonl"
    source_kind = "cleaned"
    if not jsonl.exists():
        jsonl = run_dir / "triples.normalized.jsonl"
        source_kind = "normalized"
    rows = []
    if jsonl.exists():
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
                if len(rows) >= limit:
                    break
    return {"run_dir": run_name, "rows": rows, "count": len(rows), "source_kind": source_kind, "source_path": str(jsonl)}


@app.post("/api/runs/{run_name}/clean")
def run_clean(run_name: str):
    """清洗指定运行"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        pipeline = _build_pipeline()
        report = pipeline.clean_run_dir(run_dir)
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_name}/publish")
def run_publish(run_name: str, replace: bool = False):
    """将指定运行发布到 graph_runtime.json"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        pipeline = _build_pipeline()
        target = pipeline.publish_graph(run_dir=run_dir, replace=replace)
        # 统计发布后图谱大小
        graph_data = json.loads(target.read_text(encoding="utf-8"))
        evidence_path = target.parent / f"{target.stem}.evidence.jsonl"
        evidence_count = 0
        if evidence_path.exists():
            evidence_count = sum(1 for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip())
        _record_json_publish_status(
            run_dir,
            target=target,
            graph_triples=len(graph_data),
            evidence_count=evidence_count,
        )
        return {
            "target": str(target),
            "graph_triples": len(graph_data),
            "evidence_count": evidence_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/runs/{run_name}/publish-status")
def run_publish_status(run_name: str):
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    return {
        "run_dir": run_name,
        "publish_status": _load_publish_status(run_dir),
    }


@app.post("/api/runs/{run_name}/publish-nebula")
def run_publish_nebula(run_name: str):
    """将指定运行增量发布到 NebulaGraph（异步启动，可轮询进度）"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    with _publish_lock:
        existing_thread = _nebula_publish_threads.get(run_name)
        already_running = existing_thread is not None and existing_thread.is_alive()
    if already_running:
        return JSONResponse(
            status_code=202,
            content={
                "run_dir": run_name,
                "started": False,
                "publish_status": _load_publish_status(run_dir),
            },
        )

    _update_publish_status(
        run_dir,
        "nebula",
        {
            "status": "running",
            "published": False,
            "started_at": _now_iso(),
            "finished_at": "",
            "published_at": "",
            "progress_current": 0,
            "progress_total": 0,
            "progress_pct": 0.0,
            "ok_count": 0,
            "fail_count": 0,
            "error": "",
        },
    )
    worker = threading.Thread(target=_run_nebula_publish_job, args=(run_name,), daemon=True)
    with _publish_lock:
        _nebula_publish_threads[run_name] = worker
    worker.start()
    return JSONResponse(
        status_code=202,
        content={
            "run_dir": run_name,
            "started": True,
            "publish_status": _load_publish_status(run_dir),
        },
    )


@app.get("/api/graph/stats")
def graph_stats():
    """当前 graph_runtime.json 的统计信息"""
    try:
        target = DEFAULT_GRAPH_TARGET
        if not target.exists():
            return {"exists": False}
        data = json.loads(target.read_text(encoding="utf-8"))
        evidence_path = target.parent / f"{target.stem}.evidence.jsonl"
        evidence_count = 0
        if evidence_path.exists():
            evidence_count = sum(1 for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip())
        predicates: dict[str, int] = {}
        books: dict[str, int] = {}
        for row in data:
            p = row.get("predicate", "")
            b = row.get("source_book", "")
            predicates[p] = predicates.get(p, 0) + 1
            books[b] = books.get(b, 0) + 1
        return {
            "exists": True,
            "total_triples": len(data),
            "evidence_count": evidence_count,
            "predicate_dist": sorted(predicates.items(), key=lambda x: -x[1])[:15],
            "book_dist": sorted(books.items(), key=lambda x: -x[1])[:10],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/config/env")
def get_env_config():
    """返回当前从环境变量读取的配置（隐藏 key）"""
    model = _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="deepseek-ai/DeepSeek-V3.2")
    base_url = _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    return {
        "model": model,
        "base_url": base_url,
        "api_key_set": bool(api_key),
        "api_key_hint": (api_key[:4] + "..." + api_key[-4:]) if len(api_key) > 8 else ("已设置" if api_key else "未设置"),
    }


@app.post("/api/job/test-call")
def test_api_call(req: StartJobRequest):
    """诊断接口：拿第一本书的第一个 chunk 测试 API，返回原始 LLM 响应和解析结果"""
    try:
        pipeline = _build_pipeline(req.api_config.model_dump())
        books = pipeline.discover_books()
        if not books:
            raise HTTPException(status_code=400, detail="没有可用的书籍")
        tasks = pipeline.schedule_book_chunks(
            book_path=books[0],
            chapter_excludes=req.chapter_excludes or None,
            max_chunks_per_book=1,
            skip_initial_chunks_per_book=0,
            chunk_strategy=req.chunk_strategy or "body_first",
        )
        if not tasks:
            raise HTTPException(status_code=400, detail="该书没有可处理的 chunk")
        task = tasks[0]

        # 调用 LLM
        import httpx
        url = f"{pipeline.config.base_url.rstrip('/')}/chat/completions"
        prompt = pipeline.build_prompt(
            book_name=task.book_name,
            chapter_name=task.chapter_name,
            text_chunk=task.text_chunk,
        )
        payload = {
            "model": pipeline.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {pipeline.config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            raw_body = resp.json()

        # 解析响应
        from scripts.tcm_triple_console import _extract_json_block
        choices = raw_body.get("choices", [])
        raw_content = choices[0].get("message", {}).get("content", "") if choices else ""
        try:
            parsed = _extract_json_block(str(raw_content))
        except Exception as parse_exc:
            parsed = {"_parse_error": str(parse_exc), "_raw": str(raw_content)[:500]}

        triples_normalized = pipeline.normalize_triples(
            payload=parsed if isinstance(parsed, dict) else {"triples": parsed if isinstance(parsed, list) else []},
            book_name=task.book_name,
            chapter_name=task.chapter_name,
        )

        return {
            "book": task.book_name,
            "chapter": task.chapter_name,
            "chunk_chars": len(task.text_chunk),
            "model": pipeline.config.model,
            "base_url": pipeline.config.base_url,
            "api_key_prefix": (pipeline.config.api_key[:4] + "...") if len(pipeline.config.api_key) > 4 else pipeline.config.api_key,
            "raw_response_length": len(str(raw_content)),
            "raw_response_preview": str(raw_content)[:300],
            "parsed_triples_count": len(triples_normalized),
            "parsed_sample": [{"subject": r.subject, "predicate": r.predicate, "object": r.object} for r in triples_normalized[:3]],
            "status_code": resp.status_code,
        }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"API 返回错误 {exc.response.status_code}: {exc.response.text[:300]}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 内嵌前端（单文件 SPA）
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = _SCRIPTS_DIR / "pipeline_console.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>pipeline_console.html not found</h1>")


# ─────────────────────────────────────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="TCM Triple Pipeline Console Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7800)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"🚀 TCM Pipeline Console 启动中...")
    print(f"   访问地址: http://{args.host}:{args.port}")
    print(f"   书库路径: {DEFAULT_BOOKS_DIR}")
    print(f"   输出目录: {DEFAULT_OUTPUT_DIR}")
    print(f"   图谱目标: {DEFAULT_GRAPH_TARGET}")
    uvicorn.run(
        "scripts.pipeline_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(_BACKEND_DIR),
    )
