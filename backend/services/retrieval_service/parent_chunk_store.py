from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ParentChunkStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.store_path.exists():
            return {}
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert_documents(self, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0
        payload = self._load()
        count = 0
        for doc in docs:
            chunk_id = str(doc.get("chunk_id", "")).strip()
            if not chunk_id:
                continue
            payload[chunk_id] = dict(doc)
            count += 1
        self._save(payload)
        return count

    def get_documents_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        payload = self._load()
        return [payload[item] for item in chunk_ids if item in payload]
