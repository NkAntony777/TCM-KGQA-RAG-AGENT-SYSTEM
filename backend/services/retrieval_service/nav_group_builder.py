from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable

SECTION_KEY_PATTERN = re.compile(r"^(?P<book>.+?)::(?P<section>\d{4})$")
TITLE_FRONT_MATTER_MARKERS = ("序", "凡例", "跋", "目录", "原序", "总序", "自序")
TITLE_FORMULA_SUFFIXES = ("汤", "散", "丸", "饮", "膏", "丹", "方")
TITLE_CATEGORY_MARKERS = ("门", "篇", "论", "附论", "总论", "通治方", "证", "病")


@dataclass(frozen=True)
class SectionNode:
    section_key: str
    section_index: int
    book_name: str
    chapter_title: str
    page_number: int
    summary: str
    topic_tags: tuple[str, ...]
    entity_tags: tuple[str, ...]
    representative_passages: tuple[str, ...]
    leaf_count: int


def _read_corpus(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("classic_corpus_must_be_list")
    return [item for item in payload if isinstance(item, dict)]


def _load_summary_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT section_key, section_summary, topic_tags, entity_tags, representative_passages
                FROM section_summaries
                """
            ).fetchall()
    except sqlite3.Error:
        return {}
    payload: dict[str, dict[str, Any]] = {}
    for section_key, section_summary, topic_tags, entity_tags, representative_passages in rows:
        try:
            parsed_topic_tags = json.loads(str(topic_tags or "[]"))
        except Exception:
            parsed_topic_tags = []
        try:
            parsed_entity_tags = json.loads(str(entity_tags or "[]"))
        except Exception:
            parsed_entity_tags = []
        try:
            parsed_passages = json.loads(str(representative_passages or "[]"))
        except Exception:
            parsed_passages = []
        payload[str(section_key or "").strip()] = {
            "section_summary": str(section_summary or ""),
            "topic_tags": parsed_topic_tags if isinstance(parsed_topic_tags, list) else [],
            "entity_tags": parsed_entity_tags if isinstance(parsed_entity_tags, list) else [],
            "representative_passages": parsed_passages if isinstance(parsed_passages, list) else [],
        }
    return payload


def _section_index(section_key: str) -> int:
    match = SECTION_KEY_PATTERN.match(str(section_key or "").strip())
    if not match:
        return 0
    return int(match.group("section"))


def _dedupe_texts(values: list[str], *, limit: int) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
        if len(results) >= limit:
            break
    return results


def _title_kind(title: str) -> str:
    normalized = str(title or "").strip()
    if not normalized:
        return "unknown"
    if any(marker in normalized for marker in TITLE_FRONT_MATTER_MARKERS):
        return "front_matter"
    if normalized.endswith(TITLE_FORMULA_SUFFIXES):
        return "formula"
    if any(marker in normalized for marker in TITLE_CATEGORY_MARKERS):
        return "category"
    if len(normalized) <= 4:
        return "entry"
    return "generic"


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _node_entity_similarity(left: SectionNode, right: SectionNode) -> float:
    return _jaccard(set(left.entity_tags), set(right.entity_tags))


def _node_topic_similarity(left: SectionNode, right: SectionNode) -> float:
    return _jaccard(set(left.topic_tags), set(right.topic_tags))


def _book_similarity_floor(sections: list[SectionNode]) -> float:
    if len(sections) < 2:
        return 0.18
    entity_similarities = [
        _node_entity_similarity(sections[idx], sections[idx + 1])
        for idx in range(len(sections) - 1)
    ]
    non_zero = [value for value in entity_similarities if value > 0.0]
    if not non_zero:
        return 0.18
    # Use the book-internal median as a robust adaptive split floor.
    return round(min(0.32, max(0.12, float(median(non_zero)))), 3)


def _infer_question_types(*, title: str, topic_tags: list[str], entity_tags: list[str]) -> list[str]:
    joined = " ".join([title, *topic_tags, *entity_tags])
    kinds: list[str] = []
    if any(marker in joined for marker in ("出处", "原文", "条文", "方后注")):
        kinds.append("source_quote")
    if any(marker in joined for marker in ("功效", "主治", "治法", "方义", "归经", "药性")):
        kinds.append("property")
    if any(marker in joined for marker in ("组成", "配伍", "药味", "加减")):
        kinds.append("composition")
    if any(marker in joined for marker in ("病机", "辨证", "证", "病")):
        kinds.append("theory_explanation")
    if any(str(entity).endswith(TITLE_FORMULA_SUFFIXES) for entity in entity_tags):
        kinds.append("formula_lookup")
    if not kinds:
        kinds.append("generic_navigation")
    return _dedupe_texts(kinds, limit=4)


def _book_archetype(*, chapter_count: int, avg_leafs_per_section: float, micro_ratio: float) -> str:
    if chapter_count >= 800 and micro_ratio >= 0.93:
        return "micro_entry_book"
    if chapter_count >= 600 and avg_leafs_per_section >= 2.0:
        return "mixed_compendium"
    if chapter_count >= 300 and micro_ratio >= 0.88:
        return "fine_grained_book"
    if chapter_count <= 120 and avg_leafs_per_section >= 1.8:
        return "coarse_book"
    return "default"


def _group_params(archetype: str) -> tuple[int, int, int]:
    if archetype == "micro_entry_book":
        return (8, 16, 24)
    if archetype == "mixed_compendium":
        return (6, 12, 18)
    if archetype == "fine_grained_book":
        return (6, 12, 20)
    if archetype == "coarse_book":
        return (1, 1, 1)
    return (4, 8, 14)


def _section_nodes_from_corpus(*, corpus_rows: list[dict[str, Any]], summary_cache_payload: dict[str, dict[str, Any]]) -> dict[str, list[SectionNode]]:
    leaf_counts: Counter[str] = Counter()
    section_meta: dict[str, dict[str, Any]] = {}
    for row in corpus_rows:
        if int(row.get("chunk_level", 0) or 0) != 3:
            continue
        section_key = str(row.get("section_key", "") or "").strip()
        if not section_key:
            continue
        leaf_counts[section_key] += 1
        if section_key not in section_meta:
            section_meta[section_key] = {
                "book_name": str(row.get("book_name", "") or "").strip(),
                "chapter_title": str(row.get("chapter_title", "") or "").strip(),
                "page_number": int(row.get("page_number", 0) or 0),
            }

    grouped: dict[str, list[SectionNode]] = defaultdict(list)
    for section_key, meta in section_meta.items():
        cached = summary_cache_payload.get(section_key, {})
        book_name = str(meta.get("book_name", "") or "").strip()
        chapter_title = str(meta.get("chapter_title", "") or "").strip() or book_name
        grouped[book_name].append(
            SectionNode(
                section_key=section_key,
                section_index=_section_index(section_key),
                book_name=book_name,
                chapter_title=chapter_title,
                page_number=int(meta.get("page_number", 0) or 0),
                summary=str(cached.get("section_summary", "") or "").strip(),
                topic_tags=tuple(_dedupe_texts([str(item) for item in cached.get("topic_tags", [])], limit=12)),
                entity_tags=tuple(_dedupe_texts([str(item) for item in cached.get("entity_tags", [])], limit=12)),
                representative_passages=tuple(_dedupe_texts([str(item) for item in cached.get("representative_passages", [])], limit=3)),
                leaf_count=int(leaf_counts.get(section_key, 0)),
            )
        )

    for book_name in grouped:
        grouped[book_name].sort(key=lambda item: (item.section_index, item.page_number, item.chapter_title))
    return grouped


def _should_split_group(
    *,
    current: list[SectionNode],
    nxt: SectionNode,
    min_size: int,
    target_size: int,
    max_size: int,
    similarity_floor: float,
) -> bool:
    if not current:
        return False
    if len(current) >= max_size:
        return True
    if len(current) < min_size:
        return False
    current_kind = _title_kind(current[-1].chapter_title)
    next_kind = _title_kind(nxt.chapter_title)
    current_topics = {tag for item in current for tag in item.topic_tags}
    current_entities = {tag for item in current for tag in item.entity_tags}
    next_topics = set(nxt.topic_tags)
    next_entities = set(nxt.entity_tags)
    similarity = max(_jaccard(current_topics, next_topics), _jaccard(current_entities, next_entities))
    if current_kind == "front_matter" and next_kind != "front_matter":
        return True
    if current_kind != next_kind and len(current) >= target_size:
        return True
    if similarity < similarity_floor and len(current) >= target_size:
        return True
    return False


def _aggregate_group(book_name: str, group_id: int, archetype: str, items: list[SectionNode]) -> dict[str, Any]:
    topic_counter = Counter(tag for item in items for tag in item.topic_tags)
    entity_counter = Counter(tag for item in items for tag in item.entity_tags)
    title_counter = Counter(item.chapter_title for item in items)
    representative_passages = _dedupe_texts(
        [part for item in items for part in item.representative_passages],
        limit=4,
    )
    dominant_topics = [tag for tag, _ in topic_counter.most_common(8)]
    dominant_entities = [tag for tag, _ in entity_counter.most_common(8)]
    dominant_titles = [tag for tag, _ in title_counter.most_common(3)]
    first = items[0]
    last = items[-1]
    group_title = " / ".join(dominant_titles) if dominant_titles else first.chapter_title
    summary_parts = []
    if dominant_topics:
        summary_parts.append("主题：" + "、".join(dominant_topics[:4]))
    if dominant_entities:
        summary_parts.append("核心实体：" + "、".join(dominant_entities[:4]))
    if representative_passages:
        summary_parts.append("代表片段：" + representative_passages[0][:80])
    group_summary = "；".join(summary_parts)[:240]
    return {
        "group_key": f"{book_name}::nav::{group_id:04d}",
        "book_name": book_name,
        "archetype": archetype,
        "group_title": group_title,
        "group_summary": group_summary,
        "topic_tags": dominant_topics,
        "entity_tags": dominant_entities,
        "representative_passages": representative_passages,
        "question_types_supported": _infer_question_types(
            title=group_title,
            topic_tags=dominant_topics,
            entity_tags=dominant_entities,
        ),
        "section_count": len(items),
        "leaf_count": sum(item.leaf_count for item in items),
        "start_section_key": first.section_key,
        "end_section_key": last.section_key,
        "section_index_range": [first.section_index, last.section_index],
        "page_range": [first.page_number, last.page_number],
        "child_section_keys": [item.section_key for item in items],
        "child_titles": _dedupe_texts([item.chapter_title for item in items], limit=12),
        "search_text": " ".join(
            [
                book_name,
                group_title,
                group_summary,
                " ".join(dominant_topics),
                " ".join(dominant_entities),
                " ".join(representative_passages),
            ]
        ).strip(),
    }


def build_nav_groups(
    *,
    book_sections: dict[str, list[SectionNode]],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    nav_groups: list[dict[str, Any]] = []
    book_outlines: list[dict[str, Any]] = []
    book_stats: list[dict[str, Any]] = []

    total_books = len(book_sections)
    for index, (book_name, sections) in enumerate(book_sections.items(), start=1):
        if progress_callback is not None:
            progress_callback(index, total_books, book_name)
        chapter_count = len(sections)
        avg_leafs = sum(item.leaf_count for item in sections) / max(1, chapter_count)
        micro_ratio = sum(1 for item in sections if item.leaf_count <= 2) / max(1, chapter_count)
        archetype = _book_archetype(
            chapter_count=chapter_count,
            avg_leafs_per_section=avg_leafs,
            micro_ratio=micro_ratio,
        )
        min_size, target_size, max_size = _group_params(archetype)
        similarity_floor = _book_similarity_floor(sections)
        groups_for_book: list[dict[str, Any]] = []

        if archetype == "coarse_book":
            for idx, section in enumerate(sections, start=1):
                groups_for_book.append(_aggregate_group(book_name, idx, archetype, [section]))
        else:
            current: list[SectionNode] = []
            group_id = 1
            for node in sections:
                if _should_split_group(
                    current=current,
                    nxt=node,
                    min_size=min_size,
                    target_size=target_size,
                    max_size=max_size,
                    similarity_floor=similarity_floor,
                ):
                    groups_for_book.append(_aggregate_group(book_name, group_id, archetype, current))
                    group_id += 1
                    current = []
                current.append(node)
            if current:
                groups_for_book.append(_aggregate_group(book_name, group_id, archetype, current))

        nav_groups.extend(groups_for_book)

        topic_counter = Counter(tag for item in groups_for_book for tag in item["topic_tags"])
        entity_counter = Counter(tag for item in groups_for_book for tag in item["entity_tags"])
        dominant_topics = [tag for tag, _ in topic_counter.most_common(10)]
        dominant_entities = [tag for tag, _ in entity_counter.most_common(10)]
        outline_summary = "；".join(
            part
            for part in [
                f"全书主要覆盖{'、'.join(dominant_topics[:5])}" if dominant_topics else "",
                f"高频实体包括{'、'.join(dominant_entities[:5])}" if dominant_entities else "",
                f"共形成{len(groups_for_book)}个导航组" if groups_for_book else "",
            ]
            if part
        )[:280]
        book_outlines.append(
            {
                "book_name": book_name,
                "archetype": archetype,
                "book_summary": outline_summary,
                "major_topics": dominant_topics,
                "major_entities": dominant_entities,
                "group_count": len(groups_for_book),
                "section_count": chapter_count,
                "leaf_count": sum(item.leaf_count for item in sections),
                "group_keys": [item["group_key"] for item in groups_for_book],
                "query_types_supported": _dedupe_texts(
                    [kind for item in groups_for_book for kind in item["question_types_supported"]],
                    limit=8,
                ),
            }
        )
        book_stats.append(
            {
                "book_name": book_name,
                "archetype": archetype,
                "section_count": chapter_count,
                "leaf_count": sum(item.leaf_count for item in sections),
                "avg_leafs_per_section": round(avg_leafs, 3),
                "micro_ratio": round(micro_ratio, 3),
                "similarity_floor": similarity_floor,
                "nav_group_count": len(groups_for_book),
                "avg_sections_per_group": round(chapter_count / max(1, len(groups_for_book)), 3),
            }
        )

    manifest = {
        "books": len(book_sections),
        "nav_groups": len(nav_groups),
        "book_outlines": len(book_outlines),
        "archetype_counts": dict(Counter(item["archetype"] for item in book_stats)),
    }
    return {
        "manifest": manifest,
        "book_stats": sorted(book_stats, key=lambda item: item["section_count"], reverse=True),
        "nav_groups": nav_groups,
        "book_outlines": book_outlines,
    }


def build_nav_group_payload_from_rows(
    *,
    corpus_rows: list[dict[str, Any]],
    summary_cache_path: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    summary_cache_payload = _load_summary_cache(summary_cache_path)
    book_sections = _section_nodes_from_corpus(corpus_rows=corpus_rows, summary_cache_payload=summary_cache_payload)
    return build_nav_groups(book_sections=book_sections, progress_callback=progress_callback)


def write_nav_group_artifacts(*, output_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    nav_groups_path = output_dir / "classic_nav_groups.json"
    outlines_path = output_dir / "classic_book_outlines.json"
    stats_path = output_dir / "classic_nav_group_stats.json"
    manifest_path = output_dir / "classic_nav_group_manifest.json"

    nav_groups_path.write_text(json.dumps(payload["nav_groups"], ensure_ascii=False, indent=2), encoding="utf-8")
    outlines_path.write_text(json.dumps(payload["book_outlines"], ensure_ascii=False, indent=2), encoding="utf-8")
    stats_path.write_text(json.dumps(payload["book_stats"], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(payload["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "nav_groups_path": str(nav_groups_path),
        "book_outlines_path": str(outlines_path),
        "stats_path": str(stats_path),
        "manifest_path": str(manifest_path),
    }


def build_nav_group_artifacts(*, corpus_path: Path, summary_cache_path: Path, output_dir: Path) -> dict[str, Any]:
    corpus_rows = _read_corpus(corpus_path)
    summary_cache_payload = _load_summary_cache(summary_cache_path)
    book_sections = _section_nodes_from_corpus(corpus_rows=corpus_rows, summary_cache_payload=summary_cache_payload)
    payload = build_nav_groups(book_sections=book_sections)
    paths = write_nav_group_artifacts(output_dir=output_dir, payload=payload)
    return {
        **paths,
        **payload["manifest"],
    }
