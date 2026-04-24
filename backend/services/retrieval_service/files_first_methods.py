from __future__ import annotations

import os
import re
import sqlite3
from typing import Any

from services.qa_service.alias_service import get_runtime_alias_service

BOOK_HINTS = (
    "黄帝内经",
    "灵枢",
    "素问",
    "伤寒论",
    "金匮要略",
    "温病条辨",
    "医方集解",
    "医方论",
    "小儿药证直诀",
    "本草纲目",
    "神农本草经",
    "脾胃论",
    "临证指南医案",
)
QUERY_STOP_TERMS = {
    "什么",
    "为何",
    "为什么",
    "怎么",
    "如何",
    "请给",
    "请从",
    "请概括",
    "请解释",
    "哪本书",
    "哪部书",
    "出处",
    "原文",
    "片段",
    "记载",
    "论述",
    "条文",
    "是什么",
    "一个",
    "比较",
    "直接",
    "引用",
    "角度",
    "概括",
    "四个",
    "作用",
    "古籍",
    "经典",
    "表述",
    "记载",
    "本书",
}
QUERY_STRIP_PATTERNS = (
    "什么叫",
    "是什么",
    "为什么",
    "请给",
    "请从",
    "请概括",
    "请解释",
    "常参考什么方",
    "可参考什么方剂",
    "一个比较适合直接引用的",
    "比较适合直接引用的",
    "适合直接引用的",
    "在方剂中起什么作用",
    "起什么作用",
    "适用边界上有什么不同",
    "在古籍中常见的",
    "在本草文献中常见的",
    "在本草文献中的",
    "四个角度概括",
    "四个角度",
    "在古籍中的经典表述",
    "古籍中的经典表述",
    "古籍中的",
    "在古籍中",
    "古籍记载",
    "关于",
    "方后注",
)
FORMULA_SUFFIXES = ("汤", "散", "丸", "饮", "膏", "丹", "方", "颗粒", "胶囊")
HERB_SUFFIXES = ("草", "花", "叶", "根", "子", "仁", "皮", "藤", "术", "芩", "芎", "苓", "黄", "参", "胡")
CONCEPT_SUFFIXES = ("病", "证", "痹", "痛", "虚", "郁", "热", "寒", "咳", "喘")
FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}?(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)")
FORMULA_VARIANT_PATTERN = re.compile(r"^(?:[一二三四五六七八九十两]+味)(?P<tail>[\u4e00-\u9fff]{2,16}?(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊))$")
INTENT_CUE_TERMS = {
    "source_query": ("出处", "出自", "见于", "载于", "原文"),
    "comparison_query": ("比较", "区别", "异同", "差异"),
    "property_query": ("功效", "归经", "性味", "主治", "作用", "配伍"),
    "composition_query": ("组成", "药味", "配伍", "加减"),
}


def _env_flag(name: str, *, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


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


def _is_probable_herb_property_query(*, query: str, focus_entities: list[str], flags: dict[str, bool], books_in_query: list[str]) -> bool:
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


def _fts_quote(term: str) -> str:
    return f'"{str(term or "").replace(chr(34), " ").strip()}"'


def _join_match_terms(terms: list[str], *, operator: str) -> str:
    cleaned = [_clean_candidate_term(item) for item in terms]
    cleaned = [item for item in cleaned if item]
    if not cleaned:
        return ""
    return f" {operator} ".join(_fts_quote(item) for item in cleaned)


def _build_match_queries(*, primary_terms: list[str], auxiliary_terms: list[str], fallback_terms: list[str], flags: dict[str, bool]) -> list[str]:
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


def _build_sqlite_in_clause(values: list[str], *, alias: str, column: str) -> tuple[str, tuple[Any, ...]]:
    normalized = [str(item or "").strip() for item in values if str(item or "").strip()]
    if not normalized:
        return "", ()
    placeholders = ",".join("?" for _ in normalized)
    return f" AND {alias}.{column} IN ({placeholders})", tuple(normalized)


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
