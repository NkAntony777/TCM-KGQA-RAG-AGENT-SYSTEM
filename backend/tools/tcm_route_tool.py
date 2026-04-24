from __future__ import annotations

import asyncio
import json
from typing import Any, Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from router.query_router import decide_route
from router.retrieval_strategy import derive_retrieval_strategy
from router.tcm_intent_classifier import analyze_tcm_query
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
    return isinstance(result, dict) and result.get("code") == 0


def _has_graph_evidence(result: dict[str, object] | None) -> bool:
    if not isinstance(result, dict):
        return False
    data = result.get("data")
    if not isinstance(data, dict):
        return False
    for key in ("relations", "syndromes", "paths"):
        items = data.get(key)
        if isinstance(items, list) and items:
            return True
    return False


def _append_degradation(output: dict[str, object], *, source_route: str, target_route: str, reason: str) -> None:
    degradation = output.setdefault("degradation", [])
    if isinstance(degradation, list):
        degradation.append({"from": source_route, "to": target_route, "reason": reason})


def _normalize_route_reason(*, base_reason: str, execution_route: str, strategy_override: str = "") -> str:
    parts = [str(base_reason or "").strip()]
    if strategy_override:
        parts.append(strategy_override)
    parts = [item for item in parts if item]
    if not parts:
        return execution_route
    return "; ".join(dict.fromkeys(parts))


def _case_qa_enabled(strategy) -> bool:
    sources = {str(item).strip() for item in getattr(strategy, "sources", []) if str(item).strip()}
    return bool({"qa_case_structured_index", "qa_case_vector_db"} & sources)


def _allowed_retrieval_prefixes(strategy) -> list[str]:
    sources = {str(item).strip() for item in getattr(strategy, "sources", []) if str(item).strip()}
    prefixes: list[str] = []
    if "classic_docs" in sources or "qa_structured_index" in sources:
        prefixes.extend(["classic://", "sample://"])
    if "modern_herb_evidence" in sources:
        prefixes.append("herb2://")
    return list(dict.fromkeys(prefixes))


def _build_route_plan(query: str, top_k: int):
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

    route_reason = _normalize_route_reason(
        base_reason=decision.reason,
        execution_route=execution_route,
        strategy_override=route_override_reason,
    )
    return analysis, decision, strategy, execution_route, route_reason


def _base_route_output(
    *,
    analysis,
    decision,
    strategy,
    execution_route: str,
    route_reason: str,
    health: dict[str, Any],
) -> dict[str, object]:
    return {
        "route": execution_route,
        "route_reason": route_reason,
        "classifier_route": decision.route,
        "execution_mode": health.get("execution_mode"),
        "query_analysis": analysis.to_dict(),
        "retrieval_strategy": strategy.to_dict(),
        "evidence_paths": strategy.evidence_paths,
        "service_health": health,
        "status": "ok",
        "degradation": [],
        "executed_routes": [],
    }


def _set_executed_routes(output: dict[str, object], routes: list[str]) -> None:
    output["executed_routes"] = list(dict.fromkeys(routes))


def _append_executed_route(output: dict[str, object], route: str) -> None:
    current = output.get("executed_routes")
    routes = list(current) if isinstance(current, list) else []
    _set_executed_routes(output, [*map(str, routes), route])


def _run_graph_search(*, query: str, strategy) -> dict[str, object]:
    if strategy.graph_query_kind == "path" and strategy.path_start and strategy.path_end:
        path_result = call_graph_path_query(
            start=strategy.path_start,
            end=strategy.path_end,
            max_hops=3,
            path_limit=max(1, min(strategy.graph_final_k, 5)),
        )
        if path_result.get("code") == 0:
            return path_result

    if strategy.graph_query_kind == "entity" and strategy.graph_query_text:
        primary = call_graph_entity_lookup(
            name=strategy.graph_query_text,
            top_k=strategy.graph_final_k,
            predicate_allowlist=strategy.predicate_allowlist,
            predicate_blocklist=strategy.predicate_blocklist,
        )
        if primary.get("code") == 0:
            return primary
        secondary = call_graph_entity_lookup(
            name=strategy.graph_query_text,
            top_k=strategy.graph_final_k,
        )
        primary["fallback_attempt"] = {
            "tool": "tcm_entity_lookup",
            "mode": "unfiltered_retry",
            "code": secondary.get("code"),
            "message": secondary.get("message"),
            "trace_id": secondary.get("trace_id"),
        }
        return secondary if secondary.get("code") == 0 else primary

    primary = call_graph_syndrome_chain(symptom=strategy.symptom_name or query, top_k=min(strategy.graph_final_k, 8))
    if primary.get("code") == 0:
        return primary
    secondary = call_graph_entity_lookup(name=strategy.graph_query_text or query, top_k=strategy.graph_final_k)
    if secondary.get("code") == 0:
        return secondary
    primary["fallback_attempt"] = {
        "tool": "tcm_entity_lookup",
        "code": secondary.get("code"),
        "message": secondary.get("message"),
        "trace_id": secondary.get("trace_id"),
    }
    return primary


def _run_retrieval_search(*, query: str, top_k: int, strategy) -> tuple[dict[str, object], str]:
    expanded_query = _expand_retrieval_query(query=query, strategy=strategy)
    allowed_prefixes = _allowed_retrieval_prefixes(strategy)
    result = call_retrieval_hybrid(
        query=expanded_query,
        top_k=top_k,
        candidate_k=max(strategy.vector_candidate_k, top_k * 3, 9),
        enable_rerank=False,
        search_mode="files_first",
        allowed_file_path_prefixes=allowed_prefixes,
    )
    return result, expanded_query


def _run_case_qa_search(*, query: str, top_k: int, strategy) -> dict[str, object]:
    return call_retrieval_case_qa(
        query=query,
        top_k=min(top_k, max(3, strategy.graph_final_k)),
        candidate_k=max(strategy.vector_candidate_k, top_k * 4, 20),
    )


def _maybe_run_case_qa(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy,
    source_route: str,
) -> dict[str, object] | None:
    if not _case_qa_enabled(strategy):
        return None
    _append_executed_route(output, "case_qa")
    result = _run_case_qa_search(query=query, top_k=top_k, strategy=strategy)
    output["case_qa_result"] = result
    if not _is_success(result):
        _append_degradation(output, source_route=source_route, target_route="case_qa", reason="case_qa_branch_failed")
    return result


def _record_retrieval_result(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy,
) -> dict[str, object]:
    result, expanded_query = _run_retrieval_search(query=query, top_k=top_k, strategy=strategy)
    if expanded_query != query:
        output["retrieval_expanded_query"] = expanded_query
    output["retrieval_result"] = result
    return result


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
        output = _base_route_output(
            analysis=analysis,
            decision=decision,
            strategy=strategy,
            execution_route=execution_route,
            route_reason=route_reason,
            health=health,
        )

        graph_result = None
        retrieval_result = None
        case_qa_result = None

        if execution_route == "graph":
            _set_executed_routes(output, ["graph"])
            graph_result = _run_graph_search(query=query, strategy=strategy)
            output["graph_result"] = graph_result

            if not _is_success(graph_result) or not _has_graph_evidence(graph_result):
                _set_executed_routes(output, ["graph", "retrieval"])
                retrieval_result = _record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy)
                _append_degradation(
                    output,
                    source_route="graph",
                    target_route="retrieval",
                    reason="graph_primary_empty" if _is_success(graph_result) else "graph_primary_failed",
                )

                if _is_success(retrieval_result):
                    output["status"] = "degraded"
                    output["final_route"] = "retrieval"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "graph"
            else:
                output["final_route"] = "graph"

            case_qa_result = _maybe_run_case_qa(output=output, query=query, top_k=top_k, strategy=strategy, source_route="graph")
        elif execution_route == "retrieval":
            _set_executed_routes(output, ["retrieval"])
            retrieval_result = _record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy)

            if not _is_success(retrieval_result):
                _set_executed_routes(output, ["retrieval", "graph"])
                graph_result = _run_graph_search(query=query, strategy=strategy)
                output["graph_result"] = graph_result
                _append_degradation(output, source_route="retrieval", target_route="graph", reason="retrieval_primary_failed")

                if _is_success(graph_result) and _has_graph_evidence(graph_result):
                    output["status"] = "degraded"
                    output["final_route"] = "graph"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "retrieval"
            else:
                output["final_route"] = "retrieval"

            case_qa_result = _maybe_run_case_qa(
                output=output,
                query=query,
                top_k=top_k,
                strategy=strategy,
                source_route="retrieval",
            )
        else:
            _set_executed_routes(output, ["graph", "retrieval"])
            graph_result = _run_graph_search(query=query, strategy=strategy)
            retrieval_result = _record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy)
            output["graph_result"] = graph_result

            case_qa_result = _maybe_run_case_qa(output=output, query=query, top_k=top_k, strategy=strategy, source_route="hybrid")

            raw_graph_ok = _is_success(graph_result)
            graph_ok = raw_graph_ok and _has_graph_evidence(graph_result)
            retrieval_ok = _is_success(retrieval_result)
            if graph_ok and retrieval_ok:
                output["final_route"] = "hybrid"
            elif graph_ok:
                output["status"] = "degraded"
                output["final_route"] = "graph"
                _append_degradation(output, source_route="hybrid", target_route="graph", reason="retrieval_branch_failed")
            elif retrieval_ok:
                output["status"] = "degraded"
                output["final_route"] = "retrieval"
                _append_degradation(
                    output,
                    source_route="hybrid",
                    target_route="retrieval",
                    reason="graph_branch_empty" if raw_graph_ok else "graph_branch_failed",
                )
            else:
                output["status"] = "evidence_insufficient"
                output["final_route"] = "hybrid"

        output["service_trace_ids"] = {
            "graph": graph_result.get("trace_id") if isinstance(graph_result, dict) else None,
            "retrieval": retrieval_result.get("trace_id") if isinstance(retrieval_result, dict) else None,
            "case_qa": case_qa_result.get("trace_id") if isinstance(case_qa_result, dict) else None,
        }
        output["service_backends"] = {
            "graph": graph_result.get("backend") if isinstance(graph_result, dict) else None,
            "retrieval": retrieval_result.get("backend") if isinstance(retrieval_result, dict) else None,
            "case_qa": case_qa_result.get("backend") if isinstance(case_qa_result, dict) else None,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        top_k: int = 12,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, None)


def _expand_retrieval_query(*, query: str, strategy) -> str:
    alias_terms = list(getattr(strategy, "entity_aliases", []) or [])
    if not alias_terms:
        return query
    extras = [term for term in alias_terms if term and term not in query]
    if not extras:
        return query
    return " ".join([query, *extras[:6]]).strip()
