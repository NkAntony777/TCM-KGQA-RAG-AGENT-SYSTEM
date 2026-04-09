from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AnswerMode = Literal["quick", "deep"]
PlannerGap = Literal[
    "composition",
    "efficacy",
    "indication",
    "syndrome_formula",
    "origin",
    "source_trace",
    "path_reasoning",
    "comparison",
    "case_reference",
]

ALLOWED_PLANNER_GAPS: tuple[PlannerGap, ...] = (
    "composition",
    "efficacy",
    "indication",
    "syndrome_formula",
    "origin",
    "source_trace",
    "path_reasoning",
    "comparison",
    "case_reference",
)

@dataclass(frozen=True)
class QAServiceSettings:
    default_top_k: int = 12
    max_factual_evidence: int = 6
    max_case_references: int = 3
    max_citations: int = 6
    max_quick_prompt_evidence: int = 4
    max_quick_followup_actions: int = 1
    max_deep_prompt_evidence: int = 6
    max_deep_rounds: int = 4
    max_actions_per_round: int = 2
    deep_read_top_k: int = 6
    max_trace_evidence_per_step: int = 3

@dataclass(frozen=True)
class RouteContext:
    payload: dict[str, Any]
    route_meta: dict[str, Any]
    route_event: dict[str, Any]
    factual_evidence: list[dict[str, Any]]
    case_references: list[dict[str, Any]]

