from __future__ import annotations

import json
import math
import os
import re
import socket
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from router.tcm_intent_classifier import analyze_tcm_query
from services.retrieval_service.chroma_case_store import ChromaCaseQASettings, ChromaCaseQAStore
from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings

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

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover - optional lexical enhancement only
    jieba = None


BOOK_LINE_PATTERN = re.compile(r"^古籍：(.+?)$", re.MULTILINE)
CHAPTER_LINE_PATTERN = re.compile(r"^篇名：(.+?)$", re.MULTILINE)
CLASSIC_PATH_PATTERN = re.compile(r"^classic://(?P<book>[^/]+)/(?P<section>\d{4})(?:-\d{2})?$")


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
    case_qa_embedding_model: str
    case_qa_embedding_dimensions: int
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
    embedding_batch_size: int
    chroma_case_db_path: Path
    chroma_case_mirror_path: Path
    chroma_case_collection_prefix: str
    case_qa_vector_fallback_enabled: bool
    structured_qa_index_path: Path
    structured_qa_input_path: Path
    structured_case_input_path: Path
    files_first_dense_fallback_enabled: bool
    sparse_lexicon_path: Path
    parent_chunk_store_path: Path
    local_index_path: Path
    sample_corpus_path: Path
    modern_corpus_path: Path
    classic_corpus_path: Path
    runtime_graph_db_path: Path


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
        case_qa_embedding_model=_first_env("CASE_QA_EMBEDDING_MODEL", "EMBEDDING_MODEL", "EMBEDDER", default="text-embedding-3-small"),
        case_qa_embedding_dimensions=int(_first_env("CASE_QA_EMBEDDING_DIM", default="1024")),
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
        embedding_batch_size=int(_first_env("RETRIEVAL_EMBED_BATCH_SIZE", default="64")),
        chroma_case_db_path=Path(_first_env("CHROMA_CASE_DB_PATH", default="E:/tcm_vector_db")),
        chroma_case_mirror_path=backend_dir / "storage" / "chroma_case_query_mirror",
        chroma_case_collection_prefix=_first_env("CHROMA_CASE_COLLECTION_PREFIX", default="tcm_shard_"),
        case_qa_vector_fallback_enabled=_first_env("CASE_QA_VECTOR_FALLBACK_ENABLED", default="false").lower() == "true",
        structured_qa_index_path=backend_dir / "storage" / "qa_structured_index.sqlite",
        structured_qa_input_path=backend_dir / "services" / "retrieval_service" / "data" / "case_qa_clean" / "qa_fts_ready.jsonl",
        structured_case_input_path=backend_dir / "services" / "retrieval_service" / "data" / "case_qa_clean" / "case_fts_ready.jsonl",
        files_first_dense_fallback_enabled=_first_env("FILES_FIRST_DENSE_FALLBACK_ENABLED", default="false").lower() == "true",
        sparse_lexicon_path=backend_dir / "storage" / "retrieval_sparse_lexicon.json",
        parent_chunk_store_path=backend_dir / "storage" / "retrieval_parent_chunks.json",
        local_index_path=backend_dir / "storage" / "retrieval_local_index.json",
        sample_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "sample_corpus.json",
        modern_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "herb2_modern_corpus.json",
        classic_corpus_path=backend_dir / "services" / "retrieval_service" / "data" / "classic_books_corpus.json",
        runtime_graph_db_path=backend_dir / "services" / "graph_service" / "data" / "graph_runtime.db",
    )


class SparseLexiconStore:
    def __init__(self, store_path: Path, *, runtime_graph_db_path: Path | None = None):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_graph_db_path = runtime_graph_db_path
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
        seen: set[str] = set()
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
        english_pattern = re.compile(r"[a-zA-Z]+")

        if jieba is not None and normalized:
            _prime_jieba_runtime_words(self.runtime_graph_db_path)
            for token in jieba.cut_for_search(normalized):
                cleaned = str(token or "").strip()
                if len(cleaned) >= 2 and cleaned not in seen:
                    seen.add(cleaned)
                    tokens.append(cleaned)

        idx = 0
        while idx < len(normalized):
            char = normalized[idx]
            if chinese_pattern.match(char):
                if char not in seen:
                    seen.add(char)
                    tokens.append(char)
                idx += 1
            elif english_pattern.match(char):
                match = english_pattern.match(normalized[idx:])
                if match:
                    token = match.group()
                    if token not in seen:
                        seen.add(token)
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


@lru_cache(maxsize=1)
def _runtime_entity_words(runtime_graph_db_path: Path | None) -> tuple[str, ...]:
    if runtime_graph_db_path is None or not runtime_graph_db_path.exists():
        return ()
    try:
        with sqlite3.connect(str(runtime_graph_db_path)) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM entities
                WHERE length(name) BETWEEN 2 AND 24
                ORDER BY length(name) DESC, name ASC
                """
            ).fetchall()
    except sqlite3.Error:
        return ()
    words: list[str] = []
    for row in rows:
        name = str(row[0] or "").strip().lower()
        if not name:
            continue
        words.append(name)
    return tuple(dict.fromkeys(words))


@lru_cache(maxsize=1)
def _prime_jieba_runtime_words(runtime_graph_db_path: Path | None) -> bool:
    if jieba is None:
        return False
    for word in _runtime_entity_words(runtime_graph_db_path):
        if len(word) >= 2:
            jieba.add_word(word, freq=200000)
    return True


def _extract_book_name(*, text: str, filename: str, file_path: str) -> str:
    match = BOOK_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    if file_path.startswith("classic://"):
        return file_path.removeprefix("classic://").split("/", 1)[0].strip()
    stem = Path(filename or "").stem.strip()
    return re.sub(r"^\d+\s*[-_－—]\s*", "", stem).strip() or stem


def _extract_chapter_title(*, text: str, page_number: int | None, file_path: str) -> str:
    match = CHAPTER_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return classic_match.group("section")
    if page_number not in (None, 0):
        return f"{int(page_number):04d}"
    return ""


def _build_section_key(*, book_name: str, chapter_title: str, page_number: int | None, file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"{classic_match.group('book')}::{classic_match.group('section')}"
    if book_name and chapter_title:
        return f"{book_name}::{chapter_title}"
    if book_name and page_number not in (None, 0):
        return f"{book_name}::{int(page_number):04d}"
    return ""


def _strip_classic_headers(text: str) -> str:
    lines = [str(line or "").rstrip() for line in str(text or "").splitlines()]
    stripped: list[str] = []
    for line in lines:
        if line.startswith("古籍：") or line.startswith("篇名："):
            continue
        stripped.append(line)
    return "\n".join(stripped).strip()


def _merge_section_bodies(parts: list[str]) -> str:
    merged = ""
    for raw_part in parts:
        part = str(raw_part or "").strip()
        if not part:
            continue
        if not merged:
            merged = part
            continue
        overlap_limit = min(len(merged), len(part), 400)
        overlap_size = 0
        for size in range(overlap_limit, 24, -1):
            if merged.endswith(part[:size]):
                overlap_size = size
                break
        merged += part[overlap_size:]
    return merged.strip()


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

    def embed(self, texts: list[str], model: str, *, dimensions: int | None = None) -> list[list[float]]:
        if not self.is_ready():
            raise RuntimeError("embedding_client_not_configured")
        last_error: Exception | None = None
        for _ in range(3):
            try:
                payload: dict[str, Any] = {"model": model, "input": texts, "encoding_format": "float"}
                if dimensions and dimensions > 0:
                    payload["dimensions"] = int(dimensions)
                with httpx.Client(timeout=20.0) as client:
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

    def search_sparse(
        self,
        *,
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


class LocalFilesFirstStore:
    def __init__(self, store_path: Path, *, tokenizer: SparseLexiconStore):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer

    def health(self) -> dict[str, Any]:
        available = False
        docs = 0
        if self.store_path.exists():
            try:
                with closing(sqlite3.connect(self.store_path)) as conn:
                    docs = int(conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0])
                    available = docs > 0
            except Exception:
                available = False
                docs = 0
        return {
            "files_first_index_available": available,
            "files_first_index_path": str(self.store_path),
            "files_first_index_docs": docs,
        }

    def reset(self) -> None:
        if self.store_path.exists():
            self.store_path.unlink()

    def rebuild(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        self.reset()
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                "CREATE TABLE docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT)"
            )
            conn.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path)"
            )
            payload_rows: list[tuple[Any, ...]] = []
            fts_rows: list[tuple[str, str, str, str, str, str, str]] = []
            for row in rows:
                chunk_id = str(row.get("chunk_id", "")).strip()
                if not chunk_id:
                    continue
                text = str(row.get("text", ""))
                filename = str(row.get("filename", ""))
                file_path = str(row.get("file_path", ""))
                page_number = int(row.get("page_number", 0) or 0)
                book_name = str(row.get("book_name", "")).strip() or _extract_book_name(
                    text=text,
                    filename=filename,
                    file_path=file_path,
                )
                chapter_title = str(row.get("chapter_title", "")).strip() or _extract_chapter_title(
                    text=text,
                    page_number=page_number,
                    file_path=file_path,
                )
                section_key = str(row.get("section_key", "")).strip() or _build_section_key(
                    book_name=book_name,
                    chapter_title=chapter_title,
                    page_number=page_number,
                    file_path=file_path,
                )
                payload_rows.append(
                    (
                        chunk_id,
                        text,
                        filename,
                        str(row.get("file_type", "TXT")),
                        file_path,
                        page_number,
                        int(row.get("chunk_idx", 0) or 0),
                        str(row.get("parent_chunk_id", "")),
                        str(row.get("root_chunk_id", "")),
                        int(row.get("chunk_level", 0) or 0),
                        book_name,
                        chapter_title,
                        section_key,
                    )
                )
                search_basis = " ".join([book_name, chapter_title, filename, file_path, text])
                search_text = " ".join(self.tokenizer.tokenize(search_basis))
                fts_rows.append((chunk_id, search_text, book_name, chapter_title, text, filename, file_path))
            conn.executemany(
                "INSERT INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                payload_rows,
            )
            conn.executemany(
                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
                fts_rows,
            )
            conn.commit()
        return {"indexed_files_first_docs": len(fts_rows), "files_first_index_path": str(self.store_path)}

    def search(
        self,
        *,
        query: str,
        top_k: int,
        candidate_k: int,
        leaf_level: int,
    ) -> tuple[list[dict[str, Any]], str]:
        if not self.store_path.exists():
            return [], "fts_missing"
        tokenized_query = [token for token in self.tokenizer.tokenize(query) if str(token).strip()]
        terms = [token for token in tokenized_query if len(token) >= 2]
        if not terms:
            terms = [token for token in tokenized_query if len(token) == 1][:12]
        if not terms:
            return [], "fts_query_empty"
        match_query = " OR ".join(f'"{term.replace(chr(34), " ")}"' for term in terms[:12])
        if not match_query:
            return [], "fts_query_empty"
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT
                        d.chunk_id,
                        d.text,
                        d.filename,
                        d.file_type,
                        d.file_path,
                        d.page_number,
                        d.chunk_idx,
                        d.parent_chunk_id,
                        d.root_chunk_id,
                        d.chunk_level,
                        d.book_name,
                        d.chapter_title,
                        d.section_key,
                        snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                        bm25(docs_fts, 2.5, 3.4, 2.6, 1.0, 0.25, 0.2) AS rank_score
                    FROM docs_fts
                    JOIN docs d ON d.chunk_id = docs_fts.chunk_id
                    WHERE docs_fts MATCH ? AND d.chunk_level = ?
                    ORDER BY rank_score
                    LIMIT ?
                    """,
                    (match_query, leaf_level, max(candidate_k, top_k)),
                ).fetchall()
            except sqlite3.OperationalError:
                return [], "fts_query_error"
        results: list[dict[str, Any]] = []
        for index, row in enumerate(rows[:top_k], start=1):
            results.append(
                {
                    "chunk_id": row["chunk_id"],
                    "text": row["text"],
                    "filename": row["filename"],
                    "file_type": row["file_type"],
                    "file_path": row["file_path"],
                    "page_number": row["page_number"],
                    "chunk_idx": row["chunk_idx"],
                    "parent_chunk_id": row["parent_chunk_id"],
                    "root_chunk_id": row["root_chunk_id"],
                    "chunk_level": row["chunk_level"],
                    "book_name": row["book_name"],
                    "chapter_title": row["chapter_title"],
                    "section_key": row["section_key"],
                    "match_snippet": row["match_snippet"],
                    "score": float(-row["rank_score"]),
                    "rrf_rank": index,
                }
            )
        return results, "fts_local"

    def read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"path": path, "items": [], "count": 0, "status": "missing"}
        normalized = str(path or "").strip()
        if not normalized.startswith("chapter://"):
            return {"path": normalized, "items": [], "count": 0, "status": "unsupported"}
        body = normalized.removeprefix("chapter://")
        book_name, _, chapter_title = body.partition("/")
        book_name = book_name.strip()
        chapter_title = chapter_title.strip()
        if not book_name or not chapter_title:
            return {"path": normalized, "items": [], "count": 0, "status": "invalid"}

        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    chunk_id,
                    text,
                    filename,
                    file_type,
                    file_path,
                    page_number,
                    chunk_idx,
                    parent_chunk_id,
                    root_chunk_id,
                    chunk_level,
                    book_name,
                    chapter_title,
                    section_key
                FROM docs
                WHERE book_name = ? AND chapter_title = ?
                ORDER BY chunk_level ASC, chunk_idx ASC, page_number ASC
                LIMIT ?
                """,
                (book_name, chapter_title, max(top_k, 64)),
            ).fetchall()
        items = [dict(row) for row in rows]
        if not items:
            return {"path": normalized, "items": [], "count": 0, "status": "empty"}
        return {
            "path": normalized,
            "status": "ok",
            "count": len(items),
            "items": items,
        }


class RetrievalEngine:
    def __init__(self, settings: RetrievalServiceSettings | None = None):
        self.settings = settings or load_settings()
        self.lexicon = SparseLexiconStore(
            self.settings.sparse_lexicon_path,
            runtime_graph_db_path=self.settings.runtime_graph_db_path,
        )
        self.parent_store = ParentChunkStore(self.settings.parent_chunk_store_path)
        self.local_store = LocalHybridStore(self.settings.local_index_path)
        self.files_first_store = LocalFilesFirstStore(
            self.settings.local_index_path.with_suffix(".fts.db"),
            tokenizer=self.lexicon,
        )
        self.embedding_client = OpenAICompatibleClient(
            base_url=self.settings.embedding_base_url,
            api_key=self.settings.embedding_api_key,
        )
        self.structured_qa = StructuredQAIndex(
            StructuredQAIndexSettings(
                index_path=self.settings.structured_qa_index_path,
                qa_input_path=self.settings.structured_qa_input_path,
                case_input_path=self.settings.structured_case_input_path,
            )
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
        files_first_health = self.files_first_store.health()
        structured_qa_health = self.structured_qa.health()
        milvus_collection_exists = bool(milvus_health.get("collection_exists"))
        local_index_available = bool(local_health.get("local_index_available"))
        files_first_index_available = bool(files_first_health.get("files_first_index_available"))
        hybrid_enabled = self.embedding_client.is_ready() and self.lexicon.is_ready() and (milvus_collection_exists or local_index_available)
        return {
            "status": "ok",
            "vector_store": "milvus" if milvus_collection_exists else "local_hybrid_index",
            "hybrid_enabled": hybrid_enabled,
            "files_first_enabled": self.lexicon.is_ready() and files_first_index_available,
            "embedding_configured": self.embedding_client.is_ready(),
            "rewrite_configured": self.rewrite_client.is_ready(),
            "sparse_lexicon_loaded": self.lexicon.is_ready(),
            "modern_corpus_available": self.settings.modern_corpus_path.exists(),
            "modern_corpus_path": str(self.settings.modern_corpus_path),
            "classic_corpus_available": self.settings.classic_corpus_path.exists(),
            "classic_corpus_path": str(self.settings.classic_corpus_path),
            "structured_qa_enabled": bool(structured_qa_health.get("available")),
            "case_qa_vector_fallback_enabled": self.settings.case_qa_vector_fallback_enabled,
            "files_first_dense_fallback_enabled": self.settings.files_first_dense_fallback_enabled,
            "runtime_entity_lexicon_loaded": bool(_runtime_entity_words(self.settings.runtime_graph_db_path)),
            **structured_qa_health,
            **self.case_qa.health(),
            **milvus_health,
            **local_health,
            **files_first_health,
        }

    def search_case_qa(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        structured_rows = self.structured_qa.search_case(query, top_k=max(1, int(top_k)))
        if structured_rows:
            chunks = [self._normalize_structured_case_chunk(item) for item in structured_rows if isinstance(item, dict)]
            return {
                "backend": "case-qa",
                "retrieval_mode": "structured_case_qa",
                "candidate_k": candidate_k,
                "chunks": chunks,
                "total": len(chunks),
                "warnings": [],
            }

        warnings: list[str] = []
        if not self.settings.case_qa_vector_fallback_enabled:
            return {
                "backend": "case-qa",
                "retrieval_mode": "structured_case_qa_empty",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["structured_case_qa_empty", "case_qa_vector_fallback_disabled"],
            }
        if not self.embedding_client.is_ready():
            return {
                "backend": "case-qa",
                "retrieval_mode": "unconfigured",
                "candidate_k": candidate_k,
                "chunks": [],
                "total": 0,
                "warnings": ["embedding_client_not_configured"],
            }

        dense_vector = self.embedding_client.embed(
            [query],
            self.settings.case_qa_embedding_model,
            dimensions=self.settings.case_qa_embedding_dimensions,
        )[0]
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
            "embedding_model": self.settings.case_qa_embedding_model,
            "embedding_dimensions": self.settings.case_qa_embedding_dimensions,
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
        allowed_file_path_prefixes: list[str] | None = None,
        search_mode: str = "files_first",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        sparse_vector = self.lexicon.encode_query(query)
        search_mode = (search_mode or "hybrid").strip().lower()
        retrieval_mode = "hybrid"
        docs: list[dict[str, Any]] = []

        if search_mode == "files_first":
            try:
                docs, retrieval_mode = self.files_first_store.search(
                    query=query,
                    top_k=top_k,
                    candidate_k=max(candidate_k, top_k),
                    leaf_level=self.settings.leaf_retrieve_level,
                )
                if not docs and sparse_vector and self.milvus.has_collection():
                    docs = self.milvus.sparse_search(
                        sparse_embedding=sparse_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=self.settings.leaf_retrieve_level,
                    )
                    retrieval_mode = "sparse_milvus"
                elif not docs and sparse_vector:
                    docs, retrieval_mode = self.local_store.search_sparse(
                        sparse_embedding=sparse_vector,
                        top_k=top_k,
                        candidate_k=max(candidate_k, top_k),
                        leaf_level=self.settings.leaf_retrieve_level,
                    )
            except Exception as exc:
                warnings.append(str(exc))
                docs = []
                retrieval_mode = "files_first_error"

        if not docs:
            if search_mode == "files_first" and not sparse_vector:
                warnings.append("files_first_sparse_query_empty")
            if search_mode == "files_first" and not self.settings.files_first_dense_fallback_enabled:
                warnings.append("files_first_dense_fallback_disabled")
                return {
                    "backend": "supermew_hybrid",
                    "retrieval_mode": retrieval_mode if retrieval_mode != "hybrid" else "files_first_empty",
                    "rerank_applied": False,
                    "candidate_k": max(candidate_k, top_k),
                    "chunks": [],
                    "total": 0,
                    "warnings": warnings,
                }
            if not self.embedding_client.is_ready():
                return {
                    "backend": "supermew_hybrid",
                    "retrieval_mode": "unconfigured",
                    "rerank_applied": False,
                    "candidate_k": candidate_k,
                    "chunks": [],
                    "total": 0,
                    "warnings": ["embedding_client_not_configured", *warnings],
                }

            dense_vector = self.embedding_client.embed([query], self.settings.embedding_model)[0]
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
                        retrieval_mode = "hybrid" if search_mode != "files_first" else "files_first_dense_hybrid_fallback"
                    else:
                        retrieval_mode = "dense_fallback" if search_mode != "files_first" else "files_first_dense_fallback"
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
                    if search_mode == "files_first":
                        retrieval_mode = f"files_first_{retrieval_mode}"
                    if retrieval_mode.endswith("dense_local_fallback") and not sparse_vector:
                        warnings.append("sparse_lexicon_missing_or_query_terms_unseen")
            except Exception as exc:
                warnings.append(str(exc))
                docs = []

        docs = self._filter_docs_by_file_path_prefixes(docs, allowed_file_path_prefixes)
        if allowed_file_path_prefixes and not docs:
            warnings.append("source_prefix_filtered_all")

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
        normalized = self._apply_lexical_sanity_gate(query, normalized, warnings)

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

        dense_vectors = self._embed_texts_in_batches(leaf_texts)
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

    def index_documents_files_first(self, docs: list[dict[str, Any]], *, reset_collection: bool = False) -> dict[str, Any]:
        parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) < self.settings.leaf_retrieve_level]
        leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == self.settings.leaf_retrieve_level]
        if not leaf_docs:
            raise ValueError("no_leaf_chunks_to_index")

        leaf_texts = [str(doc.get("text", "")) for doc in leaf_docs]
        self.lexicon.fit(leaf_texts)
        self.lexicon.save()

        rows = []
        for doc in leaf_docs:
            rows.append(
                {
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
        if reset_collection:
            self.files_first_store.reset()
        files_first_meta = self.files_first_store.rebuild(rows)
        self.parent_store.upsert_documents(parent_docs)
        return {
            "indexed_leaf_chunks": len(leaf_docs),
            "indexed_parent_chunks": len(parent_docs),
            "vector_store": "files_first_fts",
            **files_first_meta,
        }

    def _embed_texts_in_batches(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = max(1, int(self.settings.embedding_batch_size or 64))
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(self.embedding_client.embed(batch, self.settings.embedding_model))
        return vectors

    @staticmethod
    def _load_corpus_file(path: Path) -> list[dict[str, Any]]:
        docs = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(docs, list):
            raise ValueError(f"invalid_corpus_file: {path}")
        return [item for item in docs if isinstance(item, dict)]

    @staticmethod
    def _dedupe_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for doc in docs:
            key = str(doc.get("chunk_id", "")).strip()
            if not key:
                key = "|".join(
                    [
                        str(doc.get("filename", "")).strip(),
                        str(doc.get("file_path", "")).strip(),
                        str(doc.get("page_number", "")).strip(),
                        str(doc.get("chunk_idx", "")).strip(),
                    ]
                )
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def index_corpus_files(self, corpus_paths: list[Path], *, reset_collection: bool = False, index_mode: str = "hybrid") -> dict[str, Any]:
        resolved_paths = [path for path in corpus_paths if path.exists()]
        if not resolved_paths:
            raise ValueError("no_corpus_files_found")
        combined_docs: list[dict[str, Any]] = []
        for path in resolved_paths:
            combined_docs.extend(self._load_corpus_file(path))
        docs = self._dedupe_docs(combined_docs)
        if (index_mode or "hybrid").strip().lower() == "files_first":
            result = self.index_documents_files_first(docs, reset_collection=reset_collection)
        else:
            result = self.index_documents(docs, reset_collection=reset_collection)
        result["corpus_files"] = [str(path) for path in resolved_paths]
        result["indexed_documents"] = len(docs)
        result["index_mode"] = (index_mode or "hybrid").strip().lower()
        return result

    def index_configured_corpora(
        self,
        *,
        reset_collection: bool = False,
        include_sample: bool = True,
        include_modern: bool = True,
        include_classic: bool = True,
        index_mode: str = "hybrid",
    ) -> dict[str, Any]:
        corpus_paths: list[Path] = []
        if include_sample and self.settings.sample_corpus_path.exists():
            corpus_paths.append(self.settings.sample_corpus_path)
        if include_modern and self.settings.modern_corpus_path.exists():
            corpus_paths.append(self.settings.modern_corpus_path)
        if include_classic and self.settings.classic_corpus_path.exists():
            corpus_paths.append(self.settings.classic_corpus_path)
        return self.index_corpus_files(corpus_paths, reset_collection=reset_collection, index_mode=index_mode)

    def index_sample_corpus(self, *, reset_collection: bool = False) -> dict[str, Any]:
        return self.index_corpus_files([self.settings.sample_corpus_path], reset_collection=reset_collection)

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

    @staticmethod
    def _normalize_structured_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
        record_id = str(item.get("record_id", "")).strip()
        collection = str(item.get("collection", "")).strip() or "qa_structured_case"
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        symptom_text = str(item.get("symptom_text", "")).strip()
        syndrome_text = str(item.get("syndrome_text", "")).strip()
        formula_text = str(item.get("formula_text", "")).strip()
        summary_parts = [question, symptom_text, syndrome_text, formula_text]
        document = "\n".join(part for part in summary_parts if part)
        return {
            "chunk_id": record_id,
            "embedding_id": str(item.get("embedding_id", "")).strip() or record_id,
            "collection": collection,
            "text": answer or question,
            "document": document,
            "answer": answer,
            "source_file": f"caseqa:{collection}",
            "source_page": None,
            "score": float(item.get("_rerank_score", 0.0) or 0.0),
            "distance": 0.0,
            "rerank_score": float(item.get("_rerank_score", 0.0) or 0.0),
            "metadata": {
                "record_id": record_id,
                "question": question,
                "answer": answer,
                "age": str(item.get("age", "")).strip(),
                "sex": str(item.get("sex", "")).strip(),
                "chief_complaint": str(item.get("chief_complaint", "")).strip(),
                "history": str(item.get("history", "")).strip(),
                "tongue": str(item.get("tongue", "")).strip(),
                "pulse": str(item.get("pulse", "")).strip(),
                "symptom_text": symptom_text,
                "syndrome_text": syndrome_text,
                "formula_text": formula_text,
            },
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
            if doc.get("match_snippet") and not parent_doc.get("match_snippet"):
                parent_doc["match_snippet"] = doc.get("match_snippet")
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

    def _apply_lexical_sanity_gate(
        self,
        query: str,
        docs: list[dict[str, Any]],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if not docs:
            return docs
        anchors = self._extract_query_anchors(query)
        if not anchors:
            return docs

        filtered = [item for item in docs if self._doc_matches_anchors(item, anchors)]
        if len(filtered) == len(docs):
            return docs
        if filtered:
            warnings.append(f"lexical_sanity_filtered:{len(docs)}->{len(filtered)}")
            return filtered
        warnings.append("lexical_sanity_filtered_all")
        return []

    @staticmethod
    def _doc_matches_anchors(item: dict[str, Any], anchors: list[str]) -> bool:
        haystacks = [
            str(item.get("text", "") or ""),
            str(item.get("source_file", "") or ""),
            str(item.get("filename", "") or ""),
        ]
        joined = "\n".join(part for part in haystacks if part).lower()
        for anchor in anchors:
            probe = anchor.lower()
            if probe and probe in joined:
                return True
        return False

    @staticmethod
    def _extract_query_anchors(query: str) -> list[str]:
        anchors: list[str] = []
        try:
            analysis = analyze_tcm_query(query)
            for item in analysis.matched_entities:
                if "source_book" in item.types:
                    continue
                name = str(item.name).strip()
                if len(name) >= 2:
                    anchors.append(name)
        except Exception:
            pass

        for match in re.finditer(r"[\u4e00-\u9fff]{2,10}(?:丸|散|汤|饮|膏|丹|颗粒|胶囊)", query):
            anchors.append(match.group(0))
        for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9\-]{1,14}\b", query):
            token = match.group(0)
            if len(token) >= 2:
                anchors.append(token)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in anchors:
            normalized = str(item).strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped

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

    def read_section(self, path: str, *, top_k: int = 12) -> dict[str, Any]:
        payload = self.files_first_store.read_section(path=path, top_k=top_k)
        raw_items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
        if not raw_items:
            return {
                "backend": "files-first",
                "path": path,
                "status": payload.get("status", "empty"),
                "items": [],
                "count": 0,
            }

        normalized_items = [self._normalize_chunk(item) for item in raw_items if isinstance(item, dict)]
        book_name = str(normalized_items[0].get("book_name", "") or "").strip()
        chapter_title = str(normalized_items[0].get("chapter_title", "") or "").strip()

        parent_candidates = [
            str(item.get("parent_chunk_id", "")).strip()
            for item in normalized_items
            if str(item.get("parent_chunk_id", "")).strip()
        ]
        section_text = ""
        if parent_candidates:
            parent_docs = self.parent_store.get_documents_by_ids(list(dict.fromkeys(parent_candidates)))
            if parent_docs:
                section_text = str(parent_docs[0].get("text", "") or "").strip()

        if not section_text:
            section_text = "\n".join(
                [
                    line
                    for line in [
                        f"古籍：{book_name}" if book_name else "",
                        f"篇名：{chapter_title}" if chapter_title else "",
                        _merge_section_bodies([_strip_classic_headers(item.get("text", "")) for item in normalized_items]),
                    ]
                    if line
                ]
            ).strip()

        return {
            "backend": "files-first",
            "path": path,
            "status": "ok",
            "count": len(normalized_items),
            "section": {
                "book_name": book_name,
                "chapter_title": chapter_title,
                "text": section_text,
                "source_file": normalized_items[0].get("source_file", ""),
                "page_number": normalized_items[0].get("page_number", 0),
            },
            "items": normalized_items,
        }

    @staticmethod
    def _normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
        text = str(item.get("text", "") or "")
        filename = str(item.get("filename", "") or item.get("source_file", "") or "")
        file_path = str(item.get("file_path", "") or "")
        page_number = item.get("page_number", item.get("source_page", 0))
        book_name = str(item.get("book_name", "") or "").strip() or _extract_book_name(
            text=text,
            filename=filename,
            file_path=file_path,
        )
        chapter_title = str(item.get("chapter_title", "") or "").strip() or _extract_chapter_title(
            text=text,
            page_number=int(page_number or 0),
            file_path=file_path,
        )
        return {
            "chunk_id": item.get("chunk_id", ""),
            "text": text,
            "score": float(item.get("score", 0.0) or 0.0),
            "source_file": filename,
            "source_page": page_number,
            "filename": filename,
            "file_path": file_path,
            "page_number": page_number,
            "file_type": item.get("file_type", ""),
            "chunk_idx": item.get("chunk_idx", 0),
            "chunk_level": item.get("chunk_level", 0),
            "parent_chunk_id": item.get("parent_chunk_id", ""),
            "root_chunk_id": item.get("root_chunk_id", ""),
            "book_name": book_name,
            "chapter_title": chapter_title,
            "section_key": item.get("section_key", ""),
            "match_snippet": item.get("match_snippet"),
            "rrf_rank": item.get("rrf_rank"),
            "rerank_score": item.get("rerank_score"),
        }

    @staticmethod
    def _filter_docs_by_file_path_prefixes(
        docs: list[dict[str, Any]],
        prefixes: list[str] | None,
    ) -> list[dict[str, Any]]:
        normalized = [str(item or "").strip() for item in (prefixes or []) if str(item or "").strip()]
        if not normalized:
            return docs
        filtered: list[dict[str, Any]] = []
        for item in docs:
            file_path = str(item.get("file_path", "") or "").strip()
            if any(file_path.startswith(prefix) for prefix in normalized):
                filtered.append(item)
        return filtered

_retrieval_engine: RetrievalEngine | None = None


def get_retrieval_engine() -> RetrievalEngine:
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine
