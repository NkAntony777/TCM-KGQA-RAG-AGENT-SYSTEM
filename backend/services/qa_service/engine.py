from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from services.common.medical_guard import append_disclaimer, assess_query
from services.qa_service.llm_client import GroundedAnswerLLMClient
from services.qa_service.skill_registry import RuntimeSkill, get_runtime_skills
from tools.tcm_evidence_tools import EvidenceNavigator
from tools.tcm_route_tool import TCMRouteSearchTool

AnswerMode = Literal["quick", "deep"]


@dataclass(frozen=True)
class QAServiceSettings:
    default_top_k: int = 12
    max_factual_evidence: int = 6
    max_case_references: int = 3
    max_citations: int = 6
    max_quick_prompt_evidence: int = 6
    max_deep_prompt_evidence: int = 8
    max_deep_rounds: int = 3
    max_actions_per_round: int = 2
    deep_read_top_k: int = 6
    max_trace_evidence_per_step: int = 3


class QAService:
    def __init__(
        self,
        *,
        route_tool: TCMRouteSearchTool | None = None,
        agent_manager_ref=None,
        settings: QAServiceSettings | None = None,
        answer_generator=None,
        evidence_navigator: EvidenceNavigator | None = None,
    ) -> None:
        self.route_tool = route_tool or TCMRouteSearchTool()
        self.agent_manager = agent_manager_ref
        self.settings = settings or QAServiceSettings()
        self.answer_generator = answer_generator or GroundedAnswerLLMClient()
        self.evidence_navigator = evidence_navigator or EvidenceNavigator()
        self.planner_skills = get_runtime_skills()

    async def answer(
        self,
        query: str,
        *,
        mode: AnswerMode = "quick",
        top_k: int | None = None,
    ) -> dict[str, Any]:
        final_result: dict[str, Any] | None = None
        async for event in self.stream_answer(query, mode=mode, top_k=top_k):
            if event.get("type") == "result" and isinstance(event.get("result"), dict):
                final_result = event["result"]
        if final_result is None:
            raise RuntimeError("qa_result_missing")
        return final_result

    async def stream_answer(
        self,
        query: str,
        *,
        mode: AnswerMode = "quick",
        top_k: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            raise ValueError("query_empty")

        resolved_top_k = max(1, int(top_k or self.settings.default_top_k))
        guard = assess_query(normalized_query)
        if guard.should_refuse:
            result = {
                "mode": mode,
                "status": "guard_refused",
                "answer": append_disclaimer(guard.refuse_response, guard.disclaimer) if guard.disclaimer else guard.refuse_response,
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
                "evidence_bundle": {"evidence_paths": [], "factual_evidence": [], "case_references": [], "coverage": {"gaps": [], "factual_count": 0, "case_count": 0, "evidence_path_count": 0, "sufficient": False}},
                "service_trace_ids": {},
                "service_backends": {},
                "generation_backend": "medical_guard",
                "tool_trace": [],
                "notes": [],
            }
            yield {"type": "qa_mode", "mode": mode}
            yield {"type": "token", "content": result["answer"]}
            yield {"type": "done", "content": result["answer"]}
            yield {"type": "result", "result": result}
            return

        if mode == "deep":
            try:
                async for event in self._stream_deep(normalized_query, top_k=resolved_top_k, guard=guard):
                    yield event
                return
            except Exception as exc:
                async for event in self._stream_quick(
                    normalized_query,
                    top_k=resolved_top_k,
                    guard=guard,
                    result_mode="deep",
                    notes_prefix=[f"deep_mode_fallback_to_quick:{exc}"],
                    status_override="degraded",
                    generation_backend_override="quick_fallback",
                ):
                    yield event
                return

        async for event in self._stream_quick(normalized_query, top_k=resolved_top_k, guard=guard):
            yield event

    async def _stream_quick(
        self,
        query: str,
        *,
        top_k: int,
        guard,
        result_mode: AnswerMode = "quick",
        notes_prefix: list[str] | None = None,
        status_override: str | None = None,
        generation_backend_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "qa_mode", "mode": result_mode}

        route_output = self.route_tool._run(query=query, top_k=top_k)
        payload = _safe_json_loads(route_output)
        if not isinstance(payload, dict):
            payload = {"status": "evidence_insufficient", "notes": ["route_output_unparseable"]}

        route_meta = {
            "status": payload.get("status", "evidence_insufficient"),
            "final_route": payload.get("final_route", payload.get("route")),
            "query": query,
            "count": len(payload.get("evidence_paths", [])) if isinstance(payload.get("evidence_paths"), list) else 0,
        }
        planner_steps = [
            _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={payload.get('final_route', payload.get('route', 'unknown'))}"),
            _planner_step(stage="answer_synthesis", label="生成最终答案", detail="quick_grounded_answer"),
        ]
        yield {"type": "planner_step", "step": planner_steps[0]}
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
        yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_meta), "meta": route_meta}

        route_event = _route_from_payload(payload)
        if route_event:
            yield {"type": "route", **route_event}

        factual_evidence = _factual_evidence_from_payload(payload)
        case_references = _case_reference_from_payload(payload)
        initial_items = factual_evidence + case_references
        if initial_items:
            yield {"type": "evidence", "items": initial_items}

        result = await self._build_response(
            query=query,
            payload=payload,
            mode=result_mode,
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=[{"tool": "tcm_route_search", "meta": route_meta}],
            notes=list(notes_prefix or []),
            evidence_paths=payload.get("evidence_paths", []),
            planner_steps=planner_steps,
            deep_trace=[],
        )
        if status_override:
            result["status"] = status_override
        if generation_backend_override:
            result["generation_backend"] = generation_backend_override
        result = _finalize_result(result=result, guard=guard)

        if result.get("notes"):
            yield {"type": "notes", "items": result["notes"]}
        if result.get("citations"):
            yield {"type": "citations", "items": result["citations"]}
        yield {"type": "planner_step", "step": planner_steps[-1]}
        yield {"type": "token", "content": result["answer"]}
        yield {"type": "done", "content": result["answer"]}
        yield {"type": "result", "result": result}

    async def _stream_deep(self, query: str, *, top_k: int, guard) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "qa_mode", "mode": "deep"}

        route_output = self.route_tool._run(query=query, top_k=top_k)
        payload = _safe_json_loads(route_output)
        if not isinstance(payload, dict):
            async for event in self._stream_quick(
                query,
                top_k=top_k,
                guard=guard,
                result_mode="deep",
                notes_prefix=["deep_mode_fallback_to_quick:route_output_unparseable"],
                status_override="degraded",
                generation_backend_override="quick_fallback",
            ):
                yield event
            return

        route_meta = {
            "status": payload.get("status", "ok"),
            "final_route": payload.get("final_route", payload.get("route")),
            "executed_routes": payload.get("executed_routes", []),
            "query": query,
        }
        planner_steps: list[dict[str, str]] = []
        deep_trace: list[dict[str, Any]] = []
        notes: list[str] = []
        tool_trace: list[dict[str, Any]] = []

        route_step = _planner_step(stage="route_search", label="执行首轮检索", detail=f"route={route_meta['final_route']}")
        planner_steps.append(route_step)
        yield {"type": "planner_step", "step": route_step}
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": _compact_json({"query": query, "top_k": top_k})}
        yield {"type": "tool_end", "tool": "tcm_route_search", "output": _compact_json(route_meta), "meta": route_meta}
        tool_trace.append({"tool": "tcm_route_search", "meta": route_meta})

        route_event = _route_from_payload(payload)
        if route_event:
            yield {"type": "route", **route_event}

        factual_evidence = _factual_evidence_from_payload(payload)
        case_references = _case_reference_from_payload(payload)
        initial_items = factual_evidence + case_references
        if initial_items:
            yield {"type": "evidence", "items": initial_items}

        list_step = _planner_step(stage="inspect_paths", label="整理证据路径", detail="derive_from_route_payload")
        planner_steps.append(list_step)
        yield {"type": "planner_step", "step": list_step}
        yield {"type": "tool_start", "tool": "list_evidence_paths", "input": _compact_json({"query": query})}
        list_result = self.evidence_navigator.list_evidence_paths(query=query, route_payload=payload)
        evidence_paths = list(list_result.get("paths", [])) if isinstance(list_result.get("paths"), list) else []
        list_meta = {"count": len(evidence_paths), "query": query}
        yield {"type": "tool_end", "tool": "list_evidence_paths", "output": _compact_json(list_meta), "meta": list_meta}
        tool_trace.append({"tool": "list_evidence_paths", "meta": list_meta})

        executed_actions: set[str] = set()
        for round_index in range(1, self.settings.max_deep_rounds + 1):
            heuristic_gaps = _identify_evidence_gaps(
                query=query,
                payload=payload,
                factual_evidence=factual_evidence,
                case_references=case_references,
            )
            gap_step = _planner_step(stage="gap_check", label="分析证据缺口", detail=f"round={round_index}; gaps={','.join(heuristic_gaps) or 'none'}")
            planner_steps.append(gap_step)
            yield {"type": "planner_step", "step": gap_step}
            if not heuristic_gaps:
                notes.append(f"deep_round_{round_index}:coverage_sufficient")
                stop_step = _planner_step(stage="coverage_ok", label="证据覆盖满足", detail=f"round={round_index}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break

            plan, planner_backend, planner_note = await self._generate_followup_plan(
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                factual_evidence=factual_evidence,
                case_references=case_references,
                deep_trace=deep_trace,
                heuristic_gaps=heuristic_gaps,
                executed_actions=executed_actions,
            )
            if planner_note:
                notes.append(planner_note)
            plan_step = _planner_step(stage="planner", label="规划下一步检索", detail=f"round={round_index}; backend={planner_backend}; actions={len(plan.get('next_actions', []))}")
            planner_steps.append(plan_step)
            yield {"type": "planner_step", "step": plan_step}

            plan_gaps = [str(item).strip() for item in plan.get("gaps", []) if str(item).strip()] if isinstance(plan.get("gaps"), list) else heuristic_gaps
            raw_actions = plan.get("next_actions", []) if isinstance(plan.get("next_actions"), list) else []
            actions = _normalize_planner_actions(
                planner_skills=self.planner_skills,
                raw_actions=raw_actions,
                query=query,
                payload=payload,
                evidence_paths=evidence_paths,
                executed_actions=executed_actions,
                max_actions=self.settings.max_actions_per_round,
            )
            if not actions:
                actions = _normalize_planner_actions(
                    planner_skills=self.planner_skills,
                    raw_actions=_plan_followup_actions(
                        planner_skills=self.planner_skills,
                        query=query,
                        payload={**payload, "_planner_factual_evidence": factual_evidence},
                        evidence_paths=evidence_paths,
                        gaps=plan_gaps or heuristic_gaps,
                        max_actions=self.settings.max_actions_per_round,
                        executed_actions=executed_actions,
                    ),
                    query=query,
                    payload=payload,
                    evidence_paths=evidence_paths,
                    executed_actions=executed_actions,
                    max_actions=self.settings.max_actions_per_round,
                )
            actions = _apply_origin_action_policy(
                planner_skills=self.planner_skills,
                query=query,
                payload={**payload, "_planner_factual_evidence": factual_evidence},
                evidence_paths=evidence_paths,
                gaps=plan_gaps or heuristic_gaps,
                actions=actions,
                max_actions=self.settings.max_actions_per_round,
                executed_actions=executed_actions,
            )
            if not actions:
                stop_reason = str(plan.get("stop_reason", "") or "no_followup_action").strip()
                notes.append(f"deep_round_{round_index}:{stop_reason}")
                stop_step = _planner_step(stage="stop", label="结束补检索", detail=f"round={round_index}; reason={stop_reason}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break

            new_items_this_round = 0
            for action_index, action in enumerate(actions, start=1):
                executed_actions.add(_action_key(action))
                step = _planner_step_for_action(action=action, round_index=round_index, action_index=action_index)
                planner_steps.append(step)
                yield {"type": "planner_step", "step": step}

                tool_name = str(action.get("tool", "followup"))
                yield {"type": "tool_start", "tool": tool_name, "input": _tool_input_for_action(action)}
                result = self._execute_action(action)
                meta = {
                    "status": result.get("status", "ok"),
                    "count": result.get("count", 0),
                    "reason": action.get("reason", ""),
                    "path": action.get("path"),
                    "query": action.get("query"),
                    "skill": action.get("skill"),
                }
                yield {"type": "tool_end", "tool": tool_name, "output": _compact_json(meta), "meta": meta}
                tool_trace.append({"tool": tool_name, "meta": meta})

                items = result.get("items", []) if isinstance(result.get("items"), list) else []
                if not items:
                    deep_trace.append(
                        _trace_step(
                            step_index=len(deep_trace) + 1,
                            action=action,
                            new_evidence=[],
                            coverage_after_step=_coverage_summary(
                                query=query,
                                payload=payload,
                                evidence_paths=evidence_paths,
                                factual_evidence=factual_evidence,
                                case_references=case_references,
                            ),
                        )
                    )
                    continue

                new_factual = [item for item in items if str(item.get("evidence_type", "")).strip() != "case_reference"]
                new_cases = [item for item in items if str(item.get("evidence_type", "")).strip() == "case_reference"]
                merged_new_items: list[dict[str, Any]] = []
                if new_factual:
                    before = len(factual_evidence)
                    factual_evidence = _merge_evidence_items(primary=new_factual, fallback=factual_evidence)
                    merged_new_items.extend(new_factual)
                    new_items_this_round += max(0, len(factual_evidence) - before)
                if new_cases:
                    before = len(case_references)
                    case_references = _merge_evidence_items(primary=new_cases, fallback=case_references)
                    merged_new_items.extend(new_cases)
                    new_items_this_round += max(0, len(case_references) - before)
                if merged_new_items:
                    yield {"type": "evidence", "items": merged_new_items}
                deep_trace.append(
                    _trace_step(
                        step_index=len(deep_trace) + 1,
                        action=action,
                        new_evidence=merged_new_items[: self.settings.max_trace_evidence_per_step],
                        coverage_after_step=_coverage_summary(
                            query=query,
                            payload=payload,
                            evidence_paths=evidence_paths,
                            factual_evidence=factual_evidence,
                            case_references=case_references,
                        ),
                    )
                )

            if new_items_this_round <= 0:
                notes.append(f"deep_round_{round_index}:no_new_evidence")
                stop_step = _planner_step(stage="stop", label="未补到新证据", detail=f"round={round_index}")
                planner_steps.append(stop_step)
                yield {"type": "planner_step", "step": stop_step}
                break
        else:
            notes.append("deep_round_limit_reached")
            stop_step = _planner_step(stage="stop", label="达到轮次上限", detail=f"max_rounds={self.settings.max_deep_rounds}")
            planner_steps.append(stop_step)
            yield {"type": "planner_step", "step": stop_step}

        answer_step = _planner_step(stage="answer_synthesis", label="生成最终答案", detail="deep_grounded_answer")
        planner_steps.append(answer_step)
        yield {"type": "planner_step", "step": answer_step}

        result = await self._build_response(
            query=query,
            payload=payload,
            mode="deep",
            factual_evidence=factual_evidence,
            case_references=case_references,
            tool_trace=tool_trace,
            notes=notes,
            evidence_paths=evidence_paths,
            planner_steps=planner_steps,
            deep_trace=deep_trace,
        )
        result = _finalize_result(result=result, guard=guard)

        if result.get("notes"):
            yield {"type": "notes", "items": result["notes"]}
        if result.get("citations"):
            yield {"type": "citations", "items": result["citations"]}
        yield {"type": "token", "content": result["answer"]}
        yield {"type": "done", "content": result["answer"]}
        yield {"type": "result", "result": result}

    async def _generate_followup_plan(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        evidence_paths: list[str],
        factual_evidence: list[dict[str, Any]],
        case_references: list[dict[str, Any]],
        deep_trace: list[dict[str, Any]],
        heuristic_gaps: list[str],
        executed_actions: set[str],
    ) -> tuple[dict[str, Any], str, str | None]:
        fallback_plan = {
            "gaps": heuristic_gaps,
            "next_actions": _plan_followup_actions(
                planner_skills=self.planner_skills,
                query=query,
                payload={**payload, "_planner_factual_evidence": factual_evidence},
                evidence_paths=evidence_paths,
                gaps=heuristic_gaps,
                max_actions=self.settings.max_actions_per_round,
                executed_actions=executed_actions,
            ),
            "stop_reason": "",
        }
        try:
            content = await self.answer_generator.acomplete(
                system_prompt=_build_planner_system_prompt(self.planner_skills),
                user_prompt=_build_planner_user_prompt(
                    query=query,
                    payload=payload,
                    evidence_paths=evidence_paths,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    deep_trace=deep_trace,
                    heuristic_gaps=heuristic_gaps,
                    max_actions=self.settings.max_actions_per_round,
                ),
            )
            parsed = _extract_json_object(content)
            if not isinstance(parsed, dict):
                raise RuntimeError("planner_json_unparseable")
            parsed.setdefault("gaps", heuristic_gaps)
            parsed.setdefault("next_actions", [])
            parsed.setdefault("stop_reason", "")
            return parsed, "planner_llm", None
        except Exception as exc:
            return fallback_plan, "heuristic_planner", f"planner_llm_fallback:{exc}"

    def _execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        tool = str(action.get("tool", "")).strip()
        if tool == "read_evidence_path":
            return self.evidence_navigator.read_evidence_path(
                path=str(action.get("path", "")),
                query=str(action.get("query", "")),
                top_k=int(action.get("top_k", self.settings.deep_read_top_k) or self.settings.deep_read_top_k),
            )
        if tool == "search_evidence_text":
            scopes = action.get("scope_paths", [])
            return self.evidence_navigator.search_evidence_text(
                query=str(action.get("query", "")),
                scope_paths=scopes if isinstance(scopes, list) else [],
                top_k=int(action.get("top_k", self.settings.deep_read_top_k) or self.settings.deep_read_top_k),
            )
        return {"tool": tool or "unknown", "status": "error", "count": 0, "items": []}

    async def _build_response(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        mode: AnswerMode,
        factual_evidence: list[dict[str, Any]] | None = None,
        case_references: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
        notes: list[str] | None = None,
        evidence_paths: list[str] | None = None,
        planner_steps: list[dict[str, str]] | None = None,
        deep_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        factual = factual_evidence or _factual_evidence_from_payload(payload)
        cases = case_references or _case_reference_from_payload(payload)
        book_citations = _build_book_citations(factual_evidence=factual)
        citations = _build_citations(
            factual_evidence=factual,
            case_references=cases,
            book_citations=book_citations,
            limit=self.settings.max_citations,
        )
        answer, generation_backend, generation_notes = await self._generate_grounded_answer(
            query=query,
            payload=payload,
            mode=mode,
            factual_evidence=factual,
            case_references=cases,
            citations=citations,
            notes=notes or [],
            book_citations=book_citations,
            deep_trace=deep_trace or [],
        )
        selected_factual = factual[: self.settings.max_factual_evidence]
        selected_cases = cases[: self.settings.max_case_references]
        coverage = _coverage_summary(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths or [],
            factual_evidence=factual,
            case_references=cases,
        )
        return {
            "mode": mode,
            "status": str(payload.get("status", "ok") or "ok"),
            "answer": answer,
            "query_analysis": payload.get("query_analysis", {}),
            "retrieval_strategy": payload.get("retrieval_strategy", {}),
            "route": _route_from_payload(payload),
            "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
            "factual_evidence": selected_factual,
            "case_references": selected_cases,
            "citations": citations,
            "book_citations": book_citations,
            "planner_steps": planner_steps or [],
            "deep_trace": deep_trace or [],
            "evidence_bundle": {
                "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
                "factual_evidence": selected_factual,
                "case_references": selected_cases,
                "book_citations": book_citations,
                "coverage": coverage,
            },
            "service_trace_ids": payload.get("service_trace_ids", {}),
            "service_backends": payload.get("service_backends", {}),
            "generation_backend": generation_backend,
            "tool_trace": tool_trace or [],
            "notes": list(notes or []) + list(generation_notes),
        }

    async def _generate_grounded_answer(
        self,
        *,
        query: str,
        payload: dict[str, Any],
        mode: AnswerMode,
        factual_evidence: list[dict[str, Any]],
        case_references: list[dict[str, Any]],
        citations: list[str],
        notes: list[str],
        book_citations: list[str],
        deep_trace: list[dict[str, Any]],
    ) -> tuple[str, str, list[str]]:
        try:
            content = await self.answer_generator.acomplete(
                system_prompt=_build_grounded_system_prompt(mode=mode),
                user_prompt=_build_grounded_user_prompt(
                    query=query,
                    payload=payload,
                    mode=mode,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    citations=citations,
                    notes=notes,
                    book_citations=book_citations,
                    deep_trace=deep_trace,
                    evidence_limit=self.settings.max_quick_prompt_evidence if mode == "quick" else self.settings.max_deep_prompt_evidence,
                ),
            )
            if content:
                return content, "grounded_llm" if mode == "quick" else "planner_llm", []
            raise RuntimeError("llm_empty_response")
        except Exception as exc:
            return (
                _compose_fallback_answer(
                    query=query,
                    payload=payload,
                    factual_evidence=factual_evidence,
                    case_references=case_references,
                    citations=citations,
                ),
                "deterministic_quick_fallback" if mode == "quick" else "planner_deterministic_fallback",
                [f"{mode}_llm_fallback:{exc}"],
            )


_qa_service: QAService | None = None


def get_qa_service() -> QAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service


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


def _extract_data(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _normalize_path_predicate(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("(逆向)", "").replace("（逆向）", "").strip()


def _factual_evidence_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    graph_data = _extract_data(payload.get("graph_result"))
    retrieval_data = _extract_data(payload.get("retrieval_result"))
    relations = graph_data.get("relations", [])
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            source_book = str(relation.get("source_book", "")).strip()
            source_chapter = str(relation.get("source_chapter", "")).strip()
            snippet = str(relation.get("source_text", "")).strip() or f"{relation.get('predicate', '')}: {relation.get('target', '')}"
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": f"{source_book}/{source_chapter}".strip("/") or "graph",
                "snippet": snippet[:300],
                "score": float(relation.get("score", relation.get("confidence", relation.get("max_confidence", 0.0))) or 0.0),
                "predicate": str(relation.get("predicate", "")).strip(),
                "target": str(relation.get("target", "")).strip(),
                "source_book": source_book or None,
                "source_chapter": source_chapter or None,
            })
    syndromes = graph_data.get("syndromes", [])
    if isinstance(syndromes, list):
        for syndrome in syndromes:
            if not isinstance(syndrome, dict):
                continue
            formulas = syndrome.get("recommended_formulas", [])
            formula_text = "、".join(str(item) for item in formulas[:4]) if isinstance(formulas, list) else ""
            snippet = str(syndrome.get("source_text", "")).strip() or f"{syndrome.get('name', '')} -> {formula_text}".strip(" ->")
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "graph",
                "source": "graph/syndrome_chain",
                "snippet": snippet[:300],
                "score": float(syndrome.get("score", syndrome.get("confidence", 0.0)) or 0.0),
                "predicate": "辨证链",
                "target": str(syndrome.get("name", "")).strip(),
                "source_book": str(syndrome.get("source_book", "")).strip() or None,
                "source_chapter": str(syndrome.get("source_chapter", "")).strip() or None,
            })
    paths = graph_data.get("paths", [])
    if isinstance(paths, list):
        for path in paths:
            if not isinstance(path, dict):
                continue
            nodes = [str(item).strip() for item in path.get("nodes", []) if str(item).strip()] if isinstance(path.get("nodes"), list) else []
            edges = [_normalize_path_predicate(item) for item in path.get("edges", [])] if isinstance(path.get("edges"), list) else []
            sources = path.get("sources", [])
            source_meta = sources[0] if isinstance(sources, list) and sources and isinstance(sources[0], dict) else {}
            source_book = str(source_meta.get("source_book", "")).strip()
            source_chapter = str(source_meta.get("source_chapter", "")).strip()
            path_score = float(path.get("score", 0.0) or 0.0)
            if len(nodes) >= 2 and edges:
                for index, predicate in enumerate(edges):
                    if index + 1 >= len(nodes):
                        break
                    snippet = f"{nodes[index]} --{predicate}--> {nodes[index + 1]}"
                    evidence.append({
                        "evidence_type": "factual_grounding",
                        "source_type": "graph_path",
                        "source": f"{source_book}/{source_chapter}".strip("/") or "graph/path",
                        "snippet": snippet[:300],
                        "score": path_score,
                        "predicate": predicate,
                        "target": nodes[index + 1],
                        "source_book": source_book or None,
                        "source_chapter": source_chapter or None,
                    })
            elif nodes:
                snippet = " -> ".join(nodes)
                evidence.append({
                    "evidence_type": "factual_grounding",
                    "source_type": "graph_path",
                    "source": f"{source_book}/{source_chapter}".strip("/") or "graph/path",
                    "snippet": snippet[:300],
                    "score": path_score,
                    "predicate": "辨证链",
                    "target": nodes[-1],
                    "source_book": source_book or None,
                    "source_chapter": source_chapter or None,
                })
    chunks = retrieval_data.get("chunks", [])
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            source_file = str(chunk.get("source_file", chunk.get("filename", "unknown"))).strip()
            source_page = chunk.get("source_page", chunk.get("page_number"))
            source_book = source_file.rsplit(".", 1)[0] if source_file else ""
            evidence.append({
                "evidence_type": "factual_grounding",
                "source_type": "doc",
                "source": f"{source_file}#{source_page}" if source_page not in (None, "") else source_file,
                "snippet": str(chunk.get("text", "")).strip()[:300],
                "score": float(chunk.get("rerank_score", chunk.get("score", 0.0)) or 0.0),
                "source_book": source_book or None,
                "source_chapter": f"第{source_page}页" if source_page not in (None, "") else None,
            })
    return _dedupe_evidence(evidence)


def _case_reference_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    case_data = _extract_data(payload.get("case_qa_result"))
    chunks = case_data.get("chunks", [])
    if not isinstance(chunks, list):
        return []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        collection = str(chunk.get("collection", "caseqa")).strip()
        embedding_id = str(chunk.get("embedding_id", chunk.get("chunk_id", ""))).strip()
        evidence.append({
            "evidence_type": "case_reference",
            "source_type": "case_qa",
            "source": f"{collection}/{embedding_id}".strip("/"),
            "snippet": str(chunk.get("answer", chunk.get("text", ""))).strip()[:300],
            "document": str(chunk.get("document", "")).strip()[:240],
            "score": float(chunk.get("rerank_score", chunk.get("score", 0.0)) or 0.0),
        })
    return _dedupe_evidence(evidence)


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda current: float(current.get("score", 0.0) or 0.0), reverse=True):
        key = (str(item.get("source_type", "")).strip(), str(item.get("source", "")).strip(), str(item.get("snippet", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _merge_evidence_items(*, primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [dict(item) for item in primary]
    merged.extend(dict(item) for item in fallback)
    return _dedupe_evidence(merged)


def _build_book_citations(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for item in factual_evidence:
        source_book = str(item.get("source_book", "")).strip()
        source_chapter = str(item.get("source_chapter", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        if source_book:
            citations.append(f"{f'{source_book}/{source_chapter}'.strip('/')} {snippet[:48]}")
    return list(dict.fromkeys(item for item in citations if item.strip()))[:6]


def _build_citations(*, factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]], book_citations: list[str], limit: int) -> list[str]:
    citations: list[str] = list(book_citations)
    for item in factual_evidence:
        source = str(item.get("source", "unknown")).strip()
        predicate = str(item.get("predicate", "")).strip()
        target = str(item.get("target", "")).strip()
        citations.append(f"{source} {predicate}:{target}" if predicate and target else f"{source} {str(item.get('snippet', '')).strip()[:40]}")
    for item in case_references:
        citations.append(f"{str(item.get('source', 'caseqa')).strip()} 相似案例")
    return list(dict.fromkeys(item for item in citations if item.strip()))[:limit]


def _identify_evidence_gaps(*, query: str, payload: dict[str, Any], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> list[str]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    intent = str(strategy.get("intent", analysis.get("dominant_intent", "")) or "").strip()
    entity_name = str(strategy.get("entity_name", "")).strip()
    predicates = {str(item.get("predicate", "")).strip() for item in factual_evidence if str(item.get("predicate", "")).strip()}
    source_types = {str(item.get("source_type", "")).strip() for item in factual_evidence if str(item.get("source_type", "")).strip()}
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    sources = {str(item).strip() for item in strategy.get("sources", []) if str(item).strip()} if isinstance(strategy.get("sources", []), list) else set()

    gaps: list[str] = []
    if intent == "formula_composition" and "使用药材" not in predicates:
        gaps.append("composition")
    if intent == "formula_efficacy" and not predicates.intersection({"功效", "治法", "归经"}):
        gaps.append("efficacy")
    if intent == "formula_indication" and not predicates.intersection({"治疗证候", "治疗症状", "治疗疾病"}):
        gaps.append("indication")
    if intent == "syndrome_to_formula" and not predicates.intersection({"推荐方剂", "辨证链"}):
        gaps.append("syndrome_formula")
    if _needs_origin_support(query=query, intent=intent) and not _origin_support_sufficient(
        query=query,
        entity_name=entity_name,
        factual_evidence=factual_evidence,
        source_types=source_types,
    ):
        gaps.append("origin")
    if compare_entities and not _compare_entities_covered(compare_entities=compare_entities, factual_evidence=factual_evidence):
        gaps.append("comparison")
    if ("qa_case_vector_db" in sources or intent == "syndrome_to_formula") and not case_references and _query_benefits_from_case_reference(query=query):
        gaps.append("case_reference")
    return list(dict.fromkeys(gaps))


def _coverage_summary(*, query: str, payload: dict[str, Any], evidence_paths: list[str], factual_evidence: list[dict[str, Any]], case_references: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = _identify_evidence_gaps(query=query, payload=payload, factual_evidence=factual_evidence, case_references=case_references)
    return {"gaps": gaps, "factual_count": len(factual_evidence), "case_count": len(case_references), "evidence_path_count": len(evidence_paths), "sufficient": not gaps}


def _needs_origin_support(*, query: str, intent: str) -> bool:
    return intent == "formula_origin" or any(marker in query for marker in ("出处", "出自", "古籍", "教材", "原文", "哪本书", "来源"))


def _query_benefits_from_case_reference(*, query: str) -> bool:
    markers = ("基本信息", "主诉", "现病史", "体格检查", "舌", "脉", "类似医案", "病例", "案例")
    hits = sum(1 for marker in markers if marker in query)
    return hits >= 2 or len(query) >= 40


def _origin_support_sufficient(*, query: str, entity_name: str, factual_evidence: list[dict[str, Any]], source_types: set[str]) -> bool:
    if not factual_evidence:
        return False

    wants_source_text = any(marker in query for marker in ("原文", "原句", "原话"))
    has_graph_book = any(
        str(item.get("source_type", "")).strip() == "graph" and str(item.get("source_book", "")).strip()
        for item in factual_evidence
    )
    if entity_name:
        has_entity_linked_passage = any(
            entity_name in " ".join(
                [
                    str(item.get("source", "")).strip(),
                    str(item.get("snippet", "")).strip(),
                    str(item.get("target", "")).strip(),
                    str(item.get("source_text", "")).strip(),
                ]
            )
            for item in factual_evidence
        )
        if wants_source_text:
            return has_entity_linked_passage
        return has_graph_book or has_entity_linked_passage

    if wants_source_text:
        return any(str(item.get("snippet", "")).strip() for item in factual_evidence)
    return any(source_type in {"doc", "graph"} for source_type in source_types)


def _compare_entities_covered(*, compare_entities: list[str], factual_evidence: list[dict[str, Any]]) -> bool:
    covered = set()
    for entity in compare_entities:
        for item in factual_evidence:
            haystack = " ".join([str(item.get("source", "")), str(item.get("snippet", "")), str(item.get("predicate", "")), str(item.get("target", ""))])
            if entity and entity in haystack:
                covered.add(entity)
                break
    return len(covered) >= len(compare_entities)


def _normalize_planner_actions(*, planner_skills: dict[str, RuntimeSkill], raw_actions: list[Any], query: str, payload: dict[str, Any], evidence_paths: list[str], executed_actions: set[str], max_actions: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        action = dict(raw)
        skill = str(action.get("skill", "")).strip()
        skill_meta = planner_skills.get(skill) if skill else None
        if skill and skill_meta and not action.get("tool"):
            action["tool"] = skill_meta.primary_tool
        if skill and skill_meta is None:
            continue
        if not action.get("tool"):
            continue
        action.setdefault("query", query)
        action.setdefault("top_k", 6)
        if skill == "read-formula-composition":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "read-formula-origin":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
            action["query"] = str(action.get("query") or f"{query} 出处 原文")
        if skill == "compare-formulas":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "find-case-reference":
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith("caseqa://")])
        if skill == "search-source-text":
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith(("book://", "qa://"))])
            action["query"] = str(action.get("query") or f"{query} 出处 古籍 原文")
        if str(action.get("tool", "")) == "read_evidence_path" and not str(action.get("path", "")).strip():
            continue
        key = _action_key(action)
        if key in executed_actions:
            continue
        normalized.append(action)
        if len(normalized) >= max_actions:
            break
    return normalized


def _apply_origin_action_policy(*, planner_skills: dict[str, RuntimeSkill], query: str, payload: dict[str, Any], evidence_paths: list[str], gaps: list[str], actions: list[dict[str, Any]], max_actions: int, executed_actions: set[str]) -> list[dict[str, Any]]:
    if "origin" not in gaps:
        return actions[:max_actions]

    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    graph_source_books = _top_graph_source_books(factual_evidence=payload.get("_planner_factual_evidence", []))
    corrected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def append_action(candidate: dict[str, Any]) -> None:
        if len(corrected) >= max_actions:
            return
        key = _action_key(candidate)
        if key in executed_actions or key in seen_keys:
            return
        corrected.append(candidate)
        seen_keys.add(key)

    def is_origin_book_action(candidate: dict[str, Any]) -> bool:
        return (
            str(candidate.get("skill", "")).strip() == "read-formula-origin"
            and str(candidate.get("path", "")).strip().startswith("book://")
        )

    if entity_name and not graph_source_books:
        append_action(
            _build_skill_action(
                planner_skills=planner_skills,
                skill_name="read-formula-origin",
                path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") or f"entity://{entity_name}/*",
                query=f"{entity_name} 出处 原文",
                top_k=6,
                reason="先从实体级证据锁定来源书名与篇章",
            )
        )
        for action in actions:
            if is_origin_book_action(action):
                continue
            append_action(action)
        return corrected[:max_actions]

    if graph_source_books:
        for source_book in graph_source_books[:2]:
            append_action(
                _build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=f"book://{source_book}/*",
                    query=f"{entity_name or query} 出处 原文",
                    top_k=4,
                    reason=f"根据实体证据已定位来源书目，继续追 {source_book} 的原文片段",
                )
            )
        for action in actions:
            path = str(action.get("path", "")).strip()
            if is_origin_book_action(action) and not any(path == f"book://{book}/*" for book in graph_source_books):
                continue
            append_action(action)
        return corrected[:max_actions]

    return actions[:max_actions]


def _preferred_path_for_skill(*, skill: str, payload: dict[str, Any], evidence_paths: list[str]) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    symptom_name = str(strategy.get("symptom_name", "")).strip()
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    if skill == "read-formula-composition" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="使用药材") or f"entity://{entity_name}/使用药材"
    if skill == "read-formula-origin":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://")) or (f"book://{entity_name}/*" if entity_name else "")
    if skill == "compare-formulas" and compare_entities:
        entity = compare_entities[0]
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity}/", suffix="*") or f"entity://{entity}/*"
    if skill == "compare-formulas" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") or f"entity://{entity_name}/*"
    if skill == "find-case-reference":
        return _pick_first_matching_path(evidence_paths, prefixes=("caseqa://",))
    if skill == "search-source-text":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
    if skill == "read-formula-origin" and symptom_name:
        return _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
    return ""


def _build_skill_action(
    *,
    planner_skills: dict[str, RuntimeSkill],
    skill_name: str,
    query: str,
    reason: str,
    path: str = "",
    scope_paths: list[str] | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    skill_meta = planner_skills.get(skill_name)
    tool_name = skill_meta.primary_tool if skill_meta is not None else ""
    action: dict[str, Any] = {
        "skill": skill_name,
        "tool": tool_name,
        "query": query,
        "top_k": top_k,
        "reason": reason,
    }
    if path:
        action["path"] = path
    if scope_paths:
        action["scope_paths"] = scope_paths
    return action


def _plan_followup_actions(*, planner_skills: dict[str, RuntimeSkill], query: str, payload: dict[str, Any], evidence_paths: list[str], gaps: list[str], max_actions: int, executed_actions: set[str]) -> list[dict[str, Any]]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    symptom_name = str(strategy.get("symptom_name", "")).strip()
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    actions: list[dict[str, Any]] = []

    def add_action(candidate: dict[str, Any]) -> None:
        if len(actions) >= max_actions:
            return
        if _action_key(candidate) in executed_actions:
            return
        actions.append(candidate)

    if "composition" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="read-formula-composition",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="使用药材") or f"entity://{entity_name}/使用药材",
            query=query,
            top_k=6,
            reason="补充方剂组成证据",
        ))
    if "efficacy" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="compare-formulas",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="功效") or f"entity://{entity_name}/功效",
            query=query,
            top_k=6,
            reason="补充功效证据",
        ))
    if "indication" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="compare-formulas",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="治疗证候") or f"entity://{entity_name}/治疗证候",
            query=query,
            top_k=6,
            reason="补充主治证候证据",
        ))
    if "syndrome_formula" in gaps:
        target_path = ""
        if symptom_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
        elif entity_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="推荐方剂") or f"entity://{entity_name}/推荐方剂"
        if target_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="compare-formulas",
                path=target_path,
                query=query,
                top_k=6,
                reason="补充证候到方剂映射",
            ))
    if "comparison" in gaps and compare_entities:
        for entity in compare_entities[:2]:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="compare-formulas",
                path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity}/", suffix="*") or f"entity://{entity}/*",
                query=query,
                top_k=6,
                reason=f"补充比较对象 {entity} 的证据",
            ))
        if len(actions) < max_actions:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="search-source-text",
                query=f"{query} 古籍 教材 出处",
                scope_paths=[path for path in evidence_paths if path.startswith(("qa://", "book://"))],
                top_k=4,
                reason="补充比较问题的文献出处",
            ))
    if "origin" in gaps:
        graph_source_books = _top_graph_source_books(factual_evidence=payload.get("_planner_factual_evidence", []))
        entity_origin_path = _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") if entity_name else ""
        if entity_name and not graph_source_books:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="read-formula-origin",
                path=entity_origin_path or f"entity://{entity_name}/*",
                query=f"{entity_name} 出处 原文",
                top_k=6,
                reason="先从实体级证据锁定来源书名与篇章",
            ))
        elif graph_source_books:
            for source_book in graph_source_books[:2]:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=f"book://{source_book}/*",
                    query=f"{entity_name or query} 出处 原文",
                    top_k=4,
                    reason=f"根据实体证据已定位来源书目，继续追 {source_book} 的原文片段",
                ))
        else:
            origin_path = _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
            if origin_path:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=origin_path,
                    query=f"{query} 出处 原文",
                    top_k=4,
                    reason="补充出处或原文证据",
                ))
            else:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="search-source-text",
                    query=f"{query} 出处 古籍 原文 教材",
                    scope_paths=[path for path in evidence_paths if path.startswith(("qa://", "book://"))],
                    top_k=4,
                    reason="补充出处或原文证据",
                ))
    if "case_reference" in gaps:
        case_path = _pick_first_matching_path(evidence_paths, prefixes=("caseqa://",))
        if case_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="find-case-reference",
                path=case_path,
                query=query,
                top_k=3,
                reason="补充相似案例参考",
            ))
        else:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="find-case-reference",
                query=query,
                scope_paths=["caseqa://query/similar"],
                top_k=3,
                reason="补充相似案例参考",
            ))
    return actions[:max_actions]


def _pick_existing_path(paths: list[str], *, prefix: str, suffix: str) -> str:
    for path in paths:
        if path.startswith(prefix) and (suffix == "*" or path.endswith(suffix) or path.endswith("/*")):
            return path
    return ""


def _pick_first_matching_path(paths: list[str], *, prefixes: tuple[str, ...]) -> str:
    for path in paths:
        if path.startswith(prefixes):
            return path
    return ""


def _action_key(action: dict[str, Any]) -> str:
    scope = action.get("scope_paths", [])
    scope_text = "|".join(str(item).strip() for item in scope) if isinstance(scope, list) else ""
    return "::".join([str(action.get("skill", "")).strip(), str(action.get("tool", "")).strip(), str(action.get("path", "")).strip(), str(action.get("query", "")).strip(), scope_text])


def _top_graph_source_books(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    books: list[str] = []
    seen = set()
    for item in factual_evidence:
        if str(item.get("source_type", "")).strip() != "graph":
            continue
        source_book = str(item.get("source_book", "")).strip()
        if not source_book or source_book in seen:
            continue
        seen.add(source_book)
        books.append(source_book)
    return books


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

