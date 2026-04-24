from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from dotenv import load_dotenv

from services.triple_pipeline.llm_json import coerce_payload_to_standard_shape as _coerce_payload_to_standard_shape
from services.triple_pipeline.llm_json import extract_all_json_blocks as _extract_all_json_blocks
from services.triple_pipeline.llm_json import extract_json_block as _extract_json_block
from services.triple_pipeline.llm_json import extract_payload_triples as _extract_payload_triples
from services.triple_pipeline import artifact_io as tcm_artifact_io
from services.triple_pipeline import book_chunking as tcm_book_chunking
from services.triple_pipeline import graph_publish as tcm_graph_publish
from services.triple_pipeline import prompts as tcm_prompts
from services.triple_pipeline import provider_config as tcm_provider_config
from services.triple_pipeline import provider_runtime as tcm_provider_runtime
from services.triple_pipeline_models import ChunkTask, CleanDecision, LLMProviderConfig, PipelineConfig, TripleRecord


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent.parent
DEFAULT_BOOKS_DIR = PROJECT_ROOT / "TCM-Ancient-Books-master" / "TCM-Ancient-Books-master"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "storage" / "triple_pipeline"
DEFAULT_GRAPH_BASE = BACKEND_DIR / "services" / "graph_service" / "data" / "sample_graph.json"
DEFAULT_GRAPH_TARGET = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.json"
GRAPH_RUNTIME_IO_LOCK = RLock()
DEFAULT_CHAPTER_EXCLUDES = ["篇名", "目录", "凡例", "序", "自序", "引言"]
WEAK_SECTION_TITLES = set(DEFAULT_CHAPTER_EXCLUDES) | {"前言", "后记", "跋", "附录", "卷首", "目录上", "目录下"}
NOISE_PREDICATES = {"出处"}
PREFERRED_PREDICATES = {
    "治疗证候",
    "治疗疾病",
    "治疗症状",
    "推荐方剂",
    "使用药材",
    "功效",
    "归经",
    "常见症状",
    "治法",
    "别名",
    "属于范畴",
    "食忌",
    "配伍禁忌",
    "用法",
    "药性",
    "五味",
    "升降浮沉",
}
NOISE_TEXT_PATTERNS = [
    "出版社",
    "出版",
    "第2版",
    "电子版",
    "底本",
    "校补",
    "公元",
    "年1月",
    "年7月",
    "巴蜀书社",
    "广西人民出版社",
    "清·",
    "汉",
    "序",
    "目录",
    "篇名",
]
NOISE_ENTITY_PATTERNS = [
    "电子版",
    "出版社",
    "目录",
    "篇名",
    "原序",
    "校补",
]

load_dotenv(BACKEND_DIR / ".env")


_first_env = tcm_provider_config.first_env


_safe_read_text = tcm_artifact_io.safe_read_text
_write_text_atomic = tcm_artifact_io.write_text_atomic


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text.strip())
    return cleaned.strip("_") or "run"


_sanitize_provider_name = tcm_provider_config.sanitize_provider_name
_provider_to_dict = tcm_provider_config.provider_to_dict
_is_response_format_compatibility_error = tcm_provider_config.is_response_format_compatibility_error
_load_env_provider_dicts = tcm_provider_config.load_env_provider_dicts
_env_flag = tcm_provider_config.env_flag
_build_env_provider = tcm_provider_config.build_env_provider
_normalize_provider_configs = tcm_provider_config.normalize_provider_configs


_load_json_file = tcm_artifact_io.load_json_file
_load_json_file_strict = tcm_artifact_io.load_json_file_strict
_extract_fact_ids = tcm_artifact_io.extract_fact_ids
_dedupe_graph_rows = tcm_artifact_io.dedupe_graph_rows
_load_jsonl_rows = tcm_artifact_io.load_jsonl_rows
_dedupe_evidence_rows = tcm_artifact_io.dedupe_evidence_rows
_derive_evidence_target_path = tcm_artifact_io.derive_evidence_target_path


def _match_any_pattern(text: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return False
    return any(pattern and pattern in text for pattern in patterns)


def _split_keywords(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _merge_keywords(primary: list[str] | None, secondary: list[str] | None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in (primary or []) + (secondary or []):
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _contains_any(text: str, patterns: list[str]) -> bool:
    cleaned = text or ""
    return any(pattern in cleaned for pattern in patterns if pattern)


_detect_formula_titles = tcm_prompts.detect_formula_titles


RELATION_NORMALIZATION = {
    "主治": "治疗证候",
    "治": "治疗证候",
    "治疗": "治疗证候",
    "适用于": "治疗证候",
    "适合": "推荐方剂",
    "推荐用方": "推荐方剂",
    "方药": "使用药材",
    "组成": "使用药材",
    "配伍": "使用药材",
    "归入经络": "归经",
    "经络归属": "归经",
    "症见": "常见症状",
    "见症": "常见症状",
    "表现": "常见症状",
    "证候表现": "常见症状",
    "功用": "功效",
    "忌食": "食忌",
    "饮食禁忌": "食忌",
    "配伍禁忌": "配伍禁忌",
    "相反": "配伍禁忌",
    "相恶": "配伍禁忌",
    "相畏": "配伍禁忌",
    "服法": "用法",
    "服用方法": "用法",
    "用法用量": "用法",
    "炮制方法": "用法",
    "药性": "药性",
    "四气": "药性",
    "五味": "五味",
    "升降浮沉": "升降浮沉",
    "浮沉": "升降浮沉",
}

ALLOWED_RELATIONS = {
    "治疗证候",
    "治疗疾病",
    "治疗症状",
    "推荐方剂",
    "使用药材",
    "功效",
    "归经",
    "常见症状",
    "治法",
    "出处",
    "别名",
    "属于范畴",
    "食忌",
    "配伍禁忌",
    "用法",
    "药性",
    "五味",
    "升降浮沉",
}

ALLOWED_ENTITY_TYPES = {
    "formula",
    "herb",
    "syndrome",
    "symptom",
    "disease",
    "therapy",
    "channel",
    "category",
    "book",
    "chapter",
    "food",
    "medicine",
    "processing_method",
    "property",
    "other",
}

ENTITY_TYPE_HINTS = {
    "方": "formula",
    "汤": "formula",
    "散": "formula",
    "丸": "formula",
    "饮": "formula",
    "证": "syndrome",
    "症": "symptom",
    "经": "channel",
}

PROCESSING_METHOD_KEYWORDS = (
    "炮制",
    "煎服",
    "丸服",
    "散服",
    "汤服",
    "酒服",
    "水煎",
    "酒浸",
    "醋浸",
    "蜜炙",
    "炒",
    "炙",
    "煅",
    "煨",
    "蒸",
    "煮",
    "焙",
    "晒",
    "曝",
    "浸",
    "外敷",
    "含化",
)

PROPERTY_TERMS = {
    "寒",
    "热",
    "温",
    "凉",
    "平",
    "微寒",
    "微温",
    "大寒",
    "大热",
    "甘",
    "辛",
    "酸",
    "苦",
    "咸",
    "淡",
    "涩",
    "甘寒",
    "甘温",
    "辛温",
    "辛凉",
    "苦寒",
    "酸温",
    "咸寒",
    "升",
    "降",
    "浮",
    "沉",
    "升浮",
    "沉降",
    "有毒",
    "无毒",
    "小毒",
}


class TCMTriplePipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.providers = _normalize_provider_configs(
            list(self.config.providers),
            fallback_model=self.config.model,
            fallback_api_key=self.config.api_key,
            fallback_base_url=self.config.base_url,
        )
        self._providers_by_name = {provider.name: provider for provider in self.config.providers}
        self._provider_rotation = [
            provider.name
            for provider in self.config.providers
            for _ in range(max(1, int(provider.weight)))
            if provider.enabled
        ] or [provider.name for provider in self.config.providers if provider.enabled]
        self._provider_lock = Lock()
        self._provider_cursor = 0
        self._provider_stats: dict[str, dict[str, Any]] = {
            provider.name: {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_error": "",
                "last_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "latency_sample_count": 0,
            }
            for provider in self.config.providers
        }

    def discover_books(self) -> list[Path]:
        return tcm_book_chunking.discover_books(self)

    def recommend_books(self, limit: int = 12) -> list[Path]:
        return tcm_book_chunking.recommend_books(self, limit=limit)

    def split_book(self, path: Path) -> list[dict[str, str]]:
        return tcm_book_chunking.split_book(self, path)

    def _is_weak_section_title(self, title: str, book_name: str) -> bool:
        return tcm_book_chunking._is_weak_section_title(self, title, book_name)

    def _normalize_chunk_label(self, title: str, book_name: str) -> str:
        return tcm_book_chunking._normalize_chunk_label(self, title, book_name)

    def chunk_text(self, content: str) -> list[tuple[str, int, int]]:
        return tcm_book_chunking.chunk_text(self, content)

    def chunk_section(self, content: str) -> list[str]:
        return tcm_book_chunking.chunk_section(self, content)

    def _select_chunk_title(
        self,
        *,
        book_name: str,
        chunk_start: int,
        chunk_end: int,
        ranges: list[tuple[int, int, str]],
    ) -> str:
        return tcm_book_chunking._select_chunk_title(
            self,
            book_name=book_name,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            ranges=ranges,
        )

    def schedule_book_chunks(
        self,
        *,
        book_path: Path,
        chapter_contains: list[str] | None = None,
        chapter_excludes: list[str] | None = None,
        max_chunks_per_book: int | None = None,
        skip_initial_chunks_per_book: int = 0,
        chunk_strategy: str | None = None,
    ) -> list[ChunkTask]:
        return tcm_book_chunking.schedule_book_chunks(
            self,
            book_path=book_path,
            chapter_contains=chapter_contains,
            chapter_excludes=chapter_excludes,
            max_chunks_per_book=max_chunks_per_book,
            skip_initial_chunks_per_book=skip_initial_chunks_per_book,
            chunk_strategy=chunk_strategy,
        )

    def build_prompt(self, *, book_name: str, chapter_name: str, text_chunk: str) -> str:
        return tcm_prompts.build_prompt(
            book_name=book_name,
            chapter_name=chapter_name,
            text_chunk=text_chunk,
            allowed_relations=ALLOWED_RELATIONS,
        )

    def build_compact_prompt(self, *, book_name: str, chapter_name: str, text_chunk: str) -> str:
        return tcm_prompts.build_compact_prompt(
            book_name=book_name,
            chapter_name=chapter_name,
            text_chunk=text_chunk,
            allowed_relations=ALLOWED_RELATIONS,
        )

    def build_prompt_variant(self, *, book_name: str, chapter_name: str, text_chunk: str, variant: str = "current") -> str:
        return tcm_prompts.build_prompt_variant(
            book_name=book_name,
            chapter_name=chapter_name,
            text_chunk=text_chunk,
            allowed_relations=ALLOWED_RELATIONS,
            variant=variant,
        )

    def _select_provider_sequence(self) -> list[LLMProviderConfig]:
        return tcm_provider_runtime._select_provider_sequence(self)

    def _record_provider_result(
        self,
        provider_name: str,
        *,
        success: bool,
        latency_ms: float,
        error: str = "",
    ) -> None:
        return tcm_provider_runtime._record_provider_result(
            self,
            provider_name,
            success=success,
            latency_ms=latency_ms,
            error=error,
        )

    def _reclassify_provider_success_as_failure(
        self,
        provider_name: str,
        *,
        error: str,
        latency_ms: float | None = None,
    ) -> None:
        return tcm_provider_runtime._reclassify_provider_success_as_failure(
            self,
            provider_name,
            error=error,
            latency_ms=latency_ms,
        )

    def get_provider_metrics(self) -> list[dict[str, Any]]:
        return tcm_provider_runtime.get_provider_metrics(self)

    def format_provider_metrics_summary(self) -> str:
        return tcm_provider_runtime.format_provider_metrics_summary(self)

    def _call_llm_raw_once(
        self,
        provider: LLMProviderConfig,
        prompt: str,
        *,
        response_format_mode: str = "json_object",
    ) -> dict[str, Any]:
        return tcm_provider_runtime._call_llm_raw_once(
            self,
            provider,
            prompt,
            response_format_mode=response_format_mode,
        )

    def call_llm_raw(
        self,
        prompt: str,
        *,
        response_format_mode: str = "json_object",
        provider_sequence: list[LLMProviderConfig] | None = None,
    ) -> dict[str, Any]:
        return tcm_provider_runtime.call_llm_raw(
            self,
            prompt,
            response_format_mode=response_format_mode,
            provider_sequence=provider_sequence,
        )

    def call_llm(self, prompt: str) -> dict[str, Any]:
        return tcm_provider_runtime.call_llm(self, prompt)

    def normalize_predicate(self, predicate: str) -> str:
        cleaned = predicate.strip()
        if cleaned in ALLOWED_RELATIONS:
            return cleaned
        if cleaned in RELATION_NORMALIZATION:
            return RELATION_NORMALIZATION[cleaned]
        for key, normalized in RELATION_NORMALIZATION.items():
            if key in cleaned:
                return normalized
        return cleaned

    def infer_entity_type(self, value: str, raw_type: str) -> str:
        cleaned = (raw_type or "").strip().lower()
        if cleaned in ALLOWED_ENTITY_TYPES:
            return cleaned

        text = value.strip()
        if text in {"医方集解", "本草纲目", "和剂局方", "金匮要略", "伤寒论"}:
            return "book"
        if text in PROPERTY_TERMS:
            return "property"
        if any(keyword in text for keyword in PROCESSING_METHOD_KEYWORDS):
            return "processing_method"
        for suffix, inferred in ENTITY_TYPE_HINTS.items():
            if text.endswith(suffix):
                return inferred
        return "other"

    def normalize_triples(
        self,
        *,
        payload: dict[str, Any],
        book_name: str,
        chapter_name: str,
    ) -> list[TripleRecord]:
        triples = _extract_payload_triples(payload)
        if not triples:
            return []

        normalized: list[TripleRecord] = []
        for item in triples:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject", "")).strip()
            predicate_raw = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()
            source_text = str(item.get("source_text", "")).strip()
            if not subject or not predicate_raw or not obj or not source_text:
                continue

            predicate = self.normalize_predicate(predicate_raw)
            subject_type_raw = str(item.get("subject_type", "")).strip()
            object_type_raw = str(item.get("object_type", "")).strip()
            confidence_value = item.get("confidence", 0.7)
            try:
                confidence = float(confidence_value)
            except (TypeError, ValueError):
                confidence = 0.7
            confidence = max(0.0, min(1.0, confidence))

            normalized.append(
                TripleRecord(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    subject_type=self.infer_entity_type(subject, subject_type_raw),
                    object_type=self.infer_entity_type(obj, object_type_raw),
                    source_book=book_name,
                    source_chapter=chapter_name,
                    source_text=source_text[:300],
                    confidence=round(confidence, 4),
                    raw_predicate=predicate_raw,
                    raw_subject_type=subject_type_raw,
                    raw_object_type=object_type_raw,
                )
            )
        return normalized

    def extract_chunk_payload(self, task: ChunkTask, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {
                "triples": [
                    {
                        "subject": task.book_name,
                        "predicate": "出处",
                        "object": task.chapter_name,
                        "subject_type": "book",
                        "object_type": "chapter",
                        "source_text": task.text_chunk[:120],
                        "confidence": 0.5,
                    }
                ]
            }

        prompt = self.build_prompt(
            book_name=task.book_name,
            chapter_name=task.chapter_name,
            text_chunk=task.text_chunk,
        )
        payload = self.call_llm(prompt)
        if self.config.request_delay > 0:
            time.sleep(self.config.request_delay)
        return _coerce_payload_to_standard_shape(payload)

    def create_run_dir(self, label: str | None = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"{timestamp}_{_slugify(label or 'triple_run')}"
        run_dir = self.config.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def summarize_run_dir(self, run_dir: Path) -> dict[str, Any]:
        manifest = _load_json_file(run_dir / "manifest.json", {})
        state = _load_json_file(run_dir / "state.json", {})
        normalized_jsonl = run_dir / "triples.normalized.jsonl"
        total_rows = 0
        if normalized_jsonl.exists():
            with normalized_jsonl.open("r", encoding="utf-8") as f:
                total_rows = sum(1 for line in f if line.strip())

        return {
            "run_dir": str(run_dir),
            "created_at": manifest.get("created_at"),
            "model": manifest.get("model"),
            "dry_run": bool(manifest.get("dry_run", False)),
            "books_total": state.get("books_total", 0),
            "books_completed": state.get("books_completed", 0),
            "total_triples": state.get("total_triples", total_rows),
            "status": state.get("status", "unknown"),
        }

    def audit_run_dir(self, run_dir: Path, limit: int = 8) -> dict[str, Any]:
        summary = self.summarize_run_dir(run_dir)
        manifest = _load_json_file(run_dir / "manifest.json", {})
        rows: list[dict[str, Any]] = []
        normalized_jsonl = run_dir / "triples.normalized.jsonl"
        if normalized_jsonl.exists():
            with normalized_jsonl.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line.lstrip("\ufeff")))
                    if len(rows) >= limit:
                        break

        chapters = sorted({str(row.get("source_chapter", "")).strip() for row in rows if str(row.get("source_chapter", "")).strip()})
        return {
            "summary": summary,
            "books": manifest.get("books", []),
            "config": manifest.get("config", {}),
            "sample_rows": rows,
            "sample_chapters": chapters,
        }

    def _clean_decision_for_row(self, row: dict[str, Any]) -> CleanDecision:
        predicate = str(row.get("predicate", "")).strip()
        subject = str(row.get("subject", "")).strip()
        obj = str(row.get("object", "")).strip()
        source_text = str(row.get("source_text", "")).strip()
        subject_type = str(row.get("subject_type", "")).strip()
        object_type = str(row.get("object_type", "")).strip()

        if predicate not in PREFERRED_PREDICATES:
            return CleanDecision(False, "predicate_not_supported")
        if predicate in NOISE_PREDICATES:
            return CleanDecision(False, "drop_bibliographic_predicate")
        if _contains_any(source_text, NOISE_TEXT_PATTERNS) and predicate in {"功效", "属于范畴", "别名"}:
            return CleanDecision(False, "drop_frontmatter_text")
        if _contains_any(subject, NOISE_ENTITY_PATTERNS) or _contains_any(obj, NOISE_ENTITY_PATTERNS):
            return CleanDecision(False, "drop_frontmatter_entity")
        if predicate == "属于范畴" and {subject_type, object_type} & {"book", "chapter"}:
            return CleanDecision(False, "drop_book_category_relation")
        if predicate in {"功效", "治法"} and subject_type == "book":
            return CleanDecision(False, "drop_book_level_abstract_relation")
        if predicate == "别名" and len(subject) <= 1:
            return CleanDecision(False, "drop_too_short_alias_subject")
        if subject == obj:
            return CleanDecision(False, "drop_self_loop")
        return CleanDecision(True, "keep_domain_fact")

    def clean_run_dir(self, run_dir: Path) -> dict[str, Any]:
        normalized_jsonl = run_dir / "triples.normalized.jsonl"
        if not normalized_jsonl.exists():
            raise FileNotFoundError(f"normalized_jsonl_not_found: {normalized_jsonl}")

        cleaned_jsonl = run_dir / "triples.cleaned.jsonl"
        cleaned_csv = run_dir / "triples.cleaned.csv"
        graph_facts_jsonl = run_dir / "graph_facts.cleaned.jsonl"
        graph_facts_json = run_dir / "graph_facts.cleaned.json"
        evidence_metadata_jsonl = run_dir / "evidence_metadata.jsonl"
        report_path = run_dir / "triples.cleaned.report.json"

        cleaned_rows: list[TripleRecord] = []
        cleaned_payload_rows: list[dict[str, Any]] = []
        graph_fact_rows: list[dict[str, Any]] = []
        evidence_rows: list[dict[str, Any]] = []
        dropped_count = 0
        reason_counts: dict[str, int] = {}

        with normalized_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line.lstrip("\ufeff"))
                decision = self._clean_decision_for_row(row)
                reason_counts[decision.reason] = reason_counts.get(decision.reason, 0) + 1
                if not decision.keep:
                    dropped_count += 1
                    continue
                fact_id = hashlib.sha1(
                    "||".join(
                        [
                            str(row.get("subject", "")),
                            str(row.get("predicate", "")),
                            str(row.get("object", "")),
                            str(row.get("source_book", "")),
                            str(row.get("source_chapter", "")),
                            str(row.get("source_text", "")),
                        ]
                    ).encode("utf-8")
                ).hexdigest()[:16]
                cleaned_payload_rows.append(row)
                graph_fact_rows.append(
                    {
                        "fact_id": fact_id,
                        "subject": str(row.get("subject", "")),
                        "predicate": str(row.get("predicate", "")),
                        "object": str(row.get("object", "")),
                        "subject_type": str(row.get("subject_type", "")),
                        "object_type": str(row.get("object_type", "")),
                        "source_book": str(row.get("source_book", "")),
                        "source_chapter": str(row.get("source_chapter", "")),
                    }
                )
                evidence_rows.append(
                    {
                        "fact_id": fact_id,
                        "source_book": str(row.get("source_book", "")),
                        "source_chapter": str(row.get("source_chapter", "")),
                        "source_text": str(row.get("source_text", "")),
                        "confidence": float(row.get("confidence", 0.0)),
                    }
                )
                cleaned_rows.append(
                    TripleRecord(
                        subject=str(row.get("subject", "")),
                        predicate=str(row.get("predicate", "")),
                        object=str(row.get("object", "")),
                        subject_type=str(row.get("subject_type", "")),
                        object_type=str(row.get("object_type", "")),
                        source_book=str(row.get("source_book", "")),
                        source_chapter=str(row.get("source_chapter", "")),
                        source_text=str(row.get("source_text", "")),
                        confidence=float(row.get("confidence", 0.0)),
                        raw_predicate=str(row.get("raw_predicate", row.get("predicate", ""))),
                        raw_subject_type=str(row.get("raw_subject_type", row.get("subject_type", ""))),
                        raw_object_type=str(row.get("raw_object_type", row.get("object_type", ""))),
                    )
                )

        self.write_csv(cleaned_csv, cleaned_rows)
        _write_text_atomic(cleaned_jsonl, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cleaned_payload_rows), encoding="utf-8")
        _write_text_atomic(graph_facts_jsonl, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in graph_fact_rows), encoding="utf-8")
        _write_text_atomic(graph_facts_json, json.dumps(graph_fact_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_text_atomic(evidence_metadata_jsonl, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evidence_rows), encoding="utf-8")

        report = {
            "run_dir": str(run_dir),
            "input_total": len(cleaned_payload_rows) + dropped_count,
            "kept_total": len(cleaned_payload_rows),
            "dropped_total": dropped_count,
            "reason_counts": reason_counts,
            "cleaned_jsonl": str(cleaned_jsonl),
            "cleaned_csv": str(cleaned_csv),
            "graph_facts_jsonl": str(graph_facts_jsonl),
            "graph_facts_json": str(graph_facts_json),
            "evidence_metadata_jsonl": str(evidence_metadata_jsonl),
        }
        _write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def save_manifest(self, run_dir: Path, payload: dict[str, Any]) -> None:
        return tcm_graph_publish.save_manifest(self, run_dir, payload)

    def append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        return tcm_graph_publish.append_jsonl(self, path, row)

    def write_csv(self, path: Path, rows: list[TripleRecord]) -> None:
        return tcm_graph_publish.write_csv(self, path, rows)

    def write_graph_import(self, path: Path, rows: list[TripleRecord]) -> None:
        return tcm_graph_publish.write_graph_import(self, path, rows)

    def publish_graph(
        self,
        *,
        graph_import_path: Path | None = None,
        run_dir: Path | None = None,
        target_path: Path | None = None,
        replace: bool = False,
    ) -> Path:
        return tcm_graph_publish.publish_graph(
            self,
            graph_import_path=graph_import_path,
            run_dir=run_dir,
            target_path=target_path,
            replace=replace,
        )

    def extract_books(
        self,
        *,
        selected_books: list[Path],
        label: str | None = None,
        max_chunks_per_book: int | None = None,
        dry_run: bool = False,
        chapter_contains: list[str] | None = None,
        chapter_excludes: list[str] | None = None,
        skip_initial_chunks_per_book: int = 0,
        chunk_strategy: str | None = None,
    ) -> Path:
        run_dir = self.create_run_dir(label=label)
        triples_jsonl = run_dir / "triples.normalized.jsonl"
        raw_jsonl = run_dir / "triples.raw.jsonl"
        state_path = run_dir / "state.json"
        all_rows: list[TripleRecord] = []

        state = {
            "status": "running",
            "books_total": len(selected_books),
            "books_completed": 0,
            "current_book": None,
            "current_chapter": None,
            "current_chunk_index": 0,
            "dry_run": dry_run,
            "chunk_errors": 0,
            "chunks_total": 0,
            "chunks_completed": 0,
        }
        self.save_manifest(
            run_dir,
            {
                "created_at": datetime.now().isoformat(),
                "books": [str(path) for path in selected_books],
                "model": self.config.model,
                "base_url": self.config.base_url,
                "dry_run": dry_run,
                "config": {
                    "providers": [_provider_to_dict(provider) for provider in self.config.providers],
                    "max_chunk_chars": self.config.max_chunk_chars,
                    "chunk_overlap": self.config.chunk_overlap,
                    "chapter_contains": chapter_contains or [],
                    "chapter_excludes": chapter_excludes or [],
                    "skip_initial_chunks_per_book": max(0, skip_initial_chunks_per_book),
                    "chunk_strategy": (chunk_strategy or self.config.chunk_strategy),
                    "parallel_workers": self.config.parallel_workers,
                },
            },
        )
        _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        for book_index, book_path in enumerate(selected_books, start=1):
            state["current_book"] = str(book_path)
            tasks = self.schedule_book_chunks(
                book_path=book_path,
                chapter_contains=chapter_contains,
                chapter_excludes=chapter_excludes,
                max_chunks_per_book=max_chunks_per_book,
                skip_initial_chunks_per_book=skip_initial_chunks_per_book,
                chunk_strategy=chunk_strategy,
            )
            state["chunks_total"] = int(state.get("chunks_total", 0)) + len(tasks)
            _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            if not tasks:
                state["books_completed"] = book_index
                _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                continue

            results: dict[int, dict[str, Any]] = {}
            if dry_run or self.config.parallel_workers <= 1 or len(tasks) == 1:
                for task in tasks:
                    state["current_chapter"] = task.chapter_name
                    state["current_chunk_index"] = task.chunk_index
                    _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                    try:
                        payload = self.extract_chunk_payload(task, dry_run=dry_run)
                        error = None
                    except Exception as exc:
                        payload = {"triples": []}
                        error = str(exc)
                        state["chunk_errors"] = int(state.get("chunk_errors", 0)) + 1
                    results[task.sequence] = {
                        "task": task,
                        "payload": payload,
                        "error": error,
                    }
                    state["chunks_completed"] = int(state.get("chunks_completed", 0)) + 1
                    _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                with ThreadPoolExecutor(max_workers=max(1, self.config.parallel_workers)) as executor:
                    future_map = {
                        executor.submit(self.extract_chunk_payload, task, False): task
                        for task in tasks
                    }
                    for future in as_completed(future_map):
                        task = future_map[future]
                        state["current_chapter"] = task.chapter_name
                        state["current_chunk_index"] = task.chunk_index
                        try:
                            payload = future.result()
                            error = None
                        except Exception as exc:
                            payload = {"triples": []}
                            error = str(exc)
                            state["chunk_errors"] = int(state.get("chunk_errors", 0)) + 1
                        results[task.sequence] = {
                            "task": task,
                            "payload": payload,
                            "error": error,
                        }
                        state["chunks_completed"] = int(state.get("chunks_completed", 0)) + 1
                        _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            for task in tasks:
                result = results.get(task.sequence, {"task": task, "payload": {"triples": []}, "error": "missing_result"})
                payload = result["payload"]
                error = result["error"]
                raw_row = {
                    "book": task.book_name,
                    "chapter": task.chapter_name,
                    "chunk_index": task.chunk_index,
                    "payload": payload,
                }
                if isinstance(payload, dict):
                    meta = payload.get("__meta__")
                    if isinstance(meta, dict):
                        raw_row["llm_raw_text"] = str(meta.get("raw_text", ""))
                        raw_row["llm_usage"] = meta.get("usage", {}) if isinstance(meta.get("usage"), dict) else {}
                        raw_row["llm_finish_reason"] = meta.get("finish_reason")
                        raw_row["llm_response_format_mode"] = meta.get("response_format_mode")
                if error:
                    raw_row["error"] = error
                self.append_jsonl(raw_jsonl, raw_row)
                rows = self.normalize_triples(
                    payload=payload,
                    book_name=task.book_name,
                    chapter_name=task.chapter_name,
                )
                for row in rows:
                    self.append_jsonl(triples_jsonl, asdict(row))
                all_rows.extend(rows)
            state["books_completed"] = book_index
            _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        self.write_csv(run_dir / "triples.normalized.csv", all_rows)
        self.write_graph_import(run_dir / "graph_import.json", all_rows)
        state["status"] = "completed"
        state["total_triples"] = len(all_rows)
        _write_text_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_dir

    def latest_run(self) -> Path | None:
        if not self.config.output_dir.exists():
            return None
        runs = sorted((path for path in self.config.output_dir.iterdir() if path.is_dir()), reverse=True)
        return runs[0] if runs else None


__all__ = [
    "DEFAULT_BOOKS_DIR",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_GRAPH_BASE",
    "DEFAULT_GRAPH_TARGET",
    "GRAPH_RUNTIME_IO_LOCK",
    "DEFAULT_CHAPTER_EXCLUDES",
    "LLMProviderConfig",
    "PipelineConfig",
    "TripleRecord",
    "TCMTriplePipeline",
    "_first_env",
    "_safe_read_text",
    "_write_text_atomic",
    "_provider_to_dict",
    "_normalize_provider_configs",
    "_load_json_file",
    "_load_json_file_strict",
    "_extract_fact_ids",
    "_dedupe_graph_rows",
    "_load_jsonl_rows",
    "_dedupe_evidence_rows",
    "_derive_evidence_target_path",
    "_split_keywords",
    "_merge_keywords",
    "_detect_formula_titles",
    "_extract_all_json_blocks",
    "_extract_json_block",
    "_extract_payload_triples",
]
