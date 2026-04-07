from __future__ import annotations

from typing import Any


def _init_coverage_state(*, query: str, payload: dict[str, Any], evidence_paths: list[str]) -> dict[str, Any]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    sources = {str(item).strip() for item in strategy.get("sources", []) if str(item).strip()} if isinstance(strategy.get("sources", []), list) else set()
    return {
        "query": query,
        "intent": str(strategy.get("intent", analysis.get("dominant_intent", "")) or "").strip(),
        "entity_name": str(strategy.get("entity_name", "")).strip(),
        "compare_entities": compare_entities,
        "sources": sources,
        "evidence_path_count": len(evidence_paths),
        "factual_count": 0,
        "case_count": 0,
        "predicates": set(),
        "source_types": set(),
        "graph_source_books": set(),
        "doc_source_books": set(),
        "has_origin_doc_support": False,
        "has_origin_text_support": False,
        "has_source_trace_support": False,
        "has_source_trace_text": False,
        "has_doc_origin_support": False,
        "has_doc_origin_text": False,
        "has_doc_source_trace_support": False,
        "has_doc_source_trace_text": False,
        "has_path_reasoning": False,
        "compare_covered": set(),
    }


def _update_coverage_state(
    state: dict[str, Any],
    *,
    new_factual_evidence: list[dict[str, Any]] | None = None,
    new_case_references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    factual = new_factual_evidence or []
    cases = new_case_references or []
    entity_name = str(state.get("entity_name", "")).strip()

    for item in factual:
        source_type = str(item.get("source_type", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        source_book = str(item.get("source_book", "")).strip()
        target = str(item.get("target", "")).strip()
        state["factual_count"] += 1
        if source_type:
            state["source_types"].add(source_type)
        if predicate:
            state["predicates"].add(predicate)
        if source_book and source_type == "graph":
            state["graph_source_books"].add(source_book)
        if source_book and source_type == "doc":
            state["doc_source_books"].add(source_book)
        if source_book or source_type in {"doc", "graph", "graph_path"}:
            state["has_source_trace_support"] = True
        if len(snippet) >= 16 and (source_book or source_type in {"doc", "graph", "graph_path"}):
            state["has_source_trace_text"] = True
        if source_type == "doc" and source_book:
            state["has_doc_source_trace_support"] = True
        if source_type == "doc" and len(snippet) >= 16:
            state["has_doc_source_trace_text"] = True
        if entity_name:
            haystack = " ".join([str(item.get("source", "")).strip(), snippet, target, str(item.get("source_text", "")).strip()])
            if entity_name in haystack:
                state["has_origin_doc_support"] = True
                if source_type == "doc":
                    state["has_doc_origin_support"] = True
            if source_book and len(snippet) >= 12 and entity_name in snippet:
                state["has_origin_text_support"] = True
                if source_type == "doc":
                    state["has_doc_origin_text"] = True
        elif snippet:
            state["has_origin_doc_support"] = True
            if len(snippet) >= 12:
                state["has_origin_text_support"] = True
            if source_type == "doc":
                state["has_doc_origin_support"] = True
                if len(snippet) >= 12:
                    state["has_doc_origin_text"] = True
        if source_type == "graph_path" or predicate == "辨证链" or (isinstance(item.get("path_nodes"), list) and len([str(node).strip() for node in item.get("path_nodes", []) if str(node).strip()]) >= 2):
            state["has_path_reasoning"] = True
        for entity in state.get("compare_entities", []):
            if entity and entity in " ".join([str(item.get("source", "")), snippet, predicate, target]):
                state["compare_covered"].add(entity)

    for _ in cases:
        state["case_count"] += 1
    return state


def _coverage_gaps_from_state(state: dict[str, Any]) -> list[str]:
    query = str(state.get("query", "")).strip()
    intent = str(state.get("intent", "")).strip()
    entity_name = str(state.get("entity_name", "")).strip()
    predicates = set(state.get("predicates", set()))
    source_types = set(state.get("source_types", set()))
    compare_entities = list(state.get("compare_entities", []))
    sources = set(state.get("sources", set()))

    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    wants_origin_book = any(marker in query for marker in ("出自", "哪本书", "出处"))

    gaps: list[str] = []
    if intent == "formula_composition" and "使用药材" not in predicates:
        gaps.append("composition")
    if intent == "formula_efficacy" and not predicates.intersection({"功效", "治法", "归经"}):
        gaps.append("efficacy")
    if intent == "formula_indication" and not predicates.intersection({"治疗证候", "治疗症状", "治疗疾病"}):
        gaps.append("indication")
    if intent == "syndrome_to_formula" and not predicates.intersection({"推荐方剂", "辨证链"}):
        gaps.append("syndrome_formula")

    if _needs_origin_support(query=query, intent=intent):
        has_graph_book = bool(state.get("graph_source_books"))
        has_doc_book = bool(state.get("doc_source_books"))
        has_entity_linked_passage = bool(state.get("has_origin_doc_support"))
        has_doc_entity_linked_passage = bool(state.get("has_doc_origin_support"))
        if entity_name:
            if wants_source_text:
                if not state.get("has_doc_origin_text"):
                    gaps.append("origin")
            elif wants_origin_book:
                if has_graph_book and not has_doc_book:
                    gaps.append("origin")
                elif not has_graph_book and not has_doc_entity_linked_passage:
                    gaps.append("origin")
            elif has_graph_book and not (has_doc_book or has_doc_entity_linked_passage):
                gaps.append("origin")
            elif not has_graph_book and not has_entity_linked_passage:
                gaps.append("origin")
        else:
            if wants_source_text:
                if not state.get("has_doc_origin_text"):
                    gaps.append("origin")
            elif has_graph_book and not has_doc_book:
                gaps.append("origin")
            elif not source_types.intersection({"doc", "graph"}):
                gaps.append("origin")

    if _needs_source_trace(query=query):
        has_graph_book = bool(state.get("graph_source_books"))
        if has_graph_book and not state.get("has_doc_source_trace_support"):
            gaps.append("source_trace")
        elif not state.get("has_source_trace_support"):
            gaps.append("source_trace")
        elif wants_source_text and not state.get("has_doc_source_trace_text"):
            gaps.append("source_trace")

    if _needs_path_reasoning(query=query) and not state.get("has_path_reasoning"):
        gaps.append("path_reasoning")
    if compare_entities and len(state.get("compare_covered", set())) < len(compare_entities):
        gaps.append("comparison")
    if ("qa_case_structured_index" in sources or "qa_case_vector_db" in sources or intent == "syndrome_to_formula") and int(state.get("case_count", 0)) <= 0 and _query_benefits_from_case_reference(query=query):
        gaps.append("case_reference")
    return list(dict.fromkeys(gaps))


def _coverage_summary_from_state(state: dict[str, Any]) -> dict[str, Any]:
    gaps = _coverage_gaps_from_state(state)
    return {
        "gaps": gaps,
        "factual_count": int(state.get("factual_count", 0)),
        "case_count": int(state.get("case_count", 0)),
        "evidence_path_count": int(state.get("evidence_path_count", 0)),
        "sufficient": not gaps,
    }


def _needs_origin_support(*, query: str, intent: str) -> bool:
    return intent == "formula_origin" or any(marker in query for marker in ("出处", "出自", "哪本书", "原文", "原句", "原话"))


def _needs_source_trace(*, query: str) -> bool:
    return any(marker in query for marker in ("出处", "出自", "原文", "原句", "原话", "佐证", "来源"))


def _needs_path_reasoning(*, query: str) -> bool:
    return any(marker in query for marker in ("病机", "辨证", "链路", "为什么", "异同", "区别", "比较", "共同点"))


def _query_benefits_from_case_reference(*, query: str) -> bool:
    return any(marker in query for marker in ("医案", "病例", "案例", "经验", "临床", "辨证", "主诉", "现病史"))


def _origin_support_sufficient(*, query: str, entity_name: str, factual_evidence: list[dict[str, Any]], source_types: set[str]) -> bool:
    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    wants_origin_book = any(marker in query for marker in ("出自", "哪本书", "出处"))
    has_graph_book = any(str(item.get("source_book", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip() == "graph")
    has_doc_book = any(str(item.get("source_book", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip() == "doc")
    has_entity_linked_passage = False
    has_doc_entity_linked_passage = False
    has_doc_origin_text = False
    for item in factual_evidence:
        snippet = str(item.get("snippet", "")).strip()
        source_type = str(item.get("source_type", "")).strip()
        source_book = str(item.get("source_book", "")).strip()
        target = str(item.get("target", "")).strip()
        haystack = " ".join([str(item.get("source", "")).strip(), snippet, target, str(item.get("source_text", "")).strip()])
        if entity_name:
            if entity_name in haystack:
                has_entity_linked_passage = True
                if source_type == "doc":
                    has_doc_entity_linked_passage = True
            if source_type == "doc" and source_book and len(snippet) >= 12 and entity_name in snippet:
                has_doc_origin_text = True
        elif snippet:
            has_entity_linked_passage = True
            if source_type == "doc":
                has_doc_entity_linked_passage = True
                if len(snippet) >= 12:
                    has_doc_origin_text = True
    if wants_source_text:
        return has_doc_origin_text
    if entity_name:
        if wants_origin_book:
            return (has_graph_book and has_doc_book) or (not has_graph_book and has_doc_entity_linked_passage)
        if has_graph_book:
            return has_doc_book or has_doc_entity_linked_passage
        return has_entity_linked_passage
    if has_graph_book:
        return has_doc_book
    return bool(source_types.intersection({"doc", "graph"}))


def _source_trace_sufficient(*, query: str, factual_evidence: list[dict[str, Any]]) -> bool:
    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    has_graph_book = any(str(item.get("source_book", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip() == "graph")
    has_doc_source_trace_support = False
    has_source_trace_support = False
    has_doc_source_trace_text = False
    for item in factual_evidence:
        source_type = str(item.get("source_type", "")).strip()
        source_book = str(item.get("source_book", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        if source_book or source_type in {"doc", "graph", "graph_path"}:
            has_source_trace_support = True
        if source_type == "doc" and source_book:
            has_doc_source_trace_support = True
        if source_type == "doc" and len(snippet) >= 16:
            has_doc_source_trace_text = True
    if has_graph_book:
        return has_doc_source_trace_text if wants_source_text else has_doc_source_trace_support
    if wants_source_text:
        return has_doc_source_trace_text
    return has_source_trace_support


def _path_reasoning_sufficient(*, factual_evidence: list[dict[str, Any]]) -> bool:
    for item in factual_evidence:
        source_type = str(item.get("source_type", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        if source_type == "graph_path" or predicate == "辨证链":
            return True
        if isinstance(item.get("path_nodes"), list) and len([str(node).strip() for node in item.get("path_nodes", []) if str(node).strip()]) >= 2:
            return True
    return False


def _compare_entities_covered(*, compare_entities: list[str], factual_evidence: list[dict[str, Any]]) -> bool:
    if not compare_entities:
        return True
    covered = set()
    for entity in compare_entities:
        for item in factual_evidence:
            haystack = " ".join([str(item.get("source", "")), str(item.get("snippet", "")), str(item.get("predicate", "")), str(item.get("target", ""))])
            if entity and entity in haystack:
                covered.add(entity)
                break
    return len(covered) >= len(compare_entities)


def _identify_evidence_gaps(*, query: str, payload: dict[str, Any], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> list[str]:
    state = _init_coverage_state(query=query, payload=payload, evidence_paths=payload.get("evidence_paths", []) if isinstance(payload.get("evidence_paths", []), list) else [])
    _update_coverage_state(state, new_factual_evidence=factual_evidence, new_case_references=case_references)
    return _coverage_gaps_from_state(state)


def _coverage_summary(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> dict[str, Any]:
    state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
    _update_coverage_state(state, new_factual_evidence=factual_evidence, new_case_references=case_references)
    return _coverage_summary_from_state(state)
