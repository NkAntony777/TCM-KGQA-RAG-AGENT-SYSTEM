from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from services.qa_service.alias_service import get_runtime_alias_service

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover - optional lexical enhancement only
    jieba = None


CHINESE_SPAN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,24}")
ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.%-]{2,32}")
FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|剂|方|颗粒|胶囊)")
HERB_SUFFIX_HINTS = ("草", "花", "叶", "根", "子", "仁", "皮", "藤", "术", "芩", "芎", "苓", "黄", "参")
ROLE_HINTS = ("作用", "功效", "意义", "为何", "为什么", "配伍", "方中", "君药", "臣药", "佐药", "使药")
ORIGIN_HINTS = ("出处", "出自", "原文", "哪本书", "古籍")
COMPOSITION_HINTS = ("组成", "配方", "药物组成", "成分", "哪些药")
INDICATION_HINTS = ("主治", "适应", "治什么", "证候", "症状")
CASE_HINTS = ("年龄", "性别", "舌", "脉", "主诉", "现病史", "病例", "医案", "患者")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield payload


def _json_text(value: object) -> str:
    if isinstance(value, list):
        return "；".join(_clean(item) for item in value if _clean(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _clean(value)


@dataclass(frozen=True)
class StructuredQAIndexSettings:
    index_path: Path
    qa_input_path: Path
    case_input_path: Path


@dataclass(frozen=True)
class QueryProfile:
    intent: str
    formula_terms: tuple[str, ...]
    herb_terms: tuple[str, ...]
    symptom_terms: tuple[str, ...]
    role_query: bool = False
    origin_query: bool = False
    composition_query: bool = False
    indication_query: bool = False
    case_query: bool = False


class StructuredQAIndex:
    def __init__(self, settings: StructuredQAIndexSettings):
        self.settings = settings
        self.settings.index_path.parent.mkdir(parents=True, exist_ok=True)

    def rebuild(self, *, batch_size: int = 5000) -> dict[str, Any]:
        if self.settings.index_path.exists():
            self.settings.index_path.unlink()

        with sqlite3.connect(self.settings.index_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=FILE")
            conn.execute("PRAGMA cache_size=-65536")
            conn.execute("PRAGMA mmap_size=268435456")
            self._create_schema(conn)
            qa_count = self._load_qa(conn, self.settings.qa_input_path, batch_size=batch_size)
            case_count = self._load_case(conn, self.settings.case_input_path, batch_size=batch_size)
            conn.execute("PRAGMA optimize")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.commit()

        return {
            "index_path": str(self.settings.index_path),
            "qa_records": qa_count,
            "case_records": case_count,
            "status": "ok",
        }

    def health(self) -> dict[str, Any]:
        if not self.settings.index_path.exists():
            return {
                "index_path": str(self.settings.index_path),
                "available": False,
                "qa_records": 0,
                "case_records": 0,
            }
        with sqlite3.connect(self.settings.index_path) as conn:
            qa_records = int(conn.execute("SELECT COUNT(1) FROM qa_records").fetchone()[0])
            case_records = int(conn.execute("SELECT COUNT(1) FROM case_records").fetchone()[0])
        return {
            "index_path": str(self.settings.index_path),
            "available": qa_records > 0 or case_records > 0,
            "qa_records": qa_records,
            "case_records": case_records,
        }

    def search_qa(self, query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        if not self.settings.index_path.exists():
            return []
        profile = self._build_query_profile(query)
        terms = self._prepare_search_query(query, profile=profile)
        if not terms:
            return []
        with sqlite3.connect(self.settings.index_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    r.record_id,
                    r.collection,
                    r.embedding_id,
                    r.bucket,
                    r.question_type,
                    r.question,
                    r.answer,
                    r.formula_text,
                    r.keyword_text,
                    snippet(qa_fts, 1, '[', ']', '...', 16) AS question_snippet,
                    snippet(qa_fts, 2, '[', ']', '...', 16) AS answer_snippet,
                    bm25(qa_fts, 4.0, 1.5, 2.0, 1.2, 0.8, 0.6) AS rank_score
                FROM qa_fts
                JOIN qa_records r ON r.record_id = qa_fts.record_id
                WHERE qa_fts MATCH ?
                ORDER BY rank_score
                LIMIT ?
                """,
                (terms, max(8, int(top_k) * 8)),
            ).fetchall()
        return self._rerank_qa_rows(query, [dict(row) for row in rows], profile=profile, top_k=top_k)

    def search_case(self, query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        if not self.settings.index_path.exists():
            return []
        profile = self._build_query_profile(query)
        terms = self._prepare_search_query(query, profile=profile, include_numeric=True, max_terms=30)
        if not terms:
            return []
        with sqlite3.connect(self.settings.index_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    r.record_id,
                    r.collection,
                    r.embedding_id,
                    r.question,
                    r.answer,
                    r.age,
                    r.sex,
                    r.chief_complaint,
                    r.history,
                    r.tongue,
                    r.pulse,
                    r.symptom_text,
                    r.syndrome_text,
                    r.formula_text,
                    snippet(case_fts, 1, '[', ']', '...', 16) AS question_snippet,
                    snippet(case_fts, 2, '[', ']', '...', 16) AS answer_snippet,
                    bm25(case_fts, 3.2, 1.4, 2.4, 2.2, 1.5, 1.5, 1.1, 1.1, 0.8, 0.8) AS rank_score
                FROM case_fts
                JOIN case_records r ON r.record_id = case_fts.record_id
                WHERE case_fts MATCH ?
                ORDER BY rank_score
                LIMIT ?
                """,
                (terms, max(10, int(top_k) * 8)),
            ).fetchall()
        return self._rerank_case_rows(query, [dict(row) for row in rows], profile=profile, top_k=top_k)

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE qa_records (
                record_id TEXT PRIMARY KEY,
                collection TEXT NOT NULL,
                embedding_id TEXT NOT NULL,
                bucket TEXT NOT NULL,
                question_type TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                formula_text TEXT NOT NULL DEFAULT '',
                keyword_text TEXT NOT NULL DEFAULT '',
                source_terms_text TEXT NOT NULL DEFAULT '',
                search_text TEXT NOT NULL DEFAULT ''
            );
            CREATE VIRTUAL TABLE qa_fts USING fts5(
                record_id UNINDEXED,
                question,
                answer,
                formula_text,
                keyword_text,
                source_terms_text,
                search_text,
                tokenize='trigram'
            );

            CREATE TABLE case_records (
                record_id TEXT PRIMARY KEY,
                collection TEXT NOT NULL,
                embedding_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                age TEXT NOT NULL DEFAULT '',
                sex TEXT NOT NULL DEFAULT '',
                chief_complaint TEXT NOT NULL DEFAULT '',
                history TEXT NOT NULL DEFAULT '',
                tongue TEXT NOT NULL DEFAULT '',
                pulse TEXT NOT NULL DEFAULT '',
                formula_text TEXT NOT NULL DEFAULT '',
                symptom_text TEXT NOT NULL DEFAULT '',
                syndrome_text TEXT NOT NULL DEFAULT '',
                search_text TEXT NOT NULL DEFAULT ''
            );
            CREATE VIRTUAL TABLE case_fts USING fts5(
                record_id UNINDEXED,
                question,
                answer,
                chief_complaint,
                history,
                tongue,
                pulse,
                formula_text,
                symptom_text,
                syndrome_text,
                search_text,
                tokenize='trigram'
            );
            """
        )

    def _load_qa(self, conn: sqlite3.Connection, input_path: Path, *, batch_size: int) -> int:
        row_buffer: list[tuple[Any, ...]] = []
        fts_buffer: list[tuple[Any, ...]] = []
        count = 0
        for payload in _iter_jsonl(input_path):
            row_buffer.append(
                (
                    _clean(payload.get("record_id")),
                    _clean(payload.get("collection")),
                    _clean(payload.get("embedding_id")),
                    _clean(payload.get("bucket")),
                    _clean(payload.get("question_type")),
                    _clean(payload.get("question")),
                    _clean(payload.get("answer")),
                    _json_text(payload.get("formula_candidates")),
                    _json_text(payload.get("keywords")),
                    "；".join(
                        item
                        for item in [
                            _json_text(payload.get("formula_candidates")),
                            _json_text(payload.get("keywords")),
                            _json_text(payload.get("symptom_terms")),
                            _json_text(payload.get("syndrome_terms")),
                        ]
                        if item
                    ),
                    _clean(payload.get("search_text")),
                )
            )
            fts_buffer.append(
                (
                    _clean(payload.get("record_id")),
                    _clean(payload.get("question")),
                    _clean(payload.get("answer")),
                    _json_text(payload.get("formula_candidates")),
                    _json_text(payload.get("keywords")),
                    "；".join(
                        item
                        for item in [
                            _json_text(payload.get("formula_candidates")),
                            _json_text(payload.get("keywords")),
                            _json_text(payload.get("symptom_terms")),
                            _json_text(payload.get("syndrome_terms")),
                        ]
                        if item
                    ),
                    _clean(payload.get("search_text")),
                )
            )
            count += 1
            if len(row_buffer) >= batch_size:
                self._flush_qa(conn, row_buffer, fts_buffer)
                row_buffer.clear()
                fts_buffer.clear()
        if row_buffer:
            self._flush_qa(conn, row_buffer, fts_buffer)
        return count

    def _load_case(self, conn: sqlite3.Connection, input_path: Path, *, batch_size: int) -> int:
        row_buffer: list[tuple[Any, ...]] = []
        fts_buffer: list[tuple[Any, ...]] = []
        count = 0
        for payload in _iter_jsonl(input_path):
            slots = payload.get("slots", {})
            if not isinstance(slots, dict):
                slots = {}
            row_buffer.append(
                (
                    _clean(payload.get("record_id")),
                    _clean(payload.get("collection")),
                    _clean(payload.get("embedding_id")),
                    _clean(payload.get("question")),
                    _clean(payload.get("answer")),
                    _clean(slots.get("age")),
                    _clean(slots.get("sex")),
                    _clean(slots.get("chief_complaint")),
                    _clean(slots.get("history")),
                    _clean(slots.get("tongue")),
                    _clean(slots.get("pulse")),
                    _json_text(payload.get("formula_candidates")),
                    _json_text(payload.get("symptom_terms")),
                    _json_text(payload.get("syndrome_terms")),
                    _clean(payload.get("search_text")),
                )
            )
            fts_buffer.append(
                (
                    _clean(payload.get("record_id")),
                    _clean(payload.get("question")),
                    _clean(payload.get("answer")),
                    _clean(slots.get("chief_complaint")),
                    _clean(slots.get("history")),
                    _clean(slots.get("tongue")),
                    _clean(slots.get("pulse")),
                    _json_text(payload.get("formula_candidates")),
                    _json_text(payload.get("symptom_terms")),
                    _json_text(payload.get("syndrome_terms")),
                    _clean(payload.get("search_text")),
                )
            )
            count += 1
            if len(row_buffer) >= batch_size:
                self._flush_case(conn, row_buffer, fts_buffer)
                row_buffer.clear()
                fts_buffer.clear()
        if row_buffer:
            self._flush_case(conn, row_buffer, fts_buffer)
        return count

    @staticmethod
    def _flush_qa(conn: sqlite3.Connection, rows: list[tuple[Any, ...]], fts_rows: list[tuple[Any, ...]]) -> None:
        conn.executemany(
            """
            INSERT INTO qa_records (
                record_id, collection, embedding_id, bucket, question_type, question, answer,
                formula_text, keyword_text, source_terms_text, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.executemany(
            """
            INSERT INTO qa_fts (
                record_id, question, answer, formula_text, keyword_text, source_terms_text, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            fts_rows,
        )
        conn.commit()

    @staticmethod
    def _flush_case(conn: sqlite3.Connection, rows: list[tuple[Any, ...]], fts_rows: list[tuple[Any, ...]]) -> None:
        conn.executemany(
            """
            INSERT INTO case_records (
                record_id, collection, embedding_id, question, answer, age, sex, chief_complaint, history,
                tongue, pulse, formula_text, symptom_text, syndrome_text, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.executemany(
            """
            INSERT INTO case_fts (
                record_id, question, answer, chief_complaint, history, tongue, pulse,
                formula_text, symptom_text, syndrome_text, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fts_rows,
        )
        conn.commit()

    @staticmethod
    def _fts_query(tokens: list[str]) -> str:
        quoted = []
        for token in tokens:
            safe = token.replace('"', " ")
            if safe:
                quoted.append(f'"{safe}"')
        return " OR ".join(quoted)

    def _prepare_search_query(
        self,
        query: str,
        *,
        profile: QueryProfile | None = None,
        include_numeric: bool = False,
        max_terms: int = 24,
    ) -> str:
        normalized = _clean(query)
        if not normalized:
            return ""
        profile = profile or self._build_query_profile(normalized)

        alias_service = get_runtime_alias_service()
        focus_entities: list[str] = []
        alias_terms: list[str] = []
        expanded_query = normalized
        if alias_service.is_available():
            focus_entities = alias_service.detect_entities(normalized, limit=3)
            expanded_query = alias_service.expand_query_with_aliases(
                normalized,
                focus_entities=focus_entities,
                max_aliases_per_entity=4,
                max_entities=2,
            )
            for entity_name in focus_entities[:2]:
                for alias_name in alias_service.aliases_for_entity(entity_name, max_aliases=4):
                    if alias_name not in alias_terms:
                        alias_terms.append(alias_name)

        candidates: list[str] = []
        seen: set[str] = set()

        def push(term: str, *, min_len: int = 2) -> None:
            cleaned = _clean(term)
            if len(cleaned) < min_len:
                return
            if not include_numeric and cleaned.isdigit():
                return
            if cleaned in seen:
                return
            seen.add(cleaned)
            candidates.append(cleaned)

        for item in focus_entities:
            push(item, min_len=3)
        for item in alias_terms:
            push(item, min_len=3)
        for item in profile.formula_terms:
            push(item, min_len=2)
        for item in profile.herb_terms:
            push(item, min_len=2)
        for item in profile.symptom_terms:
            push(item, min_len=2)
        if profile.role_query:
            for item in ("方中作用", "配伍意义", "功效", "作用"):
                push(item, min_len=2)
        if profile.origin_query:
            for item in ("出处", "原文", "古籍"):
                push(item, min_len=2)
        if profile.composition_query:
            for item in ("组成", "成分", "配方"):
                push(item, min_len=2)
        if profile.indication_query:
            for item in ("主治", "证候", "症状"):
                push(item, min_len=2)

        for part in normalized.replace("\n", " ").split():
            push(part, min_len=3)
        for part in expanded_query.replace("\n", " ").split():
            push(part, min_len=3)

        segmented_terms = self._segment_text(expanded_query, include_numeric=include_numeric)
        for token in segmented_terms:
            push(token, min_len=3)

        combined_terms = self._combine_adjacent_terms(segmented_terms, include_numeric=include_numeric)
        for token in combined_terms:
            push(token, min_len=3)

        for pair in zip(profile.formula_terms, profile.herb_terms):
            push("".join(pair), min_len=3)
        for text in [*focus_entities, *alias_terms, *profile.formula_terms, *profile.herb_terms, *segmented_terms, *combined_terms]:
            for token in self._trigram_chunks(text):
                push(token, min_len=3)

        return self._fts_query(candidates[: max(1, max_terms)])

    def _segment_text(self, text: str, *, include_numeric: bool = False) -> list[str]:
        normalized = _clean(text)
        if not normalized:
            return []
        tokens: list[str] = []
        seen: set[str] = set()

        if jieba is not None:
            alias_service = get_runtime_alias_service()
            if alias_service.is_available():
                for entity_name in alias_service.detect_entities(normalized, limit=4):
                    if len(entity_name) >= 2:
                        jieba.add_word(entity_name, freq=200000)
                    for alias_name in alias_service.aliases_for_entity(entity_name, max_aliases=4):
                        if len(alias_name) >= 2:
                            jieba.add_word(alias_name, freq=200000)
            for token in jieba.cut_for_search(normalized):
                cleaned = _clean(token)
                if len(cleaned) < 2:
                    continue
                if not include_numeric and cleaned.isdigit():
                    continue
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                tokens.append(cleaned)

        for match in CHINESE_SPAN_PATTERN.findall(normalized):
            if len(match) > 8:
                continue
            if match not in seen:
                seen.add(match)
                tokens.append(match)
        for match in ASCII_TOKEN_PATTERN.findall(normalized):
            if not include_numeric and match.isdigit():
                continue
            if match not in seen:
                seen.add(match)
                tokens.append(match)
        if include_numeric:
            for number_like in re.findall(r"\d{1,3}岁|\d{1,3}", normalized):
                if number_like not in seen:
                    seen.add(number_like)
                    tokens.append(number_like)
        return tokens

    @staticmethod
    def _trigram_chunks(text: str) -> list[str]:
        normalized = _clean(text).replace(" ", "")
        results: list[str] = []
        seen: set[str] = set()
        for span in CHINESE_SPAN_PATTERN.findall(normalized):
            if len(span) < 3:
                continue
            for idx in range(0, len(span) - 2):
                token = span[idx : idx + 3]
                if token not in seen:
                    seen.add(token)
                    results.append(token)
        return results

    @staticmethod
    def _combine_adjacent_terms(tokens: list[str], *, include_numeric: bool = False) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        cleaned_tokens = [_clean(token) for token in tokens if _clean(token)]
        for idx in range(len(cleaned_tokens) - 1):
            left = cleaned_tokens[idx]
            right = cleaned_tokens[idx + 1]
            if not include_numeric and (left.isdigit() or right.isdigit()):
                continue
            merged = f"{left}{right}"
            if len(merged) < 3 or len(merged) > 12:
                continue
            if merged not in seen:
                seen.add(merged)
                results.append(merged)
        return results

    def _build_query_profile(self, query: str) -> QueryProfile:
        normalized = _clean(query)
        lowered = normalized.lower()
        formula_terms = tuple(dict.fromkeys(FORMULA_PATTERN.findall(normalized)))

        segmented = self._segment_text(normalized, include_numeric=True)
        herb_terms: list[str] = []
        symptom_terms: list[str] = []
        for token in segmented:
            cleaned = _clean(token)
            if not cleaned:
                continue
            if cleaned in formula_terms:
                continue
            if 2 <= len(cleaned) <= 8 and cleaned.endswith(HERB_SUFFIX_HINTS):
                herb_terms.append(cleaned)
            if any(marker in cleaned for marker in ("痛", "热", "寒", "汗", "渴", "咳", "喘", "胁", "舌", "脉", "胃", "口苦")):
                symptom_terms.append(cleaned)

        role_query = any(hint in normalized for hint in ROLE_HINTS)
        origin_query = any(hint in normalized for hint in ORIGIN_HINTS)
        composition_query = any(hint in normalized for hint in COMPOSITION_HINTS)
        indication_query = any(hint in normalized for hint in INDICATION_HINTS)
        case_query = any(hint in normalized for hint in CASE_HINTS) or bool(re.search(r"\d{1,3}岁", normalized))

        intent = "generic"
        if case_query:
            intent = "case"
        elif origin_query:
            intent = "origin"
        elif role_query and formula_terms:
            intent = "formula_role"
        elif composition_query and formula_terms:
            intent = "formula_composition"
        elif indication_query and formula_terms:
            intent = "formula_indication"
        elif formula_terms:
            intent = "formula_generic"

        return QueryProfile(
            intent=intent,
            formula_terms=tuple(dict.fromkeys(formula_terms)),
            herb_terms=tuple(dict.fromkeys(herb_terms)),
            symptom_terms=tuple(dict.fromkeys(symptom_terms)),
            role_query=role_query,
            origin_query=origin_query,
            composition_query=composition_query,
            indication_query=indication_query,
            case_query=case_query,
        )

    def _rerank_qa_rows(
        self,
        query: str,
        rows: list[dict[str, Any]],
        *,
        profile: QueryProfile,
        top_k: int,
    ) -> list[dict[str, Any]]:
        normalized = _clean(query)
        reranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            score = -float(row.get("rank_score", 0.0) or 0.0)
            bucket = _clean(row.get("bucket"))
            question_type = _clean(row.get("question_type"))
            haystack = "\n".join(
                [
                    _clean(row.get("question")),
                    _clean(row.get("answer")),
                    _clean(row.get("formula_text")),
                    _clean(row.get("keyword_text")),
                ]
            )

            if profile.origin_query:
                if bucket == "origin_qa":
                    score += 6.0
                if question_type == "origin":
                    score += 5.0
                if any(hint in haystack for hint in ("出处", "原文", "出自")):
                    score += 2.0
            if profile.intent.startswith("formula"):
                if bucket == "formula_qa":
                    score += 6.0
                if question_type in {"composition", "efficacy", "indication"}:
                    score += 4.0
                for formula in profile.formula_terms:
                    if formula and formula in haystack:
                        score += 3.0
                for herb in profile.herb_terms:
                    if herb and herb in haystack:
                        score += 2.5
                if profile.role_query:
                    if any(hint in haystack for hint in ("作用", "功效", "配伍", "君药", "臣药", "佐药", "使药")):
                        score += 2.5
                    else:
                        score -= 1.5
                if profile.composition_query and any(hint in haystack for hint in ("组成", "成分", "配方")):
                    score += 2.0
                if profile.indication_query and any(hint in haystack for hint in ("主治", "证候", "症状")):
                    score += 2.0
            if not profile.intent.startswith("formula") and bucket == "formula_qa" and not profile.origin_query:
                score -= 0.5
            if normalized and normalized in haystack:
                score += 2.0

            row["_rerank_score"] = round(score, 6)
            reranked.append((score, row))

        reranked.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in reranked[: max(1, int(top_k))]]

    def _rerank_case_rows(
        self,
        query: str,
        rows: list[dict[str, Any]],
        *,
        profile: QueryProfile,
        top_k: int,
    ) -> list[dict[str, Any]]:
        normalized = _clean(query)
        age_match = re.search(r"(\d{1,3})岁", normalized)
        sex_terms = [term for term in ("男", "女") if term in normalized]
        reranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            score = -float(row.get("rank_score", 0.0) or 0.0)
            haystack = "\n".join(
                [
                    _clean(row.get("question")),
                    _clean(row.get("answer")),
                    _clean(row.get("chief_complaint")),
                    _clean(row.get("history")),
                    _clean(row.get("tongue")),
                    _clean(row.get("pulse")),
                    _clean(row.get("formula_text")),
                    _clean(row.get("symptom_text")),
                    _clean(row.get("syndrome_text")),
                ]
            )
            if profile.case_query:
                score += 2.0
            if age_match and age_match.group(1) and age_match.group(1) in haystack:
                score += 3.0
            for sex in sex_terms:
                if sex in haystack:
                    score += 2.0
            for symptom in profile.symptom_terms:
                if symptom and symptom in haystack:
                    score += 1.5
            if any(token in haystack for token in ("诊断", "治疗方案", "医案", "患者", "主诉", "现病史")):
                score += 1.2
            row["_rerank_score"] = round(score, 6)
            reranked.append((score, row))

        reranked.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in reranked[: max(1, int(top_k))]]
