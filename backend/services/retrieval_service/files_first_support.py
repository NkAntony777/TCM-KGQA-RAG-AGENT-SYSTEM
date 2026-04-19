from __future__ import annotations

import gc
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from services.qa_service.alias_service import get_runtime_alias_service
from services.retrieval_service import files_first_methods as ffm
from services.retrieval_service.nav_group_builder import build_nav_group_payload_from_rows

BOOK_LINE_PATTERN = re.compile(r"^古籍：(.+?)$", re.MULTILINE)
CHAPTER_LINE_PATTERN = re.compile(r"^篇名：(.+?)$", re.MULTILINE)
CLASSIC_PATH_PATTERN = re.compile(r"^classic://(?P<book>[^/]+)/(?P<section>\d{4})(?:-\d{2})?$")
FORMULA_TAG_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)")
CHINESE_SPAN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,10}")
TOPIC_KEYWORDS = (
    "病机",
    "辨证",
    "主治",
    "功效",
    "治法",
    "方义",
    "组成",
    "配伍",
    "加减",
    "归经",
    "药性",
    "煎服",
    "禁忌",
    "条文",
    "方后注",
)
FILES_FIRST_SCHEMA_VERSION = 5
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
REQUIRED_DOC_COLUMNS = {
    "chunk_id",
    "text",
    "filename",
    "file_type",
    "file_path",
    "page_number",
    "chunk_idx",
    "parent_chunk_id",
    "root_chunk_id",
    "chunk_level",
    "book_name",
    "chapter_title",
    "section_key",
    "section_summary",
    "topic_tags",
    "entity_tags",
}


def extract_book_name(*, text: str, filename: str, file_path: str) -> str:
    match = BOOK_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    if file_path.startswith("classic://"):
        return file_path.removeprefix("classic://").split("/", 1)[0].strip()
    stem = Path(filename or "").stem.strip()
    return re.sub(r"^\d+\s*[-_－—]\s*", "", stem).strip() or stem


def extract_chapter_title(*, text: str, page_number: int | None, file_path: str) -> str:
    match = CHAPTER_LINE_PATTERN.search(text or "")
    if match:
        return str(match.group(1) or "").strip()
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return classic_match.group("section")
    if page_number not in (None, 0):
        return f"{int(page_number):04d}"
    return ""


def build_section_key(*, book_name: str, chapter_title: str, page_number: int | None, file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"{classic_match.group('book')}::{classic_match.group('section')}"
    if book_name and chapter_title:
        return f"{book_name}::{chapter_title}"
    if book_name and page_number not in (None, 0):
        return f"{book_name}::{int(page_number):04d}"
    return ""


def strip_classic_headers(text: str) -> str:
    lines = [str(line or "").rstrip() for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if not (line.startswith("古籍：") or line.startswith("篇名："))).strip()


def merge_section_bodies(parts: list[str]) -> str:
    merged = ""
    for raw_part in parts:
        part = str(raw_part or "").strip()
        if not part:
            continue
        if not merged:
            merged = part
            continue
        overlap_limit = min(len(merged), len(part), 400)
        overlap_size = 0
        for size in range(overlap_limit, 24, -1):
            if merged.endswith(part[:size]):
                overlap_size = size
                break
        merged += part[overlap_size:]
    return merged.strip()


def _compose_section_preview(*, section_summary: str, representative_passages: list[str]) -> str:
    parts = [str(section_summary or "").strip()]
    parts.extend(str(item or "").strip() for item in representative_passages if str(item or "").strip())
    return "\n".join(part for part in parts if part).strip()


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _build_section_search_basis(
    *,
    book_name: str,
    chapter_title: str,
    section_summary: str,
    topic_tags_text: str,
    entity_tags_text: str,
    representative_text: str,
) -> str:
    return " ".join(
        [
            str(book_name or ""),
            str(chapter_title or ""),
            str(section_summary or ""),
            str(topic_tags_text or ""),
            str(entity_tags_text or ""),
            str(representative_text or ""),
        ]
    ).strip()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _normalize_section_file_path(file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"classic://{classic_match.group('book')}/{classic_match.group('section')}"
    return str(file_path or "")


def _query_flags(query: str) -> dict[str, bool]:
    text = str(query or "").strip()
    return {
        "source_query": any(marker in text for marker in ("出处", "原文", "原句", "条文", "哪本书", "哪部书", "记载", "哪一篇")),
        "comparison_query": ("比较" in text and "比较适合" not in text) or any(marker in text for marker in ("区别", "异同", "不同")),
        "property_query": any(marker in text for marker in ("功效", "归经", "性味", "作用", "主治", "表现")),
        "composition_query": any(marker in text for marker in ("组成", "药味", "配方", "哪些药", "加减", "叫什么", "什么方", "哪些方")),
    }


def _merge_query_flags(base_flags: dict[str, bool], query_context: dict[str, Any] | None) -> dict[str, bool]:
    flags = dict(base_flags)
    if not query_context:
        return flags
    question_type = str(query_context.get("question_type", "")).strip()
    facets = {str(item).strip() for item in query_context.get("answer_facets", []) if str(item).strip()}
    if question_type == "source_locate":
        flags["source_query"] = True
    if question_type == "composition" or "组成" in facets:
        flags["composition_query"] = True
    if question_type == "property" or facets & {"功效", "归经", "别名", "主治", "治法"}:
        flags["property_query"] = True
    if question_type == "comparison":
        flags["comparison_query"] = True
    return flags


def _apply_query_context(
    *,
    query: str,
    tokenizer,
    query_context: dict[str, Any] | None,
) -> tuple[dict[str, bool], list[str], list[str], str, bool, bool]:
    base_flags = _query_flags(query)
    flags = _merge_query_flags(base_flags, query_context)
    heuristic_entities = _sanitize_focus_entities(_extract_focus_entities(query, tokenizer))
    llm_entities = [
        str(item).strip()
        for item in (query_context or {}).get("focus_entities", [])
        if str(item).strip()
    ]
    primary_entity = str((query_context or {}).get("primary_entity", "")).strip()
    ordered = []
    seen: set[str] = set()
    for item in [primary_entity, *llm_entities, *heuristic_entities]:
        normalized = str(item or "").strip()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    books_in_query = _unique_nonempty_strings(
        [*[(query_context or {}).get("source_book_hints", [])], _books_in_query(query)]
    )
    expanded_query = str((query_context or {}).get("expanded_query", "")).strip()
    weak_anchor = bool((query_context or {}).get("weak_anchor", False))
    need_broad_recall = bool((query_context or {}).get("need_broad_recall", False))
    return flags, ordered[:4], books_in_query[:8], expanded_query, weak_anchor, need_broad_recall


def _unique_nonempty_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    stack: list[str] = []
    for value in values:
        if isinstance(value, list):
            stack.extend(str(item).strip() for item in value if str(item).strip())
        else:
            normalized = str(value or "").strip()
            if normalized:
                stack.append(normalized)
    for item in stack:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


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
        normalized = str(item or "").strip()
        if len(normalized) < 2 or _is_noisy_term(normalized):
            continue
        if any(marker in normalized for marker in ("里", "中", "的")) and not normalized.endswith(("病", "证")):
            continue
        if normalized in _books_in_query(text):
            continue
        if normalized in {"方论", "本草", "病证", "哪些方", "什么方"}:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
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


def _gather_metadata_candidates(
    conn: sqlite3.Connection,
    *,
    query: str,
    focus_entities: list[str],
    query_terms: list[str],
    books_in_query: list[str],
    flags: dict[str, bool],
    limit: int,
) -> dict[str, list[str]]:
    candidate_books: list[str] = []
    candidate_sections: list[str] = []
    candidate_groups: list[str] = []
    seen_books: set[str] = set()
    seen_sections: set[str] = set()
    seen_groups: set[str] = set()

    def push_book(book_name: str) -> None:
        normalized = str(book_name or "").strip()
        if not normalized or normalized in seen_books:
            return
        seen_books.add(normalized)
        candidate_books.append(normalized)

    def push_section(section_key: str) -> None:
        normalized = str(section_key or "").strip()
        if not normalized or normalized in seen_sections:
            return
        seen_sections.add(normalized)
        candidate_sections.append(normalized)

    def push_group(group_key: str) -> None:
        normalized = str(group_key or "").strip()
        if not normalized or normalized in seen_groups:
            return
        seen_groups.add(normalized)
        candidate_groups.append(normalized)

    conn.row_factory = sqlite3.Row
    for book in _db_books_in_query(conn, query=query, focus_entities=focus_entities, limit=max(8, limit // 2)):
        push_book(book)
    if _is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
        rows = conn.execute(
            """
            SELECT book_name
            FROM book_outlines
            WHERE instr(book_name, '本草') > 0
            LIMIT ?
            """,
            (max(8, limit),),
        ).fetchall()
        for row in rows:
            push_book(str(row["book_name"] or ""))
    for book in books_in_query:
        push_book(book)
        rows = conn.execute(
            """
            SELECT DISTINCT book_name
            FROM book_outlines
            WHERE book_name = ? OR instr(book_name, ?) > 0
            LIMIT ?
            """,
            (book, book, max(4, limit // 2)),
        ).fetchall()
        for row in rows:
            push_book(str(row["book_name"] or ""))
        rows = conn.execute(
            """
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE book_name = ? OR instr(book_name, ?) > 0
            LIMIT ?
            """,
            (book, book, max(4, limit // 2)),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:24]:
                push_section(str(item))

    entity_limit = max(4, min(limit, 24))
    for entity in focus_entities[:4]:
        rows = conn.execute(
            """
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE group_title = ?
               OR instr(group_title, ?) > 0
               OR instr(entity_tags, ?) > 0
               OR instr(topic_tags, ?) > 0
               OR instr(group_summary, ?) > 0
            LIMIT ?
            """,
            (entity, entity, entity, entity, entity, entity_limit),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:24]:
                push_section(str(item))
        if _is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
            rows = conn.execute(
                """
                SELECT DISTINCT section_key, book_name
                FROM docs
                WHERE chunk_level = 3
                  AND instr(book_name, '本草') > 0
                  AND (
                        chapter_title = ?
                     OR instr(chapter_title, ?) > 0
                     OR instr(text, ?) > 0
                  )
                LIMIT ?
                """,
                (entity, entity, entity, max(10, limit)),
            ).fetchall()
            for row in rows:
                push_section(str(row["section_key"] or ""))
                push_book(str(row["book_name"] or ""))
        if not books_in_query and len(entity) >= 2:
            rows = conn.execute(
                """
                SELECT DISTINCT section_key, book_name
                FROM docs
                WHERE chunk_level = 3
                  AND (
                        chapter_title = ?
                     OR instr(chapter_title, ?) > 0
                  )
                LIMIT ?
                """,
                (entity, entity, max(8, limit)),
            ).fetchall()
            for row in rows:
                push_section(str(row["section_key"] or ""))
                push_book(str(row["book_name"] or ""))

    direct_terms = list(dict.fromkeys([*focus_entities, *query_terms[:8]]))
    book_filter_values = candidate_books[:8]
    book_filter_sql = ""
    if book_filter_values:
        placeholders = ",".join("?" for _ in book_filter_values)
        book_filter_sql = f" AND book_name IN ({placeholders})"
    for term in direct_terms[:10]:
        normalized = str(term or "").strip()
        if len(normalized) < 2 or _is_noisy_term(normalized):
            continue
        params: list[Any] = []
        params.extend(book_filter_values)
        params.extend([normalized, normalized, normalized, normalized, normalized, entity_limit])
        rows = conn.execute(
            f"""
            SELECT DISTINCT section_key, book_name
            FROM docs
            WHERE chunk_level = 3
              AND trim(COALESCE(section_key, '')) <> ''
              {book_filter_sql}
              AND (
                    chapter_title = ?
                 OR instr(chapter_title, ?) > 0
                 OR instr(section_summary, ?) > 0
                 OR instr(entity_tags, ?) > 0
                 OR instr(text, ?) > 0
              )
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        for row in rows:
            push_section(str(row["section_key"] or ""))
            push_book(str(row["book_name"] or ""))

    if flags.get("source_query") and candidate_books:
        rows = conn.execute(
            f"""
            SELECT group_key, book_name, child_section_keys
            FROM nav_groups
            WHERE book_name IN ({",".join("?" for _ in candidate_books[:8])})
            ORDER BY group_key ASC
            LIMIT ?
            """,
            (*candidate_books[:8], max(8, limit)),
        ).fetchall()
        for row in rows:
            push_group(str(row["group_key"] or ""))
            push_book(str(row["book_name"] or ""))
            try:
                children = json.loads(str(row["child_section_keys"] or "[]"))
            except Exception:
                children = []
            for item in children[:16]:
                push_section(str(item))

    return {
        "candidate_books": candidate_books[:8],
        "candidate_groups": candidate_groups[:32],
        "candidate_sections": candidate_sections[: max(8, min(limit, 96))],
    }


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
    answer_bearing_bonus = _answer_bearing_bonus(
        row=row,
        flags=flags,
        focus_entities=focus_entities,
    )
    score += answer_bearing_bonus
    return 1.0 + min(0.55, score * 0.06)


def _answer_bearing_bonus(
    *,
    row: dict[str, Any],
    flags: dict[str, bool],
    focus_entities: list[str],
) -> float:
    chapter_title = str(row.get("chapter_title", "") or "")
    section_summary = str(row.get("section_summary", "") or "")
    snippet = str(row.get("match_snippet", "") or "")
    text = str(row.get("text", "") or "")
    haystack = " ".join([chapter_title, section_summary, snippet, text])
    exact_anchor = any(entity and entity == chapter_title for entity in focus_entities[:3])
    anchor_overlap = sum(1 for entity in focus_entities[:3] if entity and entity in haystack)
    bonus = 0.0

    if flags.get("composition_query"):
        if any(marker in haystack for marker in ("各", "一钱", "二钱", "三钱", "四钱", "五钱", "去皮", "炙", "炒", "末", "研")):
            bonus += 1.8
        if exact_anchor:
            bonus += 1.6
        bonus += min(1.0, anchor_overlap * 0.4)

    if flags.get("property_query"):
        if any(marker in haystack for marker in ("功效", "主治", "归经", "性味", "味", "性", "入", "治")):
            bonus += 1.2
        if exact_anchor:
            bonus += 1.2
        bonus += min(0.8, anchor_overlap * 0.3)

    if flags.get("source_query"):
        if any(marker in haystack for marker in ("出自", "见于", "载于", "原文", "语出", "曰")):
            bonus += 1.4
        if exact_anchor:
            bonus += 1.2

    if flags.get("comparison_query"):
        if any(marker in haystack for marker in ("异", "同", "别", "兼", "并", "较", "不同")):
            bonus += 0.8

    return bonus


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


def _build_section_metadata(*, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
    compact = _compact_text(strip_classic_headers(section_text))
    summary = compact[:180]
    topic_tags: list[str] = []
    entity_tags: list[str] = []
    for keyword in TOPIC_KEYWORDS:
        if keyword in compact and keyword not in topic_tags:
            topic_tags.append(keyword)
    for formula in FORMULA_TAG_PATTERN.findall(f"{chapter_title} {compact}"):
        if formula not in entity_tags:
            entity_tags.append(formula)
    for span in CHINESE_SPAN_PATTERN.findall(chapter_title):
        if span not in topic_tags and span not in entity_tags and span not in {book_name, chapter_title}:
            topic_tags.append(span)
    representative_passages = []
    for fragment in re.split(r"[。！？!?]\s*", compact):
        candidate = fragment.strip()
        if len(candidate) >= 16:
            representative_passages.append(candidate[:120])
        if len(representative_passages) >= 2:
            break
    return {
        "section_summary": summary,
        "topic_tags": topic_tags[:12],
        "entity_tags": entity_tags[:12],
        "representative_passages": representative_passages,
    }


# Query planning, candidate generation, and reranking methods are maintained in
# a dedicated module for easier explanation and safer iteration.
_query_flags = ffm._query_flags
_books_in_query = ffm._books_in_query
_db_books_in_query = ffm._db_books_in_query
_is_probable_herb_property_query = ffm._is_probable_herb_property_query
_extract_content_spans = ffm._extract_content_spans
_descriptive_clause_terms = ffm._descriptive_clause_terms
_leading_subject_terms = ffm._leading_subject_terms
_high_precision_direct_terms = ffm._high_precision_direct_terms
_strip_query_noise = ffm._strip_query_noise
_looks_like_entity = ffm._looks_like_entity
_contains_query_scaffolding = ffm._contains_query_scaffolding
_is_noisy_term = ffm._is_noisy_term
_is_front_matter_title = ffm._is_front_matter_title
_normalize_formula_match = ffm._normalize_formula_match
_expand_entity_aliases = ffm._expand_entity_aliases
_collapse_overlapping_terms = ffm._collapse_overlapping_terms
_sanitize_focus_entities = ffm._sanitize_focus_entities
_intent_terms = ffm._intent_terms
_clean_candidate_term = ffm._clean_candidate_term
_compact_phrase = ffm._compact_phrase
_tokenized_query_terms = ffm._tokenized_query_terms
_fts_quote = ffm._fts_quote
_join_match_terms = ffm._join_match_terms
_build_match_queries = ffm._build_match_queries
_gather_metadata_candidates = ffm._gather_metadata_candidates
_build_sqlite_in_clause = ffm._build_sqlite_in_clause
_field_overlap_multiplier = ffm._field_overlap_multiplier
_split_compare_entities = ffm._split_compare_entities
_entity_from_relation_query = ffm._entity_from_relation_query
_extract_focus_entities = ffm._extract_focus_entities
_prepare_match_terms = ffm._prepare_match_terms


class SectionSummaryCache:
    def __init__(self, cache_path: Path | None = None):
        self.legacy_json_path: Path | None = None
        if cache_path is not None and cache_path.suffix.lower() == ".json":
            self.legacy_json_path = cache_path
            self.cache_path = cache_path.with_suffix(".sqlite")
        else:
            self.cache_path = cache_path
            if cache_path is not None:
                legacy_candidate = cache_path.with_suffix(".json")
                if legacy_candidate.exists():
                    self.legacy_json_path = legacy_candidate
        self._initialized = False
        self._init_lock = Lock()
        if self.cache_path is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        if self.cache_path is None:
            raise RuntimeError("section_summary_cache_not_configured")
        conn = sqlite3.connect(self.cache_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized or self.cache_path is None:
            return
        with self._init_lock:
            if self._initialized:
                return
            with closing(self._connect()) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS section_summaries (
                        section_key TEXT PRIMARY KEY,
                        section_summary TEXT NOT NULL DEFAULT '',
                        topic_tags TEXT NOT NULL DEFAULT '[]',
                        entity_tags TEXT NOT NULL DEFAULT '[]',
                        representative_passages TEXT NOT NULL DEFAULT '[]',
                        updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                    )
                    """
                )
                count_row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
                existing_count = int(count_row[0]) if count_row and count_row[0] is not None else 0
                if existing_count <= 0 and self.legacy_json_path is not None and self.legacy_json_path.exists():
                    try:
                        payload = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
                    except Exception:
                        payload = {}
                    if isinstance(payload, dict) and payload:
                        rows = []
                        for section_key, item in payload.items():
                            if not isinstance(item, dict):
                                continue
                            rows.append(
                                (
                                    str(section_key).strip(),
                                    str(item.get("section_summary", "")),
                                    json.dumps(list(item.get("topic_tags", [])) if isinstance(item.get("topic_tags", []), list) else [], ensure_ascii=False),
                                    json.dumps(list(item.get("entity_tags", [])) if isinstance(item.get("entity_tags", []), list) else [], ensure_ascii=False),
                                    json.dumps(list(item.get("representative_passages", [])) if isinstance(item.get("representative_passages", []), list) else [], ensure_ascii=False),
                                )
                            )
                        if rows:
                            conn.executemany(
                                """
                                INSERT OR REPLACE INTO section_summaries
                                (section_key, section_summary, topic_tags, entity_tags, representative_passages)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                rows,
                            )
                conn.commit()
            self._initialized = True

    def load(self) -> dict[str, dict[str, Any]]:
        self._ensure_initialized()
        if self.cache_path is None:
            return {}
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT section_key, section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                """
            ).fetchall()
        payload: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                topic_tags = json.loads(str(row["topic_tags"] or "[]"))
            except Exception:
                topic_tags = []
            try:
                entity_tags = json.loads(str(row["entity_tags"] or "[]"))
            except Exception:
                entity_tags = []
            try:
                representative_passages = json.loads(str(row["representative_passages"] or "[]"))
            except Exception:
                representative_passages = []
            payload[str(row["section_key"])] = {
                "section_summary": str(row["section_summary"] or ""),
                "topic_tags": topic_tags if isinstance(topic_tags, list) else [],
                "entity_tags": entity_tags if isinstance(entity_tags, list) else [],
                "representative_passages": representative_passages if isinstance(representative_passages, list) else [],
            }
        return payload

    def get(self, section_key: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        if self.cache_path is None:
            return None
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                WHERE section_key = ?
                LIMIT 1
                """,
                (section_key,),
            ).fetchone()
        if row is None:
            return None
        try:
            topic_tags = json.loads(str(row["topic_tags"] or "[]"))
        except Exception:
            topic_tags = []
        try:
            entity_tags = json.loads(str(row["entity_tags"] or "[]"))
        except Exception:
            entity_tags = []
        try:
            representative_passages = json.loads(str(row["representative_passages"] or "[]"))
        except Exception:
            representative_passages = []
        return {
            "section_summary": str(row["section_summary"] or ""),
            "topic_tags": topic_tags if isinstance(topic_tags, list) else [],
            "entity_tags": entity_tags if isinstance(entity_tags, list) else [],
            "representative_passages": representative_passages if isinstance(representative_passages, list) else [],
        }

    def has(self, section_key: str) -> bool:
        self._ensure_initialized()
        if self.cache_path is None:
            return False
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM section_summaries WHERE section_key = ? LIMIT 1",
                (section_key,),
            ).fetchone()
        return row is not None

    def count(self) -> int:
        self._ensure_initialized()
        if self.cache_path is None:
            return 0
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(1) FROM section_summaries").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def set(self, section_key: str, metadata: dict[str, Any]) -> None:
        if self.cache_path is None:
            return
        self._ensure_initialized()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO section_summaries
                (section_key, section_summary, topic_tags, entity_tags, representative_passages, updated_at)
                VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                """,
                (
                    section_key,
                    str(metadata.get("section_summary", "")),
                    json.dumps(list(metadata.get("topic_tags", [])) if isinstance(metadata.get("topic_tags", []), list) else [], ensure_ascii=False),
                    json.dumps(list(metadata.get("entity_tags", [])) if isinstance(metadata.get("entity_tags", []), list) else [], ensure_ascii=False),
                    json.dumps(list(metadata.get("representative_passages", [])) if isinstance(metadata.get("representative_passages", []), list) else [], ensure_ascii=False),
                ),
            )
            conn.commit()


def normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("text", "") or "")
    filename = str(item.get("filename", "") or item.get("source_file", "") or "")
    file_path = str(item.get("file_path", "") or "")
    page_number = item.get("page_number", item.get("source_page", 0))
    book_name = str(item.get("book_name", "") or "").strip() or extract_book_name(
        text=text,
        filename=filename,
        file_path=file_path,
    )
    chapter_title = str(item.get("chapter_title", "") or "").strip() or extract_chapter_title(
        text=text,
        page_number=int(page_number or 0),
        file_path=file_path,
    )
    return {
        "chunk_id": item.get("chunk_id", ""),
        "text": text,
        "score": float(item.get("score", 0.0) or 0.0),
        "source_file": filename,
        "source_page": page_number,
        "filename": filename,
        "file_path": file_path,
        "page_number": page_number,
        "file_type": item.get("file_type", ""),
        "chunk_idx": item.get("chunk_idx", 0),
        "chunk_level": item.get("chunk_level", 0),
        "parent_chunk_id": item.get("parent_chunk_id", ""),
        "root_chunk_id": item.get("root_chunk_id", ""),
        "book_name": book_name,
        "chapter_title": chapter_title,
        "section_key": item.get("section_key", ""),
        "section_summary": item.get("section_summary", ""),
        "topic_tags": item.get("topic_tags", ""),
        "entity_tags": item.get("entity_tags", ""),
        "representative_passages": item.get("representative_passages", []),
        "match_snippet": item.get("match_snippet"),
        "rrf_rank": item.get("rrf_rank"),
        "rerank_score": item.get("rerank_score"),
    }


def build_section_response(
    *,
    path: str,
    payload: dict[str, Any],
    parent_store: "ParentChunkStore",
) -> dict[str, Any]:
    raw_items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
    if not raw_items:
        return {
            "backend": "files-first",
            "path": path,
            "status": payload.get("status", "empty"),
            "items": [],
            "count": 0,
        }

    normalized_items = [normalize_chunk(item) for item in raw_items if isinstance(item, dict)]
    if not normalized_items:
        return {
            "backend": "files-first",
            "path": path,
            "status": payload.get("status", "empty"),
            "items": [],
            "count": 0,
        }

    book_name = str(normalized_items[0].get("book_name", "") or "").strip()
    chapter_title = str(normalized_items[0].get("chapter_title", "") or "").strip()
    parent_candidates = [
        str(item.get("parent_chunk_id", "")).strip()
        for item in normalized_items
        if str(item.get("parent_chunk_id", "")).strip()
    ]
    section_text = ""
    if parent_candidates:
        parent_docs = parent_store.get_documents_by_ids(list(dict.fromkeys(parent_candidates)))
        if parent_docs:
            section_text = str(parent_docs[0].get("text", "") or "").strip()

    if not section_text:
        section_text = "\n".join(
            [
                line
                for line in [
                    f"古籍：{book_name}" if book_name else "",
                    f"篇名：{chapter_title}" if chapter_title else "",
                    merge_section_bodies([strip_classic_headers(item.get("text", "")) for item in normalized_items]),
                ]
                if line
            ]
        ).strip()
    metadata = _build_section_metadata(
        book_name=book_name,
        chapter_title=chapter_title,
        section_text=section_text,
    )

    return {
        "backend": "files-first",
        "path": path,
        "status": "ok",
        "count": len(normalized_items),
        "section": {
            "book_name": book_name,
            "chapter_title": chapter_title,
            "text": section_text,
            "source_file": normalized_items[0].get("source_file", ""),
            "page_number": normalized_items[0].get("page_number", 0),
            "section_summary": metadata["section_summary"],
            "topic_tags": metadata["topic_tags"],
            "entity_tags": metadata["entity_tags"],
            "representative_passages": metadata["representative_passages"],
        },
        "items": normalized_items,
    }


class ParentChunkStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.store_path.exists():
            return {}
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert_documents(self, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0
        payload = self._load()
        count = 0
        for doc in docs:
            chunk_id = str(doc.get("chunk_id", "")).strip()
            if not chunk_id:
                continue
            payload[chunk_id] = dict(doc)
            count += 1
        self._save(payload)
        return count

    def get_documents_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        payload = self._load()
        return [payload[item] for item in chunk_ids if item in payload]


class LocalFilesFirstStore:
    def __init__(self, store_path: Path, *, tokenizer, summary_cache_path: Path | None = None, llm_summary_fn: Callable[[str, str, str], dict[str, Any]] | None = None):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.summary_cache = SectionSummaryCache(summary_cache_path)
        self.llm_summary_fn = llm_summary_fn

    def _schema_status(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"exists": False, "compatible": False, "version": 0}
        try:
            with closing(sqlite3.connect(self.store_path)) as conn:
                tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "docs" not in tables:
                    return {"exists": True, "compatible": False, "version": 0}
                doc_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
                meta_version = 0
                if "files_first_meta" in tables:
                    try:
                        row = conn.execute("SELECT value FROM files_first_meta WHERE key = 'schema_version' LIMIT 1").fetchone()
                        meta_version = int(row[0]) if row and row[0] is not None else 0
                    except Exception:
                        meta_version = 0
                compatible = (
                    doc_columns >= REQUIRED_DOC_COLUMNS
                    and "nav_groups" in tables
                    and "nav_groups_fts" in tables
                    and "book_outlines" in tables
                    and "book_outlines_fts" in tables
                    and meta_version >= FILES_FIRST_SCHEMA_VERSION
                )
                return {"exists": True, "compatible": compatible, "version": meta_version}
        except Exception:
            return {"exists": True, "compatible": False, "version": 0}

    def ensure_schema(self) -> dict[str, Any]:
        status = self._schema_status()
        if not status["exists"] or status["compatible"]:
            return status
        try:
            with closing(sqlite3.connect(self.store_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key
                    FROM docs
                    """
                ).fetchall()
        except Exception:
            return status
        base_rows = [dict(row) for row in rows if isinstance(row, sqlite3.Row)]
        if not base_rows:
            self.reset()
            return {"exists": False, "compatible": False, "version": 0, "migrated": True}
        rows = []
        gc.collect()
        time.sleep(0.2)
        try:
            self.rebuild(base_rows)
        except PermissionError:
            self._migrate_legacy_schema_in_place(base_rows)
        migrated = self._schema_status()
        migrated["migrated"] = True
        return migrated

    def _migrate_legacy_schema_in_place(self, rows: list[dict[str, Any]]) -> None:
        with closing(sqlite3.connect(self.store_path)) as conn:
            existing_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(docs)").fetchall()}
            for column in ("section_summary", "topic_tags", "entity_tags"):
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE docs ADD COLUMN {column} TEXT")
            conn.execute("CREATE TABLE IF NOT EXISTS files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("DROP TABLE IF EXISTS docs_fts")
            conn.execute("DROP TABLE IF EXISTS sections")
            conn.execute("DROP TABLE IF EXISTS sections_fts")
            conn.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
            )
            fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
            update_rows: list[tuple[str, str, str, str, str, str, str]] = []
            for row in rows:
                chunk_id = str(row.get("chunk_id", "")).strip()
                if not chunk_id:
                    continue
                text = str(row.get("text", "") or "")
                filename = str(row.get("filename", "") or "")
                file_path = str(row.get("file_path", "") or "")
                page_number = int(row.get("page_number", 0) or 0)
                book_name = str(row.get("book_name", "")).strip() or extract_book_name(text=text, filename=filename, file_path=file_path)
                chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                section_key = str(row.get("section_key", "")).strip() or build_section_key(book_name=book_name, chapter_title=chapter_title, page_number=page_number, file_path=file_path)
                metadata = self._resolve_section_metadata(
                    section_key=section_key or chunk_id,
                    book_name=book_name,
                    chapter_title=chapter_title,
                    section_text=text,
                )
                topic_tags_text = " ".join(metadata["topic_tags"])
                entity_tags_text = " ".join(metadata["entity_tags"])
                update_rows.append((book_name, chapter_title, section_key, metadata["section_summary"], topic_tags_text, entity_tags_text, chunk_id))
                search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
                fts_rows.append((chunk_id, " ".join(self.tokenizer.tokenize(search_basis)), book_name, chapter_title, text, filename, file_path, metadata["section_summary"], topic_tags_text, entity_tags_text))
            conn.executemany(
                "UPDATE docs SET book_name=?, chapter_title=?, section_key=?, section_summary=?, topic_tags=?, entity_tags=? WHERE chunk_id=?",
                update_rows,
            )
            conn.executemany(
                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                fts_rows,
            )
            conn.execute(
                "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
            )
            conn.commit()

    def _resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        cached = self.summary_cache.get(section_key)
        if cached:
            return {
                "section_summary": str(cached.get("section_summary", "")),
                "topic_tags": list(cached.get("topic_tags", []))[:12],
                "entity_tags": list(cached.get("entity_tags", []))[:12],
                "representative_passages": list(cached.get("representative_passages", []))[:2],
            }
        metadata = _build_section_metadata(book_name=book_name, chapter_title=chapter_title, section_text=section_text)
        if self.llm_summary_fn is not None:
            try:
                llm_metadata = self.llm_summary_fn(book_name, chapter_title, section_text)
            except Exception:
                llm_metadata = None
            if isinstance(llm_metadata, dict):
                metadata = {
                    "section_summary": str(llm_metadata.get("section_summary", metadata["section_summary"])),
                    "topic_tags": list(llm_metadata.get("topic_tags", metadata["topic_tags"]))[:12],
                    "entity_tags": list(llm_metadata.get("entity_tags", metadata["entity_tags"]))[:12],
                    "representative_passages": list(llm_metadata.get("representative_passages", metadata["representative_passages"]))[:2],
                }
                self.summary_cache.set(section_key, metadata)
        return metadata

    def health(self) -> dict[str, Any]:
        available = False
        docs = 0
        schema_status = self.ensure_schema()
        if self.store_path.exists():
            try:
                with closing(sqlite3.connect(self.store_path)) as conn:
                    docs = int(conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0])
                    available = docs > 0
            except Exception:
                available = False
                docs = 0
        return {
            "files_first_index_available": available,
            "files_first_index_path": str(self.store_path),
            "files_first_index_docs": docs,
            "files_first_schema_version": schema_status.get("version", 0),
            "files_first_schema_compatible": bool(schema_status.get("compatible")),
            "files_first_schema_migrated": bool(schema_status.get("migrated")),
        }

    def reset(self) -> None:
        if self.store_path.exists():
            self._unlink_with_retry(self.store_path)

    @staticmethod
    def _unlink_with_retry(path: Path) -> None:
        last_error: Exception | None = None
        for _ in range(5):
            try:
                path.unlink(missing_ok=True)
                return
            except PermissionError as exc:
                last_error = exc
                gc.collect()
                time.sleep(0.1)
        if last_error is not None:
            raise last_error

    @staticmethod
    def _replace_file(target_path: Path, replacement_path: Path) -> None:
        last_error: Exception | None = None
        for _ in range(5):
            try:
                replacement_path.replace(target_path)
                return
            except PermissionError as exc:
                last_error = exc
                gc.collect()
                time.sleep(0.1)
        if last_error is not None:
            raise last_error

    def _default_state_path(self) -> Path:
        return self.store_path.with_suffix(f"{self.store_path.suffix}.state.json")

    @staticmethod
    def _initialize_build_db(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-200000")
        conn.execute("CREATE TABLE IF NOT EXISTS files_first_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT, section_summary TEXT, topic_tags TEXT, entity_tags TEXT)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(chunk_id UNINDEXED, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS nav_groups (group_key TEXT PRIMARY KEY, book_name TEXT, archetype TEXT, group_title TEXT, group_summary TEXT, topic_tags TEXT, entity_tags TEXT, representative_passages TEXT, question_types_supported TEXT, section_count INTEGER, leaf_count INTEGER, start_section_key TEXT, end_section_key TEXT, section_index_range TEXT, page_range TEXT, child_section_keys TEXT, child_titles TEXT)"
        )
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS nav_groups_fts USING fts5(group_key UNINDEXED, search_text)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS book_outlines (book_name TEXT PRIMARY KEY, archetype TEXT, book_summary TEXT, major_topics TEXT, major_entities TEXT, group_count INTEGER, section_count INTEGER, leaf_count INTEGER, group_keys TEXT, query_types_supported TEXT)"
        )
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS book_outlines_fts USING fts5(book_name UNINDEXED, search_text)")
        conn.commit()

    @staticmethod
    def _ensure_post_docs_indexes(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_section_order ON docs(section_key, chunk_idx, page_number, chunk_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_book_chapter ON docs(book_name, chapter_title, section_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nav_groups_book ON nav_groups(book_name, group_key)")
        conn.commit()

    @staticmethod
    def _print_build_progress(*, stage: str, done: int, total: int, started_at: float) -> None:
        elapsed = max(0.1, time.perf_counter() - started_at)
        rate = done / elapsed if done > 0 else 0.0
        eta = (total - done) / rate if rate > 0 else 0.0
        print(
            f"[files-first:{stage}] {_progress_bar(done, total)} "
            f"{done}/{total} ({done * 100.0 / max(1, total):.1f}%) "
            f"rate={rate:.1f}/s eta={_format_seconds(eta)}",
            flush=True,
        )

    @staticmethod
    def _print_stage_banner(*, stage: str, detail: str) -> None:
        print(f"[files-first:{stage}] {detail}", flush=True)

    @staticmethod
    def _count_rows_in_db(path: Path) -> dict[str, int]:
        if not path.exists():
            return {"docs": 0, "nav_groups": 0, "book_outlines": 0}
        with closing(sqlite3.connect(path)) as conn:
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {
                "docs": int(conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0]) if "docs" in tables else 0,
                "nav_groups": int(conn.execute("SELECT COUNT(1) FROM nav_groups").fetchone()[0]) if "nav_groups" in tables else 0,
                "book_outlines": int(conn.execute("SELECT COUNT(1) FROM book_outlines").fetchone()[0]) if "book_outlines" in tables else 0,
            }

    @staticmethod
    def _load_nav_group_seed_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                chunk_id,
                chunk_level,
                book_name,
                chapter_title,
                section_key,
                page_number
            FROM docs
            WHERE trim(COALESCE(section_key, '')) <> ''
            ORDER BY book_name ASC, section_key ASC, page_number ASC, chunk_idx ASC, chunk_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _rebuild_nav_groups(self, conn: sqlite3.Connection, *, show_progress: bool) -> dict[str, Any]:
        if show_progress:
            self._print_stage_banner(stage="nav-groups", detail="building adaptive nav groups from section summaries")
        seed_rows = self._load_nav_group_seed_rows(conn)
        if show_progress:
            book_count = len({str(row.get("book_name", "") or "").strip() for row in seed_rows if str(row.get("book_name", "") or "").strip()})
            section_count = len({str(row.get("section_key", "") or "").strip() for row in seed_rows if str(row.get("section_key", "") or "").strip()})
            self._print_stage_banner(stage="nav-groups", detail=f"seed_rows={len(seed_rows)} books={book_count} sections={section_count}")
        last_reported = 0

        def _progress(current: int, total: int, _book_name: str) -> None:
            nonlocal last_reported
            if not show_progress or total <= 0:
                return
            if current != total and (current - last_reported) < 25:
                return
            last_reported = current
            self._print_build_progress(stage="nav-groups", done=current, total=total, started_at=docs_started_at)

        docs_started_at = time.perf_counter()
        payload = build_nav_group_payload_from_rows(
            corpus_rows=seed_rows,
            summary_cache_path=self.summary_cache.cache_path if self.summary_cache.cache_path is not None else Path(""),
            progress_callback=_progress if show_progress else None,
        )
        nav_groups = payload["nav_groups"]
        book_outlines = payload["book_outlines"]
        conn.execute("DELETE FROM nav_groups")
        conn.execute("DELETE FROM nav_groups_fts")
        conn.execute("DELETE FROM book_outlines")
        conn.execute("DELETE FROM book_outlines_fts")
        if nav_groups:
            conn.executemany(
                """
                INSERT INTO nav_groups (
                    group_key, book_name, archetype, group_title, group_summary, topic_tags, entity_tags,
                    representative_passages, question_types_supported, section_count, leaf_count,
                    start_section_key, end_section_key, section_index_range, page_range, child_section_keys, child_titles
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["group_key"],
                        item["book_name"],
                        item["archetype"],
                        item["group_title"],
                        item["group_summary"],
                        json.dumps(item["topic_tags"], ensure_ascii=False),
                        json.dumps(item["entity_tags"], ensure_ascii=False),
                        json.dumps(item["representative_passages"], ensure_ascii=False),
                        json.dumps(item["question_types_supported"], ensure_ascii=False),
                        int(item["section_count"]),
                        int(item["leaf_count"]),
                        item["start_section_key"],
                        item["end_section_key"],
                        json.dumps(item["section_index_range"], ensure_ascii=False),
                        json.dumps(item["page_range"], ensure_ascii=False),
                        json.dumps(item["child_section_keys"], ensure_ascii=False),
                        json.dumps(item["child_titles"], ensure_ascii=False),
                    )
                    for item in nav_groups
                ],
            )
            conn.executemany(
                "INSERT INTO nav_groups_fts (group_key, search_text) VALUES (?, ?)",
                [(item["group_key"], item["search_text"]) for item in nav_groups],
            )
        if book_outlines:
            conn.executemany(
                """
                INSERT INTO book_outlines (
                    book_name, archetype, book_summary, major_topics, major_entities,
                    group_count, section_count, leaf_count, group_keys, query_types_supported
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["book_name"],
                        item["archetype"],
                        item["book_summary"],
                        json.dumps(item["major_topics"], ensure_ascii=False),
                        json.dumps(item["major_entities"], ensure_ascii=False),
                        int(item["group_count"]),
                        int(item["section_count"]),
                        int(item["leaf_count"]),
                        json.dumps(item["group_keys"], ensure_ascii=False),
                        json.dumps(item["query_types_supported"], ensure_ascii=False),
                    )
                    for item in book_outlines
                ],
            )
            conn.executemany(
                "INSERT INTO book_outlines_fts (book_name, search_text) VALUES (?, ?)",
                [
                    (
                        item["book_name"],
                        " ".join(
                            [
                                item["book_name"],
                                item["book_summary"],
                                " ".join(item["major_topics"]),
                                " ".join(item["major_entities"]),
                                " ".join(item["query_types_supported"]),
                            ]
                        ).strip(),
                    )
                    for item in book_outlines
                ],
            )
        conn.commit()
        if show_progress:
            self._print_stage_banner(
                stage="nav-groups",
                detail=f"books={payload['manifest']['books']} nav_groups={payload['manifest']['nav_groups']} outlines={payload['manifest']['book_outlines']}",
            )
        return payload["manifest"]

    def rebuild(
        self,
        rows: list[dict[str, Any]],
        *,
        state_path: Path | None = None,
        reset: bool = False,
        show_progress: bool = False,
        batch_size: int = 512,
    ) -> dict[str, Any]:
        target_path = self.store_path
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        state_path = state_path or self._default_state_path()
        existing_target_counts = self._count_rows_in_db(target_path)
        reuse_existing_docs = (
            not reset
            and existing_target_counts["docs"] >= len(rows)
            and existing_target_counts["nav_groups"] <= 0
        )
        if reuse_existing_docs:
            state = {
                "status": "running_nav_groups",
                "temp_path": str(target_path),
                "target_path": str(target_path),
                "total_rows": len(rows),
                "docs_processed": len(rows),
                "nav_groups_built": 0,
                "updated_at": time.time(),
                "reused_existing_docs": True,
            }
            _write_json(state_path, state)
            with closing(sqlite3.connect(target_path)) as conn:
                self._initialize_build_db(conn)
                if show_progress:
                    self._print_stage_banner(stage="docs", detail=f"reusing existing docs rows={existing_target_counts['docs']}")
                    self._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
                self._ensure_post_docs_indexes(conn)
                nav_manifest = self._rebuild_nav_groups(conn, show_progress=show_progress)
                state.update({"status": "running_nav_groups", "nav_groups_built": int(nav_manifest.get("nav_groups", 0)), "updated_at": time.time()})
                _write_json(state_path, state)
                conn.execute(
                    "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
                )
                conn.commit()
            state.update(
                {
                    "status": "completed",
                    "docs_processed": len(rows),
                    "nav_groups_built": int(nav_manifest.get("nav_groups", 0)),
                    "completed_at": time.time(),
                    "updated_at": time.time(),
                    "reused_existing_docs": True,
                }
            )
            _write_json(state_path, state)
            return {
                "indexed_files_first_docs": len(rows),
                "indexed_nav_groups": int(nav_manifest.get("nav_groups", 0)),
                "files_first_index_path": str(self.store_path),
                "state_path": str(state_path),
                "resumed": True,
                "reused_existing_docs": True,
            }
        if reset:
            if temp_path.exists():
                self._unlink_with_retry(temp_path)
            if state_path.exists():
                self._unlink_with_retry(state_path)
        state = _read_json(state_path, {})
        if not isinstance(state, dict):
            state = {}
        resume_ready = (
            bool(state)
            and str(state.get("temp_path", "")) == str(temp_path)
            and temp_path.exists()
            and state.get("status") in {"running_docs", "running_nav_groups", "interrupted", "failed"}
            and int(state.get("total_rows", 0) or 0) == len(rows)
        )
        if not resume_ready and temp_path.exists():
            self._unlink_with_retry(temp_path)
        if not resume_ready:
            with closing(sqlite3.connect(temp_path)) as conn:
                self._initialize_build_db(conn)
            state = {
                "status": "running_docs",
                "temp_path": str(temp_path),
                "target_path": str(target_path),
                "total_rows": len(rows),
                "docs_processed": 0,
                "nav_groups_built": 0,
                "updated_at": time.time(),
            }
            _write_json(state_path, state)

        batch_size = max(64, int(batch_size or 512))
        docs_started_at = time.perf_counter()
        try:
            with closing(sqlite3.connect(temp_path)) as conn:
                self._initialize_build_db(conn)
                docs_processed = int(state.get("docs_processed", 0) or 0)
                if docs_processed < len(rows):
                    payload_rows: list[tuple[Any, ...]] = []
                    fts_rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
                    for index in range(docs_processed, len(rows)):
                        row = rows[index]
                        chunk_id = str(row.get("chunk_id", "")).strip()
                        if not chunk_id:
                            continue
                        text = str(row.get("text", ""))
                        filename = str(row.get("filename", ""))
                        file_path = str(row.get("file_path", ""))
                        page_number = int(row.get("page_number", 0) or 0)
                        book_name = str(row.get("book_name", "")).strip() or extract_book_name(text=text, filename=filename, file_path=file_path)
                        chapter_title = str(row.get("chapter_title", "")).strip() or extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                        section_key = str(row.get("section_key", "")).strip() or build_section_key(book_name=book_name, chapter_title=chapter_title, page_number=page_number, file_path=file_path)
                        metadata = self._resolve_section_metadata(
                            section_key=section_key or chunk_id,
                            book_name=book_name,
                            chapter_title=chapter_title,
                            section_text=text,
                        )
                        topic_tags_text = " ".join(metadata["topic_tags"])
                        entity_tags_text = " ".join(metadata["entity_tags"])
                        payload_rows.append(
                            (
                                chunk_id,
                                text,
                                filename,
                                str(row.get("file_type", "TXT")),
                                file_path,
                                page_number,
                                int(row.get("chunk_idx", 0) or 0),
                                str(row.get("parent_chunk_id", "")),
                                str(row.get("root_chunk_id", "")),
                                int(row.get("chunk_level", 0) or 0),
                                book_name,
                                chapter_title,
                                section_key,
                                metadata["section_summary"],
                                topic_tags_text,
                                entity_tags_text,
                            )
                        )
                        search_basis = " ".join([book_name, chapter_title, filename, file_path, topic_tags_text, entity_tags_text, metadata["section_summary"], text])
                        fts_rows.append(
                            (
                                chunk_id,
                                " ".join(self.tokenizer.tokenize(search_basis)),
                                book_name,
                                chapter_title,
                                text,
                                filename,
                                file_path,
                                metadata["section_summary"],
                                topic_tags_text,
                                entity_tags_text,
                            )
                        )
                        if len(payload_rows) >= batch_size:
                            conn.executemany(
                                "INSERT OR REPLACE INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                payload_rows,
                            )
                            conn.executemany(
                                "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                fts_rows,
                            )
                            conn.commit()
                            docs_processed = index + 1
                            state.update({"status": "running_docs", "docs_processed": docs_processed, "updated_at": time.time()})
                            _write_json(state_path, state)
                            if show_progress:
                                self._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=docs_started_at)
                            payload_rows = []
                            fts_rows = []
                    if payload_rows:
                        conn.executemany(
                            "INSERT OR REPLACE INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            payload_rows,
                        )
                        conn.executemany(
                            "INSERT INTO docs_fts (chunk_id, search_text, book_name, chapter_title, text, filename, file_path, section_summary, topic_tags, entity_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            fts_rows,
                        )
                        conn.commit()
                        docs_processed = len(rows)
                        state.update({"status": "running_docs", "docs_processed": docs_processed, "updated_at": time.time()})
                        _write_json(state_path, state)
                        if show_progress:
                            self._print_build_progress(stage="docs", done=docs_processed, total=len(rows), started_at=docs_started_at)

                if show_progress:
                    self._print_stage_banner(stage="indexes", detail="creating docs/nav_groups helper indexes")
                self._ensure_post_docs_indexes(conn)
                state.update({"status": "running_nav_groups", "docs_processed": len(rows), "updated_at": time.time()})
                _write_json(state_path, state)
                nav_manifest = self._rebuild_nav_groups(conn, show_progress=show_progress)
                state.update({"status": "running_nav_groups", "nav_groups_built": int(nav_manifest.get("nav_groups", 0)), "updated_at": time.time()})
                _write_json(state_path, state)
                conn.execute(
                    "INSERT OR REPLACE INTO files_first_meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(FILES_FIRST_SCHEMA_VERSION)),
                )
                conn.commit()
        except KeyboardInterrupt:
            state.update({"status": "interrupted", "updated_at": time.time()})
            _write_json(state_path, state)
            raise
        except Exception as exc:
            state.update({"status": "failed", "last_error": str(exc), "updated_at": time.time()})
            _write_json(state_path, state)
            raise
        self._replace_file(target_path, temp_path)
        state.update(
            {
                "status": "completed",
                "docs_processed": len(rows),
                "nav_groups_built": int(nav_manifest.get("nav_groups", 0) if 'nav_manifest' in locals() else 0),
                "completed_at": time.time(),
                "updated_at": time.time(),
            }
        )
        _write_json(state_path, state)
        return {
            "indexed_files_first_docs": len(rows),
            "indexed_nav_groups": int(nav_manifest.get("nav_groups", 0) if 'nav_manifest' in locals() else 0),
            "files_first_index_path": str(self.store_path),
            "state_path": str(state_path),
            "resumed": bool(resume_ready),
        }

    def search(self, *, query: str, query_context: dict[str, Any] | None = None, top_k: int, candidate_k: int, leaf_level: int) -> tuple[list[dict[str, Any]], str]:
        self.ensure_schema()
        if not self.store_path.exists():
            return [], "fts_missing"
        effective_top_k = max(int(top_k or 0), 5)
        flags, focus_entities, books_in_query, expanded_query, weak_anchor, need_broad_recall = _apply_query_context(
            query=query,
            tokenizer=self.tokenizer,
            query_context=query_context,
        )
        focus_search_terms = _sanitize_focus_entities(_expand_entity_aliases(focus_entities))
        alias_terms = [term for term in focus_search_terms if term not in focus_entities]
        auxiliary_terms = _intent_terms(flags)
        primary_terms = list(dict.fromkeys([*focus_entities, *books_in_query]))
        expanded_terms = _tokenized_query_terms(expanded_query, self.tokenizer, limit=10) if expanded_query else []
        fallback_terms = alias_terms if alias_terms else ([] if primary_terms else _prepare_match_terms(query, self.tokenizer))
        if expanded_terms:
            fallback_terms = list(dict.fromkeys([*fallback_terms, *expanded_terms]))
        ranking_terms = list(dict.fromkeys([*focus_entities, *books_in_query, *fallback_terms, *auxiliary_terms]))
        if not primary_terms:
            primary_terms = _tokenized_query_terms(query, self.tokenizer, limit=8)
            if not fallback_terms:
                fallback_terms = _prepare_match_terms(query, self.tokenizer)
            ranking_terms = list(dict.fromkeys([*primary_terms, *fallback_terms, *auxiliary_terms]))
        match_queries = _build_match_queries(
            primary_terms=primary_terms,
            auxiliary_terms=auxiliary_terms,
            fallback_terms=fallback_terms,
            flags=flags,
        )
        if not match_queries:
            return [], "fts_query_empty"
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            metadata_candidates = _gather_metadata_candidates(
                conn,
                query=query,
                focus_entities=focus_entities,
                query_terms=ranking_terms,
                books_in_query=books_in_query,
                flags=flags,
                limit=max(candidate_k, effective_top_k * 2),
            )
            candidate_books = metadata_candidates["candidate_books"]
            candidate_groups = metadata_candidates["candidate_groups"]
            candidate_sections = metadata_candidates["candidate_sections"]
            section_rows: list[dict[str, Any]] = []
            rows: list[dict[str, Any]] = []
            direct_seed_map: dict[str, dict[str, Any]] = {}
            section_limit = max(6, min(candidate_k * 2, max(effective_top_k * 2, 12)))
            leaf_limit = max(candidate_k * 2, effective_top_k * 2)
            unique_sections: set[str] = set()
            descriptive_clauses = [
                item
                for item in _descriptive_clause_terms(expanded_query or query)
                if (2 if books_in_query else 3) <= len(str(item or "").strip()) <= 16
            ]
            direct_terms_seed = [] if weak_anchor or need_broad_recall else _high_precision_direct_terms(expanded_query or query)
            direct_terms = list(
                dict.fromkeys(
                    [
                        *direct_terms_seed,
                        *[
                            item
                            for item in focus_entities
                            if item
                            and not _is_noisy_term(item)
                            and (
                                _looks_like_entity(item)
                                or item.endswith(("病", "证"))
                                or len(item) <= 8
                            )
                        ],
                    ]
                )
            )
            if direct_terms:
                docs_book_filter_sql = ""
                docs_book_filter_params: tuple[Any, ...] = ()
                has_strong_direct_anchor = any(
                    item.endswith(FORMULA_SUFFIXES) or item.endswith(("病", "证")) or len(item) <= 4
                    for item in direct_terms
                )
                if books_in_query:
                    target_books = books_in_query[:8]
                elif _is_probable_herb_property_query(query=query, focus_entities=focus_entities, flags=flags, books_in_query=books_in_query):
                    target_books = [book for book in candidate_books[:8] if "本草" in str(book)]
                elif has_strong_direct_anchor and not need_broad_recall:
                    target_books = []
                else:
                    target_books = candidate_books[:8]
                if target_books:
                    docs_book_filter_sql, docs_book_filter_params = _build_sqlite_in_clause(target_books, alias="d", column="book_name")
                for direct_term in direct_terms[:10]:
                    normalized_term = str(direct_term or "").strip()
                    if len(normalized_term) < 2 or _is_noisy_term(normalized_term):
                        continue
                    try:
                        current_direct = conn.execute(
                            f"""
                            SELECT
                                d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                                '[]' AS representative_passages,
                                substr(d.text, 1, 180) AS match_snippet,
                                -40.0 AS rank_score
                            FROM docs d
                            WHERE d.chunk_level = ?
                              AND (
                                    d.chapter_title = ?
                                 OR instr(d.chapter_title, ?) > 0
                                 OR instr(d.entity_tags, ?) > 0
                                 OR (? != '' AND length(?) >= 3 AND instr(d.text, ?) > 0)
                              ){docs_book_filter_sql}
                            ORDER BY
                                CASE WHEN d.chapter_title = ? THEN 0 ELSE 1 END,
                                CASE WHEN instr(d.chapter_title, ?) > 0 THEN 0 ELSE 1 END,
                                CASE WHEN instr(d.entity_tags, ?) > 0 THEN 0 ELSE 1 END,
                                d.book_name ASC,
                                d.page_number ASC,
                                d.chunk_idx ASC
                            LIMIT ?
                            """,
                            (
                                leaf_level,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                *docs_book_filter_params,
                                normalized_term,
                                normalized_term,
                                normalized_term,
                                max(effective_top_k * 2, 8),
                            ),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        current_direct = []
                    for row in current_direct:
                        payload = dict(row)
                        payload["_plan_rank"] = 0
                        payload["_direct_clause_hits"] = 0
                        direct_seed_map[str(payload.get("chunk_id") or "")] = payload
                        section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                        if section_key:
                            unique_sections.add(section_key)
            if descriptive_clauses:
                clause_book_filter_sql = ""
                clause_book_filter_params: tuple[Any, ...] = ()
                clause_target_books = books_in_query[:8] if books_in_query else candidate_books[:8]
                if clause_target_books:
                    clause_book_filter_sql, clause_book_filter_params = _build_sqlite_in_clause(clause_target_books, alias="d", column="book_name")
                for clause in descriptive_clauses[:8]:
                    normalized_clause = str(clause or "").strip()
                    if len(normalized_clause) < 3:
                        continue
                    compact_clause = _compact_phrase(normalized_clause)
                    try:
                        clause_rows = conn.execute(
                            f"""
                            SELECT
                                d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                                '[]' AS representative_passages,
                                substr(d.text, 1, 180) AS match_snippet,
                                -35.0 AS rank_score
                            FROM docs d
                            WHERE d.chunk_level = ?
                              AND (
                                    instr(d.chapter_title, ?) > 0
                                 OR instr(d.section_summary, ?) > 0
                                 OR instr(d.text, ?) > 0
                                 OR (? != '' AND length(?) >= 4 AND instr(
                                        replace(replace(replace(replace(replace(replace(replace(d.text, '，', ''), '。', ''), '、', ''), ' ', ''), '：', ''), '；', ''), '（', ''),
                                        ?
                                    ) > 0)
                              ){clause_book_filter_sql}
                            LIMIT ?
                            """,
                            (
                                leaf_level,
                                normalized_clause,
                                normalized_clause,
                                normalized_clause,
                                compact_clause,
                                compact_clause,
                                compact_clause,
                                *clause_book_filter_params,
                                max(effective_top_k * 2, 8),
                            ),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        clause_rows = []
                    for row in clause_rows:
                        payload = dict(row)
                        chunk_id = str(payload.get("chunk_id") or "").strip()
                        if not chunk_id:
                            continue
                        existing_payload = direct_seed_map.get(chunk_id)
                        if existing_payload is None:
                            payload["_plan_rank"] = 0
                            payload["_direct_clause_hits"] = 1
                            direct_seed_map[chunk_id] = payload
                        else:
                            existing_payload["_direct_clause_hits"] = int(existing_payload.get("_direct_clause_hits", 0) or 0) + 1
                        section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                        if section_key:
                            unique_sections.add(section_key)
            for plan_rank, match_query in enumerate(match_queries):
                section_filter_sql = ""
                section_filter_params: tuple[Any, ...] = ()
                docs_filter_sql = ""
                docs_filter_params: tuple[Any, ...] = ()
                if candidate_sections:
                    docs_filter_sql, docs_filter_params = _build_sqlite_in_clause(candidate_sections[:96], alias="d", column="section_key")
                elif candidate_books:
                    docs_filter_sql, docs_filter_params = _build_sqlite_in_clause(candidate_books[:8], alias="d", column="book_name")
                if candidate_groups:
                    section_filter_sql, section_filter_params = _build_sqlite_in_clause(candidate_groups[:96], alias="n", column="group_key")
                elif candidate_books:
                    section_filter_sql, section_filter_params = _build_sqlite_in_clause(candidate_books[:8], alias="n", column="book_name")
                try:
                    current_sections = conn.execute(
                        f"""
                        SELECT
                            n.group_key AS chunk_id,
                            trim(COALESCE(n.group_summary, '') || ' ' || COALESCE(n.representative_passages, '')) AS text,
                            n.book_name AS filename,'NAV_GROUP' AS file_type,'classic://' || n.book_name || '/nav-group-' || replace(substr(n.group_key, instr(n.group_key, '::nav::') + 7), '::', '-') AS file_path,0 AS page_number,
                            0 AS chunk_idx,'' AS parent_chunk_id,'' AS root_chunk_id,1 AS chunk_level,
                            n.book_name,n.group_title AS chapter_title,n.group_key AS section_key,n.group_summary AS section_summary,n.topic_tags,n.entity_tags,n.representative_passages,
                            substr(COALESCE(n.group_summary, n.group_title, ''), 1, 160) AS match_snippet,
                            bm25(nav_groups_fts) AS rank_score
                        FROM nav_groups_fts
                        JOIN nav_groups n ON n.group_key = nav_groups_fts.group_key
                        WHERE nav_groups_fts MATCH ?{section_filter_sql}
                        ORDER BY rank_score
                        LIMIT ?
                        """,
                        (match_query, *section_filter_params, section_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    current_sections = []
                try:
                    current_rows = conn.execute(
                        f"""
                        SELECT
                            d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                            '[]' AS representative_passages,
                            snippet(docs_fts, 4, '[', ']', '...', 18) AS match_snippet,
                            bm25(docs_fts, 2.5, 3.4, 2.6, 1.0, 0.25, 0.2, 1.4, 1.2, 1.2) AS rank_score
                        FROM docs_fts
                        JOIN docs d ON d.chunk_id = docs_fts.chunk_id
                        WHERE docs_fts MATCH ? AND d.chunk_level = ?{docs_filter_sql}
                        ORDER BY rank_score
                        LIMIT ?
                        """,
                        (match_query, leaf_level, *docs_filter_params, leaf_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    current_rows = []
                if not current_sections and not current_rows and plan_rank == 0 and len(match_queries) == 1:
                    return [], "fts_query_error"
                for row in current_sections:
                    payload = dict(row)
                    payload["_plan_rank"] = plan_rank
                    section_rows.append(payload)
                    section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                    if section_key:
                        unique_sections.add(section_key)
                for row in current_rows:
                    payload = dict(row)
                    payload["_plan_rank"] = plan_rank
                    rows.append(payload)
                    section_key = str(payload.get("section_key") or payload.get("chunk_id") or "").strip()
                    if section_key:
                        unique_sections.add(section_key)
                if plan_rank == 0 and len(unique_sections) >= max(effective_top_k * 2, min(candidate_k * 2, effective_top_k * 2)):
                    break
                if len(unique_sections) >= max(effective_top_k * 2, candidate_k * 2):
                    break
        if direct_seed_map:
            rows = [*direct_seed_map.values(), *rows]
        if not section_rows and rows:
            synthetic_sections: dict[str, dict[str, Any]] = {}
            for row in rows:
                section_key = str(row.get("section_key") or row.get("chunk_id") or "").strip()
                if not section_key or section_key in synthetic_sections:
                    continue
                synthetic_sections[section_key] = {
                    **row,
                    "chunk_id": section_key,
                    "file_type": "SECTION",
                    "file_path": _normalize_section_file_path(str(row.get("file_path", ""))),
                    "chunk_level": 2,
                    "parent_chunk_id": "",
                    "root_chunk_id": "",
                    "_plan_rank": int(row.get("_plan_rank", 0) or 0),
                }
            section_rows = list(synthetic_sections.values())
        results: list[dict[str, Any]] = []
        best_rows_by_section: dict[str, dict[str, Any]] = {}
        for row in list(section_rows) + list(rows):
            section_key = str(row["section_key"] or row["chunk_id"])
            existing = best_rows_by_section.get(section_key)
            if existing is None:
                best_rows_by_section[section_key] = row
                continue
            current_score = float(-(row["rank_score"]))
            existing_score = float(-(existing["rank_score"]))
            current_priority = 1 if str(row["file_type"]) == "SECTION" else 0
            existing_priority = 1 if str(existing["file_type"]) == "SECTION" else 0
            current_plan_rank = -int(row.get("_plan_rank", 0) or 0)
            existing_plan_rank = -int(existing.get("_plan_rank", 0) or 0)
            if (current_priority, current_plan_rank, current_score) > (existing_priority, existing_plan_rank, existing_score):
                best_rows_by_section[section_key] = row
        merged_rows = list(best_rows_by_section.values())
        if books_in_query:
            narrowed_rows = [
                row
                for row in merged_rows
                if any(
                    book and (
                        book in str(row.get("book_name", "") or "")
                        or str(row.get("book_name", "") or "") in book
                    )
                    for book in books_in_query
                )
            ]
            if narrowed_rows:
                merged_rows = narrowed_rows
        scored_rows: list[tuple[float, dict[str, Any]]] = []
        for row in merged_rows:
            base_score = float(-(row["rank_score"]))
            multiplier = _field_overlap_multiplier(
                row=row,
                focus_entities=focus_entities,
                books_in_query=books_in_query,
                query_terms=ranking_terms,
                flags=flags,
                plan_rank=int(row.get("_plan_rank", 0) or 0),
            )
            scored_rows.append((base_score * multiplier, row))
        scored_rows.sort(key=lambda item: item[0], reverse=True)
        for index, (final_score, row) in enumerate(scored_rows[:top_k], start=1):
            representative_passages = row["representative_passages"]
            try:
                parsed_representative_passages = json.loads(representative_passages) if isinstance(representative_passages, str) and representative_passages else []
            except json.JSONDecodeError:
                parsed_representative_passages = []
            results.append({"chunk_id": row["chunk_id"], "text": row["text"], "filename": row["filename"], "file_type": row["file_type"], "file_path": row["file_path"], "page_number": row["page_number"], "chunk_idx": row["chunk_idx"], "parent_chunk_id": row["parent_chunk_id"], "root_chunk_id": row["root_chunk_id"], "chunk_level": row["chunk_level"], "book_name": row["book_name"], "chapter_title": row["chapter_title"], "section_key": row["section_key"], "section_summary": row["section_summary"], "topic_tags": row["topic_tags"], "entity_tags": row["entity_tags"], "representative_passages": parsed_representative_passages, "match_snippet": row["match_snippet"], "score": final_score, "rrf_rank": index})
        retrieval_mode = "fts_local"
        return results, retrieval_mode

    def get_docs_by_chunk_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        self.ensure_schema()
        normalized_ids = [str(item or "").strip() for item in chunk_ids if str(item or "").strip()]
        if not normalized_ids or not self.store_path.exists():
            return []
        placeholders = ",".join("?" for _ in normalized_ids)
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    d.chunk_id,d.text,d.filename,d.file_type,d.file_path,d.page_number,d.chunk_idx,d.parent_chunk_id,d.root_chunk_id,d.chunk_level,
                    d.book_name,d.chapter_title,d.section_key,d.section_summary,d.topic_tags,d.entity_tags,
                    '[]' AS representative_passages,
                    substr(d.text, 1, 180) AS match_snippet
                FROM docs d
                WHERE d.chunk_id IN ({placeholders})
                """,
                normalized_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        self.ensure_schema()
        if not self.store_path.exists():
            return {"path": path, "items": [], "count": 0, "status": "missing"}
        normalized = str(path or "").strip()
        if not normalized.startswith("chapter://"):
            return {"path": normalized, "items": [], "count": 0, "status": "unsupported"}
        body = normalized.removeprefix("chapter://")
        book_name, _, chapter_title = body.partition("/")
        book_name = book_name.strip()
        chapter_title = chapter_title.strip()
        if not book_name or not chapter_title:
            return {"path": normalized, "items": [], "count": 0, "status": "invalid"}
        with closing(sqlite3.connect(self.store_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT chunk_id,text,filename,file_type,file_path,page_number,chunk_idx,parent_chunk_id,root_chunk_id,chunk_level,book_name,chapter_title,section_key,section_summary,topic_tags,entity_tags
                FROM docs
                WHERE book_name = ? AND chapter_title = ?
                ORDER BY chunk_level ASC, chunk_idx ASC, page_number ASC
                LIMIT ?
                """,
                (book_name, chapter_title, max(top_k, 64)),
            ).fetchall()
        items = [dict(row) for row in rows]
        if not items:
            return {"path": normalized, "items": [], "count": 0, "status": "empty"}
        response: dict[str, Any] = {"path": normalized, "status": "ok", "count": len(items), "items": items}
        summary_key = str(items[0].get("section_key", "") or "").strip()
        cached = self.summary_cache.get(summary_key) if summary_key else None
        if cached is None:
            section_text = merge_section_bodies([strip_classic_headers(str(item.get("text", ""))) for item in items])
            cached = self._resolve_section_metadata(
                section_key=summary_key or f"{book_name}::{chapter_title}",
                book_name=book_name,
                chapter_title=chapter_title,
                section_text=section_text,
            )
        section_text = merge_section_bodies([strip_classic_headers(str(item.get("text", ""))) for item in items])
        response["section"] = {
            "book_name": book_name,
            "chapter_title": chapter_title,
            "text": section_text,
            "source_file": items[0].get("filename", ""),
            "page_number": items[0].get("page_number", 0),
            "section_summary": str(cached.get("section_summary", "") if isinstance(cached, dict) else ""),
            "topic_tags": list(cached.get("topic_tags", []) if isinstance(cached, dict) else []),
            "entity_tags": list(cached.get("entity_tags", []) if isinstance(cached, dict) else []),
            "representative_passages": list(cached.get("representative_passages", []) if isinstance(cached, dict) else []),
        }
        return response
