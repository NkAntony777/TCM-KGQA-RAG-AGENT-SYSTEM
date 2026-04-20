from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from services.retrieval_service.settings import RetrievalServiceSettings


_PYMILVUS_LOCK = threading.Lock()
_PYMILVUS_SDK: tuple[Any, Any, Any, Any] | None = None


def _load_pymilvus_sdk() -> tuple[Any, Any, Any, Any]:
    global _PYMILVUS_SDK
    if _PYMILVUS_SDK is not None:
        return _PYMILVUS_SDK
    with _PYMILVUS_LOCK:
        if _PYMILVUS_SDK is not None:
            return _PYMILVUS_SDK
        original_milvus_uri = os.environ.get("MILVUS_URI", "")
        needs_import_workaround = bool(original_milvus_uri and "://" not in original_milvus_uri)
        if needs_import_workaround:
            os.environ["MILVUS_URI"] = "http://127.0.0.1:19530"
        try:  # pragma: no cover - optional dependency in local dev
            from pymilvus import AnnSearchRequest, DataType, MilvusClient, RRFRanker
        except Exception:  # pragma: no cover
            _PYMILVUS_SDK = (None, None, None, None)
        else:
            _PYMILVUS_SDK = (AnnSearchRequest, DataType, MilvusClient, RRFRanker)
        finally:
            if needs_import_workaround:
                os.environ["MILVUS_URI"] = original_milvus_uri
    return _PYMILVUS_SDK


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key

    def is_ready(self) -> bool:
        return bool(self.base_url and self.api_key)

    def embed(self, texts: list[str], model: str, *, dimensions: int | None = None) -> list[list[float]]:
        if not self.is_ready():
            raise RuntimeError("embedding_client_not_configured")
        last_error: Exception | None = None
        max_retries = 6
        for attempt in range(max_retries):
            try:
                payload: dict[str, Any] = {"model": model, "input": texts, "encoding_format": "float"}
                if dimensions and dimensions > 0:
                    payload["dimensions"] = int(dimensions)
                with httpx.Client(timeout=45.0, trust_env=False) as client:
                    response = client.post(
                        f"{self.base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    payload = response.json()
                return [item["embedding"] for item in payload.get("data", [])]
            except Exception as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(min(8.0, 0.8 * (2**attempt)))
        raise RuntimeError(f"embedding_request_failed: {last_error}")

    def chat(self, prompt: str, model: str) -> str:
        if not self.is_ready():
            return ""
        with httpx.Client(timeout=20.0, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", "")).strip()


class MilvusHybridStore:
    def __init__(self, settings: RetrievalServiceSettings):
        self.settings = settings
        self._client = None

    def _is_enabled(self) -> bool:
        return bool(self.settings.vector_compatibility_enabled)

    def _sdk(self) -> tuple[Any, Any, Any, Any]:
        return _load_pymilvus_sdk()

    def _get_client(self):
        _, _, MilvusClient, _ = self._sdk()
        if not self._is_enabled():
            return None
        if self._client is None and MilvusClient is not None:
            uri = self.settings.milvus_uri.strip()
            if uri:
                uri_path = Path(uri)
                if not uri_path.is_absolute():
                    uri_path = self.settings.project_backend_dir / uri_path
                uri_path.parent.mkdir(parents=True, exist_ok=True)
                self._client = MilvusClient(uri=str(uri_path))
            else:
                self._client = MilvusClient(uri=f"http://{self.settings.milvus_host}:{self.settings.milvus_port}")
        return self._client

    def _is_reachable(self) -> bool:
        if not self._is_enabled():
            return False
        if self.settings.milvus_uri.strip():
            return True
        try:
            with socket.create_connection(
                (self.settings.milvus_host, int(self.settings.milvus_port)),
                timeout=1.0,
            ):
                return True
        except OSError:
            return False

    def is_available(self) -> bool:
        return self._is_reachable() and self._get_client() is not None

    def has_collection(self) -> bool:
        if not self._is_reachable():
            return False
        client = self._get_client()
        if not client:
            return False
        return client.has_collection(self.settings.milvus_collection)

    def health(self) -> dict[str, Any]:
        if not self._is_enabled():
            return {"milvus_available": False, "collection_exists": False, "vector_compatibility_enabled": False}
        try:
            if not self._is_reachable():
                return {"milvus_available": False, "collection_exists": False, "error": "milvus_unreachable"}
            client = self._get_client()
            if not client:
                return {"milvus_available": False, "collection_exists": False}
            return {
                "milvus_available": True,
                "collection_exists": client.has_collection(self.settings.milvus_collection),
            }
        except Exception as exc:
            return {
                "milvus_available": False,
                "collection_exists": False,
                "error": str(exc),
            }

    def reset_collection(self) -> None:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if client and client.has_collection(self.settings.milvus_collection):
            client.drop_collection(self.settings.milvus_collection)

    def ensure_collection(self, dense_dim: int) -> None:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if not client:
            raise RuntimeError("pymilvus_not_installed")
        _, DataType, _, _ = self._sdk()
        if client.has_collection(self.settings.milvus_collection):
            return
        schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("dense_embedding", DataType.FLOAT_VECTOR, dim=dense_dim)
        schema.add_field("sparse_embedding", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("filename", DataType.VARCHAR, max_length=255)
        schema.add_field("file_type", DataType.VARCHAR, max_length=50)
        schema.add_field("file_path", DataType.VARCHAR, max_length=1024)
        schema.add_field("page_number", DataType.INT64)
        schema.add_field("chunk_idx", DataType.INT64)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("parent_chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("root_chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("chunk_level", DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense_embedding",
            index_type="HNSW",
            metric_type="IP",
            params={"M": 16, "efConstruction": 256},
        )
        index_params.add_index(
            field_name="sparse_embedding",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={"drop_ratio_build": 0.2},
        )
        client.create_collection(
            collection_name=self.settings.milvus_collection,
            schema=schema,
            index_params=index_params,
        )

    def insert(self, rows: list[dict[str, Any]]) -> None:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if not client:
            raise RuntimeError("pymilvus_not_installed")
        if rows:
            client.insert(self.settings.milvus_collection, rows)

    def hybrid_search(
        self,
        *,
        dense_embedding: list[float],
        sparse_embedding: dict[int, float],
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> list[dict[str, Any]]:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if not client:
            raise RuntimeError("pymilvus_not_installed")
        AnnSearchRequest, _, _, RRFRanker = self._sdk()
        expr = f"chunk_level == {leaf_level}"
        dense_search = AnnSearchRequest(
            data=[dense_embedding],
            anns_field="dense_embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=candidate_k,
            expr=expr,
        )
        sparse_search = AnnSearchRequest(
            data=[sparse_embedding],
            anns_field="sparse_embedding",
            param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=candidate_k,
            expr=expr,
        )
        results = client.hybrid_search(
            collection_name=self.settings.milvus_collection,
            reqs=[dense_search, sparse_search],
            ranker=RRFRanker(k=60),
            limit=top_k,
            output_fields=[
                "text",
                "filename",
                "file_type",
                "file_path",
                "page_number",
                "chunk_idx",
                "chunk_id",
                "parent_chunk_id",
                "root_chunk_id",
                "chunk_level",
            ],
        )
        return self._flatten_hits(results)

    def dense_search(
        self,
        *,
        dense_embedding: list[float],
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> list[dict[str, Any]]:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if not client:
            raise RuntimeError("pymilvus_not_installed")
        results = client.search(
            collection_name=self.settings.milvus_collection,
            data=[dense_embedding],
            anns_field="dense_embedding",
            search_params={"metric_type": "IP", "params": {"ef": 64}},
            limit=max(candidate_k, top_k),
            output_fields=[
                "text",
                "filename",
                "file_type",
                "file_path",
                "page_number",
                "chunk_idx",
                "chunk_id",
                "parent_chunk_id",
                "root_chunk_id",
                "chunk_level",
            ],
            filter=f"chunk_level == {leaf_level}",
        )
        return self._flatten_hits(results)

    def sparse_search(
        self,
        *,
        sparse_embedding: dict[int, float],
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> list[dict[str, Any]]:
        if not self._is_reachable():
            raise RuntimeError("milvus_unreachable")
        client = self._get_client()
        if not client:
            raise RuntimeError("pymilvus_not_installed")
        results = client.search(
            collection_name=self.settings.milvus_collection,
            data=[sparse_embedding],
            anns_field="sparse_embedding",
            search_params={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=max(candidate_k, top_k),
            output_fields=[
                "text",
                "filename",
                "file_type",
                "file_path",
                "page_number",
                "chunk_idx",
                "chunk_id",
                "parent_chunk_id",
                "root_chunk_id",
                "chunk_level",
            ],
            filter=f"chunk_level == {leaf_level}",
        )
        return self._flatten_hits(results)

    @staticmethod
    def _flatten_hits(results: list[Any]) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        for hits in results:
            for index, hit in enumerate(hits, start=1):
                entity = hit.get("entity", hit)
                formatted.append(
                    {
                        "id": hit.get("id"),
                        "text": entity.get("text", hit.get("text", "")),
                        "filename": entity.get("filename", hit.get("filename", "")),
                        "file_type": entity.get("file_type", hit.get("file_type", "")),
                        "file_path": entity.get("file_path", hit.get("file_path", "")),
                        "page_number": entity.get("page_number", hit.get("page_number", 0)),
                        "chunk_idx": entity.get("chunk_idx", hit.get("chunk_idx", 0)),
                        "chunk_id": entity.get("chunk_id", hit.get("chunk_id", "")),
                        "parent_chunk_id": entity.get("parent_chunk_id", hit.get("parent_chunk_id", "")),
                        "root_chunk_id": entity.get("root_chunk_id", hit.get("root_chunk_id", "")),
                        "chunk_level": entity.get("chunk_level", hit.get("chunk_level", 0)),
                        "score": hit.get("distance", 0.0),
                        "rrf_rank": index,
                    }
                )
        return formatted


class LocalHybridStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def health(self) -> dict[str, Any]:
        return {
            "local_index_available": self.store_path.exists(),
            "local_index_path": str(self.store_path),
        }

    def reset(self) -> None:
        if self.store_path.exists():
            self.store_path.unlink()

    def save(self, rows: list[dict[str, Any]]) -> None:
        self.store_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    def search(
        self,
        *,
        dense_embedding: list[float],
        sparse_embedding: dict[int, float],
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> tuple[list[dict[str, Any]], str]:
        rows = [row for row in self.load() if int(row.get("chunk_level", 0) or 0) == leaf_level]
        if not rows:
            return [], "empty"
        dense_ranked = sorted(
            rows,
            key=lambda item: self._dot(dense_embedding, item.get("dense_embedding", [])),
            reverse=True,
        )[:candidate_k]
        sparse_ranked = sorted(
            rows,
            key=lambda item: self._sparse_dot(sparse_embedding, item.get("sparse_embedding", {})),
            reverse=True,
        )[:candidate_k]
        if sparse_embedding:
            return self._rrf_merge(dense_ranked, sparse_ranked, top_k), "hybrid_local"
        for index, item in enumerate(dense_ranked[:top_k], start=1):
            item["rrf_rank"] = index
        return dense_ranked[:top_k], "dense_local_fallback"

    def search_sparse(
        self,
        *,
        sparse_embedding: dict[int, float],
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> tuple[list[dict[str, Any]], str]:
        rows = [row for row in self.load() if int(row.get("chunk_level", 0) or 0) == leaf_level]
        if not rows:
            return [], "empty"
        if not sparse_embedding:
            return [], "sparse_query_empty"
        sparse_ranked = sorted(
            rows,
            key=lambda item: self._sparse_dot(sparse_embedding, item.get("sparse_embedding", {})),
            reverse=True,
        )[: max(candidate_k, top_k)]
        results: list[dict[str, Any]] = []
        for rank, item in enumerate(sparse_ranked[:top_k], start=1):
            row = dict(item)
            row["score"] = self._sparse_dot(sparse_embedding, item.get("sparse_embedding", {}))
            row["rrf_rank"] = rank
            results.append(row)
        return results, "sparse_local"

    @staticmethod
    def _dot(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        return float(sum(a * b for a, b in zip(left, right)))

    @staticmethod
    def _sparse_dot(left: dict[int, float], right: dict[str, float] | dict[int, float]) -> float:
        if not left or not right:
            return 0.0
        score = 0.0
        normalized_right = {int(key): float(value) for key, value in right.items()}
        for key, value in left.items():
            score += float(value) * normalized_right.get(int(key), 0.0)
        return score

    @staticmethod
    def _rrf_merge(dense_ranked: list[dict[str, Any]], sparse_ranked: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        scores: dict[str, float] = {}
        payloads: dict[str, dict[str, Any]] = {}

        def add_rank(items: list[dict[str, Any]], field: str) -> None:
            for rank, item in enumerate(items, start=1):
                key = str(item.get("chunk_id") or item.get("id") or rank)
                payloads[key] = dict(item)
                payloads[key][field] = rank
                scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)

        add_rank(dense_ranked, "dense_rank")
        add_rank(sparse_ranked, "sparse_rank")
        merged = sorted(payloads.items(), key=lambda item: scores[item[0]], reverse=True)[:top_k]
        results: list[dict[str, Any]] = []
        for rank, (key, item) in enumerate(merged, start=1):
            row = dict(item)
            row["score"] = scores[key]
            row["rrf_rank"] = rank
            results.append(row)
        return results
