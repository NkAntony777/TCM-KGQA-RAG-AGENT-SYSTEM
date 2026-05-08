from __future__ import annotations

from typing import Any

from services.retrieval_service import query_rewrite_runtime


class QueryRewriteService:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def maybe_refine_files_first_query(
        self,
        *,
        query: str,
        search_mode: str,
        result: dict[str, Any],
        top_k: int,
    ) -> str:
        return query_rewrite_runtime._maybe_refine_files_first_query(
            self.engine,
            query=query,
            search_mode=search_mode,
            result=result,
            top_k=top_k,
        )

    def refine_files_first_query(self, query: str) -> str:
        return query_rewrite_runtime._refine_files_first_query(self.engine, query)

    def fast_refine_files_first_query(self, query: str) -> str:
        return query_rewrite_runtime._fast_refine_files_first_query(self.engine, query)

    def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
        return query_rewrite_runtime.rewrite_query(self.engine, query, strategy)
