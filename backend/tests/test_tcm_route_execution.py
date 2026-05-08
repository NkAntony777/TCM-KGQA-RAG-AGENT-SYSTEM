from __future__ import annotations

from types import SimpleNamespace

from tools.tcm_route_execution import RouteServiceCalls, execute_route_plan


class _Model(SimpleNamespace):
    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def _strategy(**overrides: object) -> _Model:
    values: dict[str, object] = {
        "intent": "formula_origin",
        "preferred_route": "hybrid",
        "graph_query_kind": "entity",
        "graph_query_text": "六味地黄丸",
        "entity_name": "六味地黄丸",
        "symptom_name": "",
        "path_start": "",
        "path_end": "",
        "compare_entities": [],
        "entity_aliases": ["地黄丸", "六味丸"],
        "preferred_books": [],
        "predicate_allowlist": [],
        "predicate_blocklist": [],
        "graph_candidate_k": 18,
        "graph_final_k": 6,
        "vector_candidate_k": 18,
        "sources": ["classic_docs", "qa_structured_index"],
        "evidence_paths": ["entity://六味地黄丸/*", "qa://六味地黄丸/similar"],
        "answer_policy": "",
        "notes": [],
    }
    values.update(overrides)
    return _Model(**values)


def _calls(
    *,
    graph_result: dict[str, object],
    retrieval_result: dict[str, object],
    path_result: dict[str, object] | None = None,
    syndrome_result: dict[str, object] | None = None,
    case_qa_result: dict[str, object] | None = None,
) -> tuple[RouteServiceCalls, dict[str, object]]:
    captured: dict[str, object] = {}

    def graph_entity_lookup(**kwargs: object) -> dict[str, object]:
        captured["graph_entity_lookup"] = kwargs
        return graph_result

    def graph_path_query(**kwargs: object) -> dict[str, object]:
        captured["graph_path_query"] = kwargs
        return path_result or {"code": 30001, "message": "unused"}

    def retrieval_case_qa(**kwargs: object) -> dict[str, object]:
        captured["retrieval_case_qa"] = kwargs
        return case_qa_result or {"code": 30001, "message": "unused"}

    def graph_syndrome_chain(**kwargs: object) -> dict[str, object]:
        captured["graph_syndrome_chain"] = kwargs
        return syndrome_result or {"code": 30001, "message": "unused"}

    def retrieval_hybrid(**kwargs: object) -> dict[str, object]:
        captured["retrieval_hybrid"] = kwargs
        return retrieval_result

    return (
        RouteServiceCalls(
            graph_entity_lookup=graph_entity_lookup,
            graph_path_query=graph_path_query,
            retrieval_case_qa=retrieval_case_qa,
            graph_syndrome_chain=graph_syndrome_chain,
            retrieval_hybrid=retrieval_hybrid,
        ),
        captured,
    )


def test_execute_hybrid_uses_injected_calls_and_files_first_scope() -> None:
    calls, captured = _calls(
        graph_result={"code": 0, "trace_id": "g1", "backend": "graph", "data": {"relations": []}},
        retrieval_result={"code": 0, "trace_id": "r1", "backend": "retrieval", "data": {"chunks": [{"text": "出处"}]}},
    )

    output = execute_route_plan(
        query="六味地黄丸出自哪本书？",
        top_k=6,
        analysis=_Model(dominant_intent="formula_origin"),
        decision=_Model(route="hybrid"),
        strategy=_strategy(),
        execution_route="hybrid",
        route_reason="origin_entity_forced_hybrid",
        health={"execution_mode": "local_fallback"},
        calls=calls,
    )

    assert output["status"] == "degraded"
    assert output["final_route"] == "retrieval"
    assert output["executed_routes"] == ["graph", "retrieval"]
    assert output["service_trace_ids"] == {"graph": "g1", "retrieval": "r1", "case_qa": None}
    assert captured["graph_entity_lookup"] == {
        "name": "六味地黄丸",
        "top_k": 6,
        "predicate_allowlist": [],
        "predicate_blocklist": [],
    }
    assert captured["retrieval_hybrid"]["query"] == "六味地黄丸出自哪本书？ 六味丸"
    assert captured["retrieval_hybrid"]["search_mode"] == "files_first"
    assert captured["retrieval_hybrid"]["allowed_file_path_prefixes"] == ["classic://", "sample://"]


def test_execute_retrieval_failure_falls_back_to_graph_evidence() -> None:
    calls, captured = _calls(
        graph_result={"code": 0, "trace_id": "g1", "backend": "graph", "data": {"relations": [{"target": "肝郁脾虚"}]}},
        retrieval_result={"code": 30001, "trace_id": "r1", "message": "RETRIEVE_EMPTY"},
    )

    output = execute_route_plan(
        query="逍遥散古籍出处",
        top_k=4,
        analysis=_Model(dominant_intent="source"),
        decision=_Model(route="retrieval"),
        strategy=_strategy(graph_query_text="逍遥散", entity_aliases=[]),
        execution_route="retrieval",
        route_reason="retrieval_keywords",
        health={},
        calls=calls,
    )

    assert output["status"] == "degraded"
    assert output["final_route"] == "graph"
    assert output["executed_routes"] == ["retrieval", "graph"]
    assert output["degradation"] == [{"from": "retrieval", "to": "graph", "reason": "retrieval_primary_failed"}]
    assert captured["graph_entity_lookup"]["name"] == "逍遥散"


def test_execute_graph_failure_falls_back_to_retrieval() -> None:
    calls, captured = _calls(
        graph_result={"code": 20001, "trace_id": "g2", "message": "KG_ENTITY_NOT_FOUND"},
        syndrome_result={"code": 20001, "trace_id": "g1", "message": "KG_ENTITY_NOT_FOUND"},
        retrieval_result={"code": 0, "trace_id": "r1", "backend": "retrieval", "data": {"chunks": [{"text": "证据"}]}},
    )

    output = execute_route_plan(
        query="逍遥散的证候关系",
        top_k=3,
        analysis=_Model(dominant_intent="formula_syndrome"),
        decision=_Model(route="graph"),
        strategy=_strategy(graph_query_kind="none", graph_query_text="逍遥散", entity_aliases=[], graph_final_k=3),
        execution_route="graph",
        route_reason="graph_keywords",
        health={},
        calls=calls,
    )

    assert output["status"] == "degraded"
    assert output["final_route"] == "retrieval"
    assert output["executed_routes"] == ["graph", "retrieval"]
    assert output["degradation"] == [{"from": "graph", "to": "retrieval", "reason": "graph_primary_failed"}]
    assert captured["graph_syndrome_chain"] == {"symptom": "逍遥散的证候关系", "top_k": 3}


def test_execute_path_query_uses_graph_path_call() -> None:
    calls, captured = _calls(
        graph_result={"code": 30001, "message": "unused"},
        path_result={"code": 0, "trace_id": "p1", "backend": "graph", "data": {"paths": [{"nodes": ["胁肋胀痛", "逍遥散"]}]}},
        retrieval_result={"code": 30001, "trace_id": "r1", "message": "unused"},
    )

    output = execute_route_plan(
        query="胁肋胀痛到逍遥散的路径是什么",
        top_k=8,
        analysis=_Model(dominant_intent="graph_path"),
        decision=_Model(route="graph"),
        strategy=_strategy(
            graph_query_kind="path",
            path_start="胁肋胀痛",
            path_end="逍遥散",
            graph_final_k=8,
            entity_aliases=[],
            sources=["graph_sqlite"],
        ),
        execution_route="graph",
        route_reason="path_query",
        health={},
        calls=calls,
    )

    assert output["final_route"] == "graph"
    assert output["graph_result"]["trace_id"] == "p1"
    assert captured["graph_path_query"] == {"start": "胁肋胀痛", "end": "逍遥散", "max_hops": 3, "path_limit": 5}


def test_execute_case_style_query_runs_case_qa_branch() -> None:
    calls, captured = _calls(
        graph_result={"code": 0, "trace_id": "g1", "backend": "graph", "data": {"syndromes": [{"name": "肝郁脾虚"}]}},
        retrieval_result={"code": 0, "trace_id": "r1", "backend": "retrieval", "data": {"chunks": []}},
        case_qa_result={"code": 0, "trace_id": "c1", "backend": "retrieval", "data": {"chunks": [{"collection": "qa_structured_case"}]}},
    )

    output = execute_route_plan(
        query="基本信息: 年龄:47 性别:女 主诉:胁肋胀痛 失眠",
        top_k=6,
        analysis=_Model(dominant_intent="case_qa"),
        decision=_Model(route="graph"),
        strategy=_strategy(
            graph_query_kind="none",
            entity_aliases=[],
            sources=["graph_sqlite", "qa_case_structured_index"],
            graph_final_k=6,
            vector_candidate_k=24,
        ),
        execution_route="graph",
        route_reason="case_style",
        health={},
        calls=calls,
    )

    assert output["final_route"] == "graph"
    assert output["executed_routes"] == ["graph", "case_qa"]
    assert output["service_trace_ids"]["case_qa"] == "c1"
    assert captured["retrieval_case_qa"] == {
        "query": "基本信息: 年龄:47 性别:女 主诉:胁肋胀痛 失眠",
        "top_k": 6,
        "candidate_k": 24,
    }
