from __future__ import annotations

import unittest

from router.tcm_intent_classifier import analyze_tcm_query


class TCMIntentClassifierTests(unittest.TestCase):
    def test_formula_composition_query(self) -> None:
        analysis = analyze_tcm_query("六味地黄丸的组成是什么")
        self.assertEqual(analysis.dominant_intent, "formula_composition")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.graph_query_kind, "entity")
        self.assertEqual(analysis.primary_entity, "六味地黄丸")
        self.assertIn("formula_composition", analysis.matched_keywords)

    def test_formula_origin_query_prefers_retrieval(self) -> None:
        analysis = analyze_tcm_query("逍遥散出自哪本古籍")
        self.assertEqual(analysis.dominant_intent, "formula_origin")
        self.assertEqual(analysis.route_hint, "retrieval")
        self.assertGreaterEqual(analysis.retrieval_score, 5)

    def test_compare_query_extracts_two_entities(self) -> None:
        analysis = analyze_tcm_query("逍遥散和六味地黄丸有什么区别")
        self.assertEqual(analysis.dominant_intent, "compare_entities")
        self.assertEqual(analysis.route_hint, "hybrid")
        self.assertEqual(analysis.compare_entities(), ["逍遥散", "六味地黄丸"])

    def test_symptom_query_uses_syndrome_graph_chain(self) -> None:
        analysis = analyze_tcm_query("胁肋胀痛可能对应什么证候")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.graph_query_kind, "syndrome")
        self.assertEqual(analysis.symptom_name, "胁肋胀痛")

    def test_path_query_is_detected_first(self) -> None:
        analysis = analyze_tcm_query("头痛到逍遥散的辨证路径是什么")
        self.assertEqual(analysis.dominant_intent, "graph_path")
        self.assertEqual(analysis.graph_query_kind, "path")
        self.assertEqual(analysis.path_start, "头痛")
        self.assertEqual(analysis.path_end, "逍遥散")


if __name__ == "__main__":
    unittest.main()
