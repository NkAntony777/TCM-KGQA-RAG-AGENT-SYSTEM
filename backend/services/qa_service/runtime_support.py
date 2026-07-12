from __future__ import annotations

# Re-exports from split modules for backward compatibility.
# ruff: noqa: F401
from services.qa_service.action_executor import (
    _cache_key,
    _can_parallelize_actions,
    _execute_action,
    _execute_actions_for_round,
)
from services.qa_service.answer_generator import _generate_grounded_answer
from services.qa_service.response_builder import _build_live_evidence_bundle, _build_response
from services.qa_service.route_loader import _load_route_payload, _prepare_route_context
