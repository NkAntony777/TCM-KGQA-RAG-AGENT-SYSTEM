from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from router.query_router import decide_route
from router.retrieval_strategy import derive_retrieval_strategy
from router.tcm_intent_classifier import analyze_tcm_query


@dataclass(frozen=True)
class RoutePlan:
    analysis: Any
    decision: Any
    strategy: Any
    execution_route: str
    route_reason: str


def normalize_route_reason(*, base_reason: str, execution_route: str, strategy_override: str = "") -> str:
    parts = [str(base_reason or "").strip()]
    if strategy_override:
        parts.append(strategy_override)
    parts = [item for item in parts if item]
    if not parts:
        return execution_route
    return "; ".join(dict.fromkeys(parts))


def build_route_plan(query: str, top_k: int) -> RoutePlan:
    analysis = analyze_tcm_query(query)
    decision = decide_route(query, analysis=analysis)
    strategy = derive_retrieval_strategy(query, requested_top_k=top_k, route_hint=decision.route, analysis=analysis)
    execution_route = decision.route
    route_override_reason = ""
    if strategy.intent == "formula_origin" and strategy.entity_name and decision.route == "retrieval":
        execution_route = "hybrid"
        route_override_reason = "origin_entity_forced_hybrid"
    elif strategy.preferred_route == "graph" and decision.route == "hybrid":
        execution_route = "graph"
        route_override_reason = "strategy_graph_override"

    route_reason = normalize_route_reason(
        base_reason=decision.reason,
        execution_route=execution_route,
        strategy_override=route_override_reason,
    )
    return RoutePlan(
        analysis=analysis,
        decision=decision,
        strategy=strategy,
        execution_route=execution_route,
        route_reason=route_reason,
    )
