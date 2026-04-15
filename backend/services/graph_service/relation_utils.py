from __future__ import annotations


def _legacy_utf8_gbk_alias(text: str) -> str:
    """Recover one common mojibake form without leaving corrupted literals in source."""
    try:
        return text.encode("utf-8").decode("gbk")
    except UnicodeDecodeError:
        return text


RELATION_ALIASES = {
    _legacy_utf8_gbk_alias("常见症状"): "常见症状",
    _legacy_utf8_gbk_alias("表现症状"): "表现症状",
    _legacy_utf8_gbk_alias("相关症状"): "相关症状",
    _legacy_utf8_gbk_alias("推荐方剂"): "推荐方剂",
}


PREDICATE_BASE_PRIORITY: dict[str, float] = {
    "治疗证候": 1.0,
    "功效": 0.98,
    "使用药材": 0.96,
    "治疗症状": 0.93,
    "治法": 0.9,
    "治疗疾病": 0.9,
    "推荐方剂": 0.88,
    "归经": 0.85,
    "药性": 0.82,
    "配伍禁忌": 0.8,
    "食忌": 0.78,
    "常见症状": 0.76,
    "别名": 0.72,
    "属于范畴": 0.65,
}


def normalize_relation_name(name: str) -> str:
    normalized = (name or "").strip()
    return RELATION_ALIASES.get(normalized, normalized)
