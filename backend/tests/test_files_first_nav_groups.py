from __future__ import annotations

import json

from services.retrieval_service import files_first_nav_groups
from services.retrieval_service import files_first_schema
from tests.test_temp_utils import connect_test_sqlite
from tests.test_temp_utils import make_test_dir


def test_nav_group_seed_manifest_counts_books_and_sections() -> None:
    manifest = files_first_nav_groups.seed_manifest(
        [
            {"book_name": "伤寒论", "section_key": "伤寒论::0001"},
            {"book_name": "伤寒论", "section_key": "伤寒论::0002"},
            {"book_name": "金匮要略", "section_key": "金匮要略::0001"},
            {"book_name": "", "section_key": ""},
        ]
    )

    assert manifest == {"seed_rows": 4, "books": 2, "sections": 3}


def test_replace_nav_group_payload_writes_nav_groups_and_book_outlines() -> None:
    tmp_path = make_test_dir("files_first_nav_groups")
    db_path = tmp_path / "files_first.db"
    with connect_test_sqlite(db_path) as conn:
        files_first_schema.initialize_build_db(conn)
        payload = {
            "manifest": {"books": 1, "nav_groups": 1, "book_outlines": 1},
            "nav_groups": [
                {
                    "group_key": "伤寒论::nav::0001",
                    "book_name": "伤寒论",
                    "archetype": "classic",
                    "group_title": "太阳病",
                    "group_summary": "太阳病相关条文",
                    "topic_tags": ["条文"],
                    "entity_tags": ["小柴胡汤"],
                    "representative_passages": ["小柴胡汤主治往来寒热"],
                    "question_types_supported": ["source_quote"],
                    "section_count": 1,
                    "leaf_count": 2,
                    "start_section_key": "伤寒论::0001",
                    "end_section_key": "伤寒论::0001",
                    "section_index_range": [1, 1],
                    "page_range": [1, 1],
                    "child_section_keys": ["伤寒论::0001"],
                    "child_titles": ["卷上"],
                    "search_text": "伤寒论 太阳病 小柴胡汤",
                }
            ],
            "book_outlines": [
                {
                    "book_name": "伤寒论",
                    "archetype": "classic",
                    "book_summary": "伤寒论概要",
                    "major_topics": ["条文"],
                    "major_entities": ["小柴胡汤"],
                    "group_count": 1,
                    "section_count": 1,
                    "leaf_count": 2,
                    "group_keys": ["伤寒论::nav::0001"],
                    "query_types_supported": ["source_quote"],
                }
            ],
        }

        manifest = files_first_nav_groups.replace_nav_group_payload(conn, payload)
        nav_row = conn.execute("SELECT topic_tags, child_section_keys FROM nav_groups").fetchone()
        outline_row = conn.execute("SELECT major_entities, group_keys FROM book_outlines").fetchone()
        nav_fts_count = conn.execute("SELECT COUNT(1) FROM nav_groups_fts").fetchone()[0]
        outline_fts_count = conn.execute("SELECT COUNT(1) FROM book_outlines_fts").fetchone()[0]

    assert manifest == {"books": 1, "nav_groups": 1, "book_outlines": 1}
    assert json.loads(nav_row[0]) == ["条文"]
    assert json.loads(nav_row[1]) == ["伤寒论::0001"]
    assert json.loads(outline_row[0]) == ["小柴胡汤"]
    assert json.loads(outline_row[1]) == ["伤寒论::nav::0001"]
    assert nav_fts_count == 1
    assert outline_fts_count == 1
