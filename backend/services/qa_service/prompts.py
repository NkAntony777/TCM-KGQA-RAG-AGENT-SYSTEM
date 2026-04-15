from __future__ import annotations

from typing import Any

from services.qa_service.models import ALLOWED_PLANNER_GAPS, AnswerMode
from services.qa_service.skill_registry import RuntimeSkill


def _planner_factual_summary(items: list[dict[str, Any]], *, limit: int = 4) -> list[str]:
    summary: list[str] = []
    for item in items[:limit]:
        source_type = str(item.get("source_type", "")).strip() or "unknown"
        source = str(item.get("source", "")).strip() or "unknown"
        predicate = str(item.get("predicate", "")).strip()
        target = str(item.get("target", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        parts = [source_type, source]
        if predicate or target:
            parts.append(f"{predicate}:{target}".strip(":"))
        elif snippet:
            parts.append(snippet[:48])
        summary.append(" | ".join(part for part in parts if part))
    return summary


def _planner_case_summary(items: list[dict[str, Any]], *, limit: int = 2) -> list[str]:
    summary: list[str] = []
    for item in items[:limit]:
        source = str(item.get("source", "")).strip() or "caseqa"
        document = str(item.get("document", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        parts = [source]
        if document:
            parts.append(document[:40])
        elif snippet:
            parts.append(snippet[:40])
        summary.append(" | ".join(parts))
    return summary


def _planner_trace_summary(steps: list[dict[str, Any]], *, limit: int = 2) -> list[str]:
    summary: list[str] = []
    for item in steps[-limit:]:
        summary.append(
            " | ".join(
                [
                    f"step={item.get('step')}",
                    f"skill={item.get('skill')}",
                    f"status={item.get('status')}",
                    f"remaining={','.join(item.get('coverage_after_step', {}).get('gaps', []))}",
                ]
            )
        )
    return summary

def _build_grounded_system_prompt(*, mode: AnswerMode) -> str:
    mode_text = "快速模式" if mode == "quick" else "深度模式"
    return (
        "你是面向用户的中医知识问答助手。"
        f"当前处于{mode_text}。"
        "你将基于后端已经筛选出的结构化证据回答。"
        "先给结论，再给依据；不要输出 JSON 或 tool 名称；证据不足要明确说明；涉及出处时优先点出书名、篇章或教材来源。"
        "如果用户要求从若干角度概括或分别说明，必须按这些角度显式分段作答，直接保留对应的小标题或提示词。"
    )


def _query_requests_verbatim_evidence(query: str) -> bool:
    text = str(query or "").strip()
    hints = ("原文", "原句", "原话", "条文", "方后注", "出处", "出自", "原段")
    return any(hint in text for hint in hints)


def _format_source_label(item: dict[str, Any]) -> str:
    source_book = str(item.get("source_book", "")).strip()
    source_chapter = str(item.get("source_chapter", "")).strip()
    if source_book and source_chapter:
        return f"{source_book}/{source_chapter}"
    if source_book:
        return source_book
    return str(item.get("source", "")).strip() or "unknown"


def _format_claim_text(item: dict[str, Any], *, include_snippet: bool, snippet_limit: int) -> str:
    predicate = str(item.get("predicate", "")).strip()
    target = str(item.get("target", "")).strip()
    anchor_entity = str(item.get("anchor_entity", "")).strip()
    match_snippet = str(item.get("match_snippet", "")).strip()
    snippet = str(item.get("snippet", "")).strip()
    claim = ""
    if predicate and target:
        claim = f"{predicate}:{target}"
        if anchor_entity:
            claim = f"{anchor_entity} -> {claim}"
    elif target:
        claim = target
    elif match_snippet:
        claim = match_snippet[:snippet_limit]
    elif snippet and not include_snippet:
        claim = snippet[:snippet_limit]
    if include_snippet and snippet:
        excerpt = snippet[:snippet_limit]
        if claim and excerpt and excerpt not in claim:
            return f"{claim} | 摘录:{excerpt}"
        if claim:
            return claim
        return f"摘录:{excerpt}" if excerpt else claim
    return claim or "命中相关证据"


def _grounded_factual_lines(
    *,
    items: list[dict[str, Any]],
    limit: int,
    include_snippet: bool,
) -> list[str]:
    lines: list[str] = []
    for index, item in enumerate(items[:limit], start=1):
        source_type = str(item.get("source_type", "")).strip() or "unknown"
        source_label = _format_source_label(item)
        claim = _format_claim_text(item, include_snippet=include_snippet, snippet_limit=120 if include_snippet else 64)
        lines.append(f"{index}. [{source_type}] {source_label} | {claim}")
    return lines


def _grounded_group_lines(
    *,
    label: str,
    items: list[dict[str, Any]],
    limit: int,
    include_snippet: bool,
) -> list[str]:
    if not items:
        return [f"{label}：none"]
    lines = [f"{label}："]
    lines.extend(
        _grounded_factual_lines(
            items=items,
            limit=limit,
            include_snippet=include_snippet,
        )
    )
    return lines


def _grounded_case_lines(items: list[dict[str, Any]], *, limit: int = 2) -> list[str]:
    lines: list[str] = []
    for index, item in enumerate(items[:limit], start=1):
        document = str(item.get("document", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        lines.append(f"{index}. {document[:60] or 'case'} | {snippet[:80]}")
    return lines


def _build_grounded_user_prompt(*, query: str, payload: dict[str, Any], mode: AnswerMode, factual_evidence: list[dict[str, Any]], evidence_groups: dict[str, list[dict[str, Any]]], case_references: list[dict[str, Any]], citations: list[str], notes: list[str], book_citations: list[str], deep_trace: list[dict[str, Any]], evidence_limit: int) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    include_verbatim_evidence = _query_requests_verbatim_evidence(query)
    answer_policy = str(strategy.get("answer_policy", "")).strip()
    lines = [
        f"用户问题：{query}",
        f"执行模式：{mode}",
        f"意图：{strategy.get('intent', analysis.get('dominant_intent', ''))}",
        f"核心实体：{strategy.get('entity_name', '')}",
        f"症状/证候：{strategy.get('symptom_name', '')}",
    ]
    if answer_policy:
        lines.append(f"回答策略：{answer_policy}")
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    if isinstance(compare_entities, list) and compare_entities:
        lines.append("比较对象：" + "、".join(str(item) for item in compare_entities if str(item).strip()))
    requested_dimensions = _requested_answer_dimensions(query)
    if requested_dimensions:
        lines.append("用户要求保留的回答角度：" + "、".join(requested_dimensions))
        lines.append("输出要求：请按这些角度逐段作答，并显式写出对应标题。")
    lines.append("事实证据摘要：")
    structured_items = evidence_groups.get("structured", []) if isinstance(evidence_groups, dict) else []
    documentary_items = evidence_groups.get("documentary", []) if isinstance(evidence_groups, dict) else []
    other_items = evidence_groups.get("other", []) if isinstance(evidence_groups, dict) else []
    if structured_items:
        lines.extend(
            _grounded_group_lines(
                label="结构化图谱证据",
                items=structured_items,
                limit=min(evidence_limit, 4),
                include_snippet=False,
            )
        )
    if documentary_items:
        lines.extend(
            _grounded_group_lines(
                label="文献原文证据",
                items=documentary_items,
                limit=min(evidence_limit, 4),
                include_snippet=include_verbatim_evidence,
            )
        )
    if other_items:
        lines.extend(
            _grounded_group_lines(
                label="补充证据",
                items=other_items,
                limit=max(1, min(evidence_limit, 2)),
                include_snippet=include_verbatim_evidence,
            )
        )
    if not factual_evidence:
        lines.append("1. 当前没有事实证据。")
    if case_references:
        lines.append("案例参考：")
        lines.extend(_grounded_case_lines(case_references))
    if book_citations:
        lines.append("权威出处：" + "；".join(book_citations[:4]))
    if deep_trace:
        lines.append("深度检索轨迹摘要：")
        for item in deep_trace[-2:]:
            lines.append(f"- step {item.get('step')} | skill={item.get('skill')} | why={item.get('why_this_step', '')} | remaining={','.join(item.get('coverage_after_step', {}).get('gaps', []))}")
    if notes:
        lines.append("补充说明：" + "；".join(notes[:6]))
    if citations:
        lines.append("可引用来源：" + "；".join(citations[: (2 if mode == 'quick' else 3)]))
    if include_verbatim_evidence:
        lines.append("回答时允许引用上面的出处摘录，但保持精简，不要大段抄录。")
    else:
        lines.append("回答时优先用 claim 级摘要组织结论，不要复述整段原文。")
    if answer_policy == "graph_relation_first":
        lines.append("输出要求：先用结构化关系给结论，再补充必要的文献出处；若文献证据缺失，应明确说明当前结论主要来自图谱关系。")
    elif answer_policy == "graph_relation_with_origin":
        lines.append("输出要求：先概括图谱关系结论，再补充对应出处或条文支撑；若用户问出处/原文，必须优先交代书名、篇章或方后注。")
    lines.append("输出自然中文答案，不复述检索流程，末尾可用“依据：...”列 1 到 3 条来源。")
    return "\n".join(lines)


def _requested_answer_dimensions(query: str) -> list[str]:
    text = str(query or "").strip()
    dimension_hints: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("组成", ("组成", "药材", "组方", "配方")),
        ("配伍", ("配伍", "方义", "配伍原理")),
        ("功效", ("功效", "作用", "治法")),
        ("主治", ("主治", "适应证", "证候", "治什么")),
        ("病机", ("病机", "机制", "原理", "为什么")),
        ("鉴别", ("鉴别", "辨析", "区别", "异同", "比较")),
        ("出处", ("出处", "出自", "原文", "原句", "原话")),
        ("指导意义", ("指导意义", "临床意义", "启示")),
        ("现代对接", ("现代", "免疫", "褪黑素", "GABA", "通路", "分子")),
        ("归经", ("归经",)),
        ("性味", ("性味",)),
    )
    selected: list[str] = []
    for label, hints in dimension_hints:
        if any(hint in text for hint in hints):
            selected.append(label)
    return list(dict.fromkeys(selected))


def _build_planner_system_prompt(planner_skills: dict[str, RuntimeSkill]) -> str:
    skill_lines: list[str] = []
    for name, skill in planner_skills.items():
        tool_text = ", ".join(skill.preferred_tools[:2]) if skill.preferred_tools else skill.primary_tool
        workflow_text = "；".join(skill.workflow_steps[:2])
        trigger_text = "；".join(skill.trigger_phrases[:3])
        path_text = "；".join(skill.preferred_path_patterns[:2])
        stop_text = "；".join(skill.stop_rules[:1])
        skill_lines.append(
            f"- {name}: {skill.description} | preferred_tools={tool_text or 'n/a'} | triggers={trigger_text or 'n/a'} | preferred_paths={path_text or 'n/a'} | workflow={workflow_text or 'n/a'} | stop={stop_text or 'n/a'}"
        )
    skills = "\n".join(skill_lines)
    allowed_gaps = "、".join(ALLOWED_PLANNER_GAPS)
    return (
        "你是中医知识问答系统中的 deep planner。"
        "你不能直接回答问题，只能规划下一步检索。"
        "你必须输出 JSON 对象，字段固定为 gaps、next_actions、stop_reason。"
        "每轮最多规划 2 个动作。"
        "每轮优先只补 1 到 2 个最关键缺口，不要把所有问题一次查完。"
        "不要重复已经执行过的动作。"
        "如果证据已足够，next_actions 返回空数组并填写 stop_reason。"
        f"gaps 只能来自：{allowed_gaps}。"
        f"可用 skill 如下：\n{skills}\n"
        "动作对象允许字段：skill、path、query、scope_paths、reason、top_k。"
        "不要输出 markdown，不要输出解释文本。"
        "输出格式示例："
        "{\"gaps\":[\"origin\"],\"next_actions\":[{\"skill\":\"read-formula-origin\",\"path\":\"entity://六味地黄丸/*\",\"reason\":\"先锁定来源书目\"}],\"stop_reason\":\"\"}"
    )


def _build_planner_user_prompt(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], deep_trace: list[dict[str, Any]], heuristic_gaps: list[str], max_actions: int, executed_actions: list[str], coverage_summary: dict[str, Any]) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    factual_summary = _planner_factual_summary(factual_evidence)
    case_summary = _planner_case_summary(case_references)
    trace_summary = _planner_trace_summary(deep_trace)
    lines = [
        f"query: {query}",
        f"intent: {strategy.get('intent', '')}",
        f"entity_name: {strategy.get('entity_name', '')}",
        f"symptom_name: {strategy.get('symptom_name', '')}",
        f"compare_entities: {strategy.get('compare_entities', [])}",
        f"heuristic_gaps: {heuristic_gaps}",
        f"coverage_summary: {coverage_summary}",
        f"evidence_paths: {evidence_paths[:6]}",
        f"executed_actions: {executed_actions[:6]}",
        f"max_actions: {max_actions}",
        "factual_summary:",
    ]
    lines.extend(f"- {item}" for item in factual_summary) if factual_summary else lines.append("- none")
    if case_summary:
        lines.append("case_summary:")
        lines.extend(f"- {item}" for item in case_summary)
    if trace_summary:
        lines.append("previous_steps:")
        lines.extend(f"- {item}" for item in trace_summary)
    lines.append("规划原则：先补最关键缺口；优先使用已有 evidence_path；不要重复 executed_actions；不要规划超过 2 个动作。")
    lines.append("请只输出 JSON。")
    return "\n".join(lines)



def _compose_fallback_answer(*, query: str, payload: dict[str, Any], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], citations: list[str]) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    intent = str(strategy.get("intent", "")).strip()
    if intent == "formula_composition":
        herbs = [str(item.get("target", "")).strip() for item in factual_evidence if str(item.get("predicate", "")).strip() == "使用药材" and str(item.get("target", "")).strip()]
        herbs = list(dict.fromkeys(herbs))
        if herbs:
            entity = str(strategy.get("entity_name", "")).strip() or "该方剂"
            return f"{entity}的组成主要包括{'、'.join(herbs[:12])}。\n\n依据：" + "；".join(citations[:3])
    if intent == "formula_efficacy":
        targets = [str(item.get("target", "")).strip() for item in factual_evidence if str(item.get("predicate", "")).strip() in {"功效", "治法", "归经"} and str(item.get("target", "")).strip()]
        targets = list(dict.fromkeys(targets))
        if targets:
            entity = str(strategy.get("entity_name", "")).strip() or "该药物/方剂"
            return f"{entity}当前检索到的核心信息包括{'、'.join(targets[:8])}。\n\n依据：" + "；".join(citations[:3])
    if factual_evidence:
        snippet = str(factual_evidence[0].get("snippet", "")).strip() or f"已围绕“{query}”检索到相关证据。"
        answer = snippet[:160] + ("" if snippet.endswith(("。", "！", "？")) else "。")
    else:
        answer = "当前没有检索到足够可靠的事实依据，暂时不能给出确定结论。"
    if case_references:
        snippet = str(case_references[0].get("snippet", "")).strip()
        if snippet:
            answer += f"\n\n相似案例参考：{snippet[:100]}。"
    if citations:
        answer += "\n\n依据：" + "；".join(citations[:3])
    return answer

