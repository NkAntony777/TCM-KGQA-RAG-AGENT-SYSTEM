from __future__ import annotations

import argparse
from pathlib import Path

from eval.ablations._common import BACKEND_ROOT, load_dataset, render_simple_table, write_outputs
from services.qa_service.evidence_coverage import _coverage_summary_from_state, _init_coverage_state, _update_coverage_state
from services.qa_service.engine import QAService


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "coverage_facet_6.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation for facet-aware coverage vs legacy-like coverage.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "coverage_facets_ablation_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent.parent / "docs" / "Coverage_Facets_Ablation_Latest.md")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    service = QAService()
    rows = []
    current_sufficient = 0
    legacy_sufficient = 0
    for case in dataset:
        query = str(case.get("query", "")).strip()
        payload = service._load_route_payload(query=query, top_k=12)
        context = service._prepare_route_context(query=query, top_k=12, include_executed_routes=True, payload=payload)
        state = _init_coverage_state(query=query, payload=payload, evidence_paths=payload.get("evidence_paths", []))
        _update_coverage_state(state, new_factual_evidence=context.factual_evidence, new_case_references=context.case_references)
        current = _coverage_summary_from_state(state)
        legacy_state = dict(state)
        legacy_state["requested_facets"] = set()
        legacy_state["_coverage_dirty"] = True
        legacy_state["_cached_gaps"] = None
        legacy_state["_cached_summary"] = None
        legacy = _coverage_summary_from_state(legacy_state)
        if current.get("sufficient"):
            current_sufficient += 1
        if legacy.get("sufficient"):
            legacy_sufficient += 1
        rows.append([case.get("id"), sorted(state.get("requested_facets", set())), current.get("gaps"), legacy.get("gaps"), current.get("sufficient"), legacy.get("sufficient")])
        print(f"[coverage-facets] {case.get('id')} current={current.get('gaps')} legacy={legacy.get('gaps')}", flush=True)

    payload = {
        "dataset": str(args.dataset),
        "current_sufficient_rate": round(current_sufficient / max(len(dataset), 1), 4),
        "legacy_sufficient_rate": round(legacy_sufficient / max(len(dataset), 1), 4),
        "rows": rows,
    }
    markdown = render_simple_table(
        "Coverage Facets Ablation",
        [("dataset", args.dataset), ("current_sufficient_rate", f"{payload['current_sufficient_rate']:.2%}"), ("legacy_sufficient_rate", f"{payload['legacy_sufficient_rate']:.2%}")],
        ["ID", "requested_facets", "current_gaps", "legacy_gaps", "current_sufficient", "legacy_sufficient"],
        rows,
    )
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=markdown)


if __name__ == "__main__":
    main()
