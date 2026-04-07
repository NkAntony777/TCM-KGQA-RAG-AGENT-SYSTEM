from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_GRAPH_DB_PATH = (
    Path(__file__).resolve().parents[1] / "graph_service" / "data" / "graph_runtime.db"
)


@dataclass(frozen=True)
class AliasRelation:
    entity: str
    alias: str
    source_book: str
    source_chapter: str
    source_text: str
    support: int = 1


class RuntimeAliasService:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_RUNTIME_GRAPH_DB_PATH
        self._adjacency: dict[str, dict[str, int]] | None = None
        self._relations: dict[tuple[str, str], list[AliasRelation]] | None = None
        self._known_names: tuple[str, ...] | None = None

    def is_available(self) -> bool:
        return self.db_path.exists()

    def aliases_for_entity(self, entity_name: str, *, max_aliases: int = 6, max_depth: int = 2) -> list[str]:
        normalized = str(entity_name or "").strip()
        if not normalized:
            return []
        self._ensure_loaded()
        adjacency = self._adjacency or {}
        if normalized not in adjacency:
            return []

        depths: dict[str, int] = {normalized: 0}
        support_scores: dict[str, int] = {}
        queue: deque[str] = deque([normalized])

        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            if current_depth >= max_depth:
                continue
            for neighbor, support in (adjacency.get(current) or {}).items():
                if neighbor == normalized:
                    continue
                if neighbor not in depths or current_depth + 1 < depths[neighbor]:
                    depths[neighbor] = current_depth + 1
                    queue.append(neighbor)
                support_scores[neighbor] = max(support_scores.get(neighbor, 0), int(support or 0))

        ranked = sorted(
            support_scores,
            key=lambda item: (
                depths.get(item, 99),
                -support_scores.get(item, 0),
                -len(item),
                item,
            ),
        )
        return ranked[: max(1, max_aliases)]

    def detect_entities(self, text: str, *, limit: int = 3) -> list[str]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        self._ensure_loaded()
        matches: list[str] = []
        for name in self._known_names or ():
            if name and name in normalized:
                matches.append(name)
                if len(matches) >= max(1, limit):
                    break
        return matches

    def expand_query_with_aliases(
        self,
        query: str,
        *,
        focus_entities: list[str] | None = None,
        max_aliases_per_entity: int = 3,
        max_entities: int = 2,
    ) -> str:
        base_query = str(query or "").strip()
        if not base_query:
            return ""

        entities = [
            str(item).strip()
            for item in (focus_entities or self.detect_entities(base_query, limit=max_entities))
            if str(item).strip()
        ]
        if not entities:
            return base_query

        extra_terms: list[str] = []
        seen = {base_query}
        for entity in entities[: max(1, max_entities)]:
            for alias in self.aliases_for_entity(entity, max_aliases=max_aliases_per_entity):
                if alias in base_query or alias in seen:
                    continue
                seen.add(alias)
                extra_terms.append(alias)
        if not extra_terms:
            return base_query
        return " ".join([base_query, *extra_terms]).strip()

    def alias_relations(self, entity_name: str, *, max_items: int = 6) -> list[AliasRelation]:
        normalized = str(entity_name or "").strip()
        if not normalized:
            return []
        self._ensure_loaded()

        collected: list[AliasRelation] = []
        seen_pairs: set[tuple[str, str]] = set()
        aliases = self.aliases_for_entity(normalized, max_aliases=max_items, max_depth=2)
        for alias in aliases:
            pair = tuple(sorted((normalized, alias)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            rows = (self._relations or {}).get(pair, [])
            if rows:
                collected.extend(rows[:1])
                continue
            collected.append(
                AliasRelation(
                    entity=normalized,
                    alias=alias,
                    source_book="graph_runtime",
                    source_chapter="",
                    source_text=f"{normalized} 别名 {alias}",
                    support=1,
                )
            )
        return collected[: max(1, max_items)]

    def _ensure_loaded(self) -> None:
        if self._adjacency is not None and self._relations is not None and self._known_names is not None:
            return

        adjacency: dict[str, dict[str, int]] = defaultdict(dict)
        relations: dict[tuple[str, str], list[AliasRelation]] = defaultdict(list)
        known_names: set[str] = set()
        if not self.db_path.exists():
            self._adjacency = {}
            self._relations = {}
            self._known_names = ()
            return

        try:
            with closing(sqlite3.connect(str(self.db_path))) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT
                        subject,
                        object,
                        source_book,
                        source_chapter,
                        best_source_text
                    FROM facts
                    WHERE predicate = '别名'
                      AND length(subject) BETWEEN 2 AND 24
                      AND length(object) BETWEEN 2 AND 24
                    """
                ).fetchall()
        except sqlite3.Error:
            self._adjacency = {}
            self._relations = {}
            self._known_names = ()
            return

        support_counter: dict[tuple[str, str], int] = defaultdict(int)
        for row in rows:
            subject = str(row["subject"] or "").strip()
            obj = str(row["object"] or "").strip()
            if not subject or not obj or subject == obj:
                continue
            known_names.add(subject)
            known_names.add(obj)
            pair = tuple(sorted((subject, obj)))
            support_counter[pair] += 1
            relation = AliasRelation(
                entity=subject,
                alias=obj,
                source_book=str(row["source_book"] or "").strip(),
                source_chapter=str(row["source_chapter"] or "").strip(),
                source_text=str(row["best_source_text"] or "").strip(),
                support=1,
            )
            relations[pair].append(relation)

        for (left, right), support in support_counter.items():
            adjacency[left][right] = max(adjacency[left].get(right, 0), support)
            adjacency[right][left] = max(adjacency[right].get(left, 0), support)

        ordered_names = tuple(sorted(known_names, key=lambda item: (-len(item), item)))
        self._adjacency = {key: dict(value) for key, value in adjacency.items()}
        self._relations = {key: list(value) for key, value in relations.items()}
        self._known_names = ordered_names


@lru_cache(maxsize=1)
def get_runtime_alias_service() -> RuntimeAliasService:
    return RuntimeAliasService()


def clear_runtime_alias_service_cache() -> None:
    get_runtime_alias_service.cache_clear()
