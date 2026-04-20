from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.ablations._common import load_dataset, write_outputs
from router.query_router import decide_route
from router.retrieval_strategy import derive_retrieval_strategy
from router.tcm_intent_classifier import analyze_tcm_query
from services.qa_service.evidence import _factual_evidence_from_payload
from tools.tcm_route_tool import (
    _allowed_retrieval_prefixes,
    _expand_retrieval_query,
    _has_graph_evidence,
    _is_success,
)
from tools.tcm_service_client import (
    call_graph_entity_lookup,
    call_graph_path_query,
    call_graph_syndrome_chain,
    call_retrieval_hybrid,
    service_health_snapshot,
)


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "ablations" / "graph_filesfirst_synergy_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent.parent / "docs" / "Graph_FilesFirst_Synergy_Latest.md"


def _graph_search(strategy, query: str) -> dict[str, object]:
    if strategy.graph_query_kind == "path" and strategy.path_start and strategy.path_end:
        result = call_graph_path_query(
            start=strategy.path_start,
            end=strategy.path_end,
            max_hops=3,
            path_limit=max(1, min(strategy.graph_final_k, 5)),
        )
        if result.get("code") == 0:
            return result
    if strategy.graph_query_kind == "entity" and strategy.graph_query_text:
        primary = call_graph_entity_lookup(
            name=strategy.graph_query_text,
            top_k=strategy.graph_final_k,
            predicate_allowlist=strategy.predicate_allowlist,
            predicate_blocklist=strategy.predicate_blocklist,
        )
        if primary.get("code") == 0:
            return primary
        secondary = call_graph_entity_lookup(name=strategy.graph_query_text, top_k=strategy.graph_final_k)
        return secondary if secondary.get("code") == 0 else primary
    primary = call_graph_syndrome_chain(symptom=strategy.symptom_name or query, top_k=min(strategy.graph_final_k, 8))
    if primary.get("code") == 0:
        return primary
    return call_graph_entity_lookup(name=strategy.graph_query_text or query, top_k=strategy.graph_final_k)


def _retrieval_search(strategy, query: str, top_k: int) -> dict[str, object]:
    expanded_query = _expand_retrieval_query(query=query, strategy=strategy)
    return call_retrieval_hybrid(
        query=expanded_query,
        top_k=top_k,
        candidate_k=max(strategy.vector_candidate_k, top_k * 3, 9),
        enable_rerank=False,
        search_mode="files_first",
        allowed_file_path_prefixes=_allowed_retrieval_prefixes(strategy),
    )


def _forced_payload(*, query: str, top_k: int, forced_route: str) -> dict[str, Any]:
    analysis = analyze_tcm_query(query)
    decision = decide_route(query, analysis=analysis)
    strategy = derive_retrieval_strategy(query, requested_top_k=top_k, route_hint=decision.route, analysis=analysis)
    output: dict[str, Any] = {
        "route": forced_route,
        "route_reason": f"forced_{forced_route}; classifier={decision.route}",
        "classifier_route": decision.route,
        "execution_mode": service_health_snapshot().get("execution_mode"),
        "query_analysis": analysis.to_dict(),
        "retrieval_strategy": strategy.to_dict(),
        "evidence_paths": strategy.evidence_paths,
        "service_health": service_health_snapshot(),
        "status": "ok",
        "degradation": [],
        "executed_routes": [],
    }
    graph_result = None
    retrieval_result = None
    if forced_route == "graph":
        output["executed_routes"] = ["graph"]
        graph_result = _graph_search(strategy, query)
        output["graph_result"] = graph_result
        output["final_route"] = "graph"
        if not (_is_success(graph_result) and _has_graph_evidence(graph_result)):
            output["status"] = "evidence_insufficient"
    elif forced_route == "retrieval":
        output["executed_routes"] = ["retrieval"]
        retrieval_result = _retrieval_search(strategy, query, top_k)
        output["retrieval_result"] = retrieval_result
        output["final_route"] = "retrieval"
        if not _is_success(retrieval_result):
            output["status"] = "evidence_insufficient"
    else:
        output["executed_routes"] = ["graph", "retrieval"]
        graph_result = _graph_search(strategy, query)
        retrieval_result = _retrieval_search(strategy, query, top_k)
        output["graph_result"] = graph_result
        output["retrieval_result"] = retrieval_result
        graph_ok = _is_success(graph_result) and _has_graph_evidence(graph_result)
        retrieval_ok = _is_success(retrieval_result)
        if graph_ok and retrieval_ok:
            output["final_route"] = "hybrid"
        elif graph_ok:
            output["status"] = "degraded"
            output["final_route"] = "graph"
        elif retrieval_ok:
            output["status"] = "degraded"
            output["final_route"] = "retrieval"
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
    return output


def _evaluate(case: dict[str, Any], payload: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    factual_evidence = _factual_evidence_from_payload(payload)
    predicates = {
        str(item.get("predicate", "")).strip()
        for item in factual_evidence
        if isinstance(item, dict) and str(item.get("predicate", "")).strip()
    }
    source_books: set[str] = set()
    for item in factual_evidence:
        if not isinstance(item, dict):
            continue
        source_book = str(item.get("source_book", "")).strip()
        if source_book:
            source_books.add(source_book)
        for book in item.get("source_books", []) or []:
            text = str(book).strip()
            if text:
                source_books.add(text)

    expected_routes = []
    if isinstance(case.get("expected_routes_any"), list):
        expected_routes.extend(str(item).strip() for item in case.get("expected_routes_any", []) if str(item).strip())
    expected_route = str(case.get("expected_route", "")).strip()
    if expected_route:
        expected_routes.append(expected_route)
    expected_routes = list(dict.fromkeys(expected_routes))

    expected_predicates = [str(item).strip() for item in case.get("evidence_predicates_any", []) if str(item).strip()] if isinstance(case.get("evidence_predicates_any"), list) else []
    expected_source_books = [str(item).strip() for item in case.get("evidence_source_books_any", []) if str(item).strip()] if isinstance(case.get("evidence_source_books_any"), list) else []
    expected_executed = [str(item).strip() for item in case.get("executed_routes_contains_any", []) if str(item).strip()] if isinstance(case.get("executed_routes_contains_any"), list) else []

    route_hit = bool(expected_routes) and str(payload.get("final_route", "")).strip() in expected_routes
    predicate_hit = bool(expected_predicates) and bool(predicates.intersection(expected_predicates))
    source_book_hit = bool(expected_source_books) and bool(source_books.intersection(expected_source_books))
    executed = {str(item).strip() for item in payload.get("executed_routes", []) if str(item).strip()} if isinstance(payload.get("executed_routes"), list) else set()
    executed_hit = bool(expected_executed) and bool(executed.intersection(expected_executed))

    checks: list[bool] = []
    if expected_routes:
        checks.append(route_hit)
    if expected_predicates:
        checks.append(predicate_hit)
    if expected_source_books:
        checks.append(source_book_hit)
    if expected_executed:
        checks.append(executed_hit)
    if not checks:
        checks.append(bool(factual_evidence))

    return {
        "latency_ms": round(latency_ms, 1),
        "final_route": payload.get("final_route"),
        "status": payload.get("status"),
        "executed_routes": sorted(executed),
        "evidence_count": len(factual_evidence),
        "route_hit": route_hit if expected_routes else None,
        "predicate_hit": predicate_hit if expected_predicates else None,
        "source_book_hit": source_book_hit if expected_source_books else None,
        "executed_route_hit": executed_hit if expected_executed else None,
        "score": round(sum(1.0 for item in checks if item) / max(len(checks), 1), 4),
    }


def _run_condition(*, label: str, forced_route: str, dataset: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(dataset, start=1):
        query = str(case.get("query", "")).strip()
        started = time.perf_counter()
        payload = _forced_payload(query=query, top_k=top_k, forced_route=forced_route)
        latency_ms = (time.perf_counter() - started) * 1000.0
        metrics = _evaluate(case, payload, latency_ms)
        rows.append(
            {
                "case": case,
                "payload": {
                    "status": payload.get("status"),
                    "final_route": payload.get("final_route"),
                    "executed_routes": payload.get("executed_routes", []),
                    "service_backends": payload.get("service_backends", {}),
                    "service_trace_ids": payload.get("service_trace_ids", {}),
                },
                "metrics": metrics,
            }
        )
        print(
            f"[graph-synergy] {label} {idx:02d}/{len(dataset)} {case.get('id')} "
            f"route={metrics['final_route']} score={metrics['score']:.2f} latency={metrics['latency_ms']:.1f}ms",
            flush=True,
        )
    hybrid_focus_rows = [
        item
        for item in rows
        if (
            ("hybrid" in [str(x).strip() for x in item["case"].get("expected_routes_any", []) if str(x).strip()])
            or str(item["case"].get("expected_route", "")).strip() == "hybrid"
            or bool(item["case"].get("evidence_source_books_any"))
        )
    ]

    def _rate(rows_source: list[dict[str, Any]], key: str) -> float | None:
        available = [item for item in rows_source if item["metrics"].get(key) is not None]
        if not available:
            return None
        return round(sum(1 for item in available if item["metrics"].get(key) is True) / len(available), 4)

    def _avg_score(rows_source: list[dict[str, Any]]) -> float | None:
        if not rows_source:
            return None
        return round(statistics.mean(float(item["metrics"]["score"]) for item in rows_source), 4)

    def _avg_latency(rows_source: list[dict[str, Any]]) -> float | None:
        if not rows_source:
            return None
        return round(statistics.mean(float(item["metrics"]["latency_ms"]) for item in rows_source), 1)

    return {
        "label": label,
        "forced_route": forced_route,
        "cases": rows,
        "all_cases": {
            "count": len(rows),
            "avg_latency_ms": _avg_latency(rows),
            "avg_score": _avg_score(rows),
            "route_hit_rate": _rate(rows, "route_hit"),
            "predicate_hit_rate": _rate(rows, "predicate_hit"),
            "source_book_hit_rate": _rate(rows, "source_book_hit"),
        },
        "hybrid_focus_cases": {
            "count": len(hybrid_focus_rows),
            "avg_latency_ms": _avg_latency(hybrid_focus_rows),
            "avg_score": _avg_score(hybrid_focus_rows),
            "route_hit_rate": _rate(hybrid_focus_rows, "route_hit"),
            "predicate_hit_rate": _rate(hybrid_focus_rows, "predicate_hit"),
            "source_book_hit_rate": _rate(hybrid_focus_rows, "source_book_hit"),
        },
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Graph + Files-First Synergy Experiment",
        "",
        "## Overview",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| dataset | {payload['settings']['dataset']} |",
        f"| top_k | {payload['settings']['top_k']} |",
        "",
        "## Aggregate",
        "",
        "| Condition | scope | count | avg_latency_ms | avg_score | route_hit_rate | predicate_hit_rate | source_book_hit_rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition in payload["conditions"]:
        for scope in ("all_cases", "hybrid_focus_cases"):
            metrics = condition[scope]
            lines.append(
                f"| {condition['label']} | {scope} | {metrics['count']} | {metrics['avg_latency_ms']} | {metrics['avg_score']} | "
                f"{metrics['route_hit_rate']} | {metrics['predicate_hit_rate']} | {metrics['source_book_hit_rate']} |"
            )
    lines.extend(
        [
            "",
            "## Per Case",
            "",
            "| case_id | category | graph_only | files_first_only | graph_plus_files_first |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    case_ids = [str(item["case"].get("id")) for item in payload["conditions"][0]["cases"]]
    by_label = {
        condition["label"]: {str(item["case"].get("id")): item for item in condition["cases"]}
        for condition in payload["conditions"]
    }
    for case_id in case_ids:
        graph_only = by_label["graph_only"][case_id]
        files_first = by_label["files_first_only"][case_id]
        hybrid = by_label["graph_plus_files_first"][case_id]
        lines.append(
            f"| {case_id} | {graph_only['case'].get('category', '-')} | "
            f"{graph_only['metrics']['score']} | {files_first['metrics']['score']} | {hybrid['metrics']['score']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate graph-only, files-first-only, and graph+files-first synergy.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    conditions = [
        _run_condition(label="graph_only", forced_route="graph", dataset=dataset, top_k=max(1, int(args.top_k))),
        _run_condition(label="files_first_only", forced_route="retrieval", dataset=dataset, top_k=max(1, int(args.top_k))),
        _run_condition(label="graph_plus_files_first", forced_route="hybrid", dataset=dataset, top_k=max(1, int(args.top_k))),
    ]
    payload = {
        "settings": {
            "dataset": str(args.dataset),
            "top_k": max(1, int(args.top_k)),
        },
        "conditions": conditions,
    }
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=_render_markdown(payload))
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "summary": {
                    item["label"]: {
                        "all_cases": item["all_cases"],
                        "hybrid_focus_cases": item["hybrid_focus_cases"],
                    }
                    for item in conditions
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
