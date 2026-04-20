from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from array import array
from datetime import datetime
from pathlib import Path
from typing import Any

from services.retrieval_service.engine import RetrievalEngine
from services.retrieval_service.files_first_support import extract_book_name, extract_chapter_title
from services.qa_service.alias_service import get_runtime_alias_service

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover
    jieba = None


QUERY_STOP_TERMS = {
    "什么",
    "为何",
    "为什么",
    "怎么",
    "如何",
    "请给",
    "请从",
    "请概括",
    "请解释",
    "哪本书",
    "哪部书",
    "出处",
    "原文",
    "片段",
    "记载",
    "论述",
    "条文",
    "是什么",
}
QUERY_NOISE_PATTERNS = ("是什么", "什么作用", "有什么不同", "适合直接引用", "请从", "请给", "请概括")
QUERY_STRIP_PATTERNS = (
    "什么叫",
    "是什么",
    "为什么",
    "请给",
    "请从",
    "请概括",
    "请解释",
    "常参考什么方",
    "可参考什么方剂",
    "适合直接引用的",
    "在方剂中起什么作用",
    "适用边界上有什么不同",
    "在古籍中常见的",
    "在本草文献中常见的",
    "在本草文献中的",
    "关于",
    "方后注",
)
FORMULA_SUFFIXES = ("汤", "散", "丸", "饮", "膏", "丹", "方", "颗粒", "胶囊")
HERB_SUFFIXES = ("草", "花", "叶", "根", "子", "仁", "皮", "藤", "术", "芩", "芎", "苓", "黄", "参", "胡")
CONCEPT_SUFFIXES = ("病", "证", "痹", "痛", "虚", "郁", "热", "寒", "咳", "喘")
FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}?(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊)")
BOOK_HINTS = (
    "黄帝内经",
    "灵枢",
    "素问",
    "伤寒论",
    "金匮要略",
    "温病条辨",
    "医方集解",
    "医方论",
    "小儿药证直诀",
    "本草纲目",
    "神农本草经",
    "脾胃论",
    "临证指南医案",
)


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def count_rows(path: Path) -> int:
    total = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                total += 1
    return total


def load_first_valid_row(path: Path) -> dict[str, Any]:
    for row in iter_jsonl(path):
        return row
    raise RuntimeError("rows_jsonl_empty")


def dense_to_blob(values: list[float]) -> bytes:
    arr = array("f", [float(value) for value in values])
    return arr.tobytes()


def blob_to_dense(blob: bytes) -> list[float]:
    arr = array("f")
    arr.frombytes(blob)
    return arr.tolist()


def sparse_dot(left: dict[int, float], right_json: str) -> float:
    if not left or not right_json:
        return 0.0
    try:
        right_payload = json.loads(right_json)
    except Exception:
        return 0.0
    if not isinstance(right_payload, dict):
        return 0.0
    score = 0.0
    for key, value in left.items():
        score += float(value) * float(right_payload.get(str(int(key)), 0.0) or 0.0)
    return score


def dense_dot(left: list[float], right_blob: bytes) -> float:
    if not left or not right_blob:
        return 0.0
    right = blob_to_dense(right_blob)
    return float(sum(a * b for a, b in zip(left, right)))


def build_rrf_results(*, rows: list[dict[str, Any]], dense_scores: dict[str, float], sparse_scores: dict[str, float], top_k: int) -> list[dict[str, Any]]:
    dense_ranked = sorted(dense_scores.items(), key=lambda item: item[1], reverse=True)
    sparse_ranked = sorted(sparse_scores.items(), key=lambda item: item[1], reverse=True)
    rrf_scores: dict[str, float] = {}
    for rank, (chunk_id, _) in enumerate(dense_ranked, start=1):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (60 + rank)
    for rank, (chunk_id, _) in enumerate(sparse_ranked, start=1):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (60 + rank)

    row_map = {str(row.get("chunk_id", "")): row for row in rows}
    merged = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)[: max(1, top_k)]
    results: list[dict[str, Any]] = []
    for rank, (chunk_id, score) in enumerate(merged, start=1):
        row = dict(row_map[chunk_id])
        row["score"] = score
        row["rrf_rank"] = rank
        row["dense_score"] = dense_scores.get(chunk_id, 0.0)
        row["sparse_score"] = sparse_scores.get(chunk_id, 0.0)
        row["match_snippet"] = str(row.get("text", "") or "")[:240]
        results.append(row)
    return results


def _looks_like_entity(term: str) -> bool:
    normalized = str(term or "").strip()
    if len(normalized) < 2:
        return False
    if normalized in BOOK_HINTS:
        return True
    if normalized.endswith(FORMULA_SUFFIXES):
        return True
    if normalized.endswith(HERB_SUFFIXES):
        return True
    if normalized.endswith(CONCEPT_SUFFIXES):
        return True
    return False


def _is_formula_like(term: str) -> bool:
    normalized = str(term or "").strip()
    return bool(normalized) and normalized.endswith(FORMULA_SUFFIXES)


def _is_book_like(term: str) -> bool:
    return str(term or "").strip() in BOOK_HINTS


def _is_concept_like(term: str) -> bool:
    normalized = str(term or "").strip()
    return _looks_like_entity(normalized) and not _is_formula_like(normalized) and not _is_book_like(normalized)


def _is_noisy_term(term: str) -> bool:
    normalized = str(term or "").strip()
    if not normalized:
        return True
    if normalized in QUERY_STOP_TERMS:
        return True
    if len(normalized) > 8 and not _looks_like_entity(normalized) and normalized not in BOOK_HINTS:
        return True
    if normalized.endswith("是什么") or normalized.endswith("功效是什么") or normalized.endswith("作用是什么"):
        return True
    if any(pattern in normalized for pattern in QUERY_NOISE_PATTERNS) and not _looks_like_entity(normalized):
        return True
    return False


def _query_flags(query: str) -> dict[str, bool]:
    text = str(query or "").strip()
    return {
        "source_query": any(marker in text for marker in ("出处", "原文", "原句", "哪本书", "哪部书")),
        "comparison_query": any(marker in text for marker in ("比较", "区别", "异同", "不同")),
        "property_query": any(marker in text for marker in ("功效", "归经", "性味", "作用")),
        "composition_query": any(marker in text for marker in ("组成", "药味", "配方", "哪些药")),
    }


def _books_in_query(query: str) -> list[str]:
    text = str(query or "").strip()
    return [book for book in BOOK_HINTS if book in text]


def _normalize_formula_match(value: str) -> str:
    normalized = str(value or "").strip().lstrip("和与跟及")
    if "的" in normalized:
        tail = normalized.split("的")[-1].strip()
        if tail.endswith(FORMULA_SUFFIXES):
            normalized = tail
    return normalized


def _strip_query_noise(text: str) -> str:
    normalized = str(text or "").strip()
    for pattern in QUERY_STRIP_PATTERNS:
        normalized = normalized.replace(pattern, " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _split_compare_entities(query: str) -> list[str]:
    text = str(query or "").strip()
    split_parts = re.split(r"(?:和|与|跟|及|、|，|,)", text)
    formula_matches: list[str] = []
    for part in split_parts:
        cleaned_part = str(part or "").strip().lstrip("和与跟及")
        formula_matches.extend(
            _normalize_formula_match(item)
            for item in FORMULA_PATTERN.findall(cleaned_part)
            if _normalize_formula_match(item)
        )
    if len(formula_matches) >= 2:
        return list(dict.fromkeys(formula_matches[:4]))
    pairs = re.match(
        r"^([\u4e00-\u9fff]{2,16}?)(?:和|与|跟|及)([\u4e00-\u9fff]{2,16}?)(?:除|在|有|适用|组成|区别|不同|偏重|偏于|上|中|的|，|,|。|$)",
        text,
    )
    if pairs:
        return [pairs.group(1), pairs.group(2)]
    return []


def _entity_from_relation_query(query: str) -> list[str]:
    text = _strip_query_noise(str(query or "").strip())
    results: list[str] = []
    direct_formulas = [
        _normalize_formula_match(item)
        for item in FORMULA_PATTERN.findall(text)
        if _normalize_formula_match(item)
    ]
    if direct_formulas:
        results.extend(direct_formulas[:3])
    # 1. Formula + herb role style query: "托里消毒饮中的金银花在方剂中起什么作用"
    match = re.search(
        r"^([\u4e00-\u9fff]{2,16}(?:汤|散|丸|饮|膏|丹|方|颗粒|胶囊))中的([\u4e00-\u9fff]{2,8}?)(?:在|起|的|$)",
        text,
    )
    if match:
        for value in match.groups():
            if value:
                results.append(str(value).strip())
        return list(dict.fromkeys(item for item in results if item))

    # 2. Most property/source queries expose the anchor entity before "的".
    if "的" in text:
        head = text.split("的", 1)[0].strip()
        if head.endswith("中") and any(head[:-1].endswith(suffix) for suffix in FORMULA_SUFFIXES):
            head = head[:-1]
        if 2 <= len(head) <= 16:
            results.append(head)
            return list(dict.fromkeys(item for item in results if item))

    # 3. Explicit source/composition markers.
    for marker in ("最早见于", "出自", "见于", "包含哪些药", "包含什么药"):
        if marker in text:
            head = text.split(marker, 1)[0].strip()
            if 2 <= len(head) <= 16:
                results.append(head)
    return list(dict.fromkeys(item for item in results if item))


def _extract_focus_entities(query: str, engine: RetrievalEngine) -> list[str]:
    normalized = _strip_query_noise(str(query or "").strip())
    alias_service = get_runtime_alias_service()
    entities: list[str] = []
    flags = _query_flags(normalized)
    direct_formulas = list(
        dict.fromkeys(
            _normalize_formula_match(item)
            for item in FORMULA_PATTERN.findall(normalized)
            if _normalize_formula_match(item)
        )
    )
    for book in BOOK_HINTS:
        if book in normalized and book not in entities:
            entities.append(book)
    compare_entities = _split_compare_entities(normalized) if flags["comparison_query"] else []
    for item in compare_entities:
        if item not in entities:
            entities.append(item)
    for item in _entity_from_relation_query(normalized):
        if item not in entities and not _is_noisy_term(item):
            entities.append(item)
    if compare_entities:
        return list(dict.fromkeys([*entities, *compare_entities]))[:4]
    if direct_formulas and (flags["source_query"] or flags["composition_query"] or flags["property_query"]):
        return direct_formulas[:4]
    if entities and (flags["property_query"] or flags["source_query"] or flags["composition_query"]):
        return list(dict.fromkeys(item for item in entities if not _is_noisy_term(item)))[:4]
    if alias_service.is_available():
        entities.extend(alias_service.detect_entities(normalized, limit=4))
    if jieba is not None:
        for word in [*BOOK_HINTS, *entities]:
            if len(str(word).strip()) >= 2:
                jieba.add_word(str(word).strip(), freq=200000)
        for token in jieba.cut_for_search(normalized):
            cleaned = str(token or "").strip()
            if len(cleaned) < 2 or _is_noisy_term(cleaned):
                continue
            if _looks_like_entity(cleaned) and cleaned not in entities:
                entities.append(cleaned)
    for match in (
        _normalize_formula_match(item)
        for item in FORMULA_PATTERN.findall(normalized)
        if _normalize_formula_match(item)
    ):
        if match not in entities:
            entities.append(match)
    for match in re.findall(r"[\u4e00-\u9fff]{2,8}", normalized):
        if _is_noisy_term(match):
            continue
        if _looks_like_entity(match) and match not in entities:
            entities.append(match)
        elif flags["property_query"] and len(match) in {2, 3} and match not in entities:
            entities.append(match)
    return list(dict.fromkeys(entity for entity in entities if entity))[:4]


def _build_sparse_query(engine: RetrievalEngine, terms: list[str]) -> dict[int, float]:
    sparse: dict[int, float] = {}
    for term in terms:
        normalized = str(term or "").strip()
        if len(normalized) < 2:
            continue
        token_id = engine.lexicon._vocab.get(normalized)  # noqa: SLF001
        if token_id is None:
            continue
        idf = engine.lexicon._idf(normalized)  # noqa: SLF001
        if idf <= 0:
            continue
        sparse[int(token_id)] = float(idf)
    return sparse


def _extract_query_terms(query: str, engine: RetrievalEngine) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized:
        return []
    alias_service = get_runtime_alias_service()
    focus_entities = _extract_focus_entities(normalized, engine)
    expanded = alias_service.expand_query_with_aliases(
        normalized,
        focus_entities=focus_entities,
        max_aliases_per_entity=3,
        max_entities=2,
    ) if alias_service.is_available() else normalized
    stripped = _strip_query_noise(expanded)

    terms: list[str] = []
    seen: set[str] = set()

    def push(term: str) -> None:
        cleaned = str(term or "").strip()
        if len(cleaned) < 2:
            return
        if _is_noisy_term(cleaned):
            return
        if cleaned in seen:
            return
        seen.add(cleaned)
        terms.append(cleaned)

    for entity in focus_entities:
        push(entity)
        if alias_service.is_available():
            for alias_name in alias_service.aliases_for_entity(entity, max_aliases=3):
                push(alias_name)

    # Only keep meaningful multi-char lexical tokens. Avoid single-char BM25-style noise.
    for token in engine.lexicon.tokenize(stripped):
        if len(str(token).strip()) >= 2:
            push(token)

    if jieba is not None:
        for word in [*BOOK_HINTS, *focus_entities]:
            if len(str(word).strip()) >= 2:
                jieba.add_word(str(word).strip(), freq=200000)
        for token in jieba.cut_for_search(stripped):
            cleaned = str(token or "").strip()
            if len(cleaned) >= 2:
                push(cleaned)

    chinese_spans = re.findall(r"[\u4e00-\u9fff]{2,20}", stripped)
    for span in chinese_spans:
        if _is_noisy_term(span):
            continue
        if _looks_like_entity(span):
            push(span)
        elif len(span) >= 4:
            push(span)
        if len(span) >= 3:
            widths = (6, 4, 3) if len(span) >= 6 else (4, 3)
            for width in widths:
                if len(span) < width:
                    continue
                for idx in range(0, len(span) - width + 1):
                    push(span[idx : idx + width])

    for ascii_term in re.findall(r"[A-Za-z0-9_.%-]{2,32}", stripped):
        push(ascii_term)

    return terms[:32]


class ClassicsVectorSQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=FILE")
        conn.execute("PRAGMA cache_size=-65536")
        return conn

    def create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vector_rows (
                chunk_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_idx INTEGER NOT NULL,
                parent_chunk_id TEXT NOT NULL,
                root_chunk_id TEXT NOT NULL,
                chunk_level INTEGER NOT NULL,
                book_name TEXT NOT NULL DEFAULT '',
                chapter_title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                dense_blob BLOB NOT NULL,
                sparse_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_vector_rows_file_path ON vector_rows(file_path);
            CREATE INDEX IF NOT EXISTS idx_vector_rows_book_name ON vector_rows(book_name);
            CREATE INDEX IF NOT EXISTS idx_vector_rows_chunk_level ON vector_rows(chunk_level);

            CREATE VIRTUAL TABLE IF NOT EXISTS vector_rows_fts USING fts5(
                chunk_id UNINDEXED,
                text,
                filename,
                file_path,
                book_name,
                chapter_title,
                tokenize='trigram'
            );
            """
        )

    def reset(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        shm = self.db_path.with_suffix(self.db_path.suffix + "-shm")
        wal = self.db_path.with_suffix(self.db_path.suffix + "-wal")
        for path in (shm, wal):
            if path.exists():
                path.unlink()

    def health(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {
                "db_path": str(self.db_path),
                "available": False,
                "rows": 0,
            }
        with self.connect() as conn:
            count = int(conn.execute("SELECT COUNT(1) FROM vector_rows").fetchone()[0])
        return {
            "db_path": str(self.db_path),
            "available": count > 0,
            "rows": count,
        }

    def import_rows_jsonl(
        self,
        *,
        rows_path: Path,
        state_path: Path,
        batch_size: int,
        reset: bool,
    ) -> dict[str, Any]:
        if not rows_path.exists():
            raise FileNotFoundError(f"rows_jsonl_not_found: {rows_path}")

        total_rows = count_rows(rows_path)
        state = read_json(state_path, {})
        if reset or not isinstance(state, dict):
            state = {
                "created_at": now_text(),
                "updated_at": now_text(),
                "status": "idle",
                "rows_path": str(rows_path),
                "total_rows": total_rows,
                "inserted_rows": 0,
                "byte_offset": 0,
                "last_error": "",
            }
        state["rows_path"] = str(rows_path)
        state["total_rows"] = total_rows
        write_json(state_path, state)

        if reset:
            self.reset()

        inserted = int(state.get("inserted_rows", 0) or 0)
        byte_offset = int(state.get("byte_offset", 0) or 0)
        started = time.perf_counter()

        with self.connect() as conn:
            self.create_schema(conn)
            state["status"] = "running"
            state["last_error"] = ""
            write_json(state_path, state)

            rows_batch: list[tuple[Any, ...]] = []
            fts_batch: list[tuple[Any, ...]] = []
            batch_end_offset = byte_offset

            try:
                with rows_path.open("rb") as f:
                    if byte_offset > 0:
                        f.seek(byte_offset)
                    while True:
                        raw_line = f.readline()
                        if not raw_line:
                            break
                        batch_end_offset = f.tell()
                        try:
                            row = json.loads(raw_line.decode("utf-8").strip())
                        except Exception:
                            continue
                        if not isinstance(row, dict):
                            continue
                        text = str(row.get("text", "") or "")
                        file_path = str(row.get("file_path", "") or "")
                        filename = str(row.get("filename", "") or "")
                        page_number = int(row.get("page_number", 0) or 0)
                        book_name = extract_book_name(text=text, filename=filename, file_path=file_path)
                        chapter_title = extract_chapter_title(text=text, page_number=page_number, file_path=file_path)
                        chunk_id = str(row.get("chunk_id", "") or "").strip()
                        dense_blob = dense_to_blob([float(v) for v in (row.get("dense_embedding", []) or [])])
                        sparse_json = json.dumps(row.get("sparse_embedding", {}) if isinstance(row.get("sparse_embedding", {}), dict) else {}, ensure_ascii=False)

                        rows_batch.append(
                            (
                                chunk_id,
                                file_path,
                                filename,
                                str(row.get("file_type", "TXT") or "TXT"),
                                page_number,
                                int(row.get("chunk_idx", 0) or 0),
                                str(row.get("parent_chunk_id", "") or ""),
                                str(row.get("root_chunk_id", "") or ""),
                                int(row.get("chunk_level", 3) or 3),
                                book_name,
                                chapter_title,
                                text,
                                dense_blob,
                                sparse_json,
                            )
                        )
                        fts_batch.append((chunk_id, text, filename, file_path, book_name, chapter_title))

                        if len(rows_batch) >= batch_size:
                            conn.executemany(
                                """
                                INSERT OR REPLACE INTO vector_rows (
                                    chunk_id, file_path, filename, file_type, page_number, chunk_idx,
                                    parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title,
                                    text, dense_blob, sparse_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                rows_batch,
                            )
                            conn.executemany(
                                """
                                INSERT INTO vector_rows_fts (
                                    chunk_id, text, filename, file_path, book_name, chapter_title
                                ) VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                fts_batch,
                            )
                            conn.commit()
                            inserted += len(rows_batch)
                            state["inserted_rows"] = inserted
                            state["byte_offset"] = batch_end_offset
                            state["updated_at"] = now_text()
                            write_json(state_path, state)
                            elapsed = max(0.1, time.perf_counter() - started)
                            rate = inserted / elapsed
                            eta = (total_rows - inserted) / rate if rate > 0 else 0
                            print(
                                f"[rows->sqlite] {progress_bar(inserted, total_rows)} "
                                f"{inserted}/{total_rows} ({inserted * 100.0 / max(1, total_rows):.1f}%) "
                                f"rate={rate:.1f} rows/s eta={format_seconds(eta)}",
                                flush=True,
                            )
                            rows_batch = []
                            fts_batch = []

                    if rows_batch:
                        conn.executemany(
                            """
                            INSERT OR REPLACE INTO vector_rows (
                                chunk_id, file_path, filename, file_type, page_number, chunk_idx,
                                parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title,
                                text, dense_blob, sparse_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            rows_batch,
                        )
                        conn.executemany(
                            """
                            INSERT INTO vector_rows_fts (
                                chunk_id, text, filename, file_path, book_name, chapter_title
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            fts_batch,
                        )
                        conn.commit()
                        inserted += len(rows_batch)
                        state["inserted_rows"] = inserted
                        state["byte_offset"] = batch_end_offset
                        state["updated_at"] = now_text()
                        write_json(state_path, state)
                        elapsed = max(0.1, time.perf_counter() - started)
                        rate = inserted / elapsed
                        eta = (total_rows - inserted) / rate if rate > 0 else 0
                        print(
                            f"[rows->sqlite] {progress_bar(inserted, total_rows)} "
                            f"{inserted}/{total_rows} ({inserted * 100.0 / max(1, total_rows):.1f}%) "
                            f"rate={rate:.1f} rows/s eta={format_seconds(eta)}",
                            flush=True,
                        )
            except KeyboardInterrupt:
                state["status"] = "interrupted"
                state["updated_at"] = now_text()
                write_json(state_path, state)
                raise
            except Exception as exc:
                state["status"] = "failed"
                state["last_error"] = str(exc)
                state["updated_at"] = now_text()
                write_json(state_path, state)
                raise

            state["status"] = "completed"
            state["updated_at"] = now_text()
            write_json(state_path, state)

        return {
            "state_path": str(state_path),
            "rows_path": str(rows_path),
            "db_path": str(self.db_path),
            "inserted_rows": inserted,
            "total_rows": total_rows,
        }

    def _fts_query(self, query: str, engine: RetrievalEngine, *, candidate_limit: int) -> list[str]:
        terms = _extract_query_terms(query, engine)
        focus_entities = _extract_focus_entities(query, engine)
        candidate_ids: list[str] = []
        seen: set[str] = set()

        def append_ids(rows: list[tuple[Any, ...]]) -> None:
            for row in rows:
                chunk_id = str(row[0] or "").strip()
                if not chunk_id or chunk_id in seen:
                    continue
                seen.add(chunk_id)
                candidate_ids.append(chunk_id)

        with self.connect() as conn:
            # First: strong exact/substring recall for detected entities.
            for entity in focus_entities:
                rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM vector_rows
                    WHERE chapter_title = ?
                       OR book_name = ?
                       OR book_name LIKE ?
                       OR text LIKE ?
                    LIMIT ?
                    """,
                    (entity, entity, f"%{entity}%", f"%{entity}%", max(candidate_limit, 20)),
                ).fetchall()
                append_ids(rows)
                if len(candidate_ids) >= max(candidate_limit, 20):
                    break

            # Multi-entity joint recall: prefer chunks mentioning multiple anchors together.
            if len(focus_entities) >= 2:
                first = focus_entities[0]
                second = focus_entities[1]
                rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM vector_rows
                    WHERE text LIKE ?
                      AND text LIKE ?
                    LIMIT ?
                    """,
                    (f"%{first}%", f"%{second}%", max(candidate_limit, 20)),
                ).fetchall()
                append_ids(rows)

            # Concept-to-formula recall: if the query centers on a concept such as 胸痹/少阴病,
            # prefer formula-like chapter titles that mention the concept in text.
            for entity in focus_entities:
                if not _is_concept_like(entity):
                    continue
                rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM vector_rows
                    WHERE text LIKE ?
                      AND (
                          chapter_title LIKE '%汤' OR chapter_title LIKE '%散' OR chapter_title LIKE '%丸'
                          OR chapter_title LIKE '%饮' OR chapter_title LIKE '%膏' OR chapter_title LIKE '%丹'
                          OR chapter_title LIKE '%方' OR chapter_title LIKE '%颗粒' OR chapter_title LIKE '%胶囊'
                      )
                    LIMIT ?
                    """,
                    (f"%{entity}%", max(candidate_limit, 20)),
                ).fetchall()
                append_ids(rows)

            if terms:
                clauses = ['"' + term.replace('"', " ") + '"' for term in terms if len(term.strip()) >= 3]
                if clauses:
                    match_expression = " OR ".join(clauses)
                    try:
                        rows = conn.execute(
                            """
                            SELECT chunk_id
                            FROM vector_rows_fts
                            WHERE vector_rows_fts MATCH ?
                            LIMIT ?
                            """,
                            (match_expression, max(candidate_limit * 2, 40)),
                        ).fetchall()
                        append_ids(rows)
                    except sqlite3.OperationalError:
                        pass

            # Fallback for 2-char herbs/entities and exact phrase lookup.
            for term in terms[:12]:
                rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM vector_rows
                    WHERE text LIKE ?
                       OR book_name LIKE ?
                       OR chapter_title LIKE ?
                    LIMIT ?
                    """,
                    (f"%{term}%", f"%{term}%", f"%{term}%", max(candidate_limit // 2, 10)),
                ).fetchall()
                append_ids(rows)
                if len(candidate_ids) >= max(candidate_limit, 20):
                    break

            if not candidate_ids:
                rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM vector_rows
                    WHERE text LIKE ?
                    LIMIT ?
                    """,
                    (f"%{str(query).strip()}%", max(candidate_limit, 20)),
                ).fetchall()
                append_ids(rows)

        return candidate_ids[: max(candidate_limit * 2, 40)]

    def search_hybrid(
        self,
        *,
        engine: RetrievalEngine,
        query: str,
        top_k: int,
        candidate_k: int,
    ) -> dict[str, Any]:
        query_embedding = engine.embedding_client.embed([query], engine.settings.embedding_model)[0]
        terms = _extract_query_terms(query, engine)
        query_sparse = _build_sparse_query(engine, terms)
        flags = _query_flags(query)
        focus_entities = _extract_focus_entities(query, engine)
        books_in_query = _books_in_query(query)
        candidate_ids = self._fts_query(query, engine, candidate_limit=max(candidate_k * 4, 64))
        if not candidate_ids:
            return {
                "retrieval_mode": "sqlite_vector_hybrid_empty",
                "chunks": [],
                "total": 0,
                "warnings": ["sqlite_vector_candidate_empty"],
            }

        placeholders = ",".join("?" for _ in candidate_ids)
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT chunk_id, file_path, filename, file_type, page_number, chunk_idx,
                       parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title,
                       text, dense_blob, sparse_json
                FROM vector_rows
                WHERE chunk_id IN ({placeholders})
                """,
                candidate_ids,
            ).fetchall()

        dense_scores: dict[str, float] = {}
        sparse_scores: dict[str, float] = {}
        lexical_scores: dict[str, float] = {}
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            chunk_id = str(payload.get("chunk_id", "") or "")
            dense_scores[chunk_id] = dense_dot(query_embedding, payload.get("dense_blob", b""))
            sparse_scores[chunk_id] = sparse_dot(query_sparse, str(payload.get("sparse_json", "") or ""))
            haystack = " ".join(
                [
                    str(payload.get("book_name", "") or ""),
                    str(payload.get("chapter_title", "") or ""),
                    str(payload.get("text", "") or ""),
                ]
            )
            lexical_bonus = 0.0
            for entity in focus_entities:
                if entity and entity == str(payload.get("chapter_title", "") or ""):
                    lexical_bonus += 12.0
                elif entity and entity in haystack:
                    lexical_bonus += 5.0
            if flags["property_query"] and any(entity == str(payload.get("chapter_title", "") or "") for entity in focus_entities):
                lexical_bonus += 10.0
            if flags["composition_query"] and any(entity == str(payload.get("chapter_title", "") or "") for entity in focus_entities):
                lexical_bonus += 10.0
            if len(focus_entities) >= 2:
                present = sum(1 for entity in focus_entities[:2] if entity and entity in haystack)
                if present >= 2:
                    lexical_bonus += 18.0
                elif present == 1:
                    lexical_bonus += 2.0
            if flags["comparison_query"] and len(focus_entities) >= 2:
                present = sum(1 for entity in focus_entities[:2] if entity and entity in haystack)
                if present >= 2:
                    lexical_bonus += 10.0
                elif present == 1:
                    lexical_bonus += 2.0
            for term in terms[:12]:
                if term and term in haystack:
                    lexical_bonus += 1.2
            if flags["source_query"]:
                chapter = str(payload.get("chapter_title", "") or "")
                book_name = str(payload.get("book_name", "") or "")
                if chapter in focus_entities:
                    lexical_bonus += 4.0
                if any(book in haystack or book in book_name for book in books_in_query):
                    lexical_bonus += 24.0
                elif books_in_query:
                    lexical_bonus -= 4.0
                if "古籍：" in str(payload.get("text", "") or "") and any(entity in haystack for entity in focus_entities):
                    lexical_bonus += 2.0
            elif books_in_query:
                book_name = str(payload.get("book_name", "") or "")
                if any(book in book_name for book in books_in_query):
                    lexical_bonus += 8.0
                else:
                    lexical_bonus -= 2.0
            if any(_is_concept_like(entity) for entity in focus_entities):
                chapter = str(payload.get("chapter_title", "") or "")
                if _is_formula_like(chapter):
                    concept_hits = sum(1 for entity in focus_entities if _is_concept_like(entity) and entity in haystack)
                    if concept_hits > 0:
                        lexical_bonus += 8.0 + concept_hits * 2.0
            lexical_scores[chunk_id] = lexical_bonus
            payload.pop("dense_blob", None)
            payload.pop("sparse_json", None)
            normalized_rows.append(payload)

        # Promote lexical anchors into sparse score to make chapter/entity hits visible in RRF.
        for chunk_id, bonus in lexical_scores.items():
            sparse_scores[chunk_id] = sparse_scores.get(chunk_id, 0.0) + bonus

        chunks = build_rrf_results(
            rows=normalized_rows,
            dense_scores=dense_scores,
            sparse_scores=sparse_scores,
            top_k=max(1, top_k),
        )
        return {
            "retrieval_mode": "sqlite_vector_hybrid",
            "chunks": chunks,
            "total": len(chunks),
            "warnings": [],
        }
