from __future__ import annotations

import re
from typing import Any, Callable


def clean_text(value: Any, *, limit: int = 300) -> str:
    return str(value or "").strip()[:limit]


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def extract_data(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
    return {}


def normalize_book_label(text: str) -> str:
    label = str(text or "").strip()
    return re.sub(r"^\d+\s*[-_－—]\s*", "", label)


def normalize_source_chapter_label(*, source_book: str, source_chapter: str) -> str:
    book_raw = str(source_book or "").strip()
    chapter_raw = str(source_chapter or "").strip()
    if not chapter_raw:
        return ""
    normalized_book = normalize_book_label(book_raw)
    if chapter_raw in {book_raw, normalized_book}:
        return ""
    for prefix in (book_raw, normalized_book):
        if not prefix:
            continue
        for separator in ("_", "-", "－", "—"):
            marker = f"{prefix}{separator}"
            if not chapter_raw.startswith(marker):
                continue
            tail = chapter_raw[len(marker):].strip()
            if not tail or tail in {"正文", "全文"}:
                return ""
            return tail
    if chapter_raw.endswith("_正文") or chapter_raw.endswith("-正文"):
        return ""
    return chapter_raw


def _normalized_source_book(
    value: Any,
    *,
    normalizer: Callable[[str], str] | None,
) -> str:
    source_book = str(value or "").strip()
    if not source_book:
        return ""
    return normalizer(source_book) if normalizer is not None else source_book


def _is_readable_chapter_label(*, source_book: str, chapter_title: str) -> bool:
    normalized_book = normalize_book_label(source_book)
    normalized_chapter = normalize_source_chapter_label(source_book=source_book, source_chapter=chapter_title)
    if not normalized_chapter:
        return False
    if normalized_chapter in {source_book, normalized_book}:
        return False
    if normalized_chapter.endswith("_正文") or normalized_chapter.endswith("-正文"):
        return False
    if normalized_chapter.startswith(f"{source_book}_") or normalized_chapter.startswith(f"{normalized_book}_"):
        return False
    if re.match(r"^\d+\s*[-_－—]", normalized_chapter):
        return False
    return True


def normalize_path_predicate(value: Any) -> str:
    return str(value or "").strip().replace("(逆向)", "").replace("（逆向）", "").strip()


def _logical_source_paths(*, source_book: str, source_chapter: str) -> tuple[str | None, str | None]:
    normalized_book = normalize_book_label(source_book)
    normalized_chapter = normalize_source_chapter_label(source_book=source_book, source_chapter=source_chapter)
    scope_path = f"book://{normalized_book}/*" if normalized_book else None
    if normalized_book and normalized_chapter:
        return f"chapter://{normalized_book}/{normalized_chapter}", scope_path
    return scope_path, scope_path


def graph_relation_items(payload: dict[str, Any], *, snippet_limit: int = 300) -> list[dict[str, Any]]:
    data = extract_data(payload)
    relations = data.get("relations", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for relation in relations if isinstance(relations, list) else []:
        if not isinstance(relation, dict):
            continue
        source_book = str(relation.get("source_book", "")).strip()
        source_chapter = normalize_source_chapter_label(
            source_book=source_book,
            source_chapter=str(relation.get("source_chapter", "")).strip(),
        )
        evidence_path, source_scope_path = _logical_source_paths(
            source_book=source_book,
            source_chapter=source_chapter,
        )
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": f"{source_book}/{source_chapter}".strip("/") or "graph",
                "snippet": clean_text(
                    relation.get("source_text") or f"{relation.get('predicate', '')}: {relation.get('target', '')}",
                    limit=snippet_limit,
                ),
                "score": safe_float(relation.get("score", relation.get("confidence", relation.get("max_confidence")))),
                "predicate": str(relation.get("predicate", "")).strip(),
                "target": str(relation.get("target", "")).strip(),
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
                "evidence_path": evidence_path,
                "source_scope_path": source_scope_path,
            }
        )
    return items


def graph_path_items(
    payload: dict[str, Any],
    *,
    expand_edges: bool = False,
    snippet_limit: int = 300,
) -> list[dict[str, Any]]:
    data = extract_data(payload)
    paths = data.get("paths", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for path in paths if isinstance(paths, list) else []:
        if not isinstance(path, dict):
            continue
        nodes = [str(node).strip() for node in path.get("nodes", []) if str(node).strip()] if isinstance(path.get("nodes"), list) else []
        edges = [normalize_path_predicate(edge) for edge in path.get("edges", [])] if isinstance(path.get("edges"), list) else []
        sources = path.get("sources", []) if isinstance(path.get("sources"), list) else []
        first_source = sources[0] if sources and isinstance(sources[0], dict) else {}
        source_book = str(first_source.get("source_book", "")).strip()
        source_chapter = normalize_source_chapter_label(
            source_book=source_book,
            source_chapter=str(first_source.get("source_chapter", "")).strip(),
        )
        source = f"{source_book}/{source_chapter}".strip("/") or "graph/path"
        evidence_path, source_scope_path = _logical_source_paths(
            source_book=source_book,
            source_chapter=source_chapter,
        )
        path_score = safe_float(path.get("score")) or 0.0

        if expand_edges and len(nodes) >= 2 and edges:
            for index, predicate in enumerate(edges):
                if index + 1 >= len(nodes):
                    break
                items.append(
                    {
                        "evidence_type": "factual_grounding",
                        "source_type": "graph_path",
                        "source": source,
                        "snippet": clean_text(f"{nodes[index]} --{predicate}--> {nodes[index + 1]}", limit=snippet_limit),
                        "score": path_score,
                        "predicate": predicate,
                        "target": nodes[index + 1],
                        "source_book": source_book or None,
                        "source_chapter": source_chapter or None,
                        "evidence_path": evidence_path,
                        "source_scope_path": source_scope_path,
                        "path_nodes": nodes,
                        "path_edges": edges,
                        "path_sources": sources,
                    }
                )
            continue

        snippet = " -> ".join(nodes)
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph_path",
                "source": source,
                "snippet": clean_text(snippet, limit=snippet_limit),
                "score": path_score,
                "predicate": "辨证链" if nodes else "",
                "target": nodes[-1] if nodes else "",
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
                "evidence_path": evidence_path,
                "source_scope_path": source_scope_path,
                "path_nodes": nodes,
                "path_edges": edges,
                "path_sources": sources,
            }
        )
    return items


def syndrome_items(
    payload: dict[str, Any],
    *,
    formula_limit: int = 6,
    snippet_limit: int = 300,
) -> list[dict[str, Any]]:
    data = extract_data(payload)
    syndromes = data.get("syndromes", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for syndrome in syndromes if isinstance(syndromes, list) else []:
        if not isinstance(syndrome, dict):
            continue
        formulas = syndrome.get("recommended_formulas", [])
        source_book = str(syndrome.get("source_book", "")).strip()
        source_chapter = normalize_source_chapter_label(
            source_book=source_book,
            source_chapter=str(syndrome.get("source_chapter", "")).strip(),
        )
        evidence_path, source_scope_path = _logical_source_paths(
            source_book=source_book,
            source_chapter=source_chapter,
        )
        formula_text = "、".join(str(item) for item in formulas[:formula_limit]) if isinstance(formulas, list) else ""
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": "graph/syndrome_chain",
                "snippet": clean_text(
                    syndrome.get("source_text") or f"{syndrome.get('name', '')} -> {formula_text}".strip(" ->"),
                    limit=snippet_limit,
                ),
                "score": safe_float(syndrome.get("score", syndrome.get("confidence"))) or 0.0,
                "predicate": "辨证链",
                "target": str(syndrome.get("name", "")).strip(),
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
                "evidence_path": evidence_path,
                "source_scope_path": source_scope_path,
            }
        )
    return items


def retrieval_items(
    payload: dict[str, Any],
    *,
    snippet_limit: int = 300,
    match_snippet_limit: int = 220,
    source_book_normalizer: Callable[[str], str] | None = normalize_book_label,
    fallback_page_to_chapter: bool = True,
) -> list[dict[str, Any]]:
    data = extract_data(payload)
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for chunk in chunks if isinstance(chunks, list) else []:
        if not isinstance(chunk, dict):
            continue
        source_file = str(chunk.get("source_file", chunk.get("filename", "unknown"))).strip()
        source_page = chunk.get("source_page", chunk.get("page_number"))
        source_book_raw = source_file.rsplit(".", 1)[0] if source_file else ""
        source_book = source_book_normalizer(source_book_raw) if source_book_normalizer is not None else source_book_raw
        source_chapter = normalize_source_chapter_label(
            source_book=source_book,
            source_chapter=str(chunk.get("chapter_title", "")).strip(),
        )
        if not source_chapter and fallback_page_to_chapter and source_page not in (None, ""):
            source_chapter = f"第{source_page}页"
        source = f"{source_file}#{source_page}" if source_page not in (None, "") else source_file
        evidence_path, source_scope_path = _logical_source_paths(
            source_book=source_book,
            source_chapter=source_chapter,
        )
        items.append(
            {
                "evidence_type": "factual_grounding",
                "source_type": "doc",
                "source": source,
                "snippet": clean_text(chunk.get("text"), limit=snippet_limit),
                "match_snippet": clean_text(chunk.get("match_snippet"), limit=match_snippet_limit),
                "score": safe_float(chunk.get("rerank_score", chunk.get("score"))),
                "source_file": source_file,
                "source_page": source_page,
                "file_path": str(chunk.get("file_path", "")).strip() or None,
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
                "evidence_path": evidence_path,
                "source_scope_path": source_scope_path,
            }
        )
    return items


def section_items(payload: dict[str, Any], *, snippet_limit: int = 600) -> list[dict[str, Any]]:
    data = extract_data(payload)
    section = data.get("section", {}) if isinstance(data, dict) else {}
    if not isinstance(section, dict) or not section:
        return []
    book_name = str(section.get("book_name", "")).strip()
    chapter_title = normalize_source_chapter_label(
        source_book=book_name,
        source_chapter=str(section.get("chapter_title", "")).strip(),
    )
    evidence_path, source_scope_path = _logical_source_paths(
        source_book=book_name,
        source_chapter=chapter_title,
    )
    return [
        {
            "evidence_type": "factual_grounding",
            "source_type": "chapter",
            "source": f"{book_name}/{chapter_title}".strip("/") or "chapter",
            "snippet": clean_text(section.get("text"), limit=snippet_limit),
            "score": 1.0,
            "source_file": str(section.get("source_file", "")).strip() or None,
            "source_book": book_name or None,
            "source_chapter": chapter_title or None,
            "evidence_path": evidence_path,
            "source_scope_path": source_scope_path,
        }
    ]


def book_paths_from_route_payload(
    payload: dict[str, Any],
    *,
    source_book_normalizer: Callable[[str], str] | None = normalize_book_label,
) -> list[str]:
    paths: list[str] = []
    graph_result = payload.get("graph_result", {}) if isinstance(payload, dict) else {}
    retrieval_result = payload.get("retrieval_result", {}) if isinstance(payload, dict) else {}

    for item in graph_relation_items(graph_result):
        source_book = _normalized_source_book(item.get("source_book", ""), normalizer=source_book_normalizer)
        if source_book:
            paths.append(f"book://{source_book}/*")

    for item in retrieval_items(retrieval_result, source_book_normalizer=source_book_normalizer):
        source_book = str(item.get("source_book", "")).strip()
        if source_book:
            paths.append(f"book://{source_book}/*")

    return list(dict.fromkeys(path for path in paths if path))


def chapter_paths_from_route_payload(
    payload: dict[str, Any],
    *,
    source_book_normalizer: Callable[[str], str] | None = normalize_book_label,
) -> list[str]:
    paths: list[str] = []
    graph_result = payload.get("graph_result", {}) if isinstance(payload, dict) else {}
    retrieval_result = payload.get("retrieval_result", {}) if isinstance(payload, dict) else {}

    for item in graph_relation_items(graph_result):
        source_book_raw = str(item.get("source_book", "")).strip()
        source_book = _normalized_source_book(source_book_raw, normalizer=source_book_normalizer)
        source_chapter = str(item.get("source_chapter", "")).strip()
        if source_book and source_chapter and _is_readable_chapter_label(source_book=source_book_raw, chapter_title=source_chapter):
            paths.append(f"chapter://{source_book}/{source_chapter}")

    for item in retrieval_items(
        retrieval_result,
        source_book_normalizer=source_book_normalizer,
        fallback_page_to_chapter=False,
    ):
        source_book = str(item.get("source_book", "")).strip()
        source_chapter = str(item.get("source_chapter", "")).strip()
        if source_book and source_chapter:
            paths.append(f"chapter://{source_book}/{source_chapter}")

    return list(dict.fromkeys(path for path in paths if path))
