from __future__ import annotations

from typing import Any

from services.qa_service.helpers import _extract_json_object
from services.qa_service.planner import (
    _apply_origin_action_policy,
    _normalize_gap_names,
    _normalize_planner_actions,
    _plan_followup_actions,
)
from services.qa_service.prompts import _build_planner_system_prompt, _build_planner_user_prompt


def resolve_followup_actions(
    *,
    planner_skills: list[dict[str, Any]],
    settings,
    query: str,
    payload: dict[str, Any],
    evidence_paths: list[str],
    factual_evidence: list[dict[str, Any]],
    plan: dict[str, Any],
    heuristic_gaps: list[str],
    plan_gaps: list[str],
    executed_actions: set[str],
) -> list[dict[str, Any]]:
    planner_payload = {**payload, "_planner_factual_evidence": factual_evidence}
    resolved_gaps = plan_gaps or heuristic_gaps
    raw_actions = plan.get("next_actions", []) if isinstance(plan.get("next_actions"), list) else []
    actions = _normalize_planner_actions(
        planner_skills=planner_skills,
        raw_actions=raw_actions,
        query=query,
        payload=payload,
        evidence_paths=evidence_paths,
        executed_actions=executed_actions,
        max_actions=settings.max_actions_per_round,
    )
    if not actions:
        fallback_actions = _plan_followup_actions(
            planner_skills=planner_skills,
            query=query,
            payload=planner_payload,
            evidence_paths=evidence_paths,
            gaps=resolved_gaps,
            max_actions=settings.max_actions_per_round,
            executed_actions=executed_actions,
        )
        actions = _normalize_planner_actions(
            planner_skills=planner_skills,
            raw_actions=fallback_actions,
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            executed_actions=executed_actions,
            max_actions=settings.max_actions_per_round,
        )
    return _apply_origin_action_policy(
        planner_skills=planner_skills,
        query=query,
        payload=planner_payload,
        evidence_paths=evidence_paths,
        gaps=resolved_gaps,
        actions=actions,
        max_actions=settings.max_actions_per_round,
        executed_actions=executed_actions,
    )


async def generate_followup_plan(
    *,
    planner_skills: list[dict[str, Any]],
    settings,
    answer_generator,
    query: str,
    payload: dict[str, Any],
    evidence_paths: list[str],
    factual_evidence: list[dict[str, Any]],
    case_references: list[dict[str, Any]],
    deep_trace: list[dict[str, Any]],
    heuristic_gaps: list[str],
    coverage_summary: dict[str, Any],
    executed_actions: set[str],
) -> tuple[dict[str, Any], str, str | None]:
    fallback_plan = {
        "gaps": heuristic_gaps,
        "next_actions": _plan_followup_actions(
            planner_skills=planner_skills,
            query=query,
            payload={**payload, "_planner_factual_evidence": factual_evidence},
            evidence_paths=evidence_paths,
            gaps=heuristic_gaps,
            max_actions=settings.max_actions_per_round,
            executed_actions=executed_actions,
        ),
        "stop_reason": "",
    }
    try:
        content = await answer_generator.acomplete(
            system_prompt=_build_planner_system_prompt(planner_skills),
            user_prompt=_build_planner_user_prompt(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                case_references=case_references,
                deep_trace=deep_trace,
                heuristic_gaps=heuristic_gaps,
                max_actions=settings.max_actions_per_round,
                executed_actions=sorted(executed_actions),
                coverage_summary=coverage_summary,
            ),
        )
        parsed = _extract_json_object(content)
        if not isinstance(parsed, dict):
            raise RuntimeError("planner_json_unparseable")
        parsed["gaps"] = _normalize_gap_names(parsed.get("gaps", [])) or heuristic_gaps
        parsed.setdefault("next_actions", [])
        parsed.setdefault("stop_reason", "")
        return parsed, "planner_llm", None
    except Exception as exc:
        return fallback_plan, "heuristic_planner", f"planner_llm_fallback:{exc}"
