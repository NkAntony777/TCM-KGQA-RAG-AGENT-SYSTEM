from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.retrieval_service.query_service import RetrievalQueryService


class FakeEngine(SimpleNamespace):
    pass


def test_query_service_search_hybrid_delegates_to_runtime_with_engine() -> None:
    engine = FakeEngine()
    service = RetrievalQueryService(engine)

    with patch(
        "services.retrieval_service.query_service.run_search_hybrid",
        return_value={"retrieval_mode": "files_first", "total": 1},
    ) as runtime:
        result = service.search_hybrid(
            "逍遥散 出处",
            top_k=3,
            candidate_k=9,
            enable_rerank=False,
            allowed_file_path_prefixes=["classic://"],
            search_mode="files_first",
        )

    assert result == {"retrieval_mode": "files_first", "total": 1}
    runtime.assert_called_once_with(
        engine,
        "逍遥散 出处",
        top_k=3,
        candidate_k=9,
        enable_rerank=False,
        allowed_file_path_prefixes=["classic://"],
        search_mode="files_first",
    )


def test_query_service_search_case_qa_delegates_to_runtime_with_engine() -> None:
    engine = FakeEngine()
    service = RetrievalQueryService(engine)

    with patch(
        "services.retrieval_service.case_qa_search_service.case_qa_runtime.search_case_qa",
        return_value={"retrieval_mode": "structured_case_qa", "total": 1},
    ) as runtime:
        result = service.search_case_qa("主诉: 胁肋胀痛", top_k=3, candidate_k=12)

    assert result == {"retrieval_mode": "structured_case_qa", "total": 1}
    runtime.assert_called_once_with(engine, "主诉: 胁肋胀痛", top_k=3, candidate_k=12)


def test_query_service_read_section_builds_response_from_files_first_store() -> None:
    engine = FakeEngine(
        files_first_store=SimpleNamespace(read_section=lambda *, path, top_k: {"path": path, "status": "ok", "items": [], "count": 0}),
        parent_store=SimpleNamespace(),
    )
    service = RetrievalQueryService(engine)

    with patch(
        "services.retrieval_service.section_read_service.build_section_response",
        return_value={"status": "ok", "section": {"text": "原文"}},
    ) as builder:
        result = service.read_section("chapter://小儿药证直诀/卷上", top_k=16)

    assert result == {"status": "ok", "section": {"text": "原文"}}
    builder.assert_called_once()
    assert builder.call_args.kwargs["path"] == "chapter://小儿药证直诀/卷上"
    assert builder.call_args.kwargs["payload"]["status"] == "ok"
    assert builder.call_args.kwargs["parent_store"] is engine.parent_store


def test_query_service_rewrite_methods_delegate_to_runtime_with_engine() -> None:
    engine = FakeEngine()
    service = RetrievalQueryService(engine)

    with (
        patch("services.retrieval_service.query_rewrite_service.query_rewrite_runtime._maybe_refine_files_first_query", return_value="逍遥散 出处") as maybe_refine,
        patch("services.retrieval_service.query_rewrite_service.query_rewrite_runtime.rewrite_query", return_value={"expanded_query": "expanded"}) as rewrite,
    ):
        refined = service.maybe_refine_files_first_query(
            query="逍遥散哪本书",
            search_mode="files_first",
            result={"chunks": []},
            top_k=3,
        )
        rewritten = service.rewrite_query("逍遥散哪本书", strategy="complex")

    assert refined == "逍遥散 出处"
    assert rewritten == {"expanded_query": "expanded"}
    maybe_refine.assert_called_once_with(
        engine,
        query="逍遥散哪本书",
        search_mode="files_first",
        result={"chunks": []},
        top_k=3,
    )
    rewrite.assert_called_once_with(engine, "逍遥散哪本书", "complex")


def test_query_service_composes_explicit_subservices() -> None:
    engine = FakeEngine()
    service = RetrievalQueryService(engine)
    service.case_qa = Mock()
    service.sections = Mock()
    service.rewrite = Mock()
    service.case_qa.search_case_qa.return_value = {"mode": "case"}
    service.sections.read_section.return_value = {"status": "ok"}
    service.rewrite.rewrite_query.return_value = {"expanded_query": "expanded"}

    with patch(
        "services.retrieval_service.query_service.run_search_hybrid",
        return_value={"mode": "files"},
    ) as runtime:
        assert service.search_hybrid("q", top_k=1, candidate_k=2, enable_rerank=False) == {"mode": "files"}
    assert service.search_case_qa("case", top_k=1, candidate_k=2) == {"mode": "case"}
    assert service.read_section("chapter://a/b") == {"status": "ok"}
    assert service.rewrite_query("q") == {"expanded_query": "expanded"}

    runtime.assert_called_once()
    service.case_qa.search_case_qa.assert_called_once()
    service.sections.read_section.assert_called_once()
    service.rewrite.rewrite_query.assert_called_once()
