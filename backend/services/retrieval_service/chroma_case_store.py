from __future__ import annotations

import gc
import json
import math
import re
import sqlite3
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import depends on runtime environment
    import hnswlib
    import numpy as np
except Exception:  # pragma: no cover
    hnswlib = None
    np = None


CASE_STYLE_MARKERS = ("基本信息", "主诉", "现病史", "体格检查", "年龄", "性别", "舌", "脉")
QA_ANSWER_MARKERS = ("诊断", "证型", "方剂", "中药", "治疗", "治法")
MAX_HNSW_METADATA_BYTES = 64 * 1024 * 1024
HNSW_METADATA_JSON_NAME = "index_metadata.json"


@dataclass(frozen=True)
class ChromaCaseQASettings:
    db_path: Path
    mirror_path: Path
    collection_prefix: str = "tcm_shard_"
    max_collections: int = 32
    query_workers: int = 3
    initial_shard_limit: int = 4
    max_loaded_collections: int = 2
    batch_load_target_bytes: int = 2_200_000_000


@dataclass(frozen=True)
class _CollectionDescriptor:
    name: str
    collection_id: str
    vector_segment_id: str
    metadata_segment_id: str
    dimension: int
    vector_dir: Path
    estimated_elements: int = 0
    estimated_bytes: int = 0


class _NativeHnswCollection:
    def __init__(self, descriptor: _CollectionDescriptor):
        self.descriptor = descriptor
        self._lock = threading.Lock()
        self._index = None
        self._label_to_id: dict[int, str] | None = None
        self._count = int(descriptor.estimated_elements or 0)
        self._last_access_tick = 0

    def query(self, *, db_path: Path, query: str, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if self._index is None or not self._label_to_id:
            return []

        if len(query_embedding) != self.descriptor.dimension:
            raise ValueError(
                f"embedding_dimension_mismatch:{self.descriptor.name}:{len(query_embedding)}!={self.descriptor.dimension}"
            )

        k = min(max(1, int(top_k)), self._count)
        if k <= 0:
            return []

        index = self._index
        index.set_ef(min(max(k * 10, 64), 256))
        labels, distances = index.knn_query(np.array([query_embedding], dtype=np.float32), k=k)
        ordered_embedding_ids = [
            self._label_to_id.get(int(label), "")
            for label in labels[0].tolist()
            if self._label_to_id.get(int(label), "")
        ]
        metadata_map = _load_embedding_metadata(
            db_path / "chroma.sqlite3",
            self.descriptor.metadata_segment_id,
            ordered_embedding_ids,
        )
        rows: list[dict[str, Any]] = []
        for label, distance in zip(labels[0].tolist(), distances[0].tolist()):
            embedding_id = self._label_to_id.get(int(label), "")
            if not embedding_id:
                continue
            metadata = metadata_map.get(embedding_id, {})
            document = str(metadata.get("chroma:document", "")).strip()
            answer = str(metadata.get("answer", "")).strip()
            if not _looks_like_qa_record(document, answer):
                continue
            raw_distance = float(distance)
            similarity_score = 1.0 / (1.0 + max(raw_distance, 0.0))
            rerank_score = similarity_score
            rerank_score += _query_overlap_bonus(query, document, answer)
            rerank_score += _answer_quality_bonus(answer)
            rerank_score += 0.08 if _is_case_style_text(query) and _is_case_style_text(document + " " + answer) else 0.0
            rerank_score += 0.05 if any(marker in answer for marker in QA_ANSWER_MARKERS) else 0.0
            rows.append(
                {
                    "chunk_id": embedding_id,
                    "embedding_id": embedding_id,
                    "collection": self.descriptor.name,
                    "document": document,
                    "answer": answer,
                    "text": answer or document,
                    "source_file": f"caseqa:{self.descriptor.name}",
                    "source_page": None,
                    "distance": raw_distance,
                    "score": round(similarity_score, 6),
                    "rerank_score": round(rerank_score, 6),
                    "metadata": metadata,
                }
            )
        return rows

    def _ensure_loaded(self) -> None:
        if self._index is not None and self._label_to_id is not None:
            return
        with self._lock:
            if self._index is not None and self._label_to_id is not None:
                return
            payload = _load_hnsw_metadata(self.descriptor.vector_dir)
            label_to_id = {int(key): str(value) for key, value in dict(payload.get("label_to_id", {})).items()}
            index_count = max(
                int(payload.get("total_elements_added", 0) or 0),
                len(label_to_id),
            )
            index = hnswlib.Index(space="l2", dim=self.descriptor.dimension)
            index.load_index(
                str(self.descriptor.vector_dir),
                is_persistent_index=True,
                max_elements=max(index_count, 1000),
            )
            index.set_num_threads(1)
            self._index = index
            self._label_to_id = label_to_id
            self._count = len(label_to_id)

    def is_loaded(self) -> bool:
        return self._index is not None and self._label_to_id is not None

    def touch(self, access_tick: int) -> None:
        self._last_access_tick = int(access_tick)

    def release(self) -> None:
        with self._lock:
            self._index = None
            self._label_to_id = None
        gc.collect()


class ChromaCaseQAStore:
    def __init__(self, settings: ChromaCaseQASettings):
        self.settings = settings
        self._descriptors: list[_CollectionDescriptor] | None = None
        self._collections: dict[str, _NativeHnswCollection] = {}
        self._state_lock = threading.Lock()
        self._access_tick = 0

    def is_configured(self) -> bool:
        return self.settings.db_path.exists() and (self.settings.db_path / "chroma.sqlite3").exists()

    def is_available(self) -> bool:
        return self.is_configured() and hnswlib is not None and np is not None

    def health(self) -> dict[str, Any]:
        configured = self.is_configured()
        descriptors = self.discover_collections() if configured else []
        return {
            "case_qa_configured": configured,
            "case_qa_client_available": self.is_available(),
            "case_qa_backend": "native_hnsw_sqlite",
            "case_qa_db_path": str(self.settings.db_path),
            "case_qa_mirror_path": str(self.settings.mirror_path),
            "case_qa_collection_prefix": self.settings.collection_prefix,
            "case_qa_query_workers": self.settings.query_workers,
            "case_qa_initial_shard_limit": self.settings.initial_shard_limit,
            "case_qa_max_loaded_collections": self.settings.max_loaded_collections,
            "case_qa_collection_count": len(descriptors),
            "case_qa_collections": [item.name for item in descriptors[:10]],
        }

    def discover_collections(self) -> list[_CollectionDescriptor]:
        if self._descriptors is not None:
            return list(self._descriptors)

        sqlite_path = self.settings.db_path / "chroma.sqlite3"
        if not sqlite_path.exists():
            self._descriptors = []
            return []

        conn = _open_sqlite_readonly(sqlite_path)
        try:
            rows = conn.execute(
                """
                SELECT
                    c.name,
                    c.id,
                    COALESCE(c.dimension, 1024) AS dimension,
                    MAX(CASE WHEN s.scope = 'VECTOR' THEN s.id END) AS vector_segment_id,
                    MAX(CASE WHEN s.scope = 'METADATA' THEN s.id END) AS metadata_segment_id
                FROM collections c
                JOIN segments s ON s.collection = c.id
                WHERE c.name LIKE ?
                GROUP BY c.name, c.id, c.dimension
                ORDER BY c.name
                LIMIT ?
                """,
                (f"{self.settings.collection_prefix}%", self.settings.max_collections),
            ).fetchall()
        finally:
            conn.close()

        descriptors: list[_CollectionDescriptor] = []
        for row in rows:
            name, collection_id, dimension, vector_segment_id, metadata_segment_id = row
            vector_dir = self.settings.db_path / str(vector_segment_id)
            if not vector_segment_id or not metadata_segment_id or not vector_dir.exists():
                continue
            estimated_elements, estimated_bytes = _read_vector_index_summary(vector_dir)
            descriptors.append(
                _CollectionDescriptor(
                    name=str(name),
                    collection_id=str(collection_id),
                    vector_segment_id=str(vector_segment_id),
                    metadata_segment_id=str(metadata_segment_id),
                    dimension=int(dimension or 1024),
                    vector_dir=vector_dir,
                    estimated_elements=estimated_elements,
                    estimated_bytes=estimated_bytes,
                )
            )

        self._descriptors = descriptors
        return list(self._descriptors)

    def search(
        self,
        *,
        query: str,
        query_embedding: list[float],
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "retrieval_mode": "case_qa_unconfigured",
                "chunks": [],
                "total": 0,
                "warnings": ["case_qa_db_not_configured"],
            }
        if hnswlib is None or np is None:
            return {
                "retrieval_mode": "case_qa_missing_dependency",
                "chunks": [],
                "total": 0,
                "warnings": ["native_hnsw_dependencies_missing"],
            }

        descriptors = self.discover_collections()
        if not descriptors:
            return {
                "retrieval_mode": "case_qa_no_collections",
                "chunks": [],
                "total": 0,
                "warnings": ["case_qa_collections_missing"],
            }

        per_collection_k = max(2, min(candidate_k, math.ceil(candidate_k / max(1, len(descriptors))) + 1))
        warnings: list[str] = []
        candidates: list[dict[str, Any]] = []
        lexical_scores = self._lexical_probe_scores(query, descriptors)
        ordered_descriptors = self._order_descriptors_for_query(descriptors, lexical_scores)
        positive_lexical_count = sum(1 for descriptor in ordered_descriptors if lexical_scores.get(descriptor.metadata_segment_id, 0) > 0)
        initial_limit = min(
            len(ordered_descriptors),
            max(
                2,
                positive_lexical_count if positive_lexical_count else self.settings.initial_shard_limit,
            ),
        )
        staged_groups = [
            ordered_descriptors[:initial_limit],
            ordered_descriptors[initial_limit:],
        ]
        searched_collections: list[str] = []
        skipped_collections: list[str] = []

        for stage_index, stage_descriptors in enumerate(staged_groups):
            if not stage_descriptors:
                continue
            for wave in self._build_query_waves(stage_descriptors):
                wave_results, wave_warnings = self._execute_wave(
                    descriptors=wave,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=per_collection_k,
                )
                candidates.extend(wave_results)
                warnings.extend(wave_warnings)
                searched_collections.extend(item.name for item in wave)
                self._prune_loaded_collections(active_names={item.name for item in wave})

            if stage_index == 0:
                preview = _select_diverse_top_k(candidates, query=query, top_k=max(1, top_k))
                remaining = staged_groups[1]
                if self._should_stop_after_stage_one(
                    selected=preview,
                    candidate_count=len(candidates),
                    top_k=top_k,
                    remaining_descriptors=remaining,
                    lexical_scores=lexical_scores,
                ):
                    skipped_collections = [item.name for item in remaining]
                    break

        ranked = _select_diverse_top_k(candidates, query=query, top_k=max(1, top_k))
        return {
            "retrieval_mode": "native_hnsw_case_qa",
            "candidate_k": candidate_k,
            "per_collection_k": per_collection_k,
            "collection_count": len(descriptors),
            "searched_collections": searched_collections,
            "skipped_collections": skipped_collections,
            "chunks": ranked,
            "total": len(ranked),
            "warnings": warnings,
        }

    def _query_collection(
        self,
        *,
        descriptor: _CollectionDescriptor,
        query: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        collection = self._get_or_create_collection(descriptor)
        collection.touch(self._next_access_tick())
        return collection.query(
            db_path=self.settings.db_path,
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
        )

    def _get_or_create_collection(self, descriptor: _CollectionDescriptor) -> _NativeHnswCollection:
        with self._state_lock:
            collection = self._collections.get(descriptor.name)
            if collection is None:
                collection = _NativeHnswCollection(descriptor)
                self._collections[descriptor.name] = collection
            return collection

    def _next_access_tick(self) -> int:
        with self._state_lock:
            self._access_tick += 1
            return self._access_tick

    def _build_query_waves(self, descriptors: list[_CollectionDescriptor]) -> list[list[_CollectionDescriptor]]:
        if not descriptors:
            return []
        waves: list[list[_CollectionDescriptor]] = []
        current_wave: list[_CollectionDescriptor] = []
        current_bytes = 0
        max_workers = max(1, self.settings.query_workers)
        target_bytes = max(1, self.settings.batch_load_target_bytes)

        for descriptor in descriptors:
            collection = self._collections.get(descriptor.name)
            extra_bytes = 0 if (collection and collection.is_loaded()) else max(1, int(descriptor.estimated_bytes or 0))
            exceeds_worker_limit = len(current_wave) >= max_workers
            exceeds_byte_limit = bool(current_wave) and current_bytes + extra_bytes > target_bytes
            if exceeds_worker_limit or exceeds_byte_limit:
                waves.append(current_wave)
                current_wave = []
                current_bytes = 0
            current_wave.append(descriptor)
            current_bytes += extra_bytes

        if current_wave:
            waves.append(current_wave)
        return waves

    def _execute_wave(
        self,
        *,
        descriptors: list[_CollectionDescriptor],
        query: str,
        query_embedding: list[float],
        top_k: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if not descriptors:
            return [], []

        warnings: list[str] = []
        results: list[dict[str, Any]] = []
        retry_descriptors: list[_CollectionDescriptor] = []
        worker_count = min(max(1, self.settings.query_workers), len(descriptors))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self._query_collection,
                    descriptor=descriptor,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=top_k,
                ): descriptor
                for descriptor in descriptors
            }
            for future in as_completed(futures):
                descriptor = futures[future]
                try:
                    results.extend(future.result())
                except Exception as exc:  # pragma: no cover - runtime database dependent
                    message = str(exc)
                    if _is_memory_load_error(message):
                        retry_descriptors.append(descriptor)
                    else:
                        warnings.append(f"{descriptor.name}: {message}")

        if retry_descriptors:
            self._prune_loaded_collections(active_names=set(), force=True)
            for descriptor in retry_descriptors:
                try:
                    results.extend(
                        self._query_collection(
                            descriptor=descriptor,
                            query=query,
                            query_embedding=query_embedding,
                            top_k=top_k,
                        )
                    )
                except Exception as exc:  # pragma: no cover - runtime database dependent
                    warnings.append(f"{descriptor.name}: {exc}")
                finally:
                    self._prune_loaded_collections(active_names={descriptor.name})
        return results, warnings

    def _prune_loaded_collections(self, *, active_names: set[str], force: bool = False) -> None:
        if self.settings.max_loaded_collections <= 0:
            return
        with self._state_lock:
            loaded = [
                (name, collection)
                for name, collection in self._collections.items()
                if collection.is_loaded() and name not in active_names
            ]
            loaded.sort(key=lambda item: item[1]._last_access_tick)
            target = 0 if force else self.settings.max_loaded_collections - len(active_names)
            while len(loaded) > max(0, target):
                name, collection = loaded.pop(0)
                collection.release()

    def _lexical_probe_scores(
        self,
        query: str,
        descriptors: list[_CollectionDescriptor],
    ) -> dict[str, float]:
        terms = _extract_probe_terms(query)
        if not terms:
            return {}

        sqlite_path = self.settings.db_path / "chroma.sqlite3"
        conn = _open_sqlite_readonly(sqlite_path)
        try:
            match_expression = _build_fts5_match_expression(terms)
            if not match_expression:
                return {}
            rows = conn.execute(
                """
                SELECT
                    e.segment_id,
                    SUM(CASE WHEN em.key = 'chroma:document' THEN 2.0 ELSE 1.0 END) AS hit_score,
                    COUNT(DISTINCT e.embedding_id) AS hit_count
                FROM embedding_fulltext_search f
                JOIN embedding_metadata em ON em.rowid = f.rowid
                JOIN embeddings e ON e.id = em.id
                WHERE embedding_fulltext_search MATCH ?
                GROUP BY e.segment_id
                ORDER BY hit_score DESC, hit_count DESC
                """,
                (match_expression,),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()

        segment_scores = {
            str(segment_id): float(hit_score) + min(int(hit_count), 12) * 0.1
            for segment_id, hit_score, hit_count in rows
        }
        return segment_scores

    def _order_descriptors_for_query(
        self,
        descriptors: list[_CollectionDescriptor],
        lexical_scores: dict[str, float],
    ) -> list[_CollectionDescriptor]:
        def sort_key(descriptor: _CollectionDescriptor) -> tuple[float, int, int, str]:
            collection = self._collections.get(descriptor.name)
            is_loaded = 1 if (collection and collection.is_loaded()) else 0
            lexical = lexical_scores.get(descriptor.metadata_segment_id, 0.0)
            return (-lexical, -is_loaded, int(descriptor.estimated_bytes or 0), descriptor.name)

        return sorted(descriptors, key=sort_key)

    def _should_stop_after_stage_one(
        self,
        *,
        selected: list[dict[str, Any]],
        candidate_count: int,
        top_k: int,
        remaining_descriptors: list[_CollectionDescriptor],
        lexical_scores: dict[str, float],
    ) -> bool:
        if not remaining_descriptors:
            return True
        if len(selected) < max(1, top_k):
            return False
        if any(lexical_scores.get(item.metadata_segment_id, 0.0) > 0 for item in remaining_descriptors):
            return False
        if candidate_count < max(top_k * 2, top_k + 2):
            return False
        head = selected[: min(len(selected), max(1, min(top_k, 3)))]
        if not head:
            return False
        avg_score = sum(float(item.get("selection_score", item.get("rerank_score", 0.0))) for item in head) / len(head)
        return avg_score >= 0.7


def _open_sqlite_readonly(sqlite_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)


def _load_embedding_metadata(sqlite_path: Path, metadata_segment_id: str, embedding_ids: list[str]) -> dict[str, dict[str, str]]:
    if not embedding_ids:
        return {}
    conn = _open_sqlite_readonly(sqlite_path)
    try:
        placeholders = ",".join("?" for _ in embedding_ids)
        sql = f"""
            SELECT e.embedding_id, em.key, em.string_value
            FROM embeddings e
            JOIN embedding_metadata em ON em.id = e.id
            WHERE e.segment_id = ?
              AND e.embedding_id IN ({placeholders})
        """
        rows = conn.execute(sql, [metadata_segment_id, *embedding_ids]).fetchall()
    finally:
        conn.close()

    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for embedding_id, key, string_value in rows:
        grouped[str(embedding_id)][str(key)] = str(string_value or "")
    return dict(grouped)


def _read_vector_index_summary(vector_dir: Path) -> tuple[int, int]:
    estimated_elements = 0
    if (vector_dir / HNSW_METADATA_JSON_NAME).exists():
        try:
            payload = _load_hnsw_metadata(vector_dir)
            estimated_elements = max(
                int(payload.get("total_elements_added", 0) or 0),
                len(dict(payload.get("label_to_id", {}))),
            )
        except Exception:
            estimated_elements = 0

    estimated_bytes = 0
    for name in ("data_level0.bin", "link_lists.bin", "length.bin", "header.bin"):
        file_path = vector_dir / name
        if file_path.exists():
            estimated_bytes += int(file_path.stat().st_size)
    return estimated_elements, estimated_bytes


def _load_hnsw_metadata(vector_dir: Path) -> dict[str, Any]:
    metadata_path = vector_dir / HNSW_METADATA_JSON_NAME
    if metadata_path.exists():
        return _load_hnsw_metadata_json(metadata_path)
    raise FileNotFoundError(f"hnsw_metadata_json_missing:{metadata_path}")


def _load_hnsw_metadata_json(metadata_path: Path) -> dict[str, Any]:
    file_size = metadata_path.stat().st_size
    if file_size > MAX_HNSW_METADATA_BYTES:
        raise ValueError(f"hnsw_metadata_too_large:{file_size}")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return _validate_hnsw_metadata(payload)


def _validate_hnsw_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("invalid_hnsw_metadata_payload")
    label_to_id = payload.get("label_to_id", {})
    if not isinstance(label_to_id, dict):
        raise ValueError("invalid_hnsw_metadata_label_map")
    total_elements_added = int(payload.get("total_elements_added", 0) or 0)
    return {
        "label_to_id": {str(key): str(value) for key, value in label_to_id.items()},
        "total_elements_added": max(total_elements_added, 0),
    }


def _build_fts5_match_expression(terms: list[str]) -> str:
    quoted_terms: list[str] = []
    for raw_term in terms:
        term = _sanitize_fts5_term(raw_term)
        if term:
            quoted_terms.append(f'"{term}"')
    return " OR ".join(quoted_terms)


def _sanitize_fts5_term(term: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", str(term or ""))
    cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]+", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return cleaned[:80]


def _is_memory_load_error(message: str) -> bool:
    lowered = (message or "").lower()
    return "not enough memory" in lowered or "loadpersistedindex failed to allocate" in lowered


def _looks_like_qa_record(document: str, answer: str) -> bool:
    return bool(document.strip() and answer.strip())


def _is_case_style_text(text: str) -> bool:
    if not text:
        return False
    hit_count = sum(1 for marker in CASE_STYLE_MARKERS if marker in text)
    return hit_count >= 2


def _answer_quality_bonus(answer: str) -> float:
    answer = (answer or "").strip()
    if not answer:
        return 0.0
    length = len(answer)
    if 12 <= length <= 180:
        return 0.08
    if 180 < length <= 320:
        return 0.05
    if length < 12:
        return -0.04
    return 0.02


def _query_overlap_bonus(query: str, document: str, answer: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0
    question_tokens = set(_tokenize(document))
    answer_tokens = set(_tokenize(answer))
    question_overlap = len(query_tokens & question_tokens)
    answer_overlap = len(query_tokens & answer_tokens)
    return min(question_overlap * 0.03 + answer_overlap * 0.02, 0.25)


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", "", (text or "").strip().lower())
    return normalized


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_tokens = set(_tokenize(f"{left.get('document', '')} {left.get('answer', '')}"))
    right_tokens = set(_tokenize(f"{right.get('document', '')} {right.get('answer', '')}"))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _select_diverse_top_k(items: list[dict[str, Any]], *, query: str, top_k: int) -> list[dict[str, Any]]:
    if not items:
        return []

    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in sorted(
        items,
        key=lambda current: (
            float(current.get("rerank_score", 0.0)),
            float(current.get("score", 0.0)),
        ),
        reverse=True,
    ):
        key = (
            _normalize_text(str(item.get("document", ""))),
            _normalize_text(str(item.get("answer", ""))),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    selected: list[dict[str, Any]] = []
    pool = deduped[: max(top_k * 6, top_k)]
    collection_counter: Counter[str] = Counter()

    while pool and len(selected) < top_k:
        best_index = 0
        best_score = float("-inf")
        for index, item in enumerate(pool):
            adjusted_score = float(item.get("rerank_score", 0.0))
            if selected:
                adjusted_score -= 0.22 * max(_similarity(item, chosen) for chosen in selected)
            adjusted_score -= 0.03 * collection_counter.get(str(item.get("collection", "")), 0)
            adjusted_score += 0.02 if _is_case_style_text(query) and _is_case_style_text(str(item.get("document", ""))) else 0.0
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_index = index

        chosen = dict(pool.pop(best_index))
        chosen["selection_score"] = round(best_score, 6)
        selected.append(chosen)
        collection_counter[str(chosen.get("collection", ""))] += 1

    return selected


def _tokenize(text: str) -> list[str]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return []
    return [token for token in re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", normalized) if token.strip()]


def _extract_probe_terms(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []
    stop_terms = {
        "基本信息",
        "主诉",
        "现病史",
        "体格检查",
        "年龄",
        "性别",
        "请问",
        "如何",
        "什么",
        "哪些",
        "为什么",
    }
    phrases = re.findall(r"[\u4e00-\u9fff]{2,12}|[a-zA-Z0-9]{2,32}", normalized)
    ranked = sorted(
        {phrase.strip() for phrase in phrases if phrase.strip() and phrase.strip() not in stop_terms},
        key=len,
        reverse=True,
    )
    if not ranked:
        compact = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", normalized)
        if compact:
            return [compact[:12]]
        return []
    return ranked[:8]
