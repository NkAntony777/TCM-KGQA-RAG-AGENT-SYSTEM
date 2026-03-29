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


def _log(level: str, msg: str, **extra: Any) -> None:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "msg": msg, **extra}
    with _run_lock:
        _job_log.append(entry)
        if _job_log_file is not None:
            _job_log_file.write_text(
                json.dumps(entry, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _build_pipeline(cfg_override: dict[str, Any] | None = None) -> TCMTriplePipeline:
    cfg = cfg_override or {}
    model = cfg.get("model") or _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="deepseek-ai/DeepSeek-V3.2")
    api_key = cfg.get("api_key") or _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
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


def _get_processed_book_stems() -> set[str]:
    """扫描所有历史 run 目录的 manifest.json，收集已处理过的书名 stems。"""
    processed: set[str] = set()
    output_dir = DEFAULT_OUTPUT_DIR
    if not output_dir.exists():
        return processed
    for run_dir in output_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for book_str in manifest.get("books", []):
                processed.add(Path(book_str).stem)
        except Exception:
            pass
    return processed


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
) -> None:
    """在独立线程中运行完整的提取→清洗→发布流程，实时更新 _current_job。"""
    global _current_job

    pipeline = _build_pipeline(cfg_override)
    run_dir = pipeline.create_run_dir(label=label)

    start_ts = time.time()
    total_chunks_done = 0
    total_chunks_all = 0
    total_triples = 0
    chunk_errors = 0

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
    }
    with _run_lock:
        _current_job.update(state)

    _log("info", f"任务启动 job_id={job_id}，共 {len(selected_books)} 本书")

    # 保存 manifest
    pipeline.save_manifest(run_dir, {
        "job_id": job_id,
        "created_at": datetime.now().isoformat(),
        "books": [str(p) for p in selected_books],
        "model": pipeline.config.model,
        "base_url": pipeline.config.base_url,
        "dry_run": dry_run,
        "config": {
            "max_chunk_chars": pipeline.config.max_chunk_chars,
            "chunk_overlap": pipeline.config.chunk_overlap,
            "chapter_excludes": chapter_excludes,
            "skip_initial_chunks_per_book": skip_initial_chunks,
            "chunk_strategy": chunk_strategy,
            "parallel_workers": pipeline.config.parallel_workers,
        },
    })

    triples_jsonl = run_dir / "triples.normalized.jsonl"
    raw_jsonl = run_dir / "triples.raw.jsonl"
    state_path = run_dir / "state.json"
    all_rows = []

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
        state["phase"] = "extracting"
        with _run_lock:
            _current_job.update(state)
        _log("info", f"调度完成，共 {total_chunks_all} 个 chunk")

        # ── 第二阶段：逐书提取 ──────────────────────────────────────────
        for book_index, (book_path, tasks) in enumerate(all_tasks_per_book, start=1):
            if _job_cancelled.is_set():
                state["status"] = "cancelled"
                _log("warn", "任务被用户取消")
                break

            state["current_book"] = book_path.stem
            state["books_completed"] = book_index - 1
            with _run_lock:
                _current_job.update(state)
            _log("info", f"开始处理 [{book_index}/{len(selected_books)}] {book_path.stem}，{len(tasks)} chunks")

            if not tasks:
                state["books_completed"] = book_index
                with _run_lock:
                    _current_job.update(state)
                _log("warn", f"{book_path.stem} 无可处理 chunk（全部被过滤）")
                continue

            results: dict[int, dict[str, Any]] = {}

            if dry_run or pipeline.config.parallel_workers <= 1 or len(tasks) == 1:
                for task in tasks:
                    if _job_cancelled.is_set():
                        break
                    state["current_chapter"] = task.chapter_name
                    with _run_lock:
                        _current_job.update(state)
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
                    results[task.sequence] = {"task": task, "payload": payload, "error": error, "_retried": 0}
                    # Real-time triple counting per chunk
                    rows = pipeline.normalize_triples(payload=payload, book_name=task.book_name, chapter_name=task.chapter_name)
                    if rows:
                        for row in rows:
                            pipeline.append_jsonl(triples_jsonl, asdict(row))
                        result["_written"] = True
                    else:
                        result["_written"] = result.get("_written", False)
                        _log("debug", f"  chunk {task.chunk_index} 无可抽取三元组（原文可能不包含知识关系）")
                    total_triples += len(rows)
                    state["total_triples"] = total_triples
                    if error is None:
                        pipeline.append_jsonl(raw_jsonl, {"book": task.book_name, "chapter": task.chapter_name, "chunk_index": task.chunk_index, "payload": payload})
                    total_chunks_done += 1
                    state["chunks_completed"] = total_chunks_done
                    elapsed = time.time() - start_ts
                    state["elapsed_secs"] = int(elapsed)
                    if total_chunks_done > 0 and total_chunks_all > 0:
                        rate = total_chunks_done / max(elapsed, 1)
                        remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
                        state["eta"] = _fmt_eta(remaining)
                        state["speed_chunks_per_min"] = round(rate * 60, 1)
                    with _run_lock:
                        _current_job.update(state)

            # Retry failed chunks (serial path)
            retry_count = 0
            while retry_count < max_chunk_retries:
                failed_tasks = [r for r in results.values() if r["error"] is not None and r.get("_retried", 0) < max_chunk_retries]
                if not failed_tasks:
                    break
                retry_count += 1
                _log("warn", f"  开始第 {retry_count} 轮重试，{len(failed_tasks)} 个 chunk 待重试")
                state["chunk_retries"] = retry_count
                for result in failed_tasks:
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
                        result["payload"] = {"triples": []}
                        result["error"] = str(exc)
                        _log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
                    # Real-time triple counting per chunk (retry: only write if not yet written)
                    if not result.get("_written"):
                        rows = pipeline.normalize_triples(payload=payload, book_name=task.book_name, chapter_name=task.chapter_name)
                        if rows:
                            for row in rows:
                                pipeline.append_jsonl(triples_jsonl, asdict(row))
                            result["_written"] = True
                        total_triples += len(rows)
                        state["total_triples"] = total_triples
                    pipeline.append_jsonl(raw_jsonl, {"book": task.book_name, "chapter": task.chapter_name, "chunk_index": task.chunk_index, "payload": payload})
                    total_chunks_done += 1
                    state["chunks_completed"] = total_chunks_done
                    elapsed = time.time() - start_ts
                    state["elapsed_secs"] = int(elapsed)
                    if total_chunks_done > 0 and total_chunks_all > 0:
                        rate = total_chunks_done / max(elapsed, 1)
                        remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
                        state["eta"] = _fmt_eta(remaining)
                        state["speed_chunks_per_min"] = round(rate * 60, 1)
                    with _run_lock:
                        _current_job.update(state)
            else:
                with ThreadPoolExecutor(max_workers=pipeline.config.parallel_workers) as executor:
                    future_map = {
                        executor.submit(pipeline.extract_chunk_payload, task, False): task
                        for task in tasks
                    }
                    for future in as_completed(future_map):
                        if _job_cancelled.is_set():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        task = future_map[future]
                        state["current_chapter"] = task.chapter_name
                        try:
                            payload = future.result()
                            error = None
                            _log("ok", f"  chunk {task.chunk_index} ✓ {task.chapter_name[:30]}")
                        except Exception as exc:
                            payload = {"triples": []}
                            error = str(exc)
                            chunk_errors += 1
                            state["chunk_errors"] = chunk_errors
                            _log("error", f"  chunk {task.chunk_index} 失败: {str(exc)[:80]}")
                        results[task.sequence] = {"task": task, "payload": payload, "error": error, "_retried": 0}
                        # Real-time triple counting per chunk
                        rows = pipeline.normalize_triples(payload=payload, book_name=task.book_name, chapter_name=task.chapter_name)
                        if rows:
                            for row in rows:
                                pipeline.append_jsonl(triples_jsonl, asdict(row))
                            results[task.sequence]["_written"] = True
                        else:
                            results[task.sequence]["_written"] = False
                        total_triples += len(rows)
                        state["total_triples"] = total_triples
                        if error is None:
                            pipeline.append_jsonl(raw_jsonl, {"book": task.book_name, "chapter": task.chapter_name, "chunk_index": task.chunk_index, "payload": payload})
                        total_chunks_done += 1
                        state["chunks_completed"] = total_chunks_done
                        elapsed = time.time() - start_ts
                        state["elapsed_secs"] = int(elapsed)
                        if total_chunks_done > 0 and total_chunks_all > 0:
                            rate = total_chunks_done / max(elapsed, 1)
                            remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
                            state["eta"] = _fmt_eta(remaining)
                            state["speed_chunks_per_min"] = round(rate * 60, 1)
                        with _run_lock:
                            _current_job.update(state)

                # Retry failed chunks (parallel path)
                retry_count = 0
                while retry_count < max_chunk_retries:
                    failed_tasks = [r for r in results.values() if r["error"] is not None and r.get("_retried", 0) < max_chunk_retries]
                    if not failed_tasks:
                        break
                    retry_count += 1
                    _log("warn", f"  开始第 {retry_count} 轮重试，{len(failed_tasks)} 个 chunk 待重试")
                    state["chunk_retries"] = retry_count
                    for result in failed_tasks:
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
                            result["payload"] = {"triples": []}
                            result["error"] = str(exc)
                            _log("error", f"  chunk {task.chunk_index} 重试仍失败: {str(exc)[:80]}")
                        # Real-time triple counting per chunk (parallel retry: only write if not yet written)
                        if not result.get("_written"):
                            rows = pipeline.normalize_triples(payload=payload, book_name=task.book_name, chapter_name=task.chapter_name)
                            if rows:
                                for row in rows:
                                    pipeline.append_jsonl(triples_jsonl, asdict(row))
                                result["_written"] = True
                            total_triples += len(rows)
                            state["total_triples"] = total_triples
                        pipeline.append_jsonl(raw_jsonl, {"book": task.book_name, "chapter": task.chapter_name, "chunk_index": task.chunk_index, "payload": payload})
                        total_chunks_done += 1
                        state["chunks_completed"] = total_chunks_done
                        elapsed = time.time() - start_ts
                        state["elapsed_secs"] = int(elapsed)
                        if total_chunks_done > 0 and total_chunks_all > 0:
                            rate = total_chunks_done / max(elapsed, 1)
                            remaining = max(0, (total_chunks_all - total_chunks_done) / rate)
                            state["eta"] = _fmt_eta(remaining)
                            state["speed_chunks_per_min"] = round(rate * 60, 1)
                        with _run_lock:
                            _current_job.update(state)

            # 按序收集 all_rows（triples_jsonl 已在 per-chunk 循环中实时写入，不再重复 normalize_triples）
            book_triples = 0
            for task in tasks:
                result = results.get(task.sequence, {"task": task, "payload": {"triples": []}, "error": "missing"})
                payload = result["payload"]
                rows = pipeline.normalize_triples(
                    payload=payload, book_name=task.book_name, chapter_name=task.chapter_name
                )
                book_triples += len(rows)
                all_rows.extend(rows)
            # 只有实际贡献了三元组的书才标记为已处理
            if book_triples > 0:
                state["books_completed"] = book_index
            with _run_lock:
                _current_job.update(state)
            _log("info", f"  完成 {book_path.stem}，累计三元组: {total_triples}")

        # ── 写出 CSV + graph_import ─────────────────────────────────────
        pipeline.write_csv(run_dir / "triples.normalized.csv", all_rows)
        pipeline.write_graph_import(run_dir / "graph_import.json", all_rows)

        state["phase"] = "done"
        if state.get("status") != "cancelled":
            state["status"] = "completed"
        state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        state["elapsed_secs"] = int(time.time() - start_ts)
        state["eta"] = "完成"
        state["total_triples"] = total_triples
        with _run_lock:
            _current_job.update(state)
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
    books = pipeline.discover_books()
    selected: list[Path] = []
    if req.selected_books:
        for token in req.selected_books:
            token = token.strip()
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(books):
                    selected.append(books[idx - 1])
            else:
                selected.extend([b for b in books if token in b.stem])
        # 去重
        seen: set[Path] = set()
        deduped = []
        for p in selected:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        selected = deduped
    else:
        selected = pipeline.recommend_books(limit=6)

    if not selected:
        raise HTTPException(status_code=400, detail="未找到匹配的书目")

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
    return {"job_id": job_id, "selected_books": [b.stem for b in selected], "message": "任务已启动"}


@app.post("/api/job/cancel")
def cancel_job():
    """取消当前运行中的任务"""
    _job_cancelled.set()
    return {"message": "取消信号已发送"}


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
        })
    return {"runs": result}


@app.get("/api/runs/{run_name}/triples")
def run_triples(run_name: str, limit: int = 50):
    """查看某次运行的三元组样本"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    # 优先用 cleaned，没有则用 normalized
    jsonl = run_dir / "triples.cleaned.jsonl"
    if not jsonl.exists():
        jsonl = run_dir / "triples.normalized.jsonl"
    rows = []
    if jsonl.exists():
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
                if len(rows) >= limit:
                    break
    return {"run_dir": run_name, "rows": rows, "count": len(rows)}


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
        return {
            "target": str(target),
            "graph_triples": len(graph_data),
            "evidence_count": evidence_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_name}/publish-nebula")
def run_publish_nebula(run_name: str):
    """将指定运行增量发布到 NebulaGraph（先同步到 graph_runtime.json，再写入 Nebula）"""
    run_dir = DEFAULT_OUTPUT_DIR / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        # 1. 先同步到 graph_runtime.json（追加模式）
        pipeline = _build_pipeline()
        target = pipeline.publish_graph(run_dir=run_dir, replace=False)

        # 2. 加载本次 run 的三元组
        graph_import_path = run_dir / "graph_import.json"
        if not graph_import_path.exists():
            raise HTTPException(status_code=400, detail="graph_import.json not found in run dir")
        rows = json.loads(graph_import_path.read_text(encoding="utf-8"))

        # 3. 加载 evidence
        from services.graph_service.nebulagraph_store import NebulaGraphStore, load_graph_rows
        evidence_path = run_dir / "evidence_metadata.jsonl"
        rows_with_evidence = load_graph_rows(graph_import_path, evidence_path if evidence_path.exists() else None)

        # 4. 连接 NebulaGraph 并写入
        store = NebulaGraphStore()
        if not store.ready():
            raise HTTPException(status_code=503, detail="NebulaGraph not reachable — is Docker running?")

        stmts = store.build_import_statements(rows_with_evidence)

        from nebula3.gclient.net import ConnectionPool
        from nebula3.Config import Config as NebulaConfig
        config = NebulaConfig()
        config.max_connection_pool_size = 2
        config.timeout = 30000
        pool = ConnectionPool()
        pool.init([(store.settings.host, store.settings.port)], config)
        session = pool.get_session(store.settings.user, store.settings.password)

        ok_count = fail_count = 0
        for stmt in stmts:
            r = session.execute(f"USE `{store.settings.space}`; {stmt}")
            if r.is_succeeded():
                ok_count += 1
            else:
                fail_count += 1

        session.release()
        pool.close()

        graph_data = json.loads(target.read_text(encoding="utf-8"))
        return {
            "target": str(target),
            "graph_triples": len(graph_data),
            "nebula_ok": ok_count,
            "nebula_fail": fail_count,
            "nebula_space": store.settings.space,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
