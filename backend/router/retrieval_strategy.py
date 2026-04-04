from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Literal


RouteName = Literal["graph", "retrieval", "hybrid"]
GraphQueryKind = Literal["entity", "syndrome", "path", "none"]

COMPOSITION_KEYWORDS = ("组成", "药材", "配伍", "方组", "组方", "由什么组成")
EFFICACY_KEYWORDS = ("功效", "作用", "有什么用", "有什么功效")
INDICATION_KEYWORDS = ("主治", "适应症", "证候", "治什么", "治疗什么", "适用于", "治哪些")
SOURCE_KEYWORDS = ("出处", "出自", "原文", "古籍", "哪本书", "哪部书", "记载", "来源", "原书")
COMPARE_KEYWORDS = ("区别", "比较", "对比", "异同")
PATH_KEYWORDS = ("路径", "关系", "链路", "怎么到", "如何到")


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


def derive_retrieval_strategy(query: str, *, requested_top_k: int, route_hint: RouteName) -> RetrievalStrategy:
    text = (query or "").strip()
    final_k = max(1, requested_top_k)

    path_targets = _extract_path_targets(text)
    if path_targets is not None:
        start, end = path_targets
        strategy = RetrievalStrategy(
            intent="graph_path",
            preferred_route="graph",
            graph_query_kind="path",
            graph_query_text=text,
            path_start=start,
            path_end=end,
            graph_candidate_k=max(final_k * 3, 12),
            graph_final_k=min(final_k, 5),
            vector_candidate_k=max(final_k * 2, 8),
            sources=["graph_sqlite", "graph_nebula"],
            notes=["path query detected from explicit path wording"],
        )
        strategy.evidence_paths = [
            f"path://{strategy.path_start}->{strategy.path_end}",
            f"entity://{strategy.path_start}/*",
            f"entity://{strategy.path_end}/*",
        ]
        return strategy

    entity_name = _extract_primary_entity(text)
    intent = "open_ended_grounded_qa"
    preferred_route = route_hint
    graph_query_kind: GraphQueryKind = "entity" if entity_name else "none"
    predicate_allowlist: list[str] = []
    sources = ["graph_sqlite", "graph_nebula", "qa_vector_db"] if route_hint == "hybrid" else ["graph_sqlite", "graph_nebula"]
    notes: list[str] = []

    if _contains_any(text, COMPOSITION_KEYWORDS):
        intent = "formula_composition"
        preferred_route = "graph"
        predicate_allowlist = ["使用药材"]
        notes.append("composition intent detected")
    elif _contains_any(text, EFFICACY_KEYWORDS):
        intent = "formula_efficacy"
        preferred_route = "graph"
        predicate_allowlist = ["功效", "治法", "归经"]
        notes.append("efficacy intent detected")
    elif _contains_any(text, INDICATION_KEYWORDS):
        intent = "formula_indication"
        preferred_route = "graph"
        predicate_allowlist = ["治疗证候", "治疗症状", "治疗疾病", "推荐方剂"]
        notes.append("indication intent detected")
    elif _contains_any(text, SOURCE_KEYWORDS):
        intent = "formula_origin"
        preferred_route = "hybrid"
        predicate_allowlist = ["别名", "属于范畴", "治疗证候", "功效"]
        sources = ["graph_sqlite", "graph_nebula", "qa_vector_db", "classic_docs"]
        notes.append("source/origin intent detected")
    elif _contains_any(text, COMPARE_KEYWORDS):
        intent = "compare_entities"
        preferred_route = "hybrid"
        notes.append("comparison intent detected")

    if graph_query_kind == "none" and _looks_like_symptom_question(text):
        graph_query_kind = "syndrome"

    strategy = RetrievalStrategy(
        intent=intent,
        preferred_route=preferred_route,
        graph_query_kind=graph_query_kind,
        graph_query_text=entity_name or text,
        entity_name=entity_name,
        symptom_name=text if graph_query_kind == "syndrome" else "",
        predicate_allowlist=predicate_allowlist,
        graph_candidate_k=max(final_k * 4, 24),
        graph_final_k=final_k,
        vector_candidate_k=max(final_k * 3, 12),
        sources=sources,
        notes=notes,
    )
    strategy.evidence_paths = _build_evidence_paths(strategy)
    return strategy


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _extract_path_targets(text: str) -> tuple[str, str] | None:
    normalized = text.strip()
    if not normalized or "到" not in normalized or not _contains_any(normalized, PATH_KEYWORDS):
        return None
    left, right = normalized.split("到", 1)
    start = left.replace("从", "").replace("请问", "").replace("请解释", "").strip(" ，。？?：:的")
    end = right
    for marker in ("的路径", "路径", "关系", "链路", "怎么到", "如何到", "是什么", "有哪些", "吗"):
        end = end.split(marker, 1)[0]
    end = end.strip(" ，。？?：:的")
    if not start or not end:
        return None
    return start, end


def _extract_primary_entity(text: str) -> str:
    normalized = text.strip()
    patterns = [
        r"^(.+?)(?:的)(?:组成|药材|配伍|方组|组方|功效|作用|主治|适应症|证候|出处|原文|古籍|来源|区别|比较|对比).*$",
        r"^(.+?)(?:是什么|有哪些|有什么用|有什么功效).*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, normalized)
        if match:
            return match.group(1).strip(" ，。？?：:")
    return normalized if len(normalized) <= 24 and " " not in normalized and "？" not in normalized and "?" not in normalized else ""


def _looks_like_symptom_question(text: str) -> bool:
    return "症状" in text or ("怎么办" in text and len(text) <= 20)


def _build_evidence_paths(strategy: RetrievalStrategy) -> list[str]:
    paths: list[str] = []
    if strategy.entity_name:
        if strategy.predicate_allowlist:
            paths.extend([f"entity://{strategy.entity_name}/{predicate}" for predicate in strategy.predicate_allowlist])
        else:
            paths.append(f"entity://{strategy.entity_name}/*")
    if strategy.symptom_name:
        paths.append(f"symptom://{strategy.symptom_name}/syndrome_chain")
    if "qa_vector_db" in strategy.sources and strategy.graph_query_text:
        paths.append(f"qa://{strategy.graph_query_text}/similar")
    return paths
