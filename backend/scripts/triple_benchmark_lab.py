from __future__ import annotations

import json
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
    PipelineConfig,
    TCMTriplePipeline,
    _first_env,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

router = APIRouter()

DEFAULT_BENCHMARK_BOOK = "072-医方考"
DEFAULT_BENCHMARK_CHUNK_IDS = [20, 30, 50, 100]
DEFAULT_BENCHMARK_MODELS = [
    "mimo-v2-pro",
    "doubao-seed-2.0-pro",
    "doubao-seed-2.0-lite",
    "deepseek-v3.2",
    "mimo-v2-omni",
    "mimo-v2-flash",
    "kimi-k2.5",
]
DEFAULT_OUTPUT_ROOT = DEFAULT_OUTPUT_DIR.parent / "triple_benchmark_lab"

GOLD: dict[int, list[dict[str, str]]] = {
    20: [
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "大黄"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "附子泻心汤", "predicate": "治疗证候", "object": "伤寒心下痞"},
        {"subject": "附子泻心汤", "predicate": "治疗症状", "object": "汗出恶寒"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "生姜"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "甘草"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "半夏"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "生姜泻心汤", "predicate": "治疗疾病", "object": "伤寒中风"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "下利"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "谷不化"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "腹中雷鸣"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "心下痞硬而满"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "干噫"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "心烦不得安"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "芫花"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "甘遂"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "大戟"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "大枣"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "汗出"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "心下痞硬"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "胁痛"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "干呕"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "短气"},
    ],
    30: [
        {"subject": "附子汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "茯苓"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "芍药"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "白术"},
        {"subject": "附子汤", "predicate": "治疗证候", "object": "少阴病"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "背恶寒"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "身体痛"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "手足寒"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "骨节痛"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "甘草"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "干姜"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "自利不渴"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "身痛"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "厥逆下利"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "脉不至"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "干姜"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "治疗症状", "object": "食入口即吐"},
    ],
    50: [
        {"subject": "二妙散", "predicate": "使用药材", "object": "黄柏"},
        {"subject": "二妙散", "predicate": "使用药材", "object": "苍术"},
        {"subject": "二妙散", "predicate": "治疗症状", "object": "腰膝疼痛"},
        {"subject": "二妙散", "predicate": "治疗证候", "object": "湿热"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "白术"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "茯苓"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "猪苓"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "泽泻"},
        {"subject": "四苓散", "predicate": "治疗症状", "object": "水泻"},
        {"subject": "四苓散", "predicate": "治疗症状", "object": "小便不利"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "厚朴"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "陈皮"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "半夏"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "藿香"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "苍术"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "甘草"},
        {"subject": "不换金正气散", "predicate": "治疗症状", "object": "吐泻下利"},
        {"subject": "不换金正气散", "predicate": "治疗证候", "object": "山岚瘴气"},
        {"subject": "不换金正气散", "predicate": "治疗证候", "object": "不服水土"},
    ],
    100: [
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "半夏"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "胆南星"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "陈皮"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "香附"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "苏子"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "青皮"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "神曲"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "萝卜子"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "栝楼仁"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "麦芽"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "杏仁"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "葛根"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗证候", "object": "酒食生痰"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗症状", "object": "五更咳嗽"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗症状", "object": "胸膈膨闷"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "生地黄"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "白茯苓"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "人参"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "白蜜"},
        {"subject": "琼玉膏", "predicate": "治疗症状", "object": "干咳嗽"},
    ],
}

_benchmark_lock = threading.Lock()
_benchmark_job: dict[str, Any] = {}
_benchmark_logs: list[dict[str, Any]] = []
_benchmark_thread: threading.Thread | None = None
_benchmark_cancelled = threading.Event()


class BenchmarkApiConfig(BaseModel):
    api_key: str = Field(default="")
    base_url: str = Field(default="")
    request_timeout: float = Field(default=314.0, ge=10.0, le=3600.0)
    max_retries: int = Field(default=2, ge=0, le=10)
    request_delay: float = Field(default=1.1, ge=0.0, le=30.0)
    retry_backoff_base: float = Field(default=2.0, ge=0.5, le=60.0)
    parallel_workers: int = Field(default=11, ge=1, le=64)
    max_chunk_chars: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    chunk_strategy: str = Field(default="body_first")


class BenchmarkStartRequest(BaseModel):
    label: str = Field(default="model_benchmark")
    book_name: str = Field(default=DEFAULT_BENCHMARK_BOOK)
    chunk_ids: list[int] = Field(default_factory=lambda: list(DEFAULT_BENCHMARK_CHUNK_IDS))
    models: list[str] = Field(default_factory=lambda: list(DEFAULT_BENCHMARK_MODELS))
    api_config: BenchmarkApiConfig = Field(default_factory=BenchmarkApiConfig)


def _normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    for token in [" ", "\n", "\t", "\r", "（", "）", "(", ")", "：", ":", "，", ",", "。", ".", "；", ";", "、"]:
        text = text.replace(token, "")
    return text


def _triple_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize_text(row.get("subject", "")),
        _normalize_text(row.get("predicate", "")),
        _normalize_text(row.get("object", "")),
    )


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


def _benchmark_log(level: str, msg: str, **extra: Any) -> None:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "msg": msg, **extra}
    with _benchmark_lock:
        _benchmark_logs.append(entry)


def _benchmark_output_dir(label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in (label or "benchmark")).strip("_") or "benchmark"
    return DEFAULT_OUTPUT_ROOT / f"{timestamp}_{safe}"


def _safe_model_filename(model_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(model_name or "").strip())
    return safe or "model"


def _build_pipeline_for_model(model_name: str, cfg: BenchmarkApiConfig) -> TCMTriplePipeline:
    api_key = cfg.api_key or _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = cfg.base_url or _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    return TCMTriplePipeline(
        PipelineConfig(
            books_dir=DEFAULT_BOOKS_DIR,
            output_dir=DEFAULT_OUTPUT_DIR,
            model=model_name,
            api_key=api_key or "dummy_for_dry_run",
            base_url=base_url,
            request_timeout=cfg.request_timeout,
            max_chunk_chars=cfg.max_chunk_chars,
            chunk_overlap=cfg.chunk_overlap,
            max_retries=cfg.max_retries,
            request_delay=cfg.request_delay,
            parallel_workers=cfg.parallel_workers,
            retry_backoff_base=cfg.retry_backoff_base,
            chunk_strategy=cfg.chunk_strategy,
        )
    )


def _choose_chunk_tasks(book_name: str, chunk_ids: list[int], cfg: BenchmarkApiConfig) -> list[Any]:
    pipeline = TCMTriplePipeline(
        PipelineConfig(
            books_dir=DEFAULT_BOOKS_DIR,
            output_dir=DEFAULT_OUTPUT_DIR,
            model="benchmark-dummy",
            api_key="dummy",
            base_url="https://example.invalid",
            request_timeout=cfg.request_timeout,
            max_chunk_chars=cfg.max_chunk_chars,
            chunk_overlap=cfg.chunk_overlap,
            max_retries=cfg.max_retries,
            request_delay=0.0,
            parallel_workers=1,
            retry_backoff_base=cfg.retry_backoff_base,
            chunk_strategy=cfg.chunk_strategy,
        )
    )
    matches = list(DEFAULT_BOOKS_DIR.glob(f"{book_name}.txt"))
    if not matches:
        raise FileNotFoundError(f"book_not_found: {book_name}")
    tasks = pipeline.schedule_book_chunks(book_path=matches[0], chunk_strategy=cfg.chunk_strategy)
    mapping = {task.chunk_index: task for task in tasks}
    missing = [chunk_id for chunk_id in chunk_ids if chunk_id not in mapping]
    if missing:
        raise ValueError(f"chunk_not_found: {missing}")
    return [mapping[chunk_id] for chunk_id in chunk_ids]


def _format_triple(key: tuple[str, str, str]) -> str:
    return f"{key[0]} -[{key[1]}]-> {key[2]}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_state() -> dict[str, Any]:
    with _benchmark_lock:
        return json.loads(json.dumps(_benchmark_job, ensure_ascii=False))


def _load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


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
                "book_name": str((manifest or {}).get("book_name", "") or (state or {}).get("book_name", DEFAULT_BENCHMARK_BOOK)),
                "chunk_ids": list((manifest or {}).get("chunk_ids", []) or (state or {}).get("chunk_ids", [])),
                "models": list((manifest or {}).get("models", []) or (state or {}).get("models", [])),
                "status": str((state or {}).get("status", "unknown") or "unknown"),
                "started_at": str((state or {}).get("started_at", "") or ""),
                "finished_at": str((state or {}).get("finished_at", "") or ""),
                "report_path": str((results or {}).get("report_path", "") or (state or {}).get("report_path", "")),
                "ranking_count": len(ranking),
                "best_model": str(ranking[0].get("model", "") or "") if ranking else "",
                "best_f1": float(ranking[0].get("f1", 0.0) or 0.0) if ranking else 0.0,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _load_history_run(run_name: str) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_dir = DEFAULT_OUTPUT_ROOT / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="benchmark_run_not_found")
    manifest = _load_json_if_exists(run_dir / "manifest.json", {})
    state = _load_json_if_exists(run_dir / "state.json", {})
    results = _load_json_if_exists(run_dir / "results.json", {})
    return run_dir, manifest, state, results


def _rank_results(results: list[dict[str, Any]], chunk_count: int) -> list[dict[str, Any]]:
    if not results:
        return []
    positives = [item["latency_mean_sec"] for item in results if item["latency_mean_sec"] > 0]
    min_latency = min(positives) if positives else 1.0
    ranked: list[dict[str, Any]] = []
    for item in results:
        speed_score = min_latency / item["latency_mean_sec"] if item["latency_mean_sec"] else 0.0
        robustness_score = 1.0 - (item["low_yield_chunks"] / max(chunk_count, 1))
        composite = (
            item["f1"] * 0.45
            + item["precision"] * 0.10
            + item["recall"] * 0.15
            + item["parse_success_rate"] * 0.10
            + robustness_score * 0.10
            + speed_score * 0.10
        )
        ranked.append({**item, "speed_score": speed_score, "robustness_score": robustness_score, "composite_score": composite})
    ranked.sort(key=lambda item: item["composite_score"], reverse=True)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _render_report(run_dir: Path, state: dict[str, Any], ranked: list[dict[str, Any]]) -> Path:
    report_path = run_dir / "benchmark_report.md"
    lines = [
        "# 模型实验台报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 基准书目：`{state.get('book_name', DEFAULT_BENCHMARK_BOOK)}`",
        f"- 基准 chunk：{', '.join(str(item) for item in state.get('chunk_ids', []))}",
        "- 评分不纳入模型价格，仅比较性能、完整度与稳健性。",
        "",
        "## 总榜",
        "",
        "| 排名 | 模型 | F1 | Precision | Recall | 平均延迟(s) | 平均每 chunk 三元组数 | low_yield_chunks | 解析成功率 | 综合分 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in ranked:
        lines.append(
            f"| {item['rank']} | `{item['model']}` | {item['f1']:.3f} | {item['precision']:.3f} | {item['recall']:.3f} | "
            f"{item['latency_mean_sec']:.2f} | {item['mean_triples_per_chunk']:.2f} | {item['low_yield_chunks']} | "
            f"{item['parse_success_rate']:.2%} | {item['composite_score']:.3f} |"
        )
    lines.extend(["", "## 分模型详情", ""])
    for item in ranked:
        lines.extend([
            f"### {item['model']}",
            "",
            f"- 总体：F1={item['f1']:.3f}，Precision={item['precision']:.3f}，Recall={item['recall']:.3f}，TP={item['tp']}，FP={item['fp']}，FN={item['fn']}。",
            f"- 速度：平均 {item['latency_mean_sec']:.2f}s，中位数 {item['latency_median_sec']:.2f}s，最大 {item['latency_max_sec']:.2f}s。",
            f"- 产量：总三元组 {item['total_triples']}，平均每 chunk {item['mean_triples_per_chunk']:.2f}，低产出 chunk {item['low_yield_chunks']}。",
            "",
            "| chunk | triples | precision | recall | f1 | latency(s) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ])
        for output in item["outputs"]:
            lines.append(
                f"| {output['chunk_index']} | {output['triples_count']} | {output['precision']:.3f} | "
                f"{output['recall']:.3f} | {output['f1']:.3f} | {output['elapsed_sec']:.2f} |"
            )
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _run_benchmark_job(job_id: str, req: BenchmarkStartRequest) -> None:
    global _benchmark_job
    start_ts = time.time()
    run_dir = _benchmark_output_dir(req.label)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    results_path = run_dir / "results.json"

    tasks = _choose_chunk_tasks(req.book_name, req.chunk_ids, req.api_config)
    state: dict[str, Any] = {
        "job_id": job_id,
        "status": "running",
        "phase": "preparing",
        "label": req.label,
        "book_name": req.book_name,
        "chunk_ids": list(req.chunk_ids),
        "models": list(req.models),
        "models_total": len(req.models),
        "models_completed": 0,
        "chunks_total": len(req.models) * len(tasks),
        "chunks_completed": 0,
        "current_model": "",
        "current_chunk": None,
        "elapsed_secs": 0,
        "eta": "",
        "speed_chunks_per_min": 0.0,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": "",
        "run_dir": str(run_dir),
        "results": [
            {
                "model": model,
                "status": "pending",
                "completed_chunks": 0,
                "total_chunks": len(tasks),
                "current_chunk": None,
                "mean_latency_sec": 0.0,
                "total_triples": 0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "low_yield_chunks": 0,
                "parse_success_rate": 0.0,
                "error": "",
            }
            for model in req.models
        ],
        "ranking": [],
    }
    with _benchmark_lock:
        _benchmark_job = state
    _write_json(state_path, state)
    _write_json(run_dir / "manifest.json", req.model_dump())
    _benchmark_log("info", f"模型实验已启动 {job_id}，共 {len(req.models)} 个模型，{len(tasks)} 个 chunk")

    model_results: list[dict[str, Any]] = []
    total_chunks_done = 0

    try:
        for model_index, model_name in enumerate(req.models):
            if _benchmark_cancelled.is_set():
                raise RuntimeError("benchmark_cancelled")

            pipeline = _build_pipeline_for_model(model_name, req.api_config)
            gold_union: set[tuple[str, str, str]] = set()
            predicted_union: set[tuple[str, str, str]] = set()
            outputs: list[dict[str, Any]] = []
            parse_success = 0
            _benchmark_log("info", f"开始模型 {model_name} ({model_index + 1}/{len(req.models)})")

            with _benchmark_lock:
                _benchmark_job["phase"] = "running"
                _benchmark_job["current_model"] = model_name
                _benchmark_job["current_chunk"] = None
                for row in _benchmark_job["results"]:
                    if row["model"] == model_name:
                        row["status"] = "running"
                        row["error"] = ""
                        break

            for task in tasks:
                if _benchmark_cancelled.is_set():
                    raise RuntimeError("benchmark_cancelled")

                gold_keys = {_triple_key(item) for item in GOLD.get(task.chunk_index, [])}
                gold_union |= gold_keys

                with _benchmark_lock:
                    _benchmark_job["current_chunk"] = task.chunk_index
                    for row in _benchmark_job["results"]:
                        if row["model"] == model_name:
                            row["current_chunk"] = task.chunk_index
                            break

                _benchmark_log("info", f"  [{model_name}] chunk {task.chunk_index} 开始")
                one_start = time.perf_counter()
                error = ""
                payload_for_audit: Any = None
                raw_meta: dict[str, Any] = {}
                normalized_rows: list[dict[str, Any]] = []

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

                elapsed_one = time.perf_counter() - one_start
                predicted_keys = {_triple_key(item) for item in normalized_rows}
                predicted_union |= predicted_keys
                tp_keys = sorted(predicted_keys & gold_keys)
                fp_keys = sorted(predicted_keys - gold_keys)
                fn_keys = sorted(gold_keys - predicted_keys)
                tp = len(tp_keys)
                fp = len(fp_keys)
                fn = len(fn_keys)
                precision = tp / (tp + fp) if (tp + fp) else 0.0
                recall = tp / (tp + fn) if (tp + fn) else 0.0
                f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
                usage = raw_meta.get("usage", {}) if isinstance(raw_meta, dict) else {}

                outputs.append(
                    {
                        "chunk_index": task.chunk_index,
                        "chapter_name": task.chapter_name,
                        "elapsed_sec": elapsed_one,
                        "triples_count": len(normalized_rows),
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                        "tp": tp,
                        "fp": fp,
                        "fn": fn,
                        "error": error,
                        "usage": usage,
                        "raw_payload": payload_for_audit,
                        "raw_response_text": raw_meta.get("raw_text", "") if isinstance(raw_meta, dict) else "",
                        "raw_response_format_mode": raw_meta.get("response_format_mode", "") if isinstance(raw_meta, dict) else "",
                        "predicted_rows": normalized_rows,
                        "tp_examples": [_format_triple(item) for item in tp_keys[:5]],
                        "fp_examples": [_format_triple(item) for item in fp_keys[:5]],
                        "fn_examples": [_format_triple(item) for item in fn_keys[:5]],
                        "low_yield": len(normalized_rows) <= 1,
                    }
                )

                total_chunks_done += 1
                latency_mean = statistics.mean(row["elapsed_sec"] for row in outputs)
                total_triples = sum(row["triples_count"] for row in outputs)
                low_yield = sum(1 for row in outputs if row["low_yield"])

                with _benchmark_lock:
                    elapsed = time.time() - start_ts
                    _benchmark_job["chunks_completed"] = total_chunks_done
                    _benchmark_job["elapsed_secs"] = int(elapsed)
                    rate = total_chunks_done / max(elapsed, 1.0)
                    remaining = max(0.0, (_benchmark_job["chunks_total"] - total_chunks_done) / rate) if rate > 0 else 0.0
                    _benchmark_job["eta"] = _fmt_eta(remaining) if total_chunks_done > 0 else ""
                    _benchmark_job["speed_chunks_per_min"] = round(rate * 60, 2) if total_chunks_done > 0 else 0.0
                    for row in _benchmark_job["results"]:
                        if row["model"] == model_name:
                            row["completed_chunks"] = len(outputs)
                            row["current_chunk"] = task.chunk_index
                            row["mean_latency_sec"] = round(latency_mean, 3)
                            row["total_triples"] = total_triples
                            row["low_yield_chunks"] = low_yield
                            row["parse_success_rate"] = round(parse_success / len(outputs), 4)
                            row["error"] = error
                            break

                _benchmark_log(
                    "info" if not error else "warn",
                    f"  [{model_name}] chunk {task.chunk_index} 完成 | triples={len(normalized_rows)} | latency={elapsed_one:.2f}s"
                    + (f" | error={error}" if error else ""),
                )
                _write_json(state_path, _snapshot_state())

            tp_total = len(predicted_union & gold_union)
            fp_total = len(predicted_union - gold_union)
            fn_total = len(gold_union - predicted_union)
            precision_total = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
            recall_total = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
            f1_total = (2 * precision_total * recall_total / (precision_total + recall_total)) if (precision_total + recall_total) else 0.0
            latencies = [row["elapsed_sec"] for row in outputs]
            completion_tokens_total = sum(int(row["usage"].get("completion_tokens", 0) or 0) for row in outputs)
            total_triples = sum(row["triples_count"] for row in outputs)
            model_result = {
                "model": model_name,
                "outputs": outputs,
                "parse_success_rate": parse_success / len(tasks),
                "total_triples": total_triples,
                "mean_triples_per_chunk": total_triples / len(tasks),
                "low_yield_chunks": sum(1 for row in outputs if row["low_yield"]),
                "latency_mean_sec": statistics.mean(latencies),
                "latency_median_sec": statistics.median(latencies),
                "latency_max_sec": max(latencies),
                "completion_tokens_total": completion_tokens_total,
                "completion_tokens_per_triple": (completion_tokens_total / total_triples) if total_triples else 0.0,
                "precision": precision_total,
                "recall": recall_total,
                "f1": f1_total,
                "tp": tp_total,
                "fp": fp_total,
                "fn": fn_total,
            }
            model_results.append(model_result)
            result_file = f"{_safe_model_filename(model_name)}.json"
            model_result["result_file"] = result_file
            _write_json(run_dir / result_file, model_result)

            with _benchmark_lock:
                _benchmark_job["models_completed"] += 1
                for row in _benchmark_job["results"]:
                    if row["model"] == model_name:
                        row["status"] = "completed"
                        row["current_chunk"] = None
                        row["precision"] = round(precision_total, 4)
                        row["recall"] = round(recall_total, 4)
                        row["f1"] = round(f1_total, 4)
                        row["parse_success_rate"] = round(parse_success / len(tasks), 4)
                        row["mean_latency_sec"] = round(statistics.mean(latencies), 3)
                        row["total_triples"] = total_triples
                        row["low_yield_chunks"] = sum(1 for one in outputs if one["low_yield"])
                        row["error"] = ""
                        break
                _benchmark_job["ranking"] = _rank_results(model_results, len(tasks))

            _benchmark_log("info", f"完成模型 {model_name} | F1={f1_total:.3f} | recall={recall_total:.3f} | mean_latency={statistics.mean(latencies):.2f}s")
            _write_json(state_path, _snapshot_state())

        ranked = _rank_results(model_results, len(tasks))
        report_path = _render_report(run_dir, _snapshot_state(), ranked)
        final_state = _snapshot_state()
        final_state["status"] = "completed"
        final_state["phase"] = "finished"
        final_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        final_state["current_model"] = ""
        final_state["current_chunk"] = None
        final_state["ranking"] = ranked
        final_state["report_path"] = str(report_path)
        with _benchmark_lock:
            _benchmark_job = final_state
        _write_json(results_path, {"ranking": ranked, "report_path": str(report_path)})
        _write_json(state_path, final_state)
        _benchmark_log("info", f"模型实验完成，共比较 {len(model_results)} 个模型")
    except RuntimeError as exc:
        if str(exc) == "benchmark_cancelled":
            cancelled_state = _snapshot_state()
            cancelled_state["status"] = "cancelled"
            cancelled_state["phase"] = "cancelled"
            cancelled_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            cancelled_state["current_model"] = ""
            cancelled_state["current_chunk"] = None
            with _benchmark_lock:
                _benchmark_job = cancelled_state
            _write_json(state_path, cancelled_state)
            _write_json(results_path, {"ranking": cancelled_state.get("ranking", []), "partial": True})
            _benchmark_log("warn", "模型实验已取消，已保留当前结果")
        else:
            raise
    except Exception as exc:
        error_state = _snapshot_state()
        error_state["status"] = "error"
        error_state["phase"] = "error"
        error_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        error_state["error"] = str(exc)
        error_state["current_model"] = ""
        error_state["current_chunk"] = None
        with _benchmark_lock:
            _benchmark_job = error_state
        _write_json(state_path, error_state)
        _benchmark_log("error", f"模型实验失败: {exc}")
    finally:
        if _benchmark_cancelled.is_set():
            _benchmark_cancelled.clear()


@router.get("/api/benchmark/config")
def benchmark_config() -> dict[str, Any]:
    return {
        "default_book_name": DEFAULT_BENCHMARK_BOOK,
        "default_chunk_ids": DEFAULT_BENCHMARK_CHUNK_IDS,
        "default_models": DEFAULT_BENCHMARK_MODELS,
        "default_api_config": BenchmarkApiConfig().model_dump(),
        "output_root": str(DEFAULT_OUTPUT_ROOT),
        "gold_total": sum(len(rows) for rows in GOLD.values()),
        "notes": {
            "evaluation_mode": "gold_benchmark_fixed",
            "cost_included": False,
            "accuracy_available": True,
        },
    }


@router.post("/api/benchmark/start")
def start_benchmark(req: BenchmarkStartRequest) -> dict[str, Any]:
    global _benchmark_thread, _benchmark_job, _benchmark_logs
    with _benchmark_lock:
        if _benchmark_thread and _benchmark_thread.is_alive():
            raise HTTPException(status_code=409, detail="已有模型实验在运行中")
        _benchmark_logs = []
        _benchmark_job = {
            "status": "starting",
            "phase": "starting",
            "models": list(req.models),
            "book_name": req.book_name,
            "chunk_ids": list(req.chunk_ids),
        }
    _benchmark_cancelled.clear()
    job_id = uuid4().hex[:8]
    worker = threading.Thread(target=_run_benchmark_job, args=(job_id, req), daemon=True)
    _benchmark_thread = worker
    worker.start()
    return {"ok": True, "job_id": job_id, "models": req.models, "book_name": req.book_name, "chunk_ids": req.chunk_ids}


@router.post("/api/benchmark/cancel")
def cancel_benchmark() -> dict[str, Any]:
    with _benchmark_lock:
        if not (_benchmark_thread and _benchmark_thread.is_alive()):
            return {"ok": True, "message": "no_active_benchmark"}
    _benchmark_cancelled.set()
    _benchmark_log("warn", "收到用户取消模型实验请求")
    return {"ok": True, "message": "cancel_requested"}


@router.get("/api/benchmark/status")
def benchmark_status() -> dict[str, Any]:
    snapshot = _snapshot_state()
    if not snapshot:
        return {"status": "idle", "phase": "idle", "results": [], "ranking": []}
    return snapshot


@router.get("/api/benchmark/results")
def benchmark_results() -> dict[str, Any]:
    snapshot = _snapshot_state()
    if not snapshot:
        raise HTTPException(status_code=404, detail="benchmark_not_found")
    return {
        "status": snapshot.get("status", "idle"),
        "run_dir": snapshot.get("run_dir", ""),
        "report_path": snapshot.get("report_path", ""),
        "ranking": snapshot.get("ranking", []),
        "results": snapshot.get("results", []),
    }


@router.get("/api/benchmark/history")
def benchmark_history(limit: int = 50) -> dict[str, Any]:
    return {"runs": _list_history_runs(limit=max(1, min(limit, 200)))}


@router.get("/api/benchmark/history/{run_name}")
def benchmark_history_detail(run_name: str) -> dict[str, Any]:
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


@router.get("/api/benchmark/model")
def benchmark_model_detail(name: str, run_name: str = "") -> dict[str, Any]:
    if run_name:
        run_dir = DEFAULT_OUTPUT_ROOT / run_name
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail="benchmark_run_not_found")
    else:
        snapshot = _snapshot_state()
        run_dir = Path(str(snapshot.get("run_dir", "") or ""))
        if not str(run_dir):
            raise HTTPException(status_code=404, detail="benchmark_not_found")
    path = run_dir / f"{_safe_model_filename(name)}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="model_result_not_found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/benchmark/stream")
def benchmark_stream():
    def event_gen():
        last_index = 0
        while True:
            with _benchmark_lock:
                state = json.loads(json.dumps(_benchmark_job, ensure_ascii=False))
                logs = _benchmark_logs[last_index:]
                last_index = len(_benchmark_logs)
            yield f"data: {json.dumps({'state': state, 'logs': logs}, ensure_ascii=False)}\n\n"
            if state.get("status") in {"completed", "error", "cancelled", "idle"}:
                break
            time.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
