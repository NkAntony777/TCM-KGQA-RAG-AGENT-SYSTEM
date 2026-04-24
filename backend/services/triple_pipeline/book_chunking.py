from __future__ import annotations

import re
from pathlib import Path

from services.triple_pipeline_models import ChunkTask

DEFAULT_CHAPTER_EXCLUDES = ["篇名", "目录", "凡例", "序", "自序", "引言"]
WEAK_SECTION_TITLES = set(DEFAULT_CHAPTER_EXCLUDES) | {"前言", "后记", "跋", "附录", "卷首", "目录上", "目录下"}


def _safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _match_any_pattern(text: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return False
    return any(pattern and pattern in text for pattern in patterns)

def discover_books(self) -> list[Path]:
    if not self.config.books_dir.exists():
        raise FileNotFoundError(f"books_dir_not_found: {self.config.books_dir}")
    return sorted(self.config.books_dir.glob("*.txt"))

def recommend_books(self, limit: int = 12) -> list[Path]:
    preferred_keywords = (
        "医方",
        "局方",
        "方论",
        "本草纲目",
        "金匮",
        "伤寒",
        "汤头",
        "中医",
    )
    ranked: list[tuple[int, Path]] = []
    for path in self.discover_books():
        score = sum(3 for keyword in preferred_keywords if keyword in path.stem)
        score += max(0, 30 - len(path.stem)) * 0.01
        ranked.append((score, path))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    return [path for _, path in ranked[:limit]]

def split_book(self, path: Path) -> list[dict[str, str]]:
    text = _safe_read_text(path)
    text = text.replace("\r\n", "\n")
    parts = re.split(r"(<[^>]+>)", text)
    sections: list[dict[str, str]] = []
    current_title = f"{path.stem}_全文"
    current_body: list[str] = []

    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if chunk.startswith("<") and chunk.endswith(">"):
            if current_body:
                sections.append({"title": current_title, "content": "\n".join(current_body).strip()})
            current_title = chunk[1:-1].strip() or current_title
            current_body = []
        else:
            current_body.append(chunk)

    if current_body:
        sections.append({"title": current_title, "content": "\n".join(current_body).strip()})

    if not sections and text.strip():
        sections.append({"title": f"{path.stem}_全文", "content": text.strip()})
    return [section for section in sections if section["content"].strip()]

def _is_weak_section_title(self, title: str, book_name: str) -> bool:
    cleaned = (title or "").strip()
    return cleaned in WEAK_SECTION_TITLES or cleaned in {f"{book_name}_全文", "全文"}

def _normalize_chunk_label(self, title: str, book_name: str) -> str:
    cleaned = (title or "").strip()
    if not cleaned or self._is_weak_section_title(cleaned, book_name):
        return f"{book_name}_正文"
    return cleaned

def chunk_text(self, content: str) -> list[tuple[str, int, int]]:
    normalized = re.sub(r"\n{3,}", "\n\n", content.strip())
    if not normalized:
        return []
    if len(normalized) <= self.config.max_chunk_chars:
        return [(normalized, 0, len(normalized))]

    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(normalized):
        end = min(start + self.config.max_chunk_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind("\n", start, end)
            if boundary > start + self.config.max_chunk_chars // 2:
                end = boundary
        raw_slice = normalized[start:end]
        left_trim = len(raw_slice) - len(raw_slice.lstrip())
        right_trim = len(raw_slice.rstrip())
        chunk = raw_slice.strip()
        if chunk:
            chunk_start = start + left_trim
            chunk_end = start + right_trim
            chunks.append((chunk, chunk_start, chunk_end))
        if end >= len(normalized):
            break
        start = max(end - self.config.chunk_overlap, start + 1)
    return chunks

def chunk_section(self, content: str) -> list[str]:
    return [chunk for chunk, _, _ in self.chunk_text(content)]

def _select_chunk_title(
    self,
    *,
    book_name: str,
    chunk_start: int,
    chunk_end: int,
    ranges: list[tuple[int, int, str]],
) -> str:
    best_title = ""
    best_overlap = 0
    for section_start, section_end, title in ranges:
        overlap = min(chunk_end, section_end) - max(chunk_start, section_start)
        if overlap <= 0:
            continue
        if overlap > best_overlap:
            best_overlap = overlap
            best_title = title
    return self._normalize_chunk_label(best_title, book_name)

def schedule_book_chunks(
    self,
    *,
    book_path: Path,
    chapter_contains: list[str] | None = None,
    chapter_excludes: list[str] | None = None,
    max_chunks_per_book: int | None = None,
    skip_initial_chunks_per_book: int = 0,
    chunk_strategy: str | None = None,
) -> list[ChunkTask]:
    sections = self.split_book(book_path)
    filtered_sections = [
        section
        for section in sections
        if (not chapter_contains or _match_any_pattern(section["title"], chapter_contains))
        and not _match_any_pattern(section["title"], chapter_excludes)
    ]
    if not filtered_sections:
        return []

    strategy = (chunk_strategy or self.config.chunk_strategy).strip().lower()
    tasks: list[ChunkTask] = []
    sequence = 0

    if strategy == "chapter_first":
        for section in filtered_sections:
            chapter_name = self._normalize_chunk_label(section["title"], book_path.stem)
            for chunk_text, _, _ in self.chunk_text(section["content"]):
                sequence += 1
                if sequence <= max(0, skip_initial_chunks_per_book):
                    continue
                tasks.append(
                    ChunkTask(
                        sequence=sequence,
                        book_path=book_path,
                        book_name=book_path.stem,
                        chapter_name=chapter_name,
                        chunk_index=len(tasks) + 1,
                        text_chunk=chunk_text,
                    )
                )
                if max_chunks_per_book is not None and len(tasks) >= max_chunks_per_book:
                    return tasks
        return tasks

    combined_parts: list[str] = []
    ranges: list[tuple[int, int, str]] = []
    cursor = 0
    for section in filtered_sections:
        section_content = re.sub(r"\n{3,}", "\n\n", section["content"].strip())
        if not section_content:
            continue
        if combined_parts:
            combined_parts.append("\n\n")
            cursor += 2
        start = cursor
        combined_parts.append(section_content)
        cursor += len(section_content)
        ranges.append((start, cursor, section["title"]))

    combined_body = "".join(combined_parts)
    for chunk_text, chunk_start, chunk_end in self.chunk_text(combined_body):
        sequence += 1
        if sequence <= max(0, skip_initial_chunks_per_book):
            continue
        tasks.append(
            ChunkTask(
                sequence=sequence,
                book_path=book_path,
                book_name=book_path.stem,
                chapter_name=self._select_chunk_title(
                    book_name=book_path.stem,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                    ranges=ranges,
                ),
                chunk_index=len(tasks) + 1,
                text_chunk=chunk_text,
            )
        )
        if max_chunks_per_book is not None and len(tasks) >= max_chunks_per_book:
            break
    return tasks
