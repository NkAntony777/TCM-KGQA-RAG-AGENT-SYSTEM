from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RouteName = Literal["graph", "retrieval", "hybrid"]

GRAPH_SIGNALS: dict[str, int] = {
    "证候": 3,
    "方剂": 3,
    "药材": 3,
    "组成": 4,
    "组方": 4,
    "关系": 2,
    "路径": 4,
    "配伍": 4,
    "辨证": 3,
    "症状": 2,
    "归经": 3,
    "功效": 2,
    "治法": 2,
    "推荐": 2,
    "对应": 2,
    "适用于": 2,
    "适合": 1,
    "治疗": 2,
}

RETRIEVAL_SIGNALS: dict[str, int] = {
    "出处": 4,
    "出自": 4,
    "原文": 4,
    "文献": 3,
    "古籍": 3,
    "解释": 2,
    "定义": 3,
    "概念": 2,
    "记载": 3,
    "来源": 2,
    "原句": 4,
    "哪本书": 3,
    "哪部书": 3,
    "原书": 3,
    "怎么说": 2,
    "什么意思": 2,
}

BOOK_HINTS = (
    "本草纲目",
    "医方集解",
    "和剂局方",
    "医宗金鉴",
    "金匮要略",
    "伤寒论",
    "黄帝内经",
)

HYBRID_CONNECTORS = (
    "并",
    "以及",
    "同时",
    "结合",
    "并且",
    "并说明",
    "并给出",
    "并附",
)


@dataclass
class RouteDecision:
    route: RouteName
    reason: str


def _score(text: str, signals: dict[str, int]) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    for keyword, weight in signals.items():
        if keyword in text:
            score += weight
            hits.append(keyword)
    return score, hits


def decide_route(query: str) -> RouteDecision:
    text = (query or "").strip()
    if not text:
        return RouteDecision(route="retrieval", reason="empty_query_default_retrieval")

    graph_score, graph_hits = _score(text, GRAPH_SIGNALS)
    retrieval_score, retrieval_hits = _score(text, RETRIEVAL_SIGNALS)

    book_hits = [book for book in BOOK_HINTS if book in text]
    if book_hits:
        retrieval_score += len(book_hits) * 2
        retrieval_hits.extend(book_hits)

    connector_hits = [token for token in HYBRID_CONNECTORS if token in text]

    if text.startswith(("什么是", "何谓")):
        retrieval_score += 3
        retrieval_hits.append("definition_prefix")

    if "到" in text and "路径" in text:
        graph_score += 2
        graph_hits.append("path_pattern")

    if graph_score > 0 and retrieval_score > 0:
        return RouteDecision(
            route="hybrid",
            reason=(
                "hybrid_scored_match: "
                f"graph_score={graph_score}, retrieval_score={retrieval_score}, "
                f"graph_hits={graph_hits}, retrieval_hits={retrieval_hits}, connectors={connector_hits}"
            ),
        )

    if graph_score >= 3:
        return RouteDecision(
            route="graph",
            reason=f"graph_scored_match: score={graph_score}, hits={graph_hits}",
        )

    if retrieval_score >= 3:
        return RouteDecision(
            route="retrieval",
            reason=f"retrieval_scored_match: score={retrieval_score}, hits={retrieval_hits}",
        )

    if connector_hits:
        return RouteDecision(
            route="hybrid",
            reason=f"connector_only_hybrid_fallback: connectors={connector_hits}",
        )

    return RouteDecision(
        route="hybrid",
        reason=(
            "default_hybrid_low_signal: "
            f"graph_score={graph_score}, retrieval_score={retrieval_score}"
        ),
    )
