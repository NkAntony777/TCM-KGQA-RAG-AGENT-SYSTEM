from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

import httpx

from router.tcm_intent_classifier import analyze_tcm_query
from services.retrieval_service.files_first_methods import _descriptive_clause_terms

def _auto_merge(self, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta = {
        "auto_merge_enabled": self.settings.auto_merge_enabled,
        "auto_merge_applied": False,
        "auto_merge_threshold": self.settings.auto_merge_threshold,
        "auto_merge_replaced_chunks": 0,
        "auto_merge_steps": 0,
    }
    if not self.settings.auto_merge_enabled or not docs:
        return docs[:top_k], meta

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        parent_id = str(doc.get("parent_chunk_id", "")).strip()
        if parent_id:
            groups[parent_id].append(doc)

    target_parent_ids = [
        parent_id for parent_id, children in groups.items()
        if len(children) >= self.settings.auto_merge_threshold
    ]
    if not target_parent_ids:
        return docs[:top_k], meta

    parent_map = {
        item.get("chunk_id", ""): item
        for item in self.parent_store.get_documents_by_ids(target_parent_ids)
        if item.get("chunk_id")
    }
    merged_docs: list[dict[str, Any]] = []
    replaced_count = 0
    for doc in docs:
        parent_id = str(doc.get("parent_chunk_id", "")).strip()
        if not parent_id or parent_id not in parent_map:
            merged_docs.append(doc)
            continue
        parent_doc = dict(parent_map[parent_id])
        parent_doc["score"] = max(float(parent_doc.get("score", 0.0)), float(doc.get("score", 0.0)))
        if doc.get("match_snippet") and not parent_doc.get("match_snippet"):
            parent_doc["match_snippet"] = doc.get("match_snippet")
        parent_doc["merged_from_children"] = True
        parent_doc["merged_child_count"] = len(groups[parent_id])
        merged_docs.append(parent_doc)
        replaced_count += 1

    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in merged_docs:
        key = item.get("chunk_id") or (item.get("filename"), item.get("page_number"), item.get("text"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    meta.update(
        {
            "auto_merge_applied": replaced_count > 0,
            "auto_merge_replaced_chunks": replaced_count,
            "auto_merge_steps": 1 if replaced_count > 0 else 0,
        }
    )
    return deduped[:top_k], meta

def _apply_lexical_sanity_gate(
    self,
    query: str,
    docs: list[dict[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    if os.getenv("FILES_FIRST_LEXICAL_SANITY_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return docs
    if not docs:
        return docs
    anchors = self._extract_query_anchors(query)
    if not anchors:
        return docs

    filtered = [item for item in docs if self._doc_matches_anchors(item, anchors)]
    if len(filtered) == len(docs):
        return docs
    if filtered:
        warnings.append(f"lexical_sanity_filtered:{len(docs)}->{len(filtered)}")
        return filtered
    warnings.append("lexical_sanity_filtered_all")
    return []

def _doc_matches_anchors(item: dict[str, Any], anchors: list[str]) -> bool:
    haystacks = [
        str(item.get("text", "") or ""),
        str(item.get("source_file", "") or ""),
        str(item.get("filename", "") or ""),
        str(item.get("file_path", "") or ""),
        str(item.get("book_name", "") or ""),
        str(item.get("chapter_title", "") or ""),
        str(item.get("section_summary", "") or ""),
        str(item.get("topic_tags", "") or ""),
        str(item.get("entity_tags", "") or ""),
    ]
    joined = "\n".join(part for part in haystacks if part).lower()
    for anchor in anchors:
        probe = anchor.lower()
        if probe and probe in joined:
            return True
    return False

def _extract_query_anchors(query: str) -> list[str]:
    anchors: list[str] = []
    try:
        analysis = analyze_tcm_query(query)
        for item in analysis.matched_entities:
            if "source_book" in item.types:
                continue
            name = str(item.name).strip()
            if len(name) >= 2:
                anchors.append(name)
    except Exception:
        pass

    for clause in _descriptive_clause_terms(query):
        if len(clause) >= 3:
            anchors.append(clause)

    for match in re.finditer(r"《([^》]{2,24})》", query):
        anchors.append(str(match.group(1)).strip())
    for match in re.finditer(r"([\u4e00-\u9fff]{2,24}?)(?:里|中)(?!医|药|方)", query):
        candidate = str(match.group(1)).strip()
        if len(candidate) >= 2:
            anchors.append(candidate)
    for match in re.finditer(r"[\u4e00-\u9fff]{2,10}(?:经|论|方论|心典|浅注|集解|方|本草)", query):
        anchors.append(str(match.group(0)).strip())

    for match in re.finditer(r"[\u4e00-\u9fff]{2,10}(?:丸|散|汤|饮|膏|丹|颗粒|胶囊)", query):
        anchors.append(match.group(0))
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9\-]{1,14}\b", query):
        token = match.group(0)
        if len(token) >= 2:
            anchors.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in anchors:
        normalized = str(item).strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped

def _rerank(self, query: str, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    payload = {
        "model": self.settings.rerank_model,
        "query": query,
        "documents": [doc.get("text", "") for doc in docs],
        "top_n": min(top_k, len(docs)),
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {self.settings.rerank_api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(self.settings.rerank_endpoint, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        reranked: list[dict[str, Any]] = []
        for item in results:
            index = item.get("index")
            if isinstance(index, int) and 0 <= index < len(docs):
                doc = dict(docs[index])
                if item.get("relevance_score") is not None:
                    doc["rerank_score"] = float(item["relevance_score"])
                reranked.append(doc)
        return (reranked or docs[:top_k], True, None if reranked else "empty_rerank_results")
    except Exception as exc:
        return docs[:top_k], False, str(exc)

def _filter_docs_by_file_path_prefixes(
    docs: list[dict[str, Any]],
    prefixes: list[str] | None,
) -> list[dict[str, Any]]:
    normalized = [str(item or "").strip() for item in (prefixes or []) if str(item or "").strip()]
    if not normalized:
        return docs
    filtered: list[dict[str, Any]] = []
    for item in docs:
        file_path = str(item.get("file_path", "") or "").strip()
        if any(file_path.startswith(prefix) for prefix in normalized):
            filtered.append(item)
    return filtered
