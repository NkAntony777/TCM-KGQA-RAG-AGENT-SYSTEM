from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from services.retrieval_service.section_summary_cache import SectionSummaryCache


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = BACKEND_ROOT / ".test_tmp"


def _test_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    return TEST_TMP_ROOT / f"{uuid4().hex}_{name}"


def test_section_summary_cache_round_trip() -> None:
    cache_path = _test_path("section_summary_cache.sqlite")
    cache = SectionSummaryCache(cache_path)

    cache.set(
        "book::0001",
        {
            "section_summary": "调和营卫。",
            "topic_tags": ["营卫"],
            "entity_tags": ["桂枝汤"],
            "representative_passages": ["太阳中风，阳浮而阴弱。"],
        },
    )

    assert cache.count() == 1
    assert cache.has("book::0001")
    assert cache.get("book::0001") == {
        "section_summary": "调和营卫。",
        "topic_tags": ["营卫"],
        "entity_tags": ["桂枝汤"],
        "representative_passages": ["太阳中风，阳浮而阴弱。"],
    }


def test_section_summary_cache_imports_legacy_json() -> None:
    legacy_path = _test_path("section_summary_cache.json")
    legacy_path.write_text(
        json.dumps(
            {
                "book::0002": {
                    "section_summary": "辨少阳病。",
                    "topic_tags": ["少阳"],
                    "entity_tags": ["小柴胡汤"],
                    "representative_passages": ["往来寒热，胸胁苦满。"],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cache = SectionSummaryCache(legacy_path.with_suffix(".sqlite"))

    assert cache.count() == 1
    assert cache.get("book::0002") == {
        "section_summary": "辨少阳病。",
        "topic_tags": ["少阳"],
        "entity_tags": ["小柴胡汤"],
        "representative_passages": ["往来寒热，胸胁苦满。"],
    }
