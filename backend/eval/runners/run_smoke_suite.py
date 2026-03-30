from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eval.runners.run_eval import DEFAULT_DATASET, evaluate_router, load_dataset


DEFAULT_HEALTH_ENDPOINTS = {
    "main_backend": "http://127.0.0.1:8002/health",
    "graph_service": "http://127.0.0.1:8101/api/v1/graph/health",
    "retrieval_service": "http://127.0.0.1:8102/api/v1/retrieval/health",
}


def check_health(endpoints: dict[str, str], timeout: float) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    with httpx.Client(timeout=timeout) as client:
        for name, url in endpoints.items():
            try:
                response = client.get(url)
                ok = response.status_code == 200
                payload: Any
                try:
                    payload = response.json()
                except Exception:
                    payload = response.text
                summary[name] = {
                    "ok": ok,
                    "status_code": response.status_code,
                    "url": url,
                    "payload": payload,
                }
            except Exception as exc:
                summary[name] = {
                    "ok": False,
                    "status_code": None,
                    "url": url,
                    "error": str(exc),
                }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run health checks and router smoke eval.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to smoke dataset JSON.",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.8,
        help="Minimum router accuracy threshold.",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=3.0,
        help="Per-request timeout in seconds for health checks.",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip HTTP health checks and only run router smoke eval.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print suite summary as JSON.",
    )
    args = parser.parse_args()

    route_summary = evaluate_router(load_dataset(args.dataset))
    health_summary = {} if args.skip_health else check_health(DEFAULT_HEALTH_ENDPOINTS, args.health_timeout)

    all_health_ok = all(item.get("ok") for item in health_summary.values()) if health_summary else True
    passed = all_health_ok and route_summary["accuracy"] >= args.min_accuracy

    summary = {
        "passed": passed,
        "health": health_summary,
        "router_eval": route_summary,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if health_summary:
            print("Health checks:")
            for name, item in health_summary.items():
                state = "OK" if item.get("ok") else "FAIL"
                extra = item.get("error") or item.get("payload")
                print(f"- {name}: {state} ({item.get('url')}) -> {extra}")
        print(
            "Router smoke: "
            f"{route_summary['correct']}/{route_summary['total']} = {route_summary['accuracy']:.2%}"
        )
        if route_summary["mismatches"]:
            print("Router mismatches:")
            for item in route_summary["mismatches"]:
                print(
                    f"- {item['id']}: expected={item['expected_route']}, "
                    f"predicted={item['predicted_route']}, query={item['query']}"
                )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
