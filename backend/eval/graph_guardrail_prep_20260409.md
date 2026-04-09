# Lane D graph minimal guardrail prep — 2026-04-09

## Scope

- Goal: identify the smallest safe graph hot-path guardrails for the next patch.
- Non-goal: do **not** start a deep graph rewrite.
- Constraint: preserve current route/evidence/trace observability (`final_route`, `executed_routes`, `service_trace_ids`, `tool_trace`, evidence payload shape).

## Concrete evidence from current code

### 1) Path expansion still uses list FIFO with `pop(0)`

- `backend/services/graph_service/engine.py:178-213`
- `backend/services/graph_service/engine.py:622-660`

Both SQLite and Nebula-primary path search use:

- `queue: list[list[str]] = [[start_node]]`
- `current_path = queue.pop(0)`

This is the first low-risk hotspot because it adds repeated O(n) queue churn on broader graph neighborhoods without changing result semantics.

### 2) Current dedupe is path-signature-only, not frontier/state based

- `backend/services/graph_service/engine.py:186-210`
- `backend/services/graph_service/engine.py:633-657`

The code only tracks `seen_signatures: set[tuple[str, ...]]`. That prevents exact duplicate paths, but it does **not** stop the same node from being expanded again at the same-or-worse depth through multiple parents. On high-fanout graph regions this is the main reason path search can do extra work before `path_limit` is reached.

### 3) Route layer hardcodes small path-query limits and depends on graph result shape

- `backend/tools/tcm_route_tool.py:108-125`
- `backend/tools/tcm_route_tool.py:186-250`

The route tool currently calls graph path search with:

- `max_hops=3`
- `path_limit=max(1, min(strategy.graph_final_k, 5))`

This means any guardrail patch must keep the returned payload compatible with current routing/fallback decisions. We should optimize internal expansion without changing the route contract.

### 4) Predicate-scoped entity lookups are already part of routing guarantees

- `backend/router/retrieval_strategy.py:132-145`
- `backend/tests/test_graph_engine.py:137-145`
- `backend/tests/test_tcm_router_smoke.py:317-339`

Composition / efficacy / indication queries already rely on `predicate_allowlist`. Any graph-side guardrail should avoid widening those entity lookup results again.

### 5) Relation ranking already has a stable weighting surface

- `backend/services/graph_service/engine.py:47-63`
- `backend/services/graph_service/engine.py:354-404`

Current entity-lookup ranking already combines:

- predicate base priority
- query hint match
- confidence
- source-book coverage
- evidence count

So if we introduce a path-query fanout cap, the safest follow-up is a **small** path-local adjacency ordering tweak, not a global ranking rewrite.

## Minimal patch set recommended next

### Patch A — replace list queue with `collections.deque`

Apply in both:

- `GraphQueryEngine.path_query`
- `NebulaPrimaryGraphEngine.path_query`

Why first:

- zero route-contract change
- deterministic behavior can be preserved
- directly removes avoidable queue churn

### Patch B — add frontier guard keyed by `(node, depth)` or best-known depth

Goal:

- stop re-expanding the same node at equal-or-worse depth
- still allow distinct terminal paths when they genuinely improve depth or reach target quickly

Recommended shape:

- keep `seen_signatures` for duplicate path suppression
- add `best_depth_by_node: dict[str, int]`
- only enqueue `next_node` when the new depth is strictly better than the best recorded depth, or when `next_node` is a target

This is the highest-value “minimal” guardrail after `deque`.

### Patch C — cap path-query adjacency fanout only inside path search

Do **not** cap entity lookup globally.

Safer target:

- cap neighbors consumed by `path_query` after local ordering
- example initial cap: 24 or 32 neighbors per expanded node

Why path-local only:

- keeps entity lookup evidence breadth unchanged
- isolates behavior change to the hot BFS-like expansion path

### Patch D — if fanout cap is introduced, add a small path-local ordering preference

Only if needed after Patch C.

Prefer edges whose predicates are more likely to bridge reasoning:

- `推荐方剂`
- `治疗证候`
- `常见症状`
- `功效`
- `使用药材`

This should be path-query-local ordering, not a broad change to entity lookup cluster ranking.

## Changes explicitly **not** recommended in the next patch

- no deep rewrite of graph storage APIs
- no change to `final_route` / fallback semantics
- no widening of default retrieval back toward dense/vector-first
- no global cache with cross-request staleness risk
- no route-level increase to `max_hops`

## Regression surface to keep green

### Graph engine

- `backend/tests/test_graph_engine.py`
  - `test_lookup_predicate_allowlist_supports_intent_scoped_retrieval`
  - `test_herb_to_syndrome_via_formula`
  - `test_herb_to_formula_direct`
  - `test_formula_to_formula_returns_empty_or_indirect`
  - `test_unreachable_entities_return_empty`

### Router / service-client contract

- `backend/tests/test_tcm_router_smoke.py`
  - `test_composition_query_uses_filtered_entity_lookup_strategy`
  - path-query routing smoke coverage
- `backend/tests/test_tcm_service_client.py`
  - sidecar fallback behavior for graph lookup / path behavior

### QA evidence consumers

- `backend/tests/test_qa_service.py`
  - graph-path payload exposure
  - path-reasoning coverage acceptance
- `backend/tests/test_tcm_evidence_tools.py`
  - graph path / source chapter evidence normalization

## Suggested verification plan for the actual guardrail patch

1. `pytest tests/test_graph_engine.py -q`
2. `pytest tests/test_tcm_router_smoke.py tests/test_tcm_service_client.py -q`
3. `pytest tests/test_tcm_evidence_tools.py tests/test_qa_service.py -q`
4. one targeted live/manual check for a graph-path-style query to confirm `final_route`, `executed_routes`, and evidence payload stay stable

## Current status

Task 4 prep is ready for implementation handoff:

- hotspots identified
- smallest safe patch order identified
- regression surface enumerated
- no deep rewrite started
