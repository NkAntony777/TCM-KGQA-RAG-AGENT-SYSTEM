"""Module-level constants and regex patterns for files-first retrieval.

This module is the single source of truth for the static data the other
files-first sub-modules rely on:

* TCM book-name hints used to short-circuit book detection.
* Stop words, strip phrases, and suffix sets used to clean query text.
* Compiled regex patterns used to recognize formula names and variants.
* Intent cue buckets consumed by the query-term extractor.
* A small environment-variable helper used to gate retrieval features.
"""

from __future__ import annotations

import os
import re

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


def _env_flag(name: str, *, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}