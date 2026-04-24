from __future__ import annotations

import json
import re
import statistics
import threading
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.triple_pipeline_service import (
    DEFAULT_BOOKS_DIR,
    DEFAULT_OUTPUT_DIR,
    ChunkTask,
    PipelineConfig,
    TCMTriplePipeline,
    _first_env,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_DIR.parent.parent
BOOKS_DIR = DEFAULT_BOOKS_DIR if DEFAULT_BOOKS_DIR.exists() else WORKSPACE_ROOT / "TCM-Ancient-Books-master" / "TCM-Ancient-Books-master"
load_dotenv(BACKEND_DIR / ".env")

router = APIRouter()

DEFAULT_SWEEP_BOOK = "072-医方考"
DEFAULT_SWEEP_MODEL = "mimo-v2-pro"
DEFAULT_CHUNK_SIZES = [800, 1200, 1800, 2400, 3000, 4000, 6000, 8000, 10000]
DEFAULT_OUTPUT_ROOT = DEFAULT_OUTPUT_DIR.parent / "chunk_size_benchmark_lab"

_sweep_lock = threading.Lock()
_sweep_job: dict[str, Any] = {}
_sweep_logs: list[dict[str, Any]] = []
_sweep_thread: threading.Thread | None = None
_sweep_cancelled = threading.Event()


class ChunkSweepApiConfig(BaseModel):
    api_key: str = Field(default="")
    base_url: str = Field(default="")
    request_timeout: float = Field(default=314.0, ge=10.0, le=3600.0)
    max_retries: int = Field(default=2, ge=0, le=10)
    request_delay: float = Field(default=1.1, ge=0.0, le=30.0)
    retry_backoff_base: float = Field(default=2.0, ge=0.5, le=60.0)
    parallel_workers: int = Field(default=1, ge=1, le=8)
    chunk_strategy: str = Field(default="body_first")


class ChunkSweepStartRequest(BaseModel):
    label: str = Field(default="chunk_size_benchmark")
    book_name: str = Field(default=DEFAULT_SWEEP_BOOK)
    model: str = Field(default=DEFAULT_SWEEP_MODEL)
    chunk_sizes: list[int] = Field(default_factory=lambda: list(DEFAULT_CHUNK_SIZES))
    sample_count: int = Field(default=5, ge=2, le=8)
    baseline_chunk_chars: int = Field(default=800, ge=200, le=20000)
    baseline_overlap: int = Field(default=200, ge=0, le=5000)
    overlap_ratio: float = Field(default=0.125, ge=0.0, le=0.5)
    api_config: ChunkSweepApiConfig = Field(default_factory=ChunkSweepApiConfig)


def _sweep_log(level: str, msg: str, **extra: Any) -> None:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "msg": msg, **extra}
    with _sweep_lock:
        _sweep_logs.append(entry)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_state() -> dict[str, Any]:
    with _sweep_lock:
        return json.loads(json.dumps(_sweep_job, ensure_ascii=False))


def _load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


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


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _make_safe_name(value: str, default: str = "item") -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "").strip())
    return safe or default


def _classify_error(error: str) -> str:
    lower = str(error or "").lower()
    if not lower:
        return ""
    if "not_json" in lower or "json" in lower or "expecting value" in lower:
        return "json"
    if "timed out" in lower or "timeout" in lower:
        return "timeout"
    if "ssl" in lower or "unexpected_eof" in lower or "eof" in lower:
        return "ssl"
    return "other"


def _estimate_overlap(chunk_size: int, ratio: float) -> int:
    estimated = int(round(max(0.0, float(chunk_size) * float(ratio))))
    minimum = 100 if chunk_size >= 800 else max(0, chunk_size // 8)
    return max(0, min(chunk_size - 1, max(minimum, estimated)))


def _build_output_dir(label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_ROOT / f"{timestamp}_{_make_safe_name(label, default='chunk_size_benchmark')}"


def _resolve_book_path(book_name: str) -> Path:
    matches = list(BOOKS_DIR.glob(f"{book_name}.txt"))
    if not matches:
        raise FileNotFoundError(f"book_not_found: {book_name}")
    return matches[0]


def _build_pipeline(
    *,
    model: str,
    max_chunk_chars: int,
    chunk_overlap: int,
    api_cfg: ChunkSweepApiConfig,
) -> TCMTriplePipeline:
    api_key = api_cfg.api_key or _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = api_cfg.base_url or _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    return TCMTriplePipeline(
        PipelineConfig(
            books_dir=BOOKS_DIR,
            output_dir=DEFAULT_OUTPUT_DIR,
            model=model,
            api_key=api_key or "dummy_for_dry_run",
            base_url=base_url,
            request_timeout=api_cfg.request_timeout,
            max_chunk_chars=max_chunk_chars,
            chunk_overlap=chunk_overlap,
            max_retries=api_cfg.max_retries,
            request_delay=api_cfg.request_delay,
            parallel_workers=api_cfg.parallel_workers,
            retry_backoff_base=api_cfg.retry_backoff_base,
            chunk_strategy=api_cfg.chunk_strategy,
        )
    )


def _sample_indices(total: int, sample_count: int) -> list[int]:
    if total <= 0:
        return []
    if total <= sample_count:
        return list(range(total))
    positions = [(idx + 1) / (sample_count + 1) for idx in range(sample_count)]
    result: list[int] = []
    for pos in positions:
        candidate = min(total - 1, max(0, round((total - 1) * pos)))
        while candidate in result and candidate < total - 1:
            candidate += 1
        while candidate in result and candidate > 0:
            candidate -= 1
        if candidate not in result:
            result.append(candidate)
    return sorted(result)


def _build_snippets(text: str) -> list[str]:
    normalized = _normalize_match_text(text)
    if not normalized:
        return []
    snippets: list[str] = []
    for ratio in (0.2, 0.5, 0.8):
        center = int(len(normalized) * ratio)
        start = max(0, center - 12)
        snippet = normalized[start : start + 24]
        if len(snippet) >= 12 and snippet not in snippets:
            snippets.append(snippet)
    if len(normalized) >= 16:
        head = normalized[:16]
        tail = normalized[-16:]
        if head not in snippets:
            snippets.append(head)
        if tail not in snippets:
            snippets.append(tail)
    return snippets


def _build_anchor_tasks(book_path: Path, req: ChunkSweepStartRequest) -> list[dict[str, Any]]:
    pipeline = _build_pipeline(
        model=req.model,
        max_chunk_chars=req.baseline_chunk_chars,
        chunk_overlap=req.baseline_overlap,
        api_cfg=req.api_config,
    )
    tasks = pipeline.schedule_book_chunks(book_path=book_path, chunk_strategy=req.api_config.chunk_strategy)
    indices = _sample_indices(len(tasks), req.sample_count)
    anchors: list[dict[str, Any]] = []
    for order, idx in enumerate(indices, start=1):
        task = tasks[idx]
        anchors.append(
            {
                "sample_label": f"S{order}",
                "sample_order": order,
                "sample_total": len(indices),
                "baseline_chunk_index": task.chunk_index,
                "chapter_name": task.chapter_name,
                "text_length": len(task.text_chunk),
                "text_preview": task.text_chunk[:180],
                "snippets": _build_snippets(task.text_chunk),
            }
        )
    return anchors


def _match_tasks_for_size(
    *,
    book_path: Path,
    model: str,
    chunk_size: int,
    overlap: int,
    anchors: list[dict[str, Any]],
    api_cfg: ChunkSweepApiConfig,
) -> list[dict[str, Any]]:
    pipeline = _build_pipeline(
        model=model,
        max_chunk_chars=chunk_size,
        chunk_overlap=overlap,
        api_cfg=api_cfg,
    )
    tasks = pipeline.schedule_book_chunks(book_path=book_path, chunk_strategy=api_cfg.chunk_strategy)
    normalized_tasks = [(_normalize_match_text(task.text_chunk), task) for task in tasks]
    selected_by_chunk: dict[int, dict[str, Any]] = {}

    for anchor in anchors:
        matched_task: ChunkTask | None = None
        for snippet in anchor.get("snippets", []):
            for normalized_text, task in normalized_tasks:
                if snippet and snippet in normalized_text:
                    matched_task = task
                    break
            if matched_task is not None:
                break
        if matched_task is None and tasks:
            sample_total = max(1, int(anchor.get("sample_total", 1) or 1))
            sample_order = max(1, int(anchor.get("sample_order", 1) or 1))
            if sample_total <= 1:
                approx_index = len(tasks) // 2
            else:
                approx_index = round((sample_order - 1) * (len(tasks) - 1) / (sample_total - 1))
            approx_index = min(len(tasks) - 1, max(0, approx_index))
            matched_task = tasks[approx_index]
        if matched_task is None:
            continue
        bucket = selected_by_chunk.setdefault(
            matched_task.chunk_index,
            {
                "task": matched_task,
                "sample_labels": [],
                "matched_baseline_chunks": [],
            },
        )
        bucket["sample_labels"].append(anchor["sample_label"])
        bucket["matched_baseline_chunks"].append(anchor["baseline_chunk_index"])

    rows = sorted(selected_by_chunk.values(), key=lambda item: item["task"].chunk_index)
    for item in rows:
        item["sample_labels"] = sorted(item["sample_labels"])
        item["matched_baseline_chunks"] = sorted(item["matched_baseline_chunks"])
    return rows


def _rank_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    positive_sec_per_triple = [row["sec_per_triple"] for row in rows if row.get("sec_per_triple") not in (None, 0)]
    min_sec_per_triple = min(positive_sec_per_triple) if positive_sec_per_triple else 1.0
    max_triples = max((row.get("mean_triples_per_call", 0.0) for row in rows), default=1.0) or 1.0
    ranked: list[dict[str, Any]] = []
    for row in rows:
        api_calls = max(1, int(row.get("api_calls", 0) or 0))
        parse_success_rate = float(row.get("parse_success_rate", 0.0) or 0.0)
        low_yield_rate = float(row.get("low_yield_calls", 0) or 0) / api_calls
        robustness = max(0.0, 1.0 - low_yield_rate)
        sec_per_triple = row.get("sec_per_triple")
        speed_score = (min_sec_per_triple / sec_per_triple) if sec_per_triple not in (None, 0) else 0.0
        yield_score = min(1.0, (row.get("mean_triples_per_call", 0.0) or 0.0) / max_triples)
        composite = parse_success_rate * 0.45 + robustness * 0.25 + speed_score * 0.20 + yield_score * 0.10
        ranked.append({**row, "robustness_score": robustness, "speed_score": speed_score, "yield_score": yield_score, "composite_score": composite})
    ranked.sort(key=lambda item: item["composite_score"], reverse=True)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _render_report(run_dir: Path, state: dict[str, Any], ranked: list[dict[str, Any]]) -> Path:
    report_path = run_dir / "chunk_size_benchmark_report.md"
    lines = [
        "# Chunk Size 扫描实验报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 书目：`{state.get('book_name', DEFAULT_SWEEP_BOOK)}`",
        f"- 模型：`{state.get('model', DEFAULT_SWEEP_MODEL)}`",
        f"- 样本窗口数：{state.get('sample_count', 0)}",
        f"- Chunk sizes：{', '.join(str(item) for item in state.get('chunk_sizes', []))}",
        "- 说明：该实验不比较金标准确率，重点观察速度、JSON 可解析性、低产出比例与异常类型。",
        "",
        "## 总榜",
        "",
        "| 排名 | Chunk Size | Overlap | API Calls | 解析成功率 | 平均延迟(s) | 每三元组耗时(s) | 平均每调用三元组数 | 低产出 | JSON错误 | 超时 | 其他错误 | 综合分 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ranked:
        sec_per_triple_text = f"{row['sec_per_triple']:.3f}" if row.get("sec_per_triple") is not None else "∞"
        lines.append(
            f"| {row['rank']} | {row['chunk_size']} | {row['overlap']} | {row['api_calls']} | {row['parse_success_rate']:.2%} | "
            f"{row['latency_mean_sec']:.2f} | {sec_per_triple_text} | {row['mean_triples_per_call']:.2f} | {row['low_yield_calls']} | "
            f"{row['json_error_calls']} | {row['timeout_error_calls']} | {row['other_error_calls']} | {row['composite_score']:.3f} |"
        )
    lines.extend(["", "## 分档详情", ""])
    for row in ranked:
        lines.extend(
            [
                f"### chunk_size={row['chunk_size']} / overlap={row['overlap']}",
                "",
                f"- 调用数：{row['api_calls']}，样本覆盖：{row['sample_labels']}",
                f"- 速度：总耗时 {row['elapsed_total_sec']:.2f}s，平均 {row['latency_mean_sec']:.2f}s，中位数 {row['latency_median_sec']:.2f}s，最大 {row['latency_max_sec']:.2f}s，每三元组耗时 {row['sec_per_triple']:.3f}s。"
                if row.get("sec_per_triple") is not None
                else f"- 速度：总耗时 {row['elapsed_total_sec']:.2f}s，平均 {row['latency_mean_sec']:.2f}s，中位数 {row['latency_median_sec']:.2f}s，最大 {row['latency_max_sec']:.2f}s，本档未产出三元组，无法计算每三元组耗时。",
                f"- 解析：成功率 {row['parse_success_rate']:.2%}，JSON 错误 {row['json_error_calls']}，超时 {row['timeout_error_calls']}，SSL {row['ssl_error_calls']}，其他错误 {row['other_error_calls']}。",
                f"- 产量：总三元组 {row['total_triples']}，平均每调用 {row['mean_triples_per_call']:.2f}，低产出调用 {row['low_yield_calls']}。",
                "",
                "| sample | 章节 | triples | latency(s) | error |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for output in row.get("outputs", []):
            lines.append(
                f"| {', '.join(output.get('sample_labels', []))} | {output.get('chapter_name', '')} | {output.get('triples_count', 0)} | "
                f"{output.get('elapsed_sec', 0.0):.2f} | {output.get('error', '') or '-'} |"
            )
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _list_history_runs(limit: int = 50) -> list[dict[str, Any]]:
    if not DEFAULT_OUTPUT_ROOT.exists():
        return []
    rows: list[dict[str, Any]] = []
    for run_dir in sorted((path for path in DEFAULT_OUTPUT_ROOT.iterdir() if path.is_dir()), reverse=True):
        manifest = _load_json_if_exists(run_dir / "manifest.json", {})
        state = _load_json_if_exists(run_dir / "state.json", {})
        results = _load_json_if_exists(run_dir / "results.json", {})
        ranking = results.get("ranking", []) if isinstance(results, dict) else []
        rows.append(
            {
                "run_dir": run_dir.name,
                "path": str(run_dir),
                "label": str((manifest or {}).get("label", "") or run_dir.name),
                "book_name": str((manifest or {}).get("book_name", "") or (state or {}).get("book_name", DEFAULT_SWEEP_BOOK)),
                "model": str((manifest or {}).get("model", "") or (state or {}).get("model", DEFAULT_SWEEP_MODEL)),
                "chunk_sizes": list((manifest or {}).get("chunk_sizes", []) or (state or {}).get("chunk_sizes", [])),
                "status": str((state or {}).get("status", "unknown") or "unknown"),
                "started_at": str((state or {}).get("started_at", "") or ""),
                "finished_at": str((state or {}).get("finished_at", "") or ""),
                "report_path": str((results or {}).get("report_path", "") or (state or {}).get("report_path", "")),
                "best_chunk_size": int(ranking[0].get("chunk_size", 0) or 0) if ranking else 0,
                "best_parse_success_rate": float(ranking[0].get("parse_success_rate", 0.0) or 0.0) if ranking else 0.0,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _load_history_run(run_name: str) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_dir = DEFAULT_OUTPUT_ROOT / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="chunk_benchmark_run_not_found")
    manifest = _load_json_if_exists(run_dir / "manifest.json", {})
    state = _load_json_if_exists(run_dir / "state.json", {})
    results = _load_json_if_exists(run_dir / "results.json", {})
    return run_dir, manifest, state, results


def _run_chunk_sweep_job(job_id: str, req: ChunkSweepStartRequest) -> None:
    global _sweep_job
    start_ts = time.time()
    run_dir = _build_output_dir(req.label)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    results_path = run_dir / "results.json"

    book_path = _resolve_book_path(req.book_name)
    anchors = _build_anchor_tasks(book_path, req)
    if not anchors:
        raise RuntimeError("no_anchor_samples_found")

    plans: list[dict[str, Any]] = []
    calls_total = 0
    for chunk_size in sorted({max(200, int(value)) for value in req.chunk_sizes}):
        overlap = _estimate_overlap(chunk_size, req.overlap_ratio)
        selected = _match_tasks_for_size(
            book_path=book_path,
            model=req.model,
            chunk_size=chunk_size,
            overlap=overlap,
            anchors=anchors,
            api_cfg=req.api_config,
        )
        plans.append({"chunk_size": chunk_size, "overlap": overlap, "selected_calls": selected})
        calls_total += len(selected)

    state: dict[str, Any] = {
        "job_id": job_id,
        "status": "running",
        "phase": "preparing",
        "label": req.label,
        "book_name": req.book_name,
        "model": req.model,
        "chunk_sizes": [plan["chunk_size"] for plan in plans],
        "sample_count": len(anchors),
        "sample_labels": [anchor["sample_label"] for anchor in anchors],
        "calls_total": calls_total,
        "calls_completed": 0,
        "current_chunk_size": None,
        "current_sample": "",
        "elapsed_secs": 0,
        "eta": "",
        "speed_calls_per_min": 0.0,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": "",
        "run_dir": str(run_dir),
        "results": [
            {
                "chunk_size": plan["chunk_size"],
                "overlap": plan["overlap"],
                "status": "pending",
                "api_calls": len(plan["selected_calls"]),
                "completed_calls": 0,
                "parse_success_rate": 0.0,
                "latency_mean_sec": 0.0,
                "total_triples": 0,
                "mean_triples_per_call": 0.0,
                "sec_per_triple": None,
                "triples_per_minute": 0.0,
                "low_yield_calls": 0,
                "json_error_calls": 0,
                "timeout_error_calls": 0,
                "ssl_error_calls": 0,
                "other_error_calls": 0,
                "error": "",
            }
            for plan in plans
        ],
        "ranking": [],
    }

    with _sweep_lock:
        _sweep_job = state
    _write_json(run_dir / "manifest.json", req.model_dump())
    _write_json(state_path, state)
    _sweep_log("info", f"Chunk 大小扫描已启动 {job_id}，共 {len(plans)} 档，{calls_total} 次调用")

    size_results: list[dict[str, Any]] = []
    calls_completed = 0

    try:
        for plan in plans:
            if _sweep_cancelled.is_set():
                raise RuntimeError("chunk_sweep_cancelled")

            chunk_size = plan["chunk_size"]
            overlap = plan["overlap"]
            selected_calls = plan["selected_calls"]
            pipeline = _build_pipeline(
                model=req.model,
                max_chunk_chars=chunk_size,
                chunk_overlap=overlap,
                api_cfg=req.api_config,
            )
            outputs: list[dict[str, Any]] = []
            parse_success = 0
            _sweep_log("info", f"开始 chunk_size={chunk_size} / overlap={overlap} | api_calls={len(selected_calls)}")

            with _sweep_lock:
                _sweep_job["phase"] = "running"
                _sweep_job["current_chunk_size"] = chunk_size
                _sweep_job["current_sample"] = ""
                for row in _sweep_job["results"]:
                    if row["chunk_size"] == chunk_size:
                        row["status"] = "running"
                        row["error"] = ""
                        break

            for selected in selected_calls:
                if _sweep_cancelled.is_set():
                    raise RuntimeError("chunk_sweep_cancelled")

                task = selected["task"]
                sample_label = ",".join(selected["sample_labels"])
                with _sweep_lock:
                    _sweep_job["current_sample"] = sample_label

                _sweep_log("info", f"  [size={chunk_size}] sample={sample_label} chunk={task.chunk_index} 开始")
                started = time.perf_counter()
                payload_for_audit: Any = None
                raw_meta: dict[str, Any] = {}
                normalized_rows: list[dict[str, Any]] = []
                error = ""

                try:
                    payload = pipeline.extract_chunk_payload(task, dry_run=False)
                    payload_for_audit = payload
                    raw_meta = payload.get("__meta__", {}) if isinstance(payload, dict) else {}
                    normalized_rows = [
                        asdict(row)
                        for row in pipeline.normalize_triples(
                            payload=payload,
                            book_name=task.book_name,
                            chapter_name=task.chapter_name,
                        )
                    ]
                    parse_success += 1
                except Exception as exc:
                    error = str(exc)

                elapsed_one = time.perf_counter() - started
                outputs.append(
                    {
                        "sample_labels": list(selected["sample_labels"]),
                        "matched_baseline_chunks": list(selected["matched_baseline_chunks"]),
                        "chunk_index": task.chunk_index,
                        "chapter_name": task.chapter_name,
                        "text_length": len(task.text_chunk),
                        "text_preview": task.text_chunk[:240],
                        "selected_text": task.text_chunk,
                        "elapsed_sec": elapsed_one,
                        "triples_count": len(normalized_rows),
                        "error": error,
                        "error_type": _classify_error(error),
                        "usage": raw_meta.get("usage", {}) if isinstance(raw_meta, dict) else {},
                        "raw_payload": payload_for_audit,
                        "raw_response_text": raw_meta.get("raw_text", "") if isinstance(raw_meta, dict) else "",
                        "raw_response_format_mode": raw_meta.get("response_format_mode", "") if isinstance(raw_meta, dict) else "",
                        "predicted_rows": normalized_rows,
                        "low_yield": len(normalized_rows) <= 1,
                    }
                )

                calls_completed += 1
                latencies = [item["elapsed_sec"] for item in outputs]
                total_triples = sum(item["triples_count"] for item in outputs)
                json_errors = sum(1 for item in outputs if item["error_type"] == "json")
                timeout_errors = sum(1 for item in outputs if item["error_type"] == "timeout")
                ssl_errors = sum(1 for item in outputs if item["error_type"] == "ssl")
                other_errors = sum(1 for item in outputs if item["error_type"] == "other")
                low_yield = sum(1 for item in outputs if item["low_yield"])

                with _sweep_lock:
                    elapsed = time.time() - start_ts
                    _sweep_job["calls_completed"] = calls_completed
                    _sweep_job["elapsed_secs"] = int(elapsed)
                    rate = calls_completed / max(elapsed, 1.0)
                    remaining = max(0.0, (_sweep_job["calls_total"] - calls_completed) / rate) if rate > 0 else 0.0
                    _sweep_job["eta"] = _fmt_eta(remaining) if calls_completed > 0 else ""
                    _sweep_job["speed_calls_per_min"] = round(rate * 60, 2) if calls_completed > 0 else 0.0
                    for row in _sweep_job["results"]:
                        if row["chunk_size"] == chunk_size:
                            row["completed_calls"] = len(outputs)
                            row["parse_success_rate"] = round(parse_success / len(outputs), 4)
                            row["latency_mean_sec"] = round(statistics.mean(latencies), 3)
                            row["total_triples"] = total_triples
                            row["mean_triples_per_call"] = round(total_triples / len(outputs), 3)
                            row["sec_per_triple"] = round(sum(latencies) / total_triples, 3) if total_triples > 0 else None
                            row["triples_per_minute"] = round(total_triples * 60 / sum(latencies), 3) if total_triples > 0 and sum(latencies) > 0 else 0.0
                            row["low_yield_calls"] = low_yield
                            row["json_error_calls"] = json_errors
                            row["timeout_error_calls"] = timeout_errors
                            row["ssl_error_calls"] = ssl_errors
                            row["other_error_calls"] = other_errors
                            row["error"] = error
                            break

                _sweep_log(
                    "info" if not error else "warn",
                    f"  [size={chunk_size}] sample={sample_label} 完成 | triples={len(normalized_rows)} | latency={elapsed_one:.2f}s"
                    + (f" | error={error}" if error else ""),
                )
                _write_json(state_path, _snapshot_state())

            latencies = [item["elapsed_sec"] for item in outputs] or [0.0]
            total_triples = sum(item["triples_count"] for item in outputs)
            size_result = {
                "chunk_size": chunk_size,
                "overlap": overlap,
                "api_calls": len(outputs),
                "sample_labels": sorted({label for output in outputs for label in output["sample_labels"]}),
                "parse_success_rate": parse_success / max(len(outputs), 1),
                "total_triples": total_triples,
                "mean_triples_per_call": (total_triples / len(outputs)) if outputs else 0.0,
                "sec_per_triple": (sum(latencies) / total_triples) if total_triples > 0 else None,
                "triples_per_minute": (total_triples * 60 / sum(latencies)) if sum(latencies) > 0 and total_triples > 0 else 0.0,
                "low_yield_calls": sum(1 for item in outputs if item["low_yield"]),
                "latency_mean_sec": statistics.mean(latencies),
                "latency_median_sec": statistics.median(latencies),
                "latency_max_sec": max(latencies),
                "elapsed_total_sec": sum(latencies),
                "json_error_calls": sum(1 for item in outputs if item["error_type"] == "json"),
                "timeout_error_calls": sum(1 for item in outputs if item["error_type"] == "timeout"),
                "ssl_error_calls": sum(1 for item in outputs if item["error_type"] == "ssl"),
                "other_error_calls": sum(1 for item in outputs if item["error_type"] == "other"),
                "completion_tokens_total": sum(int(item["usage"].get("completion_tokens", 0) or 0) for item in outputs),
                "outputs": outputs,
            }
            size_result["result_file"] = f"chunk_{chunk_size:06d}.json"
            size_results.append(size_result)
            _write_json(run_dir / size_result["result_file"], size_result)

            with _sweep_lock:
                for row in _sweep_job["results"]:
                    if row["chunk_size"] == chunk_size:
                        row["status"] = "completed"
                        row["error"] = ""
                        break
                _sweep_job["ranking"] = _rank_results(size_results)

            _sweep_log(
                "info",
                f"完成 chunk_size={chunk_size} | parse_success={size_result['parse_success_rate']:.2%} | mean_latency={size_result['latency_mean_sec']:.2f}s",
            )
            _write_json(state_path, _snapshot_state())

        ranked = _rank_results(size_results)
        report_path = _render_report(run_dir, _snapshot_state(), ranked)
        final_state = _snapshot_state()
        final_state["status"] = "completed"
        final_state["phase"] = "finished"
        final_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        final_state["current_chunk_size"] = None
        final_state["current_sample"] = ""
        final_state["ranking"] = ranked
        final_state["report_path"] = str(report_path)
        with _sweep_lock:
            _sweep_job = final_state
        _write_json(results_path, {"ranking": ranked, "report_path": str(report_path)})
        _write_json(state_path, final_state)
        _sweep_log("info", f"Chunk 大小扫描完成，共比较 {len(size_results)} 档")
    except RuntimeError as exc:
        if str(exc) == "chunk_sweep_cancelled":
            cancelled_state = _snapshot_state()
            cancelled_state["status"] = "cancelled"
            cancelled_state["phase"] = "cancelled"
            cancelled_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            cancelled_state["current_chunk_size"] = None
            cancelled_state["current_sample"] = ""
            with _sweep_lock:
                _sweep_job = cancelled_state
            _write_json(state_path, cancelled_state)
            _write_json(results_path, {"ranking": cancelled_state.get("ranking", []), "partial": True})
            _sweep_log("warn", "Chunk 大小扫描已取消，已保留当前结果")
        else:
            raise
    except Exception as exc:
        error_state = _snapshot_state()
        error_state["status"] = "error"
        error_state["phase"] = "error"
        error_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        error_state["error"] = str(exc)
        error_state["current_chunk_size"] = None
        error_state["current_sample"] = ""
        with _sweep_lock:
            _sweep_job = error_state
        _write_json(state_path, error_state)
        _sweep_log("error", f"Chunk 大小扫描失败: {exc}")
    finally:
        if _sweep_cancelled.is_set():
            _sweep_cancelled.clear()


@router.get("/api/chunk-benchmark/config")
def chunk_benchmark_config() -> dict[str, Any]:
    return {
        "default_book_name": DEFAULT_SWEEP_BOOK,
        "default_model": DEFAULT_SWEEP_MODEL,
        "default_chunk_sizes": DEFAULT_CHUNK_SIZES,
        "default_api_config": ChunkSweepApiConfig().model_dump(),
        "default_sample_count": 5,
        "default_baseline_chunk_chars": 800,
        "default_baseline_overlap": 200,
        "default_overlap_ratio": 0.125,
        "output_root": str(DEFAULT_OUTPUT_ROOT),
        "notes": {
            "evaluation_mode": "speed_parse_robustness",
            "accuracy_included": False,
            "focus": ["latency", "parse_success", "low_yield", "error_types"],
        },
    }


@router.post("/api/chunk-benchmark/start")
def start_chunk_benchmark(req: ChunkSweepStartRequest) -> dict[str, Any]:
    global _sweep_thread, _sweep_job, _sweep_logs
    with _sweep_lock:
        if _sweep_thread and _sweep_thread.is_alive():
            raise HTTPException(status_code=409, detail="已有 chunk 大小实验在运行中")
        _sweep_logs = []
        _sweep_job = {
            "status": "starting",
            "phase": "starting",
            "book_name": req.book_name,
            "model": req.model,
            "chunk_sizes": list(req.chunk_sizes),
        }
    _sweep_cancelled.clear()
    job_id = uuid4().hex[:8]
    worker = threading.Thread(target=_run_chunk_sweep_job, args=(job_id, req), daemon=True)
    _sweep_thread = worker
    worker.start()
    return {"ok": True, "job_id": job_id, "book_name": req.book_name, "model": req.model, "chunk_sizes": req.chunk_sizes}


@router.post("/api/chunk-benchmark/cancel")
def cancel_chunk_benchmark() -> dict[str, Any]:
    with _sweep_lock:
        if not (_sweep_thread and _sweep_thread.is_alive()):
            return {"ok": True, "message": "no_active_chunk_benchmark"}
    _sweep_cancelled.set()
    _sweep_log("warn", "收到用户取消 chunk 大小实验请求")
    return {"ok": True, "message": "cancel_requested"}


@router.get("/api/chunk-benchmark/status")
def chunk_benchmark_status() -> dict[str, Any]:
    snapshot = _snapshot_state()
    if not snapshot:
        return {"status": "idle", "phase": "idle", "results": [], "ranking": []}
    return snapshot


@router.get("/api/chunk-benchmark/results")
def chunk_benchmark_results() -> dict[str, Any]:
    snapshot = _snapshot_state()
    if not snapshot:
        raise HTTPException(status_code=404, detail="chunk_benchmark_not_found")
    return {
        "status": snapshot.get("status", "idle"),
        "run_dir": snapshot.get("run_dir", ""),
        "report_path": snapshot.get("report_path", ""),
        "ranking": snapshot.get("ranking", []),
        "results": snapshot.get("results", []),
    }


@router.get("/api/chunk-benchmark/history")
def chunk_benchmark_history(limit: int = 50) -> dict[str, Any]:
    return {"runs": _list_history_runs(limit=max(1, min(limit, 200)))}


@router.get("/api/chunk-benchmark/history/{run_name}")
def chunk_benchmark_history_detail(run_name: str) -> dict[str, Any]:
    run_dir, manifest, state, results = _load_history_run(run_name)
    ranking = results.get("ranking", []) if isinstance(results, dict) else []
    return {
        "run_dir": run_dir.name,
        "path": str(run_dir),
        "manifest": manifest,
        "state": state,
        "report_path": str((results or {}).get("report_path", "") or (state or {}).get("report_path", "")),
        "ranking": ranking,
    }


@router.get("/api/chunk-benchmark/size")
def chunk_benchmark_size_detail(chunk_size: int, run_name: str = "") -> dict[str, Any]:
    if run_name:
        run_dir = DEFAULT_OUTPUT_ROOT / run_name
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail="chunk_benchmark_run_not_found")
    else:
        snapshot = _snapshot_state()
        run_dir = Path(str(snapshot.get("run_dir", "") or ""))
        if not str(run_dir):
            raise HTTPException(status_code=404, detail="chunk_benchmark_not_found")
    path = run_dir / f"chunk_{int(chunk_size):06d}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="chunk_size_result_not_found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/chunk-benchmark/stream")
def chunk_benchmark_stream():
    def event_gen():
        last_index = 0
        while True:
            with _sweep_lock:
                state = json.loads(json.dumps(_sweep_job, ensure_ascii=False))
                logs = _sweep_logs[last_index:]
                last_index = len(_sweep_logs)
            yield f"data: {json.dumps({'state': state, 'logs': logs}, ensure_ascii=False)}\n\n"
            if state.get("status") in {"completed", "error", "cancelled", "idle"}:
                break
            time.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
