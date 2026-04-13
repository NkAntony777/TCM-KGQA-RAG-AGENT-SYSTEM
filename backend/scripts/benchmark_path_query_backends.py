from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT.parent / "docs"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@dataclass
class PathBenchmarkCase:
    id: str
    lane: str
    start: str
    end: str
    max_hops: int
    path_limit: int
    expected_nodes_any: list[str]


@dataclass
class PathBenchmarkResult:
    case_id: str
    lane: str
    backend: str
    status: str
    mean_ms: float | None
    median_ms: float | None
    runs: int
    timeout_s: int
    total: int | None
    first_hops: int | None
    quality_ok: bool
    first_nodes: list[str]
    warning: str = ""


CASES: list[PathBenchmarkCase] = [
    PathBenchmarkCase(
        id="light_001",
        lane="light",
        start="熟地黄",
        end="六味地黄汤",
        max_hops=2,
        path_limit=3,
        expected_nodes_any=["熟地黄", "六味地黄汤"],
    ),
    PathBenchmarkCase(
        id="light_002",
        lane="light",
        start="附子",
        end="少阴病",
        max_hops=2,
        path_limit=3,
        expected_nodes_any=["附子", "少阴病"],
    ),
    PathBenchmarkCase(
        id="light_003",
        lane="light",
        start="人参",
        end="脾胃气虚",
        max_hops=3,
        path_limit=3,
        expected_nodes_any=["人参", "脾胃气虚"],
    ),
    PathBenchmarkCase(
        id="light_004",
        lane="light",
        start="四君子汤",
        end="六味地黄丸",
        max_hops=3,
        path_limit=3,
        expected_nodes_any=["四君子汤", "六味地黄丸"],
    ),
    PathBenchmarkCase(
        id="heavy_001",
        lane="heavy",
        start="熟地黄",
        end="真阴亏损",
        max_hops=4,
        path_limit=3,
        expected_nodes_any=["熟地黄", "真阴亏损", "六味地黄汤", "六味地黄丸"],
    ),
    PathBenchmarkCase(
        id="heavy_002",
        lane="heavy",
        start="黄芪",
        end="虚风内动",
        max_hops=5,
        path_limit=3,
        expected_nodes_any=["黄芪", "虚风内动", "三甲复脉汤"],
    ),
    PathBenchmarkCase(
        id="heavy_003",
        lane="heavy",
        start="桂枝",
        end="虚风内动",
        max_hops=5,
        path_limit=3,
        expected_nodes_any=["桂枝", "虚风内动", "三甲复脉汤", "复脉汤"],
    ),
    PathBenchmarkCase(
        id="heavy_004",
        lane="heavy",
        start="附子",
        end="虚风内动",
        max_hops=5,
        path_limit=3,
        expected_nodes_any=["附子", "虚风内动", "三甲复脉汤"],
    ),
]


def _quality_ok(result: dict[str, Any], expected_nodes_any: list[str]) -> bool:
    paths = result.get("paths") or []
    if not isinstance(paths, list) or not paths:
        return False
    expected = {str(item).strip() for item in expected_nodes_any if str(item).strip()}
    if not expected:
        return True
    flattened: set[str] = set()
    for path in paths:
        flattened.update(str(item).strip() for item in path.get("nodes", []) if str(item).strip())
    return bool(flattened & expected)


def _worker(backend: str, case_payload: dict[str, Any], iterations: int, queue: Any) -> None:
    from services.graph_service.engine import GraphQueryEngine
    from services.graph_service.engine import NebulaPrimaryGraphEngine

    case = PathBenchmarkCase(**case_payload)
    try:
        if backend == "sqlite_local":
            engine = GraphQueryEngine()

            def run_once() -> dict[str, Any]:
                return engine.path_query(case.start, case.end, max_hops=case.max_hops, path_limit=case.path_limit)

        elif backend == "nebula_direct":
            engine = NebulaPrimaryGraphEngine()
            start_candidates = engine.fallback_engine._resolve_entities(case.start, exact_only=True)[:3]  # noqa: SLF001
            end_candidates = engine.fallback_engine._resolve_entities(case.end, exact_only=True)[:3]  # noqa: SLF001

            def run_once() -> dict[str, Any]:
                return engine._direct_path_query_via_nebula(  # noqa: SLF001
                    start_candidates=start_candidates,
                    end_candidates=end_candidates,
                    max_hops=case.max_hops,
                    path_limit=case.path_limit,
                )

        else:
            raise ValueError(f"unsupported_backend:{backend}")

        # Warm up once without recording.
        run_once()

        timings: list[float] = []
        last_result: dict[str, Any] = {}
        for _ in range(max(1, iterations)):
            start_at = time.perf_counter()
            last_result = run_once()
            timings.append((time.perf_counter() - start_at) * 1000)

        first_nodes = []
        first_hops = None
        if isinstance(last_result.get("paths"), list) and last_result["paths"]:
            first_nodes = [str(item).strip() for item in last_result["paths"][0].get("nodes", []) if str(item).strip()]
            if first_nodes:
                first_hops = len(first_nodes) - 1

        queue.put(
            asdict(
                PathBenchmarkResult(
                    case_id=case.id,
                    lane=case.lane,
                    backend=backend,
                    status="ok",
                    mean_ms=round(statistics.mean(timings), 2),
                    median_ms=round(statistics.median(timings), 2),
                    runs=len(timings),
                    timeout_s=0,
                    total=int(last_result.get("total", 0) or 0),
                    first_hops=first_hops,
                    quality_ok=_quality_ok(last_result, case.expected_nodes_any),
                    first_nodes=first_nodes,
                )
            )
        )
    except Exception as exc:
        queue.put(
            asdict(
                PathBenchmarkResult(
                    case_id=case.id,
                    lane=case.lane,
                    backend=backend,
                    status="error",
                    mean_ms=None,
                    median_ms=None,
                    runs=0,
                    timeout_s=0,
                    total=None,
                    first_hops=None,
                    quality_ok=False,
                    first_nodes=[],
                    warning=str(exc),
                )
            )
        )


def _run_case(backend: str, case: PathBenchmarkCase, iterations: int, timeout_s: int) -> PathBenchmarkResult:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=_worker, args=(backend, asdict(case), iterations, queue))
    process.start()
    process.join(timeout=timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        return PathBenchmarkResult(
            case_id=case.id,
            lane=case.lane,
            backend=backend,
            status="timeout",
            mean_ms=None,
            median_ms=None,
            runs=0,
            timeout_s=timeout_s,
            total=None,
            first_hops=None,
            quality_ok=False,
            first_nodes=[],
            warning=f"timed out after {timeout_s}s",
        )
    if queue.empty():
        return PathBenchmarkResult(
            case_id=case.id,
            lane=case.lane,
            backend=backend,
            status="error",
            mean_ms=None,
            median_ms=None,
            runs=0,
            timeout_s=timeout_s,
            total=None,
            first_hops=None,
            quality_ok=False,
            first_nodes=[],
            warning="worker returned no payload",
        )
    return PathBenchmarkResult(**queue.get())


def _render_markdown(results: list[PathBenchmarkResult], output_json: Path) -> str:
    by_case: dict[str, list[PathBenchmarkResult]] = {}
    for row in results:
        by_case.setdefault(row.case_id, []).append(row)

    lines = [
        "# Path Query Backend Benchmark",
        "",
        f"- JSON artifact: `{output_json}`",
        "- Scope: compare current SQLite local path_query against Nebula direct shortest-path on the same real-world cases.",
        "- Metrics: latency, timeout behavior, first-path hop count, and minimal path-quality coverage.",
        "",
        "## Summary Table",
        "",
        "| Case | Lane | Backend | Status | Mean ms | Median ms | Total | First hops | Quality | First nodes | Warning |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            f"| {row.case_id} | {row.lane} | {row.backend} | {row.status} | "
            f"{'' if row.mean_ms is None else f'{row.mean_ms:.2f}'} | "
            f"{'' if row.median_ms is None else f'{row.median_ms:.2f}'} | "
            f"{'' if row.total is None else row.total} | "
            f"{'' if row.first_hops is None else row.first_hops} | "
            f"{'yes' if row.quality_ok else 'no'} | "
            f"{' -> '.join(row.first_nodes[:6])} | {row.warning} |"
        )

    lines.extend(["", "## Case-Level Comparison", ""])
    for case_id, rows in by_case.items():
        lines.append(f"### {case_id}")
        for row in rows:
            lines.append(
                f"- `{row.backend}`: status={row.status}, mean_ms={row.mean_ms}, total={row.total}, "
                f"first_hops={row.first_hops}, quality_ok={row.quality_ok}, warning={row.warning or '-'}"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--timeout-light", type=int, default=45)
    parser.add_argument("--timeout-heavy", type=int, default=90)
    parser.add_argument(
        "--output-json",
        default=str(BACKEND_DIR / "eval" / "path_query_backend_benchmark_latest.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(DOCS_DIR / "Path_Query_Backend_Benchmark_20260413.md"),
    )
    args = parser.parse_args()

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    results: list[PathBenchmarkResult] = []
    total_steps = len(CASES) * 2
    step = 0
    for case in CASES:
        timeout_s = args.timeout_heavy if case.lane == "heavy" else args.timeout_light
        for backend in ("sqlite_local", "nebula_direct"):
            step += 1
            print(f"[{step}/{total_steps}] {backend} {case.id} {case.start} -> {case.end} (timeout={timeout_s}s)", flush=True)
            results.append(_run_case(backend, case, iterations=args.iterations, timeout_s=timeout_s))

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "path_query_execution_mode": os.getenv("PATH_QUERY_EXECUTION_MODE", "local_first"),
        "iterations": args.iterations,
        "results": [asdict(row) for row in results],
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_render_markdown(results, output_json), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "md": str(output_md), "rows": len(results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
