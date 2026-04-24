from __future__ import annotations

from pathlib import Path
from typing import Any


def list_books_payload(
    pipeline: Any,
    *,
    processed_stems: set[str],
    recommend_limit: int = 12,
) -> dict[str, Any]:
    books = pipeline.discover_books()
    recommended = {str(path) for path in pipeline.recommend_books(limit=recommend_limit)}
    result = []
    for index, book_path in enumerate(books, start=1):
        size_kb = round(book_path.stat().st_size / 1024, 1)
        result.append(
            {
                "index": index,
                "name": book_path.stem,
                "path": str(book_path),
                "size_kb": size_kb,
                "recommended": str(book_path) in recommended,
                "processed": book_path.stem in processed_stems,
            }
        )
    return {"books": result, "total": len(result)}


def chapters_payload(pipeline: Any, *, book_name: str, limit: int = 50) -> dict[str, Any]:
    books: list[Path] = pipeline.discover_books()
    matched = [book_path for book_path in books if book_name in book_path.stem]
    if not matched:
        raise LookupError("book_not_found")
    sections = pipeline.split_book(matched[0])[:limit]
    return {
        "book": matched[0].stem,
        "total_sections": len(sections),
        "sections": [{"title": section["title"], "chars": len(section["content"])} for section in sections],
    }
