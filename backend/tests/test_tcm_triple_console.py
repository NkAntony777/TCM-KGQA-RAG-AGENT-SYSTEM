from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.tcm_triple_console import PipelineConfig
from scripts.tcm_triple_console import LLMProviderConfig
from scripts.tcm_triple_console import TCMTriplePipeline
from scripts.tcm_triple_console import _extract_all_json_blocks
from scripts.tcm_triple_console import _detect_formula_titles
from scripts.tcm_triple_console import _extract_json_block
from scripts.tcm_triple_console import _normalize_provider_configs
from scripts.tcm_triple_console import _write_text_atomic
from scripts.tcm_triple_console import httpx
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

    def test_write_text_atomic_retries_after_permission_error(self) -> None:
        target = self.root / "publish_status.json"
        real_replace = os.replace
        calls = {"count": 0}

        def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            calls["count"] += 1
            if calls["count"] == 1:
                raise PermissionError(5, "Access is denied")
            real_replace(src, dst)

        with mock.patch("scripts.tcm_triple_console.os.replace", side_effect=flaky_replace):
            with mock.patch("scripts.tcm_triple_console.time.sleep", return_value=None):
                _write_text_atomic(target, '{"status":"queued"}', encoding="utf-8")

        self.assertEqual(target.read_text(encoding="utf-8"), '{"status":"queued"}')
        self.assertEqual(calls["count"], 2)

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

    def test_normalize_triples_supports_new_relations_and_entity_types(self) -> None:
        rows = self.pipeline.normalize_triples(
            payload={
                "triples": [
                    {
                        "subject": "附子",
                        "predicate": "四气",
                        "object": "大热",
                        "subject_type": "medicine",
                        "object_type": "property",
                        "source_text": "附子大热。",
                        "confidence": 0.93,
                    },
                    {
                        "subject": "鳖甲",
                        "predicate": "服法",
                        "object": "醋浸",
                        "subject_type": "medicine",
                        "object_type": "",
                        "source_text": "鳖甲宜醋浸。",
                        "confidence": 0.86,
                    },
                ]
            },
            book_name="本草纲目",
            chapter_name="卷一",
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].predicate, "药性")
        self.assertEqual(rows[0].subject_type, "medicine")
        self.assertEqual(rows[0].object_type, "property")
        self.assertEqual(rows[1].predicate, "用法")
        self.assertEqual(rows[1].object_type, "processing_method")

    def test_clean_decision_keeps_new_relation(self) -> None:
        decision = self.pipeline._clean_decision_for_row(
            {
                "subject": "猪肉",
                "predicate": "食忌",
                "object": "甘草",
                "subject_type": "food",
                "object_type": "medicine",
                "source_text": "猪肉不可与甘草同食。",
            }
        )

        self.assertTrue(decision.keep)
        self.assertEqual(decision.reason, "keep_domain_fact")

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

    def test_call_llm_raw_round_robins_across_configured_providers(self) -> None:
        class ProviderPipeline(TCMTriplePipeline):
            def _call_llm_raw_once(self, provider, prompt: str, *, response_format_mode: str = "json_object"):  # type: ignore[override]
                return {
                    "raw_text": '{"triples":[]}',
                    "usage": {},
                    "finish_reason": "stop",
                    "response_format_mode": response_format_mode,
                    "raw_body": {},
                    "provider_name": provider.name,
                    "provider_model": provider.model,
                    "provider_base_url": provider.base_url,
                    "provider_latency_ms": 1.0,
                }

        pipeline = ProviderPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="mimo-v2-pro",
                api_key="primary-key",
                base_url="https://primary.invalid/v1",
                providers=(
                    LLMProviderConfig(name="primary", model="mimo-v2-pro", api_key="k1", base_url="https://primary.invalid/v1"),
                    LLMProviderConfig(name="secondary", model="mimo-v2-pro", api_key="k2", base_url="https://secondary.invalid/v1"),
                ),
                request_delay=0.0,
                max_retries=0,
            )
        )

        first = pipeline.call_llm_raw("prompt-1", response_format_mode="text")
        second = pipeline.call_llm_raw("prompt-2", response_format_mode="text")

        self.assertEqual(first["provider_name"], "primary")
        self.assertEqual(second["provider_name"], "secondary")

    def test_call_llm_raw_fails_over_to_secondary_provider(self) -> None:
        class FailoverPipeline(TCMTriplePipeline):
            def _call_llm_raw_once(self, provider, prompt: str, *, response_format_mode: str = "json_object"):  # type: ignore[override]
                if provider.name == "primary":
                    raise RuntimeError("primary_unavailable")
                return {
                    "raw_text": '{"triples":[]}',
                    "usage": {},
                    "finish_reason": "stop",
                    "response_format_mode": response_format_mode,
                    "raw_body": {},
                    "provider_name": provider.name,
                    "provider_model": provider.model,
                    "provider_base_url": provider.base_url,
                    "provider_latency_ms": 2.0,
                }

        pipeline = FailoverPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="mimo-v2-pro",
                api_key="primary-key",
                base_url="https://primary.invalid/v1",
                providers=(
                    LLMProviderConfig(name="primary", model="mimo-v2-pro", api_key="k1", base_url="https://primary.invalid/v1"),
                    LLMProviderConfig(name="secondary", model="mimo-v2-pro", api_key="k2", base_url="https://secondary.invalid/v1"),
                ),
                request_delay=0.0,
                max_retries=0,
            )
        )

        meta = pipeline.call_llm_raw("prompt", response_format_mode="text")

        self.assertEqual(meta["provider_name"], "secondary")
        self.assertEqual(pipeline._provider_stats["primary"]["failure_count"], 1)
        self.assertEqual(pipeline._provider_stats["secondary"]["success_count"], 1)

    def test_normalize_provider_configs_adds_jmrai_from_env_fallbacks(self) -> None:
        env_patch = {
            "TRIPLE_LLM_JMRAI_ENABLED": "true",
            "TRIPLE_LLM_JMRAI_NAME": "jmrai",
            "LLM_MODEL": "mimo-v2-pro",
            "LLM_API_KEY": "jmrai-key",
            "LLM_BASE_URL": "https://jmrai.invalid/v1",
        }
        with mock.patch.dict(os.environ, env_patch, clear=True):
            providers = _normalize_provider_configs(
                [],
                fallback_model="mimo-v2-pro",
                fallback_api_key="primary-key",
                fallback_base_url="https://primary.invalid/v1",
            )

        self.assertEqual([provider.name for provider in providers], ["primary", "jmrai"])
        self.assertEqual(providers[1].model, env_patch["LLM_MODEL"])
        self.assertEqual(providers[1].api_key, "jmrai-key")
        self.assertEqual(providers[1].base_url, "https://jmrai.invalid/v1")

    def test_normalize_provider_configs_prefers_explicit_env_provider_list(self) -> None:
        env_patch = {
            "TRIPLE_LLM_PROVIDERS": json.dumps(
                [
                    {
                        "name": "primary",
                        "model": "mimo-v2-pro",
                        "api_key": "primary-key",
                        "base_url": "https://primary.invalid/v1",
                        "weight": 1,
                        "enabled": True,
                    },
                    {
                        "name": "jmrai-2",
                        "model": "mimo-v2-pro",
                        "api_key": "jmrai-key-2",
                        "base_url": "https://jmrai.invalid/v1",
                        "weight": 1,
                        "enabled": True,
                    },
                    {
                        "name": "jmrai-3",
                        "model": "mimo-v2-pro",
                        "api_key": "jmrai-key-3",
                        "base_url": "https://jmrai.invalid/v1",
                        "weight": 2,
                        "enabled": True,
                    },
                ],
                ensure_ascii=False,
            ),
            "TRIPLE_LLM_JMRAI_ENABLED": "true",
            "TRIPLE_LLM_JMRAI_API_KEY": "legacy-jmrai-key",
            "TRIPLE_LLM_JMRAI_BASE_URL": "https://legacy.invalid/v1",
        }

        with mock.patch.dict(os.environ, env_patch, clear=True):
            providers = _normalize_provider_configs(
                [],
                fallback_model="mimo-v2-pro",
                fallback_api_key="fallback-key",
                fallback_base_url="https://fallback.invalid/v1",
            )

        self.assertEqual([provider.name for provider in providers], ["primary", "jmrai-2", "jmrai-3"])
        self.assertEqual(providers[1].api_key, "jmrai-key-2")
        self.assertEqual(providers[2].weight, 2)

    def test_normalize_provider_configs_hydrates_masked_provider_list_from_env(self) -> None:
        env_patch = {
            "TRIPLE_LLM_PROVIDERS": json.dumps(
                [
                    {
                        "name": "primary",
                        "model": "mimo-v2-pro",
                        "api_key": "primary-key",
                        "base_url": "https://primary.invalid/v1",
                        "weight": 1,
                        "enabled": True,
                    },
                    {
                        "name": "jmrai-2",
                        "model": "mimo-v2-pro",
                        "api_key": "jmrai-key-2",
                        "base_url": "https://jmrai.invalid/v1",
                        "weight": 1,
                        "enabled": True,
                    },
                    {
                        "name": "jmrai-3",
                        "model": "mimo-v2-pro",
                        "api_key": "jmrai-key-3",
                        "base_url": "https://jmrai.invalid/v1",
                        "weight": 2,
                        "enabled": True,
                    },
                ],
                ensure_ascii=False,
            ),
        }
        masked_providers = [
            {
                "name": "primary",
                "model": "mimo-v2-pro",
                "base_url": "https://primary.invalid/v1",
                "weight": 1,
                "enabled": True,
                "api_key_set": True,
            },
            {
                "name": "jmrai-2",
                "model": "mimo-v2-pro",
                "base_url": "https://jmrai.invalid/v1",
                "weight": 1,
                "enabled": True,
                "api_key_set": True,
            },
            {
                "name": "jmrai-3",
                "model": "mimo-v2-pro",
                "base_url": "https://jmrai.invalid/v1",
                "weight": 2,
                "enabled": True,
                "api_key_set": True,
            },
        ]

        with mock.patch.dict(os.environ, env_patch, clear=True):
            providers = _normalize_provider_configs(
                masked_providers,
                fallback_model="mimo-v2-pro",
                fallback_api_key="",
                fallback_base_url="https://primary.invalid/v1",
            )

        self.assertEqual([provider.name for provider in providers], ["primary", "jmrai-2", "jmrai-3"])
        self.assertEqual([provider.api_key for provider in providers], ["primary-key", "jmrai-key-2", "jmrai-key-3"])
        self.assertEqual(providers[2].weight, 2)

    def test_get_provider_metrics_reports_rates_and_latency(self) -> None:
        class MetricsPipeline(TCMTriplePipeline):
            def _call_llm_raw_once(self, provider, prompt: str, *, response_format_mode: str = "json_object"):  # type: ignore[override]
                if provider.name == "primary" and prompt == "force-fail":
                    raise RuntimeError("primary_down")
                latency = 12.0 if provider.name == "primary" else 24.0
                return {
                    "raw_text": '{"triples":[]}',
                    "usage": {},
                    "finish_reason": "stop",
                    "response_format_mode": response_format_mode,
                    "raw_body": {},
                    "provider_name": provider.name,
                    "provider_model": provider.model,
                    "provider_base_url": provider.base_url,
                    "provider_latency_ms": latency,
                }

        pipeline = MetricsPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="mimo-v2-pro",
                api_key="primary-key",
                base_url="https://primary.invalid/v1",
                providers=(
                    LLMProviderConfig(name="primary", model="mimo-v2-pro", api_key="k1", base_url="https://primary.invalid/v1"),
                    LLMProviderConfig(name="secondary", model="deepseek-ai/DeepSeek-V3.2", api_key="k2", base_url="https://secondary.invalid/v1"),
                ),
                request_delay=0.0,
                max_retries=0,
            )
        )

        pipeline.call_llm_raw("ok-primary", response_format_mode="text")
        pipeline.call_llm_raw("ok-secondary", response_format_mode="text")
        with self.assertRaises(RuntimeError):
            pipeline.call_llm_raw(
                "force-fail",
                response_format_mode="text",
                provider_sequence=[pipeline.config.providers[0]],
            )

        metrics = {item["name"]: item for item in pipeline.get_provider_metrics()}

        self.assertEqual(metrics["primary"]["attempt_count"], 2)
        self.assertEqual(metrics["primary"]["success_count"], 1)
        self.assertEqual(metrics["primary"]["failure_count"], 1)
        self.assertAlmostEqual(metrics["primary"]["success_rate"], 0.5)
        self.assertEqual(metrics["secondary"]["attempt_count"], 1)
        self.assertEqual(metrics["secondary"]["avg_latency_ms"], 24.0)
        self.assertIn("secondary", pipeline.format_provider_metrics_summary())

    def test_call_llm_ignores_response_format_compatibility_failures_in_metrics(self) -> None:
        class CompatibilityPipeline(TCMTriplePipeline):
            def _call_llm_raw_once(self, provider, prompt: str, *, response_format_mode: str = "json_object"):  # type: ignore[override]
                if provider.name == "primary" and response_format_mode == "json_object":
                    request = httpx.Request("POST", "https://primary.invalid/v1/chat/completions")
                    response = httpx.Response(
                        400,
                        request=request,
                        text='{"error":"response_format json_object is not supported"}',
                    )
                    raise httpx.HTTPStatusError("response_format_not_supported", request=request, response=response)
                return {
                    "raw_text": '{"triples":[]}',
                    "usage": {},
                    "finish_reason": "stop",
                    "response_format_mode": response_format_mode,
                    "raw_body": {},
                    "provider_name": provider.name,
                    "provider_model": provider.model,
                    "provider_base_url": provider.base_url,
                    "provider_latency_ms": 3.0,
                }

        pipeline = CompatibilityPipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="mimo-v2-pro",
                api_key="primary-key",
                base_url="https://primary.invalid/v1",
                providers=(
                    LLMProviderConfig(name="primary", model="mimo-v2-pro", api_key="k1", base_url="https://primary.invalid/v1"),
                    LLMProviderConfig(name="secondary", model="mimo-v2-pro", api_key="k2", base_url="https://secondary.invalid/v1"),
                ),
                request_delay=0.0,
                max_retries=0,
            )
        )

        payload = pipeline.call_llm("prompt")
        metrics = {item["name"]: item for item in pipeline.get_provider_metrics()}

        self.assertEqual(payload["__meta__"]["provider_name"], "secondary")
        self.assertEqual(metrics["primary"]["success_count"], 0)
        self.assertEqual(metrics["primary"]["failure_count"], 0)
        self.assertEqual(metrics["primary"]["attempt_count"], 0)
        self.assertEqual(metrics["secondary"]["success_count"], 1)

    def test_call_llm_counts_unprocessable_response_as_provider_failure(self) -> None:
        class UnprocessablePipeline(TCMTriplePipeline):
            def _call_llm_raw_once(self, provider, prompt: str, *, response_format_mode: str = "json_object"):  # type: ignore[override]
                if provider.name == "primary" and response_format_mode == "json_object":
                    return {
                        "raw_text": "not-json",
                        "usage": {},
                        "finish_reason": "stop",
                        "response_format_mode": response_format_mode,
                        "raw_body": {},
                        "provider_name": provider.name,
                        "provider_model": provider.model,
                        "provider_base_url": provider.base_url,
                        "provider_latency_ms": 5.0,
                    }
                return {
                    "raw_text": '{"triples":[]}',
                    "usage": {},
                    "finish_reason": "stop",
                    "response_format_mode": response_format_mode,
                    "raw_body": {},
                    "provider_name": provider.name,
                    "provider_model": provider.model,
                    "provider_base_url": provider.base_url,
                    "provider_latency_ms": 7.0,
                }

        pipeline = UnprocessablePipeline(
            PipelineConfig(
                books_dir=self.books_dir,
                output_dir=self.output_dir,
                model="mimo-v2-pro",
                api_key="primary-key",
                base_url="https://primary.invalid/v1",
                providers=(
                    LLMProviderConfig(name="primary", model="mimo-v2-pro", api_key="k1", base_url="https://primary.invalid/v1"),
                    LLMProviderConfig(name="secondary", model="mimo-v2-pro", api_key="k2", base_url="https://secondary.invalid/v1"),
                ),
                request_delay=0.0,
                max_retries=0,
            )
        )

        payload = pipeline.call_llm("prompt")
        metrics = {item["name"]: item for item in pipeline.get_provider_metrics()}

        self.assertEqual(payload["__meta__"]["provider_name"], "primary")
        self.assertEqual(metrics["primary"]["success_count"], 1)
        self.assertEqual(metrics["primary"]["failure_count"], 1)
        self.assertEqual(metrics["primary"]["attempt_count"], 2)

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
