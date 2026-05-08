from __future__ import annotations

from typing import Any

from services.retrieval_service import case_qa_runtime


class CaseQASearchService:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        return case_qa_runtime.search_case_qa(self.engine, query, top_k=top_k, candidate_k=candidate_k)
