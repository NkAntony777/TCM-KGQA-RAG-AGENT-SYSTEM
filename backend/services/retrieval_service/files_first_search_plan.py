from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.retrieval_service import files_first_methods as ffm
from services.retrieval_service import files_first_query_context


@dataclass(frozen=True)
class FilesFirstSearchPlan:
    flags: dict[str, bool]
    focus_entities: list[str]
    books_in_query: list[str]
    expanded_query: str
    weak_anchor: bool
    need_broad_recall: bool
    auxiliary_terms: list[str]
    primary_terms: list[str]
    fallback_terms: list[str]
    ranking_terms: list[str]
    match_queries: list[str]
    descriptive_clauses: list[str]
    direct_terms: list[str]


def build_search_plan(
    *,
    query: str,
    tokenizer: Any,
    query_context: dict[str, Any] | None,
) -> FilesFirstSearchPlan:
    flags, focus_entities, books_in_query, expanded_query, weak_anchor, need_broad_recall = files_first_query_context.apply_query_context(
        query=query,
        tokenizer=tokenizer,
        query_context=query_context,
    )
    focus_search_terms = ffm._sanitize_focus_entities(ffm._expand_entity_aliases(focus_entities))
    alias_terms = [term for term in focus_search_terms if term not in focus_entities]
    auxiliary_terms = ffm._intent_terms(flags)
    primary_terms = list(dict.fromkeys([*focus_entities, *books_in_query]))
    expanded_terms = ffm._tokenized_query_terms(expanded_query, tokenizer, limit=10) if expanded_query else []
    fallback_terms = alias_terms if alias_terms else ([] if primary_terms else ffm._prepare_match_terms(query, tokenizer))
    if expanded_terms:
        fallback_terms = list(dict.fromkeys([*fallback_terms, *expanded_terms]))
    ranking_terms = list(dict.fromkeys([*focus_entities, *books_in_query, *fallback_terms, *auxiliary_terms]))
    if not primary_terms:
        primary_terms = ffm._tokenized_query_terms(query, tokenizer, limit=8)
        if not fallback_terms:
            fallback_terms = ffm._prepare_match_terms(query, tokenizer)
        ranking_terms = list(dict.fromkeys([*primary_terms, *fallback_terms, *auxiliary_terms]))
    match_queries = ffm._build_match_queries(
        primary_terms=primary_terms,
        auxiliary_terms=auxiliary_terms,
        fallback_terms=fallback_terms,
        flags=flags,
    )
    descriptive_clauses = [
        item
        for item in ffm._descriptive_clause_terms(expanded_query or query)
        if (2 if books_in_query else 3) <= len(str(item or "").strip()) <= 16
    ]
    direct_terms_seed = [] if weak_anchor or need_broad_recall else ffm._high_precision_direct_terms(expanded_query or query)
    direct_terms = list(
        dict.fromkeys(
            [
                *direct_terms_seed,
                *[
                    item
                    for item in focus_entities
                    if item
                    and not ffm._is_noisy_term(item)
                    and (
                        ffm._looks_like_entity(item)
                        or item.endswith(("病", "证"))
                        or len(item) <= 8
                    )
                ],
            ]
        )
    )
    return FilesFirstSearchPlan(
        flags=flags,
        focus_entities=focus_entities,
        books_in_query=books_in_query,
        expanded_query=expanded_query,
        weak_anchor=weak_anchor,
        need_broad_recall=need_broad_recall,
        auxiliary_terms=auxiliary_terms,
        primary_terms=primary_terms,
        fallback_terms=fallback_terms,
        ranking_terms=ranking_terms,
        match_queries=match_queries,
        descriptive_clauses=descriptive_clauses,
        direct_terms=direct_terms,
    )


def select_direct_seed_books(
    *,
    query: str,
    plan: FilesFirstSearchPlan,
    candidate_books: list[str],
) -> list[str]:
    has_strong_direct_anchor = any(
        item.endswith(ffm.FORMULA_SUFFIXES) or item.endswith(("病", "证")) or len(item) <= 4
        for item in plan.direct_terms
    )
    if plan.books_in_query:
        return plan.books_in_query[:8]
    if ffm._is_probable_herb_property_query(
        query=query,
        focus_entities=plan.focus_entities,
        flags=plan.flags,
        books_in_query=plan.books_in_query,
    ):
        return [book for book in candidate_books[:8] if "本草" in str(book)]
    if has_strong_direct_anchor and not plan.need_broad_recall:
        return []
    return candidate_books[:8]


def select_clause_seed_books(
    *,
    plan: FilesFirstSearchPlan,
    candidate_books: list[str],
) -> list[str]:
    return plan.books_in_query[:8] if plan.books_in_query else candidate_books[:8]
