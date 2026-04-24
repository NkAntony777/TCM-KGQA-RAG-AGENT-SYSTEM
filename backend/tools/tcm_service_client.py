from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import httpx

from services.graph_service.engine import get_graph_engine
from services.retrieval_service.engine import get_retrieval_engine
from tools.tcm_service_backends import LocalTCMServiceBackend, SidecarTCMServiceBackend


def graph_service_base_url() -> str:
    return os.getenv("GRAPH_SERVICE_BASE_URL", "http://127.0.0.1:8101").strip().rstrip("/")


def retrieval_service_base_url() -> str:
    return os.getenv("RETRIEVAL_SERVICE_BASE_URL", "http://127.0.0.1:8102").strip().rstrip("/")


def execution_mode() -> str:
    mode = os.getenv("TCM_SERVICE_MODE", "local").strip().lower()
    return mode if mode in {"local", "sidecar"} else "local"


def sidecar_fallback_enabled() -> bool:
    return os.getenv("TCM_SERVICE_SIDECAR_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}


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


def _local_backend() -> LocalTCMServiceBackend:
    return LocalTCMServiceBackend(
        graph_engine_factory=get_graph_engine,
        retrieval_engine_factory=get_retrieval_engine,
    )


def _active_backend() -> LocalTCMServiceBackend | SidecarTCMServiceBackend:
    local_backend = _local_backend()
    if execution_mode() != "sidecar":
        return local_backend
    return SidecarTCMServiceBackend(
        graph_base_url=graph_service_base_url(),
        retrieval_base_url=retrieval_service_base_url(),
        post_func=_post,
        health_func=_health,
        local_backend=local_backend,
        fallback_enabled=sidecar_fallback_enabled(),
    )


def call_graph_entity_lookup(
    name: str,
    top_k: int = 12,
    predicate_allowlist: list[str] | None = None,
    predicate_blocklist: list[str] | None = None,
) -> dict[str, Any]:
    return _active_backend().graph_entity_lookup(
        name=name,
        top_k=top_k,
        predicate_allowlist=predicate_allowlist,
        predicate_blocklist=predicate_blocklist,
    )


def call_graph_path_query(start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
    return _active_backend().graph_path_query(
        start=start,
        end=end,
        max_hops=max_hops,
        path_limit=path_limit,
    )


def call_graph_syndrome_chain(symptom: str, top_k: int = 5) -> dict[str, Any]:
    return _active_backend().graph_syndrome_chain(symptom=symptom, top_k=top_k)


def call_retrieval_hybrid(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    enable_rerank: bool = True,
    search_mode: str = "files_first",
    allowed_file_path_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    return _active_backend().retrieval_hybrid(
        query=query,
        top_k=top_k,
        candidate_k=candidate_k,
        enable_rerank=enable_rerank,
        search_mode=search_mode,
        allowed_file_path_prefixes=allowed_file_path_prefixes,
    )


def call_retrieval_rewrite(query: str, strategy: str = "complex") -> dict[str, Any]:
    return _active_backend().retrieval_rewrite(query=query, strategy=strategy)


def call_retrieval_case_qa(
    query: str,
    top_k: int = 5,
    candidate_k: int = 30,
) -> dict[str, Any]:
    return _active_backend().retrieval_case_qa(
        query=query,
        top_k=top_k,
        candidate_k=candidate_k,
    )


def call_retrieval_read_section(
    path: str,
    top_k: int = 12,
) -> dict[str, Any]:
    return _active_backend().retrieval_read_section(path=path, top_k=top_k)


def service_health_snapshot() -> dict[str, Any]:
    mode = execution_mode()
    backend = _active_backend()
    if isinstance(backend, SidecarTCMServiceBackend):
        return backend.health_snapshot(execution_mode=mode)
    return backend.health_snapshot(
        graph_base_url=graph_service_base_url(),
        retrieval_base_url=retrieval_service_base_url(),
        execution_mode=mode,
    )
