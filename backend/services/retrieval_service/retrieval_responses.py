from __future__ import annotations

from typing import Any


def empty_search_response(
    *,
    retrieval_mode: str,
    candidate_k: int,
    warnings: list[str],
    backend: str = "supermew_hybrid",
) -> dict[str, Any]:
    return {
        "backend": backend,
        "retrieval_mode": retrieval_mode,
        "rerank_applied": False,
        "candidate_k": candidate_k,
        "chunks": [],
        "total": 0,
        "warnings": warnings,
    }
