from __future__ import annotations

import json
import unittest

from eval.runners.run_release_gate import summarize_doctoral_baseline
from tests.test_temp_utils import cleanup_test_dir
from tests.test_temp_utils import make_test_dir


class TestReleaseGateDoctoralBaseline(unittest.TestCase):
    def test_summarize_doctoral_baseline_detects_complete_payload(self) -> None:
        tmpdir = make_test_dir("release_gate")
        try:
            path = tmpdir / "doctoral.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": [
                            {"quick": {"ok": True, "answer": "a" * 20}, "deep": {"ok": True, "answer": "b" * 500, "generation_backend": "planner_llm"}},
                            {"quick": {"ok": True, "answer": "c" * 20}, "deep": {"ok": True, "answer": "d" * 500, "generation_backend": "planner_llm"}},
                        ],
                        "summary": {"total_questions": 2},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary = summarize_doctoral_baseline(path)
        finally:
            cleanup_test_dir(tmpdir)

        self.assertTrue(summary["available"])
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["quick_ok"], 2)
        self.assertEqual(summary["deep_ok"], 2)
        self.assertEqual(summary["deep_fallback_count"], 0)
        self.assertEqual(summary["deep_short_answer_count"], 0)
        self.assertEqual(summary["total_questions"], 2)

    def test_summarize_doctoral_baseline_detects_incomplete_payload(self) -> None:
        tmpdir = make_test_dir("release_gate")
        try:
            path = tmpdir / "doctoral.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": [
                            {"quick": {"ok": True, "answer": "a"}, "deep": None},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary = summarize_doctoral_baseline(path)
        finally:
            cleanup_test_dir(tmpdir)

        self.assertTrue(summary["available"])
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["quick_ok"], 1)
        self.assertEqual(summary["deep_ok"], 0)

    def test_summarize_doctoral_baseline_rejects_short_or_fallback_deep_answer(self) -> None:
        tmpdir = make_test_dir("release_gate")
        try:
            path = tmpdir / "doctoral.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": [
                            {
                                "quick": {"ok": True, "answer": "a"},
                                "deep": {"ok": True, "answer": "太短", "generation_backend": "planner_deterministic_fallback"},
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary = summarize_doctoral_baseline(path)
        finally:
            cleanup_test_dir(tmpdir)

        self.assertFalse(summary["complete"])
        self.assertEqual(summary["deep_fallback_count"], 1)
        self.assertEqual(summary["deep_short_answer_count"], 1)


if __name__ == "__main__":
    unittest.main()
