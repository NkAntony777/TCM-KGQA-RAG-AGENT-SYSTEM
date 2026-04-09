from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import httpx

from services.graph_service.engine import get_graph_engine
from services.retrieval_service.engine import get_retrieval_engine


GRAPH_SERVICE_BASE_URL = os.getenv("GRAPH_SERVICE_BASE_URL", "http://127.0.0.1:8101")
RETRIEVAL_SERVICE_BASE_URL = os.getenv("RETRIEVAL_SERVICE_BASE_URL", "http://127.0.0.1:8102")


def execution_mode() -> str:
    mode = os.getenv("TCM_SERVICE_MODE", "local").strip().lower()
    return mode if mode in {"local", "sidecar"} else "local"


def sidecar_fallback_enabled() -> bool:
    return os.getenv("TCM_SERVICE_SIDECAR_FALLBACK", "false").strip().lower() == "true"


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


def _service_unavailable_response(*, backend: str, code: int, message: str, exc: Exception) -> dict[str, Any]:
    return {
        "backend": backend,
        "code": code,
        "message": message,
        "data": {},
        "trace_id": str(uuid4()),
        "warning": str(exc),
    }


def _local_hybrid_search(
    *,
    query: str,
    top_k: int,
    candidate_k: int,
    enable_rerank: bool,
    allowed_file_path_prefixes: list[str] | None,
    search_mode: str,
) -> dict[str, Any]:
    engine = get_retrieval_engine()
    try:
        return engine.search_hybrid(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )
    except Exception as primary_exc:
        if (search_mode or "").strip().lower() == "files_first":
            raise primary_exc
        fallback = engine.search_hybrid(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=False,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode="files_first",
        )
        warnings = list(fallback.get("warnings", [])) if isinstance(fallback.get("warnings"), list) else []
        warnings.append(f"local_dense_fallback_failed:{primary_exc}")
        fallback["warnings"] = warnings
        return fallback


def call_graph_entity_lookup(
    name: str,
    top_k: int = 12,
    predicate_allowlist: list[str] | None = None,
    predicate_blocklist: list[str] | None = None,
) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        mock = get_graph_engine().entity_lookup(
            name,
            top_k=top_k,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )
        has_relations = bool((mock or {}).get("relations"))
        result = {
            "backend": backend_label,
            "code": 0 if has_relations else 20001,
            "message": "ok" if has_relations else "KG_ENTITY_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/entity/lookup",
            {
                "name": name,
                "top_k": top_k,
                "predicate_allowlist": predicate_allowlist,
                "predicate_blocklist": predicate_blocklist,
            },
        )
        return {"backend": "graph-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"graph-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="graph-service-error",
            code=20090,
            message="GRAPH_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_graph_path_query(start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        mock = get_graph_engine().path_query(start, end, max_hops=max_hops, path_limit=path_limit)
        result = {
            "backend": backend_label,
            "code": 0 if mock.get("paths") else 20002,
            "message": "ok" if mock.get("paths") else "KG_PATH_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

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
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"graph-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="graph-service-error",
            code=20090,
            message="GRAPH_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_graph_syndrome_chain(symptom: str, top_k: int = 5) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        mock = get_graph_engine().syndrome_chain(symptom, top_k=top_k)
        result = {
            "backend": backend_label,
            "code": 0 if mock.get("syndromes") else 20001,
            "message": "ok" if mock.get("syndromes") else "KG_ENTITY_NOT_FOUND",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{GRAPH_SERVICE_BASE_URL}/api/v1/graph/syndrome/chain",
            {"symptom": symptom, "top_k": top_k},
        )
        return {"backend": "graph-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"graph-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="graph-service-error",
            code=20090,
            message="GRAPH_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_retrieval_hybrid(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    enable_rerank: bool = True,
    search_mode: str = "files_first",
    allowed_file_path_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        mock = _local_hybrid_search(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )
        result = {
            "backend": backend_label,
            "code": 0 if mock.get("chunks") else 30001,
            "message": "ok" if mock.get("chunks") else "RETRIEVE_EMPTY",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/search/hybrid",
            {
                "query": query,
                "top_k": top_k,
                "candidate_k": candidate_k,
                "enable_rerank": enable_rerank,
                "search_mode": search_mode,
                "allowed_file_path_prefixes": allowed_file_path_prefixes or [],
            },
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"retrieval-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="retrieval-service-error",
            code=30090,
            message="RETRIEVAL_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_retrieval_rewrite(query: str, strategy: str = "complex") -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        mock = get_retrieval_engine().rewrite_query(query, strategy=strategy)
        result = {
            "backend": backend_label,
            "code": 0,
            "message": "ok",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/search/rewrite",
            {"query": query, "strategy": strategy},
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"retrieval-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="retrieval-service-error",
            code=30090,
            message="RETRIEVAL_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_retrieval_case_qa(
    query: str,
    top_k: int = 5,
    candidate_k: int = 30,
) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        try:
            mock = get_retrieval_engine().search_case_qa(
                query=query,
                top_k=top_k,
                candidate_k=candidate_k,
            )
        except Exception as local_exc:
            mock = {
                "retrieval_mode": "case_qa_local_error",
                "chunks": [],
                "total": 0,
                "warnings": [f"local_case_qa_failed:{local_exc}"],
            }
        result = {
            "backend": backend_label,
            "code": 0 if mock.get("chunks") else 30002,
            "message": "ok" if mock.get("chunks") else "CASE_QA_EMPTY",
            "data": mock,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/search/case-qa",
            {
                "query": query,
                "top_k": top_k,
                "candidate_k": candidate_k,
            },
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"retrieval-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="retrieval-service-error",
            code=30090,
            message="RETRIEVAL_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def call_retrieval_read_section(
    path: str,
    top_k: int = 12,
) -> dict[str, Any]:
    def _local_result(backend_label: str, warning: str | None = None) -> dict[str, Any]:
        local = get_retrieval_engine().read_section(path, top_k=top_k)
        has_section = bool(local.get("section"))
        result = {
            "backend": backend_label,
            "code": 0 if has_section else 30003,
            "message": "ok" if has_section else "SECTION_EMPTY",
            "data": local,
            "trace_id": str(uuid4()),
        }
        if warning:
            result["warning"] = warning
        return result

    if execution_mode() != "sidecar":
        return _local_result("local-engine")

    try:
        payload = _post(
            f"{RETRIEVAL_SERVICE_BASE_URL}/api/v1/retrieval/read/section",
            {
                "path": path,
                "top_k": top_k,
            },
        )
        return {"backend": "retrieval-service", **payload}
    except Exception as exc:
        if sidecar_fallback_enabled():
            return _local_result("local-fallback", warning=f"retrieval-service unavailable: {exc}")
        return _service_unavailable_response(
            backend="retrieval-service-error",
            code=30090,
            message="RETRIEVAL_SERVICE_UNAVAILABLE",
            exc=exc,
        )


def service_health_snapshot() -> dict[str, Any]:
    mode = execution_mode()
    if mode != "sidecar":
        return {
            "execution_mode": mode,
            "graph_service_up": None,
            "retrieval_service_up": None,
            "graph_service_base_url": GRAPH_SERVICE_BASE_URL,
            "retrieval_service_base_url": RETRIEVAL_SERVICE_BASE_URL,
            "graph_backend": "local-engine",
            "retrieval_backend": "local-engine",
            "sidecar_probe_skipped": True,
        }
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
        "execution_mode": mode,
        "graph_service_up": graph_ok,
        "retrieval_service_up": retrieval_ok,
        "graph_service_base_url": GRAPH_SERVICE_BASE_URL,
        "retrieval_service_base_url": RETRIEVAL_SERVICE_BASE_URL,
        "graph_backend": "graph-service",
        "retrieval_backend": "retrieval-service",
        "sidecar_probe_skipped": False,
    }
