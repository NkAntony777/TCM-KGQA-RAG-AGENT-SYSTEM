from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from router.tcm_intent_classifier import QueryAnalysis, analyze_tcm_query


RouteName = Literal["graph", "retrieval", "hybrid"]


@dataclass
class RouteDecision:
    route: RouteName
    reason: str


def decide_route(query: str, *, analysis: QueryAnalysis | None = None) -> RouteDecision:
    resolved = analysis or analyze_tcm_query(query)
    return RouteDecision(route=resolved.route_hint, reason=resolved.route_reason)
