from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.tcm_triple_console import (
    DEFAULT_OUTPUT_DIR,
    PipelineConfig,
    TCMTriplePipeline,
    _detect_formula_titles,
    _extract_all_json_blocks,
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
    base_url = manifest.get("base_url") or _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("missing_llm_api_key")
    pipeline = TCMTriplePipeline(
        PipelineConfig(
            books_dir=Path(config.get("books_dir") or manifest.get("books_dir") or _first_env("TRIPLE_BOOKS_DIR", default="") or Path.cwd()),
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
    return pipeline


def _resolve_book_path(manifest: dict[str, Any], book_name: str) -> Path:
    book_paths = [Path(item) for item in manifest.get("books", []) if str(item).strip()]
    for path in book_paths:
        if path.stem == book_name or path.name == book_name:
            return path
    raise FileNotFoundError(f"book_not_found_in_manifest: {book_name}")


def _resolve_task(
    pipeline: TCMTriplePipeline,
    *,
    manifest: dict[str, Any],
    book_name: str,
    chunk_index: int,
) -> Any:
    config = manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}
    book_path = _resolve_book_path(manifest, book_name)
    tasks = pipeline.schedule_book_chunks(
        book_path=book_path,
        chapter_excludes=config.get("chapter_excludes") or None,
        max_chunks_per_book=None,
        skip_initial_chunks_per_book=int(config.get("skip_initial_chunks_per_book", 0)),
        chunk_strategy=str(config.get("chunk_strategy", "body_first")),
    )
    for task in tasks:
        if int(task.chunk_index) == chunk_index:
            return task
    raise ValueError(f"chunk_not_found: {book_name}#{chunk_index}")


def _summarize_mode(
    pipeline: TCMTriplePipeline,
    *,
    task: Any,
    prompt_variant: str,
    response_mode: str,
) -> dict[str, Any]:
    prompt = pipeline.build_prompt_variant(
        book_name=task.book_name,
        chapter_name=task.chapter_name,
        text_chunk=task.text_chunk,
        variant=prompt_variant,
    )
    raw = pipeline.call_llm_raw(prompt, response_format_mode=response_mode)
    raw_text = str(raw.get("raw_text", ""))

    first_payload: Any = None
    first_error = ""
    try:
        first_payload = _extract_json_block(raw_text)
    except Exception as exc:
        first_error = str(exc)

    all_payloads = _extract_all_json_blocks(raw_text)
    first_triples = _extract_payload_triples(first_payload)
    all_counts = [len(_extract_payload_triples(item)) for item in all_payloads]
    all_total = sum(all_counts)

    diagnosis = "model_only_first_or_low_yield"
    if all_total > len(first_triples):
        diagnosis = "parser_only_read_first_json_block"
    elif len(all_payloads) == 0:
        diagnosis = "format_not_json_or_parse_failed"
    elif len(first_triples) > 1:
        diagnosis = "not_low_yield_in_raw_output"

    return {
        "prompt_variant": prompt_variant,
        "response_mode": response_mode,
        "prompt_chars": len(prompt),
        "response_format_mode": raw.get("response_format_mode"),
        "finish_reason": raw.get("finish_reason"),
        "usage": raw.get("usage", {}),
        "raw_text_length": len(raw_text),
        "raw_subject_token_count": raw_text.count('"subject"'),
        "first_block_triples": len(first_triples),
        "all_json_blocks": len(all_payloads),
        "all_blocks_triple_counts": all_counts,
        "all_blocks_total_triples": all_total,
        "first_parse_error": first_error,
        "diagnosis": diagnosis,
        "raw_text_preview": raw_text[:1200],
        "raw_text": raw_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose low-yield triple extraction on a specific chunk.")
    parser.add_argument("--run-name", required=True, help="Run directory name under storage/triple_pipeline")
    parser.add_argument("--book-name", required=True, help="Book stem, for example 089-医方论")
    parser.add_argument("--chunk-index", required=True, type=int, help="Chunk index within the selected book")
    parser.add_argument("--output-dir", default="", help="Optional output directory for the diagnostic report")
    parser.add_argument("--prompt-variants", default="current,compact", help="Comma-separated prompt variants")
    parser.add_argument("--response-modes", default="json_object,text", help="Comma-separated response modes")
    args = parser.parse_args()

    run_dir, manifest = _load_run_manifest(args.run_name)
    pipeline = _build_pipeline_from_manifest(manifest)
    task = _resolve_task(
        pipeline,
        manifest=manifest,
        book_name=args.book_name,
        chunk_index=int(args.chunk_index),
    )

    prompt_variants = [item.strip() for item in str(args.prompt_variants).split(",") if item.strip()]
    response_modes = [item.strip() for item in str(args.response_modes).split(",") if item.strip()]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(args.output_dir) if args.output_dir else (run_dir / f"diagnostics_{args.book_name}_{args.chunk_index}_{timestamp}")
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for prompt_variant in prompt_variants:
        for response_mode in response_modes:
            try:
                result = _summarize_mode(
                    pipeline,
                    task=task,
                    prompt_variant=prompt_variant,
                    response_mode=response_mode,
                )
            except Exception as exc:
                result = {
                    "prompt_variant": prompt_variant,
                    "response_mode": response_mode,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            safe_name = f"{prompt_variant}_{response_mode}".replace("/", "_")
            if "raw_text" in result:
                (report_dir / f"{safe_name}.raw.txt").write_text(str(result["raw_text"]), encoding="utf-8")
            slim = dict(result)
            slim.pop("raw_text", None)
            (report_dir / f"{safe_name}.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(slim)

    summary = {
        "run_name": args.run_name,
        "book_name": args.book_name,
        "chunk_index": int(args.chunk_index),
        "chapter_name": task.chapter_name,
        "chunk_chars": len(task.text_chunk),
        "formula_title_hints": _detect_formula_titles(task.text_chunk),
        "results": results,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report_dir": str(report_dir), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
