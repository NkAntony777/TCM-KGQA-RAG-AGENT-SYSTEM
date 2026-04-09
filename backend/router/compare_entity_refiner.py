from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from config import Settings, get_settings

COMPARE_NOISE_TERMS = {
    "咳者",
    "人参",
    "大枣",
    "生姜",
    "五味子",
    "干姜",
    "加减法",
    "和解少阳",
    "少阳咳",
    "病机",
    "治法",
    "配伍",
    "功效",
    "主治",
    "出处",
    "原文",
    "来源",
}
COMPARE_NOISE_PREFIXES = ("请从", "请结合", "分析", "论述", "论证", "比较", "鉴别", "说明", "解释")
TARGET_SUFFIXES = ("汤", "散", "丸", "饮", "膏", "丹", "方", "颗粒", "胶囊", "证", "法", "论")
FORMULA_TRAILING_SUFFIXES = ("汤方", "散方", "丸方", "饮方", "膏方", "丹方")


@dataclass(frozen=True)
class CompareEntityRefineResult:
    compare_entities: list[str]
    primary_entity: str
    backend: str
    notes: list[str]


class CompareEntityRefiner:
    def __init__(self, *, settings: Settings | None = None, timeout_seconds: float = 8.0) -> None:
        self.settings = settings or get_settings()
        self.timeout_seconds = timeout_seconds

    def refine(
        self,
        *,
        query: str,
        compare_entities: list[str],
        primary_entity: str,
    ) -> CompareEntityRefineResult:
        cleaned = _heuristic_compare_cleanup(compare_entities=compare_entities, primary_entity=primary_entity)
        if not _should_use_llm_refinement(query=query, compare_entities=cleaned):
            return CompareEntityRefineResult(
                compare_entities=cleaned,
                primary_entity=_resolve_primary_entity(primary_entity=primary_entity, compare_entities=cleaned),
                backend="heuristic",
                notes=[],
            )
        if not self.settings.llm_api_key:
            return CompareEntityRefineResult(
                compare_entities=cleaned,
                primary_entity=_resolve_primary_entity(primary_entity=primary_entity, compare_entities=cleaned),
                backend="heuristic_no_llm",
                notes=["compare_entities_llm_refine_skipped:no_llm_api_key"],
            )
        try:
            refined = self._llm_refine(query=query, compare_entities=cleaned, primary_entity=primary_entity)
            return CompareEntityRefineResult(
                compare_entities=refined,
                primary_entity=_resolve_primary_entity(primary_entity=primary_entity, compare_entities=refined),
                backend="llm",
                notes=["compare_entities_llm_refined"],
            )
        except Exception as exc:
            return CompareEntityRefineResult(
                compare_entities=cleaned,
                primary_entity=_resolve_primary_entity(primary_entity=primary_entity, compare_entities=cleaned),
                backend="heuristic_fallback",
                notes=[f"compare_entities_llm_refine_failed:{exc}"],
            )

    def _llm_refine(self, *, query: str, compare_entities: list[str], primary_entity: str) -> list[str]:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是中医问答系统的比较对象提取器。"
                        "你的任务是从候选实体中筛出真正需要比较的核心对象。"
                        "只保留方剂、证候、治法、经典文本中真正构成比较对照的对象。"
                        "去掉药味、普通术语、修饰语、提示词、加减动作词。"
                        "输出 JSON，字段固定为 primary_entity 和 compare_entities。"
                        "compare_entities 最多 3 个。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "primary_entity": primary_entity,
                            "candidate_compare_entities": compare_entities,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("llm_empty_choices")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            text = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        else:
            text = str(content or "")
        parsed = json.loads(text)
        refined = parsed.get("compare_entities", [])
        if not isinstance(refined, list):
            raise RuntimeError("llm_invalid_compare_entities")
        normalized = _heuristic_compare_cleanup(
            compare_entities=[str(item).strip() for item in refined if str(item).strip()],
            primary_entity=str(parsed.get("primary_entity", primary_entity)).strip() or primary_entity,
        )
        if len(normalized) < 2:
            raise RuntimeError("llm_refine_too_few_entities")
        return normalized[:3]


def _should_use_llm_refinement(*, query: str, compare_entities: list[str]) -> bool:
    text = str(query or "").strip()
    if len(compare_entities) >= 4:
        return True
    if len(compare_entities) >= 3 and len(text) >= 40 and any(marker in text for marker in ("比较", "鉴别", "异同", "区别")):
        return True
    return False


def _resolve_primary_entity(*, primary_entity: str, compare_entities: list[str]) -> str:
    if primary_entity and primary_entity in compare_entities:
        return primary_entity
    return compare_entities[0] if compare_entities else primary_entity


def _heuristic_compare_cleanup(*, compare_entities: list[str], primary_entity: str) -> list[str]:
    normalized_primary = _normalize_compare_entity(primary_entity)
    ordered: list[str] = []
    seen = set()
    for item in compare_entities:
        entity = _normalize_compare_entity(item)
        if not entity or entity in seen:
            continue
        seen.add(entity)
        if _is_noise_entity(entity):
            continue
        ordered.append(entity)
    if normalized_primary and normalized_primary in ordered:
        ordered = [normalized_primary, *[item for item in ordered if item != normalized_primary]]
    focused = [item for item in ordered if item.endswith(TARGET_SUFFIXES)]
    if len(focused) >= 2:
        ordered = focused
        if normalized_primary and normalized_primary in ordered:
            ordered = [normalized_primary, *[item for item in ordered if item != normalized_primary]]
    return list(dict.fromkeys(ordered))[:6]


def _is_noise_entity(entity: str) -> bool:
    normalized = str(entity or "").strip()
    if len(normalized) < 2:
        return True
    if normalized in COMPARE_NOISE_TERMS:
        return True
    return any(normalized.startswith(prefix) for prefix in COMPARE_NOISE_PREFIXES)


def _normalize_compare_entity(entity: Any) -> str:
    normalized = str(entity or "").strip(" ，。？?：:；;（）()[]【】\"'")
    if not normalized:
        return ""
    for prefix in COMPARE_NOISE_PREFIXES:
        if normalized.startswith(prefix) and len(normalized) > len(prefix) + 1:
            candidate = normalized[len(prefix) :].strip(" ，。？?：:；;（）()[]【】\"'")
            if candidate:
                normalized = candidate
                break
    for suffix in FORMULA_TRAILING_SUFFIXES:
        if normalized.endswith(suffix):
            return normalized[: -1]
    return normalized
