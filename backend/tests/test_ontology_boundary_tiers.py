from __future__ import annotations

import unittest

from scripts.audit_ontology_boundary_tiers import ACCEPTABLE
from scripts.audit_ontology_boundary_tiers import DIRTY
from scripts.audit_ontology_boundary_tiers import REVIEW
from scripts.audit_ontology_boundary_tiers import classify_boundary_tier


class OntologyBoundaryTierTests(unittest.TestCase):
    def test_formula_to_herb_composition_stays_in_schema(self) -> None:
        self.assertEqual(classify_boundary_tier("使用药材", "formula", "herb"), "in_schema")

    def test_disease_to_herb_under_composition_is_acceptable_polysemy(self) -> None:
        self.assertEqual(classify_boundary_tier("使用药材", "disease", "herb"), ACCEPTABLE)

    def test_herb_to_herb_under_composition_is_likely_dirty(self) -> None:
        self.assertEqual(classify_boundary_tier("使用药材", "herb", "herb"), DIRTY)

    def test_formula_to_channel_under_guijing_is_acceptable_polysemy(self) -> None:
        self.assertEqual(classify_boundary_tier("归经", "formula", "channel"), ACCEPTABLE)

    def test_disease_to_formula_under_recommend_formula_stays_in_schema(self) -> None:
        self.assertEqual(classify_boundary_tier("推荐方剂", "disease", "formula"), "in_schema")

    def test_formula_to_formula_under_recommend_formula_is_review_needed(self) -> None:
        self.assertEqual(classify_boundary_tier("推荐方剂", "formula", "formula"), REVIEW)


if __name__ == "__main__":
    unittest.main()
