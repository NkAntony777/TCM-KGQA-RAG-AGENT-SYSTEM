from __future__ import annotations

import asyncio
import json
from typing import Any, Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.tcm_route_execution import (
    RouteServiceCalls,
    allowed_retrieval_prefixes,
    append_degradation,
    base_route_output,
    case_qa_enabled,
    execute_route_plan,
    expand_retrieval_query,
    has_graph_evidence,
    is_success,
    maybe_run_case_qa,
    record_retrieval_result,
    run_case_qa_search,
    run_graph_search,
    run_retrieval_search,
    set_executed_routes,
)
from tools.tcm_route_planning import build_route_plan
from tools.tcm_route_planning import normalize_route_reason as _normalize_route_reason_impl
from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_graph_path_query,
    call_retrieval_case_qa,
    call_graph_syndrome_chain,
    call_retrieval_hybrid,
    service_health_snapshot,
)


class TCMRouteSearchInput(BaseModel):
    query: str = Field(..., description="Original user query")
    top_k: int = Field(default=12, ge=1, le=20, description="Result size")


def _is_success(result: dict[str, object] | None) -> bool:
    return is_success(result)


def _has_graph_evidence(result: dict[str, object] | None) -> bool:
    return has_graph_evidence(result)


def _append_degradation(output: dict[str, object], *, source_route: str, target_route: str, reason: str) -> None:
    append_degradation(output, source_route=source_route, target_route=target_route, reason=reason)


def _normalize_route_reason(*, base_reason: str, execution_route: str, strategy_override: str = "") -> str:
    return _normalize_route_reason_impl(
        base_reason=base_reason,
        execution_route=execution_route,
        strategy_override=strategy_override,
    )


def _case_qa_enabled(strategy) -> bool:
    return case_qa_enabled(strategy)


def _allowed_retrieval_prefixes(strategy) -> list[str]:
    return allowed_retrieval_prefixes(strategy)


def _build_route_plan(query: str, top_k: int):
    plan = build_route_plan(query, top_k)
    return plan.analysis, plan.decision, plan.strategy, plan.execution_route, plan.route_reason


def _base_route_output(
    *,
    analysis,
    decision,
    strategy,
    execution_route: str,
    route_reason: str,
    health: dict[str, Any],
) -> dict[str, object]:
    return base_route_output(
        analysis=analysis,
        decision=decision,
        strategy=strategy,
        execution_route=execution_route,
        route_reason=route_reason,
        health=health,
    )


def _set_executed_routes(output: dict[str, object], routes: list[str]) -> None:
    set_executed_routes(output, routes)


def _append_executed_route(output: dict[str, object], route: str) -> None:
    current = output.get("executed_routes")
    routes = list(current) if isinstance(current, list) else []
    _set_executed_routes(output, [*map(str, routes), route])


def _run_graph_search(*, query: str, strategy) -> dict[str, object]:
    return run_graph_search(query=query, strategy=strategy, calls=_route_service_calls())


def _run_retrieval_search(*, query: str, top_k: int, strategy) -> tuple[dict[str, object], str]:
    return run_retrieval_search(query=query, top_k=top_k, strategy=strategy, calls=_route_service_calls())


def _run_case_qa_search(*, query: str, top_k: int, strategy) -> dict[str, object]:
    return run_case_qa_search(query=query, top_k=top_k, strategy=strategy, calls=_route_service_calls())


def _maybe_run_case_qa(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy,
    source_route: str,
) -> dict[str, object] | None:
    return maybe_run_case_qa(
        output=output,
        query=query,
        top_k=top_k,
        strategy=strategy,
        source_route=source_route,
        calls=_route_service_calls(),
    )


def _record_retrieval_result(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy,
) -> dict[str, object]:
    return record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy, calls=_route_service_calls())


def _route_service_calls() -> RouteServiceCalls:
    return RouteServiceCalls(
        graph_entity_lookup=call_graph_entity_lookup,
        graph_path_query=call_graph_path_query,
        retrieval_case_qa=call_retrieval_case_qa,
        graph_syndrome_chain=call_graph_syndrome_chain,
        retrieval_hybrid=call_retrieval_hybrid,
    )


class TCMRouteSearchTool(BaseTool):
    name: str = "tcm_route_search"
    description: str = (
        "Preferred entry tool for TCM Q&A. It routes query to graph-service, retrieval-service, "
        "or both, then returns structured evidence and route reason."
    )
    args_schema: Type[BaseModel] = TCMRouteSearchInput

    def _run(
        self,
        query: str,
        top_k: int = 12,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        analysis, decision, strategy, execution_route, route_reason = _build_route_plan(query, top_k)
        health = service_health_snapshot()
        output = execute_route_plan(
            query=query,
            top_k=top_k,
            analysis=analysis,
            decision=decision,
            strategy=strategy,
            execution_route=execution_route,
            route_reason=route_reason,
            health=health,
            calls=_route_service_calls(),
        )
        return json.dumps(output, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        top_k: int = 12,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, None)


def _expand_retrieval_query(*, query: str, strategy) -> str:
    return expand_retrieval_query(query=query, strategy=strategy)
