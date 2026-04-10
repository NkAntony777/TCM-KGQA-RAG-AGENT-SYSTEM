from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.common.evidence_payloads import normalize_book_label
from services.graph_service.engine import GraphQueryEngine, get_graph_engine


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "graph_regression_12.json"
DEFAULT_OUTPUT_JSON = BACKEND_ROOT / "eval" / "graph_regression_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_ROOT.parent.parent / "docs" / "Graph_Regression_Latest.md"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset must be a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def select_cases(dataset: list[dict[str, Any]], *, include_heavy: bool) -> list[dict[str, Any]]:
    if include_heavy:
        return dataset
    return [item for item in dataset if str(item.get("lane", "fast")).strip().lower() != "heavy"]


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _normalize_books(values: list[str]) -> set[str]:
    return {normalize_book_label(value) for value in values if str(value).strip()}


def _ranked_entity_lookup(
    engine: GraphQueryEngine,
    *,
    entity: str,
    query_text: str,
    top_k: int,
    predicate_allowlist: list[str] | None = None,
    predicate_blocklist: list[str] | None = None,
) -> dict[str, Any]:
    inner_engine = getattr(engine, "fallback_engine", engine)
    candidates = inner_engine._resolve_entities(entity)  # noqa: SLF001
    if not candidates:
        return {"entity": {}, "relations": [], "total": 0}
    canonical_name = candidates[0]
    relations = inner_engine._select_relation_clusters(  # noqa: SLF001
        inner_engine._filter_relations(  # noqa: SLF001
            inner_engine._collect_relations(canonical_name),  # noqa: SLF001
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        ),
        query_text=query_text,
        top_k=max(1, top_k),
    )
    return {
        "entity": {
            "name": entity,
            "canonical_name": canonical_name,
            "entity_type": inner_engine.entity_type(canonical_name),
        },
        "relations": relations,
        "total": len(relations),
    }


def _evaluate_entity_lookup(case: dict[str, Any], engine: GraphQueryEngine) -> dict[str, Any]:
    result = _ranked_entity_lookup(
        engine,
        entity=str(case.get("entity", "")).strip(),
        query_text=str(case.get("query", "")).strip(),
        top_k=int(case.get("top_k", 6) or 6),
        predicate_allowlist=[str(item).strip() for item in (case.get("predicate_allowlist", []) or []) if str(item).strip()],
        predicate_blocklist=[str(item).strip() for item in (case.get("predicate_blocklist", []) or []) if str(item).strip()],
    )
    relations = result.get("relations", []) if isinstance(result.get("relations"), list) else []
    predicates = {str(item.get("predicate", "")).strip() for item in relations if isinstance(item, dict)}
    targets = {str(item.get("target", "")).strip() for item in relations if isinstance(item, dict)}
    books = _normalize_books(
        [str(item.get("source_book", "")).strip() for item in relations if isinstance(item, dict)]
    )
    issues: list[str] = []

    expected_predicates_any = {str(item).strip() for item in (case.get("expected_predicates_any", []) or []) if str(item).strip()}
    expected_targets_any = {str(item).strip() for item in (case.get("expected_targets_any", []) or []) if str(item).strip()}
    expected_books_any = _normalize_books([str(item).strip() for item in (case.get("expected_source_books_any", []) or []) if str(item).strip()])

    if expected_predicates_any and not predicates.intersection(expected_predicates_any):
        issues.append("predicate_missing_any:" + "|".join(sorted(expected_predicates_any)))
    if expected_targets_any and not targets.intersection(expected_targets_any):
        issues.append("target_missing_any:" + "|".join(sorted(expected_targets_any)))
    if expected_books_any and not books.intersection(expected_books_any):
        issues.append("source_book_missing_any:" + "|".join(sorted(expected_books_any)))

    return {
        "id": case.get("id", ""),
        "category": case.get("category", "entity_lookup"),
        "kind": "entity_lookup",
        "passed": not issues,
        "issues": issues,
        "entity": result.get("entity", {}),
        "predicates": sorted(predicates),
        "targets": sorted(list(targets))[:10],
        "books": sorted(books),
        "total": int(result.get("total", 0) or 0),
    }


def _evaluate_resolve_entity(case: dict[str, Any], engine: GraphQueryEngine) -> dict[str, Any]:
    preferred_types = {str(item).strip() for item in (case.get("preferred_types", []) or []) if str(item).strip()}
    inner_engine = getattr(engine, "fallback_engine", engine)
    entities = inner_engine._resolve_entities(str(case.get("query", "")).strip(), preferred_types=preferred_types or None)  # noqa: SLF001
    expected_entities_any = {str(item).strip() for item in (case.get("expected_entities_any", []) or []) if str(item).strip()}
    issues: list[str] = []
    if expected_entities_any and not expected_entities_any.intersection(entities):
        issues.append("entity_missing_any:" + "|".join(sorted(expected_entities_any)))
    return {
        "id": case.get("id", ""),
        "category": case.get("category", "entity_resolution"),
        "kind": "resolve_entity",
        "passed": not issues,
        "issues": issues,
        "resolved_entities": entities[:10],
    }


def _evaluate_path_query(case: dict[str, Any], engine: GraphQueryEngine) -> dict[str, Any]:
    result = engine.path_query(
        str(case.get("start", "")).strip(),
        str(case.get("end", "")).strip(),
        max_hops=int(case.get("max_hops", 3) or 3),
        path_limit=int(case.get("path_limit", 3) or 3),
    )
    path_nodes: set[str] = set()
    for item in result.get("paths", []) if isinstance(result.get("paths"), list) else []:
        if isinstance(item, dict):
            path_nodes.update(str(node).strip() for node in (item.get("nodes", []) or []) if str(node).strip())
    expected_any = {str(item).strip() for item in (case.get("expected_path_nodes_any", []) or []) if str(item).strip()}
    issues: list[str] = []
    if expected_any and not expected_any.intersection(path_nodes):
        issues.append("path_node_missing_any:" + "|".join(sorted(expected_any)))
    if int(result.get("total", 0) or 0) <= 0:
        issues.append("path_total_zero")
    return {
        "id": case.get("id", ""),
        "category": case.get("category", "path_quality"),
        "kind": "path_query",
        "passed": not issues,
        "issues": issues,
        "total": int(result.get("total", 0) or 0),
        "path_nodes": sorted(path_nodes),
    }


def _evaluate_syndrome_chain(case: dict[str, Any], engine: GraphQueryEngine) -> dict[str, Any]:
    result = engine.syndrome_chain(str(case.get("symptom", "")).strip(), top_k=int(case.get("top_k", 5) or 5))
    syndromes = {
        str(item.get("name", "")).strip()
        for item in (result.get("syndromes", []) or [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    expected_any = {str(item).strip() for item in (case.get("expected_syndromes_any", []) or []) if str(item).strip()}
    issues: list[str] = []
    if expected_any and not expected_any.intersection(syndromes):
        issues.append("syndrome_missing_any:" + "|".join(sorted(expected_any)))
    return {
        "id": case.get("id", ""),
        "category": case.get("category", "syndrome_chain"),
        "kind": "syndrome_chain",
        "passed": not issues,
        "issues": issues,
        "syndromes": sorted(syndromes),
    }


def evaluate_graph_regression(dataset: list[dict[str, Any]]) -> dict[str, Any]:
    engine = get_graph_engine()
    results: list[dict[str, Any]] = []
    for case in dataset:
        kind = str(case.get("kind", "")).strip()
        if kind == "resolve_entity":
            results.append(_evaluate_resolve_entity(case, engine))
        elif kind == "entity_lookup":
            results.append(_evaluate_entity_lookup(case, engine))
        elif kind == "path_query":
            results.append(_evaluate_path_query(case, engine))
        elif kind == "syndrome_chain":
            results.append(_evaluate_syndrome_chain(case, engine))
        else:
            results.append(
                {
                    "id": case.get("id", ""),
                    "category": case.get("category", "unknown"),
                    "kind": kind or "unknown",
                    "passed": False,
                    "issues": [f"unsupported_kind:{kind or 'missing'}"],
                }
            )

    failures = [item for item in results if not item.get("passed")]
    issue_counter = Counter()
    by_category: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[str(item.get("category", "unknown"))].append(item)
        for issue in item.get("issues", []) or []:
            issue_counter[str(issue)] += 1
    for category, items in grouped.items():
        by_category[category] = {
            "total": len(items),
            "failed": sum(1 for item in items if not item.get("passed")),
        }

    return {
        "generated_at": _utc_now_text(),
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "top_issues": issue_counter.most_common(20),
        "by_category": by_category,
        "failures": failures,
        "results": results,
    }


def render_markdown(summary: dict[str, Any], *, dataset_path: Path, include_heavy: bool) -> str:
    lines = [
        "# Graph Regression Report",
        "",
        f"- dataset: `{dataset_path}`",
        f"- include_heavy: `{str(include_heavy).lower()}`",
        f"- generated_at: `{summary['generated_at']}`",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| total | {summary['total']} |",
        f"| passed | {summary['passed']} |",
        f"| failed | {summary['failed']} |",
        "",
        "## By Category",
        "",
        "| Category | Total | Failed |",
        "| --- | ---: | ---: |",
    ]
    for category, item in sorted(summary.get("by_category", {}).items()):
        lines.append(f"| {category} | {item.get('total', 0)} | {item.get('failed', 0)} |")
    lines.extend(
        [
            "",
            "## Top Issues",
            "",
        ]
    )
    top_issues = summary.get("top_issues", []) or []
    if top_issues:
        for issue, count in top_issues:
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Failures",
            "",
        ]
    )
    failures = summary.get("failures", []) or []
    if failures:
        for item in failures[:20]:
            lines.append(
                f"- {item.get('id', '-')}"
                f" [{item.get('kind', '-')}]"
                f" issues={','.join(str(x) for x in (item.get('issues', []) or [])) or '-'}"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run graph regression against the local graph engine.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--include-heavy", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    selected_cases = select_cases(load_dataset(args.dataset), include_heavy=args.include_heavy)
    summary = evaluate_graph_regression(selected_cases)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(summary, dataset_path=args.dataset, include_heavy=args.include_heavy), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"passed={summary['passed']}/{summary['total']}")
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
