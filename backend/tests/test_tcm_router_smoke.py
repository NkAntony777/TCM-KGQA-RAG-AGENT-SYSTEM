from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from eval.runners.run_eval import DEFAULT_DATASET, evaluate_router, load_dataset
from router.query_router import decide_route
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

    def test_retrieval_failure_falls_back_to_graph(self) -> None:
        with (
            patch("tools.tcm_route_tool.service_health_snapshot", return_value={}),
            patch(
                "tools.tcm_route_tool.call_retrieval_hybrid",
                return_value={"code": 30001, "message": "RETRIEVE_EMPTY", "trace_id": "r1"},
            ),
            patch(
                "tools.tcm_route_tool.call_graph_syndrome_chain",
                return_value={"code": 0, "message": "ok", "trace_id": "g1", "backend": "graph-service"},
            ),
        ):
            payload = json.loads(self.tool._run("逍遥散的古籍出处和原文", top_k=3))

        self.assertEqual(payload["route"], "retrieval")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["final_route"], "graph")
        self.assertEqual(payload["executed_routes"], ["retrieval", "graph"])
        self.assertEqual(payload["service_trace_ids"]["graph"], "g1")

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


if __name__ == "__main__":
    unittest.main()
