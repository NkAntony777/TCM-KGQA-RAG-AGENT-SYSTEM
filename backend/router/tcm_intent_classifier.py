from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
import sqlite3
import re
from typing import Literal

try:
    import ahocorasick  # type: ignore
except ImportError:  # pragma: no cover - exercised via substring fallback
    ahocorasick = None

try:
    import jieba  # type: ignore
except ImportError:  # pragma: no cover - optional enhancement only
    jieba = None


RouteName = Literal["graph", "retrieval", "hybrid"]
GraphQueryKind = Literal["entity", "syndrome", "path", "none"]

COMPOSITION_KEYWORDS = ("组成", "药材", "配伍", "方组", "组方", "由什么组成", "由哪些药材组成")
EFFICACY_KEYWORDS = ("功效", "作用", "有什么用", "有什么功效", "有何功效", "归经", "治法", "性味")
INDICATION_KEYWORDS = ("主治", "适应症", "证候", "治什么", "治疗什么", "治疗哪些", "适用于", "适合")
SOURCE_KEYWORDS = ("出处", "出自", "原文", "文献", "古籍", "记载", "来源", "原句", "哪本书", "哪部书", "原书", "医书", "佐证")
COMPARE_KEYWORDS = ("区别", "比较", "对比", "异同")
PATH_KEYWORDS = ("路径", "关系", "链路", "怎么到", "如何到")
DEFINITION_KEYWORDS = ("定义", "是什么", "什么意思", "何谓", "概念", "怎么解释", "解释")
SYNDROME_TO_FORMULA_KEYWORDS = ("推荐什么方剂", "推荐方剂", "对应什么方剂", "用什么方", "哪首方", "什么方剂")
MIXED_CONNECTORS = ("并", "以及", "同时", "结合", "并且", "并说明", "并给出", "并附", "和", "与")
QUESTION_PREFIXES = ("请问", "请解释", "请给我", "请告诉我", "想知道", "帮我看看", "麻烦问下")
FORMULA_SUFFIXES = ("丸", "散", "汤", "饮", "膏", "丹", "方", "颗粒", "胶囊")
FORMULA_PATTERN_SUFFIXES = ("丸", "散", "汤", "饮", "膏", "丹", "颗粒", "胶囊")
FORMULA_ENTITY_PATTERN = re.compile(
    rf"(?<![\u4e00-\u9fffA-Za-z0-9])([\u4e00-\u9fff]{{2,10}}?(?:{'|'.join(FORMULA_PATTERN_SUFFIXES)}))(?![\u4e00-\u9fff])"
)
ALNUM_ENTITY_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9\-]{1,14}\b")
CLASSIFIER_RUNTIME_GRAPH_DB_PATH = (
    Path(__file__).resolve().parents[1] / "services" / "graph_service" / "data" / "graph_runtime.db"
)
GENERIC_ENTITY_STOPWORDS = set(
    COMPOSITION_KEYWORDS
    + EFFICACY_KEYWORDS
    + INDICATION_KEYWORDS
    + SOURCE_KEYWORDS
    + COMPARE_KEYWORDS
    + PATH_KEYWORDS
    + DEFINITION_KEYWORDS
    + SYNDROME_TO_FORMULA_KEYWORDS
    + ("方剂", "治法", "归经", "性味", "功效", "作用", "主治", "出处", "原文", "古籍")
)

BOOK_HINTS = (
    "本草纲目",
    "医方集解",
    "和剂局方",
    "医宗金鉴",
    "金匮要略",
    "伤寒论",
    "黄帝内经",
    "小儿药证直诀",
)

DEFAULT_ENTITY_LEXICON: dict[str, tuple[str, ...]] = {
    "formula": (
        "六味地黄丸",
        "逍遥散",
        "丹栀逍遥散",
        "天麻钩藤饮",
        "四君子汤",
        "六君子汤",
        "升阳益胃汤",
        "紫菀汤",
    ),
    "herb": (
        "柴胡",
        "当归",
        "熟地黄",
        "山药",
        "山茱萸",
        "泽泻",
        "牡丹皮",
        "丹皮",
        "茯苓",
        "人参",
        "白术",
        "甘草",
        "杏仁",
        "麻黄",
    ),
    "syndrome": (
        "肝郁脾虚",
        "肝阳上亢",
        "肝郁化火",
        "真阴亏损",
        "肝肾不足",
    ),
    "symptom": (
        "胁肋胀痛",
        "头痛",
        "烦躁",
        "神疲食少",
    ),
    "therapy": (
        "疏肝解郁",
        "健脾养血",
        "滋阴补肾",
    ),
    "source_book": BOOK_HINTS,
}


@dataclass
class EntityMatch:
    name: str
    types: list[str]
    source: str
    start: int

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "types": self.types, "source": self.source, "start": self.start}


@dataclass
class QueryAnalysis:
    query: str
    normalized_query: str
    dominant_intent: str
    intent_candidates: list[str]
    matched_entities: list[EntityMatch] = field(default_factory=list)
    matched_keywords: dict[str, list[str]] = field(default_factory=dict)
    graph_score: int = 0
    retrieval_score: int = 0
    route_hint: RouteName = "hybrid"
    route_reason: str = ""
    graph_query_kind: GraphQueryKind = "none"
    primary_entity: str = ""
    symptom_name: str = ""
    path_start: str = ""
    path_end: str = ""
    notes: list[str] = field(default_factory=list)

    def entity_types(self) -> dict[str, list[str]]:
        return {item.name: list(item.types) for item in self.matched_entities}

    def compare_entities(self) -> list[str]:
        entities = [item.name for item in self.matched_entities if "source_book" not in item.types]
        deduped = list(dict.fromkeys(entity for entity in entities if entity))
        return deduped if len(deduped) >= 2 else []

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["matched_entities"] = [item.to_dict() for item in self.matched_entities]
        payload["entity_types"] = self.entity_types()
        payload["compare_entities"] = self.compare_entities()
        return payload


class _EntityMatcher:
    def __init__(self, lexicon: dict[str, tuple[str, ...]]) -> None:
        self.lexicon = lexicon
        self.word_types: dict[str, list[str]] = {}
        for entity_type, words in lexicon.items():
            for word in words:
                normalized = word.strip()
                if not normalized:
                    continue
                self.word_types.setdefault(normalized, [])
                if entity_type not in self.word_types[normalized]:
                    self.word_types[normalized].append(entity_type)

        self._automaton = None
        if ahocorasick is not None:
            tree = ahocorasick.Automaton()
            for index, word in enumerate(self.word_types):
                tree.add_word(word, (index, word))
            tree.make_automaton()
            self._automaton = tree

    def match(self, text: str) -> list[EntityMatch]:
        if not text:
            return []

        found: list[EntityMatch] = []
        if self._automaton is not None:
            for end_index, (_, word) in self._automaton.iter(text):
                found.append(
                    EntityMatch(
                        name=word,
                        types=list(self.word_types.get(word, [])),
                        source="lexicon_ac",
                        start=end_index - len(word) + 1,
                    )
                )
        else:
            for word, types in self.word_types.items():
                start = text.find(word)
                if start >= 0:
                    found.append(EntityMatch(name=word, types=list(types), source="lexicon_scan", start=start))
        return _dedupe_overlaps(found)


ENTITY_MATCHER = _EntityMatcher(DEFAULT_ENTITY_LEXICON)


def _runtime_graph_db_path() -> Path:
    return CLASSIFIER_RUNTIME_GRAPH_DB_PATH


def _normalize_runtime_entity_type(entity_type: str) -> str | None:
    normalized = str(entity_type or "").strip().lower()
    mapping = {
        "formula": "formula",
        "方剂": "formula",
        "herb": "herb",
        "中药": "herb",
        "药物": "herb",
        "symptom": "symptom",
        "症状": "symptom",
        "syndrome": "syndrome",
        "证候": "syndrome",
        "证型": "syndrome",
        "therapy": "therapy",
        "治法": "therapy",
        "source_book": "source_book",
        "古籍": "source_book",
        "医书": "source_book",
    }
    return mapping.get(normalized)


def _should_skip_runtime_entity_name(name: str) -> bool:
    normalized = str(name or "").strip()
    if len(normalized) < 2 or len(normalized) > 24:
        return True
    return normalized in GENERIC_ENTITY_STOPWORDS


@lru_cache(maxsize=1)
def _load_runtime_entity_lexicon() -> dict[str, tuple[str, ...]]:
    path = _runtime_graph_db_path()
    if not path.exists():
        return {}

    grouped: dict[str, list[str]] = {
        "formula": [],
        "herb": [],
        "syndrome": [],
        "symptom": [],
        "therapy": [],
        "source_book": [],
    }
    try:
        with sqlite3.connect(str(path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT name, entity_type
                FROM entities
                WHERE length(name) BETWEEN 2 AND 24
                """
            ).fetchall()
    except sqlite3.Error:
        return {}

    for row in rows:
        name = str(row["name"] or "").strip()
        entity_type = _normalize_runtime_entity_type(str(row["entity_type"] or ""))
        if not name or entity_type is None or _should_skip_runtime_entity_name(name):
            continue
        grouped[entity_type].append(name)

    return {
        key: tuple(dict.fromkeys(sorted(values, key=lambda item: (-len(item), item))))
        for key, values in grouped.items()
        if values
    }


@lru_cache(maxsize=1)
def _get_runtime_entity_matcher() -> _EntityMatcher | None:
    lexicon = _load_runtime_entity_lexicon()
    if not lexicon:
        return None
    return _EntityMatcher(lexicon)


@lru_cache(maxsize=1)
def _combined_word_types() -> dict[str, list[str]]:
    combined: dict[str, list[str]] = {
        word: list(types)
        for word, types in ENTITY_MATCHER.word_types.items()
    }
    runtime_matcher = _get_runtime_entity_matcher()
    if runtime_matcher is not None:
        for word, types in runtime_matcher.word_types.items():
            bucket = combined.setdefault(word, [])
            for entity_type in types:
                if entity_type not in bucket:
                    bucket.append(entity_type)
    return combined


@lru_cache(maxsize=1)
def _init_jieba_user_dict() -> bool:
    if jieba is None:
        return False
    for word in _combined_word_types():
        if len(word) >= 2:
            jieba.add_word(word, freq=200000)
    return True


def analyze_tcm_query(query: str) -> QueryAnalysis:
    text = _normalize_query(query)
    if not text:
        return QueryAnalysis(
            query=query,
            normalized_query=text,
            dominant_intent="open_ended_grounded_qa",
            intent_candidates=["open_ended_grounded_qa"],
            route_hint="retrieval",
            route_reason="empty_query_default_retrieval",
            notes=["empty query"],
        )

    path_targets = _extract_path_targets(text)
    lexicon_matches = ENTITY_MATCHER.match(text)
    runtime_matcher = _get_runtime_entity_matcher()
    runtime_matches = runtime_matcher.match(text) if runtime_matcher is not None else []
    jieba_matches = _extract_jieba_entities(text)
    heuristic_matches = _extract_heuristic_entities(text)
    formula_regex_matches = _extract_formula_regex_entities(text)
    matched_entities = _merge_entity_matches(
        lexicon_matches,
        runtime_matches,
        jieba_matches,
        heuristic_matches,
        formula_regex_matches,
    )

    if path_targets is not None:
        start, end = path_targets
        source_hits = _hit_keywords(text, SOURCE_KEYWORDS)
        route_hint: RouteName = "hybrid" if source_hits else "graph"
        route_reason = f"path_pattern_detected: start={start}, end={end}"
        if source_hits:
            route_reason += f"; source_hits={source_hits}"
        matched_keywords = {"graph_path": ["path_pattern"]}
        if source_hits:
            matched_keywords["formula_origin"] = source_hits
        return QueryAnalysis(
            query=query,
            normalized_query=text,
            dominant_intent="graph_path",
            intent_candidates=["graph_path"],
            matched_entities=_merge_entity_matches(
                matched_entities,
                [
                    _make_entity_match(start, text, "heuristic_path"),
                    _make_entity_match(end, text, "heuristic_path"),
                ],
            ),
            matched_keywords=matched_keywords,
            graph_score=8,
            retrieval_score=4 if source_hits else 0,
            route_hint=route_hint,
            route_reason=route_reason,
            graph_query_kind="path",
            primary_entity=start,
            path_start=start,
            path_end=end,
            notes=["explicit path query detected"] + (["path query also requests source support"] if source_hits else []),
        )

    keyword_hits: dict[str, list[str]] = {}
    score_board: dict[str, int] = {}
    graph_score = 0
    retrieval_score = 0
    notes: list[str] = []

    entity_types = _collect_entity_types(matched_entities)
    non_book_entities = [item for item in matched_entities if "source_book" not in item.types]
    primary_entity = _choose_primary_entity(non_book_entities)

    composition_hits = _hit_keywords(text, COMPOSITION_KEYWORDS)
    if composition_hits:
        keyword_hits["formula_composition"] = composition_hits
        score_board["formula_composition"] = 9 if _has_any_type(entity_types, "formula") else 7
        graph_score += 5
        notes.append("composition intent signal detected")

    efficacy_hits = _hit_keywords(text, EFFICACY_KEYWORDS)
    if efficacy_hits:
        keyword_hits["formula_efficacy"] = efficacy_hits
        score_board["formula_efficacy"] = 7 if _has_any_type(entity_types, "formula", "herb") else 5
        graph_score += 3
        if "归经" in efficacy_hits:
            graph_score += 1

    indication_hits = _hit_keywords(text, INDICATION_KEYWORDS)
    if indication_hits:
        keyword_hits["formula_indication"] = indication_hits
        score_board["formula_indication"] = 8
        graph_score += 4

    source_hits = _hit_keywords(text, SOURCE_KEYWORDS)
    if source_hits:
        keyword_hits["formula_origin"] = source_hits
        score_board["formula_origin"] = 9
        retrieval_score += 5
        notes.append("origin/source intent signal detected")

    compare_hits = _hit_keywords(text, COMPARE_KEYWORDS)
    if compare_hits or (len(non_book_entities) >= 2 and _contains_any(text, MIXED_CONNECTORS)):
        keyword_hits["compare_entities"] = compare_hits or ["entity_pair"]
        score_board["compare_entities"] = 8
        graph_score += 2
        retrieval_score += 2
        notes.append("comparison intent signal detected")

    syndrome_formula_hits = _hit_keywords(text, SYNDROME_TO_FORMULA_KEYWORDS)
    if syndrome_formula_hits and (_has_any_type(entity_types, "syndrome", "symptom") or _looks_like_symptom_question(text)):
        keyword_hits["syndrome_to_formula"] = syndrome_formula_hits
        score_board["syndrome_to_formula"] = 8
        graph_score += 5
        notes.append("syndrome-to-formula signal detected")

    definition_hits = _hit_keywords(text, DEFINITION_KEYWORDS)
    strong_graph_intent = bool(composition_hits or efficacy_hits or indication_hits or syndrome_formula_hits)
    if definition_hits and not source_hits and not strong_graph_intent:
        keyword_hits["definition_lookup"] = definition_hits
        score_board["open_ended_grounded_qa"] = max(score_board.get("open_ended_grounded_qa", 0), 4)
        retrieval_score += 4
        notes.append("definition/explanation intent signal detected")

    book_hits = [book for book in BOOK_HINTS if book in text]
    if book_hits:
        retrieval_score += len(book_hits) * 2
        keyword_hits.setdefault("formula_origin", [])
        keyword_hits["formula_origin"].extend(book_hits)

    if not score_board and primary_entity and _has_any_type(entity_types, "formula", "herb", "syndrome", "therapy"):
        graph_score += 3
        notes.append("structured entity anchor detected in open-ended query")

    if primary_entity:
        graph_score += 1

    if not score_board:
        score_board["open_ended_grounded_qa"] = 1
        if primary_entity:
            graph_score += 1
        else:
            retrieval_score += 1

    intent_candidates = [
        intent
        for intent, _ in sorted(
            score_board.items(),
            key=lambda item: (-item[1], _intent_priority(item[0])),
        )
    ]
    dominant_intent = intent_candidates[0]

    graph_query_kind, symptom_name = _derive_graph_query_kind(
        dominant_intent=dominant_intent,
        matched_entities=matched_entities,
        text=text,
        primary_entity=primary_entity,
    )

    route_hint, route_reason = _decide_route(
        text=text,
        graph_score=graph_score,
        retrieval_score=retrieval_score,
        keyword_hits=keyword_hits,
        dominant_intent=dominant_intent,
        primary_entity=primary_entity,
        matched_entities=matched_entities,
    )

    return QueryAnalysis(
        query=query,
        normalized_query=text,
        dominant_intent=dominant_intent,
        intent_candidates=intent_candidates,
        matched_entities=matched_entities,
        matched_keywords=keyword_hits,
        graph_score=graph_score,
        retrieval_score=retrieval_score,
        route_hint=route_hint,
        route_reason=route_reason,
        graph_query_kind=graph_query_kind,
        primary_entity=primary_entity,
        symptom_name=symptom_name,
        notes=notes,
    )


def _normalize_query(query: str) -> str:
    text = (query or "").strip()
    for prefix in QUESTION_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    return text.strip(" \t\r\n")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _hit_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _extract_path_targets(text: str) -> tuple[str, str] | None:
    normalized = text.strip()
    if not normalized or "到" not in normalized or not _contains_any(normalized, PATH_KEYWORDS):
        return None
    left, right = normalized.split("到", 1)
    start = left.replace("从", "").strip(" ，。？?：:的")
    end = right
    for marker in ("的辨证路径", "辨证路径", "的路径", "路径", "关系", "链路", "怎么到", "如何到", "是什么", "有哪些", "吗"):
        end = end.split(marker, 1)[0]
    end = end.strip(" ，。？?：:的")
    if not start or not end:
        return None
    return start, end


def _extract_heuristic_entities(text: str) -> list[EntityMatch]:
    candidates: list[EntityMatch] = []
    compare_match = re.match(r"^(.+?)(?:和|与|跟|及)(.+?)(?:有什么区别|有何区别|区别|比较|对比|异同).*$", text)
    if compare_match:
        for raw in compare_match.groups():
            entity = _clean_candidate(raw)
            if entity:
                candidates.append(_make_entity_match(entity, text, "heuristic_compare"))

    patterns = [
        r"^(.+?)(?:的)(?:组成|药材|配伍|方组|组方|功效|作用|主治|适应症|证候|出处|原文|古籍|来源|定义|归经).*$",
        r"^(.+?)(?:是什么|有哪些|有什么用|有什么功效|出自哪本古籍|出自哪里|怎么解释).*$",
        r"^(.+?)(?:可能)?(?:对应什么证候|推荐什么方剂|对应什么方剂).*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            entity = _clean_candidate(match.group(1))
            if entity:
                candidates.append(_make_entity_match(entity, text, "heuristic_primary"))

    return _dedupe_overlaps(candidates)


def _extract_jieba_entities(text: str) -> list[EntityMatch]:
    if jieba is None or not text:
        return []
    _init_jieba_user_dict()
    combined_types = _combined_word_types()
    candidates: list[EntityMatch] = []
    for token, start, _ in jieba.tokenize(text):
        normalized = str(token).strip()
        if len(normalized) < 2:
            continue
        types = combined_types.get(normalized)
        if not types:
            continue
        candidates.append(
            EntityMatch(
                name=normalized,
                types=list(types),
                source="jieba_runtime",
                start=max(start, 0),
            )
        )
    return _dedupe_overlaps(candidates)


def _extract_formula_regex_entities(text: str) -> list[EntityMatch]:
    candidates: list[EntityMatch] = []
    for match in FORMULA_ENTITY_PATTERN.finditer(text):
        entity = str(match.group(1) or "").strip()
        if not entity:
            continue
        candidates.append(
            EntityMatch(
                name=entity,
                types=["formula"],
                source="regex_formula",
                start=match.start(1),
            )
        )
    for match in ALNUM_ENTITY_PATTERN.finditer(text):
        token = str(match.group(0) or "").strip()
        if len(token) < 2:
            continue
        if token.lower() not in {"aqp", "hif", "mmp"} and "-" not in token:
            continue
        candidates.append(
            EntityMatch(
                name=token,
                types=["unknown"],
                source="regex_alnum",
                start=match.start(0),
            )
        )
    return _dedupe_overlaps(candidates)


def _make_entity_match(entity: str, text: str, source: str) -> EntityMatch:
    guessed_types = _guess_entity_types(entity)
    return EntityMatch(
        name=entity,
        types=guessed_types or ["unknown"],
        source=source,
        start=max(text.find(entity), 0),
    )


def _clean_candidate(raw: str) -> str:
    value = raw.strip(" ，。？?：:的")
    for prefix in QUESTION_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix) :].strip(" ，。？?：:")
    if "的" in value:
        head, tail = value.split("的", 1)
        if any(
            token in tail
            for token in {
                "组成",
                "药材",
                "配伍",
                "功效",
                "作用",
                "主治",
                "适应症",
                "证候",
                "出处",
                "原文",
                "古籍",
                "来源",
                "定义",
                "归经",
                "治法",
                "性味",
                "推荐什么方剂",
                "什么方剂",
            }
        ):
            value = head.strip(" ，。？?：:")
    for suffix in ("一般", "常见", "通常", "可参考", "可能"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].strip(" ，。？?：:")
    return value


def _guess_entity_types(entity: str) -> list[str]:
    guessed: list[str] = []
    if entity in BOOK_HINTS or entity.endswith(("论", "经", "鉴", "目")):
        guessed.append("source_book")
    if entity.endswith(FORMULA_SUFFIXES):
        guessed.append("formula")
    if entity.endswith(("证", "虚", "郁", "亏损", "不足", "上亢", "化火")):
        guessed.append("syndrome")
    if entity.endswith(("痛", "胀", "烦躁", "失眠", "头晕")) or entity in DEFAULT_ENTITY_LEXICON["symptom"]:
        guessed.append("symptom")
    return guessed


def _merge_entity_matches(*groups: list[EntityMatch]) -> list[EntityMatch]:
    combined: list[EntityMatch] = []
    seen: dict[str, EntityMatch] = {}
    for group in groups:
        for item in group:
            if not item.name:
                continue
            existing = seen.get(item.name)
            if existing is None:
                seen[item.name] = EntityMatch(
                    name=item.name,
                    types=list(dict.fromkeys(item.types)),
                    source=item.source,
                    start=item.start,
                )
                continue
            existing.types = list(dict.fromkeys(existing.types + item.types))
            if existing.source.startswith("heuristic") and not item.source.startswith("heuristic"):
                existing.source = item.source
            existing.start = min(existing.start, item.start)
    combined.extend(seen.values())
    combined.sort(key=lambda item: (item.start, -len(item.name)))
    return _dedupe_overlaps(combined)


def _dedupe_overlaps(items: list[EntityMatch]) -> list[EntityMatch]:
    if not items:
        return []
    sorted_items = sorted(items, key=lambda item: (item.start, -_entity_priority(item), -len(item.name)))
    kept: list[EntityMatch] = []
    for item in sorted_items:
        handled = False
        for index, other in enumerate(kept):
            if item.name == other.name:
                other.types = list(dict.fromkeys(other.types + item.types))
                handled = True
                break
            if _spans_overlap(item, other):
                if _entity_priority(item) > _entity_priority(other):
                    item.types = list(dict.fromkeys(item.types + other.types))
                    kept[index] = item
                else:
                    other.types = list(dict.fromkeys(other.types + item.types))
                handled = True
                break
        if not handled:
            kept.append(item)
    return kept


def _spans_overlap(left: EntityMatch, right: EntityMatch) -> bool:
    left_end = left.start + len(left.name)
    right_end = right.start + len(right.name)
    return max(left.start, right.start) < min(left_end, right_end)


def _entity_priority(item: EntityMatch) -> int:
    score = 0
    if not item.source.startswith("heuristic"):
        score += 10
    for entity_type in item.types:
        if entity_type == "unknown":
            continue
        score += 4
    if "unknown" not in item.types:
        score += 2
    return score


def _collect_entity_types(matches: list[EntityMatch]) -> set[str]:
    collected: set[str] = set()
    for item in matches:
        collected.update(item.types)
    return collected


def _has_any_type(entity_types: set[str], *targets: str) -> bool:
    return any(target in entity_types for target in targets)


def _choose_primary_entity(matches: list[EntityMatch]) -> str:
    if not matches:
        return ""
    ordered_types = ("formula", "herb", "syndrome", "symptom", "therapy", "unknown")
    for entity_type in ordered_types:
        for item in matches:
            if entity_type in item.types:
                return item.name
    return matches[0].name


def _looks_like_symptom_question(text: str) -> bool:
    return "症状" in text or ("怎么办" in text and len(text) <= 24)


def _derive_graph_query_kind(
    *,
    dominant_intent: str,
    matched_entities: list[EntityMatch],
    text: str,
    primary_entity: str,
) -> tuple[GraphQueryKind, str]:
    if dominant_intent == "graph_path":
        return "path", ""

    if dominant_intent == "syndrome_to_formula":
        for item in matched_entities:
            if "symptom" in item.types:
                return "syndrome", item.name
        if _looks_like_symptom_question(text):
            return "syndrome", primary_entity or text

    if primary_entity:
        for item in matched_entities:
            if item.name == primary_entity and any(entity_type in item.types for entity_type in ("formula", "herb", "syndrome", "therapy")):
                return "entity", ""

    for item in matched_entities:
        if "symptom" in item.types:
            return "syndrome", item.name

    if primary_entity:
        return "entity", ""

    if _looks_like_symptom_question(text):
        return "syndrome", text
    return "none", ""


def _decide_route(
    *,
    text: str,
    graph_score: int,
    retrieval_score: int,
    keyword_hits: dict[str, list[str]],
    dominant_intent: str,
    primary_entity: str,
    matched_entities: list[EntityMatch],
) -> tuple[RouteName, str]:
    graph_hits = sorted({hit for label, hits in keyword_hits.items() if label != "formula_origin" for hit in hits})
    retrieval_hits = sorted({hit for label, hits in keyword_hits.items() if label == "formula_origin" or label == "definition_lookup" for hit in hits})
    has_non_book_entity = bool(primary_entity) or any("source_book" not in item.types for item in matched_entities)
    source_requested = "formula_origin" in keyword_hits
    graph_first_intents = {"formula_composition", "formula_efficacy", "formula_indication", "syndrome_to_formula", "graph_path"}
    hybrid_bias_markers = (
        "结合",
        "分析",
        "论证",
        "机制",
        "原理",
        "阈值",
        "通路",
        "现代",
        "分布",
        "差异",
        "对接",
        "跨学科",
    )
    explanatory_complex = len(text) >= 30 or _contains_any(text, hybrid_bias_markers)

    if "compare_entities" in keyword_hits:
        return (
            "hybrid",
            "compare_entities_forced_hybrid: "
            f"graph_score={graph_score}, retrieval_score={retrieval_score}, hits={keyword_hits['compare_entities']}",
        )

    if source_requested and has_non_book_entity:
        return (
            "hybrid",
            "entity_source_request_prefers_hybrid: "
            f"intent={dominant_intent}, primary_entity={primary_entity or 'missing'}, retrieval_hits={retrieval_hits}",
        )

    if graph_score >= 3 and retrieval_score >= 3:
        return (
            "hybrid",
            "hybrid_classifier_match: "
            f"graph_score={graph_score}, retrieval_score={retrieval_score}, "
            f"graph_hits={graph_hits}, retrieval_hits={retrieval_hits}",
        )

    if graph_score >= 3:
        if dominant_intent in graph_first_intents and not explanatory_complex:
            return (
                "graph",
                f"classifier_graph_match: score={graph_score}, intent={dominant_intent}, hits={graph_hits}",
            )
        return (
            "hybrid",
            "graph_anchor_prefers_hybrid: "
            f"score={graph_score}, intent={dominant_intent}, primary_entity={primary_entity or 'missing'}, graph_hits={graph_hits}",
        )

    if retrieval_score >= 3:
        if has_non_book_entity:
            return (
                "hybrid",
                "retrieval_signal_with_entity_prefers_hybrid: "
                f"score={retrieval_score}, intent={dominant_intent}, primary_entity={primary_entity or 'missing'}, retrieval_hits={retrieval_hits}",
            )
        return (
            "retrieval",
            f"classifier_retrieval_match: score={retrieval_score}, hits={retrieval_hits}",
        )

    if _contains_any(text, MIXED_CONNECTORS):
        return ("hybrid", "connector_only_hybrid_fallback")

    if has_non_book_entity:
        return (
            "hybrid",
            f"entity_present_default_hybrid: intent={dominant_intent}, primary_entity={primary_entity or 'missing'}",
        )

    return (
        "hybrid",
        f"default_hybrid_low_signal: graph_score={graph_score}, retrieval_score={retrieval_score}",
    )


def _intent_priority(intent: str) -> int:
    order = (
        "graph_path",
        "formula_composition",
        "formula_origin",
        "formula_indication",
        "formula_efficacy",
        "syndrome_to_formula",
        "compare_entities",
        "open_ended_grounded_qa",
    )
    try:
        return order.index(intent)
    except ValueError:
        return len(order)
