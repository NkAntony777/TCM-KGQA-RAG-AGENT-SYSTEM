from __future__ import annotations

from tools.tcm_route_planning import build_route_plan, normalize_route_reason


def test_normalize_route_reason_dedupes_strategy_override() -> None:
    assert normalize_route_reason(
        base_reason="hybrid",
        execution_route="hybrid",
        strategy_override="hybrid",
    ) == "hybrid"


def test_origin_entity_forces_hybrid_execution_plan() -> None:
    plan = build_route_plan("六味地黄丸出自哪本书？请给出处原文。", 6)

    assert plan.strategy.intent == "formula_origin"
    assert plan.execution_route == "hybrid"
    assert "formula_origin" in plan.route_reason
