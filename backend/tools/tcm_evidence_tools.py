from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.common.evidence_payloads import (
    book_paths_from_route_payload as _book_paths_from_payload,
    chapter_paths_from_route_payload as _chapter_paths_from_payload,
    graph_path_items as _graph_path_items,
    graph_relation_items as _graph_relation_items,
    retrieval_items as _retrieval_items,
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

from tools.tcm_evidence_support import (
    _alias_items,
    _case_items,
    _dedupe_items,
    _has_citation_ready_items,
    _normalize_path,
    _ordered_unique_paths,
    _prefers_scoped_source_trace,
    _response_payload,
    _source_lite_search,
    _source_scope_specs,
)


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
        scoped_items: list[dict[str, Any]] = []
        raw_payload: dict[str, Any] | None = None
        book_scopes = _source_scope_specs(normalized_scopes)
        chapter_scopes = [path for path in normalized_scopes if path.startswith("chapter://")]

        if chapter_scopes:
            for chapter_path in chapter_scopes[:2]:
                chapter_payload = call_retrieval_read_section(
                    path=chapter_path,
                    top_k=max(resolved_top_k * 4, 16),
                )
                chapter_items = _section_items(chapter_payload)
                raw_payload = raw_payload or chapter_payload
                items.extend(chapter_items)
                scoped_items.extend(chapter_items)

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
                scoped_items.extend(book_items)

        if _prefers_scoped_source_trace(query) and _has_citation_ready_items(scoped_items):
            return _response_payload(
                tool="search_evidence_text",
                query=query,
                scope_paths=normalized_scopes,
                raw=raw_payload,
                items=_dedupe_items(scoped_items, limit=max(resolved_top_k * 2, resolved_top_k)),
            )

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
