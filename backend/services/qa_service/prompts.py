from __future__ import annotations

from typing import Any

from services.qa_service.models import AnswerMode
from services.qa_service.skill_registry import RuntimeSkill

def _build_grounded_system_prompt(*, mode: AnswerMode) -> str:
    mode_text = "快速模式" if mode == "quick" else "深度模式"
    return (
        "你是面向用户的中医知识问答助手。"
        f"当前处于{mode_text}。"
        "你将基于后端已经筛选出的结构化证据回答。"
        "先给结论，再给依据；不要输出 JSON 或 tool 名称；证据不足要明确说明；涉及出处时优先点出书名、篇章或教材来源。"
        "如果用户要求从若干角度概括或分别说明，必须按这些角度显式分段作答，直接保留对应的小标题或提示词。"
    )


def _build_grounded_user_prompt(*, query: str, payload: dict[str, Any], mode: AnswerMode, factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], citations: list[str], notes: list[str], book_citations: list[str], deep_trace: list[dict[str, Any]], evidence_limit: int) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    lines = [
        f"用户问题：{query}",
        f"执行模式：{mode}",
        f"意图：{strategy.get('intent', analysis.get('dominant_intent', ''))}",
        f"核心实体：{strategy.get('entity_name', '')}",
        f"症状/证候：{strategy.get('symptom_name', '')}",
    ]
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    if isinstance(compare_entities, list) and compare_entities:
        lines.append("比较对象：" + "、".join(str(item) for item in compare_entities if str(item).strip()))
    requested_dimensions = _requested_answer_dimensions(query)
    if requested_dimensions:
        lines.append("用户要求保留的回答角度：" + "、".join(requested_dimensions))
        lines.append("输出要求：请按这些角度逐段作答，并显式写出对应标题。")
    lines.append("事实证据：")
    if factual_evidence:
        for index, item in enumerate(factual_evidence[:evidence_limit], start=1):
            lines.append(f"{index}. [{item.get('source_type', 'unknown')}] {item.get('source', 'unknown')} | {item.get('predicate', '')}:{item.get('target', '')} | {item.get('snippet', '')}")
    else:
        lines.append("1. 当前没有事实证据。")
    if case_references:
        lines.append("案例参考：")
        for index, item in enumerate(case_references[:3], start=1):
            lines.append(f"{index}. {item.get('document', '')[:80]} | {item.get('snippet', '')[:120]}")
    if book_citations:
        lines.append("权威出处：" + "；".join(book_citations[:4]))
    if deep_trace:
        lines.append("深度检索轨迹：")
        for item in deep_trace[-4:]:
            lines.append(f"- step {item.get('step')} | skill={item.get('skill')} | why={item.get('why_this_step', '')} | remaining={','.join(item.get('coverage_after_step', {}).get('gaps', []))}")
    if notes:
        lines.append("补充说明：" + "；".join(notes[:6]))
    if citations:
        lines.append("可引用来源：" + "；".join(citations[:4]))
    lines.append("输出自然中文答案，不复述检索流程，末尾可用“依据：...”列 1 到 3 条来源。")
    return "\n".join(lines)


def _requested_answer_dimensions(query: str) -> list[str]:
    text = str(query or "").strip()
    dimension_keywords = ("组成", "功效", "主治", "出处", "归经", "性味", "配伍", "治法")
    return [keyword for keyword in dimension_keywords if keyword in text]


def _build_planner_system_prompt(planner_skills: dict[str, RuntimeSkill]) -> str:
    skill_lines: list[str] = []
    for name, skill in planner_skills.items():
        tool_text = ", ".join(skill.preferred_tools[:2]) if skill.preferred_tools else skill.primary_tool
        workflow_text = "；".join(skill.workflow_steps[:2])
        stop_text = "；".join(skill.stop_rules[:1])
        skill_lines.append(
            f"- {name}: {skill.description} | preferred_tools={tool_text or 'n/a'} | workflow={workflow_text or 'n/a'} | stop={stop_text or 'n/a'}"
        )
    skills = "\n".join(skill_lines)
    return (
        "你是中医知识问答系统中的 deep planner。"
        "你不能直接回答问题，只能规划下一步检索。"
        "你必须输出 JSON 对象，字段固定为 gaps、next_actions、stop_reason。"
        "每轮最多规划 2 个动作。"
        "如果证据已足够，next_actions 返回空数组并填写 stop_reason。"
        f"可用 skill 如下：\n{skills}\n"
        "动作对象允许字段：skill、path、query、scope_paths、reason。不要输出 markdown。"
    )


def _build_planner_user_prompt(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], deep_trace: list[dict[str, Any]], heuristic_gaps: list[str], max_actions: int) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    lines = [
        f"query: {query}",
        f"intent: {strategy.get('intent', '')}",
        f"entity_name: {strategy.get('entity_name', '')}",
        f"symptom_name: {strategy.get('symptom_name', '')}",
        f"compare_entities: {strategy.get('compare_entities', [])}",
        f"heuristic_gaps: {heuristic_gaps}",
        f"evidence_paths: {evidence_paths[:10]}",
        f"max_actions: {max_actions}",
        "factual_evidence:",
    ]
    for item in factual_evidence[:6]:
        lines.append(f"- {item.get('source_type')} | {item.get('source')} | {item.get('predicate', '')}:{item.get('target', '')} | {item.get('snippet', '')[:120]}")
    if case_references:
        lines.append("case_references:")
        for item in case_references[:3]:
            lines.append(f"- {item.get('source')} | {item.get('document', '')[:60]} | {item.get('snippet', '')[:100]}")
    if deep_trace:
        lines.append("previous_steps:")
        for item in deep_trace[-4:]:
            lines.append(f"- step={item.get('step')} skill={item.get('skill')} why={item.get('why_this_step')} remaining={item.get('coverage_after_step', {}).get('gaps', [])}")
    lines.append("请输出 JSON，例如：{\"gaps\":[\"origin\"],\"next_actions\":[{\"skill\":\"read-formula-origin\",\"path\":\"book://某书/*\",\"reason\":\"补出处\"}],\"stop_reason\":\"\"}")
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

