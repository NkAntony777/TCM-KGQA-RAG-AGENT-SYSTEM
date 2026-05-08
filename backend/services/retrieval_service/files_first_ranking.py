from __future__ import annotations

import json
from typing import Any, Callable

NormalizeSectionFilePathFn = Callable[[str], str]
FieldOverlapMultiplierFn = Callable[..., float]


def synthesize_sections_from_rows(
    *,
    section_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    normalize_section_file_path: NormalizeSectionFilePathFn,
) -> list[dict[str, Any]]:
    if section_rows or not rows:
        return section_rows
    synthetic_sections: dict[str, dict[str, Any]] = {}
    for row in rows:
        section_key = str(row.get("section_key") or row.get("chunk_id") or "").strip()
        if not section_key or section_key in synthetic_sections:
            continue
        synthetic_sections[section_key] = {
            **row,
            "chunk_id": section_key,
            "file_type": "SECTION",
            "file_path": normalize_section_file_path(str(row.get("file_path", ""))),
            "chunk_level": 2,
            "parent_chunk_id": "",
            "root_chunk_id": "",
            "_plan_rank": int(row.get("_plan_rank", 0) or 0),
        }
    return list(synthetic_sections.values())


def _prefer_current_row(current: dict[str, Any], existing: dict[str, Any]) -> bool:
    current_score = float(-(current["rank_score"]))
    existing_score = float(-(existing["rank_score"]))
    current_priority = 1 if str(current["file_type"]) == "SECTION" else 0
    existing_priority = 1 if str(existing["file_type"]) == "SECTION" else 0
    current_plan_rank = -int(current.get("_plan_rank", 0) or 0)
    existing_plan_rank = -int(existing.get("_plan_rank", 0) or 0)
    return (current_priority, current_plan_rank, current_score) > (
        existing_priority,
        existing_plan_rank,
        existing_score,
    )


def best_rows_by_section(
    *,
    section_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in list(section_rows) + list(rows):
        section_key = str(row["section_key"] or row["chunk_id"])
        existing = best.get(section_key)
        if existing is None or _prefer_current_row(row, existing):
            best[section_key] = row
    return list(best.values())


def narrow_rows_to_books(rows: list[dict[str, Any]], books_in_query: list[str]) -> list[dict[str, Any]]:
    if not books_in_query:
        return rows
    narrowed_rows = [
        row
        for row in rows
        if any(
            book
            and (
                book in str(row.get("book_name", "") or "")
                or str(row.get("book_name", "") or "") in book
            )
            for book in books_in_query
        )
    ]
    return narrowed_rows or rows


def _coverage(row: dict[str, Any], ranking_terms: list[str]) -> int:
    return sum(
        1
        for term in ranking_terms[:10]
        if term
        and (
            term in str(row.get("chapter_title", "") or "")
            or term in str(row.get("section_summary", "") or "")
            or term in str(row.get("entity_tags", "") or "")
            or term in str(row.get("text", "") or "")
        )
    )


def score_rows(
    *,
    rows: list[dict[str, Any]],
    focus_entities: list[str],
    books_in_query: list[str],
    ranking_terms: list[str],
    flags: dict[str, bool],
    field_overlap_multiplier: FieldOverlapMultiplierFn,
) -> list[tuple[float, dict[str, Any]]]:
    scored_rows: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        base_score = float(-(row["rank_score"]))
        multiplier = field_overlap_multiplier(
            row=row,
            focus_entities=focus_entities,
            books_in_query=books_in_query,
            query_terms=ranking_terms,
            flags=flags,
            plan_rank=int(row.get("_plan_rank", 0) or 0),
        )
        scored_rows.append((base_score * multiplier + _coverage(row, ranking_terms) * 0.001, row))
    scored_rows.sort(key=lambda item: item[0], reverse=True)
    return scored_rows


def format_ranked_results(
    *,
    scored_rows: list[tuple[float, dict[str, Any]]],
    top_k: int,
    normalize_section_file_path: NormalizeSectionFilePathFn,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, (final_score, row) in enumerate(scored_rows[:top_k], start=1):
        representative_passages = row["representative_passages"]
        try:
            parsed_representative_passages = json.loads(representative_passages) if isinstance(representative_passages, str) and representative_passages else []
        except json.JSONDecodeError:
            parsed_representative_passages = []
        raw_file_path = str(row["file_path"] or "")
        normalized_file_path = normalize_section_file_path(raw_file_path)
        normalized_chunk_level = 2 if normalized_file_path != raw_file_path else row["chunk_level"]
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "filename": row["filename"],
                "file_type": row["file_type"],
                "file_path": normalized_file_path,
                "page_number": row["page_number"],
                "chunk_idx": row["chunk_idx"],
                "parent_chunk_id": row["parent_chunk_id"],
                "root_chunk_id": row["root_chunk_id"],
                "chunk_level": normalized_chunk_level,
                "book_name": row["book_name"],
                "chapter_title": row["chapter_title"],
                "section_key": row["section_key"],
                "section_summary": row["section_summary"],
                "topic_tags": row["topic_tags"],
                "entity_tags": row["entity_tags"],
                "representative_passages": parsed_representative_passages,
                "match_snippet": row["match_snippet"],
                "score": final_score,
                "rrf_rank": index,
            }
        )
    return results


def rank_search_results(
    *,
    section_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    books_in_query: list[str],
    focus_entities: list[str],
    ranking_terms: list[str],
    flags: dict[str, bool],
    top_k: int,
    normalize_section_file_path: NormalizeSectionFilePathFn,
    field_overlap_multiplier: FieldOverlapMultiplierFn,
) -> list[dict[str, Any]]:
    effective_section_rows = synthesize_sections_from_rows(
        section_rows=section_rows,
        rows=rows,
        normalize_section_file_path=normalize_section_file_path,
    )
    merged_rows = best_rows_by_section(section_rows=effective_section_rows, rows=rows)
    merged_rows = narrow_rows_to_books(merged_rows, books_in_query)
    scored_rows = score_rows(
        rows=merged_rows,
        focus_entities=focus_entities,
        books_in_query=books_in_query,
        ranking_terms=ranking_terms,
        flags=flags,
        field_overlap_multiplier=field_overlap_multiplier,
    )
    return format_ranked_results(
        scored_rows=scored_rows,
        top_k=top_k,
        normalize_section_file_path=normalize_section_file_path,
    )
