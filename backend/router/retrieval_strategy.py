from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from router.tcm_intent_classifier import GraphQueryKind, QueryAnalysis, RouteName, analyze_tcm_query


@dataclass
class RetrievalStrategy:
    intent: str
    preferred_route: RouteName
    graph_query_kind: GraphQueryKind
    graph_query_text: str
    entity_name: str = ""
    symptom_name: str = ""
    path_start: str = ""
    path_end: str = ""
    compare_entities: list[str] = field(default_factory=list)
    predicate_allowlist: list[str] = field(default_factory=list)
    predicate_blocklist: list[str] = field(default_factory=list)
    graph_candidate_k: int = 24
    graph_final_k: int = 12
    vector_candidate_k: int = 24
    sources: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def derive_retrieval_strategy(
    query: str,
    *,
    requested_top_k: int,
    route_hint: RouteName,
    analysis: QueryAnalysis | None = None,
) -> RetrievalStrategy:
    text = (query or "").strip()
    final_k = max(1, requested_top_k)
    resolved = analysis or analyze_tcm_query(text)

    if resolved.graph_query_kind == "path" and resolved.path_start and resolved.path_end:
        preferred_route = route_hint if route_hint == "hybrid" else "graph"
        strategy = RetrievalStrategy(
            intent="graph_path",
            preferred_route=preferred_route,
            graph_query_kind="path",
            graph_query_text=text,
            path_start=resolved.path_start,
            path_end=resolved.path_end,
            compare_entities=resolved.compare_entities(),
            graph_candidate_k=max(final_k * 3, 12),
            graph_final_k=min(final_k, 5),
            vector_candidate_k=max(final_k * 2, 8),
            sources=["graph_sqlite", "graph_nebula"] if preferred_route == "graph" else ["graph_sqlite", "graph_nebula", "qa_vector_db", "classic_docs"],
            notes=resolved.notes + ["path query detected from classifier"],
        )
        strategy.evidence_paths = [
            f"path://{strategy.path_start}->{strategy.path_end}",
            f"entity://{strategy.path_start}/*",
            f"entity://{strategy.path_end}/*",
        ]
        if preferred_route == "hybrid":
            strategy.evidence_paths.append(f"qa://{strategy.path_start}->{strategy.path_end}/similar")
        return strategy

    intent = resolved.dominant_intent
    preferred_route = route_hint
    graph_query_kind = resolved.graph_query_kind
    entity_name = resolved.primary_entity if graph_query_kind == "entity" else ""
    symptom_name = resolved.symptom_name if graph_query_kind == "syndrome" else ""
    compare_entities = resolved.compare_entities()
    predicate_allowlist: list[str] = []
    predicate_blocklist: list[str] = []
    sources = _default_sources(route_hint)
    notes = list(resolved.notes)

    if intent == "formula_composition":
        preferred_route = "graph"
        predicate_allowlist = ["使用药材"]
        sources = ["graph_sqlite", "graph_nebula"]
    elif intent == "formula_efficacy":
        preferred_route = "graph"
        predicate_allowlist = ["功效", "治法", "归经"]
        sources = ["graph_sqlite", "graph_nebula"]
    elif intent == "formula_indication":
        preferred_route = "graph"
        predicate_allowlist = ["治疗证候", "治疗症状", "治疗疾病", "推荐方剂"]
        sources = ["graph_sqlite", "graph_nebula"]
    elif intent == "formula_origin":
        preferred_route = "hybrid"
        predicate_allowlist = []
        sources = ["graph_sqlite", "graph_nebula", "qa_vector_db", "classic_docs"]
        notes.append("origin queries keep graph lookup broad to expose source-book clues")
    elif intent == "compare_entities":
        preferred_route = "hybrid"
        sources = ["graph_sqlite", "graph_nebula", "qa_vector_db", "classic_docs"]
    elif intent == "syndrome_to_formula":
        preferred_route = "graph"
        if graph_query_kind == "entity":
            predicate_allowlist = ["推荐方剂", "常见症状", "治疗证候"]
        else:
            predicate_allowlist = ["推荐方剂"]
        sources = ["graph_sqlite", "graph_nebula"]
    elif route_hint == "retrieval":
        sources = ["qa_vector_db", "classic_docs"]

    if _should_use_case_qa(text=text, intent=intent, analysis=resolved):
        if "qa_case_vector_db" not in sources:
            sources.append("qa_case_vector_db")
        notes.append("case qa vector source enabled")

    graph_candidate_k, graph_final_k, vector_candidate_k = _tune_k(
        intent=intent,
        final_k=final_k,
        route=preferred_route,
    )

    graph_query_text = entity_name or symptom_name or text
    strategy = RetrievalStrategy(
        intent=intent,
        preferred_route=preferred_route,
        graph_query_kind=graph_query_kind,
        graph_query_text=graph_query_text,
        entity_name=entity_name,
        symptom_name=symptom_name,
        compare_entities=compare_entities,
        predicate_allowlist=predicate_allowlist,
        predicate_blocklist=predicate_blocklist,
        graph_candidate_k=graph_candidate_k,
        graph_final_k=graph_final_k,
        vector_candidate_k=vector_candidate_k,
        sources=sources,
        notes=notes + [f"classifier_dominant_intent={intent}"],
    )
    strategy.evidence_paths = _build_evidence_paths(strategy, resolved)
    return strategy


def _default_sources(route: RouteName) -> list[str]:
    if route == "graph":
        return ["graph_sqlite", "graph_nebula"]
    if route == "retrieval":
        return ["qa_vector_db", "classic_docs"]
    return ["graph_sqlite", "graph_nebula", "qa_vector_db", "classic_docs"]


def _tune_k(*, intent: str, final_k: int, route: RouteName) -> tuple[int, int, int]:
    graph_candidate_k = max(final_k * 4, 24)
    graph_final_k = final_k
    vector_candidate_k = max(final_k * 3, 12)

    if intent == "formula_origin":
        graph_candidate_k = max(final_k * 3, 24)
        vector_candidate_k = max(final_k * 4, 16)
    elif intent == "compare_entities":
        graph_candidate_k = max(final_k * 5, 30)
        vector_candidate_k = max(final_k * 4, 18)
    elif intent == "syndrome_to_formula":
        graph_candidate_k = max(final_k * 3, 20)
    elif route == "retrieval":
        graph_candidate_k = max(final_k * 2, 12)
        vector_candidate_k = max(final_k * 4, 16)

    return graph_candidate_k, graph_final_k, vector_candidate_k


def _build_evidence_paths(strategy: RetrievalStrategy, analysis: QueryAnalysis) -> list[str]:
    paths: list[str] = []

    entity_paths = strategy.compare_entities or ([strategy.entity_name] if strategy.entity_name else [])
    for entity in entity_paths:
        if not entity:
            continue
        if strategy.predicate_allowlist:
            paths.extend([f"entity://{entity}/{predicate}" for predicate in strategy.predicate_allowlist])
        else:
            paths.append(f"entity://{entity}/*")

    if strategy.symptom_name:
        paths.append(f"symptom://{strategy.symptom_name}/syndrome_chain")

    for entity in analysis.matched_entities:
        if "source_book" in entity.types:
            paths.append(f"book://{entity.name}/*")

    if "qa_vector_db" in strategy.sources and strategy.graph_query_text:
        paths.append(f"qa://{strategy.graph_query_text}/similar")
    if "qa_case_vector_db" in strategy.sources and strategy.graph_query_text:
        paths.append(f"caseqa://{strategy.graph_query_text}/similar")

    return list(dict.fromkeys(paths))


def _should_use_case_qa(*, text: str, intent: str, analysis: QueryAnalysis) -> bool:
    if intent not in {"syndrome_to_formula", "open_ended_grounded_qa", "formula_indication"}:
        return False

    case_markers = (
        "基本信息",
        "主诉",
        "现病史",
        "体格检查",
        "年龄",
        "性别",
        "舌",
        "脉",
        "口苦",
        "失眠",
        "便溏",
        "头晕",
        "腰酸",
    )
    hits = sum(1 for marker in case_markers if marker in text)
    symptom_like_hits = 0
    for entity in analysis.matched_entities:
        if "symptom" in entity.types or "syndrome" in entity.types:
            symptom_like_hits += 1
    symptom_separator_count = text.count("、") + text.count("，") + text.count(",")
    if hits >= 3 or (len(text) >= 40 and hits >= 2):
        return True
    if symptom_like_hits >= 2 and any(marker in text for marker in ("什么证候", "什么方剂", "推荐什么方剂", "可参考什么方剂")):
        return True
    if symptom_separator_count >= 3 and any(marker in text for marker in ("什么证候", "什么方剂", "推荐什么方剂", "可参考什么方剂")):
        return True
    return False
