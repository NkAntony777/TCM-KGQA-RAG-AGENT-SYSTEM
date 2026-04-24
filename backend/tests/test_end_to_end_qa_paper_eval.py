import unittest

from paper_experiments.run_end_to_end_qa_paper_eval import _resolve_eval_workers


class EndToEndQAPaperEvalTests(unittest.TestCase):
    def test_resolve_eval_workers_uses_auto_workers_when_requested_is_zero(self) -> None:
        self.assertEqual(_resolve_eval_workers(0, total_runs=20, auto_workers=8), 8)

    def test_resolve_eval_workers_caps_requested_workers_by_total_runs(self) -> None:
        self.assertEqual(_resolve_eval_workers(12, total_runs=5, auto_workers=8), 5)

    def test_resolve_eval_workers_never_returns_less_than_one(self) -> None:
        self.assertEqual(_resolve_eval_workers(0, total_runs=0, auto_workers=8), 1)


if __name__ == "__main__":
    unittest.main()
