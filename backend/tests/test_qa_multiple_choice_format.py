from __future__ import annotations

import unittest

from services.qa_service.prompts import (
    _build_grounded_user_prompt,
    _ensure_multiple_choice_answer_format,
)


class QAMultipleChoiceFormatTests(unittest.TestCase):
    def test_grounded_prompt_adds_multiple_choice_output_contract(self) -> None:
        query = (
            "请回答下面的中药学选择题。\n"
            "题目：制川乌采用的方法为\n"
            "选项：\n"
            "A. 先煎\n"
            "B. 后下\n"
            "C. 烊化\n"
            "D. 包煎\n"
            "E. 另煎"
        )
        prompt = _build_grounded_user_prompt(
            query=query,
            payload={},
            mode="quick",
            factual_evidence=[],
            evidence_groups={"structured": [], "documentary": [], "other": []},
            case_references=[],
            citations=[],
            notes=[],
            book_citations=[],
            deep_trace=[],
            evidence_limit=4,
        )
        self.assertIn("这是带选项的选择题。", prompt)
        self.assertIn("最终选项：X", prompt)

    def test_postprocess_appends_missing_choice_letter_from_option_text(self) -> None:
        query = (
            "请回答下面的中药学选择题。\n"
            "题目：制川乌采用的方法为\n"
            "选项：\n"
            "A. 先煎\n"
            "B. 后下\n"
            "C. 烊化\n"
            "D. 包煎\n"
            "E. 另煎"
        )
        answer = "制川乌的常规煎煮方法是先煎。"
        normalized = _ensure_multiple_choice_answer_format(query, answer)
        self.assertIn("最终选项：A", normalized)

    def test_postprocess_keeps_existing_explicit_choice_letters(self) -> None:
        query = (
            "请回答下面的中药学选择题。\n"
            "题目：阿胶采用的方法为\n"
            "选项：\n"
            "A. 先煎\n"
            "B. 后下\n"
            "C. 烊化\n"
            "D. 包煎\n"
            "E. 另煎"
        )
        answer = "阿胶应采用烊化。\n\n最终选项：C"
        normalized = _ensure_multiple_choice_answer_format(query, answer)
        self.assertEqual(normalized.count("最终选项：C"), 1)


if __name__ == "__main__":
    unittest.main()
