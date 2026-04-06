from __future__ import annotations

import json
import math
import os
import re
import socket
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from services.retrieval_service.chroma_case_store import ChromaCaseQASettings, ChromaCaseQAStore

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_raw_milvus_uri = os.getenv("MILVUS_URI", "").strip()
_use_pymilvus = not _raw_milvus_uri or _raw_milvus_uri.startswith(("http://", "https://"))
if _use_pymilvus:
    try:  # pragma: no cover - optional at import time, required in deployed S2 env
        from pymilvus import AnnSearchRequest, DataType, MilvusClient, RRFRanker
    except Exception:  # pragma: no cover
        AnnSearchRequest = None
        DataType = None
        MilvusClient = None
        RRFRanker = None
else:  # pragma: no cover - local index mode on unsupported platforms
    AnnSearchRequest = None
    DataType = None
    MilvusClient = None
    RRFRanker = None


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


@dataclass(frozen=True)
class RetrievalServiceSettings:
    project_backend_dir: Path
    milvus_uri: str
    milvus_host: str
    milvus_port: str
    milvus_collection: str
    embedding_base_url: str
    embedding_model: str
    embedding_api_key: str
    rewrite_base_url: str
    rewrite_model: str
    rewrite_api_key: str
    rerank_endpoint: str
    rerank_model: str
    rerank_api_key: str
    auto_merge_enabled: bool
    auto_merge_threshold: int
    leaf_retrieve_level: int
    dense_dim: int
    chroma_case_db_path: Path
    chroma_case_mirror_path: Path
    chroma_case_collection_prefix: str
    sparse_lexicon_path: Path
    parent_chunk_store_path: Path
    local_index_path: Path
    sample_corpus_path: Path


def load_settings() -> RetrievalServiceSettings:
    backend_dir = Path(__file__).resolve().parents[2]
    base_url = _first_env("EMBEDDING_BASE_URL", "LLM_BASE_URL", "BASE_URL", "OPENAI_BASE_URL")
    api_key = _first_env("EMBEDDING_API_KEY", "LLM_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY")
    rewrite_base_url = _first_env("LLM_BASE_URL", "BASE_URL", "OPENAI_BASE_URL", default=base_url)
    rewrite_api_key = _first_env("LLM_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY", default=api_key)
    rerank_endpoint = _first_env("RETRIEVAL_RERANK_ENDPOINT", "RERANK_BINDING_HOST").rstrip("/")
    if rerank_endpoint and not rerank_endpoint.endswith("/v1/rerank"):
        rerank_endpoint = f"{rerank_endpoint}/v1/rerank"

    return RetrievalServiceSettings(
        project_backend_dir=backend_dir,
        milvus_uri=_first_env("MILVUS_URI"),
        milvus_host=_first_env("MILVUS_HOST", default="127.0.0.1"),
        milvus_port=_first_env("MILVUS_PORT", default="19530"),
        milvus_collection=_first_env("MILVUS_COLLECTION", default="embeddings_collection"),
        embedding_base_url=base_url,
        embedding_model=_first_env("EMBEDDING_MODEL", "EMBEDDER", default="text-embedding-3-small"),
        embedding_api_key=api_key,
        rewrite_base_url=rewrite_base_url,
        rewrite_model=_first_env("RETRIEVAL_REWRITE_MODEL", "LLM_MODEL", "MODEL", default="gpt-4.1-mini"),
        rewrite_api_key=rewrite_api_key,
        rerank_endpoint=rerank_endpoint,
        rerank_model=_first_env("RETRIEVAL_RERANK_MODEL", "RERANK_MODEL"),
        rerank_api_key=_first_env("RETRIEVAL_RERANK_API_KEY", "RERANK_API_KEY"),
        auto_merge_enabled=_first_env("AUTO_MERGE_ENABLED", default="true").lower() != "false",
        auto_merge_threshold=int(_first_env("AUTO_MERGE_THRESHOLD", default="2")),
        leaf_retrieve_level=int(_first_env("LEAF_RETRIEVE_LEVEL", default="3")),
        dense_dim=int(_first_env("RETRIEVAL_DENSE_DIM", default="2560")),
        chroma_case_db_path=Path(_first_env("CHROMA_CASE_DB_PATH", default="E:/tcm_vector_db")),
        chroma_case_mirror_path=backend_dir / "storage" / "chroma_case_query_mirror",
        chroma_case_collection_prefix=_first_env("CHROMA_CASE_COLLECTION_PREFIX", default="tcm_shard_"),
        sparse_lexicon_path=backend_dir / "storage" / "retrieval_sparse_lexicon.json",
        parent_chunk_store_path=backend_dir / "storage" / "retrieval_parent_chunks.json",
        local_index_path=backend_dir / "storage" / "retrieval_local_index.json",
        sample_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "sample_corpus.json",
    )


class SparseLexiconStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._vocab: dict[str, int] = {}
        self._doc_freq: Counter[str] = Counter()
        self._total_docs = 0
        self._avg_doc_len = 1.0
        self.k1 = 1.5
        self.b = 0.75
        self.load()

    def tokenize(self, text: str) -> list[str]:
        normalized = (text or "").lower()
        tokens: list[str] = []
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
        english_pattern = re.compile(r"[a-zA-Z]+")
        idx = 0
        while idx < len(normalized):
            char = normalized[idx]
            if chinese_pattern.match(char):
                tokens.append(char)
                idx += 1
            elif english_pattern.match(char):
                match = english_pattern.match(normalized[idx:])
                if match:
                    token = match.group()
                    tokens.append(token)
                    idx += len(token)
                else:
                    idx += 1
            else:
                idx += 1
        return tokens

    def fit(self, texts: list[str]) -> None:
        self._vocab = {}
        self._doc_freq = Counter()
        self._total_docs = len(texts)
        total_len = 0

        for text in texts:
            tokens = self.tokenize(text)
            total_len += len(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freq[token] += 1
                if token not in self._vocab:
                    self._vocab[token] = len(self._vocab)

        self._avg_doc_len = total_len / self._total_docs if self._total_docs else 1.0

    def save(self) -> None:
        payload = {
            "vocab": self._vocab,
            "doc_freq": dict(self._doc_freq),
            "total_docs": self._total_docs,
            "avg_doc_len": self._avg_doc_len,
        }
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        self._vocab = {str(key): int(value) for key, value in payload.get("vocab", {}).items()}
        self._doc_freq = Counter({str(key): int(value) for key, value in payload.get("doc_freq", {}).items()})
        self._total_docs = int(payload.get("total_docs", 0) or 0)
        self._avg_doc_len = float(payload.get("avg_doc_len", 1.0) or 1.0)

    def is_ready(self) -> bool:
        return bool(self._vocab) and self._total_docs > 0

    def _idf(self, token: str) -> float:
        df = self._doc_freq.get(token, 0)
        if df <= 0:
            return 0.0
        return math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1)

    def encode_document(self, text: str) -> dict[int, float]:
        return self._encode(text, allow_new_tokens=True)

    def encode_query(self, text: str) -> dict[int, float]:
        return self._encode(text, allow_new_tokens=False)

    def _encode(self, text: str, *, allow_new_tokens: bool) -> dict[int, float]:
        tokens = self.tokenize(text)
        if not tokens:
            return {}

        tf = Counter(tokens)
        doc_len = len(tokens)
        sparse_vector: dict[int, float] = {}

        for token, freq in tf.items():
            if token not in self._vocab:
                if not allow_new_tokens:
                    continue
                self._vocab[token] = len(self._vocab)
            token_id = self._vocab[token]
            idf = self._idf(token)
            if idf <= 0:
                continue
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1))
            score = idf * numerator / denominator
            if score > 0:
                sparse_vector[token_id] = float(score)
        return sparse_vector


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


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key

    def is_ready(self) -> bool:
        return bool(self.base_url and self.api_key)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        if not self.is_ready():
            raise RuntimeError("embedding_client_not_configured")
        last_error: Exception | None = None
        for _ in range(3):
            try:
                with httpx.Client(timeout=20.0) as client:
                    response = client.post(
                        f"{self.base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"model": model, "input": texts, "encoding_format": "float"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                return [item["embedding"] for item in payload.get("data", [])]
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"embedding_request_failed: {last_error}")

    def chat(self, prompt: str, model: str) -> str:
        if not self.is_ready():
            return ""
        with httpx.Client(timeout=20.0) as client:
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

    def _get_client(self):
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
        if client.has_collection(self.settings.milvus_collection):
            return
        schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("dense_embedding", DataType.FLOAT_VECTOR, dim=dense_dim)
        schema.add_field("sparse_embedding", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("text", DataType.VARCHAR, max_length=4000)
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
        rows = [
            row for row in self.load()
            if int(row.get("chunk_level", 0) or 0) == leaf_level
        ]
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
            combined = self._rrf_merge(dense_ranked, sparse_ranked, top_k)
            return combined, "hybrid_local"

        for index, item in enumerate(dense_ranked[:top_k], start=1):
            item["rrf_rank"] = index
        return dense_ranked[:top_k], "dense_local_fallback"

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


class RetrievalEngine:
    def __init__(self, settings: RetrievalServiceSettings | None = None):
        self.settings = settings or load_settings()
        self.lexicon = SparseLexiconStore(self.settings.sparse_lexicon_path)
        self.parent_store = ParentChunkStore(self.settings.parent_chunk_store_path)
        self.local_store = LocalHybridStore(self.settings.local_index_path)
        self.embedding_client = OpenAICompatibleClient(
            base_url=self.settings.embedding_base_url,
            api_key=self.settings.embedding_api_key,
        )
        self.case_qa = ChromaCaseQAStore(
            ChromaCaseQASettings(
                db_path=self.settings.chroma_case_db_path,
                mirror_path=self.settings.chroma_case_mirror_path,
                collection_prefix=self.settings.chroma_case_collection_prefix,
            )
        )
        self.rewrite_client = OpenAICompatibleClient(
            base_url=self.settings.rewrite_base_url,
            api_key=self.settings.rewrite_api_key,
        )
        self.milvus = MilvusHybridStore(self.settings)

    def health(self) -> dict[str, Any]:
        milvus_health = self.milvus.health()
        local_health = self.local_store.health()
        milvus_collection_exists = bool(milvus_health.get("collection_exists"))
        local_index_available = bool(local_health.get("local_index_available"))
        hybrid_enabled = self.embedding_client.is_ready() and self.lexicon.is_ready() and (milvus_collection_exists or local_index_available)
        return {
            "status": "ok",
            "vector_store": "milvus" if milvus_collection_exists else "local_hybrid_index",
            "hybrid_enabled": hybrid_enabled,
            "embedding_configured": self.embedding_client.is_ready(),
            "rewrite_configured": self.rewrite_client.is_ready(),
            "sparse_lexicon_loaded": self.lexicon.is_ready(),
            **self.case_qa.health(),
            **milvus_health,
            **local_health,
        }

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if not self.embedding_client.is_ready():
            return {
                "backend": "case-qa",
                "retrieval_mode": "unconfigured",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["embedding_client_not_configured"],
            }

        dense_vector = self.embedding_client.embed([query], self.settings.embedding_model)[0]
        data = self.case_qa.search(
            query=query,
            query_embedding=dense_vector,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        warnings.extend(data.get("warnings", []))
        chunks = [self._normalize_case_chunk(item) for item in data.get("chunks", []) if isinstance(item, dict)]

        return {
            "backend": "case-qa",
            "retrieval_mode": data.get("retrieval_mode", "case_qa"),
            "candidate_k": candidate_k,
            "collection_count": data.get("collection_count", 0),
            "per_collection_k": data.get("per_collection_k"),
            "chunks": chunks,
            "total": len(chunks),
            "warnings": warnings,
        }

    def search_hybrid(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
        enable_rerank: bool,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if not self.embedding_client.is_ready():
            return {
                "backend": "supermew_hybrid",
                "retrieval_mode": "unconfigured",
                "rerank_applied": False,
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["embedding_client_not_configured"],
            }

        dense_vector = self.embedding_client.embed([query], self.settings.embedding_model)[0]
        sparse_vector = self.lexicon.encode_query(query)
        retrieval_mode = "hybrid"

        try:
            if self.milvus.has_collection():
                if sparse_vector and self.lexicon.is_ready():
                    docs = self.milvus.hybrid_search(
                        dense_embedding=dense_vector,
                        sparse_embedding=sparse_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=self.settings.leaf_retrieve_level,
                    )
                else:
                    retrieval_mode = "dense_fallback"
                    docs = self.milvus.dense_search(
                        dense_embedding=dense_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=self.settings.leaf_retrieve_level,
                    )
                    if not sparse_vector:
                        warnings.append("sparse_lexicon_missing_or_query_terms_unseen")
            else:
                docs, retrieval_mode = self.local_store.search(
                    dense_embedding=dense_vector,
                    sparse_embedding=sparse_vector,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=self.settings.leaf_retrieve_level,
                )
                if retrieval_mode == "dense_local_fallback" and not sparse_vector:
                    warnings.append("sparse_lexicon_missing_or_query_terms_unseen")
        except Exception as exc:
            warnings.append(str(exc))
            docs = []

        reranked_docs = docs
        rerank_applied = False
        rerank_error = None
        if enable_rerank and self.settings.rerank_endpoint and self.settings.rerank_model and self.settings.rerank_api_key and docs:
            reranked_docs, rerank_applied, rerank_error = self._rerank(query, docs, top_k)
            if rerank_error:
                warnings.append(rerank_error)
        else:
            reranked_docs = docs[:top_k]

        merged_docs, merge_meta = self._auto_merge(reranked_docs, top_k)
        normalized = [self._normalize_chunk(item) for item in merged_docs[:top_k]]

        return {
            "backend": "supermew_hybrid",
            "retrieval_mode": retrieval_mode,
            "rerank_applied": rerank_applied,
            "rerank_model": self.settings.rerank_model or None,
            "rerank_endpoint": self.settings.rerank_endpoint or None,
            "rerank_error": rerank_error,
            "candidate_k": max(candidate_k, top_k),
            "leaf_retrieve_level": self.settings.leaf_retrieve_level,
            "auto_merge_enabled": merge_meta["auto_merge_enabled"],
            "auto_merge_applied": merge_meta["auto_merge_applied"],
            "auto_merge_threshold": merge_meta["auto_merge_threshold"],
            "auto_merge_replaced_chunks": merge_meta["auto_merge_replaced_chunks"],
            "auto_merge_steps": merge_meta["auto_merge_steps"],
            "chunks": normalized,
            "total": len(normalized),
            "warnings": warnings,
        }

    def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
        strategy = (strategy or "complex").strip().lower()
        expanded_query = f"{query}。请结合证候、治法、方剂出处与原文进行检索。"
        step_back_question = f"{query} 背后的中医辨证与治法原则是什么？" if strategy in {"step_back", "complex"} else ""
        step_back_answer = ""
        hypothetical_doc = ""

        if step_back_question and self.rewrite_client.is_ready():
            prompt = f"请用不超过120字回答：{step_back_question}"
            step_back_answer = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
        elif step_back_question:
            step_back_answer = "先辨证后论治，结合症状、证候、治法与方剂来源综合判断。"

        if strategy in {"hyde", "complex"}:
            if self.rewrite_client.is_ready():
                prompt = f"请生成一段用于检索的假设性资料片段：{query}"
                hypothetical_doc = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
            else:
                hypothetical_doc = f"{query} 可从证候识别、治法匹配、方剂来源、古籍原文四个维度组织答案。"

        if step_back_question and step_back_answer:
            expanded_query = f"{expanded_query}\n退步问题：{step_back_question}\n退步问题答案：{step_back_answer}"

        return {
            "strategy": strategy,
            "expanded_query": expanded_query,
            "step_back_question": step_back_question,
            "step_back_answer": step_back_answer,
            "hypothetical_doc": hypothetical_doc,
        }

    def index_documents(self, docs: list[dict[str, Any]], *, reset_collection: bool = False) -> dict[str, Any]:
        parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) < self.settings.leaf_retrieve_level]
        leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == self.settings.leaf_retrieve_level]
        if not leaf_docs:
            raise ValueError("no_leaf_chunks_to_index")
        if not self.embedding_client.is_ready():
            raise RuntimeError("embedding_client_not_configured")

        leaf_texts = [str(doc.get("text", "")) for doc in leaf_docs]
        self.lexicon.fit(leaf_texts)
        sparse_vectors = [self.lexicon.encode_document(text) for text in leaf_texts]
        self.lexicon.save()

        dense_vectors = self.embedding_client.embed(leaf_texts, self.settings.embedding_model)
        dense_dim = len(dense_vectors[0]) if dense_vectors else self.settings.dense_dim
        if reset_collection:
            try:
                self.milvus.reset_collection()
            except Exception:
                pass
            self.local_store.reset()

        rows = []
        for doc, dense_embedding, sparse_embedding in zip(leaf_docs, dense_vectors, sparse_vectors):
            rows.append(
                {
                    "dense_embedding": dense_embedding,
                    "sparse_embedding": sparse_embedding,
                    "text": doc.get("text", ""),
                    "filename": doc.get("filename", ""),
                    "file_type": doc.get("file_type", "TXT"),
                    "file_path": doc.get("file_path", ""),
                    "page_number": int(doc.get("page_number", 0) or 0),
                    "chunk_idx": int(doc.get("chunk_idx", 0) or 0),
                    "chunk_id": doc.get("chunk_id", ""),
                    "parent_chunk_id": doc.get("parent_chunk_id", ""),
                    "root_chunk_id": doc.get("root_chunk_id", ""),
                    "chunk_level": int(doc.get("chunk_level", self.settings.leaf_retrieve_level) or self.settings.leaf_retrieve_level),
                }
            )
        inserted_to = "local_hybrid_index"
        try:
            self.milvus.ensure_collection(dense_dim=dense_dim)
            self.milvus.insert(rows)
            inserted_to = "milvus"
        except Exception:
            self.local_store.save(rows)
        self.parent_store.upsert_documents(parent_docs)
        return {
            "indexed_leaf_chunks": len(leaf_docs),
            "indexed_parent_chunks": len(parent_docs),
            "collection": self.settings.milvus_collection,
            "dense_dim": dense_dim,
            "vector_store": inserted_to,
        }

    def index_sample_corpus(self, *, reset_collection: bool = False) -> dict[str, Any]:
        docs = json.loads(self.settings.sample_corpus_path.read_text(encoding="utf-8-sig"))
        if not isinstance(docs, list):
            raise ValueError("invalid_sample_corpus")
        return self.index_documents(docs, reset_collection=reset_collection)

    @staticmethod
    def _normalize_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": item.get("chunk_id", ""),
            "embedding_id": item.get("embedding_id", ""),
            "collection": item.get("collection", ""),
            "text": str(item.get("text", "")).strip(),
            "document": str(item.get("document", "")).strip(),
            "answer": str(item.get("answer", "")).strip(),
            "source_file": item.get("source_file", "caseqa"),
            "source_page": item.get("source_page"),
            "score": float(item.get("score", 0.0) or 0.0),
            "distance": float(item.get("distance", 0.0) or 0.0),
            "rerank_score": float(item.get("rerank_score", 0.0) or 0.0),
            "metadata": item.get("metadata", {}),
        }

    def _auto_merge(self, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        meta = {
            "auto_merge_enabled": self.settings.auto_merge_enabled,
            "auto_merge_applied": False,
            "auto_merge_threshold": self.settings.auto_merge_threshold,
            "auto_merge_replaced_chunks": 0,
            "auto_merge_steps": 0,
        }
        if not self.settings.auto_merge_enabled or not docs:
            return docs[:top_k], meta

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for doc in docs:
            parent_id = str(doc.get("parent_chunk_id", "")).strip()
            if parent_id:
                groups[parent_id].append(doc)

        target_parent_ids = [
            parent_id for parent_id, children in groups.items()
            if len(children) >= self.settings.auto_merge_threshold
        ]
        if not target_parent_ids:
            return docs[:top_k], meta

        parent_map = {
            item.get("chunk_id", ""): item
            for item in self.parent_store.get_documents_by_ids(target_parent_ids)
            if item.get("chunk_id")
        }
        merged_docs: list[dict[str, Any]] = []
        replaced_count = 0
        for doc in docs:
            parent_id = str(doc.get("parent_chunk_id", "")).strip()
            if not parent_id or parent_id not in parent_map:
                merged_docs.append(doc)
                continue
            parent_doc = dict(parent_map[parent_id])
            parent_doc["score"] = max(float(parent_doc.get("score", 0.0)), float(doc.get("score", 0.0)))
            parent_doc["merged_from_children"] = True
            parent_doc["merged_child_count"] = len(groups[parent_id])
            merged_docs.append(parent_doc)
            replaced_count += 1

        deduped: list[dict[str, Any]] = []
        seen = set()
        for item in merged_docs:
            key = item.get("chunk_id") or (item.get("filename"), item.get("page_number"), item.get("text"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        deduped.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        meta.update(
            {
                "auto_merge_applied": replaced_count > 0,
                "auto_merge_replaced_chunks": replaced_count,
                "auto_merge_steps": 1 if replaced_count > 0 else 0,
            }
        )
        return deduped[:top_k], meta

    def _rerank(self, query: str, docs: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], bool, str | None]:
        payload = {
            "model": self.settings.rerank_model,
            "query": query,
            "documents": [doc.get("text", "") for doc in docs],
            "top_n": min(top_k, len(docs)),
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.rerank_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(self.settings.rerank_endpoint, headers=headers, json=payload, timeout=15.0)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            reranked: list[dict[str, Any]] = []
            for item in results:
                index = item.get("index")
                if isinstance(index, int) and 0 <= index < len(docs):
                    doc = dict(docs[index])
                    if item.get("relevance_score") is not None:
                        doc["rerank_score"] = float(item["relevance_score"])
                    reranked.append(doc)
            return (reranked or docs[:top_k], True, None if reranked else "empty_rerank_results")
        except Exception as exc:
            return docs[:top_k], False, str(exc)

    @staticmethod
    def _normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": item.get("chunk_id", ""),
            "text": item.get("text", ""),
            "score": float(item.get("score", 0.0) or 0.0),
            "source_file": item.get("filename", ""),
            "source_page": item.get("page_number", 0),
            "filename": item.get("filename", ""),
            "page_number": item.get("page_number", 0),
            "file_type": item.get("file_type", ""),
            "chunk_idx": item.get("chunk_idx", 0),
            "chunk_level": item.get("chunk_level", 0),
            "parent_chunk_id": item.get("parent_chunk_id", ""),
            "root_chunk_id": item.get("root_chunk_id", ""),
            "rrf_rank": item.get("rrf_rank"),
            "rerank_score": item.get("rerank_score"),
        }

_retrieval_engine: RetrievalEngine | None = None


def get_retrieval_engine() -> RetrievalEngine:
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine
