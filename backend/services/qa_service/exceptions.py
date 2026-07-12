from __future__ import annotations


class QAServiceError(Exception):
    """Base exception for all QA service errors."""


class LLMGenerationError(QAServiceError):
    """LLM generation failed (API error, timeout, etc.)."""


class LLMAuthError(QAServiceError):
    """LLM API key or authentication error."""


class EvidenceInsufficientError(QAServiceError):
    """Not enough evidence to produce a grounded answer."""


class RouteDeterminationError(QAServiceError):
    """Query routing failed."""


class QueryEmptyError(QAServiceError):
    """Empty or blank query received."""


class QueryRefusedError(QAServiceError):
    """Query was refused by the medical safety guard."""
