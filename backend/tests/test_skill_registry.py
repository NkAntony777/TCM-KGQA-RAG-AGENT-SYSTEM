from __future__ import annotations

import unittest

from services.qa_service.skill_registry import clear_runtime_skills_cache, get_runtime_skills


class SkillRegistryTests(unittest.TestCase):
    def test_runtime_skills_are_loaded_from_local_skill_files(self) -> None:
        clear_runtime_skills_cache()
        skills = get_runtime_skills()

        self.assertIn("route-tcm-query", skills)
        self.assertIn("read-formula-origin", skills)
        self.assertIn("expand-entity-alias", skills)

        route_skill = skills["route-tcm-query"]
        self.assertEqual(route_skill.primary_tool, "tcm_route_search")
        self.assertTrue(any("tcm_route_search" in tool for tool in route_skill.preferred_tools))
        self.assertTrue(any("evidence_paths" in item for item in route_skill.output_focus))

        origin_skill = skills["read-formula-origin"]
        self.assertEqual(origin_skill.primary_tool, "read_evidence_path")
        self.assertTrue(any("书名" in item for item in origin_skill.output_focus))
        self.assertTrue(any("原文片段" in item for item in origin_skill.output_focus))
        self.assertTrue(any("出处" in item for item in origin_skill.trigger_phrases))
        self.assertTrue(any("book://" in item for item in origin_skill.preferred_path_patterns))

        alias_skill = skills["expand-entity-alias"]
        self.assertEqual(alias_skill.primary_tool, "read_evidence_path")
        self.assertTrue(any("别名" in item for item in alias_skill.trigger_phrases))
        self.assertTrue(any("alias://" in item for item in alias_skill.preferred_path_patterns))

    def test_executable_skill_filter_keeps_only_deep_qa_relevant_skills(self) -> None:
        clear_runtime_skills_cache()
        skills = get_runtime_skills(executable_only=True, allowed_tools={"read_evidence_path", "search_evidence_text"})

        self.assertIn("read-formula-origin", skills)
        self.assertIn("search-source-text", skills)
        self.assertIn("trace-graph-path", skills)
        self.assertIn("read-syndrome-treatment", skills)
        self.assertIn("expand-entity-alias", skills)
        self.assertNotIn("external-source-verification", skills)


if __name__ == "__main__":
    unittest.main()
