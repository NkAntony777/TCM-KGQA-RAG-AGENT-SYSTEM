from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover - optional lexical enhancement only
    jieba = None


class SparseLexiconStore:
    def __init__(self, store_path: Path, *, runtime_graph_db_path: Path | None = None):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_graph_db_path = runtime_graph_db_path
        self._vocab: dict[str, int] = {}
        self._doc_freq: Counter[str] = Counter()
        self._total_docs = 0
        self._avg_doc_len = 1.0
        self.k1 = 1.5
        self.b = 0.75
        self.load()

    def tokenize(self, text: str) -> list[str]:
        normalized = (text or "").lower()
        tokens: list[str] = []
        seen: set[str] = set()
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
        english_pattern = re.compile(r"[a-zA-Z]+")

        if jieba is not None and normalized:
            _prime_jieba_runtime_words(self.runtime_graph_db_path)
            for token in jieba.cut_for_search(normalized):
                cleaned = str(token or "").strip()
                if len(cleaned) >= 2 and cleaned not in seen:
                    seen.add(cleaned)
                    tokens.append(cleaned)

        idx = 0
        while idx < len(normalized):
            char = normalized[idx]
            if chinese_pattern.match(char):
                if char not in seen:
                    seen.add(char)
                    tokens.append(char)
                idx += 1
            elif english_pattern.match(char):
                match = english_pattern.match(normalized[idx:])
                if match:
                    token = match.group()
                    if token not in seen:
                        seen.add(token)
                        tokens.append(token)
                    idx += len(token)
                else:
                    idx += 1
            else:
                idx += 1
        return tokens

    def fit(self, texts: list[str]) -> None:
        self._vocab = {}
        self._doc_freq = Counter()
        self._total_docs = len(texts)
        total_len = 0

        for text in texts:
            tokens = self.tokenize(text)
            total_len += len(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freq[token] += 1
                if token not in self._vocab:
                    self._vocab[token] = len(self._vocab)

        self._avg_doc_len = total_len / self._total_docs if self._total_docs else 1.0

    def save(self) -> None:
        payload = {
            "vocab": self._vocab,
            "doc_freq": dict(self._doc_freq),
            "total_docs": self._total_docs,
            "avg_doc_len": self._avg_doc_len,
        }
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        self._vocab = {str(key): int(value) for key, value in payload.get("vocab", {}).items()}
        self._doc_freq = Counter({str(key): int(value) for key, value in payload.get("doc_freq", {}).items()})
        self._total_docs = int(payload.get("total_docs", 0) or 0)
        self._avg_doc_len = float(payload.get("avg_doc_len", 1.0) or 1.0)

    def is_ready(self) -> bool:
        return bool(self._vocab) and self._total_docs > 0

    def _idf(self, token: str) -> float:
        df = self._doc_freq.get(token, 0)
        if df <= 0:
            return 0.0
        return math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1)

    def encode_document(self, text: str) -> dict[int, float]:
        return self._encode(text, allow_new_tokens=True)

    def encode_query(self, text: str) -> dict[int, float]:
        return self._encode(text, allow_new_tokens=False)

    def _encode(self, text: str, *, allow_new_tokens: bool) -> dict[int, float]:
        tokens = self.tokenize(text)
        if not tokens:
            return {}

        tf = Counter(tokens)
        doc_len = len(tokens)
        sparse_vector: dict[int, float] = {}

        for token, freq in tf.items():
            if token not in self._vocab:
                if not allow_new_tokens:
                    continue
                self._vocab[token] = len(self._vocab)
            token_id = self._vocab[token]
            idf = self._idf(token)
            if idf <= 0:
                continue
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1))
            score = idf * numerator / denominator
            if score > 0:
                sparse_vector[token_id] = float(score)
        return sparse_vector


@lru_cache(maxsize=1)
def runtime_entity_words(runtime_graph_db_path: Path | None) -> tuple[str, ...]:
    if runtime_graph_db_path is None or not runtime_graph_db_path.exists():
        return ()
    try:
        with sqlite3.connect(str(runtime_graph_db_path)) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM entities
                WHERE length(name) BETWEEN 2 AND 24
                ORDER BY length(name) DESC, name ASC
                """
            ).fetchall()
    except sqlite3.Error:
        return ()
    words: list[str] = []
    for row in rows:
        name = str(row[0] or "").strip().lower()
        if not name:
            continue
        words.append(name)
    return tuple(dict.fromkeys(words))


@lru_cache(maxsize=1)
def prime_jieba_runtime_words(runtime_graph_db_path: Path | None) -> bool:
    if jieba is None:
        return False
    for word in runtime_entity_words(runtime_graph_db_path):
        if len(word) >= 2:
            jieba.add_word(word, freq=200000)
    return True
