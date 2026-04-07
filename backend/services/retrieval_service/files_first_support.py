from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


BOOK_LINE_PATTERN = re.compile(r"^古籍：(.+?)$", re.MULTILINE)
CHAPTER_LINE_PATTERN = re.compile(r"^篇名：(.+?)$", re.MULTILINE)
CLASSIC_PATH_PATTERN = re.compile(r"^classic://(?P<book>[^/]+)/(?P<section>\d{4})(?:-\d{2})?$")


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
    def __init__(self, store_path: Path, *, tokenizer):
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
                book_name = str(row.get("book_name", "")).strip() or extract_book_name(text=text, filename=filename, file_path=file_path)
                chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                section_key = str(row.get("section_key", "")).strip() or build_section_key(book_name=book_name, chapter_title=chapter_title, page_number=page_number, file_path=file_path)
                payload_rows.append((chunk_id, text, filename, str(row.get("file_type", "TXT")), file_path, page_number, int(row.get("chunk_idx", 0) or 0), str(row.get("parent_chunk_id", "")), str(row.get("root_chunk_id", "")), int(row.get("chunk_level", 0) or 0), book_name, chapter_title, section_key))
                search_basis = " ".join([book_name, chapter_title, filename, file_path, text])
                search_text = " ".join(self.tokenizer.tokenize(search_basis))
                fts_rows.append((chunk_id, search_text, book_name, chapter_title, text, filename, file_path))
            conn.executemany("INSERT INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", payload_rows)
            conn.executemany("INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path) VALUES (?, ?, ?, ?, ?, ?, ?)", fts_rows)
            conn.commit()
        return {"indexed_files_first_docs": len(fts_rows), "files_first_index_path": str(self.store_path)}

    def search(self, *, query: str, top_k: int, candidate_k: int, leaf_level: int) -> tuple[list[dict[str, Any]], str]:
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
                        d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,
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
            results.append({"chunk_id": row["chunk_id"], "text": row["text"], "filename": row["filename"], "file_type": row["file_type"], "file_path": row["file_path"], "page_number": row["page_number"], "chunk_idx": row["chunk_idx"], "parent_chunk_id": row["parent_chunk_id"], "root_chunk_id": row["root_chunk_id"], "chunk_level": row["chunk_level"], "book_name": row["book_name"], "chapter_title": row["chapter_title"], "section_key": row["section_key"], "match_snippet": row["match_snippet"], "score": float(-row["rank_score"]), "rrf_rank": index})
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
                SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key
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
        return {"path": normalized, "status": "ok", "count": len(items), "items": items}
