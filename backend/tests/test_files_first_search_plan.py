from __future__ import annotations

import re

from services.retrieval_service import files_first_search_plan


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


def test_build_search_plan_uses_context_entities_and_expanded_query() -> None:
    plan = files_first_search_plan.build_search_plan(
        query="小柴胡汤有啥用",
        tokenizer=FakeTokenizer(),
        query_context={
            "question_type": "property",
            "primary_entity": "小柴胡汤",
            "expanded_query": "小柴胡汤 功效 和解少阳",
        },
    )

    assert plan.flags["property_query"] is True
    assert plan.focus_entities[0] == "小柴胡汤"
    assert "功效" in plan.ranking_terms
    assert "和解少阳" in plan.descriptive_clauses
    assert plan.direct_terms[0] == "小柴胡汤"
    assert len(plan.direct_terms) == len(set(plan.direct_terms))
    assert plan.match_queries


def test_build_search_plan_suppresses_direct_terms_for_weak_anchor() -> None:
    plan = files_first_search_plan.build_search_plan(
        query="小柴胡汤功效是什么",
        tokenizer=FakeTokenizer(),
        query_context={
            "primary_entity": "小柴胡汤",
            "weak_anchor": True,
        },
    )

    assert plan.weak_anchor is True
    assert plan.direct_terms == ["小柴胡汤"]


def test_select_direct_seed_books_prefers_explicit_books() -> None:
    plan = files_first_search_plan.build_search_plan(
        query="伤寒论 小柴胡汤 功效",
        tokenizer=FakeTokenizer(),
        query_context={
            "primary_entity": "小柴胡汤",
            "source_book_hints": ["伤寒论"],
        },
    )

    target_books = files_first_search_plan.select_direct_seed_books(
        query="伤寒论 小柴胡汤 功效",
        plan=plan,
        candidate_books=["金匮要略", "本草纲目"],
    )

    assert target_books == ["伤寒论"]


def test_select_direct_seed_books_keeps_strong_anchor_global() -> None:
    plan = files_first_search_plan.build_search_plan(
        query="小柴胡汤功效是什么",
        tokenizer=FakeTokenizer(),
        query_context={"primary_entity": "小柴胡汤"},
    )

    target_books = files_first_search_plan.select_direct_seed_books(
        query="小柴胡汤功效是什么",
        plan=plan,
        candidate_books=["伤寒论", "金匮要略"],
    )

    assert target_books == []


def test_select_clause_seed_books_uses_candidates_without_explicit_books() -> None:
    plan = files_first_search_plan.build_search_plan(
        query="和解少阳的条文",
        tokenizer=FakeTokenizer(),
        query_context=None,
    )

    assert files_first_search_plan.select_clause_seed_books(plan=plan, candidate_books=["伤寒论", "金匮要略"]) == ["伤寒论", "金匮要略"]
