from __future__ import annotations

from typing import Any

def _extract_data(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _normalize_path_predicate(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("(逆向)", "").replace("（逆向）", "").strip()


def _factual_evidence_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    graph_data = _extract_data(payload.get("graph_result"))
    retrieval_data = _extract_data(payload.get("retrieval_result"))
    relations = graph_data.get("relations", [])
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            source_book = str(relation.get("source_book", "")).strip()
            source_chapter = str(relation.get("source_chapter", "")).strip()
            snippet = str(relation.get("source_text", "")).strip() or f"{relation.get('predicate', '')}: {relation.get('target', '')}"
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": f"{source_book}/{source_chapter}".strip("/") or "graph",
                "snippet": snippet[:300],
                "score": float(relation.get("score", relation.get("confidence", relation.get("max_confidence", 0.0))) or 0.0),
                "predicate": str(relation.get("predicate", "")).strip(),
                "target": str(relation.get("target", "")).strip(),
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
            })
    syndromes = graph_data.get("syndromes", [])
    if isinstance(syndromes, list):
        for syndrome in syndromes:
            if not isinstance(syndrome, dict):
                continue
            formulas = syndrome.get("recommended_formulas", [])
            formula_text = "、".join(str(item) for item in formulas[:4]) if isinstance(formulas, list) else ""
            snippet = str(syndrome.get("source_text", "")).strip() or f"{syndrome.get('name', '')} -> {formula_text}".strip(" ->")
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": "graph/syndrome_chain",
                "snippet": snippet[:300],
                "score": float(syndrome.get("score", syndrome.get("confidence", 0.0)) or 0.0),
                "predicate": "辨证链",
                "target": str(syndrome.get("name", "")).strip(),
                "source_book": str(syndrome.get("source_book", "")).strip() or None,
                "source_chapter": str(syndrome.get("source_chapter", "")).strip() or None,
            })
    paths = graph_data.get("paths", [])
    if isinstance(paths, list):
        for path in paths:
            if not isinstance(path, dict):
                continue
            nodes = [str(item).strip() for item in path.get("nodes", []) if str(item).strip()] if isinstance(path.get("nodes"), list) else []
            edges = [_normalize_path_predicate(item) for item in path.get("edges", [])] if isinstance(path.get("edges"), list) else []
            sources = path.get("sources", [])
            source_meta = sources[0] if isinstance(sources, list) and sources and isinstance(sources[0], dict) else {}
            source_book = str(source_meta.get("source_book", "")).strip()
            source_chapter = str(source_meta.get("source_chapter", "")).strip()
            path_score = float(path.get("score", 0.0) or 0.0)
            if len(nodes) >= 2 and edges:
                for index, predicate in enumerate(edges):
                    if index + 1 >= len(nodes):
                        break
                    snippet = f"{nodes[index]} --{predicate}--> {nodes[index + 1]}"
                    evidence.append({
                        "evidence_type": "factual_grounding",
                        "source_type": "graph_path",
                        "source": f"{source_book}/{source_chapter}".strip("/") or "graph/path",
                        "snippet": snippet[:300],
                        "score": path_score,
                        "predicate": predicate,
                        "target": nodes[index + 1],
                        "source_book": source_book or None,
                        "source_chapter": source_chapter or None,
                    })
            elif nodes:
                snippet = " -> ".join(nodes)
                evidence.append({
                    "evidence_type": "factual_grounding",
                    "source_type": "graph_path",
                    "source": f"{source_book}/{source_chapter}".strip("/") or "graph/path",
                    "snippet": snippet[:300],
                    "score": path_score,
                    "predicate": "辨证链",
                    "target": nodes[-1],
                    "source_book": source_book or None,
                    "source_chapter": source_chapter or None,
                })
    chunks = retrieval_data.get("chunks", [])
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            source_file = str(chunk.get("source_file", chunk.get("filename", "unknown"))).strip()
            source_page = chunk.get("source_page", chunk.get("page_number"))
            source_book = source_file.rsplit(".", 1)[0] if source_file else ""
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "doc",
                "source": f"{source_file}#{source_page}" if source_page not in (None, "") else source_file,
                "snippet": str(chunk.get("text", "")).strip()[:300],
                "score": float(chunk.get("rerank_score", chunk.get("score", 0.0)) or 0.0),
                "source_book": source_book or None,
                "source_chapter": f"第{source_page}页" if source_page not in (None, "") else None,
            })
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
        evidence.append({
            "evidence_type": "case_reference",
            "source_type": "case_qa",
            "source": f"{collection}/{embedding_id}".strip("/"),
            "snippet": str(chunk.get("answer", chunk.get("text", ""))).strip()[:300],
            "document": str(chunk.get("document", "")).strip()[:240],
            "score": float(chunk.get("rerank_score", chunk.get("score", 0.0)) or 0.0),
        })
    return _dedupe_evidence(evidence)


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda current: float(current.get("score", 0.0) or 0.0), reverse=True):
        key = (str(item.get("source_type", "")).strip(), str(item.get("source", "")).strip(), str(item.get("snippet", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _merge_evidence_items(*, primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [dict(item) for item in primary]
    merged.extend(dict(item) for item in fallback)
    return _dedupe_evidence(merged)


def _build_book_citations(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for item in factual_evidence:
        source_book = str(item.get("source_book", "")).strip()
        source_chapter = str(item.get("source_chapter", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        if source_book:
            citations.append(f"{f'{source_book}/{source_chapter}'.strip('/')} {snippet[:48]}")
    return list(dict.fromkeys(item for item in citations if item.strip()))[:6]


def _build_citations(*, factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], book_citations: list[str], limit: int) -> list[str]:
    citations: list[str] = list(book_citations)
    for item in factual_evidence:
        source = str(item.get("source", "unknown")).strip()
        predicate = str(item.get("predicate", "")).strip()
        target = str(item.get("target", "")).strip()
        citations.append(f"{source} {predicate}:{target}" if predicate and target else f"{source} {str(item.get('snippet', '')).strip()[:40]}")
    for item in case_references:
        citations.append(f"{str(item.get('source', 'caseqa')).strip()} 相似案例")
    return list(dict.fromkeys(item for item in citations if item.strip()))[:limit]


def _identify_evidence_gaps(*, query: str, payload: dict[str, Any], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> list[str]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    intent = str(strategy.get("intent", analysis.get("dominant_intent", "")) or "").strip()
    entity_name = str(strategy.get("entity_name", "")).strip()
    predicates = {str(item.get("predicate", "")).strip() for item in factual_evidence if str(item.get("predicate", "")).strip()}
    source_types = {str(item.get("source_type", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip()}
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    sources = {str(item).strip() for item in strategy.get("sources", []) if str(item).strip()} if isinstance(strategy.get("sources", []), list) else set()

    gaps: list[str] = []
    if intent == "formula_composition" and "使用药材" not in predicates:
        gaps.append("composition")
    if intent == "formula_efficacy" and not predicates.intersection({"功效", "治法", "归经"}):
        gaps.append("efficacy")
    if intent == "formula_indication" and not predicates.intersection({"治疗证候", "治疗症状", "治疗疾病"}):
        gaps.append("indication")
    if intent == "syndrome_to_formula" and not predicates.intersection({"推荐方剂", "辨证链"}):
        gaps.append("syndrome_formula")
    if _needs_origin_support(query=query, intent=intent) and not _origin_support_sufficient(
        query=query,
        entity_name=entity_name,
        factual_evidence=factual_evidence,
        source_types=source_types,
    ):
        gaps.append("origin")
    if _needs_source_trace(query=query) and not _source_trace_sufficient(
        query=query,
        factual_evidence=factual_evidence,
    ):
        gaps.append("source_trace")
    if _needs_path_reasoning(query=query) and not _path_reasoning_sufficient(
        factual_evidence=factual_evidence,
    ):
        gaps.append("path_reasoning")
    if compare_entities and not _compare_entities_covered(compare_entities=compare_entities, factual_evidence=factual_evidence):
        gaps.append("comparison")
    if ("qa_case_vector_db" in sources or intent == "syndrome_to_formula") and not case_references and _query_benefits_from_case_reference(query=query):
        gaps.append("case_reference")
    return list(dict.fromkeys(gaps))


def _coverage_summary(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = _identify_evidence_gaps(query=query, payload=payload, factual_evidence=factual_evidence, case_references=case_references)
    return {"gaps": gaps, "factual_count": len(factual_evidence), "case_count": len(case_references), "evidence_path_count": len(evidence_paths), "sufficient": not gaps}


def _needs_origin_support(*, query: str, intent: str) -> bool:
    return intent == "formula_origin" or any(marker in query for marker in ("出处", "出自", "古籍", "教材", "原文", "哪本书", "来源"))


def _needs_source_trace(*, query: str) -> bool:
    return any(marker in query for marker in ("原文", "原句", "原话", "佐证", "出处说明", "结合古籍", "结合教材"))


def _needs_path_reasoning(*, query: str) -> bool:
    return any(marker in query for marker in ("链路", "路径", "辨证链", "为什么", "为何"))


def _query_benefits_from_case_reference(*, query: str) -> bool:
    markers = ("基本信息", "主诉", "现病史", "体格检查", "舌", "脉", "类似医案", "病例", "案例")
    hits = sum(1 for marker in markers if marker in query)
    return hits >= 2 or len(query) >= 40


def _origin_support_sufficient(*, query: str, entity_name: str, factual_evidence: list[dict[str, Any]], source_types: set[str]) -> bool:
    if not factual_evidence:
        return False

    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    wants_origin_book = any(marker in query for marker in ("出自", "哪本书", "出处"))
    has_graph_book = any(
        str(item.get("source_type", "")).strip() == "graph" and str(item.get("source_book", "")).strip()
        for item in factual_evidence
    )
    if entity_name:
        has_entity_linked_passage = any(
            entity_name in " ".join(
                [
                    str(item.get("source", "")).strip(),
                    str(item.get("snippet", "")).strip(),
                    str(item.get("target", "")).strip(),
                    str(item.get("source_text", "")).strip(),
                ]
            )
            for item in factual_evidence
        )
        if wants_source_text:
            return any(
                str(item.get("source_book", "")).strip()
                and len(str(item.get("snippet", "")).strip()) >= 12
                and entity_name in str(item.get("snippet", "")).strip()
                for item in factual_evidence
            )
        if wants_origin_book and not has_graph_book:
            return False
        return has_graph_book or has_entity_linked_passage

    if wants_source_text:
        return any(str(item.get("snippet", "")).strip() for item in factual_evidence)
    return any(source_type in {"doc", "graph"} for source_type in source_types)


def _source_trace_sufficient(*, query: str, factual_evidence: list[dict[str, Any]]) -> bool:
    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    backed_items = [
        item for item in factual_evidence
        if str(item.get("source_book", "")).strip() or str(item.get("source_type", "")).strip() in {"doc", "graph", "graph_path"}
    ]
    if not backed_items:
        return False
    if wants_source_text:
        return any(len(str(item.get("snippet", "")).strip()) >= 16 for item in backed_items)
    return len(backed_items) >= 1


def _path_reasoning_sufficient(*, factual_evidence: list[dict[str, Any]]) -> bool:
    return any(
        str(item.get("source_type", "")).strip() == "graph_path"
        or str(item.get("predicate", "")).strip() == "辨证链"
        or (
            isinstance(item.get("path_nodes"), list)
            and len([str(node).strip() for node in item.get("path_nodes", []) if str(node).strip()]) >= 2
        )
        for item in factual_evidence
    )


def _compare_entities_covered(*, compare_entities: list[str], factual_evidence: list[dict[str, Any]]) -> bool:
    covered = set()
    for entity in compare_entities:
        for item in factual_evidence:
            haystack = " ".join([str(item.get("source", "")), str(item.get("snippet", "")), str(item.get("predicate", "")), str(item.get("target", ""))])
            if entity and entity in haystack:
                covered.add(entity)
                break
    return len(covered) >= len(compare_entities)


