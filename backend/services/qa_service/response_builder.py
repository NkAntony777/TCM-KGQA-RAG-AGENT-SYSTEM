from __future__ import annotations

from typing import Any

from services.qa_service.answer_generator import _generate_grounded_answer
from services.qa_service.evidence import (
    _build_book_citations,
    _build_citations,
    _case_reference_from_payload,
    _coverage_summary,
    _factual_evidence_from_payload,
    _split_factual_evidence,
)
from services.qa_service.evidence_selector import select_evidence_for_answer
from services.qa_service.models import AnswerMode, QAServiceSettings
from services.qa_service.prompts import _ensure_multiple_choice_answer_format
from services.qa_service.helpers import _route_from_payload


async def _build_response(
    *,
    answer_generator,
    settings: QAServiceSettings,
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
    full_evidence_mode: bool = False,
) -> dict[str, Any]:
    factual = factual_evidence or _factual_evidence_from_payload(payload)
    cases = case_references or _case_reference_from_payload(payload)
    evidence_groups = _split_factual_evidence(factual_evidence=factual)
    book_citations = _build_book_citations(factual_evidence=factual)
    citations = _build_citations(
        factual_evidence=factual,
        case_references=cases,
        book_citations=book_citations,
        limit=settings.max_citations,
    )
    selected_evidence = select_evidence_for_answer(
        query=query,
        payload=payload,
        mode=mode,
        factual_evidence=factual,
        case_references=cases,
        evidence_paths=evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []) if isinstance(payload.get("evidence_paths", []), list) else [],
        full_evidence_mode=full_evidence_mode,
    )
    answer, generation_backend, generation_notes, generation_diagnostics = await _generate_grounded_answer(
        answer_generator=answer_generator,
        settings=settings,
        query=query,
        payload=payload,
        mode=mode,
        factual_evidence=factual,
        evidence_groups=evidence_groups,
        case_references=cases,
        citations=citations,
        notes=notes or [],
        book_citations=book_citations,
        deep_trace=deep_trace or [],
        selected_evidence=selected_evidence,
        full_evidence_mode=full_evidence_mode,
    )
    answer = _ensure_multiple_choice_answer_format(query, answer)
    selected_factual = factual if full_evidence_mode else factual[: settings.max_factual_evidence]
    selected_cases = cases if full_evidence_mode else cases[: settings.max_case_references]
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
        "answer_policy": (payload.get("retrieval_strategy", {}) or {}).get("answer_policy", ""),
        "route": _route_from_payload(payload),
        "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
        "factual_evidence": selected_factual,
        "factual_evidence_groups": {
            "structured": evidence_groups["structured"][: settings.max_factual_evidence],
            "documentary": evidence_groups["documentary"][: settings.max_factual_evidence],
            "other": evidence_groups["other"][: settings.max_factual_evidence],
        },
        "case_references": selected_cases,
        "citations": citations,
        "book_citations": book_citations,
        "selected_evidence_cards": selected_evidence["selected_cards"],
        "evidence_selection": {
            "required_facets": selected_evidence["required_facets"],
            "covered_facets": selected_evidence["covered_facets"],
            "missing_facets": selected_evidence["missing_facets"],
            "selection_notes": selected_evidence["selection_notes"],
        },
        "planner_steps": planner_steps or [],
        "deep_trace": deep_trace or [],
        "evidence_bundle": {
            "evidence_paths": evidence_paths if evidence_paths is not None else payload.get("evidence_paths", []),
            "factual_evidence": selected_factual,
            "factual_evidence_groups": {
                "structured": evidence_groups["structured"][: settings.max_factual_evidence],
                "documentary": evidence_groups["documentary"][: settings.max_factual_evidence],
                "other": evidence_groups["other"][: settings.max_factual_evidence],
            },
            "case_references": selected_cases,
            "book_citations": book_citations,
            "selected_evidence_cards": selected_evidence["selected_cards"],
            "evidence_selection": {
                "required_facets": selected_evidence["required_facets"],
                "covered_facets": selected_evidence["covered_facets"],
                "missing_facets": selected_evidence["missing_facets"],
                "selection_notes": selected_evidence["selection_notes"],
            },
            "coverage": coverage,
            "generation_diagnostics": generation_diagnostics,
            "planner_steps": planner_steps or [],
            "deep_trace": deep_trace or [],
        },
        "service_trace_ids": payload.get("service_trace_ids", {}),
        "service_backends": payload.get("service_backends", {}),
        "generation_backend": generation_backend,
        "generation_diagnostics": generation_diagnostics,
        "tool_trace": tool_trace or [],
        "notes": list(notes or []) + list(generation_notes),
    }


def _build_live_evidence_bundle(
    *,
    settings: QAServiceSettings,
    query: str,
    payload: dict[str, Any],
    evidence_paths: list[str],
    factual_evidence: list[dict[str, Any]],
    case_references: list[dict[str, Any]],
    coverage_summary: dict[str, Any] | None,
    planner_steps: list[dict[str, str]],
    deep_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_factual = factual_evidence[: settings.max_factual_evidence]
    selected_cases = case_references[: settings.max_case_references]
    evidence_groups = _split_factual_evidence(factual_evidence=factual_evidence)
    return {
        "evidence_paths": evidence_paths,
        "factual_evidence": selected_factual,
        "factual_evidence_groups": {
            "structured": evidence_groups["structured"][: settings.max_factual_evidence],
            "documentary": evidence_groups["documentary"][: settings.max_factual_evidence],
            "other": evidence_groups["other"][: settings.max_factual_evidence],
        },
        "case_references": selected_cases,
        "book_citations": _build_book_citations(factual_evidence=factual_evidence),
        "coverage": coverage_summary
        or _coverage_summary(
            query=query,
            payload=payload,
            evidence_paths=evidence_paths,
            factual_evidence=factual_evidence,
            case_references=case_references,
        ),
        "generation_diagnostics": None,
        "planner_steps": planner_steps,
        "deep_trace": deep_trace,
    }
