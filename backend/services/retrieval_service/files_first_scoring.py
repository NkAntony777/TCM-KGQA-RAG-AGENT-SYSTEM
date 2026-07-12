"""Ranking and scoring helpers for files-first retrieval.

This module owns the post-search re-ranking logic:

* ``_is_front_matter_title`` detects titles that should be penalised
  (prefaces, fanli, volume markers, ...) so that focused queries do not
  surface them at the top.
* ``_field_overlap_multiplier`` returns the final multiplier applied to
  each candidate row based on how well its metadata overlaps with the
  query focus entities, books, intent flags, and rank plan position.

The module is intentionally free of query parsing. It reads constants
from :mod:`files_first_constants` and consumes row dicts that are
already shaped by the search pipeline.
"""

from __future__ import annotations

from typing import Any

from services.retrieval_service.files_first_constants import _env_flag


def _is_front_matter_title(title: str) -> bool:
    normalized = str(title or "").strip().strip("[]")
    if not normalized:
        return False
    if normalized in {"原序", "序", "凡例", "发凡", "附录", "卷一", "卷二", "卷三", "卷四"}:
        return True
    if normalized.startswith("卷"):
        return True
    if normalized.endswith(("凡例", "原序", "自序", "总序", "小序")):
        return True
    return False


def _field_overlap_multiplier(
    *,
    row: dict[str, Any],
    focus_entities: list[str],
    books_in_query: list[str],
    query_terms: list[str],
    flags: dict[str, bool],
    plan_rank: int,
) -> float:
    if not _env_flag("FILES_FIRST_RERANK_BONUS_ENABLED", default=True):
        return max(1.0, 1.12 - min(max(plan_rank, 0), 4) * 0.04)
    book_name = str(row.get("book_name", "") or "")
    chapter_title = str(row.get("chapter_title", "") or "")
    section_summary = str(row.get("section_summary", "") or "")
    topic_tags = str(row.get("topic_tags", "") or "")
    entity_tags = str(row.get("entity_tags", "") or "")
    snippet = str(row.get("match_snippet", "") or "")
    text = str(row.get("text", "") or "")
    direct_clause_hits = int(row.get("_direct_clause_hits", 0) or 0)
    score = 0.0
    haystack = " ".join([book_name, chapter_title, section_summary, topic_tags, entity_tags, snippet, text])
    content_focus = [entity for entity in focus_entities if entity and entity != book_name]
    front_matter = _is_front_matter_title(chapter_title) or chapter_title == book_name

    for entity in focus_entities:
        if not entity:
            continue
        if entity == chapter_title:
            score += 5.0
        elif entity in chapter_title:
            score += 2.4
        elif entity in entity_tags:
            score += 2.1
        elif entity in book_name:
            score += 1.8
        elif entity in section_summary or entity in snippet:
            score += 1.2
        elif entity in topic_tags:
            score += 0.9
        elif entity in text:
            score += 0.4

    if books_in_query and any(book in book_name for book in books_in_query):
        score += 2.5
    if books_in_query and any(book == book_name for book in books_in_query):
        score += 3.2
    if books_in_query and any(book == chapter_title for book in books_in_query):
        score += 1.8

    if flags.get("comparison_query") and len(focus_entities) >= 2:
        both_present = sum(1 for entity in focus_entities[:2] if entity and (entity in chapter_title or entity in entity_tags or entity in section_summary or entity in text))
        if both_present >= 2:
            score += 2.2
        elif both_present == 1:
            score += 0.5

    if any(entity and entity in chapter_title for entity in focus_entities[:3]):
        if any(marker in chapter_title for marker in ("病脉证治", "证并治", "证治", "方论")):
            score += 2.2
        elif chapter_title.endswith(("病", "证", "论")):
            score += 1.2

    if flags.get("source_query") and any(marker in section_summary or marker in snippet or marker in text for marker in ("出自", "见于", "载于", "原文", "语出", "曰")):
        score += 1.5
    if flags.get("source_query") and books_in_query and any(book in haystack for book in books_in_query):
        score += 2.0
    if flags.get("source_query") and focus_entities and any(entity in haystack for entity in focus_entities[:2]):
        score += 1.6
    if flags.get("property_query") and any(marker in chapter_title or marker in topic_tags or marker in section_summary for marker in ("功效", "归经", "性味", "主治", "作用", "配伍")):
        score += 1.0
    if flags.get("property_query") and any(entity and entity == chapter_title for entity in focus_entities):
        score += 5.0
    if flags.get("composition_query") and any(marker in chapter_title or marker in topic_tags or marker in section_summary for marker in ("组成", "药味", "配伍", "加减")):
        score += 1.0
    if flags.get("composition_query") and any(entity and entity == chapter_title for entity in focus_entities):
        score += 5.0
    if flags.get("source_query") and any(entity and entity == chapter_title for entity in focus_entities):
        score += 5.0

    light_term_hits = sum(1 for term in query_terms[:6] if term and (term in chapter_title or term in section_summary or term in entity_tags))
    score += min(1.2, light_term_hits * 0.2)
    if len(focus_entities) >= 2:
        present = sum(1 for entity in focus_entities[:2] if entity and entity in haystack)
        if present >= 2:
            score += 2.0
    if direct_clause_hits > 0:
        score += min(4.0, direct_clause_hits * 1.5)
    if front_matter and content_focus:
        covered = sum(1 for entity in content_focus[:3] if entity in haystack)
        if covered == 0:
            score -= 4.0
        elif covered == 1:
            score -= 1.5
    score += max(0.0, 0.25 * (3 - int(plan_rank or 0)))
    if str(row.get("file_type", "")) == "SECTION":
        score += 0.35
    return 1.0 + min(0.55, score * 0.06)