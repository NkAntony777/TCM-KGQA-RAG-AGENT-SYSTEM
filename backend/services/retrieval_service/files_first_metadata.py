from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_section_file_path(file_path: str) -> str:
    classic_match = CLASSIC_PATH_PATTERN.match(file_path or "")
    if classic_match:
        return f"classic://{classic_match.group('book')}/{classic_match.group('section')}"
    return str(file_path or "")


def build_section_metadata(*, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
    compact = compact_text(strip_classic_headers(section_text))
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


__all__ = [
    "BOOK_LINE_PATTERN",
    "CHAPTER_LINE_PATTERN",
    "CLASSIC_PATH_PATTERN",
    "FORMULA_TAG_PATTERN",
    "CHINESE_SPAN_PATTERN",
    "TOPIC_KEYWORDS",
    "build_section_key",
    "build_section_metadata",
    "compact_text",
    "extract_book_name",
    "extract_chapter_title",
    "merge_section_bodies",
    "normalize_section_file_path",
    "strip_classic_headers",
]
