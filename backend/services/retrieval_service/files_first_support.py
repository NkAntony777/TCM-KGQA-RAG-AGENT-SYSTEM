from __future__ import annotations

# Backward-compat shim — real implementation lives in files_first/ sub-package.
# External callers continue to import from `files_first_support` as before.

from services.retrieval_service.files_first import (  # noqa: F401
    # Store class + helpers
    LocalFilesFirstStore,
    _compose_section_preview,
    _build_section_search_basis,
    normalize_chunk,
    build_section_response,
    # Re-exported metadata symbols
    BOOK_LINE_PATTERN,
    CHAPTER_LINE_PATTERN,
    CLASSIC_PATH_PATTERN,
    FORMULA_TAG_PATTERN,
    CHINESE_SPAN_PATTERN,
    TOPIC_KEYWORDS,
    FILES_FIRST_SCHEMA_VERSION,
    REQUIRED_DOC_COLUMNS,
    extract_book_name,
    extract_chapter_title,
    build_section_key,
    strip_classic_headers,
    merge_section_bodies,
    # Re-exported query helpers (legacy private aliases)
    _query_flags,
    _books_in_query,
    _db_books_in_query,
    _extract_content_spans,
    _leading_subject_terms,
    _strip_query_noise,
    _contains_query_scaffolding,
    _is_noisy_term,
    _is_front_matter_title,
    _normalize_formula_match,
    _collapse_overlapping_terms,
    _sanitize_focus_entities,
    _clean_candidate_term,
    _split_compare_entities,
    _entity_from_relation_query,
    _extract_focus_entities,
    _prepare_match_terms,
    _compact_text,
    _normalize_section_file_path,
    _build_section_metadata,
    # External type re-exports
    ParentChunkStore,
    SectionSummaryCache,
)