from __future__ import annotations

from typing import Any

from services.qa_service.models import AnswerMode


FACET_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("composition", ("组成", "药材", "配方", "组方", "使用药材")),
    ("efficacy", ("功效", "作用", "治法", "益气", "止血")),
    ("indication", ("主治", "适应证", "治什么", "证候", "病症")),
    ("origin", ("出处", "出自", "来源", "原文", "原句", "原话", "方后注")),
    ("path_reasoning", ("病机", "机制", "原理", "为什么", "方义", "配伍")),
    ("comparison", ("比较", "异同", "差异", "区别", "对比")),
    ("case_reference", ("案例", "医案", "病例")),
    ("meridian", ("归经",)),
    ("nature_flavor", ("性味",)),
    ("modern", ("现代", "通路", "分子", "免疫", "临床试验", "HERB2")),
)

PREDICATE_FACETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("composition", ("使用药材", "组成", "药材", "配伍")),
    ("efficacy", ("功效", "治法", "作用")),
    ("indication", ("主治", "适应证", "治疗疾病", "治疗证候")),
    ("origin", ("出处", "来源", "载于", "出自")),
    ("path_reasoning", ("病机", "机制", "证候", "推荐方剂")),
    ("meridian", ("归经",)),
    ("nature_flavor", ("性味",)),
)

FACET_LABELS = {
    "composition": "组成",
    "efficacy": "功效",
    "indication": "主治",
    "origin": "出处",
    "path_reasoning": "病机/机制",
    "comparison": "异同",
    "case_reference": "案例参考",
    "meridian": "归经",
    "nature_flavor": "性味",
    "modern": "现代证据",
    "general": "综合证据",
}

DOC_SOURCE_TYPES = {"doc", "chapter"}
STRUCTURED_SOURCE_TYPES = {"graph", "graph_path", "graph_alias"}


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    text = str(value or "").strip()
    if limit is not None:
        return text[:limit]
    return text


def _source_label(item: dict[str, Any]) -> str:
    source_book = _clean_text(item.get("source_book"))
    source_chapter = _clean_text(item.get("source_chapter"))
    if source_book and source_chapter:
        return f"{source_book}/{source_chapter}"
    if source_book:
        return source_book
    document = _clean_text(item.get("document"), limit=80)
    if document:
        return document
    return _clean_text(item.get("source"), limit=120) or "unknown"


def _source_path(item: dict[str, Any]) -> str:
    for key in ("evidence_path", "source_scope_path", "file_path", "source"):
        value = _clean_text(item.get(key))
        if value:
            return value
    return ""


def _claim_text(item: dict[str, Any]) -> str:
    anchor = _clean_text(item.get("anchor_entity"))
    predicate = _clean_text(item.get("predicate"))
    target = _clean_text(item.get("target"))
    if predicate and target:
        prefix = f"{anchor} -> " if anchor else ""
        return f"{prefix}{predicate}: {target}"
    if target:
        return target
    snippet = _clean_text(item.get("match_snippet") or item.get("snippet"), limit=96)
    return snippet or "命中相关证据"


def _excerpt_text(item: dict[str, Any], *, mode: AnswerMode, full_evidence_mode: bool = False) -> str:
    if full_evidence_mode:
        return _clean_text(
            item.get("source_text")
            or item.get("match_snippet")
            or item.get("snippet"),
        )
    limit = 180 if mode == "quick" else 260
    return _clean_text(
        item.get("source_text")
        or item.get("match_snippet")
        or item.get("snippet"),
        limit=limit,
    )


def _query_terms(query: str, payload: dict[str, Any]) -> set[str]:
    terms = {word for word in _clean_text(query).replace("，", " ").replace("。", " ").split() if word}
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    for key in ("entity_name", "symptom_name"):
        value = _clean_text(strategy.get(key) or analysis.get(key))
        if value:
            terms.add(value)
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    if isinstance(compare_entities, list):
        for item in compare_entities:
            value = _clean_text(item)
            if value:
                terms.add(value)
    return terms


def _requested_facets(query: str, payload: dict[str, Any]) -> list[str]:
    text = _clean_text(query)
    facets: list[str] = []
    for facet, hints in FACET_HINTS:
        if any(hint in text for hint in hints):
            facets.append(facet)

    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    intent = _clean_text(strategy.get("intent"))
    intent_facets = {
        "formula_composition": "composition",
        "formula_efficacy": "efficacy",
        "formula_origin": "origin",
        "syndrome_formula": "indication",
        "compare_entities": "comparison",
    }
    if intent in intent_facets:
        facets.append(intent_facets[intent])
    if _clean_text(strategy.get("answer_policy")) in {"graph_relation_with_origin"}:
        facets.append("origin")
    if not facets:
        facets.append("general")
    if "origin" not in facets:
        facets.append("origin")
    return list(dict.fromkeys(facets))


def _facet_for_item(item: dict[str, Any], query: str) -> str:
    source_type = _clean_text(item.get("source_type"))
    if _clean_text(item.get("evidence_type")) == "case_reference" or source_type == "case_qa":
        return "case_reference"
    predicate = _clean_text(item.get("predicate"))
    target = _clean_text(item.get("target"))
    snippet = _clean_text(item.get("snippet"))
    haystack = " ".join([predicate, target, snippet, _clean_text(item.get("source_book")), _clean_text(item.get("source_chapter"))])
    for facet, predicates in PREDICATE_FACETS:
        if any(token and token in predicate for token in predicates):
            return facet
    for facet, hints in FACET_HINTS:
        if any(hint in haystack for hint in hints):
            return facet
    if source_type in DOC_SOURCE_TYPES and any(hint in query for hint in ("出处", "原文", "出自", "原句")):
        return "origin"
    return "general"


SCORE_FACET_MATCH = 5.0
SCORE_QUERY_TERM_MATCH = 2.0
SCORE_SOURCE_LABEL_KNOWN = 1.2
SCORE_HAS_EXCERPT = 0.8
SCORE_DOC_SOURCE_TYPE = 0.7
SCORE_STRUCTURED_TYPE = 0.5
SCORE_PATH_HAS_SCHEME = 0.5


def _score_item(item: dict[str, Any], *, facet: str, required_facets: list[str], query_terms: set[str]) -> float:
    score = float(item.get("score", 0.0) or 0.0)
    source_type = _clean_text(item.get("source_type"))
    text = " ".join(
        _clean_text(item.get(key))
        for key in ("anchor_entity", "source", "source_book", "source_chapter", "predicate", "target", "snippet", "source_text")
    )
    if facet in required_facets:
        score += SCORE_FACET_MATCH
    if any(term and term in text for term in query_terms):
        score += SCORE_QUERY_TERM_MATCH
    if _source_label(item) != "unknown":
        score += SCORE_SOURCE_LABEL_KNOWN
    if _excerpt_text(item, mode="deep"):
        score += SCORE_HAS_EXCERPT
    if source_type in DOC_SOURCE_TYPES:
        score += SCORE_DOC_SOURCE_TYPE
    if source_type in STRUCTURED_SOURCE_TYPES:
        score += SCORE_STRUCTURED_TYPE
    if _source_path(item).startswith(("book://", "chapter://", "entity://", "alias://")):
        score += SCORE_PATH_HAS_SCHEME
    return score


def _card_from_item(
    item: dict[str, Any],
    *,
    facet: str,
    mode: AnswerMode,
    reason: str,
    full_evidence_mode: bool = False,
) -> dict[str, Any]:
    source_type = _clean_text(item.get("source_type")) or "unknown"
    return {
        "facet": facet,
        "facet_label": FACET_LABELS.get(facet, facet),
        "claim": _claim_text(item),
        "source_label": _source_label(item),
        "source_path": _source_path(item),
        "source_type": source_type,
        "excerpt": _excerpt_text(item, mode=mode, full_evidence_mode=full_evidence_mode),
        "score": item.get("score"),
        "why_selected": reason,
        "used_for_answer": True,
    }


def _identity_for_card(card: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean_text(card.get("facet")),
        _clean_text(card.get("claim")),
        _clean_text(card.get("source_label")),
    )


def _select_full_evidence(
    *, query: str, candidates: list[dict[str, Any]], required_facets: list[str], mode: AnswerMode
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    seen = set()
    for item in candidates:
        facet = _facet_for_item(item, query)
        card = _card_from_item(item, facet=facet, mode=mode, reason="全证据模式：保留全部检索证据", full_evidence_mode=True)
        key = _identity_for_card(card)
        if key in seen:
            continue
        seen.add(key)
        selected.append(card)
    covered_facets = list(dict.fromkeys(_clean_text(card.get("facet")) for card in selected if _clean_text(card.get("facet"))))
    missing_facets = [facet for facet in required_facets if facet not in covered_facets and facet != "origin"]
    notes = [
        "selector_mode:full_evidence",
        f"selector_candidates:{len(candidates)}",
        f"selector_selected:{len(selected)}",
    ]
    return {
        "selected_cards": selected,
        "required_facets": required_facets,
        "covered_facets": covered_facets,
        "missing_facets": missing_facets,
        "selection_notes": notes,
    }


def _select_compact_evidence(
    *, query: str, payload: dict[str, Any], mode: AnswerMode, factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], evidence_paths: list[str], required_facets: list[str]
) -> dict[str, Any]:
    budget = 10 if mode == "quick" else 24
    per_facet_limit = 3 if mode == "quick" else 5
    query_terms = _query_terms(query, payload)
    candidates = list(factual_evidence) + list(case_references)
    by_facet: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    for item in candidates:
        facet = _facet_for_item(item, query)
        by_facet.setdefault(facet, []).append(
            (_score_item(item, facet=facet, required_facets=required_facets, query_terms=query_terms), item)
        )
    for items in by_facet.values():
        items.sort(key=lambda entry: entry[0], reverse=True)

    selected: list[dict[str, Any]] = []
    seen = set()

    def add_card(facet: str, item: dict[str, Any], reason: str) -> None:
        if len(selected) >= budget:
            return
        card = _card_from_item(item, facet=facet, mode=mode, reason=reason, full_evidence_mode=False)
        key = _identity_for_card(card)
        if key in seen:
            return
        seen.add(key)
        selected.append(card)

    for facet in required_facets:
        facet_items = by_facet.get(facet, [])
        for _, item in facet_items[:per_facet_limit]:
            add_card(facet, item, f"覆盖用户问题所需维度：{FACET_LABELS.get(facet, facet)}")

    if len(selected) < budget:
        for facet in ("efficacy", "composition", "indication", "origin", "meridian", "path_reasoning", "modern", "general"):
            if facet in required_facets:
                continue
            for _, item in by_facet.get(facet, [])[:1]:
                add_card(facet, item, f"补充{FACET_LABELS.get(facet, facet)}维度")
                if len(selected) >= budget:
                    break
            if len(selected) >= budget:
                break

    if len(selected) < budget and "case_reference" in by_facet:
        for _, item in by_facet["case_reference"][:1]:
            add_card("case_reference", item, "提供病例或问答参考")

    covered_facets = list(dict.fromkeys(_clean_text(card.get("facet")) for card in selected if _clean_text(card.get("facet"))))
    missing_facets = [facet for facet in required_facets if facet not in covered_facets and facet != "origin"]
    if "origin" in required_facets and not any(card.get("source_label") and card.get("source_label") != "unknown" for card in selected):
        missing_facets.append("origin")
    missing_facets = list(dict.fromkeys(missing_facets))

    notes = [
        f"selector_budget:{budget}",
        f"selector_candidates:{len(candidates)}",
        f"selector_selected:{len(selected)}",
    ]
    if missing_facets:
        notes.append("selector_missing_facets:" + ",".join(missing_facets))
    if evidence_paths and not selected:
        notes.append("selector_has_paths_but_no_cards")

    return {
        "selected_cards": selected,
        "required_facets": required_facets,
        "covered_facets": covered_facets,
        "missing_facets": missing_facets,
        "selection_notes": notes,
    }


def select_evidence_for_answer(
    *,
    query: str,
    payload: dict[str, Any],
    mode: AnswerMode,
    factual_evidence: list[dict[str, Any]],
    case_references: list[dict[str, Any]],
    evidence_paths: list[str],
    full_evidence_mode: bool = False,
) -> dict[str, Any]:
    required_facets = _requested_facets(query, payload)
    if full_evidence_mode:
        candidates = list(factual_evidence) + list(case_references)
        return _select_full_evidence(query=query, candidates=candidates, required_facets=required_facets, mode=mode)
    return _select_compact_evidence(
        query=query, payload=payload, mode=mode,
        factual_evidence=factual_evidence, case_references=case_references,
        evidence_paths=evidence_paths, required_facets=required_facets,
    )
