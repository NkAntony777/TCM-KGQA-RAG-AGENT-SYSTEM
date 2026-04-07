from __future__ import annotations

from typing import Any

from services.common.evidence_payloads import (
    extract_data as _extract_data,
    graph_path_items as _graph_path_items,
    graph_relation_items as _graph_relation_items,
    retrieval_items as _retrieval_items,
    syndrome_items as _syndrome_items,
)


def _evidence_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("source_type", "")).strip(),
        str(item.get("source", "")).strip(),
        str(item.get("snippet", "")).strip(),
    )


def _factual_evidence_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    graph_result = payload.get("graph_result", {}) if isinstance(payload, dict) else {}
    retrieval_result = payload.get("retrieval_result", {}) if isinstance(payload, dict) else {}
    evidence: list[dict[str, Any]] = []
    evidence.extend(_graph_relation_items(graph_result))
    evidence.extend(_syndrome_items(graph_result, formula_limit=4))
    evidence.extend(_graph_path_items(graph_result, expand_edges=True))
    evidence.extend(_retrieval_items(retrieval_result, source_book_normalizer=lambda value: str(value or "").strip()))
    return _dedupe_evidence(evidence)


def _case_reference_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    case_data = _extract_data(payload.get("case_qa_result"))
    chunks = case_data.get("chunks", [])
    if not isinstance(chunks, list):
        return []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        collection = str(chunk.get("collection", "caseqa")).strip()
        embedding_id = str(chunk.get("embedding_id", chunk.get("chunk_id", ""))).strip()
        evidence.append(
            {
                "evidence_type": "case_reference",
                "source_type": "case_qa",
                "source": f"{collection}/{embedding_id}".strip("/"),
                "snippet": str(chunk.get("answer", chunk.get("text", ""))).strip()[:300],
                "document": str(chunk.get("document", "")).strip()[:240],
                "score": float(chunk.get("rerank_score", chunk.get("score", 0.0)) or 0.0),
            }
        )
    return _dedupe_evidence(evidence)


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda current: float(current.get("score", 0.0) or 0.0), reverse=True):
        key = _evidence_identity(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _new_unique_evidence(*, primary: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_keys = {_evidence_identity(item) for item in existing}
    return [item for item in _dedupe_evidence(primary) if _evidence_identity(item) not in existing_keys]


def _merge_evidence_items(*, primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [dict(item) for item in primary]
    merged.extend(dict(item) for item in fallback)
    return _dedupe_evidence(merged)


def _build_book_citations(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for item in factual_evidence:
        source_book = str(item.get("source_book", "")).strip()
        source_chapter = str(item.get("source_chapter", "")).strip()
        if source_book:
            label = f"{source_book}/{source_chapter}".strip("/") if source_chapter else source_book
            citations.append(label)
    return list(dict.fromkeys(item for item in citations if item))


def _build_citations(*, factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], book_citations: list[str], limit: int) -> list[str]:
    citations: list[str] = list(book_citations)
    for item in factual_evidence:
        citations.append(f"{item.get('source', 'unknown')} {str(item.get('snippet', ''))[:80]}")
    for item in case_references:
        citations.append(f"{item.get('source', 'case')} {str(item.get('snippet', ''))[:80]}")
    ordered = list(dict.fromkeys(str(item).strip() for item in citations if str(item).strip()))
    return ordered[:limit]
