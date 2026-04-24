from __future__ import annotations

import re
from typing import Any


EMPTY_ACCEPT_PATTERNS = (
    "電子版序",
    "电子版序",
    "前言",
    "凡例",
    "原序",
    "校補",
    "校补",
    "題簽",
    "题签",
    "民間中醫網",
    "民间中医网",
    "中醫經典古籍電子叢書",
    "中医经典古籍电子丛书",
    "【闡釋】",
    "【阐释】",
    "鄭論：",
    "郑论：",
    "論曰：",
    "论曰：",
)


def low_yield_retry_error(triples_count: int) -> str:
    return f"low_yield_retry: triples_count={triples_count}"


def is_low_yield_retry_error(error: str | None) -> bool:
    return isinstance(error, str) and error.startswith("low_yield_retry:")


def extract_payload_meta(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    meta = payload.get("__meta__")
    return meta if isinstance(meta, dict) else {}


def build_raw_chunk_record(
    *,
    task: Any,
    payload: Any,
    error: str | None,
    rows_count: int,
) -> dict[str, Any]:
    meta = extract_payload_meta(payload)
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
        "llm_provider_name": meta.get("provider_name"),
        "llm_provider_model": meta.get("provider_model"),
        "llm_provider_base_url": meta.get("provider_base_url"),
        "llm_provider_latency_ms": meta.get("provider_latency_ms"),
    }
    if completion_tokens >= 1000 and rows_count <= 1:
        record["diagnostic"] = "high_completion_low_yield"
    return record


def should_accept_empty_chunk(task: Any, rows: list[Any], error: str | None) -> bool:
    if error is not None or rows:
        return False
    text = str(getattr(task, "text_chunk", "") or "")
    if not text.strip():
        return True
    has_formula_like_title = re.search(r"[一-龥]{2,16}[汤丸散饮丹膏煎方]", text) is not None
    if has_formula_like_title:
        return False
    chapter_name = str(getattr(task, "chapter_name", "") or "")
    combined = f"{chapter_name}\n{text[:1200]}"
    return any(pattern in combined for pattern in EMPTY_ACCEPT_PATTERNS)


def evaluate_chunk_attempt(
    pipeline: Any,
    *,
    task: Any,
    payload: dict[str, Any],
    error: str | None,
    low_yield_retry_triple_threshold: int,
) -> tuple[list[Any], str | None]:
    rows = pipeline.normalize_triples(
        payload=payload,
        book_name=task.book_name,
        chapter_name=task.chapter_name,
    )
    if should_accept_empty_chunk(task, rows, error):
        return rows, None
    if error is None and len(rows) <= low_yield_retry_triple_threshold:
        return rows, low_yield_retry_error(len(rows))
    return rows, error
