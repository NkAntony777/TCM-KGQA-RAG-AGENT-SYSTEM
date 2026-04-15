from __future__ import annotations

import re
from typing import Any

from services.common.evidence_payloads import normalize_book_label


QUERY_FRAGMENT_SPLIT_PATTERN = re.compile(r"[\s，。；、！？?：:（）()\[\]【】《》“”\"'·/]+")


def query_fragments(query_text: str) -> list[str]:
    normalized = (
        str(query_text or "")
        .replace("有什么", " ")
        .replace("是什么", " ")
        .replace("有哪些", " ")
        .replace("什么", " ")
        .replace("请从", " ")
        .replace("请结合", " ")
        .replace("并说明", " ")
        .replace("并论述", " ")
        .replace("并比较", " ")
    )
    candidates = [item.strip() for item in QUERY_FRAGMENT_SPLIT_PATTERN.split(normalized)]
    fragments: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        item = item.lstrip("中就按从与和及并请")
        if len(item) < 2:
            continue
        if item in seen:
            continue
        seen.add(item)
        fragments.append(item)
    return fragments


def query_mentions_source_book(query_text: str, source_book: str) -> bool:
    normalized_query = str(query_text or "").strip()
    normalized_book = normalize_book_label(source_book)
    if not normalized_query or not normalized_book:
        return False
    if normalized_book in normalized_query:
        return True
    return f"《{normalized_book}》" in normalized_query


def source_book_match_score(relation: dict[str, Any], query_text: str) -> int:
    source_book = str(relation.get("source_book", "")).strip()
    if not source_book:
        return 0
    return 2 if query_mentions_source_book(query_text, source_book) else 0
