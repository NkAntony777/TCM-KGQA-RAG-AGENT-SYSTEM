from __future__ import annotations

# Backward-compat shim — real implementation lives in files_first/query/terms.py.
# External callers continue to import from `files_first_query_terms` as before.

from services.retrieval_service.files_first.query.terms import (  # noqa: F401
    _query_flags,
    _descriptive_clause_terms,
    _prepare_match_terms,
    _extract_focus_entities,
)