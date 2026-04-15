from __future__ import annotations

import argparse
import json
import re
import sys
import time
from queue import Empty, Queue
from pathlib import Path
from threading import Thread
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.tcm_triple_console import LLMProviderConfig, PipelineConfig, TCMTriplePipeline, _first_env
from services.retrieval_service.engine import get_retrieval_engine
from services.retrieval_service.files_first_support import SectionSummaryCache, build_section_key, extract_book_name, extract_chapter_title


def _group_sections(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text", "") or "")
        filename = str(row.get("filename", "") or "")
        file_path = str(row.get("file_path", "") or "")
        page_number = int(row.get("page_number", 0) or 0)
        book_name = str(row.get("book_name", "") or "").strip() or extract_book_name(
            text=text,
            filename=filename,
            file_path=file_path,
        )
        chapter_title = str(row.get("chapter_title", "") or "").strip() or extract_chapter_title(
            text=text,
            page_number=page_number,
            file_path=file_path,
        )
        section_key = str(row.get("section_key", "")).strip() or build_section_key(
            book_name=book_name,
            chapter_title=chapter_title,
            page_number=page_number,
            file_path=file_path,
        )
        if not section_key:
            continue
        bucket = grouped.setdefault(
            section_key,
            {"book_name": book_name, "chapter_title": chapter_title, "parts": []},
        )
        bucket["parts"].append(text)
    return grouped


def _build_prompt(book_name: str, chapter_title: str, section_text: str) -> str:
    compact = str(section_text or "").replace("\n", " ").strip()[:2400]
    return (
        "请为一段中医古籍章节生成结构化摘要缓存。"
        "仅输出 JSON 对象，字段固定为 section_summary、topic_tags、entity_tags、representative_passages。"
        "要求："
        "section_summary 不超过120字；"
        "topic_tags 不超过8个且尽量是中医主题词；"
        "entity_tags 不超过8个且尽量是方剂/药物/证候等实体；"
        "representative_passages 不超过2条且每条不超过60字。"
        f"\n书名：{book_name}\n篇名：{chapter_title}\n正文：{compact}"
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    if cleaned.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", cleaned)
        stripped = re.sub(r"\s*```$", "", stripped)
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_summary": str(payload.get("section_summary", "")).strip()[:240],
        "topic_tags": [
            str(item).strip()
            for item in payload.get("topic_tags", [])
            if str(item).strip()
        ][:8]
        if isinstance(payload.get("topic_tags", []), list)
        else [],
        "entity_tags": [
            str(item).strip()
            for item in payload.get("entity_tags", [])
            if str(item).strip()
        ][:8]
        if isinstance(payload.get("entity_tags", []), list)
        else [],
        "representative_passages": [
            str(item).strip()[:120]
            for item in payload.get("representative_passages", [])
            if str(item).strip()
        ][:2]
        if isinstance(payload.get("representative_passages", []), list)
        else [],
    }


def _build_summary_pipeline(*, provider_scope: str, request_timeout: float, max_retries: int, request_delay: float) -> TCMTriplePipeline:
    model = _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="mimo-v2-pro")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    pipeline = TCMTriplePipeline(
        PipelineConfig(
            books_dir=BACKEND_ROOT / "tmp_books_unused",
            output_dir=BACKEND_ROOT / "storage" / "section_summary_pipeline_runtime",
            model=model,
            api_key=api_key,
            base_url=base_url,
            providers=tuple(),
            request_timeout=request_timeout,
            max_retries=max_retries,
            request_delay=request_delay,
            parallel_workers=1,
        )
    )
    if provider_scope == "jmrai":
        filtered = tuple(provider for provider in pipeline.config.providers if provider.name.startswith("jmrai"))
        if not filtered:
            raise RuntimeError("no_jmrai_providers_configured")
        pipeline.config.providers = filtered
        pipeline._providers_by_name = {provider.name: provider for provider in filtered}
        pipeline._provider_rotation = [
            provider.name
            for provider in filtered
            for _ in range(max(1, int(provider.weight)))
            if provider.enabled
        ] or [provider.name for provider in filtered if provider.enabled]
        pipeline._provider_stats = {
            provider.name: {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_error": "",
                "last_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "latency_sample_count": 0,
            }
            for provider in filtered
        }
    return pipeline


def _build_provider_pipelines(*, provider_scope: str, request_timeout: float, max_retries: int, request_delay: float, workers_per_provider: int) -> list[tuple[str, TCMTriplePipeline]]:
    base = _build_summary_pipeline(
        provider_scope=provider_scope,
        request_timeout=request_timeout,
        max_retries=max_retries,
        request_delay=request_delay,
    )
    providers = list(base.config.providers)
    if not providers:
        return []
    workers_per_provider = max(1, int(workers_per_provider) or 1)
    worker_count = max(1, len(providers) * workers_per_provider)
    pipelines: list[tuple[str, TCMTriplePipeline]] = []
    for index in range(worker_count):
        provider = providers[index % len(providers)]
        pipeline = TCMTriplePipeline(
            PipelineConfig(
                books_dir=base.config.books_dir,
                output_dir=base.config.output_dir / f"worker_{index+1}_{provider.name}",
                model=provider.model,
                api_key=provider.api_key,
                base_url=provider.base_url,
                providers=(provider,),
                request_timeout=request_timeout,
                max_retries=max_retries,
                request_delay=request_delay,
                parallel_workers=1,
            )
        )
        pipelines.append((provider.name, pipeline))
    return pipelines


def _print_progress(*, processed: int, target_total: int, success: int, failed: int, skipped: int, last_section: str, provider_name: str, latency_ms: float, provider_summary: str) -> None:
    width = 28
    ratio = 0.0 if target_total <= 0 else min(1.0, processed / target_total)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    eta_text = "-"
    if hasattr(_print_progress, "_started_at"):
        started_at = getattr(_print_progress, "_started_at")
        elapsed = max(time.perf_counter() - started_at, 0.001)
        session_generated = success + failed
        if session_generated > 0 and target_total > processed:
            rate = session_generated / elapsed
            if rate > 0:
                remaining_seconds = (target_total - processed) / rate
                hours = int(remaining_seconds // 3600)
                minutes = int((remaining_seconds % 3600) // 60)
                seconds = int(remaining_seconds % 60)
                eta_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    print(
        f"[summary-cache] [{bar}] {processed}/{target_total} "
        f"ok={success} fail={failed} skip={skipped} "
        f"eta={eta_text} "
        f"provider={provider_name or '-'} latency={latency_ms:.0f}ms "
        f"section={last_section}",
        flush=True,
    )
    print(f"[summary-cache] providers: {provider_summary}", flush=True)


def _provider_metrics_summary(worker_pipelines: list[tuple[str, TCMTriplePipeline]]) -> str:
    aggregated: dict[str, dict[str, Any]] = {}
    for _, pipeline in worker_pipelines:
        metrics = pipeline.get_provider_metrics()
        if not metrics:
            continue
        item = metrics[0]
        bucket = aggregated.setdefault(
            item["name"],
            {
                "success_count": 0,
                "failure_count": 0,
                "latency_weighted": 0.0,
                "latency_samples": 0,
                "last_latency_ms": 0.0,
                "workers": 0,
            },
        )
        bucket["workers"] += 1
        bucket["success_count"] += int(item["success_count"])
        bucket["failure_count"] += int(item["failure_count"])
        attempts = int(item["attempt_count"])
        bucket["latency_weighted"] += float(item["avg_latency_ms"]) * attempts
        bucket["latency_samples"] += attempts
        bucket["last_latency_ms"] = float(item["last_latency_ms"])
    parts: list[str] = []
    for name, item in aggregated.items():
        attempts = int(item["success_count"]) + int(item["failure_count"])
        success_rate = (float(item["success_count"]) / attempts) if attempts else 0.0
        failure_rate = (float(item["failure_count"]) / attempts) if attempts else 0.0
        avg_latency_ms = (float(item["latency_weighted"]) / float(item["latency_samples"])) if item["latency_samples"] else 0.0
        parts.append(
            f"{name} workers={item['workers']} ok={item['success_count']} fail={item['failure_count']} "
            f"succ={success_rate:.1%} failr={failure_rate:.1%} "
            f"avg={avg_latency_ms:.0f}ms last={item['last_latency_ms']:.0f}ms"
        )
    return " | ".join(parts) if parts else "provider-monitor: none"


def _summary_worker(*, worker_id: int, pipeline: TCMTriplePipeline, cache_store: SectionSummaryCache, task_queue: Queue, result_queue: Queue) -> None:
    while True:
        item = task_queue.get()
        if item is None:
            task_queue.task_done()
            return
        section_key, section_item = item
        prompt = _build_prompt(
            str(section_item.get("book_name", "")),
            str(section_item.get("chapter_title", "")),
            "\n".join(str(part) for part in section_item.get("parts", [])[:4]),
        )
        provider_name = ""
        latency_ms = 0.0
        try:
            meta = pipeline.call_llm_raw(prompt, response_format_mode="json_object")
            provider_name = str(meta.get("provider_name", "")).strip()
            latency_ms = float(meta.get("provider_latency_ms", 0.0) or 0.0)
            parsed = _extract_json_object(str(meta.get("raw_text", "")))
            if not isinstance(parsed, dict):
                raise ValueError("summary_response_not_json_object")
            normalized_payload = _normalize_summary_payload(parsed)
            cache_store.set(section_key, normalized_payload)
            result_queue.put(
                {
                    "worker_id": worker_id,
                    "section_key": section_key,
                    "ok": True,
                    "provider_name": provider_name,
                    "latency_ms": latency_ms,
                    "payload": normalized_payload,
                }
            )
        except Exception as exc:
            result_queue.put(
                {
                    "worker_id": worker_id,
                    "section_key": section_key,
                    "ok": False,
                    "provider_name": provider_name,
                    "latency_ms": latency_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            task_queue.task_done()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline section summary cache with triple-pipeline providers.")
    parser.add_argument("--corpus", default="services/retrieval_service/data/classic_books_corpus.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--provider-scope", choices=("jmrai", "all"), default="jmrai")
    parser.add_argument("--request-timeout", type=float, default=90.0)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--request-delay", type=float, default=0.3)
    parser.add_argument("--workers-per-provider", type=int, default=16)
    parser.add_argument("--parallel-workers", type=int, default=0, help="Deprecated total worker override. When >0, overrides workers-per-provider.")
    parser.add_argument("--resume", action="store_true", help="Skip sections already present in cache.")
    parser.add_argument("--only-missing", action="store_true", help="Only schedule sections missing from cache instead of scanning all sections.")
    args = parser.parse_args()

    engine = get_retrieval_engine()
    corpus_path = (BACKEND_ROOT / args.corpus).resolve() if not Path(args.corpus).is_absolute() else Path(args.corpus)
    rows = engine._load_corpus_file(corpus_path)
    grouped = _group_sections(rows)
    cache_path = engine.settings.section_summary_cache_path
    cache_store = SectionSummaryCache(cache_path)
    cached_existing = cache_store.count()
    existing_keys = set(cache_store.load().keys()) if args.resume or args.only_missing else set()

    requested_workers_per_provider = max(1, int(args.workers_per_provider))
    if int(args.parallel_workers or 0) > 0:
        base_preview = _build_summary_pipeline(
            provider_scope=args.provider_scope,
            request_timeout=args.request_timeout,
            max_retries=args.max_retries,
            request_delay=args.request_delay,
        )
        provider_count = max(1, len(base_preview.config.providers))
        requested_workers_per_provider = max(1, int(args.parallel_workers) // provider_count)

    pipelines = _build_provider_pipelines(
        provider_scope=args.provider_scope,
        request_timeout=args.request_timeout,
        max_retries=args.max_retries,
        request_delay=args.request_delay,
        workers_per_provider=requested_workers_per_provider,
    )
    if not pipelines:
        raise RuntimeError("no_summary_providers_available")
    provider_names = [name for name, _ in pipelines]
    print(
        json.dumps(
            {
                "provider_scope": args.provider_scope,
                "providers": provider_names,
                "workers_per_provider": requested_workers_per_provider,
                "parallel_workers": len(pipelines),
                "cache_path": str(cache_path),
                "sections_total": len(grouped),
                "sections_cached_existing": cached_existing,
                "only_missing": bool(args.only_missing),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    pending_items: list[tuple[str, dict[str, Any]]] = []
    if args.only_missing:
        for section_key, item in grouped.items():
            if section_key in existing_keys:
                continue
            pending_items.append((section_key, item))
        target_total = min(max(1, int(args.limit)), max(1, len(pending_items)))
    else:
        pending_items = list(grouped.items())
        target_total = max(1, int(args.limit))
    success = 0
    failed = 0
    skipped = 0
    processed = 0
    setattr(_print_progress, "_started_at", time.perf_counter())
    task_queue: Queue = Queue()
    result_queue: Queue = Queue()
    workers: list[Thread] = []
    for index, (_, pipeline) in enumerate(pipelines, start=1):
        worker = Thread(
            target=_summary_worker,
            kwargs={"worker_id": index, "pipeline": pipeline, "cache_store": cache_store, "task_queue": task_queue, "result_queue": result_queue},
            daemon=True,
        )
        worker.start()
        workers.append(worker)

    scheduled = 0
    for section_key, item in pending_items:
        if processed + scheduled >= target_total:
            break
        if (args.resume and not args.only_missing) and section_key in existing_keys:
            skipped += 1
            processed += 1
            _print_progress(
                processed=processed,
                target_total=target_total,
                success=success,
                failed=failed,
                skipped=skipped,
                last_section=section_key,
                provider_name="cache",
                latency_ms=0.0,
                provider_summary=_provider_metrics_summary(pipelines),
            )
            continue
        task_queue.put((section_key, item))
        scheduled += 1

    while processed < target_total and (scheduled > 0):
        try:
            result = result_queue.get(timeout=5.0)
        except Empty:
            _print_progress(
                processed=processed,
                target_total=target_total,
                success=success,
                failed=failed,
                skipped=skipped,
                last_section="waiting",
                provider_name="-",
                latency_ms=0.0,
                provider_summary=_provider_metrics_summary(pipelines),
            )
            continue
        scheduled -= 1
        section_key = str(result.get("section_key", "") or "")
        provider_name = str(result.get("provider_name", "") or "")
        latency_ms = float(result.get("latency_ms", 0.0) or 0.0)
        if result.get("ok") and section_key:
            success += 1
        else:
            failed += 1
        processed += 1
        _print_progress(
            processed=processed,
            target_total=target_total,
            success=success,
            failed=failed,
            skipped=skipped,
            last_section=section_key,
            provider_name=provider_name,
            latency_ms=latency_ms,
            provider_summary=_provider_metrics_summary(pipelines),
        )

    for _ in workers:
        task_queue.put(None)
    for worker in workers:
        worker.join(timeout=1.0)

    print(
        json.dumps(
            {
                "cache_path": str(cache_path),
                "provider_scope": args.provider_scope,
                "providers": provider_names,
                "workers_per_provider": requested_workers_per_provider,
                "parallel_workers": len(pipelines),
                "sections_total": len(grouped),
                "sections_processed_target": target_total,
                "sections_success": success,
                "sections_failed": failed,
                "sections_skipped": skipped,
                "sections_cached_total": cache_store.count(),
                "provider_summary": _provider_metrics_summary(pipelines),
                "only_missing": bool(args.only_missing),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
