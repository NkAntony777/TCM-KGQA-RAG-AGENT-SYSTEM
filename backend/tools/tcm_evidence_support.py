from __future__ import annotations

import json
import re
import sys
from typing import Any
from urllib.parse import unquote

from services.common.evidence_payloads import (
    clean_text as _clean_text,
    normalize_book_label as _shared_normalize_book_label,
    retrieval_items as _retrieval_items,
    safe_float as _safe_float,
)
from services.qa_service.alias_service import get_runtime_alias_service
from tools.tcm_service_client import call_retrieval_hybrid


def _owner_module_attr(name: str, default: Any) -> Any:
    owner = sys.modules.get("tools.tcm_evidence_tools")
    if owner is None:
        return default
    return getattr(owner, name, default)


def _runtime_alias_service():
    factory = _owner_module_attr("get_runtime_alias_service", get_runtime_alias_service)
    return factory()


def _call_retrieval_hybrid(**kwargs: Any) -> dict[str, Any]:
    caller = _owner_module_attr("call_retrieval_hybrid", call_retrieval_hybrid)
    return caller(**kwargs)


def _normalize_path(path: str) -> str:
    return unquote((path or "").strip())


HINT_SPLIT_PATTERN = re.compile(r"[\s,，。；;：:、/()（）【】\[\]<>《》“”\"'·]+")
HINT_STOPWORDS = {
    "出处",
    "原文",
    "原句",
    "原话",
    "古籍",
    "教材",
    "佐证",
    "证据",
    "来源",
    "条文",
    "哪本书",
    "什么书",
}
SOURCE_TRACE_QUERY_MARKERS = (
    "出处",
    "出自",
    "原文",
    "原句",
    "原话",
    "佐证",
    "来源",
    "条文",
    "方后注",
    "哪本书",
)


def _normalize_book_label(text: str) -> str:
    return _shared_normalize_book_label(text)


def _path_priority(path: str) -> tuple[int, str]:
    normalized = _normalize_path(path)
    if normalized.startswith("entity://"):
        return (0, normalized)
    if normalized.startswith("alias://"):
        return (1, normalized)
    if normalized.startswith("chapter://"):
        return (2, normalized)
    if normalized.startswith("book://"):
        return (3, normalized)
    if normalized.startswith("symptom://"):
        return (4, normalized)
    if normalized.startswith("qa://"):
        return (5, normalized)
    if normalized.startswith("caseqa://"):
        return (6, normalized)
    return (7, normalized)


def _ordered_unique_paths(paths: list[str]) -> list[str]:
    deduped = list(dict.fromkeys(path for path in (_normalize_path(item) for item in paths) if path))
    return sorted(deduped, key=_path_priority)


def _extract_hint_terms(*parts: str) -> list[str]:
    terms: list[str] = []
    seen = set()
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        fragments = [text, *HINT_SPLIT_PATTERN.split(text)]
        for fragment in fragments:
            candidate = str(fragment or "").strip()
            if len(candidate) < 2 or candidate in HINT_STOPWORDS or candidate in seen:
                continue
            seen.add(candidate)
            terms.append(candidate)
    return terms


def _alias_items(entity_name: str) -> list[dict[str, Any]]:
    alias_service = _runtime_alias_service()
    items: list[dict[str, Any]] = []
    for relation in alias_service.alias_relations(entity_name, max_items=6):
        snippet = relation.source_text or f"{relation.entity} 别名 {relation.alias}"
        source = "graph/alias"
        if relation.source_book:
            source = f"{relation.source_book}/{relation.source_chapter}".strip("/")
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph_alias",
                "source": source,
                "snippet": _clean_text(snippet),
                "score": float(relation.support or 1),
                "predicate": "别名",
                "target": relation.alias,
                "source_book": relation.source_book or None,
                "source_chapter": relation.source_chapter or None,
            }
        )
    return items

def _filter_items_by_book(items: list[dict[str, Any]], *, book_name: str) -> list[dict[str, Any]]:
    if not book_name:
        return items
    normalized_book = _normalize_book_label(book_name)
    filtered: list[dict[str, Any]] = []
    for item in items:
        haystack_parts = [
            str(item.get("source", "")),
            str(item.get("source_file", "")),
            str(item.get("source_book", "")),
            str(item.get("snippet", "")),
        ]
        haystack = " ".join(haystack_parts)
        normalized_haystack = " ".join(_normalize_book_label(part) for part in haystack_parts if str(part).strip())
        if book_name in haystack or (normalized_book and normalized_book in normalized_haystack):
            filtered.append(item)
    return filtered or items


def _rank_items_by_hint(items: list[dict[str, Any]], *, hint: str, query: str) -> list[dict[str, Any]]:
    hint_terms = _extract_hint_terms(hint)
    query_terms = _extract_hint_terms(query)
    if not hint_terms and not query_terms and not hint.strip() and not query.strip():
        return items

    def _score(item: dict[str, Any]) -> tuple[float, float, float]:
        haystack = " ".join(
            [
                str(item.get("source", "")),
                str(item.get("source_book", "")),
                str(item.get("source_chapter", "")),
                str(item.get("snippet", "")),
            ]
        )
        score = 0.0
        if hint.strip() and hint.strip() in haystack:
            score += 8.0
        if query.strip() and len(query.strip()) <= 48 and query.strip() in haystack:
            score += 5.0
        score += sum(3.0 for token in hint_terms if token in haystack)
        score += sum(1.5 for token in query_terms if token in haystack)
        base = float(item.get("score", 0.0) or 0.0)
        snippet_length = len(str(item.get("snippet", "")))
        return (score, base, -float(snippet_length))

    return sorted(items, key=_score, reverse=True)


def _source_scope_specs(paths: list[str]) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for path in paths:
        normalized = _normalize_path(path)
        if not normalized.startswith("book://"):
            continue
        body = normalized.removeprefix("book://")
        book_name, _, hint = body.partition("/")
        book_name = _normalize_book_label(book_name.strip())
        hint_text = hint.replace("*", "").strip("/")
        if book_name:
            specs.append((book_name, hint_text))
    deduped: list[tuple[str, str]] = []
    seen = set()
    for spec in specs:
        if spec in seen:
            continue
        seen.add(spec)
        deduped.append(spec)
    return deduped


def _dedupe_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("evidence_type", "")).strip(),
            str(item.get("source_type", "")).strip(),
            str(item.get("source", "")).strip(),
            str(item.get("source_book", "")).strip(),
            str(item.get("source_chapter", "")).strip(),
            str(item.get("predicate", "")).strip(),
            str(item.get("target", "")).strip(),
            str(item.get("snippet", "")).strip()[:160],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _prefers_scoped_source_trace(query: str) -> bool:
    text = str(query or "").strip()
    return any(marker in text for marker in SOURCE_TRACE_QUERY_MARKERS)


def _has_citation_ready_items(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type", "")).strip()
        if source_type in {"doc", "chapter"}:
            return True
        if str(item.get("source_book", "")).strip() and str(item.get("snippet", "")).strip():
            return True
    return False


def _source_lite_search(*, book_name: str, hint: str, query: str, source_hint: str = "", top_k: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    compact_hint = str(source_hint or "").strip().replace("\n", " ")[:120]
    ranked_terms = _extract_hint_terms(hint, compact_hint, query)
    search_query = " ".join([book_name, *ranked_terms[:8]]).strip() or book_name
    alias_service = _runtime_alias_service()
    alias_focus_entities = alias_service.detect_entities(" ".join([query, hint, compact_hint]), limit=2)
    search_query = alias_service.expand_query_with_aliases(
        search_query,
        focus_entities=alias_focus_entities,
        max_aliases_per_entity=3,
    )
    allowed_prefixes = ["herb2://"] if book_name.upper().startswith("HERB2") else ["classic://", "sample://"]
    raw = _call_retrieval_hybrid(
        query=search_query,
        top_k=top_k,
        candidate_k=max(top_k * 2, 8),
        enable_rerank=False,
        search_mode="files_first",
        allowed_file_path_prefixes=allowed_prefixes,
    )
    items = _filter_items_by_book(_retrieval_items(raw), book_name=book_name)
    items = _rank_items_by_hint(items, hint=hint, query=query)
    if items:
        return raw, items[:top_k]

    fallback_query = " ".join([book_name, *_extract_hint_terms(hint, compact_hint)[:6]]).strip() or book_name
    fallback_query = alias_service.expand_query_with_aliases(
        fallback_query,
        focus_entities=alias_focus_entities,
        max_aliases_per_entity=3,
    )
    fallback_raw = _call_retrieval_hybrid(
        query=fallback_query,
        top_k=top_k,
        candidate_k=max(top_k * 2, 8),
        enable_rerank=False,
        search_mode="files_first",
        allowed_file_path_prefixes=allowed_prefixes,
    )
    fallback_items = _filter_items_by_book(_retrieval_items(fallback_raw), book_name=book_name)
    fallback_items = _rank_items_by_hint(fallback_items, hint=hint, query=query)
    return fallback_raw, fallback_items[:top_k]


def _case_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        collection = str(chunk.get("collection", "caseqa")).strip()
        embedding_id = str(chunk.get("embedding_id", chunk.get("chunk_id", ""))).strip()
        items.append(
            {
                "evidence_type": "case_reference",
                "source_type": "case_qa",
                "source": f"{collection}/{embedding_id}".strip("/"),
                "snippet": _clean_text(chunk.get("answer", chunk.get("text"))),
                "document": _clean_text(chunk.get("document"), limit=240),
                "score": _safe_float(chunk.get("rerank_score", chunk.get("score"))),
            }
        )
    return items


def _response_payload(
    *,
    tool: str,
    path: str | None = None,
    query: str | None = None,
    scope_paths: list[str] | None = None,
    raw: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool": tool,
        "status": "ok",
        "items": items or [],
        "count": len(items or []),
    }
    if path is not None:
        payload["path"] = path
    if query is not None:
        payload["query"] = query
    if scope_paths is not None:
        payload["scope_paths"] = scope_paths
    if raw:
        payload["trace_id"] = raw.get("trace_id")
        payload["backend"] = raw.get("backend")
        payload["message"] = raw.get("message")
        payload["code"] = raw.get("code")
        if raw.get("warning"):
            payload["warning"] = raw.get("warning")
        if raw.get("code") not in (0, None):
            payload["status"] = "degraded" if items else "empty"
    if not payload["items"]:
        payload["status"] = "empty" if payload["status"] == "ok" else payload["status"]
    return payload


