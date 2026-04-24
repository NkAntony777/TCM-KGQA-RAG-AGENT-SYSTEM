from __future__ import annotations

import gc
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from services.retrieval_service import files_first_methods as ffm
from services.retrieval_service import files_first_metadata_candidates
from services.retrieval_service import files_first_query_context
from services.retrieval_service import files_first_reader
from services.retrieval_service import files_first_schema
from services.retrieval_service.nav_group_builder import build_nav_group_payload_from_rows
from services.retrieval_service import section_response
from services.retrieval_service.parent_chunk_store import ParentChunkStore
from services.retrieval_service.section_summary_cache import SectionSummaryCache

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
FILES_FIRST_SCHEMA_VERSION = 5
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


def _compose_section_preview(*, section_summary: str, representative_passages: list[str]) -> str:
    parts = [str(section_summary or "").strip()]
    parts.extend(str(item or "").strip() for item in representative_passages if str(item or "").strip())
    return "\n".join(part for part in parts if part).strip()


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _build_section_search_basis(
    *,
    book_name: str,
    chapter_title: str,
    section_summary: str,
    topic_tags_text: str,
    entity_tags_text: str,
    representative_text: str,
) -> str:
    return " ".join(
        [
            str(book_name or ""),
            str(chapter_title or ""),
            str(section_summary or ""),
            str(topic_tags_text or ""),
            str(entity_tags_text or ""),
            str(representative_text or ""),
        ]
    ).strip()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


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


# Query planning, candidate generation, and reranking methods are maintained in
# a dedicated module for easier explanation and safer iteration.
_query_flags = ffm._query_flags
_books_in_query = ffm._books_in_query
_db_books_in_query = ffm._db_books_in_query
_is_probable_herb_property_query = ffm._is_probable_herb_property_query
_extract_content_spans = ffm._extract_content_spans
_descriptive_clause_terms = ffm._descriptive_clause_terms
_leading_subject_terms = ffm._leading_subject_terms
_high_precision_direct_terms = ffm._high_precision_direct_terms
_strip_query_noise = ffm._strip_query_noise
_looks_like_entity = ffm._looks_like_entity
_contains_query_scaffolding = ffm._contains_query_scaffolding
_is_noisy_term = ffm._is_noisy_term
_is_front_matter_title = ffm._is_front_matter_title
_normalize_formula_match = ffm._normalize_formula_match
_expand_entity_aliases = ffm._expand_entity_aliases
_collapse_overlapping_terms = ffm._collapse_overlapping_terms
_sanitize_focus_entities = ffm._sanitize_focus_entities
_intent_terms = ffm._intent_terms
_clean_candidate_term = ffm._clean_candidate_term
_compact_phrase = ffm._compact_phrase
_tokenized_query_terms = ffm._tokenized_query_terms
_fts_quote = ffm._fts_quote
_join_match_terms = ffm._join_match_terms
_build_match_queries = ffm._build_match_queries
_gather_metadata_candidates = files_first_metadata_candidates.gather_metadata_candidates
_build_sqlite_in_clause = ffm._build_sqlite_in_clause
_field_overlap_multiplier = ffm._field_overlap_multiplier
_split_compare_entities = ffm._split_compare_entities
_entity_from_relation_query = ffm._entity_from_relation_query
_extract_focus_entities = ffm._extract_focus_entities
_prepare_match_terms = ffm._prepare_match_terms
FORMULA_SUFFIXES = ffm.FORMULA_SUFFIXES


def normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
    return section_response.normalize_chunk(
        item,
        extract_book_name=extract_book_name,
        extract_chapter_title=extract_chapter_title,
    )


def build_section_response(
    *,
    path: str,
    payload: dict[str, Any],
    parent_store: "ParentChunkStore",
) -> dict[str, Any]:
    return section_response.build_section_response(
        path=path,
        payload=payload,
        parent_store=parent_store,
        normalize_chunk_fn=normalize_chunk,
        strip_classic_headers=strip_classic_headers,
        merge_section_bodies=merge_section_bodies,
        build_section_metadata=_build_section_metadata,
    )


class LocalFilesFirstStore:
    def __init__(self, store_path: Path, *, tokenizer, summary_cache_path: Path | None = None, llm_summary_fn: Callable[[str, str, str], dict[str, Any]] | None = None):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.summary_cache = SectionSummaryCache(summary_cache_path)
        self.llm_summary_fn = llm_summary_fn
        self.strip_classic_headers = strip_classic_headers
        self.merge_section_bodies = merge_section_bodies

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
                compatible = (
                    doc_columns >= REQUIRED_DOC_COLUMNS
                    and "nav_groups" in tables
                    and "nav_groups_fts" in tables
                    and "book_outlines" in tables
                    and "book_outlines_fts" in tables
                    and meta_version >= FILES_FIRST_SCHEMA_VERSION
                )
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
            self.rebuild(base_rows, reset=True)
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
                "CREATE TABLE IF NOT EXISTS nav_groups (group_key TEXT PRIMARY KEY, book_name TEXT, archetype TEXT, group_title TEXT, group_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, question_types_supported TEXT, section_count INTEGER, leaf_count INTEGER, start_section_key TEXT, end_section_key TEXT, section_index_range TEXT, page_range TEXT, child_section_keys TEXT, child_titles TEXT)"
            )
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS nav_groups_fts USING fts5(group_key UNINDEXED, search_text)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS book_outlines (book_name TEXT PRIMARY KEY, archetype TEXT, book_summary TEXT, major_topics TEXT, major_entities TEXT, group_count INTEGER, section_count INTEGER, leaf_count INTEGER, group_keys TEXT, query_types_supported TEXT)"
            )
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS book_outlines_fts USING fts5(book_name UNINDEXED, search_text)")
            fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
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
            conn.executemany(
                "UPDATE docs SET book_name=?, chapter_title=?, section_key=?, section_summary=?, topic_tags=?, entity_tags=? WHERE chunk_id=?",
                update_rows,
            )
            conn.executemany(
                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                fts_rows,
            )
            self._ensure_post_docs_indexes(conn)
            self._rebuild_nav_groups(conn, show_progress=False)
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
            self._unlink_with_retry(self.store_path)

    @staticmethod
    def _unlink_with_retry(path: Path) -> None:
        last_error: Exception | None = None
        for _ in range(5):
            try:
                path.unlink(missing_ok=True)
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

    def _default_state_path(self) -> Path:
        return self.store_path.with_suffix(f"{self.store_path.suffix}.state.json")

    @staticmethod
    def _initialize_build_db(conn: sqlite3.Connection) -> None:
        files_first_schema.initialize_build_db(conn)

    @staticmethod
    def _ensure_post_docs_indexes(conn: sqlite3.Connection) -> None:
        files_first_schema.ensure_post_docs_indexes(conn)

    @staticmethod
    def _print_build_progress(*, stage: str, done: int, total: int, started_at: float) -> None:
        elapsed = max(0.1, time.perf_counter() - started_at)
        rate = done / elapsed if done > 0 else 0.0
        eta = (total - done) / rate if rate > 0 else 0.0
        print(
            f"[files-first:{stage}] {_progress_bar(done, total)} "
            f"{done}/{total} ({done * 100.0 / max(1, total):.1f}%) "
            f"rate={rate:.1f}/s eta={_format_seconds(eta)}",
            flush=True,
        )

    @staticmethod
    def _print_stage_banner(*, stage: str, detail: str) -> None:
        print(f"[files-first:{stage}] {detail}", flush=True)

    @staticmethod
    def _count_rows_in_db(path: Path) -> dict[str, int]:
        return files_first_schema.count_rows_in_db(path)

    @staticmethod
    def _load_nav_group_seed_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                chunk_id,
                chunk_level,
                book_name,
                chapter_title,
                section_key,
                page_number
            FROM docs
            WHERE trim(COALESCE(section_key, '')) <> ''
            ORDER BY book_name ASC, section_key ASC, page_number ASC, chunk_idx ASC, chunk_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _rebuild_nav_groups(self, conn: sqlite3.Connection, *, show_progress: bool) -> dict[str, Any]:
        if show_progress:
            self._print_stage_banner(stage="nav-groups", detail="building adaptive nav groups from section summaries")
        seed_rows = self._load_nav_group_seed_rows(conn)
        if show_progress:
            book_count = len({str(row.get("book_name", "") or "").strip() for row in seed_rows if str(row.get("book_name", "") or "").strip()})
            section_count = len({str(row.get("section_key", "") or "").strip() for row in seed_rows if str(row.get("section_key", "") or "").strip()})
            self._print_stage_banner(stage="nav-groups", detail=f"seed_rows={len(seed_rows)} books={book_count} sections={section_count}")
        last_reported = 0

        def _progress(current: int, total: int, _book_name: str) -> None:
            nonlocal last_reported
            if not show_progress or total <= 0:
                return
            if current != total and (current - last_reported) < 25:
                return
            last_reported = current
            self._print_build_progress(stage="nav-groups", done=current, total=total, started_at=docs_started_at)

        docs_started_at = time.perf_counter()
        payload = build_nav_group_payload_from_rows(
            corpus_rows=seed_rows,
            summary_cache_path=self.summary_cache.cache_path if self.summary_cache.cache_path is not None else Path(""),
            progress_callback=_progress if show_progress else None,
        )
        nav_groups = payload["nav_groups"]
        book_outlines = payload["book_outlines"]
        conn.execute("DELETE FROM nav_groups")
        conn.execute("DELETE FROM nav_groups_fts")
        conn.execute("DELETE FROM book_outlines")
        conn.execute("DELETE FROM book_outlines_fts")
        if nav_groups:
            conn.executemany(
                """
                INSERT INTO nav_groups (
                    group_key, book_name, archetype, group_title, group_summary, topic_tags, entity_tags,
                    representative_passages, question_types_supported, section_count, leaf_count,
                    start_section_key, end_section_key, section_index_range, page_range, child_section_keys, child_titles
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["group_key"],
                        item["book_name"],
                        item["archetype"],
                        item["group_title"],
                        item["group_summary"],
                        json.dumps(item["topic_tags"], ensure_ascii=False),
                        json.dumps(item["entity_tags"], ensure_ascii=False),
                        json.dumps(item["representative_passages"], ensure_ascii=False),
                        json.dumps(item["question_types_supported"], ensure_ascii=False),
                        int(item["section_count"]),
                        int(item["leaf_count"]),
                        item["start_section_key"],
                        item["end_section_key"],
                        json.dumps(item["section_index_range"], ensure_ascii=False),
                        json.dumps(item["page_range"], ensure_ascii=False),
                        json.dumps(item["child_section_keys"], ensure_ascii=False),
                        json.dumps(item["child_titles"], ensure_ascii=False),
                    )
                    for item in nav_groups
                ],
            )
            conn.executemany(
                "INSERT INTO nav_groups_fts (group_key, search_text) VALUES (?, ?)",
                [(item["group_key"], item["search_text"]) for item in nav_groups],
            )
        if book_outlines:
            conn.executemany(
                """
                INSERT INTO book_outlines (
                    book_name, archetype, book_summary, major_topics, major_entities,
                    group_count, section_count, leaf_count, group_keys, query_types_supported
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["book_name"],
                        item["archetype"],
                        item["book_summary"],
                        json.dumps(item["major_topics"], ensure_ascii=False),
                        json.dumps(item["major_entities"], ensure_ascii=False),
                        int(item["group_count"]),
                        int(item["section_count"]),
                        int(item["leaf_count"]),
                        json.dumps(item["group_keys"], ensure_ascii=False),
                        json.dumps(item["query_types_supported"], ensure_ascii=False),
                    )
                    for item in book_outlines
                ],
            )
            conn.executemany(
                "INSERT INTO book_outlines_fts (book_name, search_text) VALUES (?, ?)",
                [
                    (
                        item["book_name"],
                        " ".join(
                            [
                                item["book_name"],
                                item["book_summary"],
                                " ".join(item["major_topics"]),
                                " ".join(item["major_entities"]),
                                " ".join(item["query_types_supported"]),
                            ]
                        ).strip(),
                    )
                    for item in book_outlines
                ],
            )
        conn.commit()
        if show_progress:
            self._print_stage_banner(
                stage="nav-groups",
                detail=f"books={payload['manifest']['books']} nav_groups={payload['manifest']['nav_groups']} outlines={payload['manifest']['book_outlines']}",
            )
        return payload["manifest"]

    def rebuild(
        self,
        rows: list[dict[str, Any]],
        *,
        state_path: Path | None = None,
        reset: bool = False,
        show_progress: bool = False,
        batch_size: int = 512,
    ) -> dict[str, Any]:
        target_path = self.store_path
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        state_path = state_path or self._default_state_path()
        existing_target_counts = self._count_rows_in_db(target_path)
        reuse_existing_docs = (
            not reset
            and existing_target_counts["docs"] >= len(rows)
            and existing_target_counts["nav_groups"] <= 0
        )
        if reuse_existing_docs:
            state = {
                "status": "running_nav_groups",
                "temp_path": str(target_path),
                "target_path": str(target_path),
                "total_rows": len(rows),
                "docs_processed": len(rows),
                "nav_groups_built": 0,
                "updated_at": time.time(),
                "reused_existing_docs": True,
            }
            _write_json(state_path, state)
            with closing(sqlite3.connect(target_path)) as conn:
                self._initialize_build_db(conn)
                if show_progress:
                    self._print_stage_banner(stage="docs", detail=f"reusing existing docs rows={existing_target_counts['docs']}")
                    self._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
                self._ensure_post_docs_indexes(conn)
                nav_manifest = self._rebuild_nav_groups(conn, show_progress=show_progress)
                state.update({"status": "running_nav_groups", "nav_groups_built": int(nav_manifest.get("nav_groups", 0)), "updated_at": time.time()})
                _write_json(state_path, state)
                conn.execute(
                    "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
                )
                conn.commit()
            state.update(
                {
                    "status": "completed",
                    "docs_processed": len(rows),
                    "nav_groups_built": int(nav_manifest.get("nav_groups", 0)),
                    "completed_at": time.time(),
                    "updated_at": time.time(),
                    "reused_existing_docs": True,
                }
            )
            _write_json(state_path, state)
            return {
                "indexed_files_first_docs": len(rows),
                "indexed_nav_groups": int(nav_manifest.get("nav_groups", 0)),
                "indexed_sections": int(nav_manifest.get("nav_groups", 0)),
                "files_first_index_path": str(self.store_path),
                "state_path": str(state_path),
                "resumed": True,
                "reused_existing_docs": True,
            }
        if reset:
            if temp_path.exists():
                self._unlink_with_retry(temp_path)
            if state_path.exists():
                self._unlink_with_retry(state_path)
        state = _read_json(state_path, {})
        if not isinstance(state, dict):
            state = {}
        resume_ready = (
            bool(state)
            and str(state.get("temp_path", "")) == str(temp_path)
            and temp_path.exists()
            and state.get("status") in {"running_docs", "running_nav_groups", "interrupted", "failed"}
            and int(state.get("total_rows", 0) or 0) == len(rows)
        )
        if not resume_ready and temp_path.exists():
            self._unlink_with_retry(temp_path)
        if not resume_ready:
            with closing(sqlite3.connect(temp_path)) as conn:
                self._initialize_build_db(conn)
            state = {
                "status": "running_docs",
                "temp_path": str(temp_path),
                "target_path": str(target_path),
                "total_rows": len(rows),
                "docs_processed": 0,
                "nav_groups_built": 0,
                "updated_at": time.time(),
            }
            _write_json(state_path, state)

        batch_size = max(64, int(batch_size or 512))
        docs_started_at = time.perf_counter()
        try:
            with closing(sqlite3.connect(temp_path)) as conn:
                self._initialize_build_db(conn)
                docs_processed = int(state.get("docs_processed", 0) or 0)
                if docs_processed < len(rows):
                    payload_rows: list[tuple[Any, ...]] = []
                    fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
                    for index in range(docs_processed, len(rows)):
                        row = rows[index]
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
                        metadata = self._resolve_section_metadata(
                            section_key=section_key or chunk_id,
                            book_name=book_name,
                            chapter_title=chapter_title,
                            section_text=text,
                        )
                        topic_tags_text = " ".join(metadata["topic_tags"])
                        entity_tags_text = " ".join(metadata["entity_tags"])
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
                                metadata["section_summary"],
                                topic_tags_text,
                                entity_tags_text,
                            )
                        )
                        search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
                        fts_rows.append(
                            (
                                chunk_id,
                                " ".join(self.tokenizer.tokenize(search_basis)),
                                book_name,
                                chapter_title,
                                text,
                                filename,
                                file_path,
                                metadata["section_summary"],
                                topic_tags_text,
                                entity_tags_text,
                            )
                        )
                        if len(payload_rows) >= batch_size:
                            conn.executemany(
                                "INSERT OR REPLACE INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                payload_rows,
                            )
                            conn.executemany(
                                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                fts_rows,
                            )
                            conn.commit()
                            docs_processed = index + 1
                            state.update({"status": "running_docs", "docs_processed": docs_processed, "updated_at": time.time()})
                            _write_json(state_path, state)
                            if show_progress:
                                self._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=docs_started_at)
                            payload_rows = []
                            fts_rows = []
                    if payload_rows:
                        conn.executemany(
                            "INSERT OR REPLACE INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            payload_rows,
                        )
                        conn.executemany(
                            "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            fts_rows,
                        )
                        conn.commit()
                        docs_processed = len(rows)
                        state.update({"status": "running_docs", "docs_processed": docs_processed, "updated_at": time.time()})
                        _write_json(state_path, state)
                        if show_progress:
                            self._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=docs_started_at)

                if show_progress:
                    self._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
                self._ensure_post_docs_indexes(conn)
                state.update({"status": "running_nav_groups", "docs_processed": len(rows), "updated_at": time.time()})
                _write_json(state_path, state)
                nav_manifest = self._rebuild_nav_groups(conn, show_progress=show_progress)
                state.update({"status": "running_nav_groups", "nav_groups_built": int(nav_manifest.get("nav_groups", 0)), "updated_at": time.time()})
                _write_json(state_path, state)
                conn.execute(
                    "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
                )
                conn.commit()
        except KeyboardInterrupt:
            state.update({"status": "interrupted", "updated_at": time.time()})
            _write_json(state_path, state)
            raise
        except Exception as exc:
            state.update({"status": "failed", "last_error": str(exc), "updated_at": time.time()})
            _write_json(state_path, state)
            raise
        self._replace_file(target_path, temp_path)
        state.update(
            {
                "status": "completed",
                "docs_processed": len(rows),
                "nav_groups_built": int(nav_manifest.get("nav_groups", 0) if 'nav_manifest' in locals() else 0),
                "completed_at": time.time(),
                "updated_at": time.time(),
            }
        )
        _write_json(state_path, state)
        return {
            "indexed_files_first_docs": len(rows),
            "indexed_nav_groups": int(nav_manifest.get("nav_groups", 0) if 'nav_manifest' in locals() else 0),
            "indexed_sections": int(nav_manifest.get("nav_groups", 0) if 'nav_manifest' in locals() else 0),
            "files_first_index_path": str(self.store_path),
            "state_path": str(state_path),
            "resumed": bool(resume_ready),
        }

    def search(self, *, query: str, query_context: dict[str, Any] | None = None, top_k: int, candidate_k: int, leaf_level: int) -> tuple[list[dict[str, Any]], str]:
        self.ensure_schema()
        if not self.store_path.exists():
            return [], "fts_missing"
        effective_top_k = max(int(top_k or 0), 5)
        flags, focus_entities, books_in_query, expanded_query, weak_anchor, need_broad_recall = files_first_query_context.apply_query_context(
            query=query,
            tokenizer=self.tokenizer,
            query_context=query_context,
        )
        focus_search_terms = _sanitize_focus_entities(_expand_entity_aliases(focus_entities))
        alias_terms = [term for term in focus_search_terms if term not in focus_entities]
        auxiliary_terms = _intent_terms(flags)
        primary_terms = list(dict.fromkeys([*focus_entities, *books_in_query]))
        expanded_terms = _tokenized_query_terms(expanded_query, self.tokenizer, limit=10) if expanded_query else []
        fallback_terms = alias_terms if alias_terms else ([] if primary_terms else _prepare_match_terms(query, self.tokenizer))
        if expanded_terms:
            fallback_terms = list(dict.fromkeys([*fallback_terms, *expanded_terms]))
        ranking_terms = list(dict.fromkeys([*focus_entities, *books_in_query, *fallback_terms, *auxiliary_terms]))
        if not primary_terms:
            primary_terms = _tokenized_query_terms(query, self.tokenizer, limit=8)
            if not fallback_terms:
                fallback_terms = _prepare_match_terms(query, self.tokenizer)
            ranking_terms = list(dict.fromkeys([*primary_terms, *fallback_terms, *auxiliary_terms]))
        match_queries = _build_match_queries(
            primary_terms=primary_terms,
            auxiliary_terms=auxiliary_terms,
            fallback_terms=fallback_terms,
            flags=flags,
        )
        if not match_queries:
            return [], "fts_query_empty"
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            metadata_candidates = _gather_metadata_candidates(
                conn,
                query=query,
                focus_entities=focus_entities,
                query_terms=ranking_terms,
                books_in_query=books_in_query,
                flags=flags,
                limit=max(candidate_k, effective_top_k * 2),
            )
            candidate_books = metadata_candidates["candidate_books"]
            candidate_groups = metadata_candidates["candidate_groups"]
            candidate_sections = metadata_candidates["candidate_sections"]
            section_rows: list[dict[str, Any]] = []
            rows: list[dict[str, Any]] = []
            direct_seed_map: dict[str, dict[str, Any]] = {}
            section_limit = max(6, min(candidate_k * 2, max(effective_top_k * 2, 12)))
            leaf_limit = max(candidate_k * 2, effective_top_k * 2)
            unique_sections: set[str] = set()
            descriptive_clauses = [
                item
                for item in _descriptive_clause_terms(expanded_query or query)
                if (2 if books_in_query else 3) <= len(str(item or "").strip()) <= 16
            ]
            direct_terms_seed = [] if weak_anchor or need_broad_recall else _high_precision_direct_terms(expanded_query or query)
            direct_terms = list(
                dict.fromkeys(
                    [
                        *direct_terms_seed,
                        *[
                            item
                            for item in focus_entities
                            if item
                            and not _is_noisy_term(item)
                            and (
                                _looks_like_entity(item)
                                or item.endswith(("病", "证"))
                                or len(item) <= 8
                            )
                        ],
                    ]
                )
            )
            if direct_terms:
                docs_book_filter_sql = ""
                docs_book_filter_params: tuple[Any, ...] = ()
                has_strong_direct_anchor = any(
                    item.endswith(FORMULA_SUFFIXES) or item.endswith(("病", "证")) or len(item) <= 4
                    for item in direct_terms
                )
                if books_in_query:
                    target_books = books_in_query[:8]
                elif _is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
                    target_books = [book for book in candidate_books[:8] if "本草" in str(book)]
                elif has_strong_direct_anchor and not need_broad_recall:
                    target_books = []
                else:
                    target_books = candidate_books[:8]
                if target_books:
                    docs_book_filter_sql, docs_book_filter_params = _build_sqlite_in_clause(target_books, alias="d", column="book_name")
                for direct_term in direct_terms[:10]:
                    normalized_term = str(direct_term or "").strip()
                    if len(normalized_term) < 2 or _is_noisy_term(normalized_term):
                        continue
                    try:
                        current_direct = conn.execute(
                            f"""
                            SELECT
                                d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                                '[]' AS representative_passages,
                                substr(d.text, 1, 180) AS match_snippet,
                                -40.0 AS rank_score
                            FROM docs d
                            WHERE d.chunk_level = ?
                              AND (
                                    d.chapter_title = ?
                                 OR instr(d.chapter_title, ?) > 0
                                 OR instr(d.entity_tags, ?) > 0
                                 OR (? != '' AND length(?) >= 3 AND instr(d.text, ?) > 0)
                              ){docs_book_filter_sql}
                            ORDER BY
                                CASE WHEN d.chapter_title = ? THEN 0 ELSE 1 END,
                                CASE WHEN instr(d.chapter_title, ?) > 0 THEN 0 ELSE 1 END,
                                CASE WHEN instr(d.entity_tags, ?) > 0 THEN 0 ELSE 1 END,
                                d.book_name ASC,
                                d.page_number ASC,
                                d.chunk_idx ASC
                            LIMIT ?
                            """,
                            (
                                leaf_level,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                *docs_book_filter_params,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                max(effective_top_k * 2, 8),
                            ),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        current_direct = []
                    for row in current_direct:
                        payload = dict(row)
                        payload["_plan_rank"] = 0
                        payload["_direct_clause_hits"] = 0
                        direct_seed_map[str(payload.get("chunk_id") or "")] = payload
                        section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                        if section_key:
                            unique_sections.add(section_key)
            if descriptive_clauses:
                clause_book_filter_sql = ""
                clause_book_filter_params: tuple[Any, ...] = ()
                clause_target_books = books_in_query[:8] if books_in_query else candidate_books[:8]
                if clause_target_books:
                    clause_book_filter_sql, clause_book_filter_params = _build_sqlite_in_clause(clause_target_books, alias="d", column="book_name")
                for clause in descriptive_clauses[:8]:
                    normalized_clause = str(clause or "").strip()
                    if len(normalized_clause) < 3:
                        continue
                    compact_clause = _compact_phrase(normalized_clause)
                    try:
                        clause_rows = conn.execute(
                            f"""
                            SELECT
                                d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                                '[]' AS representative_passages,
                                substr(d.text, 1, 180) AS match_snippet,
                                -35.0 AS rank_score
                            FROM docs d
                            WHERE d.chunk_level = ?
                              AND (
                                    instr(d.chapter_title, ?) > 0
                                 OR instr(d.section_summary, ?) > 0
                                 OR instr(d.text, ?) > 0
                                 OR (? != '' AND length(?) >= 4 AND instr(
                                        replace(replace(replace(replace(replace(replace(replace(d.text, '，', ''), '。', ''), '、', ''), ' ', ''), '：', ''), '；', ''), '（', ''),
                                        ?
                                    ) > 0)
                              ){clause_book_filter_sql}
                            LIMIT ?
                            """,
                            (
                                leaf_level,
                                normalized_clause,
                                normalized_clause,
                                normalized_clause,
                                compact_clause,
                                compact_clause,
                                compact_clause,
                                *clause_book_filter_params,
                                max(effective_top_k * 2, 8),
                            ),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        clause_rows = []
                    for row in clause_rows:
                        payload = dict(row)
                        chunk_id = str(payload.get("chunk_id") or "").strip()
                        if not chunk_id:
                            continue
                        existing_payload = direct_seed_map.get(chunk_id)
                        if existing_payload is None:
                            payload["_plan_rank"] = 0
                            payload["_direct_clause_hits"] = 1
                            direct_seed_map[chunk_id] = payload
                        else:
                            existing_payload["_direct_clause_hits"] = int(existing_payload.get("_direct_clause_hits", 0) or 0) + 1
                        section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                        if section_key:
                            unique_sections.add(section_key)
            for plan_rank, match_query in enumerate(match_queries):
                section_filter_sql = ""
                section_filter_params: tuple[Any, ...] = ()
                docs_filter_sql = ""
                docs_filter_params: tuple[Any, ...] = ()
                if candidate_sections:
                    docs_filter_sql, docs_filter_params = _build_sqlite_in_clause(candidate_sections[:96], alias="d", column="section_key")
                elif candidate_books:
                    docs_filter_sql, docs_filter_params = _build_sqlite_in_clause(candidate_books[:8], alias="d", column="book_name")
                if candidate_groups:
                    section_filter_sql, section_filter_params = _build_sqlite_in_clause(candidate_groups[:96], alias="n", column="group_key")
                elif candidate_books:
                    section_filter_sql, section_filter_params = _build_sqlite_in_clause(candidate_books[:8], alias="n", column="book_name")
                try:
                    current_sections = conn.execute(
                        f"""
                        SELECT
                            n.group_key AS chunk_id,
                            trim(COALESCE(n.group_summary, '') || ' ' || COALESCE(n.representative_passages, '')) AS text,
                            n.book_name AS filename,'NAV_GROUP' AS file_type,'classic://' || n.book_name || '/nav-group-' || replace(substr(n.group_key, instr(n.group_key, '::nav::') + 7), '::', '-') AS file_path,0 AS page_number,
                            0 AS chunk_idx,'' AS parent_chunk_id,'' AS root_chunk_id,1 AS chunk_level,
                            n.book_name,n.group_title AS chapter_title,n.group_key AS section_key,n.group_summary AS section_summary,n.topic_tags,n.entity_tags,n.representative_passages,
                            substr(COALESCE(n.group_summary, n.group_title, ''), 1, 160) AS match_snippet,
                            bm25(nav_groups_fts) AS rank_score
                        FROM nav_groups_fts
                        JOIN nav_groups n ON n.group_key = nav_groups_fts.group_key
                        WHERE nav_groups_fts MATCH ?{section_filter_sql}
                        ORDER BY rank_score
                        LIMIT ?
                        """,
                        (match_query, *section_filter_params, section_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    current_sections = []
                try:
                    current_rows = conn.execute(
                        f"""
                        SELECT
                            d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                            '[]' AS representative_passages,
                            snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                            bm25(docs_fts, 2.5, 3.4, 2.6, 1.0, 0.25, 0.2, 1.4, 1.2, 1.2) AS rank_score
                        FROM docs_fts
                        JOIN docs d ON d.chunk_id = docs_fts.chunk_id
                        WHERE docs_fts MATCH ? AND d.chunk_level = ?{docs_filter_sql}
                        ORDER BY rank_score
                        LIMIT ?
                        """,
                        (match_query, leaf_level, *docs_filter_params, leaf_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    current_rows = []
                if not current_sections and not current_rows and plan_rank == 0 and len(match_queries) == 1:
                    return [], "fts_query_error"
                for row in current_sections:
                    payload = dict(row)
                    payload["_plan_rank"] = plan_rank
                    section_rows.append(payload)
                    section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                    if section_key:
                        unique_sections.add(section_key)
                for row in current_rows:
                    payload = dict(row)
                    payload["_plan_rank"] = plan_rank
                    rows.append(payload)
                    section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                    if section_key:
                        unique_sections.add(section_key)
                if plan_rank == 0 and len(unique_sections) >= max(effective_top_k * 2, min(candidate_k * 2, effective_top_k * 2)):
                    break
                if len(unique_sections) >= max(effective_top_k * 2, candidate_k * 2):
                    break
        if direct_seed_map:
            rows = [*direct_seed_map.values(), *rows]
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
                    "_plan_rank": int(row.get("_plan_rank", 0) or 0),
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
            current_plan_rank = -int(row.get("_plan_rank", 0) or 0)
            existing_plan_rank = -int(existing.get("_plan_rank", 0) or 0)
            if (current_priority, current_plan_rank, current_score) > (existing_priority, existing_plan_rank, existing_score):
                best_rows_by_section[section_key] = row
        merged_rows = list(best_rows_by_section.values())
        if books_in_query:
            narrowed_rows = [
                row
                for row in merged_rows
                if any(
                    book and (
                        book in str(row.get("book_name", "") or "")
                        or str(row.get("book_name", "") or "") in book
                    )
                    for book in books_in_query
                )
            ]
            if narrowed_rows:
                merged_rows = narrowed_rows
        scored_rows: list[tuple[float, dict[str, Any]]] = []
        for row in merged_rows:
            base_score = float(-(row["rank_score"]))
            multiplier = _field_overlap_multiplier(
                row=row,
                focus_entities=focus_entities,
                books_in_query=books_in_query,
                query_terms=ranking_terms,
                flags=flags,
                plan_rank=int(row.get("_plan_rank", 0) or 0),
            )
            tie_break_coverage = sum(
                1
                for term in ranking_terms[:10]
                if term and (
                    term in str(row.get("chapter_title", "") or "")
                    or term in str(row.get("section_summary", "") or "")
                    or term in str(row.get("entity_tags", "") or "")
                    or term in str(row.get("text", "") or "")
                )
            )
            scored_rows.append((base_score * multiplier + tie_break_coverage * 0.001, row))
        scored_rows.sort(key=lambda item: item[0], reverse=True)
        for index, (final_score, row) in enumerate(scored_rows[:top_k], start=1):
            representative_passages = row["representative_passages"]
            try:
                parsed_representative_passages = json.loads(representative_passages) if isinstance(representative_passages, str) and representative_passages else []
            except json.JSONDecodeError:
                parsed_representative_passages = []
            raw_file_path = str(row["file_path"] or "")
            normalized_file_path = _normalize_section_file_path(raw_file_path)
            normalized_chunk_level = 2 if normalized_file_path != raw_file_path else row["chunk_level"]
            results.append({"chunk_id": row["chunk_id"], "text": row["text"], "filename": row["filename"], "file_type": row["file_type"], "file_path": normalized_file_path, "page_number": row["page_number"], "chunk_idx": row["chunk_idx"], "parent_chunk_id": row["parent_chunk_id"], "root_chunk_id": row["root_chunk_id"], "chunk_level": normalized_chunk_level, "book_name": row["book_name"], "chapter_title": row["chapter_title"], "section_key": row["section_key"], "section_summary": row["section_summary"], "topic_tags": row["topic_tags"], "entity_tags": row["entity_tags"], "representative_passages": parsed_representative_passages, "match_snippet": row["match_snippet"], "score": final_score, "rrf_rank": index})
        retrieval_mode = "fts_local"
        return results, retrieval_mode

    def get_docs_by_chunk_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        return files_first_reader.get_docs_by_chunk_ids(self, chunk_ids)

    def read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        return files_first_reader.read_section(self, path=path, top_k=top_k)
