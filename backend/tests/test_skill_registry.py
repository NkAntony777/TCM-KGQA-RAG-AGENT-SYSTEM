from __future__ import annotations

import unittest

from services.qa_service.skill_registry import clear_runtime_skills_cache, get_runtime_skills


class SkillRegistryTests(unittest.TestCase):
    def test_runtime_skills_are_loaded_from_local_skill_files(self) -> None:
        clear_runtime_skills_cache()
        skills = get_runtime_skills()

        self.assertIn("route-tcm-query", skills)
        self.assertIn("read-formula-origin", skills)

        route_skill = skills["route-tcm-query"]
        self.assertEqual(route_skill.primary_tool, "tcm_route_search")
        self.assertTrue(any("tcm_route_search" in tool for tool in route_skill.preferred_tools))
        self.assertTrue(any("evidence_paths" in item for item in route_skill.output_focus))

        origin_skill = skills["read-formula-origin"]
        self.assertEqual(origin_skill.primary_tool, "read_evidence_path")
        self.assertTrue(any("书名" in item for item in origin_skill.output_focus))
        self.assertTrue(any("原文片段" in item for item in origin_skill.output_focus))


if __name__ == "__main__":
    unittest.main()
