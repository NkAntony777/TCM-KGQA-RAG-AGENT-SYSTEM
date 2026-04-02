from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import pipeline_server
from scripts.tcm_triple_console import PipelineConfig
from scripts.tcm_triple_console import TCMTriplePipeline


class CountingPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.calls = 0

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        self.calls += 1
        return {
            "triples": [
                {
                    "subject": "FormulaA",
                    "predicate": "治疗证候",
                    "object": f"SyndromeA{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                },
                {
                    "subject": "FormulaB",
                    "predicate": "治疗证候",
                    "object": f"SyndromeB{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.85,
                },
            ]
        }


class RetrySingleDictPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.calls_by_chunk: dict[int, int] = {}

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        count = self.calls_by_chunk.get(task.chunk_index, 0) + 1
        self.calls_by_chunk[task.chunk_index] = count
        if count == 1:
            raise RuntimeError("synthetic_retry_failure")
        return {
            "subject": "FormulaSingle",
            "predicate": "治疗证候",
            "object": f"Syndrome{task.chunk_index}",
            "subject_type": "formula",
            "object_type": "syndrome",
            "source_text": task.text_chunk[:60],
            "confidence": 0.9,
        }


class LowYieldRetryPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.calls_by_chunk: dict[int, int] = {}

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        count = self.calls_by_chunk.get(task.chunk_index, 0) + 1
        self.calls_by_chunk[task.chunk_index] = count

        if task.chunk_index == 1 and count == 1:
            return {
                "triples": [
                    {
                        "subject": "FormulaLow",
                        "predicate": "治疗证候",
                        "object": "SyndromeLow1",
                        "subject_type": "formula",
                        "object_type": "syndrome",
                        "source_text": task.text_chunk[:60],
                        "confidence": 0.9,
                    }
                ]
            }

        triples = [
            {
                "subject": f"Formula{task.chunk_index}",
                "predicate": "治疗证候",
                "object": f"Syndrome{task.chunk_index}-1",
                "subject_type": "formula",
                "object_type": "syndrome",
                "source_text": task.text_chunk[:60],
                "confidence": 0.9,
            },
            {
                "subject": f"Formula{task.chunk_index}",
                "predicate": "治疗证候",
                "object": f"Syndrome{task.chunk_index}-2",
                "subject_type": "formula",
                "object_type": "syndrome",
                "source_text": task.text_chunk[:60],
                "confidence": 0.9,
            },
        ]
        if task.chunk_index == 1:
            triples.append(
                {
                    "subject": "Formula1",
                    "predicate": "治疗证候",
                    "object": "Syndrome1-3",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                }
            )
        return {"triples": triples}


class PersistentLowYieldPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.calls_by_chunk: dict[int, int] = {}

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        self.calls_by_chunk[task.chunk_index] = self.calls_by_chunk.get(task.chunk_index, 0) + 1
        if task.chunk_index == 1:
            return {
                "triples": [
                    {
                        "subject": "FormulaLow",
                        "predicate": "治疗证候",
                        "object": "SyndromeLow1",
                        "subject_type": "formula",
                        "object_type": "syndrome",
                        "source_text": task.text_chunk[:60],
                        "confidence": 0.9,
                    }
                ]
            }
        return {
            "triples": [
                {
                    "subject": f"Formula{task.chunk_index}",
                    "predicate": "治疗证候",
                    "object": f"Syndrome{task.chunk_index}-1",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                },
                {
                    "subject": f"Formula{task.chunk_index}",
                    "predicate": "治疗证候",
                    "object": f"Syndrome{task.chunk_index}-2",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                },
            ]
        }


class PartialSuccessPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.calls = 0

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        self.calls += 1
        if task.chunk_index == 2:
            raise RuntimeError("synthetic_chunk_failure")
        return {
            "triples": [
                {
                    "subject": "FormulaPartialA",
                    "predicate": "治疗证候",
                    "object": f"SyndromePartialA{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                },
                {
                    "subject": "FormulaPartialB",
                    "predicate": "治疗证候",
                    "object": f"SyndromePartialB{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.85,
                },
            ]
        }


class OrderRecordingPipeline(TCMTriplePipeline):
    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self.started: list[tuple[str, int]] = []

    def extract_chunk_payload(self, task, dry_run: bool):  # type: ignore[override]
        self.started.append((task.book_name, task.chunk_index))
        return {
            "triples": [
                {
                    "subject": f"Formula{task.book_name}",
                    "predicate": "治疗证候",
                    "object": f"Syndrome{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.9,
                },
                {
                    "subject": f"Formula{task.book_name}",
                    "predicate": "组成药物",
                    "object": f"Herb{task.chunk_index}",
                    "subject_type": "formula",
                    "object_type": "herb",
                    "source_text": task.text_chunk[:60],
                    "confidence": 0.88,
                }
            ]
        }


class PipelineServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.books_dir = self.root / "books"
        self.output_dir = self.root / "output"
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        book = self.books_dir / "001-test-book.txt"
        book.write_text("Formula text for chunk splitting. " * 20, encoding="utf-8")
        self.book = book

        with pipeline_server._run_lock:
            pipeline_server._current_job.clear()
            pipeline_server._job_log.clear()
            pipeline_server._job_log_file = None
            pipeline_server._job_log_file_path = None
        pipeline_server._job_cancelled.clear()

    def tearDown(self) -> None:
        pipeline_server._job_cancelled.clear()
        with pipeline_server._run_lock:
            pipeline_server._current_job.clear()
            pipeline_server._job_log.clear()
            pipeline_server._job_log_file = None
            pipeline_server._job_log_file_path = None
        self.temp_dir.cleanup()

    def test_resolve_start_selected_books_returns_all_books_when_empty(self) -> None:
        extra_book = self.books_dir / "002-test-book.txt"
        extra_book.write_text("Another formula text. " * 10, encoding="utf-8")
        pipeline = TCMTriplePipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
            )
        )

        selected = pipeline_server._resolve_start_selected_books(pipeline, [])

        self.assertEqual([path.stem for path in selected], ["001-test-book", "002-test-book"])

    def test_resolve_start_selected_books_honors_explicit_selection(self) -> None:
        extra_book = self.books_dir / "002-test-book.txt"
        extra_book.write_text("Another formula text. " * 10, encoding="utf-8")
        pipeline = TCMTriplePipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
            )
        )

        selected = pipeline_server._resolve_start_selected_books(pipeline, ["2"])

        self.assertEqual([path.stem for path in selected], ["002-test-book"])

    def test_get_processed_book_stems_only_includes_completed_full_runs(self) -> None:
        completed_run = self.output_dir / "completed-run"
        completed_run.mkdir(parents=True, exist_ok=True)
        (completed_run / "manifest.json").write_text(
            json.dumps(
                {
                    "books": [str(self.book)],
                    "dry_run": False,
                    "config": {
                        "max_chunks_per_book": None,
                        "skip_initial_chunks_per_book": 0,
                        "chapter_excludes": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (completed_run / "state.json").write_text(
            json.dumps({"status": "completed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        partial_book = self.books_dir / "002-partial-book.txt"
        partial_book.write_text("partial text " * 10, encoding="utf-8")
        partial_run = self.output_dir / "partial-run"
        partial_run.mkdir(parents=True, exist_ok=True)
        (partial_run / "manifest.json").write_text(
            json.dumps(
                {
                    "books": [str(partial_book)],
                    "dry_run": False,
                    "config": {
                        "max_chunks_per_book": 10,
                        "skip_initial_chunks_per_book": 0,
                        "chapter_excludes": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (partial_run / "state.json").write_text(
            json.dumps({"status": "completed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            processed = pipeline_server._get_processed_book_stems()

        self.assertIn(self.book.stem, processed)
        self.assertNotIn(partial_book.stem, processed)

    def test_get_processed_book_stems_includes_completed_books_from_partial_run(self) -> None:
        second_book = self.books_dir / "002-partial-done-book.txt"
        second_book.write_text("second book text " * 20, encoding="utf-8")
        partial_run = self.output_dir / "partial-run"
        partial_run.mkdir(parents=True, exist_ok=True)
        manifest = {
            "books": [str(self.book), str(second_book)],
            "model": "test-model",
            "base_url": "https://example.invalid/v1",
            "dry_run": False,
            "config": {
                "max_chunks_per_book": None,
                "skip_initial_chunks_per_book": 0,
                "chapter_excludes": [],
                "chunk_strategy": "body_first",
                "max_chunk_chars": 20,
                "chunk_overlap": 0,
            },
        }
        (partial_run / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (partial_run / "state.json").write_text(
            json.dumps({"status": "partial"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        pipeline = TCMTriplePipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                max_chunk_chars=20,
                chunk_overlap=0,
            )
        )
        completed_tasks = pipeline.schedule_book_chunks(
            book_path=self.book,
            chapter_excludes=None,
            max_chunks_per_book=None,
            skip_initial_chunks_per_book=0,
            chunk_strategy="body_first",
        )
        partial_tasks = pipeline.schedule_book_chunks(
            book_path=second_book,
            chapter_excludes=None,
            max_chunks_per_book=None,
            skip_initial_chunks_per_book=0,
            chunk_strategy="body_first",
        )
        checkpoint_rows = [
            {
                "book": task.book_name,
                "chunk_index": task.chunk_index,
                "success": True,
            }
            for task in completed_tasks
        ]
        checkpoint_rows.extend(
            {
                "book": task.book_name,
                "chunk_index": task.chunk_index,
                "success": True,
            }
            for task in partial_tasks[:-1]
        )
        (partial_run / "chunks.checkpoint.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in checkpoint_rows),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            processed = pipeline_server._get_processed_book_stems()

        self.assertIn(self.book.stem, processed)
        self.assertNotIn(second_book.stem, processed)

    def test_exclude_processed_books_for_new_run_keeps_manual_candidates_out(self) -> None:
        book_two = self.books_dir / "002-next-book.txt"
        book_two.write_text("next text " * 10, encoding="utf-8")
        with patch.object(pipeline_server, "_get_processed_book_stems", return_value={self.book.stem}):
            kept, skipped = pipeline_server._exclude_processed_books_for_new_run([self.book, book_two])

        self.assertEqual([path.stem for path in kept], [book_two.stem])
        self.assertEqual(skipped, [self.book.stem])

    def test_get_processed_book_stems_respects_force_unprocessed_override(self) -> None:
        completed_run = self.output_dir / "completed-run"
        completed_run.mkdir(parents=True, exist_ok=True)
        (completed_run / "manifest.json").write_text(
            json.dumps({"books": [str(self.book)], "dry_run": False, "config": {"max_chunks_per_book": None}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (completed_run / "state.json").write_text(
            json.dumps({"status": "completed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.output_dir / "book_status_overrides.json").write_text(
            json.dumps({"force_unprocessed": [self.book.stem]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            processed = pipeline_server._get_processed_book_stems()

        self.assertNotIn(self.book.stem, processed)

    def test_delete_books_from_runtime_graph_updates_runtime_and_marks_unprocessed(self) -> None:
        graph_target = self.root / "graph_runtime.json"
        evidence_target = self.root / "graph_runtime.evidence.jsonl"
        graph_target.write_text(
            json.dumps(
                [
                    {
                        "subject": "A",
                        "predicate": "治疗证候",
                        "object": "B",
                        "source_book": self.book.stem,
                        "source_chapter": f"{self.book.stem}_正文",
                        "fact_id": "fact-1",
                        "fact_ids": ["fact-1"],
                    },
                    {
                        "subject": "C",
                        "predicate": "治疗证候",
                        "object": "D",
                        "source_book": "002-other-book",
                        "source_chapter": "002-other-book_正文",
                        "fact_id": "fact-2",
                        "fact_ids": ["fact-2"],
                    },
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        evidence_target.write_text(
            "\n".join(
                [
                    json.dumps({"fact_id": "fact-1", "source_book": self.book.stem}, ensure_ascii=False),
                    json.dumps({"fact_id": "fact-2", "source_book": "002-other-book"}, ensure_ascii=False),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_GRAPH_TARGET", graph_target):
            with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
                payload = pipeline_server._delete_books_from_runtime_graph(
                    [self.book.stem],
                    sync_nebula=False,
                    mark_unprocessed=True,
                )

        remaining_rows = json.loads(graph_target.read_text(encoding="utf-8"))
        remaining_evidence = [line for line in evidence_target.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(payload["removed_triples"], 1)
        self.assertEqual(len(remaining_rows), 1)
        self.assertEqual(remaining_rows[0]["source_book"], "002-other-book")
        self.assertEqual(len(remaining_evidence), 1)
        self.assertIn(self.book.stem, payload["force_unprocessed"])

    def test_delete_books_from_runtime_graph_rejects_when_publish_queue_busy(self) -> None:
        graph_target = self.root / "graph_runtime.json"
        graph_target.write_text(
            json.dumps(
                [
                    {
                        "subject": "A",
                        "predicate": "治疗证候",
                        "object": "B",
                        "source_book": self.book.stem,
                        "fact_id": "fact-1",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_GRAPH_TARGET", graph_target):
            with patch.object(pipeline_server, "_active_publish_task", {"run_name": "busy-run", "kind": "json"}):
                with self.assertRaisesRegex(RuntimeError, "publish_queue_busy"):
                    pipeline_server._delete_books_from_runtime_graph(
                        [self.book.stem],
                        sync_nebula=False,
                        mark_unprocessed=False,
                    )

        remaining_rows = json.loads(graph_target.read_text(encoding="utf-8"))
        self.assertEqual(len(remaining_rows), 1)

    def test_load_graph_runtime_rows_rejects_empty_file(self) -> None:
        graph_target = self.root / "graph_runtime.json"
        graph_target.write_text("", encoding="utf-8")

        with patch.object(pipeline_server, "DEFAULT_GRAPH_TARGET", graph_target):
            with self.assertRaisesRegex(ValueError, "json_file_empty"):
                pipeline_server._load_graph_runtime_rows()

    def test_select_auto_start_books_prefers_recommended_unprocessed_and_limits_to_seven(self) -> None:
        books = [self.books_dir / f"{i:03d}-book.txt" for i in range(1, 11)]
        pipeline = Mock()
        pipeline.discover_books.return_value = books
        pipeline.recommend_books.return_value = [
            books[6],
            books[1],
            books[0],
            books[7],
            books[2],
            books[8],
            books[3],
            books[9],
            books[4],
            books[5],
        ]

        with patch.object(pipeline_server, "_get_processed_book_stems", return_value={books[0].stem, books[8].stem}):
            selected, skipped = pipeline_server._select_auto_start_books(pipeline, batch_size=7)

        self.assertEqual(
            [path.stem for path in selected],
            [
                books[6].stem,
                books[1].stem,
                books[7].stem,
                books[2].stem,
                books[3].stem,
                books[9].stem,
                books[4].stem,
            ],
        )
        self.assertEqual(skipped, [books[0].stem, books[8].stem])

    def test_run_auto_extraction_batches_chains_next_batch(self) -> None:
        batch_one = [self.books_dir / "001-a.txt", self.books_dir / "002-b.txt"]
        batch_two = [self.books_dir / "003-c.txt"]
        resume_run_dir = self.output_dir / "resume-source"
        resume_run_dir.mkdir(parents=True, exist_ok=True)

        def fake_run_extraction_job(**kwargs):
            with pipeline_server._run_lock:
                pipeline_server._current_job.clear()
                pipeline_server._current_job.update(
                    {
                        "status": "completed",
                        "phase": "finished",
                        "run_dir": f"run_{len(run_calls) + 1}",
                    }
                )
            run_calls.append(kwargs)

        run_calls: list[dict[str, object]] = []
        with patch("scripts.pipeline_server._run_extraction_job", side_effect=fake_run_extraction_job):
            with patch("scripts.pipeline_server._build_pipeline", return_value=Mock()):
                with patch(
                    "scripts.pipeline_server._select_auto_start_books",
                    side_effect=[(batch_two, []), ([], [])],
                ):
                    with patch("scripts.pipeline_server._cleanup_job_log_file") as cleanup_mock:
                        pipeline_server._run_auto_extraction_batches(
                            job_id="autobatch01",
                            initial_selected_books=batch_one,
                            initial_resume_run_dir=resume_run_dir,
                            label="auto-batch",
                            dry_run=False,
                            cfg_override={},
                            chapter_excludes=[],
                            max_chunks_per_book=None,
                            skip_initial_chunks=0,
                            chunk_strategy="body_first",
                            auto_clean=False,
                            auto_publish=False,
                            max_chunk_retries=1,
                            batch_size=7,
                        )

        self.assertEqual(len(run_calls), 2)
        self.assertEqual(run_calls[0]["selected_books"], batch_one)
        self.assertEqual(run_calls[1]["selected_books"], batch_two)
        self.assertEqual(run_calls[0]["resume_run_dir"], resume_run_dir)
        self.assertIsNone(run_calls[1]["resume_run_dir"])
        self.assertFalse(run_calls[0]["cleanup_job_log_file"])
        self.assertFalse(run_calls[1]["cleanup_job_log_file"])
        cleanup_mock.assert_called_once()

    def test_resume_run_uses_auto_batch_wrapper_by_default(self) -> None:
        run_dir = self.output_dir / "resume-default-auto"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "books": [str(self.book)],
                    "model": "resume-model",
                    "base_url": "https://example.invalid/v1",
                    "dry_run": False,
                    "config": {
                        "chapter_excludes": [],
                        "skip_initial_chunks_per_book": 0,
                        "chunk_strategy": "body_first",
                        "parallel_workers": 4,
                        "max_chunk_retries": 2,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        thread_args: dict[str, object] = {}

        class FakeThread:
            def __init__(self, *, target=None, kwargs=None, daemon=None):
                thread_args["target"] = target
                thread_args["kwargs"] = kwargs or {}
                thread_args["daemon"] = daemon

            def start(self):
                thread_args["started"] = True

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            with patch("scripts.pipeline_server.threading.Thread", FakeThread):
                payload = pipeline_server.resume_run(
                    "resume-default-auto",
                    pipeline_server.ResumeRunRequest(),
                )

        self.assertEqual(payload["message"], "resume_started")
        self.assertTrue(payload["auto_chain_mode"])
        self.assertEqual(payload["auto_batch_size"], 7)
        self.assertIs(thread_args["target"], pipeline_server._run_auto_extraction_batches)
        self.assertEqual(thread_args["kwargs"]["initial_selected_books"], [self.book])
        self.assertEqual(thread_args["kwargs"]["initial_resume_run_dir"], run_dir)
        self.assertTrue(thread_args["started"])

    def test_resolve_run_publish_source_prefers_cleaned_graph_file(self) -> None:
        run_dir = self.output_dir / "publish-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        cleaned_path = run_dir / "graph_facts.cleaned.json"
        evidence_path = run_dir / "evidence_metadata.jsonl"
        raw_path = run_dir / "graph_import.json"
        cleaned_path.write_text("[]", encoding="utf-8")
        evidence_path.write_text("", encoding="utf-8")
        raw_path.write_text("[]", encoding="utf-8")

        graph_path, resolved_evidence = pipeline_server._resolve_run_publish_source(run_dir)

        self.assertEqual(graph_path, cleaned_path)
        self.assertEqual(resolved_evidence, evidence_path)

    def test_resolve_run_publish_source_falls_back_to_raw_graph_import(self) -> None:
        run_dir = self.output_dir / "publish-run-raw"
        run_dir.mkdir(parents=True, exist_ok=True)
        raw_path = run_dir / "graph_import.json"
        raw_path.write_text("[]", encoding="utf-8")

        graph_path, resolved_evidence = pipeline_server._resolve_run_publish_source(run_dir)

        self.assertEqual(graph_path, raw_path)
        self.assertIsNone(resolved_evidence)

    def test_run_extraction_job_processes_parallel_chunks(self) -> None:
        pipeline = CountingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=4,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="job12345",
                selected_books=[self.book],
                label="parallel-check",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=3,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
            )

        self.assertEqual(pipeline.calls, 3)
        self.assertEqual(pipeline_server._current_job.get("status"), "completed")
        self.assertEqual(pipeline_server._current_job.get("total_triples"), 6)
        self.assertTrue(any("[parallel] progress" in entry.get("msg", "") for entry in pipeline_server._job_log))

        run_dir = Path(str(pipeline_server._current_job["run_dir"]))
        triples_jsonl = run_dir / "triples.normalized.jsonl"
        self.assertTrue(triples_jsonl.exists())
        rows = [line for line in triples_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 6)

    def test_run_extraction_job_interleaves_chunks_across_books(self) -> None:
        second_book = self.books_dir / "002-second-book.txt"
        second_book.write_text("Second book text for chunk splitting. " * 20, encoding="utf-8")
        pipeline = OrderRecordingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=1,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="interleave01",
                selected_books=[self.book, second_book],
                label="interleave-check",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=2,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=0,
            )

        self.assertEqual(
            pipeline.started[:4],
            [
                (self.book.stem, 1),
                (second_book.stem, 1),
                (self.book.stem, 2),
                (second_book.stem, 2),
            ],
        )
        self.assertEqual(pipeline_server._current_job.get("status"), "completed")

    def test_run_extraction_job_resume_skips_completed_chunks(self) -> None:
        run_dir = self.output_dir / "resume-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "books": [str(self.book)],
                    "model": "test-model",
                    "base_url": "https://example.invalid/v1",
                    "dry_run": False,
                    "config": {
                        "chapter_excludes": [],
                        "skip_initial_chunks_per_book": 0,
                        "chunk_strategy": "body_first",
                        "parallel_workers": 4,
                        "max_chunk_chars": 20,
                        "chunk_overlap": 0,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (run_dir / "state.json").write_text(
            json.dumps({"status": "paused", "chunks_completed": 1, "total_triples": 1}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "triples.normalized.jsonl").write_text(
            json.dumps(
                {
                    "subject": "ExistingFormula",
                    "predicate": "治疗证候",
                    "object": "ExistingSyndrome",
                    "subject_type": "formula",
                    "object_type": "syndrome",
                    "source_book": self.book.stem,
                    "source_chapter": f"{self.book.stem}_正文",
                    "source_text": "existing chunk",
                    "confidence": 0.9,
                    "raw_predicate": "主治",
                    "raw_subject_type": "formula",
                    "raw_object_type": "syndrome",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "triples.raw.jsonl").write_text(
            json.dumps({"book": self.book.stem, "chapter": f"{self.book.stem}_正文", "chunk_index": 1, "payload": {"triples": [{"subject": "ExistingFormula"}]}, "error": None}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "chunks.checkpoint.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-03-30T01:00:00",
                    "book": self.book.stem,
                    "chapter": f"{self.book.stem}_正文",
                    "chunk_index": 1,
                    "sequence": 1,
                    "success": True,
                    "error": None,
                    "triples_count": 1,
                    "attempt": 0,
                    "resumed": False,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        pipeline = CountingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=4,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="resume01",
                selected_books=[self.book],
                label="resume-run",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=3,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
                resume_run_dir=run_dir,
            )

        self.assertEqual(pipeline.calls, 2)
        rows = [line for line in (run_dir / "triples.normalized.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 5)
        checkpoint_rows = [line for line in (run_dir / "chunks.checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(checkpoint_rows), 3)

    def test_run_resume_config_returns_manifest_defaults(self) -> None:
        run_dir = self.output_dir / "resume-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "model": "resume-model",
                    "base_url": "https://example.invalid/v1",
                    "dry_run": False,
                    "config": {
                        "request_timeout": 123.0,
                        "max_retries": 5,
                        "request_delay": 1.5,
                        "retry_backoff_base": 3.0,
                        "parallel_workers": 7,
                        "max_chunk_retries": 4,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "status": "cancelled",
                    "chunks_completed": 20,
                    "chunks_total": 80,
                    "books_completed": 1,
                    "books_total": 3,
                    "total_triples": 563,
                    "chunk_errors": 2,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            payload = pipeline_server.run_resume_config("resume-run")

        self.assertEqual(payload["run_dir"], "resume-run")
        self.assertEqual(payload["api_config"]["model"], "resume-model")
        self.assertEqual(payload["api_config"]["parallel_workers"], 7)
        self.assertEqual(payload["progress"]["chunks_completed"], 20)

    def test_load_completed_chunk_keys_uses_latest_checkpoint_status(self) -> None:
        run_dir = self.output_dir / "checkpoint-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = run_dir / "chunks.checkpoint.jsonl"
        checkpoint_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "book": "test-book",
                            "chunk_index": 1,
                            "success": True,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "book": "test-book",
                            "chunk_index": 1,
                            "success": False,
                            "error": "marked_incomplete_low_yield: triples_count=1",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        completed = pipeline_server._load_completed_chunk_keys(run_dir)

        self.assertNotIn(("test-book", 1), completed)

    def test_update_runtime_metrics_for_resume_excludes_historical_completed_chunks(self) -> None:
        state = {}
        with patch("scripts.pipeline_server.time.time", return_value=110.0):
            pipeline_server._update_runtime_metrics(
                state,
                start_ts=100.0,
                session_chunks_done=2,
                total_chunks_done=42,
                total_chunks_all=100,
            )

        self.assertEqual(state["elapsed_secs"], 10)
        self.assertEqual(state["chunks_completed"], 42)
        self.assertEqual(state["speed_chunks_per_min"], 12.0)
        self.assertEqual(state["eta"], "4分50秒")

    def test_derive_retry_parallel_workers_uses_half_of_main_parallelism(self) -> None:
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(None), 1)
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(0), 1)
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(1), 1)
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(2), 1)
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(4), 2)
        self.assertEqual(pipeline_server._derive_retry_parallel_workers(7), 3)

    def test_run_extraction_job_cancelled_before_processing_stays_cancelled(self) -> None:
        pipeline = CountingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=4,
            )
        )

        pipeline_server._job_cancelled.set()
        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="cancel01",
                selected_books=[self.book],
                label="cancelled-run",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=3,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
            )

        self.assertEqual(pipeline.calls, 0)
        self.assertEqual(pipeline_server._current_job.get("status"), "cancelled")

    def test_cancel_job_marks_current_state_as_cancelling(self) -> None:
        run_dir = self.output_dir / "job-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        with pipeline_server._run_lock:
            pipeline_server._current_job = {
                "status": "running",
                "phase": "extracting",
                "run_dir": str(run_dir),
            }
        pipeline_server._job_cancelled.clear()

        resp = pipeline_server.cancel_job()

        self.assertTrue(pipeline_server._job_cancelled.is_set())
        self.assertEqual(resp["status"], "cancelling")
        self.assertEqual(pipeline_server._current_job.get("status"), "cancelling")
        self.assertTrue((run_dir / "state.json").exists())

    def test_retry_single_dict_payload_counts_toward_total(self) -> None:
        pipeline = RetrySingleDictPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=1,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="retrydict",
                selected_books=[self.book],
                label="retry-dict",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=1,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
            )

        run_dir = Path(str(pipeline_server._current_job["run_dir"]))
        triples_path = run_dir / "triples.normalized.jsonl"
        rows = [line for line in triples_path.read_text(encoding="utf-8").splitlines() if line.strip()] if triples_path.exists() else []
        checkpoint_rows = [json.loads(line) for line in (run_dir / "chunks.checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(pipeline_server._current_job.get("total_triples"), 0)
        self.assertEqual(len(rows), 0)
        self.assertEqual(pipeline_server._current_job.get("status"), "completed")
        self.assertEqual(pipeline_server._current_job.get("pending_chunks", 0), 0)
        self.assertEqual(checkpoint_rows[-1]["error"], "dropped_after_low_yield_retries: low_yield_retry: triples_count=1")
        self.assertEqual(checkpoint_rows[-1]["triples_count"], 0)
        self.assertTrue(checkpoint_rows[-1]["success"])

    def test_low_yield_parallel_chunk_retries_without_double_counting(self) -> None:
        pipeline = LowYieldRetryPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=4,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="lowyield01",
                selected_books=[self.book],
                label="low-yield-retry",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=2,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
            )

        run_dir = Path(str(pipeline_server._current_job["run_dir"]))
        rows = [line for line in (run_dir / "triples.normalized.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        checkpoint_rows = [json.loads(line) for line in (run_dir / "chunks.checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        chunk_one_rows = [row for row in checkpoint_rows if row["chunk_index"] == 1]

        self.assertEqual(pipeline_server._current_job.get("total_triples"), 5)
        self.assertEqual(len(rows), 5)
        self.assertTrue(any(row["error"] == "low_yield_retry: triples_count=1" for row in chunk_one_rows))
        self.assertTrue(any(row["success"] is True and row["triples_count"] == 3 for row in chunk_one_rows))

    def test_persistent_low_yield_chunks_are_dropped_and_do_not_leave_partial_run(self) -> None:
        pipeline = PersistentLowYieldPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=4,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="persistlow01",
                selected_books=[self.book],
                label="persistent-low-yield",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=2,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=1,
            )

        run_dir = Path(str(pipeline_server._current_job["run_dir"]))
        checkpoint_rows = [json.loads(line) for line in (run_dir / "chunks.checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        chunk_one_rows = [row for row in checkpoint_rows if row["chunk_index"] == 1]
        triples_rows = [line for line in (run_dir / "triples.normalized.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(pipeline_server._current_job.get("status"), "completed")
        self.assertEqual(pipeline_server._current_job.get("pending_chunks", 0), 0)
        self.assertEqual(pipeline_server._current_job.get("total_triples"), 2)
        self.assertEqual(len(triples_rows), 2)
        self.assertTrue(any(row["error"] == "dropped_after_low_yield_retries: low_yield_retry: triples_count=1" and row["success"] is True for row in chunk_one_rows))

    def test_book_still_completes_when_some_chunks_fail_after_retry_exhaustion(self) -> None:
        pipeline = PartialSuccessPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=1,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="partialbook",
                selected_books=[self.book],
                label="partial-book",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=2,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=0,
            )

        run_dir = Path(str(pipeline_server._current_job["run_dir"]))
        checkpoint_rows = [json.loads(line) for line in (run_dir / "chunks.checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(pipeline_server._current_job.get("books_completed"), 1)
        self.assertEqual(pipeline_server._current_job.get("status"), "completed")
        self.assertEqual(pipeline_server._current_job.get("pending_chunks", 0), 0)
        self.assertTrue(any(str(row.get("error", "")).startswith("dropped_after_retries:") and row.get("success") is True for row in checkpoint_rows))

    def test_run_extraction_job_does_not_emit_provider_monitor_log_lines(self) -> None:
        pipeline = CountingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=2,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="nolog01",
                selected_books=[self.book],
                label="no-provider-monitor-log",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=1,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=0,
            )

        self.assertFalse(any("[provider-monitor]" in entry.get("msg", "") for entry in pipeline_server._job_log))

    def test_resume_metrics_only_count_completed_chunks_within_selected_books(self) -> None:
        resume_run = self.output_dir / "resume-metrics-run"
        resume_run.mkdir(parents=True, exist_ok=True)
        other_book = self.books_dir / "other-book.txt"
        other_book.write_text("<篇名>其他书\nABCDEFGHIJABCDEFGHIJ", encoding="utf-8")
        checkpoint_rows = [
            {
                "book": self.book.stem,
                "chapter": f"{self.book.stem}_正文",
                "chunk_index": 1,
                "success": True,
                "error": None,
                "triples_count": 1,
            },
            {
                "book": other_book.stem,
                "chapter": f"{other_book.stem}_正文",
                "chunk_index": 1,
                "success": True,
                "error": None,
                "triples_count": 1,
            },
        ]
        (resume_run / "chunks.checkpoint.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in checkpoint_rows) + "\n",
            encoding="utf-8",
        )
        (resume_run / "triples.normalized.jsonl").write_text("", encoding="utf-8")
        (resume_run / "triples.raw.jsonl").write_text("", encoding="utf-8")

        pipeline = CountingPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="test-model",
                api_key="test-key",
                base_url="https://example.invalid/v1",
                request_delay=0.0,
                max_chunk_chars=20,
                chunk_overlap=0,
                parallel_workers=1,
            )
        )

        with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
            pipeline_server._run_extraction_job(
                job_id="resume-metrics",
                selected_books=[self.book],
                label="resume-metrics",
                dry_run=False,
                cfg_override={},
                chapter_excludes=[],
                max_chunks_per_book=2,
                skip_initial_chunks=0,
                chunk_strategy="body_first",
                auto_clean=False,
                auto_publish=False,
                max_chunk_retries=0,
                resume_run_dir=resume_run,
            )

        self.assertEqual(pipeline_server._current_job.get("chunks_total"), 2)
        self.assertEqual(pipeline_server._current_job.get("resume_skipped_chunks"), 1)
        self.assertEqual(pipeline_server._current_job.get("chunks_completed"), 2)

    def test_run_triples_prefers_cleaned_rows(self) -> None:
        run_dir = self.output_dir / "triples-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        cleaned_row = {
            "subject": "CleanedFormula",
            "predicate": "治疗证候",
            "object": "CleanedSyndrome",
            "source_book": "TestBook",
            "source_text": "cleaned source",
            "confidence": 0.9,
        }
        normalized_row = {
            "subject": "NormalizedFormula",
            "predicate": "治疗证候",
            "object": "NormalizedSyndrome",
            "source_book": "TestBook",
            "source_text": "normalized source",
            "confidence": 0.8,
        }
        (run_dir / "triples.cleaned.jsonl").write_text(json.dumps(cleaned_row, ensure_ascii=False) + "\n", encoding="utf-8")
        (run_dir / "triples.normalized.jsonl").write_text(json.dumps(normalized_row, ensure_ascii=False) + "\n", encoding="utf-8")

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            payload = pipeline_server.run_triples("triples-run", limit=10)

        self.assertEqual(payload["source_kind"], "cleaned")
        self.assertEqual(payload["rows"][0]["subject"], "CleanedFormula")

    def test_run_publish_records_json_publish_status(self) -> None:
        run_dir = self.output_dir / "publish-status-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        target = self.root / "graph_runtime.json"
        target.write_text(
            json.dumps(
                [
                    {"subject": "A", "predicate": "治疗证候", "object": "B"},
                    {"subject": "C", "predicate": "治疗证候", "object": "D"},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.root / "graph_runtime.evidence.jsonl").write_text(
            json.dumps({"fact_id": "f1"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        pipeline = Mock()
        pipeline.publish_graph.return_value = target

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            with patch("scripts.pipeline_server._build_pipeline", return_value=pipeline):
                payload = pipeline_server._run_json_publish_job("publish-status-run")

        self.assertEqual(payload["graph_triples"], 2)
        publish_status = json.loads((run_dir / "publish_status.json").read_text(encoding="utf-8"))
        self.assertTrue(publish_status["json"]["published"])
        self.assertEqual(publish_status["json"]["graph_triples"], 2)
        self.assertEqual(publish_status["json"]["evidence_count"], 1)

    def test_list_runs_includes_publish_status_summary(self) -> None:
        run_dir = self.output_dir / "publish-list-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"created_at": "2026-03-30T20:00:00", "dry_run": False}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "state.json").write_text(
            json.dumps({"status": "completed", "books_total": 1, "books_completed": 1}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "publish_status.json").write_text(
            json.dumps(
                {
                    "json": {"status": "completed", "published": True, "published_at": "2026-03-30T20:10:00"},
                    "nebula": {"status": "running", "published": False, "progress_current": 5, "progress_total": 10},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with patch.object(pipeline_server, "DEFAULT_OUTPUT_DIR", self.output_dir):
            payload = pipeline_server.list_runs()

        self.assertEqual(len(payload["runs"]), 1)
        self.assertTrue(payload["runs"][0]["publish_status"]["json"]["published"])
        self.assertEqual(payload["runs"][0]["publish_status"]["nebula"]["status"], "running")


if __name__ == "__main__":
    unittest.main()
