from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = Path(r"D:\毕业设计数据处理\TCM-Ancient-Books-master\TCM-Ancient-Books-master")
DEFAULT_OUTPUT = BACKEND_DIR / "services" / "retrieval_service" / "data" / "classic_books_corpus.json"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")

FILE_PREFIX_PATTERN = re.compile(r"^\d+\s*[-_－—]\s*")
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SECTION_PREFIX = "<篇名>"
CATALOG_MARKERS = {"<目录>"}
PARAGRAPH_BREAK_SUFFIXES = tuple("。！？；!?：:")


def _normalize_book_name(filename: str) -> str:
    stem = Path(filename).stem.strip()
    return FILE_PREFIX_PATTERN.sub("", stem).strip() or stem


def _clean_line(raw: object) -> str:
    text = CONTROL_PATTERN.sub("", str(raw or "").replace("\ufeff", "")).strip()
    return text


def _read_source_text(path: Path) -> str:
    for encoding in ("gb18030", "utf-8-sig", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="gb18030", errors="ignore")


def _split_sections(text: str, *, fallback_title: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = fallback_title
    current_lines: list[str] = []
    front_matter: list[str] = []
    seen_heading = False

    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line or line in CATALOG_MARKERS:
            continue
        if line.startswith(SECTION_PREFIX):
            title = _clean_line(line.removeprefix(SECTION_PREFIX)) or fallback_title
            if seen_heading and current_lines:
                sections.append((current_title, current_lines))
            elif not seen_heading and front_matter:
                sections.append((fallback_title, front_matter))
            seen_heading = True
            current_title = title
            current_lines = []
            continue
        if not seen_heading:
            front_matter.append(line)
            continue
        current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))
    elif front_matter:
        sections.append((fallback_title, front_matter))
    return sections


def _collapse_wrapped_lines(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current = ""
    for raw_line in lines:
        line = _clean_line(raw_line)
        if not line or line in CATALOG_MARKERS:
            continue
        if not current:
            current = line
            continue
        if current.endswith(PARAGRAPH_BREAK_SUFFIXES):
            paragraphs.append(current)
            current = line
            continue
        current += line
    if current:
        paragraphs.append(current)
    return [paragraph for paragraph in paragraphs if paragraph]


def _chunk_paragraphs(paragraphs: list[str], *, chunk_size: int, overlap_chars: int) -> list[str]:
    if not paragraphs:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        separator_len = 1 if current else 0
        if current and current_len + separator_len + paragraph_len > chunk_size:
            chunks.append("\n".join(current))
            overlap: list[str] = []
            overlap_len = 0
            for previous in reversed(current):
                overlap.insert(0, previous)
                overlap_len += len(previous)
                if overlap_len >= overlap_chars:
                    break
            current = overlap + [paragraph]
            current_len = sum(len(item) for item in current) + max(0, len(current) - 1)
            continue
        current.append(paragraph)
        current_len += separator_len + paragraph_len

    if current:
        chunks.append("\n".join(current))
    return chunks


def _build_doc(
    *,
    book_name: str,
    filename: str,
    section_title: str,
    section_index: int,
    chunk_index: int,
    chunk_text: str,
) -> dict[str, object]:
    chunk_id = f"classic::{book_name}::{section_index:04d}::{chunk_index:02d}"
    text = "\n".join(
        [
            f"古籍：{book_name}",
            f"篇名：{section_title or book_name}",
            chunk_text,
        ]
    )[:8000]
    return {
        "chunk_id": chunk_id,
        "chunk_idx": chunk_index,
        "parent_chunk_id": f"classic::{book_name}::{section_index:04d}",
        "root_chunk_id": f"classic::{book_name}::{section_index:04d}",
        "chunk_level": 3,
        "filename": filename,
        "file_type": "TXT",
        "file_path": f"classic://{book_name}/{section_index:04d}-{chunk_index:02d}",
        "page_number": section_index,
        "book_name": book_name,
        "chapter_title": section_title or book_name,
        "section_key": f"{book_name}::{section_index:04d}",
        "text": text,
    }


def _build_section_parent_doc(
    *,
    book_name: str,
    filename: str,
    section_title: str,
    section_index: int,
    section_text: str,
) -> dict[str, object]:
    parent_id = f"classic::{book_name}::{section_index:04d}"
    text = "\n".join(
        [
            f"古籍：{book_name}",
            f"篇名：{section_title or book_name}",
            section_text,
        ]
    )[:32000]
    return {
        "chunk_id": parent_id,
        "chunk_idx": 0,
        "parent_chunk_id": "",
        "root_chunk_id": parent_id,
        "chunk_level": 2,
        "filename": filename,
        "file_type": "TXT",
        "file_path": f"classic://{book_name}/{section_index:04d}",
        "page_number": section_index,
        "book_name": book_name,
        "chapter_title": section_title or book_name,
        "section_key": f"{book_name}::{section_index:04d}",
        "text": text,
    }


def build_classic_books_corpus(
    source_root: Path,
    *,
    chunk_size: int = 1800,
    overlap_chars: int = 220,
    max_books: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    docs: list[dict[str, object]] = []
    books_processed = 0
    sections_processed = 0

    for index, path in enumerate(sorted(source_root.glob("*.txt"))):
        if max_books is not None and index >= max_books:
            break
        books_processed += 1
        book_name = _normalize_book_name(path.name)
        sections = _split_sections(_read_source_text(path), fallback_title=book_name)
        for section_index, (title, lines) in enumerate(sections, start=1):
            paragraphs = _collapse_wrapped_lines(lines)
            if not paragraphs:
                continue
            sections_processed += 1
            docs.append(
                _build_section_parent_doc(
                    book_name=book_name,
                    filename=path.name,
                    section_title=title,
                    section_index=section_index,
                    section_text="\n".join(paragraphs),
                )
            )
            for chunk_index, chunk_text in enumerate(
                _chunk_paragraphs(paragraphs, chunk_size=chunk_size, overlap_chars=overlap_chars),
                start=1,
            ):
                docs.append(
                    _build_doc(
                        book_name=book_name,
                        filename=path.name,
                        section_title=title,
                        section_index=section_index,
                        chunk_index=chunk_index,
                        chunk_text=chunk_text,
                    )
                )

    manifest = {
        "source_root": str(source_root),
        "books_processed": books_processed,
        "sections_processed": sections_processed,
        "total_docs": len(docs),
        "chunk_size": chunk_size,
        "overlap_chars": overlap_chars,
    }
    return docs, manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert classic TCM txt books into retrieval corpus JSON.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--overlap-chars", type=int, default=220)
    parser.add_argument("--max-books", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    docs, manifest = build_classic_books_corpus(
        args.source_root,
        chunk_size=max(300, int(args.chunk_size)),
        overlap_chars=max(0, int(args.overlap_chars)),
        max_books=args.max_books,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    args.manifest_output.write_text(
        json.dumps(
            {
                **manifest,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(args.manifest_output.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
