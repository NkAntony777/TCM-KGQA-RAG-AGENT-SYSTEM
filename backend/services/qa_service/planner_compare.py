from __future__ import annotations

import re


FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|剂|方)")
COMPARE_DIMENSION_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("composition", ("组成", "成分", "配方", "药物组成", "药味")),
    ("efficacy", ("功效", "作用", "配伍", "意义")),
    ("indication", ("主治", "适用", "证候", "适应证", "治什么")),
    ("path", ("病机", "辨证", "链路", "为什么", "异同", "区别", "比较", "共同点")),
    ("origin", ("出处", "原文", "出自", "古籍")),
)


def _comparison_dimensions(query: str) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized:
        return ["功效", "主治"]
    selected: list[str] = []
    for label, hints in COMPARE_DIMENSION_HINTS:
        if any(hint in normalized for hint in hints):
            if label == "composition":
                selected.append("组成")
            elif label == "efficacy":
                selected.append("功效")
            elif label == "indication":
                selected.append("主治")
            elif label == "path":
                selected.append("病机")
            elif label == "origin":
                selected.append("出处")
    if not selected:
        selected = ["组成", "功效", "主治"]
    return list(dict.fromkeys(selected))


def _extract_formula_mentions(query: str, *, compare_entities: list[str], entity_name: str) -> list[str]:
    ordered: list[str] = []
    seen = set()
    for item in [*compare_entities, entity_name, *FORMULA_PATTERN.findall(str(query or ""))]:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        if any(existing in name and len(name) - len(existing) <= 2 for existing in seen):
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _covered_compare_entities(*, compare_entities: list[str], factual_evidence: list[dict[str, object]]) -> list[str]:
    covered: list[str] = []
    for entity in compare_entities:
        for item in factual_evidence:
            haystack = " ".join(
                [
                    str(item.get("source", "")),
                    str(item.get("snippet", "")),
                    str(item.get("predicate", "")),
                    str(item.get("target", "")),
                    str(item.get("source_book", "")),
                ]
            )
            if entity and entity in haystack:
                covered.append(entity)
                break
    return list(dict.fromkeys(covered))


def _comparison_subqueries(*, query: str, compare_entities: list[str], factual_evidence: list[dict[str, object]]) -> list[dict[str, str]]:
    dimensions = _comparison_dimensions(query)
    covered = set(_covered_compare_entities(compare_entities=compare_entities, factual_evidence=factual_evidence))
    pending_entities = [entity for entity in compare_entities if entity not in covered] or list(compare_entities)
    if not pending_entities:
        pending_entities = list(compare_entities)
    subqueries: list[dict[str, str]] = []
    for entity in pending_entities:
        peer_terms = [peer for peer in compare_entities if peer != entity][:2]
        query_text = " ".join([entity, *dimensions, *peer_terms, "比较"]).strip()
        subqueries.append({"entity": entity, "query": query_text, "reason": f"补充 {entity} 的比较维度证据"})
    if len(compare_entities) >= 2:
        subqueries.append(
            {
                "entity": pending_entities[0],
                "query": f"{' '.join(compare_entities[:3])} {' '.join(dimensions[:3])} 区别 共同点 适用边界".strip(),
                "reason": "补充多对象比较的共同点与差异边界",
            }
        )
    deduped: list[dict[str, str]] = []
    seen = set()
    for item in subqueries:
        key = f"{item['entity']}::{item['query']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _reasoning_subqueries(*, query: str, compare_entities: list[str], entity_name: str) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized:
        return []
    queries: list[str] = []
    formula_mentions = _extract_formula_mentions(query, compare_entities=compare_entities, entity_name=entity_name)
    doctrine_matches = re.findall(r"《[^》]{1,20}》[^，。；；]*|[\u4e00-\u9fff]{4,20}则为[\u4e00-\u9fff]{1,12}", normalized)
    for item in doctrine_matches[:2]:
        text = str(item).strip()
        if text:
            queries.append(f"{text} 古籍原文 相关方剂")
    if formula_mentions:
        queries.append(f"{' '.join(formula_mentions[:4])} 病机 主治 比较")
    if any(marker in normalized for marker in ("比较", "异同", "区别")) and formula_mentions:
        queries.append(f"{' '.join(formula_mentions[:4])} 共同点 差异点 适用边界")
    deduped: list[str] = []
    seen = set()
    for item in queries:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped
