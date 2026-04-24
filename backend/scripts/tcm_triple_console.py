from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

import httpx

from services.triple_pipeline_service import (
    DEFAULT_BOOKS_DIR,
    DEFAULT_CHAPTER_EXCLUDES,
    DEFAULT_GRAPH_BASE,
    DEFAULT_GRAPH_TARGET,
    DEFAULT_OUTPUT_DIR,
    GRAPH_RUNTIME_IO_LOCK,
    LLMProviderConfig,
    PipelineConfig,
    TCMTriplePipeline,
    TripleRecord,
    _dedupe_evidence_rows,
    _dedupe_graph_rows,
    _derive_evidence_target_path,
    _detect_formula_titles,
    _extract_all_json_blocks,
    _extract_fact_ids,
    _extract_json_block,
    _extract_payload_triples,
    _first_env,
    _load_json_file,
    _load_json_file_strict,
    _load_jsonl_rows,
    _merge_keywords,
    _normalize_provider_configs,
    _provider_to_dict,
    _safe_read_text,
    _split_keywords,
    _write_text_atomic,
)

__all__ = [
    "DEFAULT_BOOKS_DIR",
    "DEFAULT_CHAPTER_EXCLUDES",
    "DEFAULT_GRAPH_BASE",
    "DEFAULT_GRAPH_TARGET",
    "DEFAULT_OUTPUT_DIR",
    "GRAPH_RUNTIME_IO_LOCK",
    "LLMProviderConfig",
    "PipelineConfig",
    "TCMTriplePipeline",
    "TripleRecord",
    "_dedupe_evidence_rows",
    "_dedupe_graph_rows",
    "_derive_evidence_target_path",
    "_detect_formula_titles",
    "_extract_all_json_blocks",
    "_extract_fact_ids",
    "_extract_json_block",
    "_extract_payload_triples",
    "_first_env",
    "_load_json_file",
    "_load_json_file_strict",
    "_load_jsonl_rows",
    "_merge_keywords",
    "_normalize_provider_configs",
    "_provider_to_dict",
    "_safe_read_text",
    "_split_keywords",
    "_write_text_atomic",
    "httpx",
    "os",
    "time",
]


def build_config(args: argparse.Namespace) -> PipelineConfig:
    model = args.model or _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="mimo-v2-pro")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    if not api_key and not args.dry_run:
        raise RuntimeError("missing_llm_api_key")
    providers = _normalize_provider_configs(
        [],
        fallback_model=model,
        fallback_api_key=api_key,
        fallback_base_url=base_url,
    )

    return PipelineConfig(
        books_dir=Path(args.books_dir) if args.books_dir else DEFAULT_BOOKS_DIR,
        output_dir=Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR,
        model=model,
        api_key=api_key,
        base_url=base_url,
        providers=providers,
        request_timeout=float(args.timeout),
        max_chunk_chars=int(args.max_chunk_chars),
        chunk_overlap=int(args.chunk_overlap),
        max_retries=int(args.max_retries),
        request_delay=float(args.request_delay),
        parallel_workers=max(1, int(args.parallel_workers)),
        retry_backoff_base=float(args.retry_backoff_base),
        chunk_strategy=str(args.chunk_strategy or "body_first"),
    )


def print_books(books: list[Path]) -> None:
    for index, book in enumerate(books, start=1):
        print(f"{index:>3}. {book.stem}")


def print_run_summary(summary: dict[str, Any]) -> None:
    print(f"run_dir: {summary.get('run_dir', '')}")
    print(f"status: {summary.get('status', '')}")
    print(f"books: {summary.get('books_completed', 0)}/{summary.get('books_total', 0)}")
    print(f"triples: {summary.get('total_triples', 0)}")
    print(f"dry_run: {summary.get('dry_run', False)}")
    if summary.get("model"):
        print(f"model: {summary['model']}")


def print_run_audit(audit: dict[str, Any]) -> None:
    print_run_summary(audit.get("summary", {}))
    config = audit.get("config", {})
    print(f"chapter_excludes: {config.get('chapter_excludes', [])}")
    print(f"skip_initial_chunks_per_book: {config.get('skip_initial_chunks_per_book', 0)}")
    print(f"chunk_strategy: {config.get('chunk_strategy', 'body_first')}")
    print(f"parallel_workers: {config.get('parallel_workers', 1)}")
    if audit.get("sample_chapters"):
        print(f"sample_chapters: {audit['sample_chapters']}")
    print("sample_rows:")
    for index, row in enumerate(audit.get("sample_rows", []), start=1):
        print(
            f"{index:>2}. [{row.get('source_chapter', '')}] "
            f"{row.get('subject', '')} -{row.get('predicate', '')}-> {row.get('object', '')}"
        )


def print_clean_report(report: dict[str, Any]) -> None:
    print(f"run_dir: {report.get('run_dir', '')}")
    print(f"input_total: {report.get('input_total', 0)}")
    print(f"kept_total: {report.get('kept_total', 0)}")
    print(f"dropped_total: {report.get('dropped_total', 0)}")
    print("reason_counts:")
    for key, value in sorted((report.get("reason_counts") or {}).items()):
        print(f"  {key}: {value}")


def resolve_selected_books(pipeline: TCMTriplePipeline, raw_value: str, fallback_limit: int) -> list[Path]:
    books = pipeline.discover_books()
    selected: list[Path] = []

    if raw_value.strip():
        tokens = [token.strip() for token in raw_value.split(",") if token.strip()]
        for token in tokens:
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(books):
                    selected.append(books[idx - 1])
            else:
                selected.extend([book for book in books if token in book.stem])
    else:
        selected = pipeline.recommend_books(limit=min(fallback_limit, 6))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in selected:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def resolve_single_book(pipeline: TCMTriplePipeline, raw_value: str) -> Path | None:
    matches = resolve_selected_books(pipeline, raw_value, fallback_limit=1)
    return matches[0] if matches else None


def resolve_chapter_excludes(raw_value: str, use_default_excludes: bool) -> list[str] | None:
    user_excludes = _split_keywords(raw_value)
    default_excludes = DEFAULT_CHAPTER_EXCLUDES if use_default_excludes else []
    merged = _merge_keywords(default_excludes, user_excludes)
    return merged or None


def print_chapters(pipeline: TCMTriplePipeline, book_path: Path, limit: int) -> None:
    print(f"book: {book_path.stem}")
    for index, section in enumerate(pipeline.split_book(book_path)[:limit], start=1):
        print(f"{index:>3}. {section['title']}")


def interactive_main(pipeline: TCMTriplePipeline, args: argparse.Namespace) -> int:
    print("TCM Triple Pipeline Console")
    print(f"books_dir: {pipeline.config.books_dir}")
    print(f"output_dir: {pipeline.config.output_dir}")
    print(f"model: {pipeline.config.model}")
    print(f"base_url: {pipeline.config.base_url}")

    while True:
        print("\n选择操作:")
        print("1. 列出全部书目")
        print("2. 推荐首批书目")
        print("3. 查看某本书的章节")
        print("4. 提取指定书目")
        print("5. 查看最新运行目录")
        print("6. 抽检最新运行结果")
        print("7. 清洗最新运行结果")
        print("8. 发布最新运行到图谱 JSON")
        print("9. 退出")
        choice = input("输入编号: ").strip()

        if choice == "1":
            print_books(pipeline.discover_books())
            continue
        if choice == "2":
            print_books(pipeline.recommend_books())
            continue
        if choice == "3":
            books = pipeline.discover_books()
            print_books(books[:40])
            raw = input("输入单本书的编号或关键词: ").strip()
            book_path = resolve_single_book(pipeline, raw)
            if book_path is None:
                print("未找到对应书目。")
                continue
            print_chapters(pipeline, book_path, limit=40)
            continue
        if choice == "4":
            books = pipeline.discover_books()
            print_books(books[:40])
            raw = input("输入书目编号，逗号分隔；直接回车则使用推荐书单: ").strip()
            selected = resolve_selected_books(pipeline, raw, fallback_limit=6)
            if not selected:
                print("未选择任何书目。")
                continue
            dry_run = input("是否 dry-run（yes/no，默认 no）: ").strip().lower() in {"y", "yes"}
            max_chunks_raw = input("每本最多处理多少 chunk（回车表示不限）: ").strip()
            max_chunks = int(max_chunks_raw) if max_chunks_raw.isdigit() else None
            chapter_contains_raw = input("仅处理包含这些章节关键词（逗号分隔，可空）: ").strip()
            chapter_excludes_raw = input("跳过包含这些章节关键词（逗号分隔，可空；默认不过滤）: ").strip()
            skip_chunks_raw = input("每本书跳过前多少个 chunk（默认 0）: ").strip()
            skip_chunks = int(skip_chunks_raw) if skip_chunks_raw.isdigit() else 0
            strategy_raw = input("切块策略（body_first/chapter_first，默认 body_first）: ").strip().lower() or "body_first"
            workers_raw = input(f"并行 worker 数（默认 {pipeline.config.parallel_workers}）: ").strip()
            parallel_workers = int(workers_raw) if workers_raw.isdigit() else pipeline.config.parallel_workers
            label = input("运行标签（回车默认 interactive）: ").strip() or "interactive"
            pipeline.config.parallel_workers = max(1, parallel_workers)
            pipeline.config.chunk_strategy = strategy_raw
            run_dir = pipeline.extract_books(
                selected_books=selected,
                label=label,
                max_chunks_per_book=max_chunks,
                dry_run=dry_run,
                chapter_contains=_split_keywords(chapter_contains_raw) or None,
                chapter_excludes=resolve_chapter_excludes(chapter_excludes_raw, use_default_excludes=False),
                skip_initial_chunks_per_book=skip_chunks,
                chunk_strategy=strategy_raw,
            )
            print_run_summary(pipeline.summarize_run_dir(run_dir))
            continue
        if choice == "5":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无运行目录")
            else:
                print_run_summary(pipeline.summarize_run_dir(latest))
            continue
        if choice == "6":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可抽检的运行目录")
                continue
            print_run_audit(pipeline.audit_run_dir(latest, limit=8))
            continue
        if choice == "7":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可清洗的运行目录")
                continue
            print_clean_report(pipeline.clean_run_dir(latest))
            continue
        if choice == "8":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可发布的运行目录")
                continue
            target_raw = input(
                f"目标图谱文件（回车默认 {DEFAULT_GRAPH_TARGET}）: "
            ).strip()
            replace = input("是否覆盖目标文件（yes/no，默认 no）: ").strip().lower() in {"y", "yes"}
            target_path = Path(target_raw) if target_raw else DEFAULT_GRAPH_TARGET
            published = pipeline.publish_graph(run_dir=latest, target_path=target_path, replace=replace)
            print(f"已发布到: {published}")
            continue
        if choice == "9":
            return 0
        print("无效输入。")


def cli_main() -> int:
    parser = argparse.ArgumentParser(description="Interactive TCM triple extraction pipeline.")
    parser.add_argument(
        "command",
        nargs="?",
        default="interactive",
        choices=["interactive", "list", "recommend", "chapters", "extract", "latest", "audit-run", "clean-run", "publish-graph"],
    )
    parser.add_argument("--books-dir", default="", help="Books directory.")
    parser.add_argument("--output-dir", default="", help="Output directory.")
    parser.add_argument("--model", default="", help="Override extraction model.")
    parser.add_argument("--timeout", default=90, type=float, help="LLM request timeout.")
    parser.add_argument("--max-chunk-chars", default=800, type=int, help="Max chars per chunk.")
    parser.add_argument("--chunk-overlap", default=200, type=int, help="Chunk overlap chars.")
    parser.add_argument("--max-retries", default=2, type=int, help="LLM request retries.")
    parser.add_argument("--retry-backoff-base", default=2.0, type=float, help="Base seconds for exponential retry backoff.")
    parser.add_argument("--request-delay", default=0.8, type=float, help="Delay between requests.")
    parser.add_argument("--parallel-workers", default=8, type=int, help="Parallel worker count for chunk extraction.")
    parser.add_argument("--chunk-strategy", default="body_first", choices=["body_first", "chapter_first"], help="Chunk scheduling strategy.")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic triples instead of real LLM calls.")
    parser.add_argument("--books", default="", help="Comma-separated book indices or names for extract mode.")
    parser.add_argument("--book", default="", help="Single book index or fuzzy name for chapters mode.")
    parser.add_argument("--limit", default=12, type=int, help="List/recommend limit.")
    parser.add_argument("--max-chunks-per-book", default=0, type=int, help="Limit chunks per book during extraction.")
    parser.add_argument("--label", default="manual", help="Run label.")
    parser.add_argument("--chapter-contains", default="", help="Only process chapters whose title contains these keywords.")
    parser.add_argument("--chapter-excludes", default="", help="Skip chapters whose title contains these keywords.")
    parser.add_argument("--use-default-excludes", action="store_true", help="Append default metadata chapter excludes.")
    parser.add_argument("--no-default-excludes", action="store_true", help="Do not auto-append default metadata chapter excludes.")
    parser.add_argument("--skip-initial-chunks", default=0, type=int, help="Skip the first N chunks per book before extraction.")
    parser.add_argument("--run-dir", default="", help="Existing run directory for publish-graph.")
    parser.add_argument("--graph-import", default="", help="Explicit graph_import.json path for publish-graph.")
    parser.add_argument("--target-graph", default="", help="Target graph JSON path for publish-graph.")
    parser.add_argument("--audit-limit", default=8, type=int, help="How many normalized rows to print in audit-run.")
    parser.add_argument("--replace", action="store_true", help="Replace target graph file instead of merge.")
    args = parser.parse_args()

    pipeline = TCMTriplePipeline(build_config(args))

    if args.command == "interactive":
        return interactive_main(pipeline, args)
    if args.command == "list":
        print_books(pipeline.discover_books()[: args.limit])
        return 0
    if args.command == "recommend":
        print_books(pipeline.recommend_books(limit=args.limit))
        return 0
    if args.command == "chapters":
        book_path = resolve_single_book(pipeline, args.book)
        if book_path is None:
            raise SystemExit("book_not_found")
        print_chapters(pipeline, book_path, limit=args.limit)
        return 0
    if args.command == "latest":
        latest = pipeline.latest_run()
        if latest:
            print_run_summary(pipeline.summarize_run_dir(latest))
        return 0
    if args.command == "audit-run":
        run_dir = Path(args.run_dir) if args.run_dir else pipeline.latest_run()
        if run_dir is None:
            raise SystemExit("run_dir_not_found")
        print_run_audit(pipeline.audit_run_dir(run_dir, limit=max(1, args.audit_limit)))
        return 0
    if args.command == "clean-run":
        run_dir = Path(args.run_dir) if args.run_dir else pipeline.latest_run()
        if run_dir is None:
            raise SystemExit("run_dir_not_found")
        print_clean_report(pipeline.clean_run_dir(run_dir))
        return 0
    if args.command == "extract":
        deduped = resolve_selected_books(pipeline, args.books, fallback_limit=args.limit)
        run_dir = pipeline.extract_books(
            selected_books=deduped,
            label=args.label,
            max_chunks_per_book=args.max_chunks_per_book or None,
            dry_run=args.dry_run,
            chapter_contains=_split_keywords(args.chapter_contains) or None,
            chapter_excludes=resolve_chapter_excludes(
                args.chapter_excludes,
                use_default_excludes=args.use_default_excludes and not args.no_default_excludes,
            ),
            skip_initial_chunks_per_book=max(0, args.skip_initial_chunks),
            chunk_strategy=args.chunk_strategy,
        )
        print_run_summary(pipeline.summarize_run_dir(run_dir))
        return 0
    if args.command == "publish-graph":
        run_dir = Path(args.run_dir) if args.run_dir else None
        graph_import_path = Path(args.graph_import) if args.graph_import else None
        target_path = Path(args.target_graph) if args.target_graph else DEFAULT_GRAPH_TARGET
        published = pipeline.publish_graph(
            graph_import_path=graph_import_path,
            run_dir=run_dir,
            target_path=target_path,
            replace=args.replace,
        )
        print(published)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
