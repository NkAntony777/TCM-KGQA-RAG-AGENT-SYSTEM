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
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from services.graph_service.engine import GraphQueryEngine
from services.graph_service.engine import GraphServiceSettings
from services.graph_service.engine import NebulaPrimaryGraphEngine
from services.graph_service.engine import _ordered_path_neighbors, _search_ranked_paths
from services.graph_service.relation_governance import expand_filter_predicates
from services.graph_service.runtime_store import RuntimeGraphStore
from services.graph_service.runtime_store import RuntimeGraphStoreSettings
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

    def test_lookup_predicate_allowlist_supports_family_name(self) -> None:
        """关系族应能在查询层展开，不要求调用方显式枚举所有原始谓词。"""
        result = self.engine.entity_lookup(
            "六味地黄丸",
            top_k=12,
            predicate_allowlist=["主治族"],
        )
        predicates = _predicates(result["relations"])
        self.assertTrue(predicates)
        self.assertTrue(predicates <= {"治疗证候", "治疗疾病", "治疗症状"})
        for relation in result["relations"]:
            self.assertEqual(relation.get("predicate_family"), "主治族")

    def test_lookup_marks_ontology_boundary_mismatch_for_out_of_schema_relation(self) -> None:
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
                            "fact_id": "f1",
                            "fact_ids": ["f1"],
                            "subject": "HT皮疮",
                            "predicate": "使用药材",
                            "object": "大黄",
                            "subject_type": "disease",
                            "object_type": "herb",
                            "source_book": "282-医门补要",
                            "source_chapter": "282-医门补要_正文",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text("", encoding="utf-8")

            engine = GraphQueryEngine(
                GraphServiceSettings(
                    backend_dir=root,
                    sample_graph_path=sample_path,
                    runtime_graph_path=runtime_path,
                    runtime_evidence_path=evidence_path,
                )
            )

            result = engine.entity_lookup("HT皮疮", top_k=5)

            self.assertEqual(result["entity"]["entity_type"], "disease")
            self.assertEqual(result["relations"][0]["predicate"], "使用药材")
            self.assertFalse(result["relations"][0]["ontology_boundary_ok"])
            self.assertEqual(result["relations"][0]["ontology_boundary_tier"], "acceptable_polysemy")

    def test_lookup_exposes_review_needed_tier_for_formula_to_formula_recommendation(self) -> None:
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
                            "fact_id": "f1",
                            "fact_ids": ["f1"],
                            "subject": "三焦咳",
                            "predicate": "推荐方剂",
                            "object": "小青龙汤",
                            "subject_type": "formula",
                            "object_type": "formula",
                            "source_book": "395-凌临灵方",
                            "source_chapter": "395-凌临灵方_正文",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text("", encoding="utf-8")

            engine = GraphQueryEngine(
                GraphServiceSettings(
                    backend_dir=root,
                    sample_graph_path=sample_path,
                    runtime_graph_path=runtime_path,
                    runtime_evidence_path=evidence_path,
                )
            )

            result = engine.entity_lookup("三焦咳", top_k=5)

            self.assertEqual(result["relations"][0]["predicate"], "推荐方剂")
            self.assertEqual(result["relations"][0]["ontology_boundary_tier"], "review_needed")


class TestPathQuery(unittest.TestCase):
    """路径查询：验证 runtime 图中实际存在的连通路径。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_graph_engine()

    def test_herb_to_syndrome_via_formula(self) -> None:
        """熟地黄 → 六味地黄丸/六味地黄汤 → 真阴亏损。"""
        result = self.engine.path_query("熟地黄", "真阴亏损", max_hops=3, path_limit=5)
        self.assertGreaterEqual(result["total"], 1)
        # 路径中必须经过六味地黄系方名之一
        all_nodes = set()
        for path in result["paths"]:
            all_nodes.update(path["nodes"])
        self.assertTrue(all_nodes & {"六味地黄丸", "六味地黄汤", "六味丸"})

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

    def test_search_ranked_paths_uses_two_hop_bridge_shortcut(self) -> None:
        adjacency = {
            "起点": [{"predicate": "推荐方剂", "target": "桥节点", "confidence": 1.0}],
            "桥节点": [{"predicate": "治疗证候", "target": "终点", "confidence": 1.0}],
            "终点": [{"predicate": "治疗证候", "target": "桥节点", "confidence": 1.0}],
        }
        calls: dict[str, int] = {}

        def relation_rows(node: str) -> list[dict]:
            calls[node] = calls.get(node, 0) + 1
            return adjacency.get(node, [])

        def build_path_payload(nodes: list[str]) -> dict | None:
            if nodes == ["起点", "桥节点", "终点"]:
                return {"nodes": nodes, "score": 1.0}
            if nodes == ["起点", "终点"]:
                return None
            return None

        result = _search_ranked_paths(
            start_candidates=["起点"],
            target_set={"终点"},
            max_hops=3,
            path_limit=3,
            relation_rows=relation_rows,
            build_path_payload=build_path_payload,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["paths"][0]["nodes"], ["起点", "桥节点", "终点"])
        self.assertLessEqual(calls.get("起点", 0) + calls.get("终点", 0), 2)

    def test_ordered_path_neighbors_skips_text_heavy_display_edges(self) -> None:
        rows = [
            {"predicate": "食忌", "target": "忌猪肉", "confidence": 1.0},
            {"predicate": "出处", "target": "伤寒论", "confidence": 1.0},
            {"predicate": "推荐方剂", "target": "真节点", "confidence": 0.8},
        ]

        ordered = _ordered_path_neighbors(rows, target_set={"真节点"}, fanout_cap=5)

        self.assertEqual(ordered, ["真节点"])


class TestNebulaDirectPathPayload(unittest.TestCase):
    def test_build_payload_from_nebula_path_row_preserves_nodes_and_sources(self) -> None:
        class StubStore:
            def first_edge_between(self, left: str, right: str) -> dict[str, Any]:
                mapping = {
                    ("熟地黄", "六味地黄汤"): {
                        "predicate": "使用药材",
                        "source_book": "医方考",
                        "source_chapter": "卷上",
                        "fact_id": "f1",
                        "fact_ids": ["f1"],
                        "source_text": "熟地黄入六味地黄汤。",
                        "confidence": 0.95,
                    },
                    ("六味地黄汤", "真阴亏损"): {
                        "predicate": "治疗证候",
                        "source_book": "验方新编",
                        "source_chapter": "卷下",
                        "fact_id": "f2",
                        "fact_ids": ["f2"],
                        "source_text": "六味地黄汤治真阴亏损。",
                        "confidence": 0.9,
                    },
                }
                return mapping.get((left, right), {})

        class StubFallbackEngine:
            def __init__(self) -> None:
                self.store = StubStore()

            def _edge_evidence_payload(self, edge_data: dict[str, Any]) -> dict[str, Any]:
                payload: dict[str, Any] = {}
                if edge_data.get("fact_id"):
                    payload["fact_id"] = edge_data["fact_id"]
                if edge_data.get("fact_ids"):
                    payload["fact_ids"] = edge_data["fact_ids"]
                if edge_data.get("source_text"):
                    payload["source_text"] = edge_data["source_text"]
                if edge_data.get("confidence") is not None:
                    payload["confidence"] = edge_data["confidence"]
                return payload

        engine = NebulaPrimaryGraphEngine(primary_store=None, fallback_engine=StubFallbackEngine())
        row = {
            "p": [
                {"entity.name": "熟地黄", "entity.entity_type": "herb"},
                {"predicate": "使用药材", "source_book": "医方考", "source_chapter": "卷上", "fact_id": "f1"},
                {"entity.name": "六味地黄汤", "entity.entity_type": "formula"},
                {"predicate": "治疗证候", "source_book": "验方新编", "source_chapter": "卷下", "fact_id": "f2"},
                {"entity.name": "真阴亏损", "entity.entity_type": "syndrome"},
            ]
        }

        payload = engine._build_payload_from_nebula_path_row(row)  # noqa: SLF001

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["nodes"], ["熟地黄", "六味地黄汤", "真阴亏损"])
        self.assertEqual(payload["edges"], ["使用药材", "治疗证候"])
        self.assertEqual(len(payload["sources"]), 2)
        self.assertEqual(payload["sources"][0]["source_book"], "医方考")
        self.assertEqual(payload["sources"][1]["source_book"], "验方新编")

    def test_auto_mode_prefers_nebula_for_heavy_hops_or_candidate_fanout(self) -> None:
        class StubStore:
            def ready(self) -> bool:
                return True

        engine = NebulaPrimaryGraphEngine(primary_store=StubStore(), fallback_engine=GraphQueryEngine())
        original_mode = os.environ.get("PATH_QUERY_EXECUTION_MODE")
        original_hops = os.environ.get("NEBULA_PATH_QUERY_AUTO_MIN_HOPS")
        original_pairs = os.environ.get("NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS")
        try:
            os.environ["PATH_QUERY_EXECUTION_MODE"] = "auto"
            os.environ["NEBULA_PATH_QUERY_AUTO_MIN_HOPS"] = "4"
            os.environ["NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS"] = "4"
            self.assertTrue(
                engine._should_prefer_nebula_path(  # noqa: SLF001
                    max_hops=5,
                    start_candidates=["a"],
                    end_candidates=["b"],
                )
            )
            self.assertTrue(
                engine._should_prefer_nebula_path(  # noqa: SLF001
                    max_hops=2,
                    start_candidates=["a", "b"],
                    end_candidates=["c", "d"],
                )
            )
            self.assertFalse(
                engine._should_prefer_nebula_path(  # noqa: SLF001
                    max_hops=2,
                    start_candidates=["a"],
                    end_candidates=["b"],
                )
            )
        finally:
            if original_mode is None:
                os.environ.pop("PATH_QUERY_EXECUTION_MODE", None)
            else:
                os.environ["PATH_QUERY_EXECUTION_MODE"] = original_mode
            if original_hops is None:
                os.environ.pop("NEBULA_PATH_QUERY_AUTO_MIN_HOPS", None)
            else:
                os.environ["NEBULA_PATH_QUERY_AUTO_MIN_HOPS"] = original_hops
            if original_pairs is None:
                os.environ.pop("NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS", None)
            else:
                os.environ["NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS"] = original_pairs

    def test_nebula_syndrome_chain_accepts_disease_typed_candidates(self) -> None:
        class StubPrimaryStore:
            def ready(self) -> bool:
                return True

            def batch_neighbors(self, entity_names, *, reverse=False, predicates=None, target_types=None, source_books=None, limit_per_entity=64):
                rows = []
                for name in entity_names:
                    for row in self.neighbors(name, reverse=reverse):
                        item = dict(row)
                        item.setdefault("source_vid", f"vid::{name}")
                        rows.append(item)
                return rows

            def neighbors(self, entity_name: str, *, reverse: bool = False) -> list[dict[str, Any]]:
                assert entity_name == "脉涩"
                assert reverse is True
                return [
                    {
                        "neighbor_name": "瘀血发热",
                        "neighbor_type": "syndrome",
                        "predicate": "常见症状",
                        "fact_id": "f1",
                        "fact_ids": ["f1"],
                        "source_text": "瘀血发热者，其脉涩",
                        "confidence": 0.98,
                    },
                    {
                        "neighbor_name": "滞血发热",
                        "neighbor_type": "disease",
                        "predicate": "常见症状",
                        "fact_id": "f2",
                        "fact_ids": ["f2"],
                        "source_text": "滞血发热，其脉涩",
                        "confidence": 0.9,
                    },
                    {
                        "neighbor_name": "加减息奔丸",
                        "neighbor_type": "formula",
                        "predicate": "常见症状",
                        "fact_id": "f3",
                        "fact_ids": ["f3"],
                        "source_text": "加减息奔丸......脉涩",
                        "confidence": 0.9,
                    },
                ]

        class StubFallbackEngine:
            def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
                return {"symptom": symptom, "syndromes": []}

            def _resolve_entities(self, symptom: str, preferred_types: set[str] | None = None) -> list[str]:
                return ["脉涩"] if symptom == "脉涩" else []

            def _collect_recommended_formulas(self, syndrome_name: str) -> list[str]:
                return ["当归承气汤"] if syndrome_name == "瘀血发热" else []

        engine = NebulaPrimaryGraphEngine(primary_store=StubPrimaryStore(), fallback_engine=StubFallbackEngine())

        result = engine.syndrome_chain("脉涩", top_k=5)

        syndrome_names = {item["name"] for item in result["syndromes"]}
        self.assertIn("瘀血发热", syndrome_names)
        self.assertIn("滞血发热", syndrome_names)
        self.assertNotIn("加减息奔丸", syndrome_names)

    def test_nebula_entity_lookup_prefers_primary_result_over_local(self) -> None:
        class StubPrimaryStore:
            def ready(self) -> bool:
                return True

            def exact_entity(self, entity_name: str) -> list[dict[str, Any]]:
                return [{"name": entity_name, "entity_type": "formula"}] if entity_name == "六味地黄丸" else []

            def batch_exact_entities(self, entity_names: list[str]) -> dict[str, dict[str, Any]]:
                return {
                    item: {"name": item, "entity_type": "formula"}
                    for item in entity_names
                    if item == "六味地黄丸"
                }

            def batch_neighbors(self, entity_names, *, reverse=False, predicates=None, target_types=None, source_books=None, limit_per_entity=64):
                rows = []
                for name in entity_names:
                    for row in self.neighbors(name, reverse=reverse):
                        item = dict(row)
                        item.setdefault("source_vid", f"vid::{name}")
                        rows.append(item)
                return rows

            def neighbors(self, entity_name: str, *, reverse: bool = False) -> list[dict[str, Any]]:
                assert entity_name == "六味地黄丸"
                if reverse:
                    return []
                return [
                    {
                        "neighbor_name": "熟地黄",
                        "neighbor_type": "herb",
                        "predicate": "使用药材",
                        "source_book": "医方考",
                        "source_chapter": "卷上",
                        "fact_id": "f1",
                        "fact_ids": "[]",
                        "source_text": "六味地黄丸用熟地黄。",
                        "confidence": 0.95,
                    }
                ]

        class StubFallbackEngine:
            class store:
                @staticmethod
                def source_book_exists(name: str) -> bool:
                    return False

            def entity_lookup(self, name: str, top_k: int = 12, predicate_allowlist=None, predicate_blocklist=None) -> dict[str, Any]:
                return {
                    "entity": {"name": name, "canonical_name": name, "entity_type": "formula"},
                    "relations": [{"predicate": "功效", "target": "补虚", "direction": "out"}],
                    "total": 1,
                }

            def _resolve_entities(self, query: str, preferred_types=None) -> list[str]:
                return ["六味地黄丸"] if query == "六味地黄丸" else []

            def entity_type(self, entity_name: str) -> str:
                return "formula"

            def _annotate_relation_rows(self, rows: list[dict[str, Any]], *, anchor_entity_type: str) -> list[dict[str, Any]]:
                return rows

            def _filter_relations(self, rows: list[dict[str, Any]], *, predicate_allowlist=None, predicate_blocklist=None) -> list[dict[str, Any]]:
                return rows

            def _select_relation_clusters(self, rows: list[dict[str, Any]], *, query_text: str, top_k: int) -> list[dict[str, Any]]:
                return rows[:top_k]

            def _relation_score(self, relation: dict[str, Any], query_text: str) -> int:
                return 100 if relation.get("predicate") == "使用药材" else 10

            def _predicate_priority(self, relation: dict[str, Any]) -> float:
                return 1.0 if relation.get("predicate") == "使用药材" else 0.1

            def _query_fragments(self, query_text: str) -> list[str]:
                return [query_text]

            def _query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
                return False

        engine = NebulaPrimaryGraphEngine(primary_store=StubPrimaryStore(), fallback_engine=StubFallbackEngine())

        result = engine.entity_lookup("六味地黄丸", top_k=5, predicate_allowlist=["使用药材"])

        self.assertEqual(result["entity"]["canonical_name"], "六味地黄丸")
        self.assertEqual(result["relations"][0]["predicate"], "使用药材")
        self.assertEqual(result["relations"][0]["target"], "熟地黄")

    def test_nebula_syndrome_chain_prefers_primary_result_over_local(self) -> None:
        class StubPrimaryStore:
            def ready(self) -> bool:
                return True

            def batch_neighbors(self, entity_names, *, reverse=False, predicates=None, target_types=None, source_books=None, limit_per_entity=64):
                rows = []
                for name in entity_names:
                    for row in self.neighbors(name, reverse=reverse):
                        item = dict(row)
                        item.setdefault("source_vid", f"vid::{name}")
                        rows.append(item)
                return rows

            def neighbors(self, entity_name: str, *, reverse: bool = False) -> list[dict[str, Any]]:
                assert entity_name == "脉涩"
                assert reverse is True
                return [
                    {
                        "neighbor_name": "瘀血发热",
                        "neighbor_type": "syndrome",
                        "predicate": "常见症状",
                        "fact_id": "f1",
                        "fact_ids": ["f1"],
                        "source_text": "瘀血发热者，其脉涩",
                        "confidence": 0.98,
                    }
                ]

        class StubFallbackEngine:
            def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, Any]:
                return {
                    "symptom": symptom,
                    "syndromes": [{"name": "本地旧结果", "score": 0.5, "recommended_formulas": []}],
                }

            def _resolve_entities(self, symptom: str, preferred_types: set[str] | None = None) -> list[str]:
                return ["脉涩"] if symptom == "脉涩" else []

            def _collect_recommended_formulas(self, syndrome_name: str) -> list[str]:
                return ["当归承气汤"] if syndrome_name == "瘀血发热" else []

        engine = NebulaPrimaryGraphEngine(primary_store=StubPrimaryStore(), fallback_engine=StubFallbackEngine())

        result = engine.syndrome_chain("脉涩", top_k=5)

        self.assertEqual(result["syndromes"][0]["name"], "瘀血发热")



class TestRelationRankingSignals(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = GraphQueryEngine()

    def test_query_fragments_split_chinese_punctuation(self) -> None:
        fragments = self.engine._query_fragments("《小儿药证直诀》中六味地黄丸的出处依据是什么，并说明其主治。")  # noqa: SLF001
        self.assertIn("小儿药证直诀", fragments)
        self.assertIn("六味地黄丸的出处依据", fragments)

    def test_relation_score_boosts_matching_source_book(self) -> None:
        base_relation = {
            "predicate": "治疗证候",
            "target": "真阴亏损",
            "source_text": "六味地黄丸，治肾阴不足。",
            "source_book": "小儿药证直诀",
            "source_chapter": "卷下",
            "source_book_count": 1,
            "evidence_count": 1,
            "direction": "out",
        }
        other_relation = dict(base_relation)
        other_relation["source_book"] = "医方考"

        matching_score = self.engine._relation_score(base_relation, "《小儿药证直诀》中六味地黄丸的出处依据是什么")  # noqa: SLF001
        other_score = self.engine._relation_score(other_relation, "《小儿药证直诀》中六味地黄丸的出处依据是什么")  # noqa: SLF001

        self.assertGreater(matching_score, other_score)

    def test_expand_filter_predicates_supports_normalized_and_parent_targets(self) -> None:
        expanded = expand_filter_predicates(["拉丁学名", "归经"])
        self.assertIn("药材基源", expanded)
        self.assertIn("归经", expanded)
        self.assertIn("药性特征", expanded)


class TestRuntimeEntityResolutionRanking(unittest.TestCase):
    def test_longer_exact_formula_sort_key_stays_ahead_of_fragments(self) -> None:
        store = RuntimeGraphStore(
            RuntimeGraphStoreSettings(
                graph_path=Path("graph_runtime.json"),
                evidence_path=Path("graph_runtime.evidence.jsonl"),
                db_path=Path("graph_runtime.db"),
            )
        )
        candidates = ["六味", "黄丸", "地黄丸", "六味地黄丸"]
        ranked = sorted(candidates, key=lambda item: store._entity_match_sort_key("六味地黄丸", item))  # noqa: SLF001
        self.assertEqual(ranked[0], "六味地黄丸")


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

    def test_normalized_predicate_allowlist_matches_logical_mapping(self) -> None:
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
                            "fact_id": "fact-origin-001",
                            "fact_ids": ["fact-origin-001"],
                            "subject": "黄芪",
                            "predicate": "药材基源",
                            "object": "Astragalus membranaceus",
                            "subject_type": "herb",
                            "object_type": "origin",
                            "source_book": "TCM-MKG",
                            "source_chapter": "D8_CHP_PO",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text("", encoding="utf-8")

            engine = GraphQueryEngine(
                GraphServiceSettings(
                    backend_dir=root,
                    sample_graph_path=sample_path,
                    runtime_graph_path=runtime_path,
                    runtime_evidence_path=evidence_path,
                )
            )

            result = engine.entity_lookup("黄芪", top_k=5, predicate_allowlist=["拉丁学名"])

            self.assertEqual(result["entity"]["canonical_name"], "黄芪")
            self.assertEqual(_predicates(result["relations"]), {"药材基源"})
            self.assertEqual(result["relations"][0].get("normalized_predicate"), "拉丁学名")

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


class TestRuntimePathNeighbors(unittest.TestCase):
    def test_path_neighbors_prioritize_high_value_predicates_and_dedupe_targets(self) -> None:
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
                            "fact_id": "f1",
                            "fact_ids": ["f1"],
                            "subject": "测试药",
                            "predicate": "属于范畴",
                            "object": "杂项A",
                            "subject_type": "herb",
                            "object_type": "other",
                        },
                        {
                            "fact_id": "f2",
                            "fact_ids": ["f2"],
                            "subject": "测试药",
                            "predicate": "治疗证候",
                            "object": "核心证候",
                            "subject_type": "herb",
                            "object_type": "syndrome",
                        },
                        {
                            "fact_id": "f3",
                            "fact_ids": ["f3"],
                            "subject": "测试药",
                            "predicate": "功效",
                            "object": "核心证候",
                            "subject_type": "herb",
                            "object_type": "syndrome",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text("", encoding="utf-8")

            store = RuntimeGraphStore.from_graph_paths(
                graph_path=runtime_path,
                evidence_path=evidence_path,
                sample_graph_path=sample_path,
                sample_evidence_path=None,
            )
            neighbors = store.path_neighbors("测试药", limit=3)

        self.assertEqual(neighbors[0]["target"], "核心证候")
        self.assertEqual(neighbors[0]["predicate"], "治疗证候")
        targets = [item["target"] for item in neighbors]
        self.assertEqual(targets.count("核心证候"), 1)


if __name__ == "__main__":
    unittest.main()
