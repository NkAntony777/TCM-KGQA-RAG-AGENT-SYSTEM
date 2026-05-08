from __future__ import annotations

from services.graph_service.fallback_adapter import LocalGraphFallbackAdapter
from services.graph_service.nebula_primary_engine import NebulaPrimaryGraphEngine


class FakeStore:
    def first_edge_between(self, left: str, right: str) -> dict[str, object]:
        return {"left": left, "right": right}

    def source_book_exists(self, source_book: str) -> bool:
        return source_book == "伤寒论"


class FakeEngine:
    def __init__(self) -> None:
        self.store = FakeStore()

    def health(self) -> dict[str, object]:
        return {"status": "ok", "backend": "fake_graph"}

    def entity_lookup(self, name: str, top_k: int = 12, predicate_allowlist=None, predicate_blocklist=None) -> dict[str, object]:
        return {
            "entity": {"name": name},
            "top_k": top_k,
            "predicate_allowlist": predicate_allowlist,
            "predicate_blocklist": predicate_blocklist,
        }

    def path_query(self, start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, object]:
        return {"start": start, "end": end, "max_hops": max_hops, "path_limit": path_limit}

    def syndrome_chain(self, symptom: str, top_k: int = 5) -> dict[str, object]:
        return {"symptom": symptom, "top_k": top_k}

    def _resolve_entities(self, query: str, preferred_types=None, *, exact_only: bool = False) -> list[str]:
        return [f"{query}:{exact_only}:{sorted(preferred_types or [])}"]

    def entity_type(self, entity_name: str) -> str:
        return f"type:{entity_name}"

    def _annotate_relation_rows(self, rows, *, anchor_entity_type: str):
        return [dict(row, anchor_entity_type=anchor_entity_type) for row in rows]

    def _filter_relations(self, rows, *, predicate_allowlist=None, predicate_blocklist=None):
        return list(rows)

    def _select_relation_clusters(self, rows, *, query_text: str, top_k: int):
        return list(rows)[:top_k]

    def _collect_recommended_formulas(self, syndrome_node: str):
        return [f"formula:{syndrome_node}"]

    def _fast_path_candidates(self, *, start_candidates, end_candidates, max_hops: int, path_limit: int):
        return {"paths": [[start_candidates, end_candidates, max_hops]], "total": 1, "path_limit": path_limit}

    def _build_path_payload(self, nodes):
        return {"nodes": nodes}

    def _edge_evidence_payload(self, edge_data):
        return {"fact_id": edge_data.get("fact_id", "f1")}

    def _query_fragments(self, query_text: str):
        return [query_text]

    def _query_mentions_source_book(self, query_text: str, source_book: str):
        return source_book in query_text


def test_local_graph_fallback_adapter_exposes_public_fallback_boundary() -> None:
    adapter = LocalGraphFallbackAdapter(FakeEngine())

    assert adapter.health() == {"status": "ok", "backend": "fake_graph"}
    assert adapter.entity_lookup("逍遥散", top_k=3, predicate_allowlist=["功效"]) == {
        "entity": {"name": "逍遥散"},
        "top_k": 3,
        "predicate_allowlist": ["功效"],
        "predicate_blocklist": None,
    }
    assert adapter.path_query("柴胡", "肝郁", max_hops=2, path_limit=4) == {
        "start": "柴胡",
        "end": "肝郁",
        "max_hops": 2,
        "path_limit": 4,
    }
    assert adapter.syndrome_chain("胁痛", top_k=2) == {"symptom": "胁痛", "top_k": 2}
    assert adapter.resolve_entities("逍遥散", {"formula"}, exact_only=True) == ["逍遥散:True:['formula']"]
    assert adapter.entity_type("逍遥散") == "type:逍遥散"
    assert adapter.annotate_relation_rows([{"predicate": "治疗证候"}], anchor_entity_type="formula")[0]["anchor_entity_type"] == "formula"
    assert adapter.select_relation_clusters([{"id": 1}, {"id": 2}], query_text="q", top_k=1) == [{"id": 1}]
    assert adapter.collect_recommended_formulas("肝郁脾虚") == ["formula:肝郁脾虚"]
    assert adapter.build_path_payload(["A", "B"]) == {"nodes": ["A", "B"]}
    assert adapter.first_edge_between("A", "B") == {"left": "A", "right": "B"}
    assert adapter.source_book_exists("伤寒论")
    assert adapter.query_fragments("小柴胡汤") == ["小柴胡汤"]
    assert adapter.query_mentions_source_book("伤寒论 小柴胡汤", "伤寒论")


def test_nebula_primary_accepts_protocol_fallback_without_private_engine_methods() -> None:
    class DisabledPrimaryStore:
        def health(self):
            return {"status": "disabled"}

        def ready(self) -> bool:
            return False

    class ProtocolOnlyFallback:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def health(self):
            self.calls.append("health")
            return {"status": "ok", "backend": "protocol_graph", "graph_path": "local.db"}

        def entity_lookup(self, name: str, *, top_k: int = 12, predicate_allowlist=None, predicate_blocklist=None):
            self.calls.append("entity_lookup")
            return {"entity": {"name": name}, "relations": [], "total": 0, "top_k": top_k}

        def path_query(self, start: str, end: str, *, max_hops: int = 3, path_limit: int = 5):
            self.calls.append("path_query")
            return {"paths": [], "total": 0, "max_hops": max_hops, "path_limit": path_limit}

        def syndrome_chain(self, symptom: str, *, top_k: int = 5):
            self.calls.append("syndrome_chain")
            return {"symptom": symptom, "syndromes": [], "top_k": top_k}

        def resolve_entities(self, query: str, preferred_types=None, *, exact_only: bool = False):
            self.calls.append("resolve_entities")
            return []

        def entity_type(self, entity_name: str) -> str:
            return "other"

        def annotate_relation_rows(self, rows, *, anchor_entity_type: str):
            return list(rows)

        def filter_relations(self, rows, *, predicate_allowlist=None, predicate_blocklist=None):
            return list(rows)

        def select_relation_clusters(self, rows, *, query_text: str, top_k: int):
            return list(rows)[:top_k]

        def collect_recommended_formulas(self, syndrome_node: str):
            return []

        def fast_path_candidates(self, *, start_candidates, end_candidates, max_hops: int, path_limit: int):
            return {"paths": [], "total": 0}

        def build_path_payload(self, nodes):
            return None

        def edge_evidence_payload(self, edge_data):
            return {}

        def first_edge_between(self, left: str, right: str):
            return None

        def source_book_exists(self, source_book: str) -> bool:
            return False

        def query_fragments(self, query_text: str):
            return [query_text]

        def query_mentions_source_book(self, query_text: str, source_book: str) -> bool:
            return False

    fallback = ProtocolOnlyFallback()
    engine = NebulaPrimaryGraphEngine(primary_store=DisabledPrimaryStore(), fallback=fallback)

    assert engine.health()["active_backend"] == "sqlite_fallback"
    assert engine.entity_lookup("逍遥散", top_k=2)["top_k"] == 2
    assert engine.path_query("柴胡", "肝郁", max_hops=2, path_limit=4)["path_limit"] == 4
    assert engine.syndrome_chain("胁痛", top_k=3)["top_k"] == 3
    assert fallback.calls == [
        "health",
        "entity_lookup",
        "resolve_entities",
        "resolve_entities",
        "path_query",
        "syndrome_chain",
    ]
