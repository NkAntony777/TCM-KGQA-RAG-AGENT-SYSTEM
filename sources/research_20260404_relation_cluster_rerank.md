# Relation Cluster Rerank Research Notes

Date: 2026-04-04

## Objective

Improve graph relation `top_k` selection so results are simultaneously:

- relevant to the current question
- backed by stronger evidence
- covered by more source books
- diversified across relation types instead of being dominated by repeated edges

## Key References

1. Carbonell, Goldstein. *The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries*. SIGIR 1998.
   Link: https://sigmod.org/publications/dblp/db/conf/sigir/CarbonellG98.html
   Takeaway: ranking should balance relevance with novelty to reduce redundancy.

2. Santos et al. *Explicit Search Result Diversification through Sub-queries* (xQuAD). ECIR 2010.
   Link: https://www.sciweavers.org/publications/explicit-search-result-diversification-through-sub-queries
   Takeaway: diversified ranking should explicitly cover different aspects of a query. In this project, `predicate` is the natural aspect boundary.

3. Elastic official docs. *Reciprocal rank fusion*.
   Link: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
   Takeaway: when multiple ranking signals exist but are not directly comparable, `RRF` is a stable engineering choice for fusion.

4. Qdrant official docs. *Maximal Marginal Relevance (MMR)*.
   Link: https://qdrant.tech/documentation/concepts/search-relevance/
   Takeaway: MMR is production-viable for reranking redundant candidate sets, with an explicit relevance/diversity tradeoff.

## Design Mapping To This Project

- MMR maps to:
  relation-cluster reranking after basic relevance estimation
- xQuAD maps to:
  predicate coverage in early `top_k` slots
- RRF maps to:
  fusion of query-intent match, evidence quality, source coverage, and predicate priority

## Implementation Decision

Use a three-step pipeline:

1. Cluster raw edges by `(predicate, target, direction)`.
2. Aggregate support statistics for each cluster:
   `evidence_count`, `source_book_count`, `avg_confidence`, `max_confidence`.
3. Rank with `RRF`, then apply a greedy diversity pass that prefers uncovered predicates in early positions.

## Expected Benefit

- small `top_k` no longer gets filled by repeated herb edges
- `功效 / 治疗证候 / 使用药材 / 治疗症状` can co-exist in the first page of evidence
- downstream answer generation receives richer and less redundant context
