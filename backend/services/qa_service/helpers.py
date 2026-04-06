from __future__ import annotations

import json
from typing import Any

from services.common.medical_guard import append_disclaimer
from services.qa_service.models import AnswerMode

def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    parsed = _safe_json_loads(cleaned)
    if isinstance(parsed, dict):
        return parsed
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        parsed = _safe_json_loads("\n".join(lines))
        if isinstance(parsed, dict):
            return parsed
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        parsed = _safe_json_loads(cleaned[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    return None


def _compact_json(payload: dict[str, Any]) -> str:
    compact = {key: value for key, value in payload.items() if value not in (None, "", [], {})}
    return json.dumps(compact, ensure_ascii=False) if compact else ""


def _guard_refused_result(*, mode: AnswerMode, guard) -> dict[str, Any]:
    answer = append_disclaimer(guard.refuse_response, guard.disclaimer) if guard.disclaimer else guard.refuse_response
    return {
        "mode": mode,
        "status": "guard_refused",
        "answer": answer,
        "risk_level": guard.risk_level.value,
        "matched_guard_patterns": guard.matched_patterns,
        "query_analysis": {},
        "retrieval_strategy": {},
        "route": {"route": None, "reason": "medical_guard_refused", "status": "guard_refused", "final_route": None, "executed_routes": []},
        "evidence_paths": [],
        "factual_evidence": [],
        "case_references": [],
        "citations": [],
        "book_citations": [],
        "planner_steps": [],
        "deep_trace": [],
        "evidence_bundle": {
            "evidence_paths": [],
            "factual_evidence": [],
            "case_references": [],
            "coverage": {"gaps": [], "factual_count": 0, "case_count": 0, "evidence_path_count": 0, "sufficient": False},
        },
        "service_trace_ids": {},
        "service_backends": {},
        "generation_backend": "medical_guard",
        "tool_trace": [],
        "notes": [],
    }


def _finalize_result(*, result: dict[str, Any], guard) -> dict[str, Any]:
    answer_text = str(result.get("answer", "") or "").strip()
    if guard.disclaimer:
        answer_text = append_disclaimer(answer_text, guard.disclaimer)
    result["answer"] = answer_text
    result["risk_level"] = guard.risk_level.value
    result["matched_guard_patterns"] = guard.matched_patterns
    return result


def _route_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "route": payload.get("route"),
        "reason": payload.get("route_reason", ""),
        "status": payload.get("status", "ok"),
        "final_route": payload.get("final_route"),
        "executed_routes": payload.get("executed_routes", []),
    }


def _planner_step(*, stage: str, label: str, detail: str = "", skill: str = "") -> dict[str, str]:
    step = {"stage": stage, "label": label, "detail": detail}
    if skill:
        step["skill"] = skill
    return step


def _planner_step_for_action(*, action: dict[str, Any], round_index: int, action_index: int) -> dict[str, str]:
    label_map = {"read_evidence_path": "读取证据路径", "search_evidence_text": "补充文本检索"}
    detail = [f"round={round_index}", f"action={action_index}"]
    if action.get("skill"):
        detail.append(f"skill={action['skill']}")
    if action.get("path"):
        detail.append(f"path={action['path']}")
    if action.get("reason"):
        detail.append(f"reason={action['reason']}")
    return _planner_step(
        stage=str(action.get("tool", "followup")),
        label=label_map.get(str(action.get("tool", "")), "执行后续动作"),
        detail="; ".join(detail),
        skill=str(action.get("skill", "")).strip(),
    )


def _trace_step(*, step_index: int, action: dict[str, Any], new_evidence: list[dict[str, Any]], coverage_after_step: dict[str, Any]) -> dict[str, Any]:
    return {
        "step": step_index,
        "skill": action.get("skill"),
        "tool": action.get("tool"),
        "input": {key: value for key, value in action.items() if key in {"path", "query", "scope_paths", "top_k", "skill"} and value not in (None, "", [], {})},
        "why_this_step": action.get("reason", ""),
        "new_evidence": new_evidence,
        "coverage_after_step": coverage_after_step,
    }


def _tool_input_for_action(action: dict[str, Any]) -> str:
    return _compact_json({key: value for key, value in action.items() if key in {"query", "path", "scope_paths", "top_k", "skill"} and value not in (None, "", [], {})})


