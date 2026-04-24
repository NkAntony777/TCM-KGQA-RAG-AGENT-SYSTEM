from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.runners.run_qa_probe_suite import render_probe_suite_markdown, run_suite
from eval.runners.run_qa_weakness_probe import _evaluate_case, run_probe


class QAProbeSuiteTests(unittest.TestCase):
    def test_graph_source_suite_uses_origin_and_diagnostic_datasets(self) -> None:
        expected_datasets = [
            Path("qa_origin_source_probe_4.json"),
            Path("qa_graph_agent_diagnostic_6.json"),
        ]
        observed_dataset_names: list[str] = []

        def fake_load_dataset(path: Path) -> list[dict[str, object]]:
            observed_dataset_names.append(path.name)
            return [{"id": path.stem, "query": path.name}]

        def fake_run_probe(*, dataset, base_url: str, modes: list[str], top_k: int, timeout: float) -> dict[str, object]:
            case_id = str(dataset[0]["id"])
            if case_id == "qa_origin_source_probe_4":
                return {
                    "total": 2,
                    "passed": 1,
                    "failed": 1,
                    "top_issues": [("book_missing_any:伤寒论", 1)],
                    "by_category": {"origin_clause": {"total": 2, "failed": 1, "avg_latency_ms": 123.4}},
                    "failures": [
                        {
                            "id": "origin_004",
                            "mode": "quick",
                            "route": "graph",
                            "issues": ["book_missing_any:伤寒论"],
                            "books": ["伤寒恒论"],
                            "query": "《伤寒论》四逆散原条文主治是什么？",
                        }
                    ],
                }
            return {
                "total": 4,
                "passed": 4,
                "failed": 0,
                "top_issues": [],
                "by_category": {"graph_path": {"total": 4, "failed": 0, "avg_latency_ms": 88.0}},
                "failures": [],
            }

        with (
            patch("eval.runners.run_qa_probe_suite.load_dataset", side_effect=fake_load_dataset),
            patch("eval.runners.run_qa_probe_suite.run_probe", side_effect=fake_run_probe),
        ):
            summary = run_suite(
                suite_name="graph_source",
                base_url="http://127.0.0.1:8002",
                modes=["quick", "deep"],
                top_k=12,
                timeout=90.0,
            )

        self.assertEqual(observed_dataset_names, [path.name for path in expected_datasets])
        self.assertEqual(summary["suite"], "graph_source")
        self.assertFalse(summary["gate_passed"])
        self.assertEqual(summary["total"], 6)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual([item["dataset"] for item in summary["datasets"]], [path.name for path in expected_datasets])
        self.assertEqual(summary["top_issues"][0][0], "book_missing_any:伤寒论")

    def test_render_probe_suite_markdown_includes_gate_and_failure_details(self) -> None:
        summary = {
            "generated_at": "2026-04-09 17:00:00 +0800",
            "suite": "graph_source",
            "gate_passed": False,
            "base_url": "http://127.0.0.1:8002",
            "modes": ["quick", "deep"],
            "top_k": 12,
            "timeout_s": 90.0,
            "total": 6,
            "passed": 5,
            "failed": 1,
            "top_issues": [("book_missing_any:伤寒论", 1)],
            "datasets": [
                {
                    "dataset": "qa_origin_source_probe_4.json",
                    "total": 2,
                    "passed": 1,
                    "failed": 1,
                    "by_category": {"origin_clause": {"total": 2, "failed": 1, "avg_latency_ms": 123.4}},
                    "failures": [
                        {
                            "id": "origin_004",
                            "mode": "quick",
                            "route": "graph",
                            "issues": ["book_missing_any:伤寒论"],
                            "books": ["伤寒恒论"],
                            "query": "《伤寒论》四逆散原条文主治是什么？",
                        }
                    ],
                }
            ],
            "failures": [
                {
                    "dataset": "qa_origin_source_probe_4.json",
                    "id": "origin_004",
                    "mode": "quick",
                    "route": "graph",
                    "issues": ["book_missing_any:伤寒论"],
                    "books": ["伤寒恒论"],
                }
            ],
        }

        markdown = render_probe_suite_markdown(summary)

        self.assertIn("# QA probe suite report — graph_source", markdown)
        self.assertIn("| gate_passed | no |", markdown)
        self.assertIn("qa_origin_source_probe_4.json", markdown)
        self.assertIn("book_missing_any:伤寒论", markdown)
        self.assertIn("route=graph", markdown)

    def test_run_probe_converts_request_timeout_into_failed_case(self) -> None:
        dataset = [{"id": "origin_001", "category": "origin_source", "query": "六味地黄丸出自哪本书？"}]

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def post(self, *args, **kwargs):
                raise __import__("httpx").ReadTimeout("timed out")

        with patch("eval.runners.run_qa_weakness_probe.httpx.Client", FakeClient):
            summary = run_probe(
                dataset=dataset,
                base_url="http://127.0.0.1:8002",
                modes=["quick"],
                top_k=12,
                timeout=30.0,
            )

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failures"][0]["issues"], ["request_error:ReadTimeout"])

    def test_run_probe_parallel_reuses_http_client_within_worker_threads(self) -> None:
        dataset = [
            {"id": f"origin_{index:03d}", "category": "origin_source", "query": f"问题 {index}"}
            for index in range(1, 4)
        ]
        init_lock = threading.Lock()

        class FakeResponse:
            def json(self) -> dict[str, object]:
                return {
                    "data": {
                        "answer": "标准答案",
                        "route": {"final_route": "graph", "executed_routes": ["graph"]},
                        "factual_evidence": [],
                        "citations": [],
                        "tool_trace": [],
                    }
                }

        class FakeClient:
            init_count = 0

            def __init__(self, *args, **kwargs) -> None:
                with init_lock:
                    FakeClient.init_count += 1

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def close(self) -> None:
                return None

            def post(self, *args, **kwargs):
                time.sleep(0.02)
                return FakeResponse()

        total_runs = len(dataset) * 2
        with patch("eval.runners.run_qa_weakness_probe.httpx.Client", FakeClient):
            summary = run_probe(
                dataset=dataset,
                base_url="http://127.0.0.1:8002",
                modes=["quick", "deep"],
                top_k=12,
                timeout=30.0,
                workers=2,
            )

        self.assertEqual(summary["failed"], 0)
        self.assertLess(FakeClient.init_count, total_runs)

    def test_run_probe_round_robins_across_base_urls(self) -> None:
        dataset = [
            {"id": "origin_001", "category": "origin_source", "query": "问题 1"},
            {"id": "origin_002", "category": "origin_source", "query": "问题 2"},
        ]
        post_bases: list[str] = []

        class FakeResponse:
            def json(self) -> dict[str, object]:
                return {
                    "data": {
                        "answer": "标准答案",
                        "route": {"final_route": "graph", "executed_routes": ["graph"]},
                        "factual_evidence": [],
                        "citations": [],
                        "tool_trace": [],
                    }
                }

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                self.base_url = str(kwargs.get("base_url", ""))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def close(self) -> None:
                return None

            def post(self, *args, **kwargs):
                post_bases.append(self.base_url)
                return FakeResponse()

        with patch("eval.runners.run_qa_weakness_probe.httpx.Client", FakeClient):
            summary = run_probe(
                dataset=dataset,
                base_url="http://127.0.0.1:8002",
                base_urls=["http://127.0.0.1:8002", "http://127.0.0.1:8003"],
                modes=["quick", "deep"],
                top_k=12,
                timeout=30.0,
                workers=1,
            )

        self.assertEqual(summary["failed"], 0)
        self.assertEqual(
            post_bases,
            [
                "http://127.0.0.1:8002",
                "http://127.0.0.1:8003",
                "http://127.0.0.1:8002",
                "http://127.0.0.1:8003",
            ],
        )

    def test_evaluate_case_accepts_single_choice_with_correct_final_letter(self) -> None:
        case = {
            "id": "mcq_001",
            "query": "一般药物干品的常用量为",
            "answer_option_letters_any": ["D"],
            "answer_contains_any": ["3~9g"],
        }
        response = {
            "answer": "一般药物干品的常用量范围是3~9克。\n\n最终选项：D",
            "route": {"final_route": "hybrid", "executed_routes": ["graph", "retrieval"]},
            "factual_evidence": [],
            "citations": [],
            "tool_trace": [],
        }
        result = _evaluate_case(case, mode="quick", response_data=response, latency_ms=123.4)
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    def test_evaluate_case_keeps_uncertain_answer_failed_even_if_expected_token_appears(self) -> None:
        case = {
            "id": "mcq_002",
            "query": "不宜与地榆同用的西药是",
            "answer_option_letters_any": ["E"],
            "answer_contains_any": ["维生素"],
        }
        response = {
            "answer": "根据现有证据，无法确定与哪个西药存在明确配伍禁忌。\n\n最终选项：无",
            "route": {"final_route": "hybrid", "executed_routes": ["graph", "retrieval"]},
            "factual_evidence": [],
            "citations": [],
            "tool_trace": [],
        }
        result = _evaluate_case(case, mode="quick", response_data=response, latency_ms=123.4)
        self.assertFalse(result["passed"])
        self.assertIn("answer_option_letters_missing_any:E", result["issues"])


if __name__ == "__main__":
    unittest.main()
