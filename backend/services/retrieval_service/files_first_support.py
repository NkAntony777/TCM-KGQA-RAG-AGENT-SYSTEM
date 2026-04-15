from __future__ import annotations

import gc
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Any, Callable


BOOK_LINE_PATTERN = re.compile(r"^古籍：(.+?)$", re.MULTILINE)
CHAPTER_LINE_PATTERN = re.compile(r"^篇名：(.+?)$", re.MULTILINE)
CLASSIC_PATH_PATTERN = re.compile(r"^classic://(?P<book>[^/]+)/(?P<section>\d{4})(?:-\d{2})?$")
FORMULA_TAG_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)")
CHINESE_SPAN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,10}")
TOPIC_KEYWORDS = (
    "病机",
    "辨证",
    "主治",
    "功效",
    "治法",
    "方义",
    "组成",
    "配伍",
    "加减",
    "归经",
    "药性",
    "煎服",
    "禁忌",
    "条文",
    "方后注",
)
FILES_FIRST_SCHEMA_VERSION = 2
REQUIRED_DOC_COLUMNS = {
    "chunk_id",
    "text",
    "filename",
    "file_type",
    "file_path",
    "page_number",
    "chunk_idx",
    "parent_chunk_id",
    "root_chunk_id",
    "chunk_level",
    "book_name",
    "chapter_title",
    "section_key",
    "section_summary",
    "topic_tags",
    "entity_tags",
}


def extract_book_name(*, text: str, filename: str, file_path: str) -> str:
    match = BOOK_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    if file_path.startswith("classic://"):
        return file_path.removeprefix("classic://").split("/", 1)[0].strip()
    stem = Path(filename or "").stem.strip()
    return re.sub(r"^\d+\s*[-_－—]\s*", "", stem).strip() or stem


def extract_chapter_title(*, text: str, page_number: int | None, file_path: str) -> str:
    match = CHAPTER_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return classic_match.group("section")
    if page_number not in (None, 0):
        return f"{int(page_number):04d}"
    return ""


def build_section_key(*, book_name: str, chapter_title: str, page_number: int | None, file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"{classic_match.group('book')}::{classic_match.group('section')}"
    if book_name and chapter_title:
        return f"{book_name}::{chapter_title}"
    if book_name and page_number not in (None, 0):
        return f"{book_name}::{int(page_number):04d}"
    return ""


def strip_classic_headers(text: str) -> str:
    lines = [str(line or "").rstrip() for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if not (line.startswith("古籍：") or line.startswith("篇名："))).strip()


def merge_section_bodies(parts: list[str]) -> str:
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


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_section_file_path(file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"classic://{classic_match.group('book')}/{classic_match.group('section')}"
    return str(file_path or "")


def _build_section_metadata(*, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
    compact = _compact_text(strip_classic_headers(section_text))
    summary = compact[:180]
    topic_tags: list[str] = []
    entity_tags: list[str] = []
    for keyword in TOPIC_KEYWORDS:
        if keyword in compact and keyword not in topic_tags:
            topic_tags.append(keyword)
    for formula in FORMULA_TAG_PATTERN.findall(f"{chapter_title} {compact}"):
        if formula not in entity_tags:
            entity_tags.append(formula)
    for span in CHINESE_SPAN_PATTERN.findall(chapter_title):
        if span not in topic_tags and span not in entity_tags and span not in {book_name, chapter_title}:
            topic_tags.append(span)
    representative_passages = []
    for fragment in re.split(r"[。！？!?]\s*", compact):
        candidate = fragment.strip()
        if len(candidate) >= 16:
            representative_passages.append(candidate[:120])
        if len(representative_passages) >= 2:
            break
    return {
        "section_summary": summary,
        "topic_tags": topic_tags[:12],
        "entity_tags": entity_tags[:12],
        "representative_passages": representative_passages,
    }


class SectionSummaryCache:
    def __init__(self, cache_path: Path | None = None):
        self.legacy_json_path: Path | None = None
        if cache_path is not None and cache_path.suffix.lower() == ".json":
            self.legacy_json_path = cache_path
            self.cache_path = cache_path.with_suffix(".sqlite")
        else:
            self.cache_path = cache_path
            if cache_path is not None:
                legacy_candidate = cache_path.with_suffix(".json")
                if legacy_candidate.exists():
                    self.legacy_json_path = legacy_candidate
        self._initialized = False
        self._init_lock = Lock()
        if self.cache_path is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        if self.cache_path is None:
            raise RuntimeError("section_summary_cache_not_configured")
        conn = sqlite3.connect(self.cache_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized or self.cache_path is None:
            return
        with self._init_lock:
            if self._initialized:
                return
            with closing(self._connect()) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS section_summaries (
                        section_key TEXT PRIMARY KEY,
                        section_summary TEXT NOT NULL DEFAULT '',
                        topic_tags TEXT NOT NULL DEFAULT '[]',
                        entity_tags TEXT NOT NULL DEFAULT '[]',
                        representative_passages TEXT NOT NULL DEFAULT '[]',
                        updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                    )
                    """
                )
                count_row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
                existing_count = int(count_row[0]) if count_row and count_row[0] is not None else 0
                if existing_count <= 0 and self.legacy_json_path is not None and self.legacy_json_path.exists():
                    try:
                        payload = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
                    except Exception:
                        payload = {}
                    if isinstance(payload, dict) and payload:
                        rows = []
                        for section_key, item in payload.items():
                            if not isinstance(item, dict):
                                continue
                            rows.append(
                                (
                                    str(section_key).strip(),
                                    str(item.get("section_summary", "")),
                                    json.dumps(list(item.get("topic_tags", [])) if isinstance(item.get("topic_tags", []), list) else [], ensure_ascii=False),
                                    json.dumps(list(item.get("entity_tags", [])) if isinstance(item.get("entity_tags", []), list) else [], ensure_ascii=False),
                                    json.dumps(list(item.get("representative_passages", [])) if isinstance(item.get("representative_passages", []), list) else [], ensure_ascii=False),
                                )
                            )
                        if rows:
                            conn.executemany(
                                """
                                INSERT OR REPLACE INTO section_summaries
                                (section_key, section_summary, topic_tags, entity_tags, representative_passages)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                rows,
                            )
                conn.commit()
            self._initialized = True

    def load(self) -> dict[str, dict[str, Any]]:
        self._ensure_initialized()
        if self.cache_path is None:
            return {}
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT section_key, section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                """
            ).fetchall()
        payload: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                topic_tags = json.loads(str(row["topic_tags"] or "[]"))
            except Exception:
                topic_tags = []
            try:
                entity_tags = json.loads(str(row["entity_tags"] or "[]"))
            except Exception:
                entity_tags = []
            try:
                representative_passages = json.loads(str(row["representative_passages"] or "[]"))
            except Exception:
                representative_passages = []
            payload[str(row["section_key"])] = {
                "section_summary": str(row["section_summary"] or ""),
                "topic_tags": topic_tags if isinstance(topic_tags, list) else [],
                "entity_tags": entity_tags if isinstance(entity_tags, list) else [],
                "representative_passages": representative_passages if isinstance(representative_passages, list) else [],
            }
        return payload

    def get(self, section_key: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        if self.cache_path is None:
            return None
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                WHERE section_key = ?
                LIMIT 1
                """,
                (section_key,),
            ).fetchone()
        if row is None:
            return None
        try:
            topic_tags = json.loads(str(row["topic_tags"] or "[]"))
        except Exception:
            topic_tags = []
        try:
            entity_tags = json.loads(str(row["entity_tags"] or "[]"))
        except Exception:
            entity_tags = []
        try:
            representative_passages = json.loads(str(row["representative_passages"] or "[]"))
        except Exception:
            representative_passages = []
        return {
            "section_summary": str(row["section_summary"] or ""),
            "topic_tags": topic_tags if isinstance(topic_tags, list) else [],
            "entity_tags": entity_tags if isinstance(entity_tags, list) else [],
            "representative_passages": representative_passages if isinstance(representative_passages, list) else [],
        }

    def has(self, section_key: str) -> bool:
        self._ensure_initialized()
        if self.cache_path is None:
            return False
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM section_summaries WHERE section_key = ? LIMIT 1",
                (section_key,),
            ).fetchone()
        return row is not None

    def count(self) -> int:
        self._ensure_initialized()
        if self.cache_path is None:
            return 0
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def set(self, section_key: str, metadata: dict[str, Any]) -> None:
        if self.cache_path is None:
            return
        self._ensure_initialized()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO section_summaries
                (section_key, section_summary, topic_tags, entity_tags, representative_passages, updated_at)
                VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                """,
                (
                    section_key,
                    str(metadata.get("section_summary", "")),
                    json.dumps(list(metadata.get("topic_tags", [])) if isinstance(metadata.get("topic_tags", []), list) else [], ensure_ascii=False),
                    json.dumps(list(metadata.get("entity_tags", [])) if isinstance(metadata.get("entity_tags", []), list) else [], ensure_ascii=False),
                    json.dumps(list(metadata.get("representative_passages", [])) if isinstance(metadata.get("representative_passages", []), list) else [], ensure_ascii=False),
                ),
            )
            conn.commit()


def normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("text", "") or "")
    filename = str(item.get("filename", "") or item.get("source_file", "") or "")
    file_path = str(item.get("file_path", "") or "")
    page_number = item.get("page_number", item.get("source_page", 0))
    book_name = str(item.get("book_name", "") or "").strip() or extract_book_name(
        text=text,
        filename=filename,
        file_path=file_path,
    )
    chapter_title = str(item.get("chapter_title", "") or "").strip() or extract_chapter_title(
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
        "section_summary": item.get("section_summary", ""),
        "topic_tags": item.get("topic_tags", ""),
        "entity_tags": item.get("entity_tags", ""),
        "representative_passages": item.get("representative_passages", []),
        "match_snippet": item.get("match_snippet"),
        "rrf_rank": item.get("rrf_rank"),
        "rerank_score": item.get("rerank_score"),
    }


def build_section_response(
    *,
    path: str,
    payload: dict[str, Any],
    parent_store: "ParentChunkStore",
) -> dict[str, Any]:
    raw_items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
    if not raw_items:
        return {
            "backend": "files-first",
            "path": path,
            "status": payload.get("status", "empty"),
            "items": [],
            "count": 0,
        }

    normalized_items = [normalize_chunk(item) for item in raw_items if isinstance(item, dict)]
    if not normalized_items:
        return {
            "backend": "files-first",
            "path": path,
            "status": payload.get("status", "empty"),
            "items": [],
            "count": 0,
        }

    book_name = str(normalized_items[0].get("book_name", "") or "").strip()
    chapter_title = str(normalized_items[0].get("chapter_title", "") or "").strip()
    parent_candidates = [
        str(item.get("parent_chunk_id", "")).strip()
        for item in normalized_items
        if str(item.get("parent_chunk_id", "")).strip()
    ]
    section_text = ""
    if parent_candidates:
        parent_docs = parent_store.get_documents_by_ids(list(dict.fromkeys(parent_candidates)))
        if parent_docs:
            section_text = str(parent_docs[0].get("text", "") or "").strip()

    if not section_text:
        section_text = "\n".join(
            [
                line
                for line in [
                    f"古籍：{book_name}" if book_name else "",
                    f"篇名：{chapter_title}" if chapter_title else "",
                    merge_section_bodies([strip_classic_headers(item.get("text", "")) for item in normalized_items]),
                ]
                if line
            ]
        ).strip()
    metadata = _build_section_metadata(
        book_name=book_name,
        chapter_title=chapter_title,
        section_text=section_text,
    )

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
            "section_summary": metadata["section_summary"],
            "topic_tags": metadata["topic_tags"],
            "entity_tags": metadata["entity_tags"],
            "representative_passages": metadata["representative_passages"],
        },
        "items": normalized_items,
    }


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


class LocalFilesFirstStore:
    def __init__(self, store_path: Path, *, tokenizer, summary_cache_path: Path | None = None, llm_summary_fn: Callable[[str, str, str], dict[str, Any]] | None = None):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.summary_cache = SectionSummaryCache(summary_cache_path)
        self.llm_summary_fn = llm_summary_fn

    def _schema_status(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"exists": False, "compatible": False, "version": 0}
        try:
            with closing(sqlite3.connect(self.store_path)) as conn:
                tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "docs" not in tables:
                    return {"exists": True, "compatible": False, "version": 0}
                doc_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
                meta_version = 0
                if "files_first_meta" in tables:
                    try:
                        row = conn.execute("SELECT value FROM files_first_meta WHERE key = 'schema_version' LIMIT 1").fetchone()
                        meta_version = int(row[0]) if row and row[0] is not None else 0
                    except Exception:
                        meta_version = 0
                compatible = doc_columns >= REQUIRED_DOC_COLUMNS and "sections" in tables and "sections_fts" in tables and meta_version >= FILES_FIRST_SCHEMA_VERSION
                return {"exists": True, "compatible": compatible, "version": meta_version}
        except Exception:
            return {"exists": True, "compatible": False, "version": 0}

    def ensure_schema(self) -> dict[str, Any]:
        status = self._schema_status()
        if not status["exists"] or status["compatible"]:
            return status
        try:
            with closing(sqlite3.connect(self.store_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key
                    FROM docs
                    """
                ).fetchall()
        except Exception:
            return status
        base_rows = [dict(row) for row in rows if isinstance(row, sqlite3.Row)]
        if not base_rows:
            self.reset()
            return {"exists": False, "compatible": False, "version": 0, "migrated": True}
        rows = []
        gc.collect()
        time.sleep(0.2)
        try:
            self.rebuild(base_rows)
        except PermissionError:
            self._migrate_legacy_schema_in_place(base_rows)
        migrated = self._schema_status()
        migrated["migrated"] = True
        return migrated

    def _migrate_legacy_schema_in_place(self, rows: list[dict[str, Any]]) -> None:
        with closing(sqlite3.connect(self.store_path)) as conn:
            existing_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
            for column in ("section_summary", "topic_tags", "entity_tags"):
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE docs ADD COLUMN {column} TEXT")
            conn.execute("CREATE TABLE IF NOT EXISTS files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("DROP TABLE IF EXISTS docs_fts")
            conn.execute("DROP TABLE IF EXISTS sections")
            conn.execute("DROP TABLE IF EXISTS sections_fts")
            conn.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
            )
            conn.execute(
                "CREATE TABLE sections (section_key TEXT PRIMARY KEY, book_name TEXT, chapter_title TEXT, source_file TEXT, file_path TEXT, page_number INTEGER, section_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, text TEXT)"
            )
            conn.execute(
                "CREATE VIRTUAL TABLE sections_fts USING fts5(section_key UNINDEXED, search_text, book_name, chapter_title, section_summary, topic_tags, entity_tags, representative_passages, text, tokenize='trigram')"
            )
            fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
            section_parts: dict[str, dict[str, Any]] = {}
            update_rows: list[tuple[str, str, str, str, str, str, str]] = []
            for row in rows:
                chunk_id = str(row.get("chunk_id", "")).strip()
                if not chunk_id:
                    continue
                text = str(row.get("text", "") or "")
                filename = str(row.get("filename", "") or "")
                file_path = str(row.get("file_path", "") or "")
                page_number = int(row.get("page_number", 0) or 0)
                book_name = str(row.get("book_name", "")).strip() or extract_book_name(text=text, filename=filename, file_path=file_path)
                chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                section_key = str(row.get("section_key", "")).strip() or build_section_key(book_name=book_name, chapter_title=chapter_title, page_number=page_number, file_path=file_path)
                metadata = self._resolve_section_metadata(
                    section_key=section_key or chunk_id,
                    book_name=book_name,
                    chapter_title=chapter_title,
                    section_text=text,
                )
                topic_tags_text = " ".join(metadata["topic_tags"])
                entity_tags_text = " ".join(metadata["entity_tags"])
                update_rows.append((book_name, chapter_title, section_key, metadata["section_summary"], topic_tags_text, entity_tags_text, chunk_id))
                search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
                fts_rows.append((chunk_id, " ".join(self.tokenizer.tokenize(search_basis)), book_name, chapter_title, text, filename, file_path, metadata["section_summary"], topic_tags_text, entity_tags_text))
                section_entry = section_parts.setdefault(
                    section_key or chunk_id,
                    {
                        "book_name": book_name,
                        "chapter_title": chapter_title,
                        "source_file": filename,
                        "file_path": _normalize_section_file_path(file_path),
                        "page_number": page_number,
                        "parts": [],
                    },
                )
                section_entry["parts"].append(text)
            conn.executemany(
                "UPDATE docs SET book_name=?, chapter_title=?, section_key=?, section_summary=?, topic_tags=?, entity_tags=? WHERE chunk_id=?",
                update_rows,
            )
            conn.executemany(
                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                fts_rows,
            )
            section_rows: list[tuple[Any, ...]] = []
            section_fts_rows: list[tuple[Any, ...]] = []
            for section_key, payload in section_parts.items():
                section_text = merge_section_bodies([strip_classic_headers(item) for item in payload.get("parts", [])])
                metadata = self._resolve_section_metadata(
                    section_key=section_key,
                    book_name=str(payload.get("book_name", "")),
                    chapter_title=str(payload.get("chapter_title", "")),
                    section_text=section_text,
                )
                topic_tags_text = " ".join(metadata["topic_tags"])
                entity_tags_text = " ".join(metadata["entity_tags"])
                representative_text = " ".join(metadata["representative_passages"])
                section_rows.append(
                    (
                        section_key,
                        payload.get("book_name", ""),
                        payload.get("chapter_title", ""),
                        payload.get("source_file", ""),
                        payload.get("file_path", ""),
                        payload.get("page_number", 0),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        json.dumps(metadata["representative_passages"], ensure_ascii=False),
                        section_text,
                    )
                )
                section_search_basis = " ".join(
                    [
                        str(payload.get("book_name", "")),
                        str(payload.get("chapter_title", "")),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        representative_text,
                        section_text,
                    ]
                )
                section_fts_rows.append(
                    (
                        section_key,
                        " ".join(self.tokenizer.tokenize(section_search_basis)),
                        payload.get("book_name", ""),
                        payload.get("chapter_title", ""),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        representative_text,
                        section_text,
                    )
                )
            conn.executemany(
                "INSERT INTO sections (section_key, book_name, chapter_title, source_file, file_path, page_number, section_summary, topic_tags, entity_tags, representative_passages, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                section_rows,
            )
            conn.executemany(
                "INSERT INTO sections_fts (section_key, search_text, book_name, chapter_title, section_summary, topic_tags, entity_tags, representative_passages, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                section_fts_rows,
            )
            conn.execute(
                "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
            )
            conn.commit()

    def _resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        cached = self.summary_cache.get(section_key)
        if cached:
            return {
                "section_summary": str(cached.get("section_summary", "")),
                "topic_tags": list(cached.get("topic_tags", []))[:12],
                "entity_tags": list(cached.get("entity_tags", []))[:12],
                "representative_passages": list(cached.get("representative_passages", []))[:2],
            }
        metadata = _build_section_metadata(book_name=book_name, chapter_title=chapter_title, section_text=section_text)
        if self.llm_summary_fn is not None:
            try:
                llm_metadata = self.llm_summary_fn(book_name, chapter_title, section_text)
            except Exception:
                llm_metadata = None
            if isinstance(llm_metadata, dict):
                metadata = {
                    "section_summary": str(llm_metadata.get("section_summary", metadata["section_summary"])),
                    "topic_tags": list(llm_metadata.get("topic_tags", metadata["topic_tags"]))[:12],
                    "entity_tags": list(llm_metadata.get("entity_tags", metadata["entity_tags"]))[:12],
                    "representative_passages": list(llm_metadata.get("representative_passages", metadata["representative_passages"]))[:2],
                }
                self.summary_cache.set(section_key, metadata)
        return metadata

    def health(self) -> dict[str, Any]:
        available = False
        docs = 0
        schema_status = self.ensure_schema()
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
            "files_first_schema_version": schema_status.get("version", 0),
            "files_first_schema_compatible": bool(schema_status.get("compatible")),
            "files_first_schema_migrated": bool(schema_status.get("migrated")),
        }

    def reset(self) -> None:
        if self.store_path.exists():
            last_error: Exception | None = None
            for _ in range(5):
                try:
                    self.store_path.unlink()
                    return
                except PermissionError as exc:
                    last_error = exc
                    gc.collect()
                    time.sleep(0.1)
            if last_error is not None:
                raise last_error

    @staticmethod
    def _replace_file(target_path: Path, replacement_path: Path) -> None:
        last_error: Exception | None = None
        for _ in range(5):
            try:
                replacement_path.replace(target_path)
                return
            except PermissionError as exc:
                last_error = exc
                gc.collect()
                time.sleep(0.1)
        if last_error is not None:
            raise last_error

    def rebuild(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        target_path = self.store_path
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        with closing(sqlite3.connect(temp_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("CREATE TABLE files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute(
                "CREATE TABLE docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT, section_summary TEXT, topic_tags TEXT, entity_tags TEXT)"
            )
            conn.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
            )
            conn.execute(
                "CREATE TABLE sections (section_key TEXT PRIMARY KEY, book_name TEXT, chapter_title TEXT, source_file TEXT, file_path TEXT, page_number INTEGER, section_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, text TEXT)"
            )
            conn.execute(
                "CREATE VIRTUAL TABLE sections_fts USING fts5(section_key UNINDEXED, search_text, book_name, chapter_title, section_summary, topic_tags, entity_tags, representative_passages, text, tokenize='trigram')"
            )
            payload_rows: list[tuple[Any, ...]] = []
            fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
            section_parts: dict[str, dict[str, Any]] = {}
            for row in rows:
                chunk_id = str(row.get("chunk_id", "")).strip()
                if not chunk_id:
                    continue
                text = str(row.get("text", ""))
                filename = str(row.get("filename", ""))
                file_path = str(row.get("file_path", ""))
                page_number = int(row.get("page_number", 0) or 0)
                book_name = str(row.get("book_name", "")).strip() or extract_book_name(text=text, filename=filename, file_path=file_path)
                chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                section_key = str(row.get("section_key", "")).strip() or build_section_key(book_name=book_name, chapter_title=chapter_title, page_number=page_number, file_path=file_path)
                section_entry = section_parts.setdefault(
                    section_key or chunk_id,
                    {
                        "book_name": book_name,
                        "chapter_title": chapter_title,
                        "source_file": filename,
                        "file_path": _normalize_section_file_path(file_path),
                        "page_number": page_number,
                        "parts": [],
                    },
                )
                section_entry["parts"].append(text)
                metadata = self._resolve_section_metadata(
                    section_key=section_key or chunk_id,
                    book_name=book_name,
                    chapter_title=chapter_title,
                    section_text=text,
                )
                topic_tags_text = " ".join(metadata["topic_tags"])
                entity_tags_text = " ".join(metadata["entity_tags"])
                payload_rows.append((chunk_id, text, filename, str(row.get("file_type", "TXT")), file_path, page_number, int(row.get("chunk_idx", 0) or 0), str(row.get("parent_chunk_id", "")), str(row.get("root_chunk_id", "")), int(row.get("chunk_level", 0) or 0), book_name, chapter_title, section_key, metadata["section_summary"], topic_tags_text, entity_tags_text))
                search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
                search_text = " ".join(self.tokenizer.tokenize(search_basis))
                fts_rows.append((chunk_id, search_text, book_name, chapter_title, text, filename, file_path, metadata["section_summary"], topic_tags_text, entity_tags_text))
            section_rows: list[tuple[Any, ...]] = []
            section_fts_rows: list[tuple[Any, ...]] = []
            for section_key, payload in section_parts.items():
                section_text = merge_section_bodies([strip_classic_headers(item) for item in payload.get("parts", [])])
                metadata = self._resolve_section_metadata(
                    section_key=section_key,
                    book_name=str(payload.get("book_name", "")),
                    chapter_title=str(payload.get("chapter_title", "")),
                    section_text=section_text,
                )
                topic_tags_text = " ".join(metadata["topic_tags"])
                entity_tags_text = " ".join(metadata["entity_tags"])
                representative_text = " ".join(metadata["representative_passages"])
                section_rows.append(
                    (
                        section_key,
                        payload.get("book_name", ""),
                        payload.get("chapter_title", ""),
                        payload.get("source_file", ""),
                        payload.get("file_path", ""),
                        payload.get("page_number", 0),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        json.dumps(metadata["representative_passages"], ensure_ascii=False),
                        section_text,
                    )
                )
                section_search_basis = " ".join(
                    [
                        str(payload.get("book_name", "")),
                        str(payload.get("chapter_title", "")),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        representative_text,
                        section_text,
                    ]
                )
                section_fts_rows.append(
                    (
                        section_key,
                        " ".join(self.tokenizer.tokenize(section_search_basis)),
                        payload.get("book_name", ""),
                        payload.get("chapter_title", ""),
                        metadata["section_summary"],
                        topic_tags_text,
                        entity_tags_text,
                        representative_text,
                        section_text,
                    )
                )
            conn.execute(
                "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
            )
            conn.executemany("INSERT INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", payload_rows)
            conn.executemany("INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", fts_rows)
            conn.executemany("INSERT INTO sections (section_key, book_name, chapter_title, source_file, file_path, page_number, section_summary, topic_tags, entity_tags, representative_passages, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", section_rows)
            conn.executemany("INSERT INTO sections_fts (section_key, search_text, book_name, chapter_title, section_summary, topic_tags, entity_tags, representative_passages, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", section_fts_rows)
            conn.commit()
        self._replace_file(target_path, temp_path)
        return {"indexed_files_first_docs": len(fts_rows), "indexed_sections": len(section_rows), "files_first_index_path": str(self.store_path)}

    def search(self, *, query: str, top_k: int, candidate_k: int, leaf_level: int) -> tuple[list[dict[str, Any]], str]:
        self.ensure_schema()
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
            section_rows = []
            try:
                section_rows = conn.execute(
                    """
                    SELECT
                        s.section_key AS chunk_id,
                        s.text,s.source_file AS filename,'SECTION' AS file_type,s.file_path,s.page_number,
                        0 AS chunk_idx,'' AS parent_chunk_id,'' AS root_chunk_id,2 AS chunk_level,
                        s.book_name,s.chapter_title,s.section_key,s.section_summary,s.topic_tags,s.entity_tags,s.representative_passages,
                        snippet(sections_fts, 4, '[', ']', '...', 14) AS match_snippet,
                        bm25(sections_fts, 2.8, 2.5, 2.2, 1.8, 1.2, 1.2, 1.0, 0.8) AS rank_score
                    FROM sections_fts
                    JOIN sections s ON s.section_key = sections_fts.section_key
                    WHERE sections_fts MATCH ?
                    ORDER BY rank_score
                    LIMIT ?
                    """,
                    (match_query, max(2, min(candidate_k, max(top_k, 4)))),
                ).fetchall()
            except sqlite3.OperationalError:
                section_rows = []
            try:
                rows = conn.execute(
                    """
                    SELECT
                        d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                        '[]' AS representative_passages,
                        snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                        bm25(docs_fts, 2.5, 3.4, 2.6, 1.0, 0.25, 0.2, 1.4, 1.2, 1.2) AS rank_score
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
        section_rows = [dict(row) for row in section_rows]
        rows = [dict(row) for row in rows]
        if not section_rows and rows:
            synthetic_sections: dict[str, dict[str, Any]] = {}
            for row in rows:
                section_key = str(row.get("section_key") or row.get("chunk_id") or "").strip()
                if not section_key or section_key in synthetic_sections:
                    continue
                synthetic_sections[section_key] = {
                    **row,
                    "chunk_id": section_key,
                    "file_type": "SECTION",
                    "file_path": _normalize_section_file_path(str(row.get("file_path", ""))),
                    "chunk_level": 2,
                    "parent_chunk_id": "",
                    "root_chunk_id": "",
                }
            section_rows = list(synthetic_sections.values())
        results: list[dict[str, Any]] = []
        best_rows_by_section: dict[str, dict[str, Any]] = {}
        for row in list(section_rows) + list(rows):
            section_key = str(row["section_key"] or row["chunk_id"])
            existing = best_rows_by_section.get(section_key)
            if existing is None:
                best_rows_by_section[section_key] = row
                continue
            current_score = float(-(row["rank_score"]))
            existing_score = float(-(existing["rank_score"]))
            current_priority = 1 if str(row["file_type"]) == "SECTION" else 0
            existing_priority = 1 if str(existing["file_type"]) == "SECTION" else 0
            if (current_priority, current_score) > (existing_priority, existing_score):
                best_rows_by_section[section_key] = row
        merged_rows = list(best_rows_by_section.values())
        merged_rows.sort(
            key=lambda row: (
                1 if str(row["file_type"]) == "SECTION" else 0,
                float(-(row["rank_score"])),
            ),
            reverse=True,
        )
        for index, row in enumerate(merged_rows[:top_k], start=1):
            representative_passages = row["representative_passages"]
            try:
                parsed_representative_passages = json.loads(representative_passages) if isinstance(representative_passages, str) and representative_passages else []
            except json.JSONDecodeError:
                parsed_representative_passages = []
            results.append({"chunk_id": row["chunk_id"], "text": row["text"], "filename": row["filename"], "file_type": row["file_type"], "file_path": row["file_path"], "page_number": row["page_number"], "chunk_idx": row["chunk_idx"], "parent_chunk_id": row["parent_chunk_id"], "root_chunk_id": row["root_chunk_id"], "chunk_level": row["chunk_level"], "book_name": row["book_name"], "chapter_title": row["chapter_title"], "section_key": row["section_key"], "section_summary": row["section_summary"], "topic_tags": row["topic_tags"], "entity_tags": row["entity_tags"], "representative_passages": parsed_representative_passages, "match_snippet": row["match_snippet"], "score": float(-row["rank_score"]), "rrf_rank": index})
        retrieval_mode = "fts_local"
        return results, retrieval_mode

    def read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        self.ensure_schema()
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
                SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key,section_summary,topic_tags,entity_tags
                FROM docs
                WHERE book_name = ? AND chapter_title = ?
                ORDER BY chunk_level ASC, chunk_idx ASC, page_number ASC
                LIMIT ?
                """,
                (book_name, chapter_title, max(top_k, 64)),
            ).fetchall()
            try:
                section_meta = conn.execute(
                    """
                    SELECT section_summary,topic_tags,entity_tags,representative_passages,text
                    FROM sections
                    WHERE book_name = ? AND chapter_title = ?
                    LIMIT 1
                    """,
                    (book_name, chapter_title),
                ).fetchone()
            except sqlite3.OperationalError:
                section_meta = None
        items = [dict(row) for row in rows]
        if not items:
            return {"path": normalized, "items": [], "count": 0, "status": "empty"}
        response: dict[str, Any] = {"path": normalized, "status": "ok", "count": len(items), "items": items}
        if section_meta is not None:
            try:
                representative_passages = json.loads(section_meta["representative_passages"]) if section_meta["representative_passages"] else []
            except json.JSONDecodeError:
                representative_passages = []
            response["section"] = {
                "book_name": book_name,
                "chapter_title": chapter_title,
                "text": section_meta["text"],
                "source_file": items[0].get("filename", ""),
                "page_number": items[0].get("page_number", 0),
                "section_summary": section_meta["section_summary"],
                "topic_tags": str(section_meta["topic_tags"] or "").split(),
                "entity_tags": str(section_meta["entity_tags"] or "").split(),
                "representative_passages": representative_passages,
            }
        return response
