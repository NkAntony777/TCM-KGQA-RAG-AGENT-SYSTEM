from __future__ import annotations

from typing import Any

from services.retrieval_service import files_first_ranking


def _row(
    *,
    chunk_id: str,
    file_type: str,
    rank_score: float,
    book_name: str = "伤寒论",
    section_key: str = "伤寒论::0001",
    text: str = "小柴胡汤功效在和解少阳。",
    representative_passages: str = "[]",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "filename": f"{book_name}.txt",
        "file_type": file_type,
        "file_path": f"classic://{book_name}/0001",
        "page_number": 1,
        "chunk_idx": 1,
        "parent_chunk_id": "parent",
        "root_chunk_id": "root",
        "chunk_level": 3 if file_type != "SECTION" else 2,
        "book_name": book_name,
        "chapter_title": "卷上",
        "section_key": section_key,
        "section_summary": "小柴胡汤功效",
        "topic_tags": "功效",
        "entity_tags": "小柴胡汤",
        "representative_passages": representative_passages,
        "match_snippet": "小柴胡汤功效",
        "rank_score": rank_score,
        "_plan_rank": 0,
    }


def test_rank_search_results_prefers_section_row_for_same_section() -> None:
    results = files_first_ranking.rank_search_results(
        section_rows=[_row(chunk_id="section-1", file_type="SECTION", rank_score=-0.1, representative_passages='["原文"]')],
        rows=[_row(chunk_id="leaf-1", file_type="TXT", rank_score=-100.0)],
        books_in_query=[],
        focus_entities=["小柴胡汤"],
        ranking_terms=["小柴胡汤", "功效"],
        flags={},
        top_k=3,
        normalize_section_file_path=lambda path: path,
        field_overlap_multiplier=lambda **_: 1.0,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "section-1"
    assert results[0]["file_type"] == "SECTION"
    assert results[0]["representative_passages"] == ["原文"]
    assert results[0]["rrf_rank"] == 1


def test_rank_search_results_synthesizes_section_when_only_leaf_rows_exist() -> None:
    results = files_first_ranking.rank_search_results(
        section_rows=[],
        rows=[_row(chunk_id="leaf-1", file_type="TXT", rank_score=-1.0)],
        books_in_query=[],
        focus_entities=["小柴胡汤"],
        ranking_terms=["小柴胡汤"],
        flags={},
        top_k=3,
        normalize_section_file_path=lambda path: "chapter://伤寒论/卷上",
        field_overlap_multiplier=lambda **_: 1.0,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "伤寒论::0001"
    assert results[0]["file_type"] == "SECTION"
    assert results[0]["file_path"] == "chapter://伤寒论/卷上"
    assert results[0]["chunk_level"] == 2


def test_rank_search_results_narrows_to_requested_book_when_possible() -> None:
    results = files_first_ranking.rank_search_results(
        section_rows=[
            _row(chunk_id="section-1", file_type="SECTION", rank_score=-100.0, book_name="金匮要略", section_key="金匮要略::0001"),
            _row(chunk_id="section-2", file_type="SECTION", rank_score=-1.0, book_name="伤寒论", section_key="伤寒论::0001"),
        ],
        rows=[],
        books_in_query=["伤寒论"],
        focus_entities=[],
        ranking_terms=["伤寒论"],
        flags={},
        top_k=3,
        normalize_section_file_path=lambda path: path,
        field_overlap_multiplier=lambda **_: 1.0,
    )

    assert [item["book_name"] for item in results] == ["伤寒论"]
