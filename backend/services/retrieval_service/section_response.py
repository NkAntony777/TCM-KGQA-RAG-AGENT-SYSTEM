from __future__ import annotations

from typing import Any, Callable, Protocol


class ParentStore(Protocol):
    def get_documents_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        ...


ExtractBookNameFn = Callable[..., str]
ExtractChapterTitleFn = Callable[..., str]
StripHeadersFn = Callable[[str], str]
MergeBodiesFn = Callable[[list[str]], str]
BuildMetadataFn = Callable[..., dict[str, Any]]


def normalize_chunk(
    item: dict[str, Any],
    *,
    extract_book_name: ExtractBookNameFn,
    extract_chapter_title: ExtractChapterTitleFn,
) -> dict[str, Any]:
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
    parent_store: ParentStore,
    normalize_chunk_fn: Callable[[dict[str, Any]], dict[str, Any]],
    strip_classic_headers: StripHeadersFn,
    merge_section_bodies: MergeBodiesFn,
    build_section_metadata: BuildMetadataFn,
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

    normalized_items = [normalize_chunk_fn(item) for item in raw_items if isinstance(item, dict)]
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
    metadata = build_section_metadata(
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
