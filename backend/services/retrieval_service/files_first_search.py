from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Protocol

from services.retrieval_service import files_first_fts_queries
from services.retrieval_service import files_first_metadata
from services.retrieval_service import files_first_metadata_candidates
from services.retrieval_service import files_first_methods as ffm
from services.retrieval_service import files_first_ranking
from services.retrieval_service import files_first_search_plan
from services.retrieval_service import files_first_seed_queries


class FilesFirstSearchContext(Protocol):
    store_path: Path
    tokenizer: Any

    def ensure_schema(self) -> dict[str, Any]:
        ...


def search(
    context: FilesFirstSearchContext,
    *,
    query: str,
    query_context: dict[str, Any] | None = None,
    top_k: int,
    candidate_k: int,
    leaf_level: int,
    build_sqlite_in_clause: Callable[..., tuple[str, tuple[Any, ...]]] = ffm._build_sqlite_in_clause,
    is_noisy_term: Callable[[str], bool] = ffm._is_noisy_term,
    compact_phrase: Callable[[str], str] = ffm._compact_phrase,
    normalize_section_file_path: Callable[[str], str] = files_first_metadata.normalize_section_file_path,
    field_overlap_multiplier: Callable[..., float] = ffm._field_overlap_multiplier,
) -> tuple[list[dict[str, Any]], str]:
    context.ensure_schema()
    if not context.store_path.exists():
        return [], "fts_missing"
    effective_top_k = max(int(top_k or 0), 5)
    plan = files_first_search_plan.build_search_plan(
        query=query,
        tokenizer=context.tokenizer,
        query_context=query_context,
    )
    if not plan.match_queries:
        return [], "fts_query_empty"
    with closing(sqlite3.connect(context.store_path)) as conn:
        conn.row_factory = sqlite3.Row
        metadata_candidates = files_first_metadata_candidates.gather_metadata_candidates(
            conn,
            query=query,
            focus_entities=plan.focus_entities,
            query_terms=plan.ranking_terms,
            books_in_query=plan.books_in_query,
            flags=plan.flags,
            limit=max(candidate_k, effective_top_k * 2),
        )
        candidate_books = metadata_candidates["candidate_books"]
        candidate_groups = metadata_candidates["candidate_groups"]
        candidate_sections = metadata_candidates["candidate_sections"]
        direct_seed_map: dict[str, dict[str, Any]] = {}
        unique_sections: set[str] = set()
        if plan.direct_terms:
            target_books = files_first_search_plan.select_direct_seed_books(
                query=query,
                plan=plan,
                candidate_books=candidate_books,
            )
            direct_seed_map, direct_sections = files_first_seed_queries.run_direct_seed_queries(
                conn,
                direct_terms=plan.direct_terms,
                leaf_level=leaf_level,
                effective_top_k=effective_top_k,
                target_books=target_books,
                build_sqlite_in_clause=lambda values, alias, column: build_sqlite_in_clause(values, alias=alias, column=column),
                is_noisy_term=is_noisy_term,
            )
            unique_sections.update(direct_sections)
        if plan.descriptive_clauses:
            clause_target_books = files_first_search_plan.select_clause_seed_books(
                plan=plan,
                candidate_books=candidate_books,
            )
            direct_seed_map, clause_sections = files_first_seed_queries.run_clause_seed_queries(
                conn,
                descriptive_clauses=plan.descriptive_clauses,
                leaf_level=leaf_level,
                effective_top_k=effective_top_k,
                target_books=clause_target_books,
                direct_seed_map=direct_seed_map,
                unique_sections=unique_sections,
                build_sqlite_in_clause=lambda values, alias, column: build_sqlite_in_clause(values, alias=alias, column=column),
                compact_phrase=compact_phrase,
            )
            unique_sections.update(clause_sections)
        section_rows, rows, fts_sections, query_error = files_first_fts_queries.run_match_queries(
            conn,
            match_queries=plan.match_queries,
            leaf_level=leaf_level,
            candidate_sections=candidate_sections,
            candidate_books=candidate_books,
            candidate_groups=candidate_groups,
            candidate_k=candidate_k,
            effective_top_k=effective_top_k,
            build_sqlite_in_clause=lambda values, alias, column: build_sqlite_in_clause(values, alias=alias, column=column),
        )
        if query_error:
            return [], query_error
        unique_sections.update(fts_sections)
    if direct_seed_map:
        rows = [*direct_seed_map.values(), *rows]
    results = files_first_ranking.rank_search_results(
        section_rows=section_rows,
        rows=rows,
        books_in_query=plan.books_in_query,
        focus_entities=plan.focus_entities,
        ranking_terms=plan.ranking_terms,
        flags=plan.flags,
        top_k=top_k,
        normalize_section_file_path=normalize_section_file_path,
        field_overlap_multiplier=field_overlap_multiplier,
    )
    return results, "fts_local"
