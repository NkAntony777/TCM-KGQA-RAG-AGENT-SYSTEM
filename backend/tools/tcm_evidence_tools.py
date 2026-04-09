from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Type
from urllib.parse import unquote

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from services.common.evidence_payloads import (
    book_paths_from_route_payload as _book_paths_from_payload,
    chapter_paths_from_route_payload as _chapter_paths_from_payload,
    clean_text as _clean_text,
    graph_path_items as _graph_path_items,
    graph_relation_items as _graph_relation_items,
    normalize_book_label as _shared_normalize_book_label,
    retrieval_items as _retrieval_items,
    safe_float as _safe_float,
    section_items as _section_items,
    syndrome_items as _syndrome_items,
)
from services.qa_service.alias_service import get_runtime_alias_service
from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_graph_path_query,
    call_graph_syndrome_chain,
    call_retrieval_case_qa,
    call_retrieval_hybrid,
    call_retrieval_read_section,
)


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
    alias_service = get_runtime_alias_service()
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
    filtered: list[dict[str, Any]] = []
    for item in items:
        haystack = " ".join(
            [
                str(item.get("source", "")),
                str(item.get("source_file", "")),
                str(item.get("source_book", "")),
                str(item.get("snippet", "")),
            ]
        )
        if book_name in haystack:
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
        book_name = book_name.strip()
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


def _source_lite_search(*, book_name: str, hint: str, query: str, source_hint: str = "", top_k: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    compact_hint = str(source_hint or "").strip().replace("\n", " ")[:120]
    ranked_terms = _extract_hint_terms(hint, compact_hint, query)
    search_query = " ".join([book_name, *ranked_terms[:8]]).strip() or book_name
    alias_service = get_runtime_alias_service()
    alias_focus_entities = alias_service.detect_entities(" ".join([query, hint, compact_hint]), limit=2)
    search_query = alias_service.expand_query_with_aliases(
        search_query,
        focus_entities=alias_focus_entities,
        max_aliases_per_entity=3,
    )
    allowed_prefixes = ["herb2://"] if book_name.upper().startswith("HERB2") else ["classic://", "sample://"]
    raw = call_retrieval_hybrid(
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
    fallback_raw = call_retrieval_hybrid(
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


@dataclass
class EvidenceNavigator:
    default_top_k: int = 6

    def list_evidence_paths(
        self,
        *,
        query: str,
        route_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        paths: list[str] = []
        if isinstance(route_payload, dict):
            payload_paths = route_payload.get("evidence_paths", [])
            if isinstance(payload_paths, list):
                paths.extend(str(item).strip() for item in payload_paths if str(item).strip())
            paths.extend(_book_paths_from_payload(route_payload))
            paths.extend(_chapter_paths_from_payload(route_payload))
            strategy = route_payload.get("retrieval_strategy", {})
            if isinstance(strategy, dict):
                entity_name = str(strategy.get("entity_name", "")).strip()
                compare_entities = strategy.get("compare_entities", [])
                symptom_name = str(strategy.get("symptom_name", "")).strip()
                for entity in compare_entities if isinstance(compare_entities, list) else []:
                    if entity:
                        paths.append(f"alias://{entity}")
                        paths.append(f"entity://{entity}/*")
                if entity_name:
                    paths.append(f"alias://{entity_name}")
                    paths.append(f"entity://{entity_name}/*")
                if symptom_name:
                    paths.append(f"symptom://{symptom_name}/syndrome_chain")
        return {
            "tool": "list_evidence_paths",
            "query": query,
            "paths": _ordered_unique_paths(paths),
            "count": len(_ordered_unique_paths(paths)),
        }

    def read_evidence_path(
        self,
        *,
        path: str,
        query: str = "",
        source_hint: str = "",
        top_k: int | None = None,
    ) -> dict[str, Any]:
        normalized = _normalize_path(path)
        resolved_top_k = max(1, int(top_k or self.default_top_k))

        if normalized.startswith("entity://"):
            body = normalized.removeprefix("entity://")
            entity_name, _, predicate = body.partition("/")
            allowlist = None if predicate in ("", "*") else [predicate]
            raw = call_graph_entity_lookup(
                name=entity_name,
                top_k=resolved_top_k,
                predicate_allowlist=allowlist,
            )
            items = _graph_relation_items(raw)
            if entity_name:
                for item in items:
                    item.setdefault("anchor_entity", entity_name)
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=items,
            )

        if normalized.startswith("symptom://"):
            body = normalized.removeprefix("symptom://")
            symptom_name, _, suffix = body.partition("/")
            raw = call_graph_syndrome_chain(
                symptom=symptom_name,
                top_k=min(resolved_top_k, 8),
            )
            items = _syndrome_items(raw)
            if suffix not in ("", "syndrome_chain"):
                items = []
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=items,
            )

        if normalized.startswith("path://"):
            body = normalized.removeprefix("path://")
            start, _, end = body.partition("->")
            raw = call_graph_path_query(
                start=start,
                end=end,
                max_hops=3,
                path_limit=min(resolved_top_k, 5),
            )
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=_graph_path_items(raw),
            )

        if normalized.startswith("alias://"):
            entity_name = normalized.removeprefix("alias://").split("/", 1)[0].strip()
            items = _alias_items(entity_name)
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                items=items[:resolved_top_k],
            )

        if normalized.startswith("book://"):
            body = normalized.removeprefix("book://")
            book_name, _, hint = body.partition("/")
            hint_text = hint.replace("*", "").strip("/")
            raw, items = _source_lite_search(
                book_name=book_name,
                hint=hint_text,
                query=query,
                source_hint=source_hint,
                top_k=resolved_top_k,
            )
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=items,
            )

        if normalized.startswith("chapter://"):
            raw = call_retrieval_read_section(
                path=normalized,
                top_k=max(resolved_top_k * 4, 16),
            )
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=_section_items(raw),
            )

        if normalized.startswith("qa://"):
            target = normalized.removeprefix("qa://").split("/", 1)[0]
            alias_service = get_runtime_alias_service()
            search_query = alias_service.expand_query_with_aliases(target or query)
            raw = call_retrieval_hybrid(
                query=search_query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 3, 12),
                enable_rerank=True,
                search_mode="files_first",
            )
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=_retrieval_items(raw),
            )

        if normalized.startswith("caseqa://"):
            target = normalized.removeprefix("caseqa://").split("/", 1)[0]
            search_query = target or query
            raw = call_retrieval_case_qa(
                query=search_query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 4, 20),
            )
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=_case_items(raw),
            )

        return {
            "tool": "read_evidence_path",
            "path": normalized,
            "status": "error",
            "items": [],
            "count": 0,
            "message": "unsupported_evidence_path",
        }

    def search_evidence_text(
        self,
        *,
        query: str,
        source_hint: str = "",
        scope_paths: list[str] | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        resolved_top_k = max(1, int(top_k or self.default_top_k))
        normalized_scopes = [_normalize_path(item) for item in (scope_paths or []) if _normalize_path(item)]
        schemes = {item.split("://", 1)[0] for item in normalized_scopes if "://" in item}
        alias_service = get_runtime_alias_service()
        expanded_query = alias_service.expand_query_with_aliases(query)

        items: list[dict[str, Any]] = []
        raw_payload: dict[str, Any] | None = None
        book_scopes = _source_scope_specs(normalized_scopes)
        chapter_scopes = [path for path in normalized_scopes if path.startswith("chapter://")]

        if chapter_scopes:
            for chapter_path in chapter_scopes[:2]:
                chapter_payload = call_retrieval_read_section(
                    path=chapter_path,
                    top_k=max(resolved_top_k * 4, 16),
                )
                raw_payload = raw_payload or chapter_payload
                items.extend(_section_items(chapter_payload))

        if book_scopes:
            for book_name, hint in book_scopes[:2]:
                book_raw, book_items = _source_lite_search(
                    book_name=book_name,
                    hint=hint,
                    query=query,
                    source_hint=source_hint,
                    top_k=resolved_top_k,
                )
                raw_payload = raw_payload or book_raw
                items.extend(book_items)

        if not schemes or "qa" in schemes or (not book_scopes and "book" in schemes):
            raw_payload = call_retrieval_hybrid(
                query=expanded_query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 3, 12),
                enable_rerank=True,
                search_mode="files_first",
            )
            items.extend(_retrieval_items(raw_payload))

        if not schemes or "caseqa" in schemes:
            case_payload = call_retrieval_case_qa(
                query=expanded_query,
                top_k=min(resolved_top_k, 4),
                candidate_k=max(resolved_top_k * 4, 20),
            )
            items.extend(_case_items(case_payload))
            if raw_payload is None:
                raw_payload = case_payload

        return _response_payload(
            tool="search_evidence_text",
            query=query,
            scope_paths=normalized_scopes,
            raw=raw_payload,
            items=_dedupe_items(items, limit=max(resolved_top_k * 2, resolved_top_k)),
        )


class ListEvidencePathsInput(BaseModel):
    query: str = Field(..., description="Original user query")
    route_payload_json: str = Field(default="", description="Optional route payload JSON from tcm_route_search")


class ReadEvidencePathInput(BaseModel):
    path: str = Field(..., description="Logical evidence path such as entity://六味地黄丸/功效")
    query: str = Field(default="", description="Original user query for fallback retrieval context")
    source_hint: str = Field(default="", description="Optional source-text hint from graph evidence for files-first tracing")
    top_k: int = Field(default=6, ge=1, le=20)


class SearchEvidenceTextInput(BaseModel):
    query: str = Field(..., description="Follow-up retrieval query")
    source_hint: str = Field(default="", description="Optional source-text hint from graph evidence for files-first tracing")
    scope_paths: list[str] = Field(default_factory=list, description="Optional evidence path scopes")
    top_k: int = Field(default=6, ge=1, le=20)


class TCMListEvidencePathsTool(BaseTool):
    name: str = "list_evidence_paths"
    description: str = (
        "List logical evidence paths derived from a route payload. "
        "Use before follow-up retrieval to inspect what evidence can be browsed."
    )
    args_schema: Type[BaseModel] = ListEvidencePathsInput

    def _run(
        self,
        query: str,
        route_payload_json: str = "",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        payload = None
        try:
            parsed = json.loads(route_payload_json) if route_payload_json else None
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = None
        result = EvidenceNavigator().list_evidence_paths(query=query, route_payload=payload)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        route_payload_json: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, route_payload_json, None)


class TCMReadEvidencePathTool(BaseTool):
    name: str = "read_evidence_path"
    description: str = (
        "Read a logical evidence path and return structured graph/doc/case evidence snippets. "
        "Use for bounded follow-up retrieval after initial routing."
    )
    args_schema: Type[BaseModel] = ReadEvidencePathInput

    def _run(
        self,
        path: str,
        query: str = "",
        source_hint: str = "",
        top_k: int = 6,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = EvidenceNavigator().read_evidence_path(path=path, query=query, source_hint=source_hint, top_k=top_k)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        path: str,
        query: str = "",
        source_hint: str = "",
        top_k: int = 6,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, path, query, source_hint, top_k, None)


class TCMSearchEvidenceTextTool(BaseTool):
    name: str = "search_evidence_text"
    description: str = (
        "Search textual evidence across retrieval or case-qa backends, optionally constrained by logical evidence paths. "
        "Use when the current evidence paths are insufficient or origin/source citations are missing."
    )
    args_schema: Type[BaseModel] = SearchEvidenceTextInput

    def _run(
        self,
        query: str,
        source_hint: str = "",
        scope_paths: list[str] | None = None,
        top_k: int = 6,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = EvidenceNavigator().search_evidence_text(
            query=query,
            source_hint=source_hint,
            scope_paths=scope_paths or [],
            top_k=top_k,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        source_hint: str = "",
        scope_paths: list[str] | None = None,
        top_k: int = 6,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, source_hint, scope_paths or [], top_k, None)
