from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any


def get_docs_by_chunk_ids(store: Any, chunk_ids: list[str]) -> list[dict[str, Any]]:
    store.ensure_schema()
    normalized_ids = [str(item or "").strip() for item in chunk_ids if str(item or "").strip()]
    if not normalized_ids or not store.store_path.exists():
        return []
    placeholders = ",".join("?" for _ in normalized_ids)
    with closing(sqlite3.connect(store.store_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT
                d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,
                d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                '[]' AS representative_passages,
                substr(d.text, 1, 180) AS match_snippet
            FROM docs d
            WHERE d.chunk_id IN ({placeholders})
            """,
            normalized_ids,
        ).fetchall()
    return [dict(row) for row in rows]


def read_section(store: Any, *, path: str, top_k: int = 12) -> dict[str, Any]:
    store.ensure_schema()
    if not store.store_path.exists():
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

    with closing(sqlite3.connect(store.store_path)) as conn:
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

    items = [dict(row) for row in rows]
    if not items:
        return {"path": normalized, "items": [], "count": 0, "status": "empty"}

    response: dict[str, Any] = {"path": normalized, "status": "ok", "count": len(items), "items": items}
    summary_key = str(items[0].get("section_key", "") or "").strip()
    cached = store.summary_cache.get(summary_key) if summary_key else None
    section_text = store.merge_section_bodies(
        [store.strip_classic_headers(str(item.get("text", ""))) for item in items]
    )
    if cached is None:
        cached = store._resolve_section_metadata(
            section_key=summary_key or f"{book_name}::{chapter_title}",
            book_name=book_name,
            chapter_title=chapter_title,
            section_text=section_text,
        )

    response["section"] = {
        "book_name": book_name,
        "chapter_title": chapter_title,
        "text": section_text,
        "source_file": items[0].get("filename", ""),
        "page_number": items[0].get("page_number", 0),
        "section_summary": str(cached.get("section_summary", "") if isinstance(cached, dict) else ""),
        "topic_tags": list(cached.get("topic_tags", []) if isinstance(cached, dict) else []),
        "entity_tags": list(cached.get("entity_tags", []) if isinstance(cached, dict) else []),
        "representative_passages": list(cached.get("representative_passages", []) if isinstance(cached, dict) else []),
    }
    return response
