from __future__ import annotations

from typing import Any

REASONING_PREDICATES = {"功效", "治法", "归经", "治疗证候", "治疗症状", "治疗疾病", "辨证链"}
DOC_LIKE_SOURCE_TYPES = {"doc", "chapter"}
REASONING_MARKERS = (
    "病机",
    "辨证",
    "寒热",
    "虚实",
    "表里",
    "气机",
    "枢机",
    "水饮",
    "痰浊",
    "津伤",
    "阳虚",
    "阳郁",
    "少阳",
    "太阴",
    "厥阴",
    "通阴阳",
    "升阳",
    "散火",
    "化阴",
    "化阳",
)
COMPARABLE_ENTITY_SUFFIXES = ("汤", "散", "丸", "饮", "膏", "丹", "方", "颗粒", "胶囊", "证", "病", "法")
COMPARISON_NOISE_TERMS = {
    "组成",
    "功效",
    "治法",
    "病机",
    "配伍",
    "加减法",
    "和解少阳",
    "少阳咳",
    "原文",
    "出处",
    "来源",
    "咳者",
}
COMPARISON_NOISE_PREFIXES = ("请从", "请结合", "分析", "论述", "论证", "比较", "鉴别", "说明", "解释")
SOURCE_TEXT_MARKERS = ("原文", "原句", "原话", "原段", "条文", "方后注")
ORIGIN_BOOK_MARKERS = ("出处", "出自", "哪本书", "哪部书")
SOURCE_TRACE_MARKERS = (*ORIGIN_BOOK_MARKERS, *SOURCE_TEXT_MARKERS, "佐证", "来源")
DEEP_FACET_QUERY_MARKERS = ("分析", "论述", "论证", "辨析", "鉴别", "为什么", "病机", "异同", "比较")


def _init_coverage_state(*, query: str, payload: dict[str, Any], evidence_paths: list[str]) -> dict[str, Any]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    compare_entities = _refine_compare_entities(
        raw_entities=strategy.get("compare_entities", analysis.get("compare_entities", [])),
        entity_name=str(strategy.get("entity_name", "")).strip(),
        evidence_paths=evidence_paths,
    )
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
        "entity_anchor_hits": 0,
        "comparison_signal_count": 0,
        "reasoning_signal_count": 0,
        "compare_joint_signal": False,
        "_coverage_dirty": True,
        "_cached_gaps": None,
        "_cached_summary": None,
    }


def _update_coverage_state(
    state: dict[str, Any],
    *,
    new_factual_evidence: list[dict[str, Any]] | None = None,
    new_case_references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state["_coverage_dirty"] = True
    state["_cached_gaps"] = None
    state["_cached_summary"] = None
    factual = new_factual_evidence or []
    cases = new_case_references or []
    entity_name = str(state.get("entity_name", "")).strip()

    for item in factual:
        source_type = str(item.get("source_type", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        source_book = str(item.get("source_book", "")).strip()
        target = str(item.get("target", "")).strip()
        anchor_entity = str(item.get("anchor_entity", "")).strip()
        haystack = " ".join(
            [
                str(item.get("source", "")).strip(),
                snippet,
                predicate,
                target,
                str(item.get("source_text", "")).strip(),
                anchor_entity,
                source_book,
                str(item.get("source_chapter", "")).strip(),
            ]
        )
        state["factual_count"] += 1
        if source_type:
            state["source_types"].add(source_type)
        if predicate:
            state["predicates"].add(predicate)
        if source_book and source_type == "graph":
            state["graph_source_books"].add(source_book)
        if source_book and source_type in DOC_LIKE_SOURCE_TYPES:
            state["doc_source_books"].add(source_book)
        if source_book or source_type in {"doc", "graph", "graph_path"}:
            state["has_source_trace_support"] = True
        if len(snippet) >= 16 and (source_book or source_type in {"doc", "graph", "graph_path"}):
            state["has_source_trace_text"] = True
        if source_type in DOC_LIKE_SOURCE_TYPES and source_book:
            state["has_doc_source_trace_support"] = True
        if source_type in DOC_LIKE_SOURCE_TYPES and len(snippet) >= 16:
            state["has_doc_source_trace_text"] = True
        if entity_name:
            if anchor_entity == entity_name:
                state["entity_anchor_hits"] += 1
            if entity_name in haystack:
                state["has_origin_doc_support"] = True
                if source_type in DOC_LIKE_SOURCE_TYPES:
                    state["has_doc_origin_support"] = True
            if source_book and len(snippet) >= 12 and entity_name in snippet:
                state["has_origin_text_support"] = True
                if source_type in DOC_LIKE_SOURCE_TYPES:
                    state["has_doc_origin_text"] = True
        elif snippet:
            state["has_origin_doc_support"] = True
            if len(snippet) >= 12:
                state["has_origin_text_support"] = True
            if source_type in DOC_LIKE_SOURCE_TYPES:
                state["has_doc_origin_support"] = True
                if len(snippet) >= 12:
                    state["has_doc_origin_text"] = True
        if source_type == "graph_path" or predicate == "辨证链" or (isinstance(item.get("path_nodes"), list) and len([str(node).strip() for node in item.get("path_nodes", []) if str(node).strip()]) >= 2):
            state["has_path_reasoning"] = True
            state["reasoning_signal_count"] += 1
        elif _item_supports_reasoning(predicate=predicate, haystack=haystack):
            state["reasoning_signal_count"] += 1
        matched_compare_entities = _matched_compare_entities(
            compare_entities=state.get("compare_entities", []),
            haystack=haystack,
            anchor_entity=anchor_entity,
        )
        for matched in matched_compare_entities:
            state["compare_covered"].add(matched)
        if matched_compare_entities:
            state["comparison_signal_count"] += max(1, len(matched_compare_entities))
            if len(matched_compare_entities) >= 2:
                state["compare_joint_signal"] = True

    for _ in cases:
        state["case_count"] += 1
    return state


def _coverage_gaps_from_state(state: dict[str, Any]) -> list[str]:
    if not state.get("_coverage_dirty") and isinstance(state.get("_cached_gaps"), list):
        return list(state["_cached_gaps"])
    query = str(state.get("query", "")).strip()
    intent = str(state.get("intent", "")).strip()
    entity_name = str(state.get("entity_name", "")).strip()
    predicates = set(state.get("predicates", set()))
    source_types = set(state.get("source_types", set()))
    compare_entities = list(state.get("compare_entities", []))
    sources = set(state.get("sources", set()))

    wants_source_text = any(marker in query for marker in SOURCE_TEXT_MARKERS)
    wants_origin_book = any(marker in query for marker in ORIGIN_BOOK_MARKERS)
    requires_formula_anchor = bool(entity_name) and entity_name.endswith(("汤", "散", "丸", "饮", "膏", "丹", "方", "颗粒", "胶囊"))

    gaps: list[str] = []
    if intent == "formula_composition" and "使用药材" not in predicates:
        gaps.append("composition")
    if intent == "formula_composition" and requires_formula_anchor and int(state.get("entity_anchor_hits", 0)) <= 0 and not state.get("has_origin_doc_support"):
        gaps.append("composition")
    if intent == "formula_efficacy" and not predicates.intersection({"功效", "治法", "归经"}):
        gaps.append("efficacy")
    if intent == "formula_efficacy" and requires_formula_anchor and int(state.get("entity_anchor_hits", 0)) <= 0 and not state.get("has_origin_doc_support"):
        gaps.append("efficacy")
    if intent == "formula_indication" and not predicates.intersection({"治疗证候", "治疗症状", "治疗疾病"}):
        gaps.append("indication")
    if intent == "formula_indication" and requires_formula_anchor and int(state.get("entity_anchor_hits", 0)) <= 0 and not state.get("has_origin_doc_support"):
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

    if _needs_path_reasoning(query=query) and not _path_reasoning_state_sufficient(state):
        gaps.append("path_reasoning")
    if compare_entities and not _comparison_state_sufficient(state):
        gaps.append("comparison")
    if ("qa_case_structured_index" in sources or "qa_case_vector_db" in sources or intent == "syndrome_to_formula") and int(state.get("case_count", 0)) <= 0 and _query_benefits_from_case_reference(query=query):
        gaps.append("case_reference")
    resolved = list(dict.fromkeys(gaps))
    state["_cached_gaps"] = list(resolved)
    state["_coverage_dirty"] = False
    return resolved


def _coverage_summary_from_state(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("_coverage_dirty") and isinstance(state.get("_cached_summary"), dict):
        return dict(state["_cached_summary"])
    gaps = _coverage_gaps_from_state(state)
    summary = {
        "gaps": gaps,
        "factual_count": int(state.get("factual_count", 0)),
        "case_count": int(state.get("case_count", 0)),
        "evidence_path_count": int(state.get("evidence_path_count", 0)),
        "sufficient": not gaps,
    }
    state["_cached_summary"] = dict(summary)
    state["_coverage_dirty"] = False
    return summary


def _deep_quality_gaps_from_state(state: dict[str, Any]) -> list[str]:
    query = str(state.get("query", "")).strip()
    intent = str(state.get("intent", "")).strip()
    compare_entities = list(state.get("compare_entities", []))
    predicates = set(state.get("predicates", set()))
    graph_books = set(state.get("graph_source_books", set()))
    doc_books = set(state.get("doc_source_books", set()))
    total_books = {str(item).strip() for item in graph_books.union(doc_books) if str(item).strip()}
    reasoning_signal_count = int(state.get("reasoning_signal_count", 0) or 0)

    gaps: list[str] = []
    wants_multi_facet = intent in {"compare_entities", "formula_origin"} or any(marker in query for marker in DEEP_FACET_QUERY_MARKERS)
    wants_strong_source = _needs_origin_support(query=query, intent=intent) or _needs_source_trace(query=query) or wants_multi_facet

    has_direct_source_text = bool(state.get("has_source_trace_text")) or bool(state.get("has_doc_source_trace_text"))

    if wants_multi_facet:
        if compare_entities:
            if not _comparison_state_sufficient(state):
                gaps.append("comparison")
            if reasoning_signal_count < (1 if state.get("compare_joint_signal") else 2):
                gaps.append("path_reasoning")
        elif _needs_path_reasoning(query=query) and not _path_reasoning_state_sufficient(state):
            gaps.append("path_reasoning")
        elif reasoning_signal_count < 2 and predicates.intersection(REASONING_PREDICATES):
            gaps.append("path_reasoning")

    if wants_strong_source:
        has_chapter_support = "chapter" in set(state.get("source_types", set())) or has_direct_source_text
        if len(total_books) < 2 and not has_chapter_support:
            if compare_entities:
                gaps.append("source_trace")
            elif _needs_origin_support(query=query, intent=intent):
                gaps.append("origin")
            else:
                gaps.append("source_trace")
        elif _query_requests_direct_passage(query=query) and not has_chapter_support:
            gaps.append("source_trace")

    return list(dict.fromkeys(gaps))


def _needs_origin_support(*, query: str, intent: str) -> bool:
    return intent == "formula_origin" or any(marker in query for marker in (*ORIGIN_BOOK_MARKERS, *SOURCE_TEXT_MARKERS))


def _needs_source_trace(*, query: str) -> bool:
    return any(marker in query for marker in SOURCE_TRACE_MARKERS)


def _query_requests_direct_passage(*, query: str) -> bool:
    return any(marker in query for marker in SOURCE_TEXT_MARKERS)


def _needs_path_reasoning(*, query: str) -> bool:
    return any(marker in query for marker in ("病机", "辨证", "链路", "为什么", "异同", "区别", "比较", "共同点"))


def _query_benefits_from_case_reference(*, query: str) -> bool:
    return any(marker in query for marker in ("医案", "病例", "案例", "经验", "临床", "辨证", "主诉", "现病史"))


def _refine_compare_entities(*, raw_entities: Any, entity_name: str, evidence_paths: list[str]) -> list[str]:
    if not isinstance(raw_entities, list):
        return []
    candidates: list[str] = []
    seen = set()
    for item in raw_entities:
        entity = str(item or "").strip()
        if not entity or entity in seen:
            continue
        seen.add(entity)
        if _is_noise_compare_entity(entity):
            continue
        candidates.append(entity)
    if len(candidates) <= 1:
        return candidates

    focused = [entity for entity in candidates if _looks_like_primary_compare_target(entity)]
    if len(focused) >= 2:
        return _prepend_entity_name(entity_name=entity_name, entities=focused)[:3]

    path_entities = []
    for path in evidence_paths:
        normalized = str(path or "").strip()
        if not normalized.startswith("entity://"):
            continue
        body = normalized.removeprefix("entity://")
        entity = body.split("/", 1)[0].strip()
        if entity and entity in candidates and not _is_noise_compare_entity(entity):
            path_entities.append(entity)
    path_entities = list(dict.fromkeys(path_entities))
    if len(path_entities) >= 2:
        return _prepend_entity_name(entity_name=entity_name, entities=path_entities)[:3]

    return _prepend_entity_name(entity_name=entity_name, entities=candidates)[:3] if len(candidates) >= 2 else []


def _prepend_entity_name(*, entity_name: str, entities: list[str]) -> list[str]:
    ordered = [entity for entity in entities if entity]
    if entity_name and entity_name in ordered:
        ordered = [entity_name, *[item for item in ordered if item != entity_name]]
    return list(dict.fromkeys(ordered))


def _is_noise_compare_entity(entity: str) -> bool:
    normalized = str(entity or "").strip()
    if not normalized or len(normalized) < 2:
        return True
    if normalized in COMPARISON_NOISE_TERMS:
        return True
    return any(normalized.startswith(prefix) for prefix in COMPARISON_NOISE_PREFIXES)


def _looks_like_primary_compare_target(entity: str) -> bool:
    normalized = str(entity or "").strip()
    if _is_noise_compare_entity(normalized):
        return False
    return normalized.endswith(COMPARABLE_ENTITY_SUFFIXES)


def _origin_support_sufficient(*, query: str, entity_name: str, factual_evidence: list[dict[str, Any]], source_types: set[str]) -> bool:
    wants_source_text = any(marker in query for marker in SOURCE_TEXT_MARKERS)
    wants_origin_book = any(marker in query for marker in ORIGIN_BOOK_MARKERS)
    has_graph_book = any(str(item.get("source_book", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip() == "graph")
    has_doc_book = any(str(item.get("source_book", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip() in DOC_LIKE_SOURCE_TYPES)
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
                if source_type in DOC_LIKE_SOURCE_TYPES:
                    has_doc_entity_linked_passage = True
            if source_type in DOC_LIKE_SOURCE_TYPES and source_book and len(snippet) >= 12 and entity_name in snippet:
                has_doc_origin_text = True
        elif snippet:
            has_entity_linked_passage = True
            if source_type in DOC_LIKE_SOURCE_TYPES:
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
    wants_source_text = any(marker in query for marker in SOURCE_TEXT_MARKERS)
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
        if source_type in DOC_LIKE_SOURCE_TYPES and source_book:
            has_doc_source_trace_support = True
        if source_type in DOC_LIKE_SOURCE_TYPES and len(snippet) >= 16:
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
        haystack = " ".join(
            [
                str(item.get("source", "")),
                str(item.get("snippet", "")),
                str(item.get("predicate", "")),
                str(item.get("target", "")),
                str(item.get("source_book", "")),
                str(item.get("anchor_entity", "")),
            ]
        )
        if source_type == "graph_path" or predicate == "辨证链":
            return True
        if isinstance(item.get("path_nodes"), list) and len([str(node).strip() for node in item.get("path_nodes", []) if str(node).strip()]) >= 2:
            return True
        if _item_supports_reasoning(predicate=predicate, haystack=haystack):
            return True
    return False


def _compare_entities_covered(*, compare_entities: list[str], factual_evidence: list[dict[str, Any]]) -> bool:
    if not compare_entities:
        return True
    covered = set()
    for entity in compare_entities:
        for item in factual_evidence:
            haystack = " ".join(
                [
                    str(item.get("source", "")),
                    str(item.get("snippet", "")),
                    str(item.get("predicate", "")),
                    str(item.get("target", "")),
                    str(item.get("anchor_entity", "")),
                ]
            )
            if entity and entity in haystack:
                covered.add(entity)
                break
    return len(covered) >= len(compare_entities)


def _item_supports_reasoning(*, predicate: str, haystack: str) -> bool:
    if predicate in REASONING_PREDICATES:
        return True
    return any(marker in haystack for marker in REASONING_MARKERS)


def _matched_compare_entities(*, compare_entities: list[str], haystack: str, anchor_entity: str) -> set[str]:
    matched: set[str] = set()
    for entity in compare_entities:
        if not entity:
            continue
        if entity == anchor_entity or entity in haystack:
            matched.add(entity)
    return matched


def _comparison_state_sufficient(state: dict[str, Any]) -> bool:
    compare_entities = list(state.get("compare_entities", []))
    if not compare_entities:
        return True
    covered_count = len(state.get("compare_covered", set()))
    if covered_count < len(compare_entities):
        return False
    required_signals = max(2, min(len(compare_entities), 3))
    if int(state.get("comparison_signal_count", 0)) >= required_signals:
        return True
    if bool(state.get("compare_joint_signal")):
        return True
    return int(state.get("reasoning_signal_count", 0)) >= required_signals


def _path_reasoning_state_sufficient(state: dict[str, Any]) -> bool:
    if state.get("has_path_reasoning"):
        return True
    compare_entities = list(state.get("compare_entities", []))
    required_signals = 2 if compare_entities else 1
    if int(state.get("reasoning_signal_count", 0)) < required_signals:
        return False
    if compare_entities:
        return _comparison_state_sufficient(state)
    return True


def _identify_evidence_gaps(*, query: str, payload: dict[str, Any], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> list[str]:
    state = _init_coverage_state(query=query, payload=payload, evidence_paths=payload.get("evidence_paths", []) if isinstance(payload.get("evidence_paths", []), list) else [])
    _update_coverage_state(state, new_factual_evidence=factual_evidence, new_case_references=case_references)
    return _coverage_gaps_from_state(state)


def _coverage_summary(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> dict[str, Any]:
    state = _init_coverage_state(query=query, payload=payload, evidence_paths=evidence_paths)
    _update_coverage_state(state, new_factual_evidence=factual_evidence, new_case_references=case_references)
    return _coverage_summary_from_state(state)
