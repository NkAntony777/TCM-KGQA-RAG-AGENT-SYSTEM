from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import httpx

from services.common.mock_data import hybrid_search, lookup_entity, query_path, rewrite_query, syndrome_chain


GRAPH_SERVICE_BASE_URL = os.getenv("GRAPH_SERVICE_BASE_URL", "http://127.0.0.1:8101")
RETRIEVAL_SERVICE_BASE_URL = os.getenv("RETRIEVAL_SERVICE_BASE_URL", "http://127.0.0.1:8102")


def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    trace_id = str(uuid4())
    timeout = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            url,
            json=payload,
            headers={"X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("invalid_service_response")
        return data


def _health(url: str) -> bool:
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
    return True


def call_graph_entity_lookup(name: str, top_k: int = 20) -> dict[str, Any]:
    try:
        payload = _post(
            f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/entity/lookup",
            {"name": name, "top_k": top_k},
        )
        return {"backend": "graph-service", **payload}
    except Exception as exc:
        mock = lookup_entity(name, top_k=top_k)
        return {
            "backend": "local-fallback",
            "code": 0 if mock else 20001,
            "message": "ok" if mock else "KG_ENTITY_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
            "warning": f"graph-service unavailable: {exc}",
        }


def call_graph_path_query(start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
    try:
        payload = _post(
            f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/path/query",
            {
                "start": start,
                "end": end,
                "max_hops": max_hops,
                "path_limit": path_limit,
            },
        )
        return {"backend": "graph-service", **payload}
    except Exception as exc:
        mock = query_path(start, end, max_hops=max_hops, path_limit=path_limit)
        return {
            "backend": "local-fallback",
            "code": 0 if mock.get("paths") else 20002,
            "message": "ok" if mock.get("paths") else "KG_PATH_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
            "warning": f"graph-service unavailable: {exc}",
        }


def call_graph_syndrome_chain(symptom: str, top_k: int = 5) -> dict[str, Any]:
    try:
        payload = _post(
            f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/syndrome/chain",
            {"symptom": symptom, "top_k": top_k},
        )
        return {"backend": "graph-service", **payload}
    except Exception as exc:
        mock = syndrome_chain(symptom, top_k=top_k)
        return {
            "backend": "local-fallback",
            "code": 0 if mock.get("syndromes") else 20001,
            "message": "ok" if mock.get("syndromes") else "KG_ENTITY_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
            "warning": f"graph-service unavailable: {exc}",
        }


def call_retrieval_hybrid(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    enable_rerank: bool = True,
) -> dict[str, Any]:
    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/search/hybrid",
            {
                "query": query,
                "top_k": top_k,
                "candidate_k": candidate_k,
                "enable_rerank": enable_rerank,
            },
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        mock = hybrid_search(
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
        )
        return {
            "backend": "local-fallback",
            "code": 0 if mock.get("chunks") else 30001,
            "message": "ok" if mock.get("chunks") else "RETRIEVE_EMPTY",
            "data": mock,
            "trace_id": str(uuid4()),
            "warning": f"retrieval-service unavailable: {exc}",
        }


def call_retrieval_rewrite(query: str, strategy: str = "complex") -> dict[str, Any]:
    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/search/rewrite",
            {"query": query, "strategy": strategy},
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        mock = rewrite_query(query, strategy=strategy)
        return {
            "backend": "local-fallback",
            "code": 0,
            "message": "ok",
            "data": mock,
            "trace_id": str(uuid4()),
            "warning": f"retrieval-service unavailable: {exc}",
        }


def service_health_snapshot() -> dict[str, Any]:
    graph_ok = False
    retrieval_ok = False
    try:
        graph_ok = _health(f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/health")
    except Exception:
        graph_ok = False
    try:
        retrieval_ok = _health(f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/health")
    except Exception:
        retrieval_ok = False
    return {
        "graph_service_up": graph_ok,
        "retrieval_service_up": retrieval_ok,
        "graph_service_base_url": GRAPH_SERVICE_BASE_URL,
        "retrieval_service_base_url": RETRIEVAL_SERVICE_BASE_URL,
    }
