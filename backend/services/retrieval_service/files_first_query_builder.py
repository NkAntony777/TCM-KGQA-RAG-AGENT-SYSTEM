"""FTS query builders and SQLite helpers for files-first retrieval.

This module produces the literal SQL/FTS strings and parameter tuples
that the rest of the pipeline consumes:

* ``_fts_quote`` wraps a term in FTS5 double-quote syntax.
* ``_join_match_terms`` composes boolean expressions from a term list.
* ``_build_match_queries`` orchestrates primary / auxiliary / fallback
  match queries given the current intent flags.
* ``_build_sqlite_in_clause`` builds a parameterised ``IN`` fragment for
  dynamic SQLite filters.

It depends on :mod:`files_first_query_terms` for term cleanup and on
:mod:`files_first_constants` only transitively.
"""

from __future__ import annotations

from typing import Any

from services.retrieval_service.files_first_query_terms import _clean_candidate_term


def _fts_quote(term: str) -> str:
    return f'"{str(term or "").replace(chr(34), " ").strip()}"'


def _join_match_terms(terms: list[str], *, operator: str) -> str:
    cleaned = [_clean_candidate_term(item) for item in terms]
    cleaned = [item for item in cleaned if item]
    if not cleaned:
        return ""
    return f" {operator} ".join(_fts_quote(item) for item in cleaned)


def _build_match_queries(
    *,
    primary_terms: list[str],
    auxiliary_terms: list[str],
    fallback_terms: list[str],
    flags: dict[str, bool],
) -> list[str]:
    queries: list[str] = []
    primary_or = _join_match_terms(primary_terms[:6], operator="OR")
    fallback_or = _join_match_terms(fallback_terms[:8], operator="OR")
    auxiliary_or = _join_match_terms(auxiliary_terms[:4], operator="OR")
    if len(primary_terms) >= 2 and (flags.get("comparison_query") or flags.get("property_query") or flags.get("composition_query")):
        exact_and = _join_match_terms(primary_terms[:2], operator="AND")
        if exact_and:
            queries.append(exact_and)
    if len(primary_terms) <= 1 and primary_or and auxiliary_or and (flags.get("source_query") or flags.get("property_query") or flags.get("composition_query")):
        queries.append(f"({primary_or}) AND ({auxiliary_or})")
    if primary_or:
        queries.append(primary_or)
    fallback_is_auxiliary = bool(fallback_terms) and all(term in auxiliary_terms for term in fallback_terms)
    if fallback_or and fallback_or not in queries and (not primary_or or not fallback_is_auxiliary):
        queries.append(fallback_or)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _build_sqlite_in_clause(
    values: list[str],
    *,
    alias: str,
    column: str,
) -> tuple[str, tuple[Any, ...]]:
    normalized = [str(item or "").strip() for item in values if str(item or "").strip()]
    if not normalized:
        return "", ()
    placeholders = ",".join("?" for _ in normalized)
    return f" AND {alias}.{column} IN ({placeholders})", tuple(normalized)