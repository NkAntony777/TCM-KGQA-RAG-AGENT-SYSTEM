from __future__ import annotations

import json
from typing import Any


def safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def add_evidence(
    bucket: list[dict[str, Any]],
    *,
    source_type: str,
    source: str,
    snippet: str,
    score: float | None = None,
    fact_id: str | None = None,
    source_book: str | None = None,
    source_chapter: str | None = None,
    source_text: str | None = None,
    confidence: float | None = None,
    predicate: str | None = None,
    target: str | None = None,
    path_nodes: list[str] | None = None,
    path_edges: list[str] | None = None,
    path_sources: list[dict[str, Any]] | None = None,
) -> None:
    cleaned_source = (source or "unknown").strip()
    cleaned_snippet = (snippet or "").strip()
    if not cleaned_snippet:
        return
    item: dict[str, Any] = {
        "source_type": source_type,
        "source": cleaned_source,
        "snippet": cleaned_snippet[:300],
        "score": float(score) if score is not None else None,
    }
    if fact_id:
        item["fact_id"] = fact_id
    if source_book:
        item["source_book"] = source_book
    if source_chapter:
        item["source_chapter"] = source_chapter
    if source_text:
        item["source_text"] = source_text[:300]
    if confidence is not None:
        item["confidence"] = float(confidence)
    if predicate:
        item["predicate"] = predicate
    if target:
        item["target"] = target
    if path_nodes:
        item["path_nodes"] = path_nodes
    if path_edges:
        item["path_edges"] = path_edges
    if path_sources:
        item["path_sources"] = path_sources
    bucket.append(item)


def collect_retrieval_evidence(payload: dict[str, Any], bucket: list[dict[str, Any]]) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        source_file = str(chunk.get("source_file", "unknown"))
        source_page = chunk.get("source_page")
        source = f"{source_file}#{source_page}" if source_page is not None else source_file
        add_evidence(
            bucket,
            source_type="doc",
            source=source,
            snippet=str(chunk.get("text", "")),
            score=float(chunk.get("score")) if chunk.get("score") is not None else None,
        )


def collect_case_qa_evidence(payload: dict[str, Any], bucket: list[dict[str, Any]]) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        collection = str(chunk.get("collection", "caseqa"))
        embedding_id = str(chunk.get("embedding_id", chunk.get("chunk_id", ""))).strip()
        source = f"{collection}/{embedding_id}".strip("/")
        answer = str(chunk.get("answer", "")).strip()
        document = str(chunk.get("document", "")).strip()
        snippet = answer or document
        add_evidence(
            bucket,
            source_type="case_qa",
            source=source,
            snippet=snippet,
            score=float(chunk.get("rerank_score")) if chunk.get("rerank_score") is not None else float(chunk.get("score")) if chunk.get("score") is not None else None,
            source_text=document or None,
            target=answer[:120] if answer else None,
        )


def collect_graph_evidence(payload: dict[str, Any], bucket: list[dict[str, Any]]) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return

    relations = data.get("relations", [])
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            source_book = str(relation.get("source_book", "unknown"))
            source_chapter = str(relation.get("source_chapter", ""))
            source = f"{source_book}/{source_chapter}".strip("/")
            source_text = str(relation.get("source_text", "")).strip()
            confidence = relation.get("confidence")
            snippet = source_text or f"{relation.get('predicate', '')}: {relation.get('target', '')}"
            add_evidence(
                bucket,
                source_type="graph",
                source=source,
                snippet=snippet,
                score=float(confidence) if confidence is not None else None,
                fact_id=str(relation.get("fact_id", "")).strip() or None,
                source_book=source_book,
                source_chapter=source_chapter,
                source_text=source_text or None,
                confidence=float(confidence) if confidence is not None else None,
                predicate=str(relation.get("predicate", "")).strip() or None,
                target=str(relation.get("target", "")).strip() or None,
            )

    paths = data.get("paths", [])
    if isinstance(paths, list):
        for path in paths:
            if not isinstance(path, dict):
                continue
            nodes = path.get("nodes", [])
            snippet = " -> ".join(str(node) for node in nodes) if isinstance(nodes, list) else ""
            source = "graph/path"
            sources = path.get("sources", [])
            if isinstance(sources, list) and sources:
                first = sources[0]
                if isinstance(first, dict):
                    source = f"{first.get('source_book', 'unknown')}/{first.get('source_chapter', '')}".strip("/")
            add_evidence(
                bucket,
                source_type="graph_path",
                source=source,
                snippet=snippet,
                score=float(path.get("score")) if path.get("score") is not None else None,
                path_nodes=[str(node) for node in nodes] if isinstance(nodes, list) else None,
                path_edges=[str(edge) for edge in path.get("edges", [])] if isinstance(path.get("edges"), list) else None,
                path_sources=sources if isinstance(sources, list) else None,
            )

    syndromes = data.get("syndromes", [])
    if isinstance(syndromes, list):
        for syndrome in syndromes:
            if not isinstance(syndrome, dict):
                continue
            formulas = syndrome.get("recommended_formulas", [])
            formulas_text = ",".join(str(item) for item in formulas) if isinstance(formulas, list) else ""
            source_book = str(syndrome.get("source_book", ""))
            source_chapter = str(syndrome.get("source_chapter", ""))
            source = f"{source_book}/{source_chapter}".strip("/") or "graph/syndrome_chain"
            source_text = str(syndrome.get("source_text", "")).strip()
            confidence = syndrome.get("confidence")
            snippet = source_text or f"{syndrome.get('name', '')} -> {formulas_text}".strip()
            add_evidence(
                bucket,
                source_type="graph",
                source=source,
                snippet=snippet,
                score=float(confidence) if confidence is not None else float(syndrome.get("score")) if syndrome.get("score") is not None else None,
                fact_id=str(syndrome.get("fact_id", "")).strip() or None,
                source_book=source_book or None,
                source_chapter=source_chapter or None,
                source_text=source_text or None,
                confidence=float(confidence) if confidence is not None else None,
                predicate="辨证链",
                target=str(syndrome.get("name", "")).strip() or None,
            )


def extract_route_and_evidence(tool_name: str, output: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    payload = safe_json_loads(output)
    if not isinstance(payload, dict):
        return None, []

    route_event: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []

    if tool_name == "tcm_route_search":
        route_value = payload.get("route")
        route_reason = payload.get("route_reason")
        if route_value:
            route_event = {
                "route": str(route_value),
                "reason": str(route_reason or ""),
                "status": str(payload.get("status") or "ok"),
                "final_route": str(payload.get("final_route") or route_value),
                "executed_routes": payload.get("executed_routes", []),
                "degradation": payload.get("degradation", []),
                "service_health": payload.get("service_health", {}),
                "service_trace_ids": payload.get("service_trace_ids", {}),
                "service_backends": payload.get("service_backends", {}),
            }
        graph_result = payload.get("graph_result")
        retrieval_result = payload.get("retrieval_result")
        case_qa_result = payload.get("case_qa_result")
        if isinstance(graph_result, dict):
            collect_graph_evidence(graph_result, evidence)
        if isinstance(retrieval_result, dict):
            collect_retrieval_evidence(retrieval_result, evidence)
        if isinstance(case_qa_result, dict):
            collect_case_qa_evidence(case_qa_result, evidence)
        return route_event, evidence

    if tool_name in {"tcm_hybrid_search", "tcm_query_rewrite", "tcm_case_qa_search"}:
        if tool_name == "tcm_hybrid_search":
            collect_retrieval_evidence(payload, evidence)
        if tool_name == "tcm_case_qa_search":
            collect_case_qa_evidence(payload, evidence)
        return None, evidence

    if tool_name in {"tcm_entity_lookup", "tcm_path_query", "tcm_syndrome_chain"}:
        collect_graph_evidence(payload, evidence)
        return None, evidence

    return None, []


def extract_tool_meta(tool_name: str, output: str) -> dict[str, Any]:
    payload = safe_json_loads(output)
    if not isinstance(payload, dict):
        return {}

    meta: dict[str, Any] = {}
    for key in ("code", "message", "trace_id", "backend", "warning"):
        value = payload.get(key)
        if value is not None:
            meta[key] = value

    if tool_name == "tcm_route_search":
        meta["status"] = payload.get("status", "ok")
        meta["final_route"] = payload.get("final_route", payload.get("route"))
        meta["service_trace_ids"] = payload.get("service_trace_ids", {})
        meta["service_backends"] = payload.get("service_backends", {})

    return meta


def summarize_graph_result(result: dict[str, Any]) -> list[str]:
    if result.get("code") != 0:
        return []

    data = result.get("data", {})
    if not isinstance(data, dict):
        return []

    lines: list[str] = []
    entity = data.get("entity")
    relations = data.get("relations")
    if isinstance(entity, dict) and isinstance(relations, list) and relations:
        relation_text = "；".join(
            f"{item.get('predicate', '')}:{item.get('target', '')}"
            for item in relations[:4]
            if isinstance(item, dict)
        )
        lines.append(f"图谱关系：{entity.get('canonical_name') or entity.get('name')} -> {relation_text}")

    syndromes = data.get("syndromes")
    if isinstance(syndromes, list) and syndromes:
        parts = []
        for item in syndromes[:3]:
            if not isinstance(item, dict):
                continue
            formulas = item.get("recommended_formulas", [])
            formula_text = "、".join(str(x) for x in formulas[:3]) if isinstance(formulas, list) else ""
            parts.append(f"{item.get('name', '')}（推荐方剂：{formula_text}）")
        if parts:
            lines.append(f"辨证结果：{'；'.join(parts)}")

    paths = data.get("paths")
    if isinstance(paths, list) and paths:
        first = paths[0]
        if isinstance(first, dict) and isinstance(first.get("nodes"), list):
            lines.append(f"图谱路径：{' -> '.join(str(x) for x in first['nodes'])}")

    return lines


def summarize_retrieval_result(result: dict[str, Any]) -> list[str]:
    if result.get("code") != 0:
        return []

    data = result.get("data", {})
    if not isinstance(data, dict):
        return []

    chunks = data.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        return []

    lines: list[str] = []
    for chunk in chunks[:2]:
        if not isinstance(chunk, dict):
            continue
        source_file = chunk.get("source_file", "unknown")
        source_page = chunk.get("source_page")
        source = f"{source_file}#{source_page}" if source_page is not None else str(source_file)
        lines.append(f"文献证据：{source} -> {str(chunk.get('text', '')).strip()[:120]}")
    return lines


def build_mock_answer(query: str, tool_output: str, llm_error: str) -> str:
    payload = safe_json_loads(tool_output)
    if not isinstance(payload, dict):
        return "当前处于本地降级模式，但结构化工具返回不可解析，暂时无法生成回答。"

    lines = [
        "当前处于本地演示降级模式，未调用外部大模型，以下回答直接基于路由与 mock 证据生成。",
        f"- 问题：{query}",
        f"- 路由：{payload.get('route', 'unknown')} -> {payload.get('final_route', payload.get('route', 'unknown'))}",
    ]

    for item in summarize_graph_result(payload.get("graph_result", {})):
        lines.append(f"- {item}")
    for item in summarize_retrieval_result(payload.get("retrieval_result", {})):
        lines.append(f"- {item}")

    if len(lines) <= 3:
        lines.append("- 当前证据不足，建议改问更具体的方剂、证候、出处或原文问题。")

    lines.append(f"- 降级原因：{llm_error.splitlines()[0][:120]}")
    return "\n".join(lines)


def stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")
