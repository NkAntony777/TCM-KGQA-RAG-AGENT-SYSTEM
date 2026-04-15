from __future__ import annotations

import argparse
from pathlib import Path

from eval.ablations._common import BACKEND_ROOT, load_dataset, render_simple_table, write_outputs
from router.retrieval_strategy import derive_retrieval_strategy
from services.graph_service.engine import get_graph_engine
from services.retrieval_service.engine import get_retrieval_engine


DEFAULT_DATASET = BACKEND_ROOT / "eval" / "datasets" / "graph_first_relation_8.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation: graph-first relation retrieval vs text-first files-first retrieval.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "graph_first_vs_text_first_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent.parent / "docs" / "Graph_First_vs_Text_First_Ablation_Latest.md")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    graph_engine = get_graph_engine()
    retrieval_engine = get_retrieval_engine()
    rows = []
    graph_hits = 0
    text_hits = 0
    for case in dataset:
        query = str(case.get("query", "")).strip()
        strategy = derive_retrieval_strategy(query, requested_top_k=args.top_k, route_hint="hybrid")
        graph_result = graph_engine.entity_lookup(
            str(case.get("entity", "")).strip(),
            top_k=args.top_k,
            predicate_allowlist=[str(item).strip() for item in (case.get("predicate_allowlist", []) or []) if str(item).strip()],
        )
        graph_predicates = {str(item.get("predicate", "")).strip() for item in graph_result.get("relations", []) if isinstance(item, dict)}
        graph_targets = {str(item.get("target", "")).strip() for item in graph_result.get("relations", []) if isinstance(item, dict)}
        graph_ok = bool(graph_predicates.intersection(case.get("expected_predicates_any", [])) or graph_targets.intersection(case.get("expected_targets_any", [])))
        if graph_ok:
            graph_hits += 1

        retrieval_result = retrieval_engine.search_hybrid(
            query=query,
            top_k=args.top_k,
            candidate_k=max(args.top_k * 2, 12),
            enable_rerank=False,
            search_mode="files_first",
        )
        text_blob = "\n".join(str(item.get("text", "")) for item in (retrieval_result.get("chunks", []) or []) if isinstance(item, dict))
        expected_tokens = [str(item).strip() for item in (case.get("expected_targets_any", []) or []) if str(item).strip()]
        text_ok = any(token in text_blob for token in expected_tokens)
        if text_ok:
            text_hits += 1

        rows.append(
            [
                case.get("id"),
                strategy.preferred_route,
                graph_ok,
                text_ok,
                len(graph_result.get("relations", []) or []),
                retrieval_result.get("total", 0),
            ]
        )
        print(f"[graph-first-vs-text-first] {case.get('id')} preferred={strategy.preferred_route} graph_ok={graph_ok} text_ok={text_ok}", flush=True)

    payload = {
        "dataset": str(args.dataset),
        "graph_hit_rate": round(graph_hits / max(len(dataset), 1), 4),
        "text_hit_rate": round(text_hits / max(len(dataset), 1), 4),
        "rows": rows,
    }
    markdown = render_simple_table(
        "Graph-First vs Text-First Ablation",
        [("dataset", args.dataset), ("graph_hit_rate", f"{payload['graph_hit_rate']:.2%}"), ("text_hit_rate", f"{payload['text_hit_rate']:.2%}")],
        ["ID", "preferred_route", "graph_ok", "text_ok", "graph_relations", "text_hits"],
        rows,
    )
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=markdown)


if __name__ == "__main__":
    main()
