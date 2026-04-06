from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from eval.runners.run_eval import DEFAULT_DATASET, evaluate_router, load_dataset
from router.query_router import decide_route
from router.retrieval_strategy import derive_retrieval_strategy
from tools.tcm_route_tool import TCMRouteSearchTool


class QueryRouterDecisionTests(unittest.TestCase):
    def test_graph_route_keywords(self) -> None:
        decision = decide_route("逍遥散的证候和配伍关系是什么")
        self.assertEqual(decision.route, "graph")

    def test_retrieval_route_keywords(self) -> None:
        decision = decide_route("逍遥散的古籍出处和原文解释是什么")
        self.assertEqual(decision.route, "retrieval")

    def test_hybrid_route_keywords(self) -> None:
        decision = decide_route("逍遥散的证候出处与古籍原文是什么")
        self.assertEqual(decision.route, "hybrid")

    def test_dataset_accuracy_meets_gate(self) -> None:
        dataset = load_dataset(DEFAULT_DATASET)
        summary = evaluate_router(dataset)
        self.assertGreaterEqual(summary["accuracy"], 0.8)
        self.assertEqual(summary["total"], 20)

    def test_composition_query_derives_predicate_scoped_strategy(self) -> None:
        strategy = derive_retrieval_strategy("六味地黄丸的组成是什么", requested_top_k=12, route_hint="graph")
        self.assertEqual(strategy.intent, "formula_composition")
        self.assertEqual(strategy.graph_query_kind, "entity")
        self.assertEqual(strategy.entity_name, "六味地黄丸")
        self.assertEqual(strategy.predicate_allowlist, ["使用药材"])
        self.assertIn("entity://六味地黄丸/使用药材", strategy.evidence_paths)

    def test_origin_query_derives_hybrid_strategy(self) -> None:
        strategy = derive_retrieval_strategy("逍遥散出自哪本古籍", requested_top_k=12, route_hint="retrieval")
        self.assertEqual(strategy.intent, "formula_origin")
        self.assertEqual(strategy.preferred_route, "hybrid")
        self.assertEqual(strategy.predicate_allowlist, [])
        self.assertIn("classic_docs", strategy.sources)
        self.assertIn("qa_vector_db", strategy.sources)
        self.assertIn("entity://逍遥散/*", strategy.evidence_paths)
        self.assertIn("qa://逍遥散/similar", strategy.evidence_paths)

    def test_case_style_query_enables_case_qa_source(self) -> None:
        query = "基本信息: 年龄:47 性别:女 主诉:胁肋胀痛 失眠 现病史:口苦 体格检查:舌淡红 脉弦"
        strategy = derive_retrieval_strategy(query, requested_top_k=12, route_hint="hybrid")
        self.assertIn("qa_case_vector_db", strategy.sources)
        self.assertIn("caseqa://胁肋胀痛/similar", strategy.evidence_paths)

    def test_path_query_with_source_request_derives_hybrid_strategy(self) -> None:
        query = "从肝郁脾虚到逍遥散的链路是什么，并给一个古籍出处佐证。"
        strategy = derive_retrieval_strategy(query, requested_top_k=12, route_hint="hybrid")
        self.assertEqual(strategy.intent, "graph_path")
        self.assertEqual(strategy.preferred_route, "hybrid")
        self.assertIn("classic_docs", strategy.sources)
        self.assertIn("qa://肝郁脾虚->逍遥散/similar", strategy.evidence_paths)

    def test_symptom_rich_open_query_enables_case_qa_source(self) -> None:
        query = "如果见胁肋胀痛、食少乏力、口苦、失眠，常见什么证候，可参考什么方剂？"
        strategy = derive_retrieval_strategy(query, requested_top_k=12, route_hint="graph")
        self.assertIn("qa_case_vector_db", strategy.sources)


class RouteToolDegradationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = TCMRouteSearchTool()

    def test_graph_failure_falls_back_to_retrieval(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_syndrome_chain",
                return_value={"code": 20001, "message": "KG_ENTITY_NOT_FOUND", "trace_id": "g1"},
            ),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={"code": 20001, "message": "KG_ENTITY_NOT_FOUND", "trace_id": "g2"},
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 0, "message": "ok", "trace_id": "r1", "backend": "retrieval-service"},
            ),
        ):
            payload = json.loads(self.tool._run("逍遥散的证候关系", top_k=3))

        self.assertEqual(payload["route"], "graph")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["final_route"], "retrieval")
        self.assertEqual(payload["executed_routes"], ["graph", "retrieval"])
        self.assertEqual(payload["service_trace_ids"]["retrieval"], "r1")

    def test_graph_empty_result_falls_back_to_retrieval(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={"code": 0, "message": "ok", "trace_id": "g1", "backend": "graph-service", "data": {"entity": {"canonical_name": "逍遥散"}, "relations": []}},
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 0, "message": "ok", "trace_id": "r1", "backend": "retrieval-service", "data": {"chunks": [{"text": "逍遥散用于肝郁脾虚证。", "score": 0.9}]}},
            ),
        ):
            payload = json.loads(self.tool._run("逍遥散的功效是什么", top_k=3))

        self.assertEqual(payload["route"], "graph")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["final_route"], "retrieval")
        self.assertEqual(payload["executed_routes"], ["graph", "retrieval"])
        self.assertEqual(payload["degradation"][0]["reason"], "graph_primary_empty")

    def test_retrieval_failure_falls_back_to_graph(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 30001, "message": "RETRIEVE_EMPTY", "trace_id": "r1"},
            ),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={
                    "code": 0,
                    "message": "ok",
                    "trace_id": "g1",
                    "backend": "graph-service",
                    "data": {"relations": [{"predicate": "治疗证候", "target": "肝郁脾虚"}]},
                },
            ),
        ):
            payload = json.loads(self.tool._run("逍遥散的古籍出处和原文", top_k=3))

        self.assertEqual(payload["classifier_route"], "retrieval")
        self.assertEqual(payload["route"], "hybrid")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["final_route"], "graph")
        self.assertEqual(payload["executed_routes"], ["graph", "retrieval"])
        self.assertEqual(payload["service_trace_ids"]["graph"], "g1")

    def test_origin_query_with_entity_forces_hybrid_execution(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={"code": 0, "message": "ok", "trace_id": "g1", "backend": "graph-service", "data": {"entity": {"canonical_name": "六味地黄丸"}, "relations": []}},
            ) as graph_mock,
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 0, "message": "ok", "trace_id": "r1", "backend": "retrieval-service", "data": {"chunks": [{"text": "六味地黄丸出自《小儿药证直诀》。", "score": 0.9}]}},
            ) as retrieval_mock,
        ):
            payload = json.loads(self.tool._run("六味地黄丸出自哪本书？请给出处原文。", top_k=6))

        self.assertEqual(payload["classifier_route"], "retrieval")
        self.assertEqual(payload["route"], "hybrid")
        self.assertEqual(payload["final_route"], "retrieval")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["executed_routes"], ["graph", "retrieval"])
        graph_mock.assert_called()
        retrieval_mock.assert_called()

    def test_double_failure_marks_evidence_insufficient(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_syndrome_chain",
                return_value={"code": 20001, "message": "KG_ENTITY_NOT_FOUND", "trace_id": "g1"},
            ),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={"code": 20001, "message": "KG_ENTITY_NOT_FOUND", "trace_id": "g2"},
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 30001, "message": "RETRIEVE_EMPTY", "trace_id": "r1"},
            ),
        ):
            payload = json.loads(self.tool._run("这是什么", top_k=3))

        self.assertEqual(payload["status"], "evidence_insufficient")
        self.assertIn(payload["route"], {"retrieval", "hybrid"})

    def test_graph_path_pattern_prefers_path_query(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_path_query",
                return_value={
                    "code": 0,
                    "message": "ok",
                    "trace_id": "p1",
                    "backend": "graph-service",
                    "data": {
                        "paths": [
                            {
                                "nodes": ["胁肋胀痛", "肝郁脾虚", "逍遥散"],
                                "edges": ["常见症状(逆向)", "推荐方剂"],
                                "score": 0.6,
                                "sources": [{"source_book": "医宗金鉴", "source_chapter": "杂病心法"}],
                            }
                        ],
                        "total": 1,
                    },
                },
            ),
        ):
            payload = json.loads(self.tool._run("胁肋胀痛到逍遥散的路径是什么", top_k=3))

        self.assertEqual(payload["route"], "graph")
        self.assertEqual(payload["final_route"], "graph")
        self.assertEqual(payload["graph_result"]["trace_id"], "p1")
        self.assertEqual(payload["graph_result"]["data"]["paths"][0]["nodes"][-1], "逍遥散")

    def test_composition_query_uses_filtered_entity_lookup_strategy(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_entity_lookup",
                return_value={"code": 0, "message": "ok", "trace_id": "g1", "backend": "graph-service", "data": {"relations": []}},
            ) as entity_mock,
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 0, "message": "ok", "trace_id": "r1", "backend": "retrieval-service", "data": {"chunks": []}},
            ),
        ):
            payload = json.loads(self.tool._run("逍遥散的组成是什么", top_k=12))

        self.assertEqual(payload["route"], "graph")
        self.assertEqual(payload["retrieval_strategy"]["intent"], "formula_composition")
        self.assertEqual(payload["retrieval_strategy"]["predicate_allowlist"], ["使用药材"])
        self.assertEqual(payload["query_analysis"]["dominant_intent"], "formula_composition")
        self.assertIn("entity://逍遥散/使用药材", payload["evidence_paths"])
        entity_mock.assert_called()
        _, kwargs = entity_mock.call_args
        self.assertEqual(kwargs["name"], "逍遥散")
        self.assertEqual(kwargs["predicate_allowlist"], ["使用药材"])

    def test_case_style_query_calls_case_qa_branch(self) -> None:
        query = "基本信息: 年龄:47 性别:女 主诉:胁肋胀痛 失眠 现病史:口苦 体格检查:舌淡红 脉弦"
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_graph_syndrome_chain",
                return_value={"code": 0, "message": "ok", "trace_id": "g1", "backend": "graph-service", "data": {"syndromes": []}},
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 0, "message": "ok", "trace_id": "r1", "backend": "retrieval-service", "data": {"chunks": []}},
            ),
            patch(
                "tools.tcm_route_tool.call_retrieval_case_qa",
                return_value={
                    "code": 0,
                    "message": "ok",
                    "trace_id": "c1",
                    "backend": "retrieval-service",
                    "data": {
                        "chunks": [
                            {
                                "collection": "tcm_shard_0",
                                "embedding_id": "case-1",
                                "document": "基本信息: 年龄:47 性别:女 主诉:胁肋胀痛",
                                "answer": "诊断: 肝郁脾虚证 治疗方案: 方剂: 逍遥散。",
                                "score": 0.88,
                                "rerank_score": 1.01,
                            }
                        ]
                    },
                },
            ) as case_mock,
        ):
            payload = json.loads(self.tool._run(query, top_k=6))

        self.assertIn("qa_case_vector_db", payload["retrieval_strategy"]["sources"])
        self.assertIn("case_qa", payload["executed_routes"])
        self.assertEqual(payload["service_trace_ids"]["case_qa"], "c1")
        self.assertEqual(payload["case_qa_result"]["data"]["chunks"][0]["collection"], "tcm_shard_0")
        case_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
