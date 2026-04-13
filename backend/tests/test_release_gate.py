from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.runners.run_release_gate import summarize_doctoral_baseline


class TestReleaseGateDoctoralBaseline(unittest.TestCase):
    def test_summarize_doctoral_baseline_detects_complete_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doctoral.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": [
                            {"quick": {"ok": True, "answer": "a"}, "deep": {"ok": True, "answer": "b"}},
                            {"quick": {"ok": True, "answer": "c"}, "deep": {"ok": True, "answer": "d"}},
                        ],
                        "summary": {"total_questions": 2},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary = summarize_doctoral_baseline(path)

        self.assertTrue(summary["available"])
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["quick_ok"], 2)
        self.assertEqual(summary["deep_ok"], 2)
        self.assertEqual(summary["total_questions"], 2)

    def test_summarize_doctoral_baseline_detects_incomplete_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doctoral.json"
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

        self.assertTrue(summary["available"])
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["quick_ok"], 1)
        self.assertEqual(summary["deep_ok"], 0)


if __name__ == "__main__":
    unittest.main()
