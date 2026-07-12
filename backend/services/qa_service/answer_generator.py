from __future__ import annotations

from typing import Any

from services.qa_service.exceptions import LLMAuthError, LLMGenerationError
from services.qa_service.models import AnswerMode, QAServiceSettings
from services.qa_service.prompts import (
    _build_grounded_system_prompt,
    _build_grounded_user_prompt,
    _compose_fallback_answer,
)


def _format_exception_detail(exc: Exception) -> str:
    text = str(exc).strip()
    if text:
        return f"{type(exc).__name__}: {text}"
    return f"{type(exc).__name__}: {repr(exc)}"


def _generation_timeout_plan(*, mode: AnswerMode, answer_generator) -> list[float]:
    base_timeout = float(getattr(answer_generator, "timeout_seconds", 60.0) or 60.0)
    if mode == "deep":
        return [max(base_timeout, 60.0), max(base_timeout * 2, 120.0)]
    return [max(base_timeout, 45.0), max(base_timeout * 2, 90.0)]


def _can_retry_generation(exc: Exception) -> bool:
    if isinstance(exc, LLMAuthError):
        return False
    return True


async def _try_quick_grounded_fallback(
    *,
    answer_generator,
    settings: QAServiceSettings,
    query: str,
    payload: dict[str, Any],
    factual_evidence: list[dict[str, Any]],
    evidence_groups: dict[str, list[dict[str, Any]]],
    case_references: list[dict[str, Any]],
    citations: list[str],
    notes: list[str],
    book_citations: list[str],
    deep_trace: list[dict[str, Any]],
    selected_evidence: dict[str, Any] | None,
) -> str:
    quick_system_prompt = _build_grounded_system_prompt(mode="quick")
    quick_user_prompt = _build_grounded_user_prompt(
        query=query,
        payload=payload,
        mode="quick",
        factual_evidence=factual_evidence,
        evidence_groups=evidence_groups,
        case_references=case_references,
        citations=citations,
        notes=notes,
        book_citations=book_citations,
        deep_trace=deep_trace,
        evidence_limit=settings.max_quick_prompt_evidence,
        selected_evidence=selected_evidence,
    )
    return await answer_generator.acomplete(
        system_prompt=quick_system_prompt,
        user_prompt=quick_user_prompt,
    )


async def _generate_grounded_answer(
    *,
    answer_generator,
    settings: QAServiceSettings,
    query: str,
    payload: dict[str, Any],
    mode: AnswerMode,
    factual_evidence: list[dict[str, Any]],
    evidence_groups: dict[str, list[dict[str, Any]]],
    case_references: list[dict[str, Any]],
    citations: list[str],
    notes: list[str],
    book_citations: list[str],
    deep_trace: list[dict[str, Any]],
    selected_evidence: dict[str, Any] | None = None,
    full_evidence_mode: bool = False,
) -> tuple[str, str, list[str], dict[str, Any]]:
    original_timeout = getattr(answer_generator, "timeout_seconds", None)
    attempt_notes: list[str] = []
    last_exc: Exception | None = None
    system_prompt = _build_grounded_system_prompt(mode=mode, full_evidence_mode=full_evidence_mode)
    user_prompt = _build_grounded_user_prompt(
        query=query,
        payload=payload,
        mode=mode,
        factual_evidence=factual_evidence,
        evidence_groups=evidence_groups,
        case_references=case_references,
        citations=citations,
        notes=notes,
        book_citations=book_citations,
        deep_trace=deep_trace,
        evidence_limit=settings.max_quick_prompt_evidence if mode == "quick" else settings.max_deep_prompt_evidence,
        selected_evidence=selected_evidence,
        full_evidence_mode=full_evidence_mode,
    )
    diagnostics: dict[str, Any] = {
        "mode": mode,
        "system_prompt_chars": len(system_prompt),
        "user_prompt_chars": len(user_prompt),
        "attempts": [],
        "fallback_chain": [],
    }
    try:
        timeouts = _generation_timeout_plan(mode=mode, answer_generator=answer_generator)
        for attempt_index, timeout_seconds in enumerate(timeouts, start=1):
            if original_timeout is not None and hasattr(answer_generator, "timeout_seconds"):
                setattr(answer_generator, "timeout_seconds", timeout_seconds)
            attempt_diag = {"attempt": attempt_index, "timeout_seconds": timeout_seconds, "mode": mode}
            try:
                content = await answer_generator.acomplete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                if content:
                    attempt_diag["status"] = "ok"
                    attempt_diag["answer_chars"] = len(content)
                    diagnostics["attempts"].append(attempt_diag)
                    backend = "grounded_llm" if mode == "quick" else "planner_llm"
                    diagnostics["final_backend"] = backend
                    return content, backend, attempt_notes, diagnostics
                last_exc = LLMGenerationError("llm_empty_response")
                attempt_diag["status"] = "empty"
                diagnostics["attempts"].append(attempt_diag)
                if attempt_index < len(timeouts):
                    attempt_notes.append(f"{mode}_llm_retry_{attempt_index}:empty_response")
                    continue
            except Exception as exc:
                last_exc = exc
                attempt_diag["status"] = "error"
                attempt_diag["error"] = _format_exception_detail(exc)
                diagnostics["attempts"].append(attempt_diag)
                if attempt_index < len(timeouts) and _can_retry_generation(exc):
                    attempt_notes.append(
                        f"{mode}_llm_retry_{attempt_index}:{_format_exception_detail(exc)}"
                    )
                    continue
                break
        if last_exc is None:
            last_exc = LLMGenerationError("llm_empty_response")
        raise last_exc
    except Exception as exc:
        failure_notes = [*attempt_notes, f"{mode}_llm_fallback:{_format_exception_detail(exc)}"]
        diagnostics["fallback_chain"].append(
            {
                "stage": "grounded_generation_failed",
                "error": _format_exception_detail(exc),
            }
        )
        if mode == "deep":
            quick_timeout = max(float(getattr(answer_generator, "timeout_seconds", 60.0) or 60.0), 90.0)
            if original_timeout is not None and hasattr(answer_generator, "timeout_seconds"):
                setattr(answer_generator, "timeout_seconds", quick_timeout)
            try:
                quick_content = await _try_quick_grounded_fallback(
                    answer_generator=answer_generator,
                    settings=settings,
                    query=query,
                    payload=payload,
                    factual_evidence=factual_evidence,
                    evidence_groups=evidence_groups,
                    case_references=case_references,
                    citations=citations,
                    notes=notes,
                    book_citations=book_citations,
                    deep_trace=deep_trace,
                    selected_evidence=selected_evidence,
                )
                if quick_content:
                    diagnostics["fallback_chain"].append(
                        {
                            "stage": "deep_to_quick_grounded",
                            "status": "ok",
                            "timeout_seconds": quick_timeout,
                            "answer_chars": len(quick_content),
                        }
                    )
                    return (
                        quick_content,
                        "deep_quick_grounded_fallback",
                        [*failure_notes, "deep_fallback_to_quick_grounded"],
                        diagnostics,
                    )
            except Exception as quick_exc:
                failure_notes.append(f"deep_quick_llm_fallback:{_format_exception_detail(quick_exc)}")
                diagnostics["fallback_chain"].append(
                    {
                        "stage": "deep_to_quick_grounded",
                        "status": "error",
                        "timeout_seconds": quick_timeout,
                        "error": _format_exception_detail(quick_exc),
                    }
                )
        diagnostics["fallback_chain"].append({"stage": "deterministic_fallback"})
        return (
            _compose_fallback_answer(
                query=query,
                payload=payload,
                factual_evidence=factual_evidence,
                case_references=case_references,
                citations=citations,
            ),
            "deterministic_quick_fallback" if mode == "quick" else "planner_deterministic_fallback",
            failure_notes,
            diagnostics,
        )
    finally:
        if original_timeout is not None and hasattr(answer_generator, "timeout_seconds"):
            setattr(answer_generator, "timeout_seconds", original_timeout)
