from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4


PostFunc = Callable[[str, dict[str, Any]], dict[str, Any]]
GraphEngineFactory = Callable[[], Any]
RetrievalEngineFactory = Callable[[], Any]


def service_unavailable_response(*, backend: str, code: int, message: str, exc: Exception) -> dict[str, Any]:
    return {
        "backend": backend,
        "code": code,
        "message": message,
        "data": {},
        "trace_id": str(uuid4()),
        "warning": str(exc),
    }


class LocalTCMServiceBackend:
    """Local real-engine backend used as the default path and sidecar fallback."""

    def __init__(
        self,
        *,
        graph_engine_factory: GraphEngineFactory,
        retrieval_engine_factory: RetrievalEngineFactory,
    ) -> None:
        self._graph_engine_factory = graph_engine_factory
        self._retrieval_engine_factory = retrieval_engine_factory

    def graph_entity_lookup(
        self,
        *,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._graph_engine_factory().entity_lookup(
            name,
            top_k=top_k,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )
        has_relations = bool((local_data or {}).get("relations"))
        return _service_result(
            backend=backend_label,
            code=0 if has_relations else 20001,
            message="ok" if has_relations else "KG_ENTITY_NOT_FOUND",
            data=local_data,
            warning=warning,
        )

    def graph_path_query(
        self,
        *,
        start: str,
        end: str,
        max_hops: int = 3,
        path_limit: int = 5,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._graph_engine_factory().path_query(start, end, max_hops=max_hops, path_limit=path_limit)
        return _service_result(
            backend=backend_label,
            code=0 if local_data.get("paths") else 20002,
            message="ok" if local_data.get("paths") else "KG_PATH_NOT_FOUND",
            data=local_data,
            warning=warning,
        )

    def graph_syndrome_chain(
        self,
        *,
        symptom: str,
        top_k: int = 5,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._graph_engine_factory().syndrome_chain(symptom, top_k=top_k)
        return _service_result(
            backend=backend_label,
            code=0 if local_data.get("syndromes") else 20001,
            message="ok" if local_data.get("syndromes") else "KG_ENTITY_NOT_FOUND",
            data=local_data,
            warning=warning,
        )

    def retrieval_hybrid(
        self,
        *,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        enable_rerank: bool = True,
        search_mode: str = "files_first",
        allowed_file_path_prefixes: list[str] | None = None,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._local_hybrid_search(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )
        return _service_result(
            backend=backend_label,
            code=0 if local_data.get("chunks") else 30001,
            message="ok" if local_data.get("chunks") else "RETRIEVE_EMPTY",
            data=local_data,
            warning=warning,
        )

    def retrieval_rewrite(
        self,
        *,
        query: str,
        strategy: str = "complex",
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._retrieval_engine_factory().rewrite_query(query, strategy=strategy)
        return _service_result(
            backend=backend_label,
            code=0,
            message="ok",
            data=local_data,
            warning=warning,
        )

    def retrieval_case_qa(
        self,
        *,
        query: str,
        top_k: int = 5,
        candidate_k: int = 30,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        try:
            local_data = self._retrieval_engine_factory().search_case_qa(
                query=query,
                top_k=top_k,
                candidate_k=candidate_k,
            )
        except Exception as local_exc:
            local_data = {
                "retrieval_mode": "case_qa_local_error",
                "chunks": [],
                "total": 0,
                "warnings": [f"local_case_qa_failed:{local_exc}"],
            }
        return _service_result(
            backend=backend_label,
            code=0 if local_data.get("chunks") else 30002,
            message="ok" if local_data.get("chunks") else "CASE_QA_EMPTY",
            data=local_data,
            warning=warning,
        )

    def retrieval_read_section(
        self,
        *,
        path: str,
        top_k: int = 12,
        backend_label: str = "local-engine",
        warning: str | None = None,
    ) -> dict[str, Any]:
        local_data = self._retrieval_engine_factory().read_section(path, top_k=top_k)
        has_section = bool(local_data.get("section"))
        return _service_result(
            backend=backend_label,
            code=0 if has_section else 30003,
            message="ok" if has_section else "SECTION_EMPTY",
            data=local_data,
            warning=warning,
        )

    def health_snapshot(self, *, graph_base_url: str, retrieval_base_url: str, execution_mode: str) -> dict[str, Any]:
        return {
            "execution_mode": execution_mode,
            "graph_service_up": None,
            "retrieval_service_up": None,
            "graph_service_base_url": graph_base_url,
            "retrieval_service_base_url": retrieval_base_url,
            "graph_backend": "local-engine",
            "retrieval_backend": "local-engine",
            "sidecar_probe_skipped": True,
        }

    def _local_hybrid_search(
        self,
        *,
        query: str,
        top_k: int,
        candidate_k: int,
        enable_rerank: bool,
        allowed_file_path_prefixes: list[str] | None,
        search_mode: str,
    ) -> dict[str, Any]:
        engine = self._retrieval_engine_factory()
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


class SidecarTCMServiceBackend:
    """HTTP sidecar backend with explicit local real-engine fallback."""

    def __init__(
        self,
        *,
        graph_base_url: str,
        retrieval_base_url: str,
        post_func: PostFunc,
        health_func: Callable[[str], bool],
        local_backend: LocalTCMServiceBackend,
        fallback_enabled: bool,
    ) -> None:
        self._graph_base_url = graph_base_url.rstrip("/")
        self._retrieval_base_url = retrieval_base_url.rstrip("/")
        self._post = post_func
        self._health = health_func
        self._local = local_backend
        self._fallback_enabled = fallback_enabled

    def graph_entity_lookup(
        self,
        *,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._graph_base_url}/api/v1/graph/entity/lookup",
                {
                    "name": name,
                    "top_k": top_k,
                    "predicate_allowlist": predicate_allowlist,
                    "predicate_blocklist": predicate_blocklist,
                },
            )
            return {"backend": "graph-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.graph_entity_lookup(
                    name=name,
                    top_k=top_k,
                    predicate_allowlist=predicate_allowlist,
                    predicate_blocklist=predicate_blocklist,
                    backend_label="local-fallback",
                    warning=f"graph-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="graph-service-error",
                code=20090,
                message="GRAPH_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def graph_path_query(self, *, start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._graph_base_url}/api/v1/graph/path/query",
                {
                    "start": start,
                    "end": end,
                    "max_hops": max_hops,
                    "path_limit": path_limit,
                },
            )
            return {"backend": "graph-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.graph_path_query(
                    start=start,
                    end=end,
                    max_hops=max_hops,
                    path_limit=path_limit,
                    backend_label="local-fallback",
                    warning=f"graph-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="graph-service-error",
                code=20090,
                message="GRAPH_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def graph_syndrome_chain(self, *, symptom: str, top_k: int = 5) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._graph_base_url}/api/v1/graph/syndrome/chain",
                {"symptom": symptom, "top_k": top_k},
            )
            return {"backend": "graph-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.graph_syndrome_chain(
                    symptom=symptom,
                    top_k=top_k,
                    backend_label="local-fallback",
                    warning=f"graph-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="graph-service-error",
                code=20090,
                message="GRAPH_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def retrieval_hybrid(
        self,
        *,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        enable_rerank: bool = True,
        search_mode: str = "files_first",
        allowed_file_path_prefixes: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._retrieval_base_url}/api/v1/retrieval/search/hybrid",
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
            if self._fallback_enabled:
                return self._local.retrieval_hybrid(
                    query=query,
                    top_k=top_k,
                    candidate_k=candidate_k,
                    enable_rerank=enable_rerank,
                    search_mode=search_mode,
                    allowed_file_path_prefixes=allowed_file_path_prefixes,
                    backend_label="local-fallback",
                    warning=f"retrieval-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="retrieval-service-error",
                code=30090,
                message="RETRIEVAL_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def retrieval_rewrite(self, *, query: str, strategy: str = "complex") -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._retrieval_base_url}/api/v1/retrieval/search/rewrite",
                {"query": query, "strategy": strategy},
            )
            return {"backend": "retrieval-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.retrieval_rewrite(
                    query=query,
                    strategy=strategy,
                    backend_label="local-fallback",
                    warning=f"retrieval-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="retrieval-service-error",
                code=30090,
                message="RETRIEVAL_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def retrieval_case_qa(self, *, query: str, top_k: int = 5, candidate_k: int = 30) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._retrieval_base_url}/api/v1/retrieval/search/case-qa",
                {
                    "query": query,
                    "top_k": top_k,
                    "candidate_k": candidate_k,
                },
            )
            return {"backend": "retrieval-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.retrieval_case_qa(
                    query=query,
                    top_k=top_k,
                    candidate_k=candidate_k,
                    backend_label="local-fallback",
                    warning=f"retrieval-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="retrieval-service-error",
                code=30090,
                message="RETRIEVAL_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def retrieval_read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        try:
            payload = self._post(
                f"{self._retrieval_base_url}/api/v1/retrieval/read/section",
                {
                    "path": path,
                    "top_k": top_k,
                },
            )
            return {"backend": "retrieval-service", **payload}
        except Exception as exc:
            if self._fallback_enabled:
                return self._local.retrieval_read_section(
                    path=path,
                    top_k=top_k,
                    backend_label="local-fallback",
                    warning=f"retrieval-service unavailable: {exc}",
                )
            return service_unavailable_response(
                backend="retrieval-service-error",
                code=30090,
                message="RETRIEVAL_SERVICE_UNAVAILABLE",
                exc=exc,
            )

    def health_snapshot(self, *, execution_mode: str) -> dict[str, Any]:
        graph_ok = False
        retrieval_ok = False
        try:
            graph_ok = self._health(f"{self._graph_base_url}/api/v1/graph/health")
        except Exception:
            graph_ok = False
        try:
            retrieval_ok = self._health(f"{self._retrieval_base_url}/api/v1/retrieval/health")
        except Exception:
            retrieval_ok = False
        return {
            "execution_mode": execution_mode,
            "graph_service_up": graph_ok,
            "retrieval_service_up": retrieval_ok,
            "graph_service_base_url": self._graph_base_url,
            "retrieval_service_base_url": self._retrieval_base_url,
            "graph_backend": "graph-service",
            "retrieval_backend": "retrieval-service",
            "sidecar_probe_skipped": False,
            "sidecar_fallback_enabled": self._fallback_enabled,
        }


def _service_result(
    *,
    backend: str,
    code: int,
    message: str,
    data: dict[str, Any],
    warning: str | None = None,
) -> dict[str, Any]:
    result = {
        "backend": backend,
        "code": code,
        "message": message,
        "data": data,
        "trace_id": str(uuid4()),
    }
    if warning:
        result["warning"] = warning
    return result
