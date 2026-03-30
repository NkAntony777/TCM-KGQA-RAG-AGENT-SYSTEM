from __future__ import annotations

from typing import Any
from uuid import uuid4


def ensure_trace_id(trace_id: str | None) -> str:
    return trace_id.strip() if trace_id and trace_id.strip() else str(uuid4())


def success(data: Any, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ok",
        "data": data,
        "trace_id": ensure_trace_id(trace_id),
    }


def error(
    code: int,
    message: str,
    *,
    trace_id: str | None = None,
    data: Any | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data or {},
        "trace_id": ensure_trace_id(trace_id),
    }

