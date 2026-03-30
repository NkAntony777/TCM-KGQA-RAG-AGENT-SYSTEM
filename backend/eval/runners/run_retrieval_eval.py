from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "retrieval_smoke_8.json"
DEFAULT_ENDPOINT = "http://127.0.0.1:8102/api/v1/retrieval/search/hybrid"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset must be a JSON array")
    return payload


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = max(0.0, min(1.0, p)) * (len(values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _is_hit(item: dict[str, Any], chunks: list[dict[str, Any]]) -> bool:
    expected_ids = {str(value) for value in item.get("expected_any_chunk_ids", [])}
    expected_files = {str(value) for value in item.get("expected_any_source_files", [])}

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        chunk_id = str(chunk.get("chunk_id", ""))
        source_file = str(chunk.get("source_file") or chunk.get("filename") or "")
        if expected_ids and chunk_id in expected_ids:
            return True
        if expected_files and source_file in expected_files:
            return True
    return False


def evaluate_retrieval(
    *,
    dataset: list[dict[str, Any]],
    endpoint: str,
    top_k: int,
    candidate_k: int,
    timeout: float,
    enable_rerank: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    hit_count = 0

    with httpx.Client(timeout=timeout) as client:
        for item in dataset:
            payload = {
                "query": item["query"],
                "top_k": top_k,
                "candidate_k": candidate_k,
                "enable_rerank": enable_rerank,
            }
            started = time.perf_counter()
            response = client.post(endpoint, json=payload)
            latency_ms = (time.perf_counter() - started) * 1000
            latencies_ms.append(latency_ms)

            body = response.json()
            data = body.get("data", {}) if isinstance(body, dict) else {}
            chunks = data.get("chunks", []) if isinstance(data, dict) else []
            hit = response.status_code == 200 and _is_hit(item, chunks)
            if hit:
                hit_count += 1

            rows.append(
                {
                    "id": item.get("id"),
                    "query": item.get("query"),
                    "hit": hit,
                    "status_code": response.status_code,
                    "retrieval_mode": data.get("retrieval_mode"),
                    "top_chunk_ids": [chunk.get("chunk_id") for chunk in chunks[:top_k] if isinstance(chunk, dict)],
                    "top_source_files": [
                        chunk.get("source_file") or chunk.get("filename")
                        for chunk in chunks[:top_k]
                        if isinstance(chunk, dict)
                    ],
                    "warnings": data.get("warnings", []),
                    "latency_ms": round(latency_ms, 2),
                }
            )

    sorted_latencies = sorted(latencies_ms)
    total = len(dataset)
    return {
        "total": total,
        "hits": hit_count,
        "hit_at_k": round(hit_count / total, 4) if total else 0.0,
        "avg_latency_ms": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0.0,
        "p50_latency_ms": round(percentile(sorted_latencies, 0.50), 2),
        "p95_latency_ms": round(percentile(sorted_latencies, 0.95), 2),
        "top_k": top_k,
        "candidate_k": candidate_k,
        "enable_rerank": enable_rerank,
        "endpoint": endpoint,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S2 retrieval quality baseline against retrieval-service.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Retrieval eval dataset JSON.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Hybrid search endpoint.")
    parser.add_argument("--top-k", type=int, default=3, help="Returned top-k.")
    parser.add_argument("--candidate-k", type=int, default=9, help="Retrieved candidate count.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds.")
    parser.add_argument("--min-hit-rate", type=float, default=0.75, help="Minimum hit@k required for success.")
    parser.add_argument("--enable-rerank", action="store_true", help="Enable rerank during evaluation.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    summary = evaluate_retrieval(
        dataset=load_dataset(args.dataset),
        endpoint=args.endpoint,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        timeout=args.timeout,
        enable_rerank=args.enable_rerank,
    )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Dataset: {args.dataset}")
        print(f"Endpoint: {summary['endpoint']}")
        print(f"Hit@{summary['top_k']}: {summary['hits']}/{summary['total']} = {summary['hit_at_k']:.2%}")
        print(
            f"Latency: avg={summary['avg_latency_ms']:.2f}ms "
            f"p50={summary['p50_latency_ms']:.2f}ms p95={summary['p95_latency_ms']:.2f}ms"
        )
        misses = [item for item in summary["results"] if not item["hit"]]
        if misses:
            print("Misses:")
            for item in misses:
                print(
                    f"- {item['id']}: query={item['query']}, mode={item['retrieval_mode']}, "
                    f"top_chunk_ids={item['top_chunk_ids']}, warnings={item['warnings']}"
                )

    return 0 if summary["hit_at_k"] >= args.min_hit_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
