from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from services.retrieval_service.nav_group_builder import build_nav_group_payload_from_rows

ProgressCallback = Callable[[int, int, str], None]


def load_nav_group_seed_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
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


def seed_manifest(seed_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "seed_rows": len(seed_rows),
        "books": len({str(row.get("book_name", "") or "").strip() for row in seed_rows if str(row.get("book_name", "") or "").strip()}),
        "sections": len({str(row.get("section_key", "") or "").strip() for row in seed_rows if str(row.get("section_key", "") or "").strip()}),
    }


def build_nav_group_payload(
    *,
    seed_rows: list[dict[str, Any]],
    summary_cache_path: Path,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    return build_nav_group_payload_from_rows(
        corpus_rows=seed_rows,
        summary_cache_path=summary_cache_path,
        progress_callback=progress_callback,
    )


def replace_nav_group_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
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
    return payload["manifest"]
