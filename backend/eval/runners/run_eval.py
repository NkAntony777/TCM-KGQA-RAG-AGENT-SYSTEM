from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from router.query_router import decide_route


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "router_smoke_20.json"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset must be a JSON array")
    return payload


def evaluate_router(dataset: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(dataset)
    correct = 0
    mismatches: list[dict[str, Any]] = []
    category_totals: Counter[str] = Counter()
    category_correct: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for item in dataset:
        query = str(item.get("query", "")).strip()
        expected = str(item.get("expected_route", "")).strip()
        category = str(item.get("category", expected)).strip() or expected
        decision = decide_route(query)

        category_totals[category] += 1
        confusion[expected][decision.route] += 1

        row = {
            "id": item.get("id"),
            "query": query,
            "expected_route": expected,
            "predicted_route": decision.route,
            "reason": decision.reason,
        }

        if decision.route == expected:
            correct += 1
            category_correct[category] += 1
        else:
            mismatches.append(row)

    accuracy = correct / total if total else 0.0
    category_accuracy = {
        category: round(category_correct[category] / count, 4)
        for category, count in category_totals.items()
        if count
    }

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "category_accuracy": category_accuracy,
        "mismatches": mismatches,
        "confusion": {key: dict(value) for key, value in confusion.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run smoke eval for the TCM query router.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to a JSON dataset containing query/expected_route rows.",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.8,
        help="Minimum accuracy threshold required for success.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the summary as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    summary = evaluate_router(dataset)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Dataset: {args.dataset}")
        print(f"Accuracy: {summary['correct']}/{summary['total']} = {summary['accuracy']:.2%}")
        print(f"Category accuracy: {json.dumps(summary['category_accuracy'], ensure_ascii=False)}")
        print(f"Confusion: {json.dumps(summary['confusion'], ensure_ascii=False)}")
        if summary["mismatches"]:
            print("Mismatches:")
            for item in summary["mismatches"]:
                print(
                    f"- {item['id']}: expected={item['expected_route']}, "
                    f"predicted={item['predicted_route']}, query={item['query']}, reason={item['reason']}"
                )

    return 0 if summary["accuracy"] >= args.min_accuracy else 1


if __name__ == "__main__":
    sys.exit(main())
