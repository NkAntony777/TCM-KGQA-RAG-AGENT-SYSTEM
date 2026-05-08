from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


RouteCall = Callable[..., dict[str, object]]


@dataclass(frozen=True)
class RouteServiceCalls:
    graph_entity_lookup: RouteCall
    graph_path_query: RouteCall
    retrieval_case_qa: RouteCall
    graph_syndrome_chain: RouteCall
    retrieval_hybrid: RouteCall


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


def append_degradation(output: dict[str, object], *, source_route: str, target_route: str, reason: str) -> None:
    degradation = output.setdefault("degradation", [])
    if isinstance(degradation, list):
        degradation.append({"from": source_route, "to": target_route, "reason": reason})


def case_qa_enabled(strategy: Any) -> bool:
    sources = {str(item).strip() for item in getattr(strategy, "sources", []) if str(item).strip()}
    return bool({"qa_case_structured_index", "qa_case_vector_db"} & sources)


def allowed_retrieval_prefixes(strategy: Any) -> list[str]:
    sources = {str(item).strip() for item in getattr(strategy, "sources", []) if str(item).strip()}
    prefixes: list[str] = []
    if "classic_docs" in sources or "qa_structured_index" in sources:
        prefixes.extend(["classic://", "sample://"])
    if "modern_herb_evidence" in sources:
        prefixes.append("herb2://")
    return list(dict.fromkeys(prefixes))


def base_route_output(
    *,
    analysis: Any,
    decision: Any,
    strategy: Any,
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


def set_executed_routes(output: dict[str, object], routes: list[str]) -> None:
    output["executed_routes"] = list(dict.fromkeys(routes))


def append_executed_route(output: dict[str, object], route: str) -> None:
    current = output.get("executed_routes")
    routes = list(current) if isinstance(current, list) else []
    set_executed_routes(output, [*map(str, routes), route])


def expand_retrieval_query(*, query: str, strategy: Any) -> str:
    alias_terms = list(getattr(strategy, "entity_aliases", []) or [])
    if not alias_terms:
        return query
    extras = [term for term in alias_terms if term and term not in query]
    if not extras:
        return query
    return " ".join([query, *extras[:6]]).strip()


def run_graph_search(*, query: str, strategy: Any, calls: RouteServiceCalls) -> dict[str, object]:
    if strategy.graph_query_kind == "path" and strategy.path_start and strategy.path_end:
        path_result = calls.graph_path_query(
            start=strategy.path_start,
            end=strategy.path_end,
            max_hops=3,
            path_limit=max(1, min(strategy.graph_final_k, 5)),
        )
        if path_result.get("code") == 0:
            return path_result

    if strategy.graph_query_kind == "entity" and strategy.graph_query_text:
        primary = calls.graph_entity_lookup(
            name=strategy.graph_query_text,
            top_k=strategy.graph_final_k,
            predicate_allowlist=strategy.predicate_allowlist,
            predicate_blocklist=strategy.predicate_blocklist,
        )
        if primary.get("code") == 0:
            return primary
        secondary = calls.graph_entity_lookup(
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

    primary = calls.graph_syndrome_chain(symptom=strategy.symptom_name or query, top_k=min(strategy.graph_final_k, 8))
    if primary.get("code") == 0:
        return primary
    secondary = calls.graph_entity_lookup(name=strategy.graph_query_text or query, top_k=strategy.graph_final_k)
    if secondary.get("code") == 0:
        return secondary
    primary["fallback_attempt"] = {
        "tool": "tcm_entity_lookup",
        "code": secondary.get("code"),
        "message": secondary.get("message"),
        "trace_id": secondary.get("trace_id"),
    }
    return primary


def run_retrieval_search(
    *,
    query: str,
    top_k: int,
    strategy: Any,
    calls: RouteServiceCalls,
) -> tuple[dict[str, object], str]:
    expanded_query = expand_retrieval_query(query=query, strategy=strategy)
    allowed_prefixes = allowed_retrieval_prefixes(strategy)
    result = calls.retrieval_hybrid(
        query=expanded_query,
        top_k=top_k,
        candidate_k=max(strategy.vector_candidate_k, top_k * 3, 9),
        enable_rerank=False,
        search_mode="files_first",
        allowed_file_path_prefixes=allowed_prefixes,
    )
    return result, expanded_query


def run_case_qa_search(*, query: str, top_k: int, strategy: Any, calls: RouteServiceCalls) -> dict[str, object]:
    return calls.retrieval_case_qa(
        query=query,
        top_k=min(top_k, max(3, strategy.graph_final_k)),
        candidate_k=max(strategy.vector_candidate_k, top_k * 4, 20),
    )


def maybe_run_case_qa(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy: Any,
    source_route: str,
    calls: RouteServiceCalls,
) -> dict[str, object] | None:
    if not case_qa_enabled(strategy):
        return None
    append_executed_route(output, "case_qa")
    result = run_case_qa_search(query=query, top_k=top_k, strategy=strategy, calls=calls)
    output["case_qa_result"] = result
    if not is_success(result):
        append_degradation(output, source_route=source_route, target_route="case_qa", reason="case_qa_branch_failed")
    return result


def record_retrieval_result(
    *,
    output: dict[str, object],
    query: str,
    top_k: int,
    strategy: Any,
    calls: RouteServiceCalls,
) -> dict[str, object]:
    result, expanded_query = run_retrieval_search(query=query, top_k=top_k, strategy=strategy, calls=calls)
    if expanded_query != query:
        output["retrieval_expanded_query"] = expanded_query
    output["retrieval_result"] = result
    return result


def attach_service_metadata(
    *,
    output: dict[str, object],
    graph_result: dict[str, object] | None,
    retrieval_result: dict[str, object] | None,
    case_qa_result: dict[str, object] | None,
) -> None:
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


def execute_route_plan(
    *,
    query: str,
    top_k: int,
    analysis: Any,
    decision: Any,
    strategy: Any,
    execution_route: str,
    route_reason: str,
    health: dict[str, Any],
    calls: RouteServiceCalls,
) -> dict[str, object]:
    output = base_route_output(
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
        set_executed_routes(output, ["graph"])
        graph_result = run_graph_search(query=query, strategy=strategy, calls=calls)
        output["graph_result"] = graph_result

        if not is_success(graph_result) or not has_graph_evidence(graph_result):
            set_executed_routes(output, ["graph", "retrieval"])
            retrieval_result = record_retrieval_result(
                output=output,
                query=query,
                top_k=top_k,
                strategy=strategy,
                calls=calls,
            )
            append_degradation(
                output,
                source_route="graph",
                target_route="retrieval",
                reason="graph_primary_empty" if is_success(graph_result) else "graph_primary_failed",
            )

            if is_success(retrieval_result):
                output["status"] = "degraded"
                output["final_route"] = "retrieval"
            else:
                output["status"] = "evidence_insufficient"
                output["final_route"] = "graph"
        else:
            output["final_route"] = "graph"

        case_qa_result = maybe_run_case_qa(
            output=output,
            query=query,
            top_k=top_k,
            strategy=strategy,
            source_route="graph",
            calls=calls,
        )
    elif execution_route == "retrieval":
        set_executed_routes(output, ["retrieval"])
        retrieval_result = record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy, calls=calls)

        if not is_success(retrieval_result):
            set_executed_routes(output, ["retrieval", "graph"])
            graph_result = run_graph_search(query=query, strategy=strategy, calls=calls)
            output["graph_result"] = graph_result
            append_degradation(output, source_route="retrieval", target_route="graph", reason="retrieval_primary_failed")

            if is_success(graph_result) and has_graph_evidence(graph_result):
                output["status"] = "degraded"
                output["final_route"] = "graph"
            else:
                output["status"] = "evidence_insufficient"
                output["final_route"] = "retrieval"
        else:
            output["final_route"] = "retrieval"

        case_qa_result = maybe_run_case_qa(
            output=output,
            query=query,
            top_k=top_k,
            strategy=strategy,
            source_route="retrieval",
            calls=calls,
        )
    else:
        set_executed_routes(output, ["graph", "retrieval"])
        graph_result = run_graph_search(query=query, strategy=strategy, calls=calls)
        retrieval_result = record_retrieval_result(output=output, query=query, top_k=top_k, strategy=strategy, calls=calls)
        output["graph_result"] = graph_result

        case_qa_result = maybe_run_case_qa(
            output=output,
            query=query,
            top_k=top_k,
            strategy=strategy,
            source_route="hybrid",
            calls=calls,
        )

        raw_graph_ok = is_success(graph_result)
        graph_ok = raw_graph_ok and has_graph_evidence(graph_result)
        retrieval_ok = is_success(retrieval_result)
        if graph_ok and retrieval_ok:
            output["final_route"] = "hybrid"
        elif graph_ok:
            output["status"] = "degraded"
            output["final_route"] = "graph"
            append_degradation(output, source_route="hybrid", target_route="graph", reason="retrieval_branch_failed")
        elif retrieval_ok:
            output["status"] = "degraded"
            output["final_route"] = "retrieval"
            append_degradation(
                output,
                source_route="hybrid",
                target_route="retrieval",
                reason="graph_branch_empty" if raw_graph_ok else "graph_branch_failed",
            )
        else:
            output["status"] = "evidence_insufficient"
            output["final_route"] = "hybrid"

    attach_service_metadata(
        output=output,
        graph_result=graph_result,
        retrieval_result=retrieval_result,
        case_qa_result=case_qa_result,
    )
    return output
