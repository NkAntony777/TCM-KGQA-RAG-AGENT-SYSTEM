from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.tcm_triple_console import PipelineConfig
from scripts.tcm_triple_console import TCMTriplePipeline
from scripts.tcm_triple_console import _extract_all_json_blocks
from scripts.tcm_triple_console import _detect_formula_titles
from scripts.tcm_triple_console import _extract_json_block
from scripts.tcm_triple_console import resolve_chapter_excludes


class TCMTripleConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.books_dir = self.root / "books"
        self.output_dir = self.root / "output"
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = TCMTriplePipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="deepseek-ai/DeepSeek-V3.2",
                api_key="test-key",
                base_url="https://api.siliconflow.cn/v1",
                request_delay=0.0,
            )
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_split_book_respects_chapter_markers(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<卷一>\n逍遥散主肝郁脾虚证。\n<卷二>\n柴胡味苦。", encoding="utf-8")

        sections = self.pipeline.split_book(book)

        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "卷一")
        self.assertIn("逍遥散", sections[0]["content"])
        self.assertEqual(sections[1]["title"], "卷二")

    def test_schedule_book_chunks_body_first_uses_body_label_for_weak_titles(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<篇名>\n前言内容。\n<目录>\n目录内容。\n<卷一>\n桂枝汤主太阳中风。", encoding="utf-8")

        tasks = self.pipeline.schedule_book_chunks(
            book_path=book,
            chunk_strategy="body_first",
            max_chunks_per_book=4,
        )

        self.assertGreaterEqual(len(tasks), 1)
        self.assertIn(tasks[0].chapter_name, {"001-测试方书_正文", "卷一"})

    def test_normalize_triples_maps_relations_and_types(self) -> None:
        rows = self.pipeline.normalize_triples(
            payload={
                "triples": [
                    {
                        "subject": "逍遥散",
                        "predicate": "主治",
                        "object": "肝郁脾虚证",
                        "subject_type": "",
                        "object_type": "",
                        "source_text": "逍遥散主肝郁脾虚证。",
                        "confidence": 0.92,
                    }
                ]
            },
            book_name="医方集解",
            chapter_name="卷一",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].predicate, "治疗证候")
        self.assertEqual(rows[0].subject_type, "formula")
        self.assertEqual(rows[0].object_type, "syndrome")

    def test_normalize_triples_accepts_single_triple_dict_payload(self) -> None:
        rows = self.pipeline.normalize_triples(
            payload={
                "subject": "五苓散",
                "predicate": "主治",
                "object": "小便不利",
                "subject_type": "formula",
                "object_type": "symptom",
                "source_text": "五苓散主小便不利。",
                "confidence": 0.95,
            },
            book_name="医方论",
            chapter_name="卷三",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].subject, "五苓散")
        self.assertEqual(rows[0].predicate, "治疗证候")

    def test_extract_json_block_handles_think_and_single_quotes(self) -> None:
        payload = _extract_json_block(
            """
            <think>先分析一下</think>
            ```json
            {'triples': [{'subject': '桂枝汤', 'predicate': '主治', 'object': '太阳中风证', 'source_text': '桂枝汤主太阳中风证', 'confidence': 0.9}]}
            ```
            """
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["triples"][0]["subject"], "桂枝汤")

    def test_extract_json_block_handles_trailing_commas(self) -> None:
        payload = _extract_json_block(
            """
            下面是结果：
            {
              "triples": [
                {
                  "subject": "桂枝汤",
                  "predicate": "主治",
                  "object": "太阳中风证",
                  "source_text": "桂枝汤主太阳中风证",
                  "confidence": 0.9,
                }
              ],
            }
            """
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(len(payload["triples"]), 1)

    def test_extract_all_json_blocks_collects_multiple_payloads(self) -> None:
        payloads = _extract_all_json_blocks(
            """
            先给一个示例：
            {"triples":[{"subject":"甲方","predicate":"主治","object":"证A","source_text":"甲方主治证A","confidence":0.9}]}
            最终结果：
            {"triples":[
              {"subject":"乙方","predicate":"主治","object":"证B","source_text":"乙方主治证B","confidence":0.9},
              {"subject":"丙方","predicate":"主治","object":"证C","source_text":"丙方主治证C","confidence":0.9}
            ]}
            """
        )

        self.assertEqual(len(payloads), 2)
        self.assertEqual(len(payloads[0]["triples"]), 1)
        self.assertEqual(len(payloads[1]["triples"]), 2)

    def test_extract_json_block_recovers_fragmented_multiple_triples(self) -> None:
        payload = _extract_json_block(
            """
            {"triples":[{"subject":"甲方","predicate":"主治","object":"证A","source_text":"甲方主治证A","confidence":0.9}]}
            {"subject":"乙方","predicate":"主治","object":"证B","source_text":"乙方主治证B","confidence":0.9}
            {"subject":"丙方","predicate":"主治","object":"证C","source_text":"丙方主治证C","confidence":0.9}
            """
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(len(payload["triples"]), 3)

    def test_extract_json_block_recovers_field_fragments_without_balanced_braces(self) -> None:
        payload = _extract_json_block(
            """
            输出如下，请直接使用：
            "subject":"桂枝汤","predicate":"主治","object":"太阳中风证","subject_type":"formula","object_type":"syndrome","source_text":"桂枝汤主太阳中风证","confidence":0.95
            "subject":"桂枝","predicate":"归经","object":"膀胱经","subject_type":"herb","object_type":"channel","source_text":"桂枝入膀胱经","confidence":0.88
            """
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(len(payload["triples"]), 2)
        self.assertEqual(payload["triples"][0]["subject"], "桂枝汤")
        self.assertEqual(payload["triples"][1]["predicate"], "归经")

    def test_extract_json_block_recovers_single_quoted_fragment_series(self) -> None:
        payload = _extract_json_block(
            """
            {'subject':'麻黄汤','predicate':'主治','object':'太阳伤寒证','source_text':'麻黄汤主太阳伤寒证','confidence':0.91
            'subject':'麻黄','predicate':'使用药材','object':'杏仁','source_text':'麻黄 杏仁','confidence':0.86}
            """
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(len(payload["triples"]), 2)
        self.assertEqual(payload["triples"][0]["object"], "太阳伤寒证")
        self.assertEqual(payload["triples"][1]["subject"], "麻黄")

    def test_detect_formula_titles_from_chunk_text(self) -> None:
        text = """
        卷一\\补养之剂

        黑地黄丸

        属性：苍术 熟地黄 五味子 干姜

        卷一\\补养之剂

        虎潜丸

        属性：黄柏 知母 熟地黄 虎胫骨
        """

        titles = _detect_formula_titles(text)

        self.assertEqual(titles, ["黑地黄丸", "虎潜丸"])

    def test_extract_chunk_payload_preserves_llm_meta(self) -> None:
        class MetaPipeline(TCMTriplePipeline):
            def call_llm(self, prompt: str) -> dict[str, object]:
                return {
                    "triples": [
                        {
                            "subject": "桂枝汤",
                            "predicate": "主治",
                            "object": "太阳中风证",
                            "subject_type": "formula",
                            "object_type": "syndrome",
                            "source_text": "桂枝汤主太阳中风证。",
                            "confidence": 0.9,
                        }
                    ],
                    "__meta__": {
                        "raw_text": "{\"triples\":[...]}",
                        "usage": {"completion_tokens": 1234},
                        "finish_reason": "stop",
                        "response_format_mode": "json_object",
                    },
                }

        pipeline = MetaPipeline(self.pipeline.config)
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<卷一>\n桂枝汤主太阳中风证。", encoding="utf-8")
        task = pipeline.schedule_book_chunks(book_path=book, max_chunks_per_book=1)[0]

        payload = pipeline.extract_chunk_payload(task, dry_run=False)

        self.assertIn("__meta__", payload)
        self.assertEqual(payload["__meta__"]["usage"]["completion_tokens"], 1234)
        self.assertEqual(payload["__meta__"]["response_format_mode"], "json_object")

    def test_extract_books_dry_run_writes_pipeline_outputs(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<卷一>\n逍遥散主肝郁脾虚证。", encoding="utf-8")

        run_dir = self.pipeline.extract_books(
            selected_books=[book],
            label="dry-run-check",
            max_chunks_per_book=1,
            dry_run=True,
        )

        self.assertTrue((run_dir / "manifest.json").exists())
        self.assertTrue((run_dir / "state.json").exists())
        self.assertTrue((run_dir / "triples.normalized.jsonl").exists())
        self.assertTrue((run_dir / "graph_import.json").exists())

        summary = self.pipeline.summarize_run_dir(run_dir)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["books_completed"], 1)
        self.assertGreaterEqual(summary["total_triples"], 1)

    def test_extract_books_can_filter_chapters(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<篇名>\n作者：某某。\n<卷一>\n逍遥散主肝郁脾虚证。", encoding="utf-8")

        run_dir = self.pipeline.extract_books(
            selected_books=[book],
            label="filter-check",
            max_chunks_per_book=1,
            dry_run=True,
            chapter_contains=["卷一"],
            chapter_excludes=["篇名"],
        )

        payload = json.loads((run_dir / "graph_import.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["object"], "卷一")

    def test_resolve_chapter_excludes_appends_defaults(self) -> None:
        excludes = resolve_chapter_excludes("附录,凡例", use_default_excludes=True)
        self.assertIsNotNone(excludes)
        assert excludes is not None
        self.assertIn("篇名", excludes)
        self.assertIn("目录", excludes)
        self.assertIn("附录", excludes)
        self.assertEqual(excludes.count("凡例"), 1)

    def test_extract_books_can_skip_initial_chunks(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("第一段。\n\n第二段。", encoding="utf-8")
        self.pipeline.config.max_chunk_chars = 4
        self.pipeline.config.chunk_overlap = 0

        run_dir = self.pipeline.extract_books(
            selected_books=[book],
            label="skip-chunk-check",
            max_chunks_per_book=2,
            dry_run=True,
            skip_initial_chunks_per_book=1,
        )

        payload = json.loads((run_dir / "graph_import.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 2)

    def test_skip_initial_chunks_does_not_consume_process_limit(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("第一段。\n\n第二段。\n\n第三段。", encoding="utf-8")
        self.pipeline.config.max_chunk_chars = 4
        self.pipeline.config.chunk_overlap = 0

        run_dir = self.pipeline.extract_books(
            selected_books=[book],
            label="skip-limit-check",
            max_chunks_per_book=1,
            dry_run=True,
            skip_initial_chunks_per_book=2,
        )

        payload = json.loads((run_dir / "graph_import.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 1)

    def test_publish_graph_merges_and_dedupes_rows(self) -> None:
        run_dir = self.output_dir / "20260328_publish_case"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "graph_import.json").write_text(
            json.dumps(
                [
                    {
                        "subject": "逍遥散",
                        "predicate": "治疗证候",
                        "object": "肝郁脾虚",
                        "subject_type": "formula",
                        "object_type": "syndrome",
                        "source_book": "医方集解",
                        "source_chapter": "卷一",
                    },
                    {
                        "subject": "逍遥散",
                        "predicate": "治疗证候",
                        "object": "肝郁脾虚",
                        "subject_type": "formula",
                        "object_type": "syndrome",
                        "source_book": "医方集解",
                        "source_chapter": "卷一",
                    },
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        target = self.root / "graph_runtime.json"
        target.write_text(
            json.dumps(
                [
                    {
                        "subject": "柴胡",
                        "predicate": "功效",
                        "object": "疏肝解郁",
                        "subject_type": "herb",
                        "object_type": "therapy",
                        "source_book": "本草纲目",
                        "source_chapter": "草部",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        published = self.pipeline.publish_graph(run_dir=run_dir, target_path=target, replace=False)

        self.assertEqual(published, target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 2)
        self.assertEqual({row["subject"] for row in payload}, {"柴胡", "逍遥散"})

    def test_publish_graph_prefers_cleaned_graph_facts_when_present(self) -> None:
        run_dir = self.output_dir / "20260328_publish_cleaned_case"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "graph_import.json").write_text(
            json.dumps(
                [
                    {"subject": "旧数据", "predicate": "功效", "object": "旧对象"},
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (run_dir / "graph_facts.cleaned.json").write_text(
            json.dumps(
                [
                    {
                        "fact_id": "fact-1",
                        "subject": "新数据",
                        "predicate": "使用药材",
                        "object": "甘草",
                        "subject_type": "formula",
                        "object_type": "herb",
                        "source_book": "测试书",
                        "source_chapter": "正文",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        target = self.root / "graph_runtime_prefer_cleaned.json"
        published = self.pipeline.publish_graph(run_dir=run_dir, target_path=target, replace=True)

        self.assertEqual(published, target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["subject"], "新数据")
        self.assertEqual(payload[0]["fact_id"], "fact-1")

    def test_publish_graph_also_writes_runtime_evidence_file(self) -> None:
        run_dir = self.output_dir / "20260328_publish_evidence_case"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "graph_facts.cleaned.json").write_text(
            json.dumps(
                [
                    {
                        "fact_id": "fact-1",
                        "subject": "测试方",
                        "predicate": "使用药材",
                        "object": "甘草",
                        "subject_type": "formula",
                        "object_type": "herb",
                        "source_book": "测试书",
                        "source_chapter": "正文",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (run_dir / "evidence_metadata.jsonl").write_text(
            json.dumps(
                {
                    "fact_id": "fact-1",
                    "source_book": "测试书",
                    "source_chapter": "正文",
                    "source_text": "测试方使用甘草。",
                    "confidence": 0.95,
                },
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        target = self.root / "graph_runtime_with_evidence.json"
        published = self.pipeline.publish_graph(run_dir=run_dir, target_path=target, replace=True)

        self.assertEqual(published, target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["fact_id"], "fact-1")
        self.assertEqual(payload[0]["fact_ids"], ["fact-1"])

        evidence_target = self.root / "graph_runtime_with_evidence.evidence.jsonl"
        self.assertTrue(evidence_target.exists())
        evidence_rows = evidence_target.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(evidence_rows), 1)
        evidence = json.loads(evidence_rows[0])
        self.assertEqual(evidence["fact_id"], "fact-1")
        self.assertEqual(evidence["source_text"], "测试方使用甘草。")

    def test_audit_run_dir_returns_sample_rows(self) -> None:
        book = self.books_dir / "001-测试方书.txt"
        book.write_text("<卷一>\n逍遥散主肝郁脾虚证。", encoding="utf-8")

        run_dir = self.pipeline.extract_books(
            selected_books=[book],
            label="audit-check",
            max_chunks_per_book=1,
            dry_run=True,
        )

        audit = self.pipeline.audit_run_dir(run_dir, limit=3)
        self.assertEqual(audit["summary"]["status"], "completed")
        self.assertEqual(len(audit["sample_rows"]), 1)
        self.assertEqual(audit["sample_rows"][0]["predicate"], "出处")

    def test_clean_run_dir_drops_bibliographic_noise_and_keeps_domain_fact(self) -> None:
        run_dir = self.output_dir / "clean_case"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "triples.normalized.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "subject": "伤寒杂病论",
                            "predicate": "出处",
                            "object": "广西人民出版社1980年第二版",
                            "subject_type": "book",
                            "object_type": "other",
                            "source_book": "100-桂林古本伤寒杂病论",
                            "source_chapter": "正文",
                            "source_text": "据广西人民出版社1980年第二版。",
                            "confidence": 1.0,
                            "raw_predicate": "出处",
                            "raw_subject_type": "book",
                            "raw_object_type": "other",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "subject": "桂枝汤",
                            "predicate": "使用药材",
                            "object": "桂枝",
                            "subject_type": "formula",
                            "object_type": "herb",
                            "source_book": "短文本测试",
                            "source_chapter": "测试",
                            "source_text": "使用桂枝",
                            "confidence": 1.0,
                            "raw_predicate": "使用药材",
                            "raw_subject_type": "formula",
                            "raw_object_type": "herb",
                        },
                        ensure_ascii=False,
                    ),
                ]
            ) + "\n",
            encoding="utf-8",
        )

        report = self.pipeline.clean_run_dir(run_dir)

        self.assertEqual(report["input_total"], 2)
        self.assertEqual(report["kept_total"], 1)
        cleaned_rows = (run_dir / "triples.cleaned.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(cleaned_rows), 1)
        self.assertIn("桂枝汤", cleaned_rows[0])
        graph_fact_rows = (run_dir / "graph_facts.cleaned.jsonl").read_text(encoding="utf-8").strip().splitlines()
        evidence_rows = (run_dir / "evidence_metadata.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(graph_fact_rows), 1)
        self.assertEqual(len(evidence_rows), 1)
        fact = json.loads(graph_fact_rows[0])
        evidence = json.loads(evidence_rows[0])
        self.assertEqual(fact["fact_id"], evidence["fact_id"])
        self.assertEqual(fact["subject"], "桂枝汤")
        self.assertEqual(evidence["source_text"], "使用桂枝")

    def test_extract_books_continues_when_single_chunk_fails(self) -> None:
        class FlakyPipeline(TCMTriplePipeline):
            def __init__(self, config: PipelineConfig) -> None:
                super().__init__(config)
                self.calls = 0

            def call_llm(self, prompt: str) -> dict[str, object]:
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("transient_error")
                return {
                    "triples": [
                        {
                            "subject": "桂枝汤",
                            "predicate": "主治",
                            "object": "太阳中风证",
                            "subject_type": "formula",
                            "object_type": "syndrome",
                            "source_text": "桂枝汤主太阳中风证。",
                            "confidence": 0.9,
                        }
                    ]
                }

        book = self.books_dir / "001-测试方书.txt"
        book.write_text("第一段。\n\n第二段。", encoding="utf-8")
        flaky = FlakyPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="m",
                api_key="k",
                base_url="u",
                request_delay=0.0,
                max_chunk_chars=4,
                chunk_overlap=0,
                parallel_workers=1,
            )
        )

        run_dir = flaky.extract_books(
            selected_books=[book],
            label="flaky-check",
            max_chunks_per_book=2,
            dry_run=False,
        )

        audit = flaky.audit_run_dir(run_dir, limit=5)
        self.assertEqual(audit["summary"]["status"], "completed")
        self.assertEqual(audit["summary"]["total_triples"], 1)
        self.assertEqual(audit["summary"]["books_completed"], 1)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["chunk_errors"], 1)


if __name__ == "__main__":
    unittest.main()
