from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.retrieval_service.chroma_case_store import (
    _build_fts5_match_expression,
    _load_hnsw_metadata,
)


def test_chroma_hnsw_metadata_prefers_json(tmp_path: Path) -> None:
    (tmp_path / "index_metadata.json").write_text(
        json.dumps({"label_to_id": {"1": "abc"}, "total_elements_added": 1}),
        encoding="utf-8",
    )

    payload = _load_hnsw_metadata(tmp_path)

    assert payload == {"label_to_id": {"1": "abc"}, "total_elements_added": 1}


def test_chroma_runtime_does_not_load_legacy_pickle(tmp_path: Path) -> None:
    (tmp_path / "index_metadata.pickle").write_bytes(b"legacy pickle payload")

    with pytest.raises(FileNotFoundError, match="hnsw_metadata_json_missing"):
        _load_hnsw_metadata(tmp_path)


def test_chroma_fts5_terms_are_quoted_and_sanitized() -> None:
    expression = _build_fts5_match_expression(['方剂" OR *', "主诉\x00发热"])

    assert expression == '"方剂 OR" OR "主诉 发热"'
