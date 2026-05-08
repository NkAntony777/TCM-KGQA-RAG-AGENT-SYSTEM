from __future__ import annotations

from typing import Any

from services.retrieval_service.search_runtime import search_hybrid as run_search_hybrid


class FilesFirstSearchService:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def search_hybrid(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
        enable_rerank: bool,
        allowed_file_path_prefixes: list[str] | None = None,
        search_mode: str = "files_first",
    ) -> dict[str, Any]:
        return run_search_hybrid(
            self.engine,
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )
