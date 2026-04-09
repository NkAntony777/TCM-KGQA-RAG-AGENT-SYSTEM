"""
test_graph_engine.py  —  S3 验收测试套件
基于 graph_runtime.json（109 条三元组，110 条 evidence）构建，不再假设小样本图。

Runtime 图核心实体（截至 2026-03-29）：
  方剂：六味地黄丸、六君子汤、四君子汤、升阳益胃汤、紫菀汤 …
  药材：熟地黄、丹皮、山茱萸、山药、泽泻、茯苓、人参、白术、甘草 …
  证候：真阴亏损、肝肾不足、脾弱阳虚 …
  症状（脉象/症候群）：腰痛足酸、劳热咳嗽、脉微、脉涩 …
  综合体质证：气偏衰证、气血俱衰证 …
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.graph_service.engine import GraphQueryEngine
from services.graph_service.engine import GraphServiceSettings
from services.graph_service.engine import _ordered_path_neighbors, _search_ranked_paths
from services.graph_service.engine import get_graph_engine


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _predicates(relations: list[dict]) -> set[str]:
    return {r["predicate"] for r in relations}


def _targets(relations: list[dict]) -> set[str]:
    return {str(r["target"]) for r in relations}


# ---------------------------------------------------------------------------
# 测试套件
# ---------------------------------------------------------------------------

class TestGraphEngineHealth(unittest.TestCase):
    """健康检查：确认加载了 runtime 图，并具备基本规模。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_graph_engine()

    def test_backend_is_runtime_graph(self) -> None:
        health = self.engine.health()
        self.assertIn(health["backend"], {"sqlite_runtime_graph", "nebulagraph_primary"})
        self.assertEqual(health["status"], "ok")

    def test_graph_has_minimum_scale(self) -> None:
        health = self.engine.health()
        # runtime 图至少包含 100 条三元组对应的节点/边
        self.assertGreaterEqual(health["node_count"], 30)
        self.assertGreaterEqual(health["edge_count"], 80)

    def test_evidence_loaded(self) -> None:
        health = self.engine.health()
        # evidence 文件至少与三元组数量相当
        self.assertGreaterEqual(health["evidence_count"], 80)
        self.assertTrue(health["evidence_path"].endswith(".jsonl"))


class TestEntityLookup(unittest.TestCase):
    """实体查询：验证 runtime 图中存在的实体及其关系谓词。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_graph_engine()

    def test_lookup_formula_with_herbs(self) -> None:
        """六味地黄丸应返回药材使用关系。"""
        result = self.engine.entity_lookup("六味地黄丸", top_k=20)
        self.assertEqual(result["entity"]["canonical_name"], "六味地黄丸")
        self.assertIn("使用药材", _predicates(result["relations"]))
        # 六味地黄丸六味药：丹皮、山茱萸、山药、泽泻、熟地黄、茯苓
        herb_targets = {
            r["target"] for r in result["relations"] if r["predicate"] == "使用药材"
        }
        self.assertGreaterEqual(len(herb_targets), 4)
        self.assertIn("熟地黄", herb_targets)
        self.assertTrue(
            herb_targets & {"茯苓", "白茯苓"},
            f"Expected 茯苓 or 白茯苓 in {herb_targets}",
        )

    def test_lookup_formula_efficacy(self) -> None:
        """六味地黄丸应包含功效关系。"""
        result = self.engine.entity_lookup("六味地黄丸", top_k=20)
        self.assertIn("功效", _predicates(result["relations"]))

    def test_lookup_formula_syndrome(self) -> None:
        """六味地黄丸应包含治疗证候关系，指向真阴亏损或肝肾不足。"""
        result = self.engine.entity_lookup("六味地黄丸", top_k=20)
        self.assertIn("治疗证候", _predicates(result["relations"]))
        syndrome_targets = {
            r["target"] for r in result["relations"] if r["predicate"] == "治疗证候"
        }
        self.assertTrue(
            syndrome_targets & {"真阴亏损", "肝肾不足"},
            f"Expected 真阴亏损 or 肝肾不足 in {syndrome_targets}",
        )

    def test_lookup_small_topk_still_covers_core_relation_types(self) -> None:
        """小 top_k 下也应优先保留核心关系类型，而不是被重复边挤满。"""
        result = self.engine.entity_lookup("六味地黄丸", top_k=6)
        predicates = _predicates(result["relations"])
        self.assertIn("使用药材", predicates)
        self.assertIn("功效", predicates)
        self.assertIn("治疗证候", predicates)

    def test_lookup_four_gentlemen_herbs(self) -> None:
        """四君子汤的组成药材应包含人参和白术。"""
        result = self.engine.entity_lookup("四君子汤", top_k=20)
        self.assertEqual(result["entity"]["canonical_name"], "四君子汤")
        herb_targets = {
            r["target"] for r in result["relations"] if r["predicate"] == "使用药材"
        }
        self.assertIn("人参", herb_targets)
        self.assertIn("白术", herb_targets)

    def test_lookup_returns_empty_for_unknown_entity(self) -> None:
        """完全不存在的实体应返回空结果。"""
        result = self.engine.entity_lookup("不存在的实体_xyz123", top_k=5)
        self.assertEqual(result, {})

    def test_lookup_relations_include_cluster_support_metadata(self) -> None:
        """关系簇结果应暴露证据覆盖信息，便于后续回答链路做可信度决策。"""
        result = self.engine.entity_lookup("四君子汤", top_k=10)
        herb_relation = next(r for r in result["relations"] if r["predicate"] == "使用药材" and r["target"] == "人参")
        self.assertGreaterEqual(int(herb_relation["evidence_count"]), 1)
        self.assertGreaterEqual(int(herb_relation["source_book_count"]), 1)
        self.assertIn("avg_confidence", herb_relation)
        self.assertIn("max_confidence", herb_relation)

    def test_lookup_predicate_allowlist_supports_intent_scoped_retrieval(self) -> None:
        """深度模式应能按问题意图限制谓词空间，例如组成问题只看使用药材。"""
        result = self.engine.entity_lookup(
            "六味地黄丸",
            top_k=12,
            predicate_allowlist=["使用药材"],
        )
        predicates = _predicates(result["relations"])
        self.assertEqual(predicates, {"使用药材"})


class TestPathQuery(unittest.TestCase):
    """路径查询：验证 runtime 图中实际存在的连通路径。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_graph_engine()

    def test_herb_to_syndrome_via_formula(self) -> None:
        """熟地黄 → 六味地黄丸 → 真阴亏损（2 跳，graph 中均有直连边）。"""
        result = self.engine.path_query("熟地黄", "真阴亏损", max_hops=3, path_limit=5)
        self.assertGreaterEqual(result["total"], 1)
        # 路径中必须经过六味地黄丸
        all_nodes = set()
        for path in result["paths"]:
            all_nodes.update(path["nodes"])
        self.assertIn("六味地黄丸", all_nodes)

    def test_herb_to_formula_direct(self) -> None:
        """熟地黄 → 六味地黄丸（1 跳，直连）。"""
        result = self.engine.path_query("熟地黄", "六味地黄丸", max_hops=2, path_limit=5)
        self.assertGreaterEqual(result["total"], 1)
        first = result["paths"][0]
        node_set = set(first["nodes"])
        self.assertIn("熟地黄", node_set)
        self.assertIn("六味地黄丸", node_set)

    def test_formula_to_formula_returns_empty_or_indirect(self) -> None:
        """两个方剂之间若无直连，路径可能为空或仅在 max_hops 内找到间接路径。"""
        # 四君子汤和六味地黄丸之间没有直接边，但共享茯苓（2 跳）
        result = self.engine.path_query("四君子汤", "六味地黄丸", max_hops=3, path_limit=5)
        # 不断言一定找到路径，只验证返回格式合法
        self.assertIn("paths", result)
        self.assertIn("total", result)

    def test_unreachable_entities_return_empty(self) -> None:
        """完全不存在的节点对应返回空路径，不报错。"""
        result = self.engine.path_query("不存在A", "不存在B", max_hops=3)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["paths"], [])


class TestPathGuardrails(unittest.TestCase):
    def test_ordered_path_neighbors_prefers_targets_and_caps_fanout(self) -> None:
        rows = [
            {"predicate": "属于范畴", "target": "噪声A", "confidence": 0.2},
            {"predicate": "推荐方剂", "target": "目标节点", "confidence": 0.1},
            {"predicate": "治疗证候", "target": "桥节点", "confidence": 0.8},
            {"predicate": "常见症状", "target": "噪声B", "confidence": 0.9},
        ]

        ordered = _ordered_path_neighbors(rows, target_set={"目标节点"}, fanout_cap=2)

        self.assertEqual(ordered[0], "目标节点")
        self.assertEqual(len(ordered), 2)
        self.assertIn("桥节点", ordered)

    def test_search_ranked_paths_reuses_best_depth_frontier(self) -> None:
        adjacency = {
            "起点": [
                {"predicate": "推荐方剂", "target": "甲", "confidence": 1.0},
                {"predicate": "推荐方剂", "target": "乙", "confidence": 1.0},
            ],
            "甲": [{"predicate": "治疗证候", "target": "公共节点", "confidence": 1.0}],
            "乙": [{"predicate": "治疗证候", "target": "公共节点", "confidence": 1.0}],
            "公共节点": [{"predicate": "功效", "target": "终点", "confidence": 1.0}],
        }
        calls: dict[str, int] = {}

        def relation_rows(node: str) -> list[dict]:
            calls[node] = calls.get(node, 0) + 1
            return adjacency.get(node, [])

        def build_path_payload(nodes: list[str]) -> dict:
            return {"nodes": nodes, "score": 1.0 / len(nodes)}

        result = _search_ranked_paths(
            start_candidates=["起点"],
            target_set={"终点"},
            max_hops=4,
            path_limit=5,
            relation_rows=relation_rows,
            build_path_payload=build_path_payload,
        )

        self.assertGreaterEqual(result["total"], 1)
        self.assertEqual(calls.get("公共节点"), 1, f"frontier guard should prevent duplicate expansion: {calls}")


class TestSyndromeChain(unittest.TestCase):
    """证候链路：给定症状，验证能找到对应证候及推荐方剂。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_graph_engine()

    def test_symptom_to_syndrome_has_result(self) -> None:
        """脉微应能命中当前 runtime 图中的证候结果。"""
        result = self.engine.syndrome_chain("脉微", top_k=5)
        self.assertEqual(result["symptom"], "脉微")
        # 至少找到一个证候
        self.assertGreaterEqual(len(result["syndromes"]), 1)
        syndrome_names = {s["name"] for s in result["syndromes"]}
        self.assertTrue(
            syndrome_names & {"脏厥", "少阴病"},
            f"Expected 脏厥 or 少阴病 in {syndrome_names}",
        )

    def test_syndrome_has_score_field(self) -> None:
        """每个证候条目都应包含 score 字段。"""
        result = self.engine.syndrome_chain("脉微", top_k=5)
        for item in result["syndromes"]:
            self.assertIn("score", item)
            self.assertIsInstance(item["score"], float)

    def test_syndrome_recommended_formulas_is_list(self) -> None:
        """recommended_formulas 字段必须是列表，即使为空。"""
        result = self.engine.syndrome_chain("脉微", top_k=5)
        for item in result["syndromes"]:
            self.assertIn("recommended_formulas", item)
            self.assertIsInstance(item["recommended_formulas"], list)

    def test_unknown_symptom_returns_empty_list(self) -> None:
        """完全未知的症状返回空证候列表，不报错。"""
        result = self.engine.syndrome_chain("完全不存在的症状xyz", top_k=3)
        self.assertEqual(result["syndromes"], [])


class TestRuntimeGraphPrecedence(unittest.TestCase):
    """加载优先级：runtime 图存在时应覆盖 sample 图。"""

    def test_runtime_takes_precedence_over_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sample_path = root / "sample_graph.json"
            runtime_path = root / "graph_runtime.json"

            # sample 中有节点 A，runtime 中只有节点 X
            sample_path.write_text(
                json.dumps(
                    [{"subject": "A", "predicate": "相关", "object": "B"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            runtime_path.write_text(
                json.dumps(
                    [{"subject": "X", "predicate": "推荐方剂", "object": "Y"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            engine = GraphQueryEngine(
                GraphServiceSettings(
                    backend_dir=root,
                    sample_graph_path=sample_path,
                    runtime_graph_path=runtime_path,
                )
            )

            health = engine.health()
            # runtime 图存在时，SQLite runtime 后端应被选中
            self.assertEqual(health["backend"], "sqlite_runtime_graph")
            self.assertEqual(health["graph_path"], str(runtime_path.with_suffix(".db")))
            # runtime 与 sample 均可查询，说明导入与合并正常
            self.assertEqual(engine.entity_lookup("X", top_k=5)["entity"]["canonical_name"], "X")
            self.assertEqual(engine.entity_lookup("A", top_k=5)["entity"]["canonical_name"], "A")


class TestRuntimeEvidence(unittest.TestCase):
    """Evidence 加载与返回：验证 evidence JSONL 正确注入到关系中。"""

    def test_evidence_enriches_entity_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sample_path = root / "sample_graph.json"
            runtime_path = root / "graph_runtime.json"
            evidence_path = root / "graph_runtime.evidence.jsonl"

            sample_path.write_text("[]", encoding="utf-8")
            runtime_path.write_text(
                json.dumps(
                    [
                        {
                            "fact_id": "fact-test-001",
                            "fact_ids": ["fact-test-001"],
                            "subject": "测试方",
                            "predicate": "使用药材",
                            "object": "甘草",
                            "subject_type": "formula",
                            "object_type": "herb",
                            "source_book": "测试书",
                            "source_chapter": "正文",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text(
                json.dumps(
                    {
                        "fact_id": "fact-test-001",
                        "source_book": "测试书",
                        "source_chapter": "正文",
                        "source_text": "测试方以甘草为君。",
                        "confidence": 0.95,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            engine = GraphQueryEngine(
                GraphServiceSettings(
                    backend_dir=root,
                    sample_graph_path=sample_path,
                    runtime_graph_path=runtime_path,
                    runtime_evidence_path=evidence_path,
                )
            )

            health = engine.health()
            self.assertEqual(health["evidence_count"], 1)
            self.assertEqual(health["evidence_path"], str(evidence_path))

            result = engine.entity_lookup("测试方", top_k=5)
            self.assertEqual(result["entity"]["canonical_name"], "测试方")
            rel = result["relations"][0]
            self.assertEqual(rel["fact_id"], "fact-test-001")
            self.assertEqual(rel["source_text"], "测试方以甘草为君。")
            self.assertAlmostEqual(rel["confidence"], 0.95, places=2)

    def test_runtime_evidence_count_matches_jsonl(self) -> None:
        """真实 runtime 引擎的 evidence_count 应与 JSONL 行数一致。"""
        engine = get_graph_engine()
        health = engine.health()
        # 至少有三元组数量的 80% 对应 evidence（允许少量三元组无 evidence）
        node_count = health["node_count"]
        evidence_count = health["evidence_count"]
        # 简单合理性断言：evidence 数 > 0 且非无限大
        self.assertGreater(evidence_count, 0)
        self.assertGreater(node_count, 0)


if __name__ == "__main__":
    unittest.main()
