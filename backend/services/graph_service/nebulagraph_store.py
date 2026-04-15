from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

try:  # pragma: no cover - optional dependency
    from nebula3.Config import Config as NebulaConfig
    from nebula3.gclient.net import ConnectionPool
except Exception:  # pragma: no cover
    NebulaConfig = None
    ConnectionPool = None


def _ensure_nebula_client_imported() -> bool:
    global NebulaConfig, ConnectionPool
    if NebulaConfig is not None and ConnectionPool is not None:
        return True
    try:  # pragma: no cover - runtime recovery path
        from nebula3.Config import Config as ImportedNebulaConfig
        from nebula3.gclient.net import ConnectionPool as ImportedConnectionPool
    except Exception:
        return False
    NebulaConfig = ImportedNebulaConfig
    ConnectionPool = ImportedConnectionPool
    return True


@dataclass(frozen=True)
class NebulaGraphSettings:
    host: str = "127.0.0.1"
    port: int = 9669
    user: str = "root"
    password: str = "nebula"
    space: str = "tcm_kg"
    vid_max_length: int = 64
    timeout_ms: int = 8000


def load_nebula_settings() -> NebulaGraphSettings:
    return NebulaGraphSettings(
        host=os.getenv("NEBULA_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=int(os.getenv("NEBULA_PORT", "9669").strip() or "9669"),
        user=os.getenv("NEBULA_USER", "root").strip() or "root",
        password=os.getenv("NEBULA_PASSWORD", "nebula").strip() or "nebula",
        space=os.getenv("NEBULA_SPACE", "tcm_kg").strip() or "tcm_kg",
        vid_max_length=int(os.getenv("NEBULA_VID_MAX_LENGTH", "64").strip() or "64"),
        timeout_ms=int(os.getenv("NEBULA_TIMEOUT_MS", "8000").strip() or "8000"),
    )


def entity_vid(name: str, max_length: int = 64) -> str:
    digest = hashlib.sha1((name or "").encode("utf-8")).hexdigest()
    value = f"ent_{digest}"
    return value[: max(8, max_length)]


def edge_rank(row: dict[str, Any]) -> int:
    fact_id = str(row.get("fact_id", "")).strip()
    if not fact_id:
        fact_id = "||".join(
            [
                str(row.get("subject", "")).strip(),
                str(row.get("predicate", "")).strip(),
                str(row.get("object", "")).strip(),
                str(row.get("source_book", "")).strip(),
                str(row.get("source_chapter", "")).strip(),
            ]
        )
    digest = hashlib.sha1(fact_id.encode("utf-8")).hexdigest()[:15]
    return int(digest, 16)


def _escape_ngql(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _load_evidence_map(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}

    evidence_map: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            fact_id = str(row.get("fact_id", "")).strip()
            if not fact_id:
                continue
            evidence_map[fact_id] = row
    return evidence_map


def _load_graph_payload(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line.lstrip("\ufeff"))
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("graph_payload_must_be_array")
    return [row for row in payload if isinstance(row, dict)]


def load_graph_rows(graph_path: Path, evidence_path: Path | None = None) -> list[dict[str, Any]]:
    payload = _load_graph_payload(graph_path)
    evidence_map = _load_evidence_map(evidence_path)
    rows: list[dict[str, Any]] = []
    for row in payload:
        merged = dict(row)
        fact_ids = merged.get("fact_ids")
        chosen_fact_id = ""
        if isinstance(fact_ids, list) and fact_ids:
            chosen_fact_id = str(fact_ids[0]).strip()
        elif merged.get("fact_id"):
            chosen_fact_id = str(merged.get("fact_id", "")).strip()

        evidence = evidence_map.get(chosen_fact_id, {})
        if evidence:
            merged.setdefault("source_text", evidence.get("source_text", ""))
            merged.setdefault("confidence", evidence.get("confidence", 0.0))
        rows.append(merged)
    return rows


class NebulaGraphStore:
    _pool_lock: Lock = Lock()
    _shared_pool: Any = None
    _shared_pool_key: tuple[str, int] | None = None

    def __init__(self, settings: NebulaGraphSettings | None = None):
        self.settings = settings or load_nebula_settings()

    def client_available(self) -> bool:
        return _ensure_nebula_client_imported()

    def health(self) -> dict[str, Any]:
        payload = {
            "backend": "nebulagraph",
            "client_available": self.client_available(),
            "space": self.settings.space,
            "host": self.settings.host,
            "port": self.settings.port,
        }
        if not self.client_available():
            payload["status"] = "unavailable"
            payload["warning"] = "nebula3-python not installed"
            return payload

        try:
            with self._session() as session:
                result = session.execute(f"USE `{self.settings.space}`;")
                payload["status"] = "ok" if result.is_succeeded() else "error"
                if not result.is_succeeded():
                    payload["warning"] = result.error_msg()
                return payload
        except Exception as exc:  # pragma: no cover - runtime integration path
            payload["status"] = "error"
            payload["warning"] = str(exc)
            return payload

    def ready(self) -> bool:
        return self.health().get("status") == "ok"

    def build_schema_statements(self) -> list[str]:
        space = self.settings.space
        return [
            f"CREATE SPACE IF NOT EXISTS `{space}` (partition_num=5, replica_factor=1, vid_type=FIXED_STRING({self.settings.vid_max_length}));",
            f"USE `{space}`;",
            "CREATE TAG IF NOT EXISTS `entity`(name string, entity_type string);",
            (
                "CREATE EDGE IF NOT EXISTS `relation`("
                "predicate string, source_book string, source_chapter string, "
                "fact_id string, fact_ids string, source_text string, confidence double);"
            ),
            "CREATE TAG INDEX IF NOT EXISTS `entity_name_idx` ON `entity`(name(256));",
        ]

    def build_import_statements(self, rows: list[dict[str, Any]]) -> list[str]:
        statements: list[str] = []
        seen_vertices: set[str] = set()

        for row in rows:
            subject = str(row.get("subject", "")).strip()
            obj = str(row.get("object", "")).strip()
            if not subject or not obj:
                continue

            for name, entity_type in (
                (subject, str(row.get("subject_type", "entity")).strip() or "entity"),
                (obj, str(row.get("object_type", "entity")).strip() or "entity"),
            ):
                vid = entity_vid(name, max_length=self.settings.vid_max_length)
                if vid in seen_vertices:
                    continue
                seen_vertices.add(vid)
                statements.append(
                    "INSERT VERTEX `entity`(name, entity_type) VALUES "
                    f'"{vid}":("{_escape_ngql(name)}","{_escape_ngql(entity_type)}");'
                )

            fact_ids = row.get("fact_ids")
            fact_ids_text = json.dumps(fact_ids if isinstance(fact_ids, list) else [], ensure_ascii=False)
            confidence = float(row.get("confidence", 0.0) or 0.0)
            statements.append(
                "INSERT EDGE `relation`("
                "predicate, source_book, source_chapter, fact_id, fact_ids, source_text, confidence"
                ") VALUES "
                f'"{entity_vid(subject, self.settings.vid_max_length)}"->"{entity_vid(obj, self.settings.vid_max_length)}"@{edge_rank(row)}:'
                "("
                f'"{_escape_ngql(str(row.get("predicate", "")).strip())}",'
                f'"{_escape_ngql(str(row.get("source_book", "")).strip())}",'
                f'"{_escape_ngql(str(row.get("source_chapter", "")).strip())}",'
                f'"{_escape_ngql(str(row.get("fact_id", "")).strip())}",'
                f'"{_escape_ngql(fact_ids_text)}",'
                f'"{_escape_ngql(str(row.get("source_text", "")).strip())}",'
                f"{confidence}"
                ");"
            )

        return statements

    def export_ngql(self, graph_path: Path, evidence_path: Path | None, output_path: Path) -> dict[str, Any]:
        rows = load_graph_rows(graph_path, evidence_path)
        statements = self.build_schema_statements() + self.build_import_statements(rows)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(statements) + "\n", encoding="utf-8")
        return {
            "graph_path": str(graph_path),
            "evidence_path": str(evidence_path) if evidence_path else "",
            "output_path": str(output_path),
            "space": self.settings.space,
            "triples": len(rows),
            "statements": len(statements),
        }

    def delete_rows(self, rows: list[dict[str, Any]], orphan_entity_names: list[str] | None = None) -> dict[str, Any]:
        if not self.client_available():
            raise RuntimeError("nebula3-python not installed")

        deleted_edges = 0
        deleted_vertices = 0
        orphan_entity_names = orphan_entity_names or []

        with self._session() as session:  # pragma: no cover - runtime integration path
            for row in rows:
                subject = str(row.get("subject", "")).strip()
                obj = str(row.get("object", "")).strip()
                if not subject or not obj:
                    continue
                statement = (
                    f'USE `{self.settings.space}`; '
                    f'DELETE EDGE `relation` "{entity_vid(subject, self.settings.vid_max_length)}"'
                    f'->"{entity_vid(obj, self.settings.vid_max_length)}"@{edge_rank(row)};'
                )
                result = session.execute(statement)
                if not result.is_succeeded():
                    raise RuntimeError(result.error_msg())
                deleted_edges += 1

            for entity_name in orphan_entity_names:
                statement = (
                    f'USE `{self.settings.space}`; '
                    f'DELETE VERTEX "{entity_vid(entity_name, self.settings.vid_max_length)}";'
                )
                result = session.execute(statement)
                if not result.is_succeeded():
                    raise RuntimeError(result.error_msg())
                deleted_vertices += 1

        return {
            "space": self.settings.space,
            "deleted_edges": deleted_edges,
            "deleted_vertices": deleted_vertices,
            "mode": "delete_rows",
        }

    def apply_ngql_file(self, ngql_path: Path) -> dict[str, Any]:
        if not self.client_available():
            raise RuntimeError("nebula3-python not installed")

        content = ngql_path.read_text(encoding="utf-8")
        statements = [item.strip() for item in content.splitlines() if item.strip()]
        executed = 0
        with self._session() as session:  # pragma: no cover - runtime integration path
            for statement in statements:
                result = session.execute(statement)
                if not result.is_succeeded():
                    raise RuntimeError(result.error_msg())
                executed += 1
        return {
            "space": self.settings.space,
            "input_path": str(ngql_path),
            "executed": executed,
        }

    def neighbors(self, entity_name: str, *, reverse: bool = False) -> list[dict[str, Any]]:
        vid = entity_vid(entity_name, self.settings.vid_max_length)
        edge_endpoint = "src(edge)" if reverse else "dst(edge)"
        over_clause = "`relation` REVERSELY" if reverse else "`relation`"
        statement = (
            f'USE `{self.settings.space}`; '
            f'GO FROM "{vid}" OVER {over_clause} '
            "YIELD "
            f"{edge_endpoint} AS neighbor_vid, "
            "properties($$).name AS neighbor_name, "
            "properties($$).entity_type AS neighbor_type, "
            "relation.predicate AS predicate, "
            "relation.source_book AS source_book, "
            "relation.source_chapter AS source_chapter, "
            "relation.fact_id AS fact_id, "
            "relation.fact_ids AS fact_ids, "
            "relation.source_text AS source_text, "
            "relation.confidence AS confidence;"
        )
        return self.execute_rows(statement)

    def batch_neighbors(
        self,
        entity_names: list[str],
        *,
        reverse: bool = False,
        predicates: list[str] | None = None,
        target_types: list[str] | None = None,
        source_books: list[str] | None = None,
        limit_per_entity: int = 64,
    ) -> list[dict[str, Any]]:
        vids = self._normalize_vid_inputs(entity_names)
        if not vids:
            return []

        source_vid_expr = "dst(edge)" if reverse else "src(edge)"
        neighbor_vid_expr = "src(edge)" if reverse else "dst(edge)"
        over_clause = "`relation` REVERSELY" if reverse else "`relation`"
        overall_limit = max(1, int(limit_per_entity)) * max(1, len(vids))
        base_statement = (
            f'USE `{self.settings.space}`; '
            f'GO FROM {self._format_vid_list(vids)} OVER {over_clause} '
            "YIELD "
            f"{source_vid_expr} AS source_vid, "
            f"{neighbor_vid_expr} AS neighbor_vid, "
            "properties($$).name AS neighbor_name, "
            "properties($$).entity_type AS neighbor_type, "
            "relation.predicate AS predicate, "
            "relation.source_book AS source_book, "
            "relation.source_chapter AS source_chapter, "
            "relation.fact_id AS fact_id, "
            "relation.fact_ids AS fact_ids, "
            "relation.source_text AS source_text, "
            "relation.confidence AS confidence"
        )

        where_clauses: list[str] = []
        if predicates:
            where_clauses.append(f"$-.predicate IN {self._format_string_list(predicates)}")
        if target_types:
            where_clauses.append(f"$-.neighbor_type IN {self._format_string_list(target_types)}")
        if source_books:
            where_clauses.append(f"$-.source_book IN {self._format_string_list(source_books)}")

        statement = base_statement
        if where_clauses:
            statement += " | WHERE " + " AND ".join(where_clauses)
        statement += f" | LIMIT {overall_limit};"

        try:
            return self.execute_rows(statement)
        except Exception:
            rows = self.execute_rows(base_statement + f" | LIMIT {overall_limit};")
            predicate_set = {str(item).strip() for item in predicates or [] if str(item).strip()}
            target_type_set = {str(item).strip() for item in target_types or [] if str(item).strip()}
            source_book_set = {str(item).strip() for item in source_books or [] if str(item).strip()}
            filtered: list[dict[str, Any]] = []
            for row in rows:
                predicate = str(row.get("predicate", "")).strip()
                neighbor_type = str(row.get("neighbor_type", "")).strip()
                source_book = str(row.get("source_book", "")).strip()
                if predicate_set and predicate not in predicate_set:
                    continue
                if target_type_set and neighbor_type not in target_type_set:
                    continue
                if source_book_set and source_book not in source_book_set:
                    continue
                filtered.append(row)
            return filtered[:overall_limit]

    def find_shortest_path_rows(
        self,
        start_entity_name: str | list[str],
        end_entity_name: str | list[str],
        *,
        max_hops: int = 4,
        limit: int = 5,
        with_prop: bool = True,
    ) -> list[dict[str, Any]]:
        start_vids = self._normalize_vid_inputs(start_entity_name)
        end_vids = self._normalize_vid_inputs(end_entity_name)
        if not start_vids or not end_vids:
            return []
        with_prop_clause = " WITH PROP" if with_prop else ""
        statement = (
            f'USE `{self.settings.space}`; '
            f'FIND SHORTEST PATH{with_prop_clause} FROM {self._format_vid_list(start_vids)} TO {self._format_vid_list(end_vids)} '
            f'OVER `relation` BIDIRECT UPTO {max(1, int(max_hops))} STEPS '
            f'YIELD path as p | LIMIT {max(1, int(limit))};'
        )
        return self.execute_rows(statement)

    def fetch_vertices_by_vids(self, vids: list[str]) -> dict[str, dict[str, Any]]:
        normalized = [str(item).strip() for item in vids if str(item).strip()]
        if not normalized:
            return {}
        statement = (
            f'USE `{self.settings.space}`; '
            f'FETCH PROP ON `entity` {self._format_vid_list(normalized)} '
            "YIELD id(vertex) AS vid, properties(vertex).name AS name, properties(vertex).entity_type AS entity_type;"
        )
        rows = self.execute_rows(statement)
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            vid = str(row.get("vid", "")).strip()
            if not vid:
                continue
            result[vid] = {
                "vid": vid,
                "name": str(row.get("name", "")).strip(),
                "entity_type": str(row.get("entity_type", "")).strip() or "entity",
            }
        return result

    def fetch_edges_by_refs(self, refs: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
        normalized: list[tuple[str, str, int]] = []
        for ref in refs:
            src = str(ref.get("src", "")).strip()
            dst = str(ref.get("dst", "")).strip()
            ranking = ref.get("ranking")
            if not src or not dst or ranking in (None, ""):
                continue
            normalized.append((src, dst, int(ranking)))
        if not normalized:
            return {}
        edge_expr = ",".join(f'"{src}"->"{dst}"@{ranking}' for src, dst, ranking in normalized)
        statement = (
            f'USE `{self.settings.space}`; '
            f'FETCH PROP ON `relation` {edge_expr} '
            "YIELD "
            "src(edge) AS src, "
            "dst(edge) AS dst, "
            "rank(edge) AS ranking, "
            "properties(edge).predicate AS predicate, "
            "properties(edge).source_book AS source_book, "
            "properties(edge).source_chapter AS source_chapter, "
            "properties(edge).fact_id AS fact_id, "
            "properties(edge).fact_ids AS fact_ids, "
            "properties(edge).source_text AS source_text, "
            "properties(edge).confidence AS confidence;"
        )
        rows = self.execute_rows(statement)
        result: dict[tuple[str, str, int], dict[str, Any]] = {}
        for row in rows:
            src = str(row.get("src", "")).strip()
            dst = str(row.get("dst", "")).strip()
            ranking = row.get("ranking")
            if not src or not dst or ranking in (None, ""):
                continue
            result[(src, dst, int(ranking))] = {
                "src": src,
                "dst": dst,
                "ranking": int(ranking),
                "predicate": str(row.get("predicate", "")).strip(),
                "source_book": str(row.get("source_book", "")).strip(),
                "source_chapter": str(row.get("source_chapter", "")).strip(),
                "fact_id": str(row.get("fact_id", "")).strip(),
                "fact_ids": self._parse_fact_ids(row.get("fact_ids")),
                "source_text": str(row.get("source_text", "")).strip(),
                "confidence": float(row.get("confidence", 0.0) or 0.0),
            }
        return result

    def exact_entity(self, entity_name: str) -> list[dict[str, Any]]:
        vid = entity_vid(entity_name, self.settings.vid_max_length)
        statement = (
            f'USE `{self.settings.space}`; '
            f'FETCH PROP ON `entity` "{vid}" '
            "YIELD "
            "properties(vertex).name AS name, "
            "properties(vertex).entity_type AS entity_type;"
        )
        rows = self.execute_rows(statement)
        return [row for row in rows if str(row.get("name", "")).strip()]

    def exact_entity_names(self, query: str, preferred_types: set[str] | None = None) -> list[str]:
        rows = self.exact_entity(query)
        names: list[str] = []
        preferred = {str(item).strip() for item in preferred_types or set() if str(item).strip()}
        for row in rows:
            name = str(row.get("name", "")).strip()
            entity_type = str(row.get("entity_type", "")).strip()
            if not name:
                continue
            if preferred and entity_type not in preferred:
                continue
            names.append(name)
        return names

    def alias_candidates(self, entity_name: str, *, preferred_types: set[str] | None = None, limit: int = 8) -> list[str]:
        preferred = [str(item).strip() for item in preferred_types or set() if str(item).strip()]
        names: list[str] = []
        seen: set[str] = set()
        for reverse in (False, True):
            rows = self.batch_neighbors(
                [entity_name],
                reverse=reverse,
                predicates=["别名"],
                target_types=preferred or None,
                limit_per_entity=max(1, limit),
            )
            for row in rows:
                neighbor_name = str(row.get("neighbor_name", "")).strip()
                if not neighbor_name or neighbor_name == entity_name or neighbor_name in seen:
                    continue
                seen.add(neighbor_name)
                names.append(neighbor_name)
                if len(names) >= max(1, limit):
                    return names
        return names

    def batch_exact_entities(self, entity_names: list[str]) -> dict[str, dict[str, Any]]:
        vid_map = self.fetch_vertices_by_vids(self._normalize_vid_inputs(entity_names))
        return {
            str(item.get("name", "")).strip(): item
            for item in vid_map.values()
            if str(item.get("name", "")).strip()
        }

    def execute_rows(self, statement: str) -> list[dict[str, Any]]:
        if not self.client_available():
            raise RuntimeError("nebula3-python not installed")

        with self._session() as session:  # pragma: no cover - runtime integration path
            if hasattr(session, "execute_json"):
                raw = session.execute_json(statement)
                return self._rows_from_execute_json(raw)

            result = session.execute(statement)
            if not result.is_succeeded():
                raise RuntimeError(result.error_msg())
            raise RuntimeError("nebula_execute_json_not_supported")

    def _rows_from_execute_json(self, payload: Any) -> list[dict[str, Any]]:
        text = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
        data = json.loads(text)

        errors = data.get("errors", [])
        if errors:
            first_error = errors[0]
            if int(first_error.get("code", 0)) != 0:
                raise RuntimeError(str(first_error.get("message", "nebula_query_failed")))

        results = data.get("results", [])
        rows: list[dict[str, Any]] = []
        for result in results:
            columns = [str(item) for item in result.get("columns", [])]
            for item in result.get("data", []):
                values = item.get("row", [])
                meta = item.get("meta", [])
                row = {
                    column: self._decode_value(value, meta_info=meta[index] if index < len(meta) else None)
                    for index, (column, value) in enumerate(zip(columns, values))
                }
                if row:
                    rows.append(row)
        return rows

    def _decode_value(self, value: Any, *, meta_info: Any = None) -> Any:
        if meta_info and isinstance(meta_info, list) and isinstance(value, list) and len(meta_info) == len(value):
            return [self._decode_value(item, meta_info=meta_info[index]) for index, item in enumerate(value)]
        if meta_info and isinstance(meta_info, dict):
            meta_type = str(meta_info.get("type", "")).strip().lower()
            if meta_type == "vertex":
                decoded = self._decode_value(value)
                if isinstance(decoded, dict):
                    decoded.setdefault("__kind", "vertex")
                    decoded.setdefault("vid", str(meta_info.get("id", "")).strip())
                    return decoded
                return {"__kind": "vertex", "vid": str(meta_info.get("id", "")).strip()}
            if meta_type == "edge":
                edge_id = meta_info.get("id", {}) or {}
                decoded = self._decode_value(value)
                payload = decoded if isinstance(decoded, dict) else {}
                payload.setdefault("__kind", "edge")
                payload.setdefault("src", str(edge_id.get("src", "")).strip())
                payload.setdefault("dst", str(edge_id.get("dst", "")).strip())
                ranking = edge_id.get("ranking")
                if ranking not in (None, ""):
                    payload.setdefault("ranking", int(ranking))
                payload.setdefault("edge_type", int(edge_id.get("type", 0) or 0))
                payload.setdefault("edge_name", str(edge_id.get("name", "")).strip())
                return payload
        if isinstance(value, dict):
            if "id" in value:
                return value["id"]
            if "value" in value:
                return value["value"]
            if "sVal" in value:
                return value["sVal"]
            if "nVal" in value:
                return value["nVal"]
            if "bVal" in value:
                return value["bVal"]
            if "fVal" in value:
                return value["fVal"]
            if "iVal" in value:
                return value["iVal"]
            if "path" in value:
                return value["path"]
            if "vertex" in value:
                return value["vertex"]
            if "edge" in value:
                return value["edge"]
            return {key: self._decode_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._decode_value(item) for item in value]
        return value

    def _session(self):
        if not self.client_available():  # pragma: no cover - import guarded above
            raise RuntimeError("nebula3-python not installed")
        pool = self._get_or_create_pool()
        session = pool.get_session(self.settings.user, self.settings.password)

        class _SessionContext:
            def __enter__(self_nonlocal):
                return session

            def __exit__(self_nonlocal, exc_type, exc, tb):
                session.release()

        return _SessionContext()

    def _get_or_create_pool(self):
        pool_key = (self.settings.host, self.settings.port)
        shared_pool = self.__class__._shared_pool
        if shared_pool is not None and self.__class__._shared_pool_key == pool_key:
            return shared_pool
        with self.__class__._pool_lock:
            shared_pool = self.__class__._shared_pool
            if shared_pool is not None and self.__class__._shared_pool_key == pool_key:
                return shared_pool
            config = NebulaConfig()
            config.max_connection_pool_size = 8
            pool = ConnectionPool()
            ok = pool.init([(self.settings.host, self.settings.port)], config)
            if not ok:
                raise RuntimeError("failed_to_init_nebula_connection_pool")
            self.__class__._shared_pool = pool
            self.__class__._shared_pool_key = pool_key
            return pool

    def _normalize_vid_inputs(self, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            normalized_items: list[str] = []
            for item in value:
                text = str(item).strip()
                if not text:
                    continue
                normalized_items.append(text if text.startswith("ent_") else entity_vid(text, self.settings.vid_max_length))
            return normalized_items
        normalized = str(value).strip()
        if not normalized:
            return []
        if normalized.startswith("ent_"):
            return [normalized]
        return [entity_vid(normalized, self.settings.vid_max_length)]

    def _format_vid_list(self, vids: list[str]) -> str:
        return ",".join(f'"{vid}"' for vid in vids if vid)

    def _format_string_list(self, values: list[str]) -> str:
        normalized = [f'"{_escape_ngql(str(item).strip())}"' for item in values if str(item).strip()]
        return "[" + ",".join(normalized) + "]"

    def _parse_fact_ids(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except Exception:
            return [item for item in text.split("\x1f") if item]
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]
        return [text]
