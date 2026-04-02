from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

import httpx
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent.parent
DEFAULT_BOOKS_DIR = PROJECT_ROOT / "TCM-Ancient-Books-master" / "TCM-Ancient-Books-master"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "storage" / "triple_pipeline"
DEFAULT_GRAPH_BASE = BACKEND_DIR / "services" / "graph_service" / "data" / "sample_graph.json"
DEFAULT_GRAPH_TARGET = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.json"
DEFAULT_CHAPTER_EXCLUDES = ["篇名", "目录", "凡例", "序", "自序", "引言"]
WEAK_SECTION_TITLES = set(DEFAULT_CHAPTER_EXCLUDES) | {"前言", "后记", "跋", "附录", "卷首", "目录上", "目录下"}
FORMULA_TITLE_SUFFIXES = ("汤", "丸", "散", "饮", "丹", "方", "膏", "煎")
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


def _first_env(*names: str, default: str = "") -> str:
    import os

    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text.strip())
    return cleaned.strip("_") or "run"


def _sanitize_provider_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(name or "").strip())
    return cleaned.strip("_") or f"provider_{index}"


def _provider_to_dict(provider: "LLMProviderConfig") -> dict[str, Any]:
    return {
        "name": provider.name,
        "model": provider.model,
        "base_url": provider.base_url,
        "weight": int(provider.weight),
        "enabled": bool(provider.enabled),
        "api_key_set": bool(provider.api_key),
    }


def _env_flag(*names: str, default: bool | None = None) -> bool | None:
    raw = _first_env(*names)
    if not raw:
        return default
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _build_env_provider(
    *,
    index: int,
    name_envs: tuple[str, ...],
    default_name: str,
    model_envs: tuple[str, ...],
    api_key_envs: tuple[str, ...],
    base_url_envs: tuple[str, ...],
    weight_envs: tuple[str, ...] = (),
    enabled_envs: tuple[str, ...] = (),
) -> "LLMProviderConfig" | None:
    enabled = _env_flag(*enabled_envs, default=True) if enabled_envs else True
    if enabled is False:
        return None
    model = _first_env(*model_envs)
    api_key = _first_env(*api_key_envs)
    base_url = _first_env(*base_url_envs)
    if not model or not api_key or not base_url:
        return None
    return LLMProviderConfig(
        name=_sanitize_provider_name(_first_env(*name_envs, default=default_name), index),
        model=model,
        api_key=api_key,
        base_url=base_url,
        weight=max(1, int(_first_env(*weight_envs, default="1") or 1)),
        enabled=True,
    )


def _normalize_provider_configs(
    raw_providers: Any,
    *,
    fallback_model: str,
    fallback_api_key: str,
    fallback_base_url: str,
) -> tuple["LLMProviderConfig", ...]:
    providers: list[LLMProviderConfig] = []
    raw_env_providers = _first_env("TRIPLE_LLM_PROVIDERS")

    if not raw_providers and raw_env_providers:
        try:
            decoded = json.loads(raw_env_providers)
        except json.JSONDecodeError:
            decoded = []
        if isinstance(decoded, list):
            raw_providers = decoded

    if isinstance(raw_providers, list):
        for index, item in enumerate(raw_providers, start=1):
            if isinstance(item, LLMProviderConfig):
                if item.enabled and item.api_key and item.base_url and item.model:
                    providers.append(item)
                continue
            if not isinstance(item, dict):
                continue
            enabled = bool(item.get("enabled", True))
            model = str(item.get("model") or fallback_model).strip()
            api_key = str(item.get("api_key") or "").strip()
            base_url = str(item.get("base_url") or "").strip()
            if not enabled or not model or not api_key or not base_url:
                continue
            providers.append(
                LLMProviderConfig(
                    name=_sanitize_provider_name(str(item.get("name") or ""), index),
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    weight=max(1, int(item.get("weight", 1) or 1)),
                    enabled=True,
                )
            )

    if providers:
        return tuple(providers)

    primary = LLMProviderConfig(
        name="primary",
        model=fallback_model,
        api_key=fallback_api_key,
        base_url=fallback_base_url,
        weight=1,
        enabled=True,
    )
    providers = [primary]

    extra_providers = [
        _build_env_provider(
            index=2,
            name_envs=("TRIPLE_LLM_PROVIDER2_NAME",),
            default_name="secondary",
            model_envs=("TRIPLE_LLM_PROVIDER2_MODEL", "TRIPLE_LLM_MODEL_2", "TRIPLE_LLM_MODEL"),
            api_key_envs=("TRIPLE_LLM_PROVIDER2_API_KEY", "TRIPLE_LLM_API_KEY_2"),
            base_url_envs=("TRIPLE_LLM_PROVIDER2_BASE_URL", "TRIPLE_LLM_BASE_URL_2"),
            weight_envs=("TRIPLE_LLM_PROVIDER2_WEIGHT",),
            enabled_envs=("TRIPLE_LLM_PROVIDER2_ENABLED",),
        ),
        _build_env_provider(
            index=3,
            name_envs=("TRIPLE_LLM_JMRAI_NAME",),
            default_name="jmrai",
            model_envs=("TRIPLE_LLM_JMRAI_MODEL", "LLM_MODEL"),
            api_key_envs=("TRIPLE_LLM_JMRAI_API_KEY", "LLM_API_KEY"),
            base_url_envs=("TRIPLE_LLM_JMRAI_BASE_URL", "LLM_BASE_URL"),
            weight_envs=("TRIPLE_LLM_JMRAI_WEIGHT",),
            enabled_envs=("TRIPLE_LLM_JMRAI_ENABLED",),
        ),
    ]

    existing_names = {provider.name for provider in providers}
    existing_signatures = {
        (provider.model, provider.base_url, provider.api_key)
        for provider in providers
    }
    for provider in extra_providers:
        if provider is None:
            continue
        signature = (provider.model, provider.base_url, provider.api_key)
        if provider.name in existing_names or signature in existing_signatures:
            continue
        providers.append(provider)
        existing_names.add(provider.name)
        existing_signatures.add(signature)
    return tuple(providers)


def _extract_balanced_json_candidate(text: str) -> str | None:
    for start, opener in enumerate(text):
        if opener not in "{[":
            continue
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
    return None


def _parse_json_candidate(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    normalized = re.sub(r",(\s*[}\]])", r"\1", candidate)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(normalized)
    except (SyntaxError, ValueError):
        raise ValueError("llm_response_not_json") from None
    if isinstance(parsed, (dict, list)):
        return parsed
    raise ValueError("llm_response_not_json")


def _extract_json_block(text: str) -> Any:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates: list[str] = []
    if cleaned:
        candidates.append(cleaned)
    balanced = _extract_balanced_json_candidate(cleaned)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match and match.group(1) not in candidates:
        candidates.append(match.group(1))

    for candidate in candidates:
        try:
            parsed = _parse_json_candidate(candidate)
            if len(_extract_payload_triples(parsed)) <= 1:
                recovered = _recover_triples_payload_from_text(cleaned)
                if recovered and len(_extract_payload_triples(recovered)) > len(_extract_payload_triples(parsed)):
                    return recovered
            return parsed
        except ValueError:
            continue
    recovered = _recover_triples_payload_from_text(cleaned)
    if recovered:
        return recovered
    raise ValueError("llm_response_not_json")


def _extract_all_json_blocks(text: str) -> list[Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    candidates: list[tuple[int, int, str]] = []
    seen_spans: set[tuple[int, int]] = set()

    for start, char in enumerate(cleaned):
        if char not in "{[":
            continue
        candidate = _extract_balanced_json_candidate(cleaned[start:])
        if not candidate:
            continue
        candidate = candidate.strip()
        if not candidate:
            continue
        end = start + len(candidate)
        span = (start, end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        candidates.append((start, end, candidate))

    kept: list[tuple[int, int, Any]] = []
    for start, end, candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        try:
            parsed = _parse_json_candidate(candidate)
        except ValueError:
            continue
        if not _extract_payload_triples(parsed):
            continue
        if any(start >= kept_start and end <= kept_end for kept_start, kept_end, _ in kept):
            continue
        kept.append((start, end, parsed))
    return [parsed for _, _, parsed in kept]


def _decode_jsonish_value(raw: str) -> Any:
    candidate = str(raw).strip()
    if not candidate:
        return ""
    try:
        return json.loads(candidate)
    except Exception:
        pass
    try:
        return ast.literal_eval(candidate)
    except Exception:
        lowered = candidate.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in {"null", "none"}:
            return None
        return candidate.strip("\"'")


def _extract_jsonish_field(fragment: str, field_name: str) -> Any:
    pattern = re.compile(
        rf"""["']{re.escape(field_name)}["']\s*:\s*(
            "(?:\\.|[^"\\])*"
            |'(?:\\.|[^'\\])*'
            |-?\d+(?:\.\d+)?
            |true|false|null|None
        )""",
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )
    match = pattern.search(fragment)
    if not match:
        return None
    return _decode_jsonish_value(match.group(1))


def _recover_triples_from_field_fragments(text: str) -> list[dict[str, Any]]:
    subject_key_pattern = re.compile(r"""["']subject["']\s*:""", re.IGNORECASE)
    matches = list(subject_key_pattern.finditer(text))
    if not matches:
        return []

    recovered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        start = match.start()
        brace_start = text.rfind("{", max(0, start - 200), start)
        previous_subject_start = matches[index - 1].start() if index > 0 else -1
        if brace_start != -1 and brace_start > previous_subject_start:
            start = brace_start
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        brace_end = text.find("}", match.end(), end)
        if brace_end != -1:
            end = brace_end + 1
        fragment = text[start:end]
        subject = _extract_jsonish_field(fragment, "subject")
        predicate = _extract_jsonish_field(fragment, "predicate")
        obj = _extract_jsonish_field(fragment, "object")
        if not all(isinstance(item, str) and item.strip() for item in (subject, predicate, obj)):
            continue
        triple = {
            "subject": str(subject).strip(),
            "predicate": str(predicate).strip(),
            "object": str(obj).strip(),
        }
        subject_type = _extract_jsonish_field(fragment, "subject_type")
        object_type = _extract_jsonish_field(fragment, "object_type")
        source_text = _extract_jsonish_field(fragment, "source_text")
        confidence = _extract_jsonish_field(fragment, "confidence")
        if isinstance(subject_type, str) and subject_type.strip():
            triple["subject_type"] = subject_type.strip()
        if isinstance(object_type, str) and object_type.strip():
            triple["object_type"] = object_type.strip()
        if isinstance(source_text, str) and source_text.strip():
            triple["source_text"] = source_text.strip()
        if isinstance(confidence, (int, float)):
            triple["confidence"] = float(confidence)
        elif isinstance(confidence, str):
            try:
                triple["confidence"] = float(confidence.strip())
            except ValueError:
                pass
        signature = json.dumps(triple, ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        recovered.append(triple)
    return recovered


def _recover_triples_payload_from_text(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    recovered: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    def add_triples_from_payload(payload: Any) -> None:
        for item in _extract_payload_triples(payload):
            try:
                signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
            except TypeError:
                signature = repr(sorted(item.items()))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            recovered.append(item)

    for start, char in enumerate(cleaned):
        if char not in "{[":
            continue
        candidate = _extract_balanced_json_candidate(cleaned[start:])
        if not candidate:
            continue
        try:
            parsed = _parse_json_candidate(candidate)
        except ValueError:
            continue
        add_triples_from_payload(parsed)

    for item in _recover_triples_from_field_fragments(cleaned):
        try:
            signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
        except TypeError:
            signature = repr(sorted(item.items()))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        recovered.append(item)

    if recovered:
        return {"triples": recovered}
    return None


def _load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _extract_payload_triples(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    triples = payload.get("triples")
    if isinstance(triples, list):
        return [item for item in triples if isinstance(item, dict)]
    if {"subject", "predicate", "object"} <= set(payload.keys()):
        return [payload]
    return []


def _coerce_payload_to_standard_shape(payload: Any) -> dict[str, Any]:
    meta = payload.get("__meta__") if isinstance(payload, dict) else None
    if isinstance(payload, dict) and isinstance(payload.get("triples"), list):
        result = {
            "triples": [item for item in payload.get("triples", []) if isinstance(item, dict)],
        }
        if isinstance(meta, dict):
            result["__meta__"] = meta
        return result
    triples = _extract_payload_triples(payload)
    if triples:
        result = {"triples": triples}
        if isinstance(meta, dict):
            result["__meta__"] = meta
        return result
    if isinstance(payload, dict):
        return payload
    return {"triples": []}


def _extract_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            value = str(item).strip()
            if value and value not in fact_ids:
                fact_ids.append(value)

    raw_fact_id = str(row.get("fact_id", "")).strip()
    if raw_fact_id and raw_fact_id not in fact_ids:
        fact_ids.append(raw_fact_id)
    return fact_ids


def _dedupe_graph_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_index: dict[tuple[str, str, str, str, str], int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject", "")).strip()
        predicate = str(row.get("predicate", "")).strip()
        obj = str(row.get("object", "")).strip()
        source_book = str(row.get("source_book", "")).strip()
        source_chapter = str(row.get("source_chapter", "")).strip()
        if not subject or not predicate or not obj:
            continue
        signature = (subject, predicate, obj, source_book, source_chapter)
        fact_ids = _extract_fact_ids(row)
        existing_index = seen_index.get(signature)
        if existing_index is not None:
            existing = deduped[existing_index]
            merged_fact_ids = _extract_fact_ids(existing)
            for fact_id in fact_ids:
                if fact_id not in merged_fact_ids:
                    merged_fact_ids.append(fact_id)
            if merged_fact_ids:
                existing["fact_ids"] = merged_fact_ids
                existing["fact_id"] = merged_fact_ids[0]
            continue

        payload = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "subject_type": str(row.get("subject_type", "other")).strip() or "other",
            "object_type": str(row.get("object_type", "other")).strip() or "other",
            "source_book": source_book,
            "source_chapter": source_chapter,
        }
        if fact_ids:
            payload["fact_ids"] = fact_ids
            payload["fact_id"] = fact_ids[0]
        seen_index[signature] = len(deduped)
        deduped.append(payload)

    deduped.sort(
        key=lambda item: (
            item["subject"],
            item["predicate"],
            item["object"],
            item["source_book"],
            item["source_chapter"],
        )
    )
    return deduped


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line.lstrip("\ufeff"))
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _dedupe_evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        fact_id = str(row.get("fact_id", "")).strip()
        if not fact_id or fact_id in seen:
            continue
        seen.add(fact_id)
        deduped.append(
            {
                "fact_id": fact_id,
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                "source_text": str(row.get("source_text", "")).strip(),
                "confidence": float(row.get("confidence", 0.0)),
            }
        )
    deduped.sort(key=lambda item: item["fact_id"])
    return deduped


def _derive_evidence_target_path(graph_target_path: Path) -> Path:
    if graph_target_path.suffix.lower() == ".json":
        return graph_target_path.with_name(f"{graph_target_path.stem}.evidence.jsonl")
    return graph_target_path.parent / f"{graph_target_path.name}.evidence.jsonl"


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


def _detect_formula_titles(text: str, limit: int = 12) -> list[str]:
    titles: list[str] = []
    lines = [line.strip() for line in (text or "").splitlines()]
    for index, line in enumerate(lines):
        if not line:
            continue
        if line.startswith("卷") or line.startswith("属性：") or len(line) > 24:
            continue
        if not any(line.endswith(suffix) for suffix in FORMULA_TITLE_SUFFIXES):
            continue
        lookahead = lines[index + 1:index + 5]
        if not any(item.startswith("属性：") for item in lookahead):
            continue
        if line in titles:
            continue
        titles.append(line)
        if len(titles) >= limit:
            break
    return titles


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


@dataclass
class PipelineConfig:
    books_dir: Path
    output_dir: Path
    model: str
    api_key: str
    base_url: str
    providers: tuple["LLMProviderConfig", ...] = field(default_factory=tuple)
    request_timeout: float = 90.0
    max_chunk_chars: int = 800
    chunk_overlap: int = 200
    max_retries: int = 2
    request_delay: float = 0.8
    parallel_workers: int = 8
    retry_backoff_base: float = 2.0
    chunk_strategy: str = "body_first"


@dataclass(frozen=True)
class LLMProviderConfig:
    name: str
    model: str
    api_key: str
    base_url: str
    weight: int = 1
    enabled: bool = True


@dataclass
class TripleRecord:
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    source_book: str
    source_chapter: str
    source_text: str
    confidence: float
    raw_predicate: str
    raw_subject_type: str
    raw_object_type: str


@dataclass(frozen=True)
class ChunkTask:
    sequence: int
    book_path: Path
    book_name: str
    chapter_name: str
    chunk_index: int
    text_chunk: str


@dataclass(frozen=True)
class CleanDecision:
    keep: bool
    reason: str


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
        if not self.config.books_dir.exists():
            raise FileNotFoundError(f"books_dir_not_found: {self.config.books_dir}")
        return sorted(self.config.books_dir.glob("*.txt"))

    def recommend_books(self, limit: int = 12) -> list[Path]:
        preferred_keywords = (
            "医方",
            "局方",
            "方论",
            "本草纲目",
            "金匮",
            "伤寒",
            "汤头",
            "中医",
        )
        ranked: list[tuple[int, Path]] = []
        for path in self.discover_books():
            score = sum(3 for keyword in preferred_keywords if keyword in path.stem)
            score += max(0, 30 - len(path.stem)) * 0.01
            ranked.append((score, path))
        ranked.sort(key=lambda item: (-item[0], item[1].name))
        return [path for _, path in ranked[:limit]]

    def split_book(self, path: Path) -> list[dict[str, str]]:
        text = _safe_read_text(path)
        text = text.replace("\r\n", "\n")
        parts = re.split(r"(<[^>]+>)", text)
        sections: list[dict[str, str]] = []
        current_title = f"{path.stem}_全文"
        current_body: list[str] = []

        for part in parts:
            chunk = part.strip()
            if not chunk:
                continue
            if chunk.startswith("<") and chunk.endswith(">"):
                if current_body:
                    sections.append({"title": current_title, "content": "\n".join(current_body).strip()})
                current_title = chunk[1:-1].strip() or current_title
                current_body = []
            else:
                current_body.append(chunk)

        if current_body:
            sections.append({"title": current_title, "content": "\n".join(current_body).strip()})

        if not sections and text.strip():
            sections.append({"title": f"{path.stem}_全文", "content": text.strip()})
        return [section for section in sections if section["content"].strip()]

    def _is_weak_section_title(self, title: str, book_name: str) -> bool:
        cleaned = (title or "").strip()
        return cleaned in WEAK_SECTION_TITLES or cleaned in {f"{book_name}_全文", "全文"}

    def _normalize_chunk_label(self, title: str, book_name: str) -> str:
        cleaned = (title or "").strip()
        if not cleaned or self._is_weak_section_title(cleaned, book_name):
            return f"{book_name}_正文"
        return cleaned

    def chunk_text(self, content: str) -> list[tuple[str, int, int]]:
        normalized = re.sub(r"\n{3,}", "\n\n", content.strip())
        if not normalized:
            return []
        if len(normalized) <= self.config.max_chunk_chars:
            return [(normalized, 0, len(normalized))]

        chunks: list[tuple[str, int, int]] = []
        start = 0
        while start < len(normalized):
            end = min(start + self.config.max_chunk_chars, len(normalized))
            if end < len(normalized):
                boundary = normalized.rfind("\n", start, end)
                if boundary > start + self.config.max_chunk_chars // 2:
                    end = boundary
            raw_slice = normalized[start:end]
            left_trim = len(raw_slice) - len(raw_slice.lstrip())
            right_trim = len(raw_slice.rstrip())
            chunk = raw_slice.strip()
            if chunk:
                chunk_start = start + left_trim
                chunk_end = start + right_trim
                chunks.append((chunk, chunk_start, chunk_end))
            if end >= len(normalized):
                break
            start = max(end - self.config.chunk_overlap, start + 1)
        return chunks

    def chunk_section(self, content: str) -> list[str]:
        return [chunk for chunk, _, _ in self.chunk_text(content)]

    def _select_chunk_title(
        self,
        *,
        book_name: str,
        chunk_start: int,
        chunk_end: int,
        ranges: list[tuple[int, int, str]],
    ) -> str:
        best_title = ""
        best_overlap = 0
        for section_start, section_end, title in ranges:
            overlap = min(chunk_end, section_end) - max(chunk_start, section_start)
            if overlap <= 0:
                continue
            if overlap > best_overlap:
                best_overlap = overlap
                best_title = title
        return self._normalize_chunk_label(best_title, book_name)

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
        sections = self.split_book(book_path)
        filtered_sections = [
            section
            for section in sections
            if (not chapter_contains or _match_any_pattern(section["title"], chapter_contains))
            and not _match_any_pattern(section["title"], chapter_excludes)
        ]
        if not filtered_sections:
            return []

        strategy = (chunk_strategy or self.config.chunk_strategy).strip().lower()
        tasks: list[ChunkTask] = []
        sequence = 0

        if strategy == "chapter_first":
            for section in filtered_sections:
                chapter_name = self._normalize_chunk_label(section["title"], book_path.stem)
                for chunk_text, _, _ in self.chunk_text(section["content"]):
                    sequence += 1
                    if sequence <= max(0, skip_initial_chunks_per_book):
                        continue
                    tasks.append(
                        ChunkTask(
                            sequence=sequence,
                            book_path=book_path,
                            book_name=book_path.stem,
                            chapter_name=chapter_name,
                            chunk_index=len(tasks) + 1,
                            text_chunk=chunk_text,
                        )
                    )
                    if max_chunks_per_book is not None and len(tasks) >= max_chunks_per_book:
                        return tasks
            return tasks

        combined_parts: list[str] = []
        ranges: list[tuple[int, int, str]] = []
        cursor = 0
        for section in filtered_sections:
            section_content = re.sub(r"\n{3,}", "\n\n", section["content"].strip())
            if not section_content:
                continue
            if combined_parts:
                combined_parts.append("\n\n")
                cursor += 2
            start = cursor
            combined_parts.append(section_content)
            cursor += len(section_content)
            ranges.append((start, cursor, section["title"]))

        combined_body = "".join(combined_parts)
        for chunk_text, chunk_start, chunk_end in self.chunk_text(combined_body):
            sequence += 1
            if sequence <= max(0, skip_initial_chunks_per_book):
                continue
            tasks.append(
                ChunkTask(
                    sequence=sequence,
                    book_path=book_path,
                    book_name=book_path.stem,
                    chapter_name=self._select_chunk_title(
                        book_name=book_path.stem,
                        chunk_start=chunk_start,
                        chunk_end=chunk_end,
                        ranges=ranges,
                    ),
                    chunk_index=len(tasks) + 1,
                    text_chunk=chunk_text,
                )
            )
            if max_chunks_per_book is not None and len(tasks) >= max_chunks_per_book:
                break
        return tasks

    def build_prompt(self, *, book_name: str, chapter_name: str, text_chunk: str) -> str:
        schema = {
            "triples": [
                {
                    "subject": "实体名称",
                    "predicate": "关系词",
                    "object": "实体名称或概念",
                    "subject_type": "formula|herb|syndrome|symptom|disease|therapy|channel|category|book|chapter|food|medicine|processing_method|property|other",
                    "object_type": "formula|herb|syndrome|symptom|disease|therapy|channel|category|book|chapter|food|medicine|processing_method|property|other",
                    "source_text": "对应原文短句",
                    "confidence": 0.0,
                }
            ]
        }
        formula_titles = _detect_formula_titles(text_chunk)
        formula_hint_block = ""
        if formula_titles:
            title_lines = "\n".join(f"- {title}" for title in formula_titles)
            formula_hint_block = (
                "本 chunk 中按文本结构检测到的候选方剂标题（请逐个检查，不要遗漏）：\n"
                f"{title_lines}\n"
            )
        format_example_block = textwrap.dedent(
            """
            格式约束：
            1. 只输出一个 JSON 对象，顶层必须是 {"triples":[...]}。
            2. 不要输出多个 JSON 对象，不要把每条三元组拆成多个独立 JSON 反复输出。
            3. 不要输出 Markdown 代码块，不要输出解释、分析、说明。

            正确示例：
            {
              "triples": [
                {
                  "subject": "桂枝汤",
                  "predicate": "治疗证候",
                  "object": "太阳中风证",
                  "subject_type": "formula",
                  "object_type": "syndrome",
                  "source_text": "桂枝汤主太阳中风证",
                  "confidence": 0.95
                },
                {
                  "subject": "桂枝汤",
                  "predicate": "使用药材",
                  "object": "桂枝",
                  "subject_type": "formula",
                  "object_type": "herb",
                  "source_text": "桂枝汤用桂枝三两",
                  "confidence": 0.93
                },
                {
                  "subject": "附子",
                  "predicate": "药性",
                  "object": "大热",
                  "subject_type": "medicine",
                  "object_type": "property",
                  "source_text": "附子大热，纯阳有毒",
                  "confidence": 0.91
                }
              ]
            }

            错误示例：
            {"subject":"桂枝汤","predicate":"治疗证候","object":"太阳中风证"}
            {"triples":[...]}
            {"triples":[...]}

            另一个错误示例：
            {
              "triples": [
                {
                  "subject": "本方",
                  "predicate": "使用药材",
                  "object": "甘草",
                  "source_text": "甘草"
                }
              ]
            }
            上例中的“本方”属于泛指主语。若上下文能确定具体方名，必须改写为具体方名；若无法唯一确定，则不要输出该条。

            source_text 错误示例：
            {
              "triples": [
                {
                  "subject": "桂枝汤",
                  "predicate": "使用药材",
                  "object": "桂枝",
                  "source_text": "桂枝"
                }
              ]
            }
            上例中的 source_text 只保留了孤立词语，证据过短。应至少保留能体现主语或关系成立的原文片段，例如“桂枝汤用桂枝三两”。
            """
        ).strip()
        return textwrap.dedent(
            f"""
            你是中医古籍三元组抽取器。请从给定文本中抽取可入图谱的事实。

            书名：{book_name}
            章节：{chapter_name}

            关系标准优先使用以下集合：
            {sorted(ALLOWED_RELATIONS)}

            {formula_hint_block}
            {format_example_block}

            允许你先按原文抽取，再做轻度归一化，但最终输出的 predicate 应尽量落在上述集合。
            如果无法判断，请不要编造。

            输出必须是 JSON 对象，格式如下：
            {json.dumps(schema, ensure_ascii=False, indent=2)}

            规则：
            1. 只抽取文本里明确出现或强明示的事实。
            2. source_text 必须是原文短句或原文片段，不要改写成长解释。
            3. confidence 取 0 到 1 之间的小数。
            4. 不要输出任何 JSON 之外的说明文字。
            5. 若没有合适三元组，返回 {{"triples":[]}}。
            6. 同一个 chunk 中如果出现多个方名/药名/证候块，必须继续向后抽取，不要只返回第一条或最显眼的一条。
            7. 若出现“方名 + 属性/组成/评语”结构，优先覆盖每个方名块；每个方名块至少尝试抽取“属于范畴 / 使用药材 / 功效 / 治疗证候 / 治疗症状 / 别名”中原文明确出现的事实。
            8. 不要只抽取“出处”这类书目信息；只有在缺乏更有价值的领域事实时，才保留出处。
            9. 如果同一 chunk 里有多个连续方剂条目，输出应覆盖所有能识别出的条目，而不是只挑一个示例。
            10. 先在脑中完整扫描全文，再一次性输出结果；禁止因为看到了第一个方名就停止抽取后文。
            11. 如果 chunk 中出现多个方剂标题，例如“某某丸 / 某某汤 / 某某散 / 某某饮 / 某某丹”，通常应为每个标题至少抽取 1 到 3 条事实；若只输出 1 条，通常说明漏抽。
            12. 遇到“卷X\\某某之剂 + 方名 + 属性：...”的结构时：
                卷名/某某之剂通常对应“属于范畴”
                属性中的药物列表通常对应“使用药材”
                紧随其后的评语通常对应“功效 / 治疗证候 / 治疗症状 / 治法”
            13. 只要原文中出现了明确药物名，不要省略“使用药材”关系；这类关系是优先级最高的抽取目标之一。
            14. 优先输出高信息量的领域事实，少输出低价值的“出处”；如果一个方名块里已经能抽到药材、功效、证候，就不要只给出处。
            15. 输出前自检：确认是否已经覆盖 chunk 内每个可识别的方名块；若没有，继续补充后再输出。
            16. 若文本是本草、药性、食疗、炮制或禁忌类内容，不要强行套用“方剂-证候”模板；应优先抽取“食忌 / 配伍禁忌 / 用法 / 药性 / 五味 / 升降浮沉”等关系。
            17. 当对象是寒热温凉、甘辛酸苦咸、升降浮沉、有毒无毒等性质词时，object_type 优先标为 property。
            18. 当对象是炒、炙、煅、煨、蒸、煮、焙、酒浸、水煎、丸服、散服、外敷等加工或服用方式时，object_type 优先标为 processing_method。
            19. 当主语或宾语是食物禁忌对象时可使用 food；当是一般药物名但不必细分时可使用 medicine。
            20. subject 和 object 必须尽量使用具体实体名，如具体方名、药名、食物名、证候名、症状名；不要偷懒写成“本方 / 此方 / 治方 / 其方 / 该方 / 本药 / 此药 / 其药 / 药 / 诸药”等泛指词。
            21. 如果原文出现“本方 / 此方 / 其方 / 其药 / 该药”等指代，必须结合上下文回指到唯一的具体方名或药名后再输出；若不能唯一回指，则宁可不抽，也不要输出泛主语三元组。
            22. 对“使用药材 / 用法 / 药性 / 五味 / 升降浮沉 / 配伍禁忌 / 食忌”这类关系，若原文能定位到具体药物或具体方剂，subject 不得写成“药 / 本方 / 治方”等笼统名称。
            23. source_text 不能只截取一个孤立词语；至少保留能支撑该关系成立的最短原文片段。若只写“甘草”“人参”这类单词，通常说明证据片段过短。
            24. 若一个 chunk 中包含多个具体方名或药名，不要把它们合并概括为一个笼统主语；应分别挂到各自的具体实体上。
            25. 对“使用药材 / 药性 / 五味 / 用法 / 食忌 / 配伍禁忌”这类关系，source_text 优先包含主语名 + 关系触发词或性质词，不要只截对象本身。

            原文：
            {text_chunk}
            """
        ).strip()

    def build_compact_prompt(self, *, book_name: str, chapter_name: str, text_chunk: str) -> str:
        schema = {
            "triples": [
                {
                    "subject": "实体名",
                    "predicate": "关系词",
                    "object": "实体名或概念",
                    "subject_type": "formula|herb|syndrome|symptom|disease|therapy|channel|category|book|chapter|food|medicine|processing_method|property|other",
                    "object_type": "formula|herb|syndrome|symptom|disease|therapy|channel|category|book|chapter|food|medicine|processing_method|property|other",
                    "source_text": "原文短句",
                    "confidence": 0.0,
                }
            ]
        }
        formula_titles = _detect_formula_titles(text_chunk)
        title_hint = ""
        if formula_titles:
            title_hint = "候选方剂标题：" + "、".join(formula_titles[:12])
        format_hint = textwrap.dedent(
            """
            输出时只允许返回一个 JSON 对象，格式固定为 {"triples":[...]}。
            不要输出多个 JSON 对象，不要追加解释，不要使用 Markdown 代码块。
            如果有多条三元组，必须全部放在同一个 triples 数组里。

            source_text 正确示例：
            "source_text": "桂枝汤用桂枝三两"
            source_text 错误示例：
            "source_text": "桂枝"
            """
        ).strip()
        return textwrap.dedent(
            f"""
            任务：从中医古籍片段中尽可能完整抽取三元组，返回且仅返回 JSON 对象。
            书名：{book_name}
            章节：{chapter_name}
            {title_hint}
            {format_hint}

            关系优先使用：{sorted(ALLOWED_RELATIONS)}
            重点：如果一个 chunk 内出现多个方剂标题或多个条目，必须覆盖所有可识别条目，不要只返回第一条。
            如果原文出现明确药物名，优先抽取“使用药材”。
            如果文本更像本草/禁忌/药性/炮制说明，优先抽取“食忌 / 配伍禁忌 / 用法 / 药性 / 五味 / 升降浮沉”。
            主语和宾语优先写具体方名、药名、食物名，不要写“本方 / 此方 / 治方 / 药 / 其药”等泛指词；能回指就回指，不能唯一回指就不要输出。
            source_text 不要只保留单个词，至少保留能支撑关系判断的原文短片段。
            对“使用药材 / 药性 / 五味 / 用法 / 食忌 / 配伍禁忌”，source_text 最好同时带上主语名或关系判断依据，不要只写对象词。
            如果没有可抽取事实，返回 {{"triples":[]}}。

            输出格式：
            {json.dumps(schema, ensure_ascii=False, indent=2)}

            原文：
            {text_chunk}
            """
        ).strip()

    def build_prompt_variant(self, *, book_name: str, chapter_name: str, text_chunk: str, variant: str = "current") -> str:
        normalized_variant = (variant or "current").strip().lower()
        if normalized_variant == "compact":
            return self.build_compact_prompt(book_name=book_name, chapter_name=chapter_name, text_chunk=text_chunk)
        return self.build_prompt(book_name=book_name, chapter_name=chapter_name, text_chunk=text_chunk)

    def _select_provider_sequence(self) -> list[LLMProviderConfig]:
        enabled_names = [provider.name for provider in self.config.providers if provider.enabled]
        if not enabled_names:
            return []
        with self._provider_lock:
            if not self._provider_rotation:
                ordered_names = enabled_names
            else:
                start = self._provider_cursor % len(self._provider_rotation)
                self._provider_cursor = (self._provider_cursor + 1) % max(len(self._provider_rotation), 1)
                rotated = self._provider_rotation[start:] + self._provider_rotation[:start]
                ordered_names = []
                seen: set[str] = set()
                for name in rotated:
                    if name in seen:
                        continue
                    seen.add(name)
                    ordered_names.append(name)
                for name in enabled_names:
                    if name not in seen:
                        ordered_names.append(name)
        return [self._providers_by_name[name] for name in ordered_names if name in self._providers_by_name]

    def _record_provider_result(
        self,
        provider_name: str,
        *,
        success: bool,
        latency_ms: float,
        error: str = "",
    ) -> None:
        with self._provider_lock:
            stats = self._provider_stats.setdefault(
                provider_name,
                {
                    "success_count": 0,
                    "failure_count": 0,
                    "consecutive_failures": 0,
                    "last_error": "",
                    "last_latency_ms": 0.0,
                    "total_latency_ms": 0.0,
                    "latency_sample_count": 0,
                },
            )
            stats["last_latency_ms"] = round(float(latency_ms), 2)
            stats["total_latency_ms"] = round(float(stats.get("total_latency_ms", 0.0)) + float(latency_ms), 2)
            stats["latency_sample_count"] = int(stats.get("latency_sample_count", 0)) + 1
            if success:
                stats["success_count"] = int(stats.get("success_count", 0)) + 1
                stats["consecutive_failures"] = 0
                stats["last_error"] = ""
            else:
                stats["failure_count"] = int(stats.get("failure_count", 0)) + 1
                stats["consecutive_failures"] = int(stats.get("consecutive_failures", 0)) + 1
                stats["last_error"] = error[:300]

    def get_provider_metrics(self) -> list[dict[str, Any]]:
        metrics: list[dict[str, Any]] = []
        with self._provider_lock:
            for provider in self.config.providers:
                stats = self._provider_stats.get(provider.name, {})
                success_count = int(stats.get("success_count", 0) or 0)
                failure_count = int(stats.get("failure_count", 0) or 0)
                attempt_count = success_count + failure_count
                latency_sample_count = int(stats.get("latency_sample_count", 0) or 0)
                total_latency_ms = float(stats.get("total_latency_ms", 0.0) or 0.0)
                metrics.append(
                    {
                        "name": provider.name,
                        "model": provider.model,
                        "base_url": provider.base_url,
                        "weight": int(provider.weight),
                        "enabled": bool(provider.enabled),
                        "attempt_count": attempt_count,
                        "success_count": success_count,
                        "failure_count": failure_count,
                        "success_rate": round(success_count / attempt_count, 4) if attempt_count else 0.0,
                        "failure_rate": round(failure_count / attempt_count, 4) if attempt_count else 0.0,
                        "avg_latency_ms": round(total_latency_ms / latency_sample_count, 2) if latency_sample_count else 0.0,
                        "last_latency_ms": round(float(stats.get("last_latency_ms", 0.0) or 0.0), 2),
                        "consecutive_failures": int(stats.get("consecutive_failures", 0) or 0),
                        "last_error": str(stats.get("last_error", "") or ""),
                    }
                )
        return metrics

    def format_provider_metrics_summary(self) -> str:
        metrics = self.get_provider_metrics()
        if not metrics:
            return "provider-monitor: no providers configured"
        parts = []
        for item in metrics:
            parts.append(
                f"{item['name']} ok={item['success_count']} fail={item['failure_count']} "
                f"succ={item['success_rate']:.1%} failr={item['failure_rate']:.1%} "
                f"avg={item['avg_latency_ms']:.0f}ms last={item['last_latency_ms']:.0f}ms"
            )
        return " | ".join(parts)

    def _call_llm_raw_once(
        self,
        provider: LLMProviderConfig,
        prompt: str,
        *,
        response_format_mode: str = "json_object",
    ) -> dict[str, Any]:
        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": provider.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Connection": "close",
        }

        normalized_mode = (response_format_mode or "json_object").strip().lower()
        if normalized_mode not in {"json_object", "text"}:
            raise ValueError(f"unsupported_response_format_mode: {response_format_mode}")

        request_payload = dict(payload)
        if normalized_mode == "json_object":
            request_payload["response_format"] = {"type": "json_object"}

        started_at = time.perf_counter()
        with httpx.Client(timeout=self.config.request_timeout, http2=False) as client:
            response = client.post(url, headers=headers, json=request_payload)
            response.raise_for_status()
            body = response.json()
        latency_ms = (time.perf_counter() - started_at) * 1000
        choices = body.get("choices", [])
        if not choices:
            raise ValueError("llm_empty_choices")
        content = choices[0].get("message", {}).get("content", "")
        return {
            "raw_text": str(content),
            "usage": body.get("usage", {}) if isinstance(body.get("usage"), dict) else {},
            "finish_reason": choices[0].get("finish_reason"),
            "response_format_mode": normalized_mode,
            "raw_body": body,
            "provider_name": provider.name,
            "provider_model": provider.model,
            "provider_base_url": provider.base_url,
            "provider_latency_ms": round(latency_ms, 2),
        }

    def call_llm_raw(
        self,
        prompt: str,
        *,
        response_format_mode: str = "json_object",
        provider_sequence: list[LLMProviderConfig] | None = None,
    ) -> dict[str, Any]:
        providers = provider_sequence or self._select_provider_sequence()
        if not providers:
            raise RuntimeError("llm_provider_not_configured")
        last_error: Exception | None = None
        total_attempts = max(self.config.max_retries + 1, len(providers))
        for attempt in range(total_attempts):
            provider = providers[attempt % len(providers)]
            attempt_started_at = time.perf_counter()
            try:
                meta = self._call_llm_raw_once(
                    provider,
                    prompt,
                    response_format_mode=response_format_mode,
                )
                self._record_provider_result(
                    provider.name,
                    success=True,
                    latency_ms=float(meta.get("provider_latency_ms", 0.0) or 0.0),
                )
                return meta
            except httpx.HTTPStatusError as exc:
                last_error = exc
                latency_ms = (time.perf_counter() - attempt_started_at) * 1000
                self._record_provider_result(
                    provider.name,
                    success=False,
                    latency_ms=latency_ms,
                    error=f"http_{exc.response.status_code if exc.response is not None else 'unknown'}: {str(exc)}",
                )
                if attempt < total_attempts - 1:
                    backoff = self.config.retry_backoff_base * (2 ** attempt)
                    time.sleep(min(backoff, 20.0))
            except Exception as exc:
                last_error = exc
                latency_ms = (time.perf_counter() - attempt_started_at) * 1000
                self._record_provider_result(
                    provider.name,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
                if attempt < total_attempts - 1:
                    backoff = self.config.retry_backoff_base * (2 ** attempt)
                    time.sleep(min(backoff, 20.0))
        raise RuntimeError(f"llm_request_failed: {last_error}")

    def call_llm(self, prompt: str) -> dict[str, Any]:
        provider_sequence = self._select_provider_sequence()
        last_error: Exception | None = None
        for response_format_mode in ("json_object", "text"):
            try:
                meta = self.call_llm_raw(
                    prompt,
                    response_format_mode=response_format_mode,
                    provider_sequence=provider_sequence,
                )
                parsed = _extract_json_block(str(meta.get("raw_text", "")))
                if isinstance(parsed, list):
                    return {"triples": parsed, "__meta__": meta}
                if isinstance(parsed, dict):
                    result = dict(parsed)
                    result["__meta__"] = meta
                    return result
                raise ValueError("llm_json_invalid_shape")
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if response_format_mode == "json_object" and exc.response is not None and exc.response.status_code in {400, 415, 422}:
                    response_text = exc.response.text.lower()
                    if "response_format" in response_text or "json_object" in response_text or "json_schema" in response_text:
                        continue
                break
            except Exception as exc:
                last_error = exc
                if response_format_mode == "json_object":
                    continue
                break
        raise RuntimeError(f"llm_request_failed: {last_error}")

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

        cleaned_jsonl.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cleaned_payload_rows),
            encoding="utf-8",
        )
        self.write_csv(cleaned_csv, cleaned_rows)
        graph_facts_jsonl.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in graph_fact_rows),
            encoding="utf-8",
        )
        graph_facts_json.write_text(json.dumps(graph_fact_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        evidence_metadata_jsonl.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evidence_rows),
            encoding="utf-8",
        )

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
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def save_manifest(self, run_dir: Path, payload: dict[str, Any]) -> None:
        (run_dir / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def write_csv(self, path: Path, rows: list[TripleRecord]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "subject",
                    "predicate",
                    "object",
                    "subject_type",
                    "object_type",
                    "source_book",
                    "source_chapter",
                    "source_text",
                    "confidence",
                    "raw_predicate",
                    "raw_subject_type",
                    "raw_object_type",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))

    def write_graph_import(self, path: Path, rows: list[TripleRecord]) -> None:
        payload = [
            {
                "subject": row.subject,
                "predicate": row.predicate,
                "object": row.object,
                "subject_type": row.subject_type,
                "object_type": row.object_type,
                "source_book": row.source_book,
                "source_chapter": row.source_chapter,
            }
            for row in rows
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def publish_graph(
        self,
        *,
        graph_import_path: Path | None = None,
        run_dir: Path | None = None,
        target_path: Path | None = None,
        replace: bool = False,
    ) -> Path:
        evidence_source_path: Path | None = None
        if graph_import_path is None:
            chosen_run_dir = run_dir or self.latest_run()
            if chosen_run_dir is None:
                raise FileNotFoundError("no_run_dir_available")
            cleaned_graph_path = chosen_run_dir / "graph_facts.cleaned.json"
            graph_import_path = cleaned_graph_path if cleaned_graph_path.exists() else chosen_run_dir / "graph_import.json"
            candidate_evidence_path = chosen_run_dir / "evidence_metadata.jsonl"
            if candidate_evidence_path.exists():
                evidence_source_path = candidate_evidence_path
        else:
            candidate_evidence_path = graph_import_path.parent / "evidence_metadata.jsonl"
            if candidate_evidence_path.exists():
                evidence_source_path = candidate_evidence_path

        if not graph_import_path.exists():
            raise FileNotFoundError(f"graph_import_not_found: {graph_import_path}")

        target = target_path or DEFAULT_GRAPH_TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        evidence_target_path = _derive_evidence_target_path(target)

        incoming = _load_json_file(graph_import_path, [])
        if not isinstance(incoming, list):
            raise ValueError("graph_import_invalid")

        base_rows: list[dict[str, Any]] = []
        if not replace and target.exists():
            existing = _load_json_file(target, [])
            if isinstance(existing, list):
                base_rows = existing
        elif not replace and target == DEFAULT_GRAPH_TARGET and DEFAULT_GRAPH_BASE.exists():
            base_graph = _load_json_file(DEFAULT_GRAPH_BASE, [])
            if isinstance(base_graph, list):
                base_rows = base_graph

        merged = _dedupe_graph_rows(base_rows + incoming)
        target.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

        base_evidence_rows: list[dict[str, Any]] = []
        if not replace and evidence_target_path.exists():
            base_evidence_rows = _load_jsonl_rows(evidence_target_path)

        incoming_evidence_rows = _load_jsonl_rows(evidence_source_path) if evidence_source_path else []
        if base_evidence_rows or incoming_evidence_rows:
            merged_evidence_rows = _dedupe_evidence_rows(base_evidence_rows + incoming_evidence_rows)
            evidence_target_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged_evidence_rows),
                encoding="utf-8",
            )
        return target

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
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

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
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            if not tasks:
                state["books_completed"] = book_index
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                continue

            results: dict[int, dict[str, Any]] = {}
            if dry_run or self.config.parallel_workers <= 1 or len(tasks) == 1:
                for task in tasks:
                    state["current_chapter"] = task.chapter_name
                    state["current_chunk_index"] = task.chunk_index
                    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
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
                    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
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
                        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

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
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        self.write_csv(run_dir / "triples.normalized.csv", all_rows)
        self.write_graph_import(run_dir / "graph_import.json", all_rows)
        state["status"] = "completed"
        state["total_triples"] = len(all_rows)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_dir

    def latest_run(self) -> Path | None:
        if not self.config.output_dir.exists():
            return None
        runs = sorted((path for path in self.config.output_dir.iterdir() if path.is_dir()), reverse=True)
        return runs[0] if runs else None


def build_config(args: argparse.Namespace) -> PipelineConfig:
    model = args.model or _first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="mimo-v2-pro")
    api_key = _first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = _first_env("TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.siliconflow.cn/v1")
    if not api_key and not args.dry_run:
        raise RuntimeError("missing_llm_api_key")
    providers = _normalize_provider_configs(
        [],
        fallback_model=model,
        fallback_api_key=api_key,
        fallback_base_url=base_url,
    )

    return PipelineConfig(
        books_dir=Path(args.books_dir) if args.books_dir else DEFAULT_BOOKS_DIR,
        output_dir=Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR,
        model=model,
        api_key=api_key,
        base_url=base_url,
        providers=providers,
        request_timeout=float(args.timeout),
        max_chunk_chars=int(args.max_chunk_chars),
        chunk_overlap=int(args.chunk_overlap),
        max_retries=int(args.max_retries),
        request_delay=float(args.request_delay),
        parallel_workers=max(1, int(args.parallel_workers)),
        retry_backoff_base=float(args.retry_backoff_base),
        chunk_strategy=str(args.chunk_strategy or "body_first"),
    )


def print_books(books: list[Path]) -> None:
    for index, book in enumerate(books, start=1):
        print(f"{index:>3}. {book.stem}")


def print_run_summary(summary: dict[str, Any]) -> None:
    print(f"run_dir: {summary.get('run_dir', '')}")
    print(f"status: {summary.get('status', '')}")
    print(f"books: {summary.get('books_completed', 0)}/{summary.get('books_total', 0)}")
    print(f"triples: {summary.get('total_triples', 0)}")
    print(f"dry_run: {summary.get('dry_run', False)}")
    if summary.get("model"):
        print(f"model: {summary['model']}")


def print_run_audit(audit: dict[str, Any]) -> None:
    print_run_summary(audit.get("summary", {}))
    config = audit.get("config", {})
    print(f"chapter_excludes: {config.get('chapter_excludes', [])}")
    print(f"skip_initial_chunks_per_book: {config.get('skip_initial_chunks_per_book', 0)}")
    print(f"chunk_strategy: {config.get('chunk_strategy', 'body_first')}")
    print(f"parallel_workers: {config.get('parallel_workers', 1)}")
    if audit.get("sample_chapters"):
        print(f"sample_chapters: {audit['sample_chapters']}")
    print("sample_rows:")
    for index, row in enumerate(audit.get("sample_rows", []), start=1):
        print(
            f"{index:>2}. [{row.get('source_chapter', '')}] "
            f"{row.get('subject', '')} -{row.get('predicate', '')}-> {row.get('object', '')}"
        )


def print_clean_report(report: dict[str, Any]) -> None:
    print(f"run_dir: {report.get('run_dir', '')}")
    print(f"input_total: {report.get('input_total', 0)}")
    print(f"kept_total: {report.get('kept_total', 0)}")
    print(f"dropped_total: {report.get('dropped_total', 0)}")
    print("reason_counts:")
    for key, value in sorted((report.get("reason_counts") or {}).items()):
        print(f"  {key}: {value}")


def resolve_selected_books(pipeline: TCMTriplePipeline, raw_value: str, fallback_limit: int) -> list[Path]:
    books = pipeline.discover_books()
    selected: list[Path] = []

    if raw_value.strip():
        tokens = [token.strip() for token in raw_value.split(",") if token.strip()]
        for token in tokens:
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(books):
                    selected.append(books[idx - 1])
            else:
                selected.extend([book for book in books if token in book.stem])
    else:
        selected = pipeline.recommend_books(limit=min(fallback_limit, 6))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in selected:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def resolve_single_book(pipeline: TCMTriplePipeline, raw_value: str) -> Path | None:
    matches = resolve_selected_books(pipeline, raw_value, fallback_limit=1)
    return matches[0] if matches else None


def resolve_chapter_excludes(raw_value: str, use_default_excludes: bool) -> list[str] | None:
    user_excludes = _split_keywords(raw_value)
    default_excludes = DEFAULT_CHAPTER_EXCLUDES if use_default_excludes else []
    merged = _merge_keywords(default_excludes, user_excludes)
    return merged or None


def print_chapters(pipeline: TCMTriplePipeline, book_path: Path, limit: int) -> None:
    print(f"book: {book_path.stem}")
    for index, section in enumerate(pipeline.split_book(book_path)[:limit], start=1):
        print(f"{index:>3}. {section['title']}")


def interactive_main(pipeline: TCMTriplePipeline, args: argparse.Namespace) -> int:
    print("TCM Triple Pipeline Console")
    print(f"books_dir: {pipeline.config.books_dir}")
    print(f"output_dir: {pipeline.config.output_dir}")
    print(f"model: {pipeline.config.model}")
    print(f"base_url: {pipeline.config.base_url}")

    while True:
        print("\n选择操作:")
        print("1. 列出全部书目")
        print("2. 推荐首批书目")
        print("3. 查看某本书的章节")
        print("4. 提取指定书目")
        print("5. 查看最新运行目录")
        print("6. 抽检最新运行结果")
        print("7. 清洗最新运行结果")
        print("8. 发布最新运行到图谱 JSON")
        print("9. 退出")
        choice = input("输入编号: ").strip()

        if choice == "1":
            print_books(pipeline.discover_books())
            continue
        if choice == "2":
            print_books(pipeline.recommend_books())
            continue
        if choice == "3":
            books = pipeline.discover_books()
            print_books(books[:40])
            raw = input("输入单本书的编号或关键词: ").strip()
            book_path = resolve_single_book(pipeline, raw)
            if book_path is None:
                print("未找到对应书目。")
                continue
            print_chapters(pipeline, book_path, limit=40)
            continue
        if choice == "4":
            books = pipeline.discover_books()
            print_books(books[:40])
            raw = input("输入书目编号，逗号分隔；直接回车则使用推荐书单: ").strip()
            selected = resolve_selected_books(pipeline, raw, fallback_limit=6)
            if not selected:
                print("未选择任何书目。")
                continue
            dry_run = input("是否 dry-run（yes/no，默认 no）: ").strip().lower() in {"y", "yes"}
            max_chunks_raw = input("每本最多处理多少 chunk（回车表示不限）: ").strip()
            max_chunks = int(max_chunks_raw) if max_chunks_raw.isdigit() else None
            chapter_contains_raw = input("仅处理包含这些章节关键词（逗号分隔，可空）: ").strip()
            chapter_excludes_raw = input("跳过包含这些章节关键词（逗号分隔，可空；默认不过滤）: ").strip()
            skip_chunks_raw = input("每本书跳过前多少个 chunk（默认 0）: ").strip()
            skip_chunks = int(skip_chunks_raw) if skip_chunks_raw.isdigit() else 0
            strategy_raw = input("切块策略（body_first/chapter_first，默认 body_first）: ").strip().lower() or "body_first"
            workers_raw = input(f"并行 worker 数（默认 {pipeline.config.parallel_workers}）: ").strip()
            parallel_workers = int(workers_raw) if workers_raw.isdigit() else pipeline.config.parallel_workers
            label = input("运行标签（回车默认 interactive）: ").strip() or "interactive"
            pipeline.config.parallel_workers = max(1, parallel_workers)
            pipeline.config.chunk_strategy = strategy_raw
            run_dir = pipeline.extract_books(
                selected_books=selected,
                label=label,
                max_chunks_per_book=max_chunks,
                dry_run=dry_run,
                chapter_contains=_split_keywords(chapter_contains_raw) or None,
                chapter_excludes=resolve_chapter_excludes(chapter_excludes_raw, use_default_excludes=False),
                skip_initial_chunks_per_book=skip_chunks,
                chunk_strategy=strategy_raw,
            )
            print_run_summary(pipeline.summarize_run_dir(run_dir))
            continue
        if choice == "5":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无运行目录")
            else:
                print_run_summary(pipeline.summarize_run_dir(latest))
            continue
        if choice == "6":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可抽检的运行目录")
                continue
            print_run_audit(pipeline.audit_run_dir(latest, limit=8))
            continue
        if choice == "7":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可清洗的运行目录")
                continue
            print_clean_report(pipeline.clean_run_dir(latest))
            continue
        if choice == "8":
            latest = pipeline.latest_run()
            if latest is None:
                print("暂无可发布的运行目录")
                continue
            target_raw = input(
                f"目标图谱文件（回车默认 {DEFAULT_GRAPH_TARGET}）: "
            ).strip()
            replace = input("是否覆盖目标文件（yes/no，默认 no）: ").strip().lower() in {"y", "yes"}
            target_path = Path(target_raw) if target_raw else DEFAULT_GRAPH_TARGET
            published = pipeline.publish_graph(run_dir=latest, target_path=target_path, replace=replace)
            print(f"已发布到: {published}")
            continue
        if choice == "9":
            return 0
        print("无效输入。")


def cli_main() -> int:
    parser = argparse.ArgumentParser(description="Interactive TCM triple extraction pipeline.")
    parser.add_argument(
        "command",
        nargs="?",
        default="interactive",
        choices=["interactive", "list", "recommend", "chapters", "extract", "latest", "audit-run", "clean-run", "publish-graph"],
    )
    parser.add_argument("--books-dir", default="", help="Books directory.")
    parser.add_argument("--output-dir", default="", help="Output directory.")
    parser.add_argument("--model", default="", help="Override extraction model.")
    parser.add_argument("--timeout", default=90, type=float, help="LLM request timeout.")
    parser.add_argument("--max-chunk-chars", default=800, type=int, help="Max chars per chunk.")
    parser.add_argument("--chunk-overlap", default=200, type=int, help="Chunk overlap chars.")
    parser.add_argument("--max-retries", default=2, type=int, help="LLM request retries.")
    parser.add_argument("--retry-backoff-base", default=2.0, type=float, help="Base seconds for exponential retry backoff.")
    parser.add_argument("--request-delay", default=0.8, type=float, help="Delay between requests.")
    parser.add_argument("--parallel-workers", default=8, type=int, help="Parallel worker count for chunk extraction.")
    parser.add_argument("--chunk-strategy", default="body_first", choices=["body_first", "chapter_first"], help="Chunk scheduling strategy.")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic triples instead of real LLM calls.")
    parser.add_argument("--books", default="", help="Comma-separated book indices or names for extract mode.")
    parser.add_argument("--book", default="", help="Single book index or fuzzy name for chapters mode.")
    parser.add_argument("--limit", default=12, type=int, help="List/recommend limit.")
    parser.add_argument("--max-chunks-per-book", default=0, type=int, help="Limit chunks per book during extraction.")
    parser.add_argument("--label", default="manual", help="Run label.")
    parser.add_argument("--chapter-contains", default="", help="Only process chapters whose title contains these keywords.")
    parser.add_argument("--chapter-excludes", default="", help="Skip chapters whose title contains these keywords.")
    parser.add_argument("--use-default-excludes", action="store_true", help="Append default metadata chapter excludes.")
    parser.add_argument("--no-default-excludes", action="store_true", help="Do not auto-append default metadata chapter excludes.")
    parser.add_argument("--skip-initial-chunks", default=0, type=int, help="Skip the first N chunks per book before extraction.")
    parser.add_argument("--run-dir", default="", help="Existing run directory for publish-graph.")
    parser.add_argument("--graph-import", default="", help="Explicit graph_import.json path for publish-graph.")
    parser.add_argument("--target-graph", default="", help="Target graph JSON path for publish-graph.")
    parser.add_argument("--audit-limit", default=8, type=int, help="How many normalized rows to print in audit-run.")
    parser.add_argument("--replace", action="store_true", help="Replace target graph file instead of merge.")
    args = parser.parse_args()

    pipeline = TCMTriplePipeline(build_config(args))

    if args.command == "interactive":
        return interactive_main(pipeline, args)
    if args.command == "list":
        print_books(pipeline.discover_books()[: args.limit])
        return 0
    if args.command == "recommend":
        print_books(pipeline.recommend_books(limit=args.limit))
        return 0
    if args.command == "chapters":
        book_path = resolve_single_book(pipeline, args.book)
        if book_path is None:
            raise SystemExit("book_not_found")
        print_chapters(pipeline, book_path, limit=args.limit)
        return 0
    if args.command == "latest":
        latest = pipeline.latest_run()
        if latest:
            print_run_summary(pipeline.summarize_run_dir(latest))
        return 0
    if args.command == "audit-run":
        run_dir = Path(args.run_dir) if args.run_dir else pipeline.latest_run()
        if run_dir is None:
            raise SystemExit("run_dir_not_found")
        print_run_audit(pipeline.audit_run_dir(run_dir, limit=max(1, args.audit_limit)))
        return 0
    if args.command == "clean-run":
        run_dir = Path(args.run_dir) if args.run_dir else pipeline.latest_run()
        if run_dir is None:
            raise SystemExit("run_dir_not_found")
        print_clean_report(pipeline.clean_run_dir(run_dir))
        return 0
    if args.command == "extract":
        deduped = resolve_selected_books(pipeline, args.books, fallback_limit=args.limit)
        run_dir = pipeline.extract_books(
            selected_books=deduped,
            label=args.label,
            max_chunks_per_book=args.max_chunks_per_book or None,
            dry_run=args.dry_run,
            chapter_contains=_split_keywords(args.chapter_contains) or None,
            chapter_excludes=resolve_chapter_excludes(
                args.chapter_excludes,
                use_default_excludes=args.use_default_excludes and not args.no_default_excludes,
            ),
            skip_initial_chunks_per_book=max(0, args.skip_initial_chunks),
            chunk_strategy=args.chunk_strategy,
        )
        print_run_summary(pipeline.summarize_run_dir(run_dir))
        return 0
    if args.command == "publish-graph":
        run_dir = Path(args.run_dir) if args.run_dir else None
        graph_import_path = Path(args.graph_import) if args.graph_import else None
        target_path = Path(args.target_graph) if args.target_graph else DEFAULT_GRAPH_TARGET
        published = pipeline.publish_graph(
            graph_import_path=graph_import_path,
            run_dir=run_dir,
            target_path=target_path,
            replace=args.replace,
        )
        print(published)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
