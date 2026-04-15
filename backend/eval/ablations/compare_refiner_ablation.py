from __future__ import annotations

import argparse
from pathlib import Path

from eval.ablations._common import BACKEND_ROOT, load_dataset, render_simple_table, write_outputs
from router.tcm_intent_classifier import analyze_tcm_query
from router.retrieval_strategy import derive_retrieval_strategy


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "compare_refiner_8.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation for compare entity refinement.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "compare_refiner_ablation_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent.parent / "docs" / "Compare_Refiner_Ablation_Latest.md")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    rows = []
    exact_before = 0
    exact_after = 0
    noise_reduced = 0
    for case in dataset:
        query = str(case.get("query", "")).strip()
        analysis = analyze_tcm_query(query)
        raw_compare = analysis.compare_entities()
        strategy = derive_retrieval_strategy(query, requested_top_k=12, route_hint="hybrid", analysis=analysis)
        refined = strategy.compare_entities
        expected = [str(item).strip() for item in case.get("expected_compare_entities", []) if str(item).strip()] if isinstance(case.get("expected_compare_entities", []), list) else []
        if raw_compare == expected:
            exact_before += 1
        if refined == expected:
            exact_after += 1
        if len(refined) <= len(raw_compare):
            noise_reduced += 1
        rows.append([case.get("id"), raw_compare, refined, expected, len(raw_compare), len(refined)])
        print(f"[compare-refiner] {case.get('id')} raw={raw_compare} refined={refined}", flush=True)

    payload = {
        "dataset": str(args.dataset),
        "exact_before_rate": round(exact_before / max(len(dataset), 1), 4),
        "exact_after_rate": round(exact_after / max(len(dataset), 1), 4),
        "noise_reduced_rate": round(noise_reduced / max(len(dataset), 1), 4),
        "rows": rows,
    }
    markdown = render_simple_table(
        "Compare Refiner Ablation",
        [("dataset", args.dataset), ("exact_before_rate", f"{payload['exact_before_rate']:.2%}"), ("exact_after_rate", f"{payload['exact_after_rate']:.2%}"), ("noise_reduced_rate", f"{payload['noise_reduced_rate']:.2%}")],
        ["ID", "raw_compare", "refined_compare", "expected", "raw_n", "refined_n"],
        rows,
    )
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=markdown)


if __name__ == "__main__":
    main()
