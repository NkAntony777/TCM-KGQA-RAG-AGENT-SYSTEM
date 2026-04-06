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

    def test_formula_origin_query_prefers_hybrid(self) -> None:
        analysis = analyze_tcm_query("逍遥散出自哪本古籍")
        self.assertEqual(analysis.dominant_intent, "formula_origin")
        self.assertEqual(analysis.route_hint, "hybrid")
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

    def test_definition_phrase_does_not_override_graph_entity_query(self) -> None:
        analysis = analyze_tcm_query("柴胡的归经和功效是什么？")
        self.assertEqual(analysis.dominant_intent, "formula_efficacy")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.primary_entity, "柴胡")

    def test_property_query_extracts_clean_entity_name(self) -> None:
        analysis = analyze_tcm_query("柴胡的性味归经是什么？")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.primary_entity, "柴胡")
        self.assertEqual(analysis.compare_entities(), [])

    def test_syndrome_treatment_method_query_is_treated_as_graph_efficacy(self) -> None:
        analysis = analyze_tcm_query("肝郁脾虚的治法是什么？")
        self.assertEqual(analysis.dominant_intent, "formula_efficacy")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.primary_entity, "肝郁脾虚")
        self.assertEqual(analysis.compare_entities(), [])

    def test_syndrome_formula_query_keeps_clean_syndrome_entity(self) -> None:
        analysis = analyze_tcm_query("肝郁脾虚一般推荐什么方剂？")
        self.assertEqual(analysis.dominant_intent, "syndrome_to_formula")
        self.assertEqual(analysis.route_hint, "graph")
        self.assertEqual(analysis.primary_entity, "肝郁脾虚")

    def test_path_query_with_source_request_prefers_hybrid(self) -> None:
        analysis = analyze_tcm_query("从肝郁脾虚到逍遥散的链路是什么，并给一个古籍出处佐证。")
        self.assertEqual(analysis.dominant_intent, "graph_path")
        self.assertEqual(analysis.route_hint, "hybrid")

    def test_long_formula_mechanism_query_anchors_formula_entity(self) -> None:
        analysis = analyze_tcm_query(
            "《伤寒论》五苓散方后注“多饮暖水，汗出愈”，请从AQP分布差异论证五苓散利小便与发汗是否存在阈值效应。"
        )
        self.assertIn("五苓散", analysis.entity_types())
        self.assertEqual(analysis.primary_entity, "五苓散")
        self.assertEqual(analysis.graph_query_kind, "entity")
        self.assertEqual(analysis.route_hint, "hybrid")


if __name__ == "__main__":
    unittest.main()
