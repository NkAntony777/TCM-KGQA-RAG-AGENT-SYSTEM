"""Query-term extraction and text normalization for files-first retrieval.

This module owns everything that turns a raw user query into structured
retrieval signals:

* Query-intent flags and book-detection helpers.
* Span / clause / subject extractors that pull candidate terms out of
  Chinese free-form text.
* Entity-shape predicates and noisy-term filters.
* Tokenization and token cleanup helpers.
* The high-level ``_extract_focus_entities`` and ``_prepare_match_terms``
  pipelines that combine all of the above into ranked retrieval inputs.

It depends only on :mod:`files_first_constants` and the runtime alias
service.
"""

from __future__ import annotations

import re
import sqlite3

from services.qa_service.alias_service import get_runtime_alias_service
from ..utils.constants import (
    BOOK_HINTS,
    CONCEPT_SUFFIXES,
    FORMULA_PATTERN,
    FORMULA_SUFFIXES,
    FORMULA_VARIANT_PATTERN,
    HERB_SUFFIXES,
    INTENT_CUE_TERMS,
    QUERY_STOP_TERMS,
    QUERY_STRIP_PATTERNS,
    _env_flag,
)


def _query_flags(query: str) -> dict[str, bool]:
    text = str(query or "").strip()
    return {
        "source_query": any(marker in text for marker in ("出处", "原文", "原句", "条文", "哪本书", "哪部书", "记载", "哪一篇")),
        "comparison_query": ("比较" in text and "比较适合" not in text) or any(marker in text for marker in ("区别", "异同", "不同")),
        "property_query": any(marker in text for marker in ("功效", "归经", "性味", "作用", "主治", "表现")),
        "composition_query": any(marker in text for marker in ("组成", "药味", "配方", "哪些药", "加减", "叫什么", "什么方", "哪些方")),
    }


def _books_in_query(query: str) -> list[str]:
    text = str(query or "").strip()
    books = [book for book in BOOK_HINTS if book in text]
    for match in re.finditer(r"([\u4e00-\u9fff]{2,24}(?:经|论|方论|集解|心典|浅注|直诀|本草|要略|从新|秘要|局方|医方考|方考|百种录))(?:里|中|的)", text):
        candidate = str(match.group(1)).strip()
        if candidate and candidate not in books:
            books.append(candidate)
    for match in re.finditer(r"《([^》]{2,24})》", text):
        candidate = str(match.group(1)).strip()
        if candidate and candidate not in books:
            books.append(candidate)
    books = sorted(set(books), key=len, reverse=True)
    collapsed: list[str] = []
    for book in books:
        if any(book != existing and book in existing for existing in collapsed):
            continue
        collapsed.append(book)
    return collapsed


def _db_books_in_query(
    conn: sqlite3.Connection,
    *,
    query: str,
    focus_entities: list[str],
    limit: int,
) -> list[str]:
    raw_query = str(query or "").strip()
    if not raw_query:
        return []
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT book_name FROM book_outlines").fetchall()
    exact_hits: list[str] = []
    partial_hits: list[str] = []
    seen: set[str] = set()
    probes = [raw_query, *focus_entities]
    for row in rows:
        book_name = str(row["book_name"] or "").strip()
        if not book_name or book_name in seen:
            continue
        if book_name in raw_query:
            seen.add(book_name)
            exact_hits.append(book_name)
            continue
        if any(probe and len(probe) >= 4 and (probe in book_name or book_name in probe) for probe in probes):
            seen.add(book_name)
            partial_hits.append(book_name)
    return [*exact_hits[:limit], *partial_hits[: max(0, limit - len(exact_hits))]]


def _is_probable_herb_property_query(
    *,
    query: str,
    focus_entities: list[str],
    flags: dict[str, bool],
    books_in_query: list[str],
) -> bool:
    if books_in_query:
        return False
    if not flags.get("property_query") and "哪味药" not in str(query or ""):
        return False
    if any(entity.endswith(FORMULA_SUFFIXES) for entity in focus_entities):
        return False
    return any(2 <= len(str(entity or "").strip()) <= 4 for entity in focus_entities)


def _extract_content_spans(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    for book in _books_in_query(text):
        text = text.replace(f"《{book}》", " ")
        text = text.replace(book, " ")
    text = re.sub(r"[里中](?=[\u4e00-\u9fff])", " ", text)
    text = re.sub(r"[、，,。！？?；;：:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    spans: list[str] = []
    for chunk in text.split():
        cleaned = re.sub(r"(有哪些|什么|怎么|怎样|为何|为什么|请问|先后|分别|时|又|再|主用|可用|用)(.*)$", "", chunk).strip()
        cleaned = cleaned.lstrip("再又其之的论里中卷")
        if 2 <= len(cleaned) <= 16 and not _contains_query_scaffolding(cleaned):
            spans.append(cleaned)
    return list(dict.fromkeys(spans))[:6]


def _descriptive_clause_terms(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    for book in _books_in_query(text):
        text = text.replace(f"《{book}》", " ")
        text = text.replace(book, " ")
    text = re.sub(r"^(哪味药|哪首方|哪一方|哪种方|哪部书|哪条文|病人|此方|此药|这个方子|这一条)", " ", text)
    text = re.sub(r"(被描述为|被说成|被解释为|怎样概括|为什么属|为什么是|适合治|主要治|主治|宜先用|偏向哪首|实际就是|被强调|概括|解释)", " ", text)
    text = re.sub(r"[、，,。！？?；;：:]", "\n", text)
    text = re.sub(r"\s+", " ", text).strip()
    terms: list[str] = []
    raw_chunks: list[str] = []
    for chunk in text.splitlines():
        base = str(chunk or "").strip()
        if not base:
            continue
        raw_chunks.append(base)
        raw_chunks.extend(part.strip() for part in re.split(r"\s+", base) if part.strip())
    for chunk in raw_chunks:
        cleaned = str(chunk or "").strip(" ，。；：:、")
        cleaned = re.sub(r"^(而且|并|并且|又|及|并除|并治|其能|最能|能|主|宜|偏向|初起|被说成|被描述为)", "", cleaned).strip()
        cleaned = re.sub(r"(是什么|哪首方|哪味药|哪一方|哪种方|哪部书|哪条文)$", "", cleaned).strip()
        if len(cleaned) < 3 or len(cleaned) > 18:
            continue
        if any(marker in cleaned for marker in ("什么", "怎么", "怎样", "哪味", "哪首", "为什么", "哪部", "哪条")):
            continue
        if _contains_query_scaffolding(cleaned):
            continue
        terms.append(cleaned)
        for piece in re.split(r"(?:能|主|并|而|兼|且|可|宜|被|说成|解释为|属|治)", cleaned):
            normalized_piece = str(piece or "").strip()
            if len(normalized_piece) < 2 or len(normalized_piece) > 12:
                continue
            if any(marker in normalized_piece for marker in ("什么", "怎么", "怎样", "哪味", "哪首", "为什么", "哪部", "哪条")):
                continue
            if _contains_query_scaffolding(normalized_piece):
                continue
            terms.append(normalized_piece)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in terms:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:8]


def _leading_subject_terms(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    for book in _books_in_query(text):
        text = text.replace(f"《{book}》", " ")
        text = text.replace(book, " ")
    text = re.sub(r"[里中](?=[\u4e00-\u9fff])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    terms: list[str] = []
    pattern_items = (
        r"^\s*(?:什么叫|何谓)([\u4e00-\u9fff]{2,10})",
        r"^\s*([\u4e00-\u9fff]{2,16})(?:在|的|主要|主治|为什么|适用于|能治|可治|节律|关系)",
        r"^\s*([\u4e00-\u9fff]{2,8})(?:的|主要|主治|为什么|适用于|能治|可治)",
        r"^\s*([\u4e00-\u9fff]{2,10}(?:草|汤|散|丸|饮|方|病|证))",
        r"^\s*([\u4e00-\u9fff]{3,16})的节律",
        r"^\s*([\u4e00-\u9fff]{3,12})的古籍解释",
        r"^\s*([\u4e00-\u9fff]{3,12})与[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|方)的关系",
    )
    permissive_patterns = {
        r"^\s*([\u4e00-\u9fff]{3,16})的节律",
        r"^\s*([\u4e00-\u9fff]{3,12})的古籍解释",
        r"^\s*([\u4e00-\u9fff]{3,12})与[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|方)的关系",
    }
    for pattern in pattern_items:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = str(match.group(1)).strip()
        if candidate.endswith("的"):
            candidate = candidate[:-1].strip()
        if any(marker in candidate for marker in ("古籍", "本草", "文献", "功效", "主治", "表述")):
            continue
        if pattern in permissive_patterns:
            if 3 <= len(candidate) <= 16:
                terms.append(candidate)
        elif 2 <= len(candidate) <= 10 and not _is_noisy_term(candidate):
            terms.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in terms:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:3]


def _high_precision_direct_terms(query: str) -> list[str]:
    if not _env_flag("FILES_FIRST_DIRECT_RECALL_ENABLED", default=True):
        return []
    text = str(query or "").strip()
    if not text:
        return []
    normalized = text
    for book in _books_in_query(text):
        normalized = normalized.replace(f"《{book}》", " ")
        normalized = normalized.replace(book, " ")
    normalized = re.sub(
        r"(怎样解释|为什么是|有哪些|什么|怎么|请问|时先后用哪些方|时用什么方|又叫什么|叫什么|主治什么脉证|主治哪些病证|典型表现)",
        " ",
        normalized,
    )
    normalized = re.sub(r"[、，,。！？?；;：:]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    terms: list[str] = []
    for item in _leading_subject_terms(text):
        terms.append(item)
    for item in _descriptive_clause_terms(text):
        terms.append(item)
    for item in (
        _normalize_formula_match(match)
        for match in FORMULA_PATTERN.findall(normalized)
        if _normalize_formula_match(match)
    ):
        if item:
            terms.append(item)
    for match in re.finditer(r"([\u4e00-\u9fff]{2,8})(?:主治|功效|归经|性味)", text):
        terms.append(str(match.group(1)).strip())
    for match in re.finditer(r"([\u4e00-\u9fff]{2,10}(?:病|证))", normalized):
        terms.append(str(match.group(1)).strip())
    for match in re.finditer(r"([\u4e00-\u9fff]{3,16})(?:的节律|的关系|的古籍解释|的经典表述)", text):
        candidate = str(match.group(1)).strip()
        if not _is_noisy_term(candidate):
            terms.append(candidate)
    for match in re.finditer(r"([\u4e00-\u9fff]{4,16})(?:病脉证治|证并治|证治|经典表述|古籍解释|古籍记载|条文)", text):
        candidate = str(match.group(1)).strip()
        if not _is_noisy_term(candidate):
            terms.append(candidate)
    for span in re.split(r"[、，,。！？?；;：:\s]", normalized):
        cleaned = str(span or "").strip()
        if 4 <= len(cleaned) <= 18 and not any(marker in cleaned for marker in ("什么", "怎么", "怎样", "为什么", "有哪些", "请问")):
            terms.append(cleaned)
    for span in _extract_content_spans(normalized):
        if _looks_like_entity(span) or span.endswith(("病", "证")) or 2 <= len(span) <= 6:
            terms.append(span)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in terms:
        normalized_term = str(item or "").strip()
        if len(normalized_term) < 2 or _is_noisy_term(normalized_term):
            continue
        if any(marker in normalized_term for marker in ("里", "中", "的")) and not normalized_term.endswith(("病", "证")):
            continue
        if normalized_term in _books_in_query(text):
            continue
        if normalized_term in {"方论", "本草", "病证", "哪些方", "什么方"}:
            continue
        if normalized_term in seen:
            continue
        seen.add(normalized_term)
        cleaned.append(normalized_term)
    return cleaned[:8]


def _strip_query_noise(text: str) -> str:
    normalized = str(text or "").strip()
    for pattern in QUERY_STRIP_PATTERNS:
        normalized = normalized.replace(pattern, " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _looks_like_entity(term: str) -> bool:
    normalized = str(term or "").strip()
    if len(normalized) < 2:
        return False
    if normalized in BOOK_HINTS:
        return True
    if normalized.endswith(FORMULA_SUFFIXES):
        return True
    if normalized.endswith(HERB_SUFFIXES):
        return len(normalized) <= 5
    if normalized.endswith(CONCEPT_SUFFIXES):
        return len(normalized) <= 4
    return False


def _contains_query_scaffolding(term: str) -> bool:
    normalized = str(term or "").strip()
    return any(
        marker in normalized
        for marker in (
            "在古籍中",
            "古籍中的",
            "经典表述",
            "古籍记载",
            "适合直接引用",
            "四个角度",
            "起什么作用",
            "什么方",
            "哪些方",
            "叫什么",
            "典型表现",
            "先后用哪些方",
            "时用什么方",
        )
    )


def _is_noisy_term(term: str) -> bool:
    normalized = str(term or "").strip()
    if not normalized:
        return True
    if normalized in {"方论", "卷一", "卷二", "卷三", "卷四"}:
        return True
    if normalized in {"哪味药", "哪首方", "哪一方", "哪种方", "哪味", "哪首", "描述", "表述", "解释"}:
        return True
    if "哪味药" in normalized or "哪首方" in normalized:
        return True
    if normalized in QUERY_STOP_TERMS:
        return True
    if _contains_query_scaffolding(normalized) and not _looks_like_entity(normalized):
        return True
    if len(normalized) > 8 and not _looks_like_entity(normalized) and normalized not in BOOK_HINTS:
        return True
    return False


def _normalize_formula_match(value: str) -> str:
    normalized = str(value or "").strip().lstrip("和与跟及")
    if "里" in normalized:
        tail = normalized.split("里")[-1].strip()
        if tail.endswith(FORMULA_SUFFIXES):
            normalized = tail
    if "的" in normalized:
        tail = normalized.split("的")[-1].strip()
        if tail.endswith(FORMULA_SUFFIXES):
            normalized = tail
    if _contains_query_scaffolding(normalized):
        return ""
    if normalized.endswith("方") and len(normalized) > 4 and not any(marker in normalized for marker in ("汤", "散", "丸", "饮", "膏", "丹")):
        return ""
    return normalized


def _expand_entity_aliases(entities: list[str]) -> list[str]:
    expanded: list[str] = []
    for entity in entities:
        normalized = str(entity or "").strip()
        if not normalized:
            continue
        expanded.append(normalized)
        variant_match = FORMULA_VARIANT_PATTERN.match(normalized)
        if variant_match:
            tail = str(variant_match.group("tail") or "").strip()
            if tail:
                expanded.append(tail)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in expanded:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _collapse_overlapping_terms(terms: list[str]) -> list[str]:
    collapsed: list[str] = []
    for item in terms:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        if any(normalized != existing and normalized in existing for existing in collapsed):
            continue
        collapsed.append(normalized)
    return collapsed


def _sanitize_focus_entities(terms: list[str]) -> list[str]:
    sanitized: list[str] = []
    for item in _collapse_overlapping_terms(terms):
        normalized = str(item or "").strip()
        if not normalized or _is_noisy_term(normalized):
            continue
        sanitized.append(normalized)
    return sanitized


def _intent_terms(flags: dict[str, bool]) -> list[str]:
    terms: list[str] = []
    for key, items in INTENT_CUE_TERMS.items():
        if not flags.get(key):
            continue
        for item in items:
            if item not in terms:
                terms.append(item)
    return terms


def _clean_candidate_term(term: str) -> str:
    normalized = _strip_query_noise(term)
    normalized = re.sub(r"[，。、“”‘’（）()《》【】\[\],.!?；：:]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _compact_phrase(text: str) -> str:
    normalized = str(text or "").strip()
    normalized = re.sub(r"[，。、“”‘’（）()《》【】\[\],.!?；：:\s、\\/\-]", "", normalized)
    return normalized


def _tokenized_query_terms(query: str, tokenizer, *, limit: int = 16) -> list[str]:
    normalized = _strip_query_noise(str(query or "").strip())
    if not normalized:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenizer.tokenize(normalized):
        cleaned = _clean_candidate_term(str(token))
        if len(cleaned) < 2:
            continue
        if _is_noisy_term(cleaned):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        terms.append(cleaned)
        if len(terms) >= limit:
            break
    return terms


def _split_compare_entities(query: str) -> list[str]:
    text = str(query or "").strip()
    split_parts = re.split(r"(?:和|与|跟|及|、|，|,)", text)
    formula_matches: list[str] = []
    for part in split_parts:
        cleaned_part = str(part or "").strip().lstrip("和与跟及")
        formula_matches.extend(
            _normalize_formula_match(item)
            for item in FORMULA_PATTERN.findall(cleaned_part)
            if _normalize_formula_match(item)
        )
    if len(formula_matches) >= 2:
        return list(dict.fromkeys(item for item in formula_matches[:4] if item))
    return []


def _entity_from_relation_query(query: str) -> list[str]:
    text = _strip_query_noise(str(query or "").strip())
    results: list[str] = []
    direct_formulas = [
        _normalize_formula_match(item)
        for item in FORMULA_PATTERN.findall(text)
        if _normalize_formula_match(item)
    ]
    if direct_formulas:
        results.extend(direct_formulas[:3])
    match = re.search(
        r"^([\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊))中的([\u4e00-\u9fff]{2,8}?)(?:在|起|的|$)",
        text,
    )
    if match:
        for value in match.groups():
            if value:
                results.append(str(value).strip())
        return list(dict.fromkeys(item for item in results if item))
    if "的" in text:
        head = text.split("的", 1)[0].strip()
        if head.endswith("中") and any(head[:-1].endswith(suffix) for suffix in FORMULA_SUFFIXES):
            head = head[:-1]
        if 2 <= len(head) <= 16:
            results.append(head)
            return list(dict.fromkeys(item for item in results if item))
    for marker in ("最早见于", "出自", "见于", "包含哪些药", "包含什么药"):
        if marker in text:
            head = text.split(marker, 1)[0].strip()
            if 2 <= len(head) <= 16:
                results.append(head)
    return list(dict.fromkeys(item for item in results if item))


def _extract_focus_entities(query: str, tokenizer) -> list[str]:
    normalized = _strip_query_noise(str(query or "").strip())
    alias_service = get_runtime_alias_service()
    entities: list[str] = []
    flags = _query_flags(normalized)
    books_in_query = _books_in_query(normalized)
    token_terms = _tokenized_query_terms(normalized, tokenizer, limit=12)
    content_spans = _extract_content_spans(normalized)
    leading_subjects = _leading_subject_terms(normalized)
    direct_formulas = list(
        dict.fromkeys(
            _normalize_formula_match(item)
            for item in FORMULA_PATTERN.findall(normalized)
            if _normalize_formula_match(item)
        )
    )
    for item in leading_subjects:
        if item not in entities:
            entities.append(item)
    for item in direct_formulas:
        if item not in entities:
            entities.append(item)
    for item in content_spans:
        if item not in entities and not _is_noisy_term(item):
            entities.append(item)
    for book in BOOK_HINTS:
        if book in normalized and book not in entities:
            entities.append(book)
    compare_entities = _split_compare_entities(normalized) if flags["comparison_query"] else []
    for item in compare_entities:
        if item not in entities:
            entities.append(item)
    for item in _entity_from_relation_query(normalized):
        if item not in entities and not _is_noisy_term(item):
            entities.append(item)
    if compare_entities:
        return list(dict.fromkeys([*entities, *compare_entities]))[:4]
    if direct_formulas and (flags["source_query"] or flags["composition_query"] or flags["property_query"]):
        return direct_formulas[:4]
    if entities and (flags["property_query"] or flags["source_query"] or flags["composition_query"]):
        prioritized = [
            item
            for item in entities
            if item and (not _is_noisy_term(item) or item in content_spans or item in direct_formulas)
        ]
        return list(dict.fromkeys(prioritized))[:4]
    if alias_service.is_available():
        for item in alias_service.detect_entities(normalized, limit=4):
            cleaned = _clean_candidate_term(item)
            if cleaned and not _is_noisy_term(cleaned):
                entities.append(cleaned)
    for token in token_terms:
        if token in _intent_terms(flags):
            continue
        if any(token in book or book in token for book in books_in_query):
            continue
        if token in BOOK_HINTS or _looks_like_entity(token):
            entities.append(token)
            continue
        if flags["property_query"] or flags["composition_query"] or flags["source_query"]:
            if 2 <= len(token) <= 6:
                entities.append(token)
    if not entities:
        for token in token_terms:
            if token in _intent_terms(flags):
                continue
            if 2 <= len(token) <= 6:
                entities.append(token)
    has_strong_anchor = any(item in BOOK_HINTS or item.endswith(FORMULA_SUFFIXES) for item in entities)
    if token_terms and not has_strong_anchor:
        entities = [
            *[token for token in token_terms[:3] if token not in _intent_terms(flags)],
            *entities,
        ]
    for match in re.findall(r"[\u4e00-\u9fff]{2,8}", normalized):
        if _is_noisy_term(match):
            continue
        if any(match in book or book in match for book in books_in_query):
            continue
        if _looks_like_entity(match) and match not in entities:
            entities.append(match)
    filtered = []
    for entity in entities:
        if not entity:
            continue
        if any(entity in book or book in entity for book in books_in_query):
            if entity not in books_in_query:
                continue
        filtered.append(entity)
    return list(dict.fromkeys(filtered))[:4]


def _prepare_match_terms(query: str, tokenizer) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized:
        return []
    alias_service = get_runtime_alias_service()
    focus_entities = _sanitize_focus_entities(_expand_entity_aliases(_extract_focus_entities(normalized, tokenizer)))
    flags = _query_flags(normalized)
    expanded = alias_service.expand_query_with_aliases(
        normalized,
        focus_entities=focus_entities,
        max_aliases_per_entity=3,
        max_entities=2,
    ) if alias_service.is_available() else normalized
    stripped = _strip_query_noise(expanded)
    terms: list[str] = []
    seen: set[str] = set()

    def push(term: str, *, force: bool = False) -> None:
        cleaned = _clean_candidate_term(term)
        if len(cleaned) < 2:
            return
        if not force and _is_noisy_term(cleaned):
            return
        if cleaned in seen:
            return
        seen.add(cleaned)
        terms.append(cleaned)

    for entity in focus_entities:
        push(entity)
        if alias_service.is_available():
            for alias_name in alias_service.aliases_for_entity(entity, max_aliases=3):
                push(alias_name)

    for clause in _descriptive_clause_terms(normalized):
        push(clause, force=True)

    for book in _books_in_query(normalized):
        push(book)

    for cue_term in _intent_terms(flags):
        push(cue_term, force=True)

    for token_text in _tokenized_query_terms(stripped, tokenizer, limit=16):
        if 2 <= len(token_text) <= 8:
            push(token_text)

    for span in re.findall(r"[\u4e00-\u9fff]{2,20}", stripped):
        cleaned_span = _clean_candidate_term(span)
        if _is_noisy_term(cleaned_span):
            continue
        if _looks_like_entity(cleaned_span) or 2 <= len(cleaned_span) <= 6:
            push(cleaned_span)

    for ascii_term in re.findall(r"[A-Za-z0-9_.%-]{2,32}", stripped):
        push(ascii_term)

    return terms[:16]