from __future__ import annotations

import asyncio
import json
from typing import Type

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
        analysis = analyze_tcm_query(query)
        decision = decide_route(query, analysis=analysis)
        strategy = derive_retrieval_strategy(query, requested_top_k=top_k, route_hint=decision.route, analysis=analysis)
        execution_route = decision.route
        route_reason = decision.reason
        if strategy.intent == "formula_origin" and strategy.entity_name and decision.route == "retrieval":
            execution_route = "hybrid"
            route_reason = f"{decision.reason}; origin_entity_forced_hybrid"
        health = service_health_snapshot()
        output: dict[str, object] = {
            "route": execution_route,
            "route_reason": route_reason,
            "classifier_route": decision.route,
            "query_analysis": analysis.to_dict(),
            "retrieval_strategy": strategy.to_dict(),
            "evidence_paths": strategy.evidence_paths,
            "service_health": health,
            "status": "ok",
            "degradation": [],
            "executed_routes": [],
        }

        graph_result = None
        retrieval_result = None
        case_qa_result = None

        def graph_search() -> dict[str, object]:
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

        def retrieval_search() -> dict[str, object]:
            return call_retrieval_hybrid(
                query=query,
                top_k=top_k,
                candidate_k=max(strategy.vector_candidate_k, top_k * 3, 9),
                enable_rerank=False,
            )

        def case_qa_search() -> dict[str, object]:
            return call_retrieval_case_qa(
                query=query,
                top_k=min(top_k, max(3, strategy.graph_final_k)),
                candidate_k=max(strategy.vector_candidate_k, top_k * 4, 20),
            )

        def is_success(result: dict[str, object] | None) -> bool:
            return isinstance(result, dict) and result.get("code") == 0

        def has_graph_evidence(result: dict[str, object] | None) -> bool:
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

        def add_degradation(source_route: str, target_route: str, reason: str) -> None:
            degradation = output.setdefault("degradation", [])
            if isinstance(degradation, list):
                degradation.append(
                    {
                        "from": source_route,
                        "to": target_route,
                        "reason": reason,
                    }
                )

        if execution_route == "graph":
            output["executed_routes"] = ["graph"]
            graph_result = graph_search()
            output["graph_result"] = graph_result

            if not is_success(graph_result) or not has_graph_evidence(graph_result):
                output["executed_routes"] = ["graph", "retrieval"]
                retrieval_result = retrieval_search()
                output["retrieval_result"] = retrieval_result
                add_degradation("graph", "retrieval", "graph_primary_empty" if is_success(graph_result) else "graph_primary_failed")

                if is_success(retrieval_result):
                    output["status"] = "degraded"
                    output["final_route"] = "retrieval"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "graph"
            else:
                output["final_route"] = "graph"

            if "qa_case_vector_db" in strategy.sources:
                output["executed_routes"] = list(dict.fromkeys([*output["executed_routes"], "case_qa"]))
                case_qa_result = case_qa_search()
                output["case_qa_result"] = case_qa_result
                if not is_success(case_qa_result):
                    add_degradation("graph", "case_qa", "case_qa_branch_failed")
        elif execution_route == "retrieval":
            output["executed_routes"] = ["retrieval"]
            retrieval_result = retrieval_search()
            output["retrieval_result"] = retrieval_result

            if not is_success(retrieval_result):
                output["executed_routes"] = ["retrieval", "graph"]
                graph_result = graph_search()
                output["graph_result"] = graph_result
                add_degradation("retrieval", "graph", "retrieval_primary_failed")

                if is_success(graph_result) and has_graph_evidence(graph_result):
                    output["status"] = "degraded"
                    output["final_route"] = "graph"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "retrieval"
            else:
                output["final_route"] = "retrieval"

            if "qa_case_vector_db" in strategy.sources:
                output["executed_routes"] = list(dict.fromkeys([*output["executed_routes"], "case_qa"]))
                case_qa_result = case_qa_search()
                output["case_qa_result"] = case_qa_result
                if not is_success(case_qa_result):
                    add_degradation("retrieval", "case_qa", "case_qa_branch_failed")
        else:
            output["executed_routes"] = ["graph", "retrieval"]
            graph_result = graph_search()
            retrieval_result = retrieval_search()
            output["graph_result"] = graph_result
            output["retrieval_result"] = retrieval_result

            if "qa_case_vector_db" in strategy.sources:
                output["executed_routes"] = ["graph", "retrieval", "case_qa"]
                case_qa_result = case_qa_search()
                output["case_qa_result"] = case_qa_result

            raw_graph_ok = is_success(graph_result)
            graph_ok = raw_graph_ok and has_graph_evidence(graph_result)
            retrieval_ok = is_success(retrieval_result)
            if graph_ok and retrieval_ok:
                output["final_route"] = "hybrid"
            elif graph_ok:
                output["status"] = "degraded"
                output["final_route"] = "graph"
                add_degradation("hybrid", "graph", "retrieval_branch_failed")
            elif retrieval_ok:
                output["status"] = "degraded"
                output["final_route"] = "retrieval"
                add_degradation("hybrid", "retrieval", "graph_branch_empty" if raw_graph_ok else "graph_branch_failed")
            else:
                output["status"] = "evidence_insufficient"
                output["final_route"] = "hybrid"

            if "qa_case_vector_db" in strategy.sources and not is_success(case_qa_result):
                add_degradation("hybrid", "case_qa", "case_qa_branch_failed")

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
