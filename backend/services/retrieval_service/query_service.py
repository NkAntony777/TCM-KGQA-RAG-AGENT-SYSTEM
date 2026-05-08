from __future__ import annotations

from typing import Any

from services.retrieval_service.case_qa_search_service import CaseQASearchService
from services.retrieval_service.files_first_search_service import FilesFirstSearchService
from services.retrieval_service.query_rewrite_service import QueryRewriteService
from services.retrieval_service.section_read_service import SectionReadService


class RetrievalQueryService:
    """Online query boundary for RetrievalEngine.

    The engine still owns stores, clients, and indexing state. This service keeps
    read/query orchestration separate from indexing without changing public
    RetrievalEngine methods.
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.files_first = FilesFirstSearchService(engine)
        self.case_qa = CaseQASearchService(engine)
        self.sections = SectionReadService(engine)
        self.rewrite = QueryRewriteService(engine)

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
        return self.files_first.search_hybrid(
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
            allowed_file_path_prefixes=allowed_file_path_prefixes,
            search_mode=search_mode,
        )

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        return self.case_qa.search_case_qa(query, top_k=top_k, candidate_k=candidate_k)

    def read_section(self, path: str, *, top_k: int = 12) -> dict[str, Any]:
        return self.sections.read_section(path, top_k=top_k)

    def maybe_refine_files_first_query(
        self,
        *,
        query: str,
        search_mode: str,
        result: dict[str, Any],
        top_k: int,
    ) -> str:
        return self.rewrite.maybe_refine_files_first_query(
            query=query,
            search_mode=search_mode,
            result=result,
            top_k=top_k,
        )

    def refine_files_first_query(self, query: str) -> str:
        return self.rewrite.refine_files_first_query(query)

    def fast_refine_files_first_query(self, query: str) -> str:
        return self.rewrite.fast_refine_files_first_query(query)

    def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
        return self.rewrite.rewrite_query(query, strategy)
