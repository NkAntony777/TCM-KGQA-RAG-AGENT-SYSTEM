from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import sqlite3
import sys
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.graph_service.nebulagraph_store import NebulaGraphStore
from services.graph_service.runtime_store import _iter_json_array_rows


DEFAULT_GRAPH_JSON = BACKEND_ROOT / "services" / "graph_service" / "data" / "graph_runtime.json"
DEFAULT_RETRIEVAL_DB = BACKEND_ROOT / "storage" / "retrieval_local_index.fts.db"
DEFAULT_CACHE_DB = BACKEND_ROOT / "storage" / "benchmark_traceable_classics_candidates.sqlite"
DEFAULT_EVAL_CACHE_DB = BACKEND_ROOT / "storage" / "benchmark_traceable_classics_eval_cache.sqlite"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "eval" / "datasets" / "paper"
DEFAULT_MASTER_OUTPUT = DEFAULT_OUTPUT_DIR / "traceable_classics_benchmark_master.json"
DEFAULT_DEBUG_OUTPUT = DEFAULT_OUTPUT_DIR / "traceable_classics_benchmark_debug.json"
DEFAULT_DEV_OUTPUT = DEFAULT_OUTPUT_DIR / "traceable_classics_benchmark_dev.json"
DEFAULT_TEST_OUTPUT = DEFAULT_OUTPUT_DIR / "traceable_classics_benchmark_test.json"
DEFAULT_MANIFEST_OUTPUT = DEFAULT_OUTPUT_DIR / "traceable_classics_benchmark_manifest.json"

ALLOWED_PREDICATES = {
    "使用药材",
    "功效",
    "归经",
    "药性",
    "五味",
    "治疗症状",
    "治疗证候",
    "治疗疾病",
    "别名",
    "治法",
}
ALLOWED_SUBJECT_TYPES = {"formula", "herb", "medicine"}
PREDICATE_LABELS = {
    "使用药材": "组成",
    "功效": "功效",
    "归经": "归经",
    "药性": "药性",
    "五味": "五味",
    "治疗症状": "主治症状",
    "治疗证候": "主治证候",
    "治疗疾病": "主治疾病",
    "别名": "别名",
    "治法": "治法",
}
FORMULA_SUFFIXES = ("汤", "散", "丸", "饮", "方", "丹", "膏", "剂", "酒", "露")
HERB_SUFFIXES = ("草", "根", "皮", "叶", "花", "子", "仁", "藤", "实", "米", "茎")
INVALID_PATTERN = re.compile(r"[A-Za-z]{2,}|\?|HT|\\uFFFD|□|\\\\x|ζ|đ|α|β|γ|δ|ο|ψ|ƪ|�")
CHINESE_CHAR_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
NAME_PATTERN = re.compile(r"^[《》\u3400-\u4dbf\u4e00-\u9fff0-9·、（）()\-—]+$")
GENERIC_SUBJECT_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千0-9]+[方案]|又方|本方|某方|前方|后方)$")
PUNCT_TRANSLATION = str.maketrans("", "", "《》“”\"'`·,，。！？；;：:、（）()[]【】 \t\r\n")


@dataclass(frozen=True)
class BenchmarkFamily:
    name: str
    subject_type: str
    predicate: str
    target_groups: int


@dataclass(frozen=True)
class BuildConfig:
    max_workers: int
    oversample_factor: int
    per_subject_limit: int
    per_book_limit: int
    retrieval_db: Path
    eval_cache_db: Path
    cache_version: str


SIZE_PROFILE_SCALE = {
    "default": 1.0,
    "large": 1.75,
    "xlarge": 2.5,
}

_THREAD_LOCAL = threading.local()


BENCHMARK_FAMILIES = [
    BenchmarkFamily("formula_composition", "formula", "使用药材", 50),
    BenchmarkFamily("formula_indication_symptom", "formula", "治疗症状", 28),
    BenchmarkFamily("formula_indication_disease", "formula", "治疗疾病", 20),
    BenchmarkFamily("formula_indication_syndrome", "formula", "治疗证候", 18),
    BenchmarkFamily("formula_effect", "formula", "功效", 24),
    BenchmarkFamily("formula_method", "formula", "治法", 12),
    BenchmarkFamily("herb_effect", "herb", "功效", 28),
    BenchmarkFamily("herb_property", "herb", "药性", 12),
    BenchmarkFamily("herb_flavor", "herb", "五味", 12),
    BenchmarkFamily("herb_channel", "herb", "归经", 10),
    BenchmarkFamily("entity_alias", "herb", "别名", 8),
    BenchmarkFamily("formula_alias", "formula", "别名", 8),
]


def _stable_hash(value: str) -> int:
    return int(hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:12], 16)


def _clean_book_label(book: str) -> str:
    normalized = str(book or "").strip()
    if not normalized:
        return ""
    return re.sub(r"^\d+\s*[-_－—]\s*", "", normalized).strip()


def _normalize_for_match(value: str) -> str:
    return str(value or "").translate(PUNCT_TRANSLATION)


def _chinese_ratio(value: str) -> float:
    text = str(value or "")
    if not text:
        return 0.0
    return sum(1 for char in text if CHINESE_CHAR_PATTERN.match(char)) / len(text)


def _looks_clean_name(value: str, *, subject_type: str | None = None) -> bool:
    text = str(value or "").strip()
    if len(text) < 2 or len(text) > 24:
        return False
    if INVALID_PATTERN.search(text):
        return False
    if _chinese_ratio(text) < 0.45:
        return False
    if not NAME_PATTERN.match(text):
        return False
    lowered_type = str(subject_type or "").strip()
    if lowered_type == "formula" and not any(suffix in text for suffix in FORMULA_SUFFIXES):
        return False
    if lowered_type == "formula" and GENERIC_SUBJECT_PATTERN.match(text):
        return False
    if lowered_type == "herb" and any(marker in text for marker in ("又方", "本方", "某方", "方论")):
        return False
    if text.endswith(("又方", "本方", "主方", "验方")):
        return False
    return True


def _looks_clean_source_text(value: str) -> bool:
    text = str(value or "").strip()
    if len(text) < 10 or len(text) > 160:
        return False
    if INVALID_PATTERN.search(text):
        return False
    return _chinese_ratio(text) >= 0.5


def _difficulty_for_group(predicate: str, object_count: int, source_count: int) -> str:
    if predicate in {"治疗症状", "治疗疾病", "治疗证候", "使用药材"} and object_count >= 4:
        return "hard"
    if source_count >= 2 or object_count >= 3:
        return "medium"
    return "easy"


def _question_for_answer(subject: str, predicate: str, category: str) -> str:
    if category == "formula_composition":
        return f"{subject}由哪些药材组成？请依据古籍回答并给出出处。"
    if category.startswith("formula_indication"):
        return f"{subject}主要适用于什么病证或症状？请依据古籍回答并给出出处。"
    if category == "formula_effect":
        return f"{subject}的功效是什么？请依据古籍回答并给出出处。"
    if category == "formula_method":
        return f"{subject}体现了什么治法？请依据古籍回答并给出出处。"
    if category == "herb_effect":
        return f"{subject}在古籍中的主要功效是什么？请给出依据。"
    if category == "herb_property":
        return f"{subject}的药性是什么？请给出古籍依据。"
    if category == "herb_flavor":
        return f"{subject}的五味是什么？请给出古籍依据。"
    if category == "herb_channel":
        return f"{subject}归哪些经？请给出古籍依据。"
    if category in {"entity_alias", "formula_alias"}:
        return f"{subject}在古籍中的别名是什么？请给出出处。"
    return f"{subject}的{PREDICATE_LABELS.get(predicate, predicate)}是什么？请依据古籍回答并给出出处。"


def _question_for_answer_with_scope(subject: str, predicate: str, category: str, answer_count: int) -> str:
    if answer_count <= 1:
        if category == "formula_composition":
            return f"{subject}的一个组成药材是什么？请依据古籍回答并给出出处。"
        if category.startswith("formula_indication"):
            return f"{subject}主治中的一个关键病证或症状是什么？请依据古籍回答并给出出处。"
        if category == "formula_effect":
            return f"{subject}的一个核心功效是什么？请依据古籍回答并给出出处。"
        if category == "formula_method":
            return f"{subject}体现的一个治法要点是什么？请依据古籍回答并给出出处。"
        if category == "herb_effect":
            return f"{subject}在古籍中的一个主要功效是什么？请给出依据。"
        if category == "herb_property":
            return f"{subject}的一项药性是什么？请给出古籍依据。"
        if category == "herb_flavor":
            return f"{subject}的一项五味属性是什么？请给出古籍依据。"
        if category == "herb_channel":
            return f"{subject}归入的一条经脉是什么？请给出古籍依据。"
        if category in {"entity_alias", "formula_alias"}:
            return f"{subject}在古籍中的一个别名是什么？请给出出处。"
    return _question_for_answer(subject, predicate, category)


def _question_for_source(subject: str, predicate: str, category: str) -> str:
    label = PREDICATE_LABELS.get(predicate, predicate)
    if category == "formula_composition":
        return f"古籍中关于{subject}组成的记载出自哪本书哪一篇？"
    if category.startswith("formula_indication"):
        return f"古籍中关于{subject}主治的记载出自哪本书哪一篇？"
    if category in {"entity_alias", "formula_alias"}:
        return f"古籍中关于{subject}别名的记载出自哪本书哪一篇？"
    return f"古籍中关于{subject}{label}的记载出自哪本书哪一篇？"


def _family_eval_focus(category: str, predicate: str) -> list[str]:
    focus = ["book_hit", "chapter_hit", "evidence_hit", "answer_keypoint", "provenance_success"]
    if predicate == "使用药材":
        focus.append("composition")
    elif predicate in {"治疗症状", "治疗疾病", "治疗证候"}:
        focus.append("indication")
    elif predicate in {"功效", "治法"}:
        focus.append("effect")
    elif predicate in {"药性", "五味", "归经"}:
        focus.append("property")
    elif predicate == "别名":
        focus.append("alias")
    return focus


def _split_for_subject(subject: str) -> str:
    bucket = _stable_hash(subject) % 10
    if bucket == 0:
        return "debug"
    if bucket in {1, 2}:
        return "dev"
    return "test"


def _unique_nonempty(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _scaled_families(*, size_profile: str, family_scale: float) -> list[BenchmarkFamily]:
    multiplier = SIZE_PROFILE_SCALE.get(size_profile, 1.0) * max(0.1, float(family_scale))
    scaled: list[BenchmarkFamily] = []
    for family in BENCHMARK_FAMILIES:
        scaled.append(
            BenchmarkFamily(
                name=family.name,
                subject_type=family.subject_type,
                predicate=family.predicate,
                target_groups=max(1, int(round(family.target_groups * multiplier))),
            )
        )
    return scaled


def _asset_signature(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"


def _make_cache_version(*, graph_json: Path, retrieval_db: Path) -> str:
    return "|".join(["v3", _asset_signature(graph_json), _asset_signature(retrieval_db)])


def _connect_retrieval_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_candidate_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_eval_cache_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS eval_cache (
            cache_key TEXT NOT NULL,
            cache_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (cache_key, cache_version)
        )
        """
    )
    return conn


def _get_thread_resources(retrieval_db_path: Path, eval_cache_db_path: Path) -> tuple[NebulaGraphStore, sqlite3.Connection, sqlite3.Connection]:
    store = getattr(_THREAD_LOCAL, "nebula_store", None)
    if store is None:
        store = NebulaGraphStore()
        _THREAD_LOCAL.nebula_store = store
    retrieval_conn = getattr(_THREAD_LOCAL, "retrieval_conn", None)
    if retrieval_conn is None:
        retrieval_conn = _connect_retrieval_db(retrieval_db_path)
        _THREAD_LOCAL.retrieval_conn = retrieval_conn
    eval_cache_conn = getattr(_THREAD_LOCAL, "eval_cache_conn", None)
    if eval_cache_conn is None:
        eval_cache_conn = _connect_eval_cache_db(eval_cache_db_path)
        _THREAD_LOCAL.eval_cache_conn = eval_cache_conn
    return store, retrieval_conn, eval_cache_conn


def _ensure_candidate_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS triples (
            subject TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            source_book TEXT NOT NULL,
            source_book_clean TEXT NOT NULL,
            source_chapter TEXT NOT NULL,
            fact_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_triples_group
        ON triples(subject_type, predicate, subject, source_book, source_chapter);
        CREATE INDEX IF NOT EXISTS idx_triples_fact_id
        ON triples(fact_id);
        """
    )


def _candidate_db_populated(conn: sqlite3.Connection) -> bool:
    try:
        return int(conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0]) > 0
    except sqlite3.Error:
        return False


def _populate_candidate_db(graph_json: Path, candidate_db: Path, *, rebuild: bool) -> dict[str, Any]:
    if rebuild and candidate_db.exists():
        candidate_db.unlink()
    conn = _connect_candidate_db(candidate_db)
    try:
        _ensure_candidate_schema(conn)
        if _candidate_db_populated(conn):
            row_count = int(conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0])
            return {"candidate_db": str(candidate_db), "cached": True, "rows": row_count}

        inserted = 0
        batch: list[tuple[str, str, str, str, str, str, str, str]] = []
        for row in _iter_json_array_rows(graph_json):
            predicate = str(row.get("predicate", "")).strip()
            subject = str(row.get("subject", "")).strip()
            obj = str(row.get("object", "")).strip()
            subject_type = str(row.get("subject_type", "")).strip()
            source_book = str(row.get("source_book", "")).strip()
            source_chapter = str(row.get("source_chapter", "")).strip()
            fact_id = str(row.get("fact_id", "")).strip()
            if predicate not in ALLOWED_PREDICATES:
                continue
            if subject_type not in ALLOWED_SUBJECT_TYPES:
                continue
            if source_book == "TCM-MKG" or not source_book or not source_chapter or not fact_id:
                continue
            if not _looks_clean_name(subject, subject_type=subject_type):
                continue
            if not _looks_clean_name(obj):
                continue
            source_book_clean = _clean_book_label(source_book)
            if not source_book_clean or _chinese_ratio(source_book_clean) < 0.5:
                continue
            if _chinese_ratio(source_chapter) < 0.3:
                continue
            batch.append(
                (
                    subject,
                    subject_type,
                    predicate,
                    obj,
                    source_book,
                    source_book_clean,
                    source_chapter,
                    fact_id,
                )
            )
            if len(batch) >= 5000:
                conn.executemany(
                    """
                    INSERT INTO triples (
                        subject, subject_type, predicate, object,
                        source_book, source_book_clean, source_chapter, fact_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                inserted += len(batch)
                batch.clear()
        if batch:
            conn.executemany(
                """
                INSERT INTO triples (
                    subject, subject_type, predicate, object,
                    source_book, source_book_clean, source_chapter, fact_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            inserted += len(batch)
        conn.commit()
        return {"candidate_db": str(candidate_db), "cached": False, "rows": inserted}
    finally:
        conn.close()


def _fetch_candidate_groups(conn: sqlite3.Connection, family: BenchmarkFamily, *, oversample_factor: int = 4) -> list[dict[str, Any]]:
    limit = max(64, family.target_groups * oversample_factor)
    rows = conn.execute(
        """
        SELECT
            subject,
            subject_type,
            predicate,
            source_book,
            source_book_clean,
            source_chapter,
            COUNT(DISTINCT object) AS object_count,
            COUNT(*) AS row_count
        FROM triples
        WHERE subject_type = ? AND predicate = ?
        GROUP BY subject, subject_type, predicate, source_book, source_book_clean, source_chapter
        HAVING object_count >= 1
        ORDER BY object_count DESC, row_count DESC, source_book ASC, subject ASC
        LIMIT ?
        """,
        (family.subject_type, family.predicate, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_group_rows(conn: sqlite3.Connection, group: dict[str, Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT subject, subject_type, predicate, object, source_book, source_book_clean, source_chapter, fact_id
        FROM triples
        WHERE subject = ? AND subject_type = ? AND predicate = ? AND source_book = ? AND source_chapter = ?
        ORDER BY object ASC
        """,
        (
            group["subject"],
            group["subject_type"],
            group["predicate"],
            group["source_book"],
            group["source_chapter"],
        ),
    ).fetchall()
    return [dict(row) for row in rows]


def _nebula_rows_for_group(store: NebulaGraphStore, group: dict[str, Any], objects: set[str]) -> list[dict[str, Any]]:
    reverse_modes = [False, True] if group["predicate"] == "别名" else [False]
    rows: list[dict[str, Any]] = []
    for reverse in reverse_modes:
        rows.extend(
            store.batch_neighbors(
                [group["subject"]],
                reverse=reverse,
                predicates=[group["predicate"]],
                source_books=[group["source_book"]],
                limit_per_entity=256,
            )
        )
    matched: list[dict[str, Any]] = []
    expected_book = _normalize_for_match(group["source_book"])
    expected_chapter = _normalize_for_match(group["source_chapter"])
    for row in rows:
        neighbor_name = str(row.get("neighbor_name", "")).strip()
        source_book = str(row.get("source_book", "")).strip()
        source_chapter = str(row.get("source_chapter", "")).strip()
        if neighbor_name not in objects:
            continue
        if _normalize_for_match(source_book) != expected_book:
            continue
        if _normalize_for_match(source_chapter) != expected_chapter:
            continue
        source_text = str(row.get("source_text", "")).strip()
        confidence = float(row.get("confidence", 0.0) or 0.0)
        if confidence < 0.9 or not _looks_clean_source_text(source_text):
            continue
        if not _text_mentions_term(source_text, neighbor_name):
            continue
        matched.append(
            {
                "object": neighbor_name,
                "source_book": source_book,
                "source_book_clean": _clean_book_label(source_book),
                "source_chapter": source_chapter,
                "source_text": source_text,
                "confidence": round(confidence, 4),
                "fact_id": str(row.get("fact_id", "")).strip(),
                "fact_ids": row.get("fact_ids") or [],
            }
        )
    return matched


def _text_snippet(text: str, *, limit: int = 20) -> str:
    normalized = _normalize_for_match(text)
    return normalized[:limit]


def _text_mentions_term(text: str, term: str) -> bool:
    normalized_text = _normalize_for_match(text)
    normalized_term = _normalize_for_match(term)
    if len(normalized_term) < 2:
        return False
    return normalized_term in normalized_text


def _resolve_retrieval_source(
    conn: sqlite3.Connection,
    *,
    source_book: str,
    source_book_clean: str,
    source_chapter: str,
    source_text: str,
) -> dict[str, str] | None:
    snippet = _text_snippet(source_text, limit=18)
    if len(snippet) < 8:
        return None
    strict_row = conn.execute(
        """
        SELECT book_name, chapter_title, chunk_id
        FROM docs
        WHERE file_path LIKE 'classic://%'
          AND (
            book_name = ?
            OR book_name = ?
            OR book_name LIKE '%' || ? || '%'
          )
          AND (
            chapter_title = ?
            OR chapter_title LIKE '%' || ? || '%'
          )
          AND instr(replace(replace(replace(replace(text, ' ', ''), char(10), ''), char(13), ''), '　', ''), ?) > 0
        LIMIT 1
        """,
        (
            source_book,
            source_book_clean,
            source_book_clean,
            source_chapter,
            source_chapter,
            snippet,
        ),
    ).fetchone()
    if strict_row is not None:
        return {
            "book_name": str(strict_row["book_name"]).strip(),
            "chapter_title": str(strict_row["chapter_title"]).strip(),
            "chunk_id": str(strict_row["chunk_id"]).strip(),
        }
    loose_row = conn.execute(
        """
        SELECT book_name, chapter_title, chunk_id
        FROM docs
        WHERE file_path LIKE 'classic://%'
          AND (
            book_name = ?
            OR book_name = ?
            OR book_name LIKE '%' || ? || '%'
          )
          AND instr(replace(replace(replace(replace(text, ' ', ''), char(10), ''), char(13), ''), '　', ''), ?) > 0
        LIMIT 1
        """,
        (
            source_book,
            source_book_clean,
            source_book_clean,
            snippet,
        ),
    ).fetchone()
    if loose_row is None:
        return None
    return {
        "book_name": str(loose_row["book_name"]).strip(),
        "chapter_title": str(loose_row["chapter_title"]).strip(),
        "chunk_id": str(loose_row["chunk_id"]).strip(),
    }


def _build_group_case_records(
    group: dict[str, Any],
    family: BenchmarkFamily,
    group_rows: list[dict[str, Any]],
    nebula_rows: list[dict[str, Any]],
    resolved_sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    seen_evidence: set[tuple[str, str, str]] = set()
    for row in nebula_rows:
        key = (
            str(row["source_book"]).strip(),
            str(row["source_chapter"]).strip(),
            _normalize_for_match(str(row["source_text"]).strip()),
        )
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        evidence_rows.append(row)
    keypoint_rows = evidence_rows[:3]
    unique_objects: list[str] = []
    seen_objects: set[str] = set()
    for row in keypoint_rows:
        obj = str(row.get("object", "") or row.get("neighbor_name", "")).strip()
        if obj and obj not in seen_objects:
            seen_objects.add(obj)
            unique_objects.append(obj)
    gold_evidence = [str(row["source_text"]).strip() for row in keypoint_rows]
    gold_answer_outline = unique_objects[: min(3, len(unique_objects))]
    resolved_book_names: list[str] = []
    resolved_chapter_titles: list[str] = []
    for item in resolved_sources:
        book_name = str(item.get("resolved_book_name", "")).strip()
        chapter_title = str(item.get("resolved_chapter_title", "")).strip()
        if book_name and book_name not in resolved_book_names:
            resolved_book_names.append(book_name)
        if chapter_title and chapter_title not in resolved_chapter_titles:
            resolved_chapter_titles.append(chapter_title)
    difficulty = _difficulty_for_group(group["predicate"], len(unique_objects), len(evidence_rows))
    split = _split_for_subject(group["subject"])
    common_payload = {
        "category": family.name,
        "difficulty": difficulty,
        "eval_focus": _family_eval_focus(family.name, group["predicate"]),
        "subject": group["subject"],
        "subject_type": group["subject_type"],
        "predicate": group["predicate"],
        "predicate_label": PREDICATE_LABELS.get(group["predicate"], group["predicate"]),
        "expected_route_hint": "graph",
        "answer_type": "set" if len(gold_answer_outline) > 1 else "string",
        "expected_books_any": [group["source_book"], group["source_book_clean"], *resolved_book_names],
        "expected_chapters_any": resolved_chapter_titles or [group["source_chapter"]],
        "expected_keywords_any": gold_answer_outline[:],
        "preferred_terms": gold_answer_outline[:3],
        "gold_answer_outline": gold_answer_outline,
        "gold_evidence_any": gold_evidence,
        "gold_relation_tuples": [
            {"subject": group["subject"], "predicate": group["predicate"], "object": item}
            for item in gold_answer_outline
        ],
        "provenance": [
            {
                "source_book": str(row["source_book"]).strip(),
                "source_book_clean": str(row["source_book_clean"]).strip(),
                "source_chapter": str(row["source_chapter"]).strip(),
                "source_text": str(row["source_text"]).strip(),
                "confidence": row["confidence"],
                "fact_id": str(row["fact_id"]).strip(),
            }
            for row in evidence_rows[:3]
        ],
        "split": split,
    }
    group_id = hashlib.sha1(
        f"{family.name}::{group['subject']}::{group['predicate']}::{group['source_book']}::{group['source_chapter']}".encode("utf-8")
    ).hexdigest()[:12]
    answer_case = {
        **common_payload,
        "case_id": f"tcb_{group_id}_ans",
        "task_family": "answer_trace",
        "query": _question_for_answer_with_scope(group["subject"], group["predicate"], family.name, len(gold_answer_outline)),
        "notes": f"source={group['source_book']} objects={len(gold_answer_outline)}",
    }
    source_case = {
        **common_payload,
        "case_id": f"tcb_{group_id}_src",
        "task_family": "source_locate",
        "query": _question_for_source(group["subject"], group["predicate"], family.name),
        "notes": f"source={group['source_book']} objects={len(gold_answer_outline)}",
    }
    return [answer_case, source_case]


def _query_groups_for_subject_predicate(conn: sqlite3.Connection, *, subject: str, predicate: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            subject,
            subject_type,
            predicate,
            source_book,
            source_book_clean,
            source_chapter,
            COUNT(DISTINCT object) AS object_count,
            COUNT(*) AS row_count
        FROM triples
        WHERE subject = ? AND predicate = ?
        GROUP BY subject, subject_type, predicate, source_book, source_book_clean, source_chapter
        ORDER BY object_count DESC, row_count DESC, source_book ASC
        LIMIT 32
        """,
        (subject, predicate),
    ).fetchall()
    return [dict(row) for row in rows]


def _augment_cases_with_acceptables(
    cases: list[dict[str, Any]],
    candidate_db_path: Path,
    config: BuildConfig,
    families_by_name: dict[str, BenchmarkFamily],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_conn = _connect_candidate_db(candidate_db_path)
    try:
        grouped_cases: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for case in cases:
            grouped_cases[(str(case["subject"]).strip(), str(case["predicate"]).strip())].append(case)

        augmentation_summary = {
            "subject_predicate_pairs": len(grouped_cases),
            "multi_book_pairs": 0,
            "single_book_pairs": 0,
        }

        for (subject, predicate), pair_cases in grouped_cases.items():
            family_name = str(pair_cases[0]["category"]).strip()
            family = families_by_name[family_name]
            groups = _query_groups_for_subject_predicate(candidate_conn, subject=subject, predicate=predicate)
            if not groups:
                continue
            group_rows_map = {
                (
                    str(group["subject"]).strip(),
                    str(group["subject_type"]).strip(),
                    str(group["predicate"]).strip(),
                    str(group["source_book"]).strip(),
                    str(group["source_chapter"]).strip(),
                ): _fetch_group_rows(candidate_conn, group)
                for group in groups
            }
            with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
                futures = [
                    executor.submit(
                        _evaluate_group_candidate,
                        family=family,
                        group=group,
                        group_rows=group_rows_map[
                            (
                                str(group["subject"]).strip(),
                                str(group["subject_type"]).strip(),
                                str(group["predicate"]).strip(),
                                str(group["source_book"]).strip(),
                                str(group["source_chapter"]).strip(),
                            )
                        ],
                        config=config,
                    )
                    for group in groups
                ]
                evaluated = [future.result() for future in futures]

            ok_payloads = [item for item in evaluated if item.get("status") == "ok" and item.get("cases")]
            acceptable_books = _unique_nonempty(
                [
                    value
                    for payload in ok_payloads
                    for value in payload.get("all_books", [])
                ]
            )
            acceptable_chapters = _unique_nonempty(
                [
                    value
                    for payload in ok_payloads
                    for value in payload.get("all_chapters", [])
                ]
            )
            acceptable_answers = _unique_nonempty(
                [
                    value
                    for payload in ok_payloads
                    for value in payload.get("all_objects", [])
                ]
            )
            acceptable_evidence = _unique_nonempty(
                [
                    value
                    for payload in ok_payloads
                    for value in payload.get("all_evidence", [])
                ]
            )
            acceptable_provenance: list[dict[str, Any]] = []
            seen_provenance: set[tuple[str, str, str]] = set()
            for payload in ok_payloads:
                for item in payload["cases"][0].get("provenance", []):
                    key = (
                        str(item.get("source_book", "")).strip(),
                        str(item.get("source_chapter", "")).strip(),
                        _normalize_for_match(str(item.get("source_text", "")).strip()),
                    )
                    if key in seen_provenance:
                        continue
                    seen_provenance.add(key)
                    acceptable_provenance.append(item)

            if len({book for book in acceptable_books if book}) > 1:
                augmentation_summary["multi_book_pairs"] += 1
            else:
                augmentation_summary["single_book_pairs"] += 1

            for case in pair_cases:
                case["strict_books_any"] = list(case.get("expected_books_any", []))
                case["strict_chapters_any"] = list(case.get("expected_chapters_any", []))
                case["strict_answer_outline"] = list(case.get("gold_answer_outline", []))
                case["strict_evidence_any"] = list(case.get("gold_evidence_any", []))
                case["expected_books_any"] = acceptable_books or list(case.get("expected_books_any", []))
                case["expected_chapters_any"] = acceptable_chapters or list(case.get("expected_chapters_any", []))
                case["expected_keywords_any"] = acceptable_answers or list(case.get("expected_keywords_any", []))
                case["preferred_terms"] = (acceptable_answers[:6] if acceptable_answers else list(case.get("preferred_terms", [])))
                case["gold_answer_outline"] = acceptable_answers or list(case.get("gold_answer_outline", []))
                case["gold_evidence_any"] = acceptable_evidence or list(case.get("gold_evidence_any", []))
                case["provenance"] = acceptable_provenance or list(case.get("provenance", []))
                case["answer_type"] = "set" if len(case["gold_answer_outline"]) > 1 else "string"
                case["acceptable_books_any"] = list(case["expected_books_any"])
                case["acceptable_chapters_any"] = list(case["expected_chapters_any"])
                case["acceptable_answer_outline"] = list(case["gold_answer_outline"])
                case["acceptable_evidence_any"] = list(case["gold_evidence_any"])
                case["notes"] = f"{case.get('notes', '')}; acceptable_books={len(case['expected_books_any'])}; acceptable_answers={len(case['gold_answer_outline'])}".strip("; ")
                if str(case.get("task_family", "")).strip() == "answer_trace":
                    case["query"] = _question_for_answer_with_scope(
                        str(case["subject"]).strip(),
                        str(case["predicate"]).strip(),
                        str(case["category"]).strip(),
                        len(case["gold_answer_outline"]),
                    )
        return cases, augmentation_summary
    finally:
        candidate_conn.close()


def _evaluate_group_candidate(
    *,
    family: BenchmarkFamily,
    group: dict[str, Any],
    group_rows: list[dict[str, Any]],
    config: BuildConfig,
) -> dict[str, Any]:
    cache_key = hashlib.sha1(
        f"{family.name}::{group['subject']}::{group['subject_type']}::{group['predicate']}::{group['source_book']}::{group['source_chapter']}".encode("utf-8")
    ).hexdigest()
    store, retrieval_conn, eval_cache_conn = _get_thread_resources(config.retrieval_db, config.eval_cache_db)
    cached = eval_cache_conn.execute(
        "SELECT payload_json FROM eval_cache WHERE cache_key = ? AND cache_version = ? LIMIT 1",
        (cache_key, config.cache_version),
    ).fetchone()
    if cached is not None:
        payload = json.loads(str(cached["payload_json"]))
        payload["group"] = group
        return payload
    unique_objects = {str(item["object"]).strip() for item in group_rows if str(item["object"]).strip()}
    if family.predicate == "使用药材" and len(unique_objects) < 2:
        payload = {"status": "insufficient_objects"}
        eval_cache_conn.execute(
            "INSERT OR REPLACE INTO eval_cache (cache_key, cache_version, payload_json) VALUES (?, ?, ?)",
            (cache_key, config.cache_version, json.dumps(payload, ensure_ascii=False)),
        )
        eval_cache_conn.commit()
        payload["group"] = group
        return payload
    nebula_rows = _nebula_rows_for_group(store, group, unique_objects)
    if not nebula_rows:
        payload = {"status": "nebula_missing"}
        eval_cache_conn.execute(
            "INSERT OR REPLACE INTO eval_cache (cache_key, cache_version, payload_json) VALUES (?, ?, ?)",
            (cache_key, config.cache_version, json.dumps(payload, ensure_ascii=False)),
        )
        eval_cache_conn.commit()
        payload["group"] = group
        return payload
    evidence_objects = {str(item.get("object", "")).strip() for item in nebula_rows if str(item.get("object", "")).strip()}
    if family.predicate == "使用药材" and len(evidence_objects) < 2:
        payload = {"status": "insufficient_evidence_objects"}
        eval_cache_conn.execute(
            "INSERT OR REPLACE INTO eval_cache (cache_key, cache_version, payload_json) VALUES (?, ?, ?)",
            (cache_key, config.cache_version, json.dumps(payload, ensure_ascii=False)),
        )
        eval_cache_conn.commit()
        payload["group"] = group
        return payload
    resolved_sources: list[dict[str, Any]] = []
    for row in nebula_rows:
        resolved = _resolve_retrieval_source(
            retrieval_conn,
            source_book=str(row["source_book"]).strip(),
            source_book_clean=str(row["source_book_clean"]).strip(),
            source_chapter=str(row["source_chapter"]).strip(),
            source_text=str(row["source_text"]).strip(),
        )
        if resolved is None:
            continue
        enriched = dict(row)
        enriched["resolved_book_name"] = resolved["book_name"]
        enriched["resolved_chapter_title"] = resolved["chapter_title"]
        enriched["resolved_chunk_id"] = resolved["chunk_id"]
        resolved_sources.append(enriched)
    if not resolved_sources:
        payload = {"status": "retrieval_missing"}
        eval_cache_conn.execute(
            "INSERT OR REPLACE INTO eval_cache (cache_key, cache_version, payload_json) VALUES (?, ?, ?)",
            (cache_key, config.cache_version, json.dumps(payload, ensure_ascii=False)),
        )
        eval_cache_conn.commit()
        payload["group"] = group
        return payload
    all_objects = _unique_nonempty([str(item.get("object", "")).strip() for item in resolved_sources])
    all_books = _unique_nonempty(
        [
            str(item.get("source_book", "")).strip()
            for item in resolved_sources
        ]
        + [
            str(item.get("source_book_clean", "")).strip()
            for item in resolved_sources
        ]
        + [
            str(item.get("resolved_book_name", "")).strip()
            for item in resolved_sources
        ]
    )
    all_chapters = _unique_nonempty(
        [
            str(item.get("resolved_chapter_title", "")).strip()
            for item in resolved_sources
        ]
        + [
            str(item.get("source_chapter", "")).strip()
            for item in resolved_sources
        ]
    )
    all_evidence = _unique_nonempty([str(item.get("source_text", "")).strip() for item in resolved_sources])
    built_cases = _build_group_case_records(group, family, group_rows, resolved_sources, resolved_sources)
    payload = {
        "status": "ok",
        "cases": built_cases,
        "all_objects": all_objects,
        "all_books": all_books,
        "all_chapters": all_chapters,
        "all_evidence": all_evidence,
    }
    eval_cache_conn.execute(
        "INSERT OR REPLACE INTO eval_cache (cache_key, cache_version, payload_json) VALUES (?, ?, ?)",
        (cache_key, config.cache_version, json.dumps(payload, ensure_ascii=False)),
    )
    eval_cache_conn.commit()
    payload["group"] = group
    return payload


def _select_cases(
    candidate_conn: sqlite3.Connection,
    retrieval_db_path: Path,
    families: list[BenchmarkFamily],
    config: BuildConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"families": {}, "rejected": Counter()}
    selected_subjects: Counter[str] = Counter()
    selected_books: Counter[str] = Counter()

    for family in families:
        selected_groups = 0
        family_rejections: Counter[str] = Counter()
        groups = _fetch_candidate_groups(candidate_conn, family, oversample_factor=config.oversample_factor)
        group_rows_map = {
            (
                str(group["subject"]).strip(),
                str(group["subject_type"]).strip(),
                str(group["predicate"]).strip(),
                str(group["source_book"]).strip(),
                str(group["source_chapter"]).strip(),
            ): _fetch_group_rows(candidate_conn, group)
            for group in groups
        }
        with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
            futures = [
                executor.submit(
                    _evaluate_group_candidate,
                    family=family,
                    group=group,
                    group_rows=group_rows_map[
                        (
                            str(group["subject"]).strip(),
                            str(group["subject_type"]).strip(),
                            str(group["predicate"]).strip(),
                            str(group["source_book"]).strip(),
                            str(group["source_chapter"]).strip(),
                        )
                    ],
                    config=config,
                )
                for group in groups
            ]
            evaluated = [future.result() for future in futures]
        for item in evaluated:
            group = item["group"]
            subject = str(group["subject"]).strip()
            source_book = str(group["source_book"]).strip()
            if selected_groups >= family.target_groups:
                break
            if selected_subjects[subject] >= config.per_subject_limit:
                family_rejections["subject_cap"] += 1
                continue
            if selected_books[source_book] >= config.per_book_limit:
                family_rejections["book_cap"] += 1
                continue
            if item["status"] != "ok":
                family_rejections[str(item["status"])] += 1
                continue
            cases.extend(item["cases"])
            selected_groups += 1
            selected_subjects[subject] += 1
            selected_books[source_book] += 1

        summary["families"][family.name] = {
            "target_groups": family.target_groups,
            "selected_groups": selected_groups,
            "selected_cases": selected_groups * 2,
            "rejections": dict(family_rejections),
        }
        summary["rejected"].update(family_rejections)
    return cases, summary


def _validate_cases(cases: list[dict[str, Any]], retrieval_conn: sqlite3.Connection, store: NebulaGraphStore) -> dict[str, Any]:
    duplicate_case_ids = [item for item, count in Counter(case["case_id"] for case in cases).items() if count > 1]
    duplicate_queries = [item for item, count in Counter(case["query"] for case in cases).items() if count > 1]
    subject_splits: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        subject_splits[str(case["subject"]).strip()].add(str(case["split"]).strip())
    leaked_subjects = [subject for subject, splits in subject_splits.items() if len(splits) > 1]

    retrieval_pass = 0
    nebula_pass = 0
    for case in cases:
        provenance = case.get("provenance", [])
        if provenance:
            for item in provenance:
                if _resolve_retrieval_source(
                    retrieval_conn,
                    source_book=str(item.get("source_book", "")).strip(),
                    source_book_clean=str(item.get("source_book_clean", "")).strip(),
                    source_chapter=str(item.get("source_chapter", "")).strip(),
                    source_text=str(item.get("source_text", "")).strip(),
                ) is not None:
                    retrieval_pass += 1
                    break
        subject = str(case.get("subject", "")).strip()
        predicate = str(case.get("predicate", "")).strip()
        expected_answers = {str(item).strip() for item in case.get("gold_answer_outline", []) if str(item).strip()}
        if not subject or not predicate or not expected_answers:
            continue
        rows: list[dict[str, Any]] = []
        reverse_modes = [False, True] if predicate == "别名" else [False]
        for reverse in reverse_modes:
            rows.extend(
                store.batch_neighbors(
                    [subject],
                    reverse=reverse,
                    predicates=[predicate],
                    source_books=[str(case.get("expected_books_any", [""])[0]).strip()],
                    limit_per_entity=256,
                )
            )
        if any(str(row.get("neighbor_name", "")).strip() in expected_answers for row in rows):
            nebula_pass += 1

    split_counter = Counter(str(case["split"]).strip() for case in cases)
    category_counter = Counter(str(case["category"]).strip() for case in cases)
    task_counter = Counter(str(case["task_family"]).strip() for case in cases)
    book_counter = Counter(str(case.get("expected_books_any", [""])[0]).strip() for case in cases)
    return {
        "total_cases": len(cases),
        "split_distribution": dict(split_counter),
        "category_distribution": dict(category_counter),
        "task_family_distribution": dict(task_counter),
        "unique_subjects": len({str(case["subject"]).strip() for case in cases}),
        "unique_books": len({str(case.get("expected_books_any", [""])[0]).strip() for case in cases}),
        "top_books": dict(book_counter.most_common(20)),
        "duplicate_case_ids": duplicate_case_ids,
        "duplicate_queries": duplicate_queries,
        "leaked_subjects": leaked_subjects,
        "retrieval_validation_pass": retrieval_pass,
        "nebula_validation_pass": nebula_pass,
    }


def _write_dataset(outputs: dict[str, Path], cases: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    outputs["master"].parent.mkdir(parents=True, exist_ok=True)
    split_cases = {
        "debug": [case for case in cases if case["split"] == "debug"],
        "dev": [case for case in cases if case["split"] == "dev"],
        "test": [case for case in cases if case["split"] == "test"],
    }
    outputs["master"].write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs["debug"].write_text(json.dumps(split_cases["debug"], ensure_ascii=False, indent=2), encoding="utf-8")
    outputs["dev"].write_text(json.dumps(split_cases["dev"], ensure_ascii=False, indent=2), encoding="utf-8")
    outputs["test"].write_text(json.dumps(split_cases["test"], ensure_ascii=False, indent=2), encoding="utf-8")
    outputs["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a traceable classics benchmark from graph triples and classic corpus evidence.")
    parser.add_argument("--graph-json", type=Path, default=DEFAULT_GRAPH_JSON)
    parser.add_argument("--retrieval-db", type=Path, default=DEFAULT_RETRIEVAL_DB)
    parser.add_argument("--candidate-db", type=Path, default=DEFAULT_CACHE_DB)
    parser.add_argument("--eval-cache-db", type=Path, default=DEFAULT_EVAL_CACHE_DB)
    parser.add_argument("--output-master", type=Path, default=DEFAULT_MASTER_OUTPUT)
    parser.add_argument("--output-debug", type=Path, default=DEFAULT_DEBUG_OUTPUT)
    parser.add_argument("--output-dev", type=Path, default=DEFAULT_DEV_OUTPUT)
    parser.add_argument("--output-test", type=Path, default=DEFAULT_TEST_OUTPUT)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--size-profile", choices=sorted(SIZE_PROFILE_SCALE), default="default")
    parser.add_argument("--family-scale", type=float, default=1.0)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--oversample-factor", type=int, default=4)
    parser.add_argument("--per-subject-limit", type=int, default=1)
    parser.add_argument("--per-book-limit", type=int, default=10)
    args = parser.parse_args()

    if not args.graph_json.exists():
        raise FileNotFoundError(f"graph_json_not_found: {args.graph_json}")
    if not args.retrieval_db.exists():
        raise FileNotFoundError(f"retrieval_db_not_found: {args.retrieval_db}")

    cache_report = _populate_candidate_db(args.graph_json, args.candidate_db, rebuild=args.rebuild_cache)
    store = NebulaGraphStore()
    health = store.health()
    if health.get("status") != "ok":
        raise RuntimeError(f"nebula_unavailable: {health}")

    candidate_conn = _connect_candidate_db(args.candidate_db)
    try:
        families = _scaled_families(size_profile=str(args.size_profile), family_scale=float(args.family_scale))
        config = BuildConfig(
            max_workers=max(1, int(args.max_workers)),
            oversample_factor=max(1, int(args.oversample_factor)),
            per_subject_limit=max(1, int(args.per_subject_limit)),
            per_book_limit=max(1, int(args.per_book_limit)),
            retrieval_db=args.retrieval_db,
            eval_cache_db=args.eval_cache_db,
            cache_version=_make_cache_version(graph_json=args.graph_json, retrieval_db=args.retrieval_db),
        )
        cases, selection_summary = _select_cases(candidate_conn, args.retrieval_db, families, config)
        cases, acceptable_summary = _augment_cases_with_acceptables(
            cases,
            args.candidate_db,
            config,
            {family.name: family for family in families},
        )
    finally:
        candidate_conn.close()
    retrieval_conn = _connect_retrieval_db(args.retrieval_db)
    try:
        validation_summary = _validate_cases(cases, retrieval_conn, store)
    finally:
        retrieval_conn.close()

    manifest = {
        "benchmark_name": "traceable_classics_benchmark",
        "version": "2026-04-18",
        "graph_json": str(args.graph_json),
        "retrieval_db": str(args.retrieval_db),
        "build_config": {
            "size_profile": args.size_profile,
            "family_scale": args.family_scale,
            "max_workers": args.max_workers,
            "oversample_factor": args.oversample_factor,
            "per_subject_limit": args.per_subject_limit,
            "per_book_limit": args.per_book_limit,
            "eval_cache_db": str(args.eval_cache_db),
            "cache_version": config.cache_version,
        },
        "candidate_cache": cache_report,
        "nebula_health": health,
        "selection_summary": selection_summary,
        "acceptable_summary": acceptable_summary,
        "validation_summary": validation_summary,
    }
    _write_dataset(
        {
            "master": args.output_master,
            "debug": args.output_debug,
            "dev": args.output_dev,
            "test": args.output_test,
            "manifest": args.output_manifest,
        },
        cases,
        manifest,
    )
    print(
        json.dumps(
            {
                "master": str(args.output_master),
                "debug": str(args.output_debug),
                "dev": str(args.output_dev),
                "test": str(args.output_test),
                "manifest": str(args.output_manifest),
                "total_cases": validation_summary["total_cases"],
                "split_distribution": validation_summary["split_distribution"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
