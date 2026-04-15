from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT.parent / "docs"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@dataclass
class GraphBackendCase:
    id: str
    kind: str
    query: str
    entity: str = ""
    symptom: str = ""
    top_k: int = 5
    predicate_allowlist: list[str] = field(default_factory=list)
    predicate_blocklist: list[str] = field(default_factory=list)
    expected_predicates_any: list[str] = field(default_factory=list)
    expected_targets_any: list[str] = field(default_factory=list)
    acceptable_targets_any: list[str] = field(default_factory=list)
    expected_source_books_any: list[str] = field(default_factory=list)
    expected_syndromes_any: list[str] = field(default_factory=list)
    acceptable_syndromes_any: list[str] = field(default_factory=list)


@dataclass
class GraphBackendResult:
    case_id: str
    kind: str
    backend: str
    status: str
    mean_ms: float | None
    median_ms: float | None
    runs: int
    timeout_s: int
    total: int | None
    score: float
    quality_ok: bool
    preview: str
    warning: str = ""


DEFAULT_DATASET = BACKEND_DIR / "eval" / "datasets" / "graph_backend_entity_relation_9.json"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "graph_entity_relation_backend_benchmark_latest.json"
DEFAULT_OUTPUT_MD = DOCS_DIR / "Graph_Entity_Relation_Backend_Benchmark_Latest.md"


def _load_cases(path: Path) -> list[GraphBackendCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset_must_be_list")
    cases: list[GraphBackendCase] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cases.append(GraphBackendCase(**item))
    return cases


def _normalize_relation_row_from_nebula(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": str(row.get("neighbor_name", "")).strip(),
        "target_type": str(row.get("neighbor_type", "")).strip() or "other",
        "predicate": str(row.get("predicate", "")).strip(),
        "source_book": str(row.get("source_book", "")).strip(),
        "source_chapter": str(row.get("source_chapter", "")).strip(),
        "fact_id": str(row.get("fact_id", "")).strip(),
        "fact_ids": list(row.get("fact_ids", [])) if isinstance(row.get("fact_ids"), list) else [],
        "source_text": str(row.get("source_text", "")).strip(),
        "confidence": float(row.get("confidence", 0.0) or 0.0),
    }


def _run_entity_lookup_sqlite(engine: Any, case: GraphBackendCase) -> dict[str, Any]:
    return engine.entity_lookup(
        case.entity or case.query,
        top_k=max(1, case.top_k),
        predicate_allowlist=case.predicate_allowlist or None,
        predicate_blocklist=case.predicate_blocklist or None,
    )


def _run_entity_lookup_nebula(engine: Any, case: GraphBackendCase) -> dict[str, Any]:
    return engine.entity_lookup(
        case.entity or case.query,
        top_k=max(1, case.top_k),
        predicate_allowlist=case.predicate_allowlist or None,
        predicate_blocklist=case.predicate_blocklist or None,
    )


def _run_syndrome_chain_sqlite(engine: Any, case: GraphBackendCase) -> dict[str, Any]:
    return engine.syndrome_chain(case.symptom, top_k=max(1, case.top_k))


def _run_syndrome_chain_nebula(engine: Any, case: GraphBackendCase) -> dict[str, Any]:
    return engine.syndrome_chain(case.symptom, top_k=max(1, case.top_k))


def _evaluate_entity_lookup(case: GraphBackendCase, result: dict[str, Any]) -> tuple[float, bool, str]:
    relations = result.get("relations", []) if isinstance(result.get("relations"), list) else []
    predicates = {str(item.get("predicate", "")).strip() for item in relations}
    targets = {str(item.get("target", "")).strip() for item in relations}
    source_books: set[str] = set()
    for relation in relations:
        source_books.update(str(item).strip() for item in relation.get("source_books", []) if str(item).strip())
        source_book = str(relation.get("source_book", "")).strip()
        if source_book:
            source_books.add(source_book)

    checks = 0
    hits = 0
    if case.expected_predicates_any:
        checks += 1
        hits += int(bool(predicates & set(case.expected_predicates_any)))
    if case.expected_targets_any:
        checks += 1
        hits += int(bool(targets & set(case.expected_targets_any)))
    elif case.acceptable_targets_any:
        checks += 1
        hits += int(bool(targets & set(case.acceptable_targets_any)))
    elif case.expected_targets_any or case.acceptable_targets_any:
        checks += 1
    if case.expected_targets_any and not (targets & set(case.expected_targets_any)) and case.acceptable_targets_any:
        hits += int(bool(targets & set(case.acceptable_targets_any)))
    if case.expected_source_books_any:
        checks += 1
        hits += int(bool(source_books & set(case.expected_source_books_any)))
    score = round(min(float(hits), float(checks or 1)) / float(checks or 1), 2)
    preview = "-"
    if relations:
        top = relations[0]
        preview = f"{top.get('predicate', '-')}: {top.get('target', '-')}"
    return score, score >= 1.0 if checks > 0 else bool(relations), preview


def _evaluate_syndrome_chain(case: GraphBackendCase, result: dict[str, Any]) -> tuple[float, bool, str]:
    syndromes = result.get("syndromes", []) if isinstance(result.get("syndromes"), list) else []
    names = {str(item.get("name", "")).strip() for item in syndromes}
    checks = 1 if (case.expected_syndromes_any or case.acceptable_syndromes_any) else 0
    hits = 0
    if case.expected_syndromes_any and (names & set(case.expected_syndromes_any)):
        hits = 1
    elif case.acceptable_syndromes_any and (names & set(case.acceptable_syndromes_any)):
        hits = 1
    score = round(float(hits) / float(checks or 1), 2)
    preview = "-"
    if syndromes:
        top = syndromes[0]
        preview = f"{top.get('name', '-')}"
    return score, score >= 1.0 if checks > 0 else bool(syndromes), preview


def _worker(backend: str, case_payload: dict[str, Any], iterations: int, queue: Any) -> None:
    from services.graph_service.engine import GraphQueryEngine
    from services.graph_service.engine import NebulaPrimaryGraphEngine
    from services.graph_service.engine import SYMPTOM_RELATIONS
    from services.graph_service.nebulagraph_store import NebulaGraphStore

    case = GraphBackendCase(**case_payload)
    try:
        sqlite_engine = GraphQueryEngine()
        nebula_engine = NebulaPrimaryGraphEngine(
            primary_store=NebulaGraphStore(),
            fallback_engine=sqlite_engine,
        )
        setattr(sqlite_engine, "SYMPTOM_RELATIONS", SYMPTOM_RELATIONS)
        setattr(nebula_engine, "SYMPTOM_RELATIONS", SYMPTOM_RELATIONS)

        if backend == "sqlite_direct" and case.kind == "entity_lookup":
            run_once = lambda: _run_entity_lookup_sqlite(sqlite_engine, case)
        elif backend == "nebula_direct" and case.kind == "entity_lookup":
            run_once = lambda: _run_entity_lookup_nebula(nebula_engine, case)
        elif backend == "sqlite_direct" and case.kind == "syndrome_chain":
            run_once = lambda: _run_syndrome_chain_sqlite(sqlite_engine, case)
        elif backend == "nebula_direct" and case.kind == "syndrome_chain":
            run_once = lambda: _run_syndrome_chain_nebula(nebula_engine, case)
        else:
            raise ValueError(f"unsupported_case_or_backend:{case.kind}:{backend}")

        run_once()

        timings: list[float] = []
        last_result: dict[str, Any] = {}
        for _ in range(max(1, iterations)):
            started = time.perf_counter()
            last_result = run_once()
            timings.append((time.perf_counter() - started) * 1000.0)

        if case.kind == "entity_lookup":
            score, quality_ok, preview = _evaluate_entity_lookup(case, last_result)
        else:
            score, quality_ok, preview = _evaluate_syndrome_chain(case, last_result)

        total = None
        if case.kind == "entity_lookup":
            total = int(last_result.get("total", 0) or 0)
        elif case.kind == "syndrome_chain":
            syndromes = last_result.get("syndromes", []) if isinstance(last_result.get("syndromes"), list) else []
            total = len(syndromes)

        queue.put(
            asdict(
                GraphBackendResult(
                    case_id=case.id,
                    kind=case.kind,
                    backend=backend,
                    status="ok",
                    mean_ms=round(statistics.mean(timings), 2),
                    median_ms=round(statistics.median(timings), 2),
                    runs=len(timings),
                    timeout_s=0,
                    total=total,
                    score=score,
                    quality_ok=quality_ok,
                    preview=preview,
                )
            )
        )
    except Exception as exc:
        queue.put(
            asdict(
                GraphBackendResult(
                    case_id=case.id,
                    kind=case.kind,
                    backend=backend,
                    status="error",
                    mean_ms=None,
                    median_ms=None,
                    runs=0,
                    timeout_s=0,
                    total=None,
                    score=0.0,
                    quality_ok=False,
                    preview="-",
                    warning=str(exc),
                )
            )
        )


def _prepare_engines() -> tuple[Any, Any]:
    from services.graph_service.engine import GraphQueryEngine
    from services.graph_service.engine import NebulaPrimaryGraphEngine
    from services.graph_service.engine import SYMPTOM_RELATIONS
    from services.graph_service.nebulagraph_store import NebulaGraphStore

    sqlite_engine = GraphQueryEngine()
    nebula_engine = NebulaPrimaryGraphEngine(
        primary_store=NebulaGraphStore(),
        fallback_engine=sqlite_engine,
    )
    setattr(sqlite_engine, "SYMPTOM_RELATIONS", SYMPTOM_RELATIONS)
    setattr(nebula_engine, "SYMPTOM_RELATIONS", SYMPTOM_RELATIONS)
    return sqlite_engine, nebula_engine


def _execute_once(backend: str, case: GraphBackendCase, sqlite_engine: Any, nebula_engine: Any) -> dict[str, Any]:
    if backend == "sqlite_direct" and case.kind == "entity_lookup":
        return _run_entity_lookup_sqlite(sqlite_engine, case)
    if backend == "nebula_direct" and case.kind == "entity_lookup":
        return _run_entity_lookup_nebula(nebula_engine, case)
    if backend == "sqlite_direct" and case.kind == "syndrome_chain":
        return _run_syndrome_chain_sqlite(sqlite_engine, case)
    if backend == "nebula_direct" and case.kind == "syndrome_chain":
        return _run_syndrome_chain_nebula(nebula_engine, case)
    raise ValueError(f"unsupported_case_or_backend:{case.kind}:{backend}")


def _run_case_in_process(
    backend: str,
    case: GraphBackendCase,
    iterations: int,
    sqlite_engine: Any,
    nebula_engine: Any,
) -> GraphBackendResult:
    try:
        _execute_once(backend, case, sqlite_engine, nebula_engine)
        timings: list[float] = []
        last_result: dict[str, Any] = {}
        for _ in range(max(1, iterations)):
            started = time.perf_counter()
            last_result = _execute_once(backend, case, sqlite_engine, nebula_engine)
            timings.append((time.perf_counter() - started) * 1000.0)

        if case.kind == "entity_lookup":
            score, quality_ok, preview = _evaluate_entity_lookup(case, last_result)
            total = int(last_result.get("total", 0) or 0)
        else:
            score, quality_ok, preview = _evaluate_syndrome_chain(case, last_result)
            syndromes = last_result.get("syndromes", []) if isinstance(last_result.get("syndromes"), list) else []
            total = len(syndromes)

        return GraphBackendResult(
            case_id=case.id,
            kind=case.kind,
            backend=backend,
            status="ok",
            mean_ms=round(statistics.mean(timings), 2),
            median_ms=round(statistics.median(timings), 2),
            runs=len(timings),
            timeout_s=0,
            total=total,
            score=score,
            quality_ok=quality_ok,
            preview=preview,
        )
    except Exception as exc:
        return GraphBackendResult(
            case_id=case.id,
            kind=case.kind,
            backend=backend,
            status="error",
            mean_ms=None,
            median_ms=None,
            runs=0,
            timeout_s=0,
            total=None,
            score=0.0,
            quality_ok=False,
            preview="-",
            warning=str(exc),
        )


def _run_case(backend: str, case: GraphBackendCase, iterations: int, timeout_s: int) -> GraphBackendResult:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=_worker, args=(backend, asdict(case), iterations, queue))
    process.start()
    process.join(timeout=timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        return GraphBackendResult(
            case_id=case.id,
            kind=case.kind,
            backend=backend,
            status="timeout",
            mean_ms=None,
            median_ms=None,
            runs=0,
            timeout_s=timeout_s,
            total=None,
            score=0.0,
            quality_ok=False,
            preview="-",
            warning=f"timed out after {timeout_s}s",
        )
    if queue.empty():
        return GraphBackendResult(
            case_id=case.id,
            kind=case.kind,
            backend=backend,
            status="error",
            mean_ms=None,
            median_ms=None,
            runs=0,
            timeout_s=timeout_s,
            total=None,
            score=0.0,
            quality_ok=False,
            preview="-",
            warning="worker_returned_no_payload",
        )
    return GraphBackendResult(**queue.get())


def _aggregate(rows: list[GraphBackendResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[GraphBackendResult]] = {}
    for row in rows:
        grouped.setdefault((row.kind, row.backend), []).append(row)
    payload: list[dict[str, Any]] = []
    for (kind, backend), items in sorted(grouped.items()):
        ok_items = [item for item in items if item.status == "ok" and item.mean_ms is not None]
        payload.append(
            {
                "kind": kind,
                "backend": backend,
                "cases": len(items),
                "ok_cases": len(ok_items),
                "quality_ok_cases": sum(1 for item in items if item.quality_ok),
                "avg_mean_ms": round(statistics.mean([float(item.mean_ms) for item in ok_items]), 2) if ok_items else None,
                "avg_score": round(statistics.mean([float(item.score) for item in items]), 2) if items else 0.0,
            }
        )
    return payload


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Graph Entity/Relation Backend Benchmark",
        "",
        "## Fairness Rules",
        "",
        "1. SQLite and Nebula use the same case set, same `top_k`, same allow/block predicates, same warmup, and same iteration count.",
        "2. Entity resolution is shared: both backends use the same local canonical resolver before backend-specific relation fetch.",
        "3. Relation annotation, governance filtering, clustering, ranking, and final quality checks are shared post-processing logic.",
        "4. For `syndrome_chain`, both backends use the same symptom candidate resolver and same final scoring/dedup logic; only raw relation fetch differs.",
        "5. This benchmark therefore compares backend fetch capability, not differences caused by unrelated planner or prompt behavior.",
        "",
        "## Aggregate",
        "",
        "| kind | backend | cases | ok_cases | quality_ok_cases | avg_mean_ms | avg_score |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["aggregate"]:
        lines.append(
            f"| {row['kind']} | {row['backend']} | {row['cases']} | {row['ok_cases']} | {row['quality_ok_cases']} | {row['avg_mean_ms']} | {row['avg_score']} |"
        )
    lines.extend(
        [
            "",
            "## Per Case",
            "",
            "| case_id | kind | backend | status | mean_ms | median_ms | total | score | quality_ok | preview | warning |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary["results"]:
        lines.append(
            f"| {row['case_id']} | {row['kind']} | {row['backend']} | {row['status']} | {row['mean_ms']} | {row['median_ms']} | {row['total']} | {row['score']} | {row['quality_ok']} | {row['preview']} | {row['warning'] or '-'} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark SQLite vs Nebula for entity lookup and syndrome chain under fair shared conditions.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--runner", choices=("spawn", "inproc"), default="spawn")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    cases = _load_cases(args.dataset)
    results: list[GraphBackendResult] = []
    sqlite_engine = None
    nebula_engine = None
    if args.runner == "inproc":
        sqlite_engine, nebula_engine = _prepare_engines()
    for case in cases:
        for backend in ("sqlite_direct", "nebula_direct"):
            if args.runner == "inproc":
                result = _run_case_in_process(
                    backend,
                    case,
                    iterations=max(1, args.iterations),
                    sqlite_engine=sqlite_engine,
                    nebula_engine=nebula_engine,
                )
            else:
                result = _run_case(backend, case, iterations=max(1, args.iterations), timeout_s=max(10, args.timeout))
            results.append(result)
            print(
                f"[graph-backend-bench] {case.id} {case.kind} {backend} "
                f"status={result.status} mean_ms={result.mean_ms} score={result.score} preview={result.preview}",
                flush=True,
            )

    summary = {
        "dataset": str(args.dataset),
        "iterations": max(1, args.iterations),
        "timeout_s": max(10, args.timeout),
        "runner": args.runner,
        "results": [asdict(item) for item in results],
        "aggregate": _aggregate(results),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps({"output_json": str(args.output_json), "output_md": str(args.output_md)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
