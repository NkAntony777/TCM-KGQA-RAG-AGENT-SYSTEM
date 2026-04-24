from __future__ import annotations

import os
import re
from typing import Any

from router.tcm_intent_classifier import analyze_tcm_query
from services.qa_service.alias_service import get_runtime_alias_service
from services.retrieval_service.files_first_methods import _query_flags

def _maybe_refine_files_first_query(
    self,
    *,
    query: str,
    search_mode: str,
    result: dict[str, Any],
    top_k: int,
) -> str:
    if os.getenv("FILES_FIRST_QUERY_REWRITE_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return ""
    if (search_mode or "").strip().lower() != "files_first":
        return ""
    chunks = result.get("chunks", []) if isinstance(result.get("chunks"), list) else []
    if chunks and len(chunks) >= min(max(2, top_k // 2), top_k):
        return ""
    flags = _query_flags(query)
    warnings = {str(item).strip() for item in result.get("warnings", []) if str(item).strip()} if isinstance(result.get("warnings"), list) else set()
    top_score = float(chunks[0].get("score", 0.0) or 0.0) if chunks else 0.0
    if chunks and flags.get("source_query") and len(chunks) == 1 and top_score >= 5.0:
        top_title = str(chunks[0].get("chapter_title", "") or "")
        top_book = str(chunks[0].get("book_name", "") or "")
        for focus in self._primary_refine_entities(query):
            if focus and (focus in top_title or focus in top_book):
                return ""
    low_confidence = (
        not chunks
        or "lexical_sanity_filtered_all" in warnings
        or "files_first_sparse_query_empty" in warnings
    )
    if not low_confidence:
        return ""
    return self._refine_files_first_query(query)

def _refine_files_first_query(self, query: str) -> str:
    base_query = str(query or "").strip()
    if not base_query:
        return ""
    flags = _query_flags(base_query)
    fast_refined = self._fast_refine_files_first_query(base_query)
    if (
        fast_refined
        and fast_refined != base_query
        and (flags.get("property_query") or flags.get("composition_query") or flags.get("comparison_query"))
        and not flags.get("source_query")
    ):
        return fast_refined
    alias_service = get_runtime_alias_service()
    heuristic = alias_service.expand_query_with_aliases(
        base_query,
        max_aliases_per_entity=3,
        max_entities=2,
    )
    should_remote_rewrite = self.rewrite_client.is_ready()
    if should_remote_rewrite:
        try:
            prompt = (
                "请把下面的中医问题改写成一条更适合古籍全文检索与图谱检索的短查询。"
                "要求：保留核心实体、证候、书名线索；补全常见古今异名或近义表述；不超过40字；只输出改写结果。\n"
                f"问题：{base_query}"
            )
            rewritten = str(self.rewrite_client.chat(prompt, self.settings.rewrite_model) or "").strip()
            rewritten = re.sub(r"\s+", " ", rewritten)
            if rewritten and rewritten != base_query:
                return rewritten
        except Exception:
            pass
    if fast_refined and fast_refined != base_query:
        return fast_refined
    return heuristic if heuristic != base_query else ""

def _fast_refine_files_first_query(self, query: str) -> str:
    base_query = str(query or "").strip()
    if not base_query:
        return ""
    flags = _query_flags(base_query)
    alias_service = get_runtime_alias_service()
    terms: list[str] = []
    seen: set[str] = set()

    def push(value: str) -> None:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(normalized) < 2 or normalized in seen:
            return
        seen.add(normalized)
        terms.append(normalized)

    try:
        analysis = analyze_tcm_query(base_query)
        for item in analysis.matched_entities:
            name = str(item.name).strip()
            if len(name) >= 2:
                push(name)
                if alias_service.is_available():
                    for alias_name in alias_service.aliases_for_entity(name, max_aliases=2):
                        push(str(alias_name).strip())
    except Exception:
        pass

    for match in re.finditer(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)", base_query):
        push(match.group(0))

    for pattern in (
        r"^([\u4e00-\u9fff]{2,8}?)(?:主|治)",
        r"中的([\u4e00-\u9fff]{2,8})",
        r"^([\u4e00-\u9fff]{2,8}?)(?:的性味|的功效|的归经)",
    ):
        for match in re.finditer(pattern, base_query):
            push(match.group(1))

    for match in re.finditer(r"《([^》]{2,16})》", base_query):
        push(match.group(1))

    for match in re.finditer(r"[\u4e00-\u9fff]{2,8}", base_query):
        token = str(match.group(0)).strip()
        if token in {"什么", "为何", "为什么", "请给", "请从", "作用", "区别", "不同", "如何", "对应"}:
            continue
        if len(terms) >= 6:
            break
        push(token)

    if flags.get("source_query"):
        for cue in ("出处", "原文", "条文", "记载"):
            push(cue)
        if any(term in base_query for term in ("黄芪", "黄耆", "当归", "柴胡", "人参", "甘草", "附子", "地黄")):
            push("本草")
    if flags.get("property_query"):
        for cue in ("功效", "作用", "方解", "归经", "性味"):
            push(cue)
    if flags.get("composition_query"):
        for cue in ("组成", "药味", "加减", "方后注"):
            push(cue)
    if flags.get("comparison_query"):
        for cue in ("比较", "区别", "异同"):
            push(cue)

    refined = " ".join(terms[:10]).strip()
    return refined if refined and refined != base_query else ""

def _primary_refine_entities(query: str) -> list[str]:
    entities: list[str] = []
    for match in re.finditer(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)", query):
        entities.append(str(match.group(0)).strip())
    for pattern in (
        r"^([\u4e00-\u9fff]{2,8}?)(?:主|治)",
        r"中的([\u4e00-\u9fff]{2,8})",
        r"^([\u4e00-\u9fff]{2,8}?)(?:的性味|的功效|的归经)",
    ):
        for match in re.finditer(pattern, query):
            entities.append(str(match.group(1)).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for item in entities:
        if len(item) < 2 or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:4]

def _prefer_refined_result(*, primary: dict[str, Any], refined: dict[str, Any]) -> bool:
    primary_chunks = primary.get("chunks", []) if isinstance(primary.get("chunks"), list) else []
    refined_chunks = refined.get("chunks", []) if isinstance(refined.get("chunks"), list) else []
    if not refined_chunks:
        return False
    if not primary_chunks:
        return True
    primary_top = float(primary_chunks[0].get("score", 0.0) or 0.0)
    refined_top = float(refined_chunks[0].get("score", 0.0) or 0.0)
    if len(refined_chunks) > len(primary_chunks):
        return True
    return refined_top > primary_top + 0.03


def rewrite_query(self, query: str, strategy: str = "complex") -> dict[str, Any]:
    strategy = (strategy or "complex").strip().lower()
    expanded_query = f"{query}。请结合证候、治法、方剂出处与原文进行检索。"
    step_back_question = f"{query} 背后的中医辨证与治法原则是什么？" if strategy in {"step_back", "complex"} else ""
    step_back_answer = ""
    hypothetical_doc = ""

    if step_back_question and self.rewrite_client.is_ready():
        prompt = f"请用不超过120字回答：{step_back_question}"
        step_back_answer = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
    elif step_back_question:
        step_back_answer = "先辨证后论治，结合症状、证候、治法与方剂来源综合判断。"

    if strategy in {"hyde", "complex"}:
        if self.rewrite_client.is_ready():
            prompt = f"请生成一段用于检索的假设性资料片段：{query}"
            hypothetical_doc = self.rewrite_client.chat(prompt, self.settings.rewrite_model)
        else:
            hypothetical_doc = f"{query} 可从证候识别、治法匹配、方剂来源、古籍原文四个维度组织答案。"

    if step_back_question and step_back_answer:
        expanded_query = f"{expanded_query}\n退步问题：{step_back_question}\n退步问题答案：{step_back_answer}"

    return {
        "strategy": strategy,
        "expanded_query": expanded_query,
        "step_back_question": step_back_question,
        "step_back_answer": step_back_answer,
        "hypothetical_doc": hypothetical_doc,
    }
