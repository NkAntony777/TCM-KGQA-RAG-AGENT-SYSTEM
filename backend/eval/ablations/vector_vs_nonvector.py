from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from eval.ablations._common import (
    BACKEND_ROOT,
    load_dataset,
    render_simple_table,
    safe_request_case,
    start_backend,
    stop_backend,
    wait_health,
    write_outputs,
)


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "qa_weakness_probe_12.json"


def _run_condition(*, label: str, env_overrides: dict[str, str], dataset: list[dict[str, Any]], top_k: int, timeout_s: int, port: int) -> dict[str, Any]:
    proc = start_backend(
        port=port,
        env_overrides=env_overrides,
        stdout_path=BACKEND_ROOT / "eval" / "ablations" / f"{label}.out.log",
        stderr_path=BACKEND_ROOT / "eval" / "ablations" / f"{label}.err.log",
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        if not wait_health(base_url, timeout_s=90):
            return {"label": label, "failed": len(dataset) * 2, "passed": 0, "avg_latency_ms": 0.0, "fallback_rate": 0.0, "rows": []}
        rows: list[dict[str, Any]] = []
        for case in dataset:
            query = str(case.get("query", "")).strip()
            if not query:
                continue
            for mode in ("quick", "deep"):
                row = safe_request_case(base_url=base_url, query=query, mode=mode, top_k=top_k, timeout_s=timeout_s)
                data = row.get("data", {}) if row.get("ok") else {}
                result = {
                    "id": case.get("id"),
                    "mode": mode,
                    "ok": bool(row.get("ok")),
                    "latency_ms": float(row.get("latency_ms", 0.0) or 0.0),
                    "status": data.get("status", "request_error"),
                    "generation_backend": data.get("generation_backend", ""),
                    "fallback": "fallback" in str(data.get("generation_backend", "")).lower() or any("fallback" in str(note).lower() for note in (data.get("notes", []) or [])),
                    "answer_len": len(str(data.get("answer", "") or "")),
                }
                rows.append(result)
                print(f"[vector-vs-nonvector] {label} {case.get('id')}[{mode}] ok={result['ok']} latency={result['latency_ms']:.1f}ms fallback={result['fallback']}", flush=True)
        avg_latency = round(sum(item["latency_ms"] for item in rows) / max(len(rows), 1), 1)
        passed = sum(1 for item in rows if item["ok"])
        failed = len(rows) - passed
        fallback_rate = round(sum(1 for item in rows if item["fallback"]) / max(len(rows), 1), 4)
        return {
            "label": label,
            "passed": passed,
            "failed": failed,
            "avg_latency_ms": avg_latency,
            "fallback_rate": fallback_rate,
            "rows": rows,
        }
    finally:
        stop_backend(proc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation: vector-first compatibility path vs non-vector primary path.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--port-base", type=int, default=8012)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "vector_vs_nonvector_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent.parent / "docs" / "Vector_vs_NonVector_Ablation_Latest.md")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    vector_on = _run_condition(
        label="vector_compat_on",
        env_overrides={
            "RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED": "true",
            "FILES_FIRST_DENSE_FALLBACK_ENABLED": "true",
            "CASE_QA_VECTOR_FALLBACK_ENABLED": "true",
        },
        dataset=dataset,
        top_k=args.top_k,
        timeout_s=args.timeout,
        port=args.port_base,
    )
    vector_off = _run_condition(
        label="vector_compat_off",
        env_overrides={
            "RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED": "false",
            "FILES_FIRST_DENSE_FALLBACK_ENABLED": "false",
            "CASE_QA_VECTOR_FALLBACK_ENABLED": "false",
        },
        dataset=dataset,
        top_k=args.top_k,
        timeout_s=args.timeout,
        port=args.port_base + 1,
    )
    payload = {
        "dataset": str(args.dataset),
        "vector_on": vector_on,
        "vector_off": vector_off,
    }
    markdown = render_simple_table(
        "Vector vs Non-Vector Ablation",
        [("dataset", args.dataset), ("total_cases_x_modes", len(dataset) * 2)],
        ["Condition", "passed", "failed", "avg_latency_ms", "fallback_rate"],
        [
            ["vector_compat_on", vector_on["passed"], vector_on["failed"], vector_on["avg_latency_ms"], vector_on["fallback_rate"]],
            ["vector_compat_off", vector_off["passed"], vector_off["failed"], vector_off["avg_latency_ms"], vector_off["fallback_rate"]],
        ],
    )
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=markdown)


if __name__ == "__main__":
    main()
