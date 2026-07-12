from __future__ import annotations

import json


class FakeRouteTool:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def _run(self, query: str, top_k: int = 12):
        return json.dumps(self.payload, ensure_ascii=False)


class FakeAnswerGenerator:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeSequentialAnswerGenerator:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self.responses:
            raise RuntimeError("no_more_responses")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakePlannerAliasService:
    def aliases_for_entity(self, entity_name: str, *, max_aliases: int = 8, max_depth: int = 2) -> list[str]:
        mapping = {
            "六味地黄丸": ["地黄丸", "六味丸"],
            "地黄丸": ["六味地黄丸", "六味丸"],
            "六味丸": ["六味地黄丸", "地黄丸"],
        }
        return mapping.get(entity_name, [])


class FakeEvidenceNavigator:
    def __init__(
        self,
        *,
        listed_paths: list[str] | None = None,
        read_results: dict[str, dict[str, object]] | None = None,
        search_results: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.listed_paths = listed_paths or []
        self.read_results = read_results or {}
        self.search_results = search_results or {}
        self.calls: list[dict[str, object]] = []

    def list_evidence_paths(self, *, query: str, route_payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append({"tool": "list_evidence_paths", "query": query})
        return {"tool": "list_evidence_paths", "paths": list(self.listed_paths), "count": len(self.listed_paths)}

    def read_evidence_path(self, *, path: str, query: str = "", source_hint: str = "", top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "read_evidence_path", "path": path, "query": query, "source_hint": source_hint, "top_k": top_k})
        return dict(self.read_results.get(path, {"tool": "read_evidence_path", "path": path, "status": "empty", "items": [], "count": 0}))

    def search_evidence_text(self, *, query: str, source_hint: str = "", scope_paths: list[str] | None = None, top_k: int | None = None) -> dict[str, object]:
        self.calls.append({"tool": "search_evidence_text", "query": query, "source_hint": source_hint, "scope_paths": scope_paths or [], "top_k": top_k})
        key = json.dumps({"query": query, "scope_paths": scope_paths or []}, ensure_ascii=False, sort_keys=True)
        return dict(self.search_results.get(key, {"tool": "search_evidence_text", "status": "empty", "items": [], "count": 0}))
