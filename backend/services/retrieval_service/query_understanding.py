from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


GENERIC_WEAK_ANCHORS = ("一方", "治方", "通治方", "诸虚通治方", "调经通治方", "正骨通治方", "牙齿通治方", "痨瘵通治方")


@dataclass(frozen=True)
class QueryUnderstandingResult:
    primary_entity: str
    focus_entities: list[str]
    question_type: str
    answer_facets: list[str]
    source_book_hints: list[str]
    expanded_query: str
    weak_anchor: bool
    need_broad_recall: bool
    confidence: float
    backend: str
    notes: list[str]

    def to_context(self) -> dict[str, Any]:
        return {
            "primary_entity": self.primary_entity,
            "focus_entities": list(self.focus_entities),
            "question_type": self.question_type,
            "answer_facets": list(self.answer_facets),
            "source_book_hints": list(self.source_book_hints),
            "expanded_query": self.expanded_query,
            "weak_anchor": self.weak_anchor,
            "need_broad_recall": self.need_broad_recall,
            "confidence": self.confidence,
            "backend": self.backend,
            "notes": list(self.notes),
        }


class LLMQueryUnderstanding:
    def __init__(self, *, client, model: str) -> None:
        self.client = client
        self.model = model

    def is_ready(self) -> bool:
        return bool(self.client and self.client.is_ready())

    def should_run(self, query: str) -> bool:
        text = str(query or "").strip()
        if not text:
            return False
        if any(anchor in text for anchor in GENERIC_WEAK_ANCHORS):
            return True
        if any(marker in text for marker in ("出处", "哪本书", "哪部书", "哪一篇", "记载出自")):
            return True
        if "通治方" in text or text.startswith("古籍中关于"):
            return True
        return False

    def understand(self, query: str) -> QueryUnderstandingResult | None:
        if not self.is_ready():
            return None
        prompt = self._build_prompt(query)
        try:
            raw = str(self.client.chat(prompt, self.model) or "").strip()
            parsed = _parse_json_object(raw)
            if not isinstance(parsed, dict):
                return None
            return QueryUnderstandingResult(
                primary_entity=str(parsed.get("primary_entity", "")).strip(),
                focus_entities=_clean_list(parsed.get("focus_entities")),
                question_type=str(parsed.get("question_type", "")).strip(),
                answer_facets=_clean_list(parsed.get("answer_facets")),
                source_book_hints=_clean_list(parsed.get("source_book_hints")),
                expanded_query=str(parsed.get("expanded_query", "")).strip(),
                weak_anchor=bool(parsed.get("weak_anchor", False)),
                need_broad_recall=bool(parsed.get("need_broad_recall", False)),
                confidence=float(parsed.get("confidence", 0.0) or 0.0),
                backend="llm",
                notes=["llm_query_understanding"],
            )
        except Exception:
            return None

    @staticmethod
    def _build_prompt(query: str) -> str:
        return (
            "你是中医古籍检索系统的问题理解器。"
            "你的任务是理解用户问题中的核心实体、问题类型和检索落点。"
            "不要回答问题，只输出 JSON。"
            "\n\n"
            "输出字段固定为："
            "\n"
            "{"
            '"primary_entity": "",'
            '"focus_entities": [],'
            '"question_type": "",'
            '"answer_facets": [],'
            '"source_book_hints": [],'
            '"expanded_query": "",'
            '"weak_anchor": false,'
            '"need_broad_recall": false,'
            '"confidence": 0.0'
            "}"
            "\n\n"
            "规则："
            "\n"
            "1. primary_entity 必须是题目真正的核心对象，如黄芪、十全大补汤、鸡内金。"
            "\n"
            "2. 如果题目里的实体只是泛称，如“一方”“治方”“通治方”，则 weak_anchor=true，need_broad_recall=true。"
            "\n"
            "3. question_type 只能取 source_locate、composition、property、comparison、definition、other 之一。"
            "\n"
            "4. answer_facets 只保留任务维度词，如 组成、功效、归经、别名、主治、治法。"
            "\n"
            "5. source_book_hints 只在题目明确指定书目时填写。"
            "\n"
            "6. expanded_query 是给检索用的短查询，保留实体和必要维度词，不超过 24 字。"
            "\n"
            "7. focus_entities 最多 4 个，按重要性排序。"
            "\n\n"
            f"问题：{query}"
        )


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    results: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = str(item or "").strip()
        if len(normalized) < 1 or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results[:8]


def _parse_json_object(text: str) -> dict[str, Any] | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", candidate, flags=re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
