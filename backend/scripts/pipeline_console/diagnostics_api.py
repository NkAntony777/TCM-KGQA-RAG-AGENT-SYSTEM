from __future__ import annotations

from typing import Any, Callable


ProviderToDictFn = Callable[[Any], dict[str, Any]]


def env_config_payload(
    *,
    model: str,
    base_url: str,
    api_key: str,
    providers: list[Any],
    provider_to_dict: ProviderToDictFn,
) -> dict[str, Any]:
    return {
        "model": model,
        "base_url": base_url,
        "api_key_set": bool(api_key),
        "api_key_hint": (api_key[:4] + "..." + api_key[-4:]) if len(api_key) > 8 else ("已设置" if api_key else "未设置"),
        "providers": [provider_to_dict(provider) for provider in providers],
    }


def test_api_call_payload(
    pipeline: Any,
    *,
    chapter_excludes: list[str],
    chunk_strategy: str,
    provider_to_dict: ProviderToDictFn,
) -> dict[str, Any]:
    books = pipeline.discover_books()
    if not books:
        raise ValueError("没有可用的书籍")
    tasks = pipeline.schedule_book_chunks(
        book_path=books[0],
        chapter_excludes=chapter_excludes or None,
        max_chunks_per_book=1,
        skip_initial_chunks_per_book=0,
        chunk_strategy=chunk_strategy or "body_first",
    )
    if not tasks:
        raise ValueError("该书没有可处理的 chunk")
    task = tasks[0]

    prompt = pipeline.build_prompt(
        book_name=task.book_name,
        chapter_name=task.chapter_name,
        text_chunk=task.text_chunk,
    )
    llm_payload = pipeline.call_llm(prompt)
    meta = llm_payload.get("__meta__", {}) if isinstance(llm_payload, dict) else {}
    raw_content = str(meta.get("raw_text", ""))
    parsed = llm_payload
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
        "providers": [provider_to_dict(provider) for provider in pipeline.config.providers],
        "llm_provider_name": meta.get("provider_name"),
        "llm_provider_model": meta.get("provider_model"),
        "llm_provider_base_url": meta.get("provider_base_url"),
        "raw_response_length": len(str(raw_content)),
        "raw_response_preview": str(raw_content)[:300],
        "parsed_triples_count": len(triples_normalized),
        "parsed_sample": [
            {"subject": row.subject, "predicate": row.predicate, "object": row.object}
            for row in triples_normalized[:3]
        ],
        "status_code": 200,
    }
