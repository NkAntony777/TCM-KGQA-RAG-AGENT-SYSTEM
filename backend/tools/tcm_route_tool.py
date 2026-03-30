from __future__ import annotations

import asyncio
import json
from typing import Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from router.query_router import decide_route
from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_graph_path_query,
    call_graph_syndrome_chain,
    call_retrieval_hybrid,
    service_health_snapshot,
)


class TCMRouteSearchInput(BaseModel):
    query: str = Field(..., description="Original user query")
    top_k: int = Field(default=5, ge=1, le=20, description="Result size")


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
        top_k: int = 5,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        decision = decide_route(query)
        health = service_health_snapshot()
        output: dict[str, object] = {
            "route": decision.route,
            "route_reason": decision.reason,
            "service_health": health,
            "status": "ok",
            "degradation": [],
            "executed_routes": [],
        }

        graph_result = None
        retrieval_result = None

        def extract_path_targets(text: str) -> tuple[str, str] | None:
            normalized = text.strip()
            if not normalized:
                return None
            if "到" not in normalized:
                return None
            if not any(token in normalized for token in ("路径", "关系", "链路", "怎么到", "如何到")):
                return None

            left, right = normalized.split("到", 1)
            start = left.replace("从", "").replace("请问", "").replace("请解释", "").strip(" ，。？?：:")
            end = right
            for marker in ("的路径", "路径", "关系", "链路", "怎么到", "如何到", "是什么", "有哪些", "吗"):
                end = end.split(marker, 1)[0]
            end = end.strip(" ，。？?：:")
            if not start or not end:
                return None
            return start, end

        def graph_search() -> dict[str, object]:
            path_targets = extract_path_targets(query)
            if path_targets is not None:
                start, end = path_targets
                path_result = call_graph_path_query(
                    start=start,
                    end=end,
                    max_hops=3,
                    path_limit=max(1, min(top_k, 5)),
                )
                if path_result.get("code") == 0:
                    return path_result

            primary = call_graph_syndrome_chain(symptom=query, top_k=top_k)
            if primary.get("code") == 0:
                return primary
            secondary = call_graph_entity_lookup(name=query, top_k=top_k)
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
                candidate_k=max(top_k * 3, 9),
                enable_rerank=False,
            )

        def is_success(result: dict[str, object] | None) -> bool:
            return isinstance(result, dict) and result.get("code") == 0

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

        if decision.route == "graph":
            output["executed_routes"] = ["graph"]
            graph_result = graph_search()
            output["graph_result"] = graph_result

            if not is_success(graph_result):
                output["executed_routes"] = ["graph", "retrieval"]
                retrieval_result = retrieval_search()
                output["retrieval_result"] = retrieval_result
                add_degradation("graph", "retrieval", "graph_primary_failed")

                if is_success(retrieval_result):
                    output["status"] = "degraded"
                    output["final_route"] = "retrieval"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "graph"
            else:
                output["final_route"] = "graph"
        elif decision.route == "retrieval":
            output["executed_routes"] = ["retrieval"]
            retrieval_result = retrieval_search()
            output["retrieval_result"] = retrieval_result

            if not is_success(retrieval_result):
                output["executed_routes"] = ["retrieval", "graph"]
                graph_result = graph_search()
                output["graph_result"] = graph_result
                add_degradation("retrieval", "graph", "retrieval_primary_failed")

                if is_success(graph_result):
                    output["status"] = "degraded"
                    output["final_route"] = "graph"
                else:
                    output["status"] = "evidence_insufficient"
                    output["final_route"] = "retrieval"
            else:
                output["final_route"] = "retrieval"
        else:
            output["executed_routes"] = ["graph", "retrieval"]
            graph_result = graph_search()
            retrieval_result = retrieval_search()
            output["graph_result"] = graph_result
            output["retrieval_result"] = retrieval_result

            graph_ok = is_success(graph_result)
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
                add_degradation("hybrid", "retrieval", "graph_branch_failed")
            else:
                output["status"] = "evidence_insufficient"
                output["final_route"] = "hybrid"

        output["service_trace_ids"] = {
            "graph": graph_result.get("trace_id") if isinstance(graph_result, dict) else None,
            "retrieval": retrieval_result.get("trace_id") if isinstance(retrieval_result, dict) else None,
        }
        output["service_backends"] = {
            "graph": graph_result.get("backend") if isinstance(graph_result, dict) else None,
            "retrieval": retrieval_result.get("backend") if isinstance(retrieval_result, dict) else None,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)[:10000]

    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, None)
