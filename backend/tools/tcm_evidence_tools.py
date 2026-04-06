from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Type
from urllib.parse import unquote

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_graph_path_query,
    call_graph_syndrome_chain,
    call_retrieval_case_qa,
    call_retrieval_hybrid,
)


def _clean_text(value: Any, *, limit: int = 300) -> str:
    return str(value or "").strip()[:limit]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _normalize_path(path: str) -> str:
    return unquote((path or "").strip())


def _graph_relation_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    relations = data.get("relations", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        source_book = str(relation.get("source_book", "")).strip()
        source_chapter = str(relation.get("source_chapter", "")).strip()
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": f"{source_book}/{source_chapter}".strip("/") or "graph",
                "snippet": _clean_text(
                    relation.get("source_text")
                    or f"{relation.get('predicate', '')}: {relation.get('target', '')}"
                ),
                "score": _safe_float(relation.get("score", relation.get("confidence"))),
                "predicate": str(relation.get("predicate", "")).strip(),
                "target": str(relation.get("target", "")).strip(),
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
            }
        )
    return items


def _graph_path_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    paths = data.get("paths", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for path in paths:
        if not isinstance(path, dict):
            continue
        nodes = [str(node) for node in path.get("nodes", [])] if isinstance(path.get("nodes"), list) else []
        edges = [str(edge) for edge in path.get("edges", [])] if isinstance(path.get("edges"), list) else []
        sources = path.get("sources", []) if isinstance(path.get("sources"), list) else []
        source = "graph/path"
        if sources:
            first = sources[0]
            if isinstance(first, dict):
                source = f"{first.get('source_book', 'unknown')}/{first.get('source_chapter', '')}".strip("/")
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph_path",
                "source": source,
                "snippet": " -> ".join(nodes)[:300],
                "score": _safe_float(path.get("score")),
                "path_nodes": nodes,
                "path_edges": edges,
                "path_sources": sources,
            }
        )
    return items


def _syndrome_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    syndromes = data.get("syndromes", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for syndrome in syndromes:
        if not isinstance(syndrome, dict):
            continue
        formulas = syndrome.get("recommended_formulas", [])
        formula_text = "、".join(str(item) for item in formulas[:6]) if isinstance(formulas, list) else ""
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": "graph/syndrome_chain",
                "snippet": _clean_text(syndrome.get("source_text") or f"{syndrome.get('name', '')} -> {formula_text}"),
                "score": _safe_float(syndrome.get("score", syndrome.get("confidence"))),
                "predicate": "辨证链",
                "target": str(syndrome.get("name", "")).strip(),
            }
        )
    return items


def _retrieval_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        source_file = str(chunk.get("source_file", chunk.get("filename", "unknown"))).strip()
        source_page = chunk.get("source_page", chunk.get("page_number"))
        source = f"{source_file}#{source_page}" if source_page not in (None, "") else source_file
        source_book = source_file.rsplit(".", 1)[0] if source_file else ""
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "doc",
                "source": source,
                "snippet": _clean_text(chunk.get("text")),
                "score": _safe_float(chunk.get("rerank_score", chunk.get("score"))),
                "source_file": source_file,
                "source_book": source_book or None,
                "source_chapter": f"第{source_page}页" if source_page not in (None, "") else None,
            }
        )
    return items


def _book_paths_from_payload(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    graph_data = payload.get("graph_result", {}).get("data", {}) if isinstance(payload.get("graph_result"), dict) else {}
    retrieval_data = payload.get("retrieval_result", {}).get("data", {}) if isinstance(payload.get("retrieval_result"), dict) else {}

    relations = graph_data.get("relations", []) if isinstance(graph_data, dict) else []
    for relation in relations if isinstance(relations, list) else []:
        if not isinstance(relation, dict):
            continue
        source_book = str(relation.get("source_book", "")).strip()
        if source_book:
            paths.append(f"book://{source_book}/*")

    chunks = retrieval_data.get("chunks", []) if isinstance(retrieval_data, dict) else []
    for chunk in chunks if isinstance(chunks, list) else []:
        if not isinstance(chunk, dict):
            continue
        source_file = str(chunk.get("source_file", chunk.get("filename", ""))).strip()
        if not source_file:
            continue
        source_name = source_file.rsplit(".", 1)[0]
        if source_name:
            paths.append(f"book://{source_name}/*")

    return list(dict.fromkeys(path for path in paths if path))


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
    tokens = [token for token in [hint.strip(), query.strip()] if token]
    if not tokens:
        return items

    def _score(item: dict[str, Any]) -> tuple[int, float]:
        haystack = " ".join(
            [
                str(item.get("source", "")),
                str(item.get("source_book", "")),
                str(item.get("source_chapter", "")),
                str(item.get("snippet", "")),
            ]
        )
        hits = sum(1 for token in tokens if token and token in haystack)
        base = float(item.get("score", 0.0) or 0.0)
        return (hits, base)

    return sorted(items, key=_score, reverse=True)


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
            strategy = route_payload.get("retrieval_strategy", {})
            if isinstance(strategy, dict):
                entity_name = str(strategy.get("entity_name", "")).strip()
                compare_entities = strategy.get("compare_entities", [])
                symptom_name = str(strategy.get("symptom_name", "")).strip()
                for entity in compare_entities if isinstance(compare_entities, list) else []:
                    if entity:
                        paths.append(f"entity://{entity}/*")
                if entity_name:
                    paths.append(f"entity://{entity_name}/*")
                if symptom_name:
                    paths.append(f"symptom://{symptom_name}/syndrome_chain")
        return {
            "tool": "list_evidence_paths",
            "query": query,
            "paths": list(dict.fromkeys(path for path in paths if path)),
            "count": len(list(dict.fromkeys(path for path in paths if path))),
        }

    def read_evidence_path(
        self,
        *,
        path: str,
        query: str = "",
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
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=_graph_relation_items(raw),
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

        if normalized.startswith("book://"):
            body = normalized.removeprefix("book://")
            book_name, _, hint = body.partition("/")
            hint_text = hint.replace("*", "").strip("/")
            search_query = " ".join(part for part in [book_name, hint_text, query] if part).strip() or book_name
            raw = call_retrieval_hybrid(
                query=search_query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 3, 12),
                enable_rerank=True,
            )
            items = _filter_items_by_book(_retrieval_items(raw), book_name=book_name)
            items = _rank_items_by_hint(items, hint=hint_text, query=query)
            return _response_payload(
                tool="read_evidence_path",
                path=normalized,
                raw=raw,
                items=items[:resolved_top_k],
            )

        if normalized.startswith("qa://"):
            target = normalized.removeprefix("qa://").split("/", 1)[0]
            search_query = target or query
            raw = call_retrieval_hybrid(
                query=search_query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 3, 12),
                enable_rerank=True,
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
        scope_paths: list[str] | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        resolved_top_k = max(1, int(top_k or self.default_top_k))
        normalized_scopes = [_normalize_path(item) for item in (scope_paths or []) if _normalize_path(item)]
        schemes = {item.split("://", 1)[0] for item in normalized_scopes if "://" in item}

        items: list[dict[str, Any]] = []
        raw_payload: dict[str, Any] | None = None

        if not schemes or schemes & {"qa", "book"}:
            raw_payload = call_retrieval_hybrid(
                query=query,
                top_k=resolved_top_k,
                candidate_k=max(resolved_top_k * 3, 12),
                enable_rerank=True,
            )
            items.extend(_retrieval_items(raw_payload))

        if not schemes or "caseqa" in schemes:
            case_payload = call_retrieval_case_qa(
                query=query,
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
            items=items[: max(resolved_top_k * 2, resolved_top_k)],
        )


class ListEvidencePathsInput(BaseModel):
    query: str = Field(..., description="Original user query")
    route_payload_json: str = Field(default="", description="Optional route payload JSON from tcm_route_search")


class ReadEvidencePathInput(BaseModel):
    path: str = Field(..., description="Logical evidence path such as entity://六味地黄丸/功效")
    query: str = Field(default="", description="Original user query for fallback retrieval context")
    top_k: int = Field(default=6, ge=1, le=20)


class SearchEvidenceTextInput(BaseModel):
    query: str = Field(..., description="Follow-up retrieval query")
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
        top_k: int = 6,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = EvidenceNavigator().read_evidence_path(path=path, query=query, top_k=top_k)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        path: str,
        query: str = "",
        top_k: int = 6,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, path, query, top_k, None)


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
        scope_paths: list[str] | None = None,
        top_k: int = 6,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = EvidenceNavigator().search_evidence_text(
            query=query,
            scope_paths=scope_paths or [],
            top_k=top_k,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        scope_paths: list[str] | None = None,
        top_k: int = 6,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, scope_paths or [], top_k, None)
