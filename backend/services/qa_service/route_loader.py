from __future__ import annotations

from typing import Any

from services.qa_service.evidence import _case_reference_from_payload, _factual_evidence_from_payload
from services.qa_service.helpers import _route_from_payload, _safe_json_loads
from services.qa_service.models import RouteContext


def _load_route_payload(route_tool, *, query: str, top_k: int) -> dict[str, Any]:
    route_output = route_tool._run(query=query, top_k=top_k)
    payload = _safe_json_loads(route_output)
    if isinstance(payload, dict):
        return payload
    return {"status": "evidence_insufficient", "notes": ["route_output_unparseable"]}


def _prepare_route_context(route_tool, *, query: str, top_k: int, include_executed_routes: bool, payload: dict[str, Any] | None = None) -> RouteContext:
    resolved_payload = payload or _load_route_payload(route_tool, query=query, top_k=top_k)
    route_meta = {
        "status": resolved_payload.get("status", "evidence_insufficient" if not include_executed_routes else "ok"),
        "final_route": resolved_payload.get("final_route", resolved_payload.get("route")),
        "query": query,
    }
    if include_executed_routes:
        route_meta["executed_routes"] = resolved_payload.get("executed_routes", [])
    else:
        route_meta["count"] = len(resolved_payload.get("evidence_paths", [])) if isinstance(resolved_payload.get("evidence_paths"), list) else 0
    return RouteContext(
        payload=resolved_payload,
        route_meta=route_meta,
        route_event=_route_from_payload(resolved_payload),
        factual_evidence=_factual_evidence_from_payload(resolved_payload),
        case_references=_case_reference_from_payload(resolved_payload),
    )
