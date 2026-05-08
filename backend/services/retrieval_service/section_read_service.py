from __future__ import annotations

from typing import Any

from services.retrieval_service.files_first_support import build_section_response


class SectionReadService:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def read_section(self, path: str, *, top_k: int = 12) -> dict[str, Any]:
        payload = self.engine.files_first_store.read_section(path=path, top_k=top_k)
        return build_section_response(path=path, payload=payload, parent_store=self.engine.parent_store)
