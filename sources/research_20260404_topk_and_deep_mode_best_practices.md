# Top-K Strategy And Deep Mode Research Notes

Date: 2026-04-04

## Scope

Research-backed best practices for:

- graph relation `top_k` selection
- relation deduplication and diversification
- deep-mode agentic retrieval architecture
- structured retrieval planning instead of unconstrained agent search

## Primary References

1. Carbonell, Goldstein. *The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries*. SIGIR 1998.
   Link: https://sigmod.org/publications/dblp/db/conf/sigir/CarbonellG98.html
   Why it matters:
   MMR is the canonical relevance-vs-diversity reranking method. It is well-suited to repeated graph edges and repeated evidence snippets.

2. Santos, Peng, Macdonald, Ounis. *Explicit Search Result Diversification through Sub-queries (xQuAD)*. ECIR 2010.
   Link: https://www.researchgate.net/publication/221397267_Explicit_Search_Result_Diversification_through_Sub-queries
   Why it matters:
   xQuAD treats a query as having multiple aspects and rewards coverage across aspects. In this project, `predicate` is the most natural aspect boundary.

3. Elastic official docs. *Reciprocal rank fusion*.
   Link: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
   Why it matters:
   RRF is a strong engineering choice when combining heterogeneous ranking signals without forcing them into one calibrated score space.

4. Qdrant official docs. *Search Relevance / Maximal Marginal Relevance*.
   Link: https://qdrant.tech/documentation/concepts/search-relevance/
   Why it matters:
   Confirms MMR is production-viable and explicitly meant for redundant candidate sets.

5. LangChain official docs. *Retrieval*.
   Link: https://docs.langchain.com/oss/python/langchain/retrieval
   Why it matters:
   Distinguishes 2-step RAG, Agentic RAG, and Hybrid RAG. This maps cleanly to this project’s quick mode and deep mode split.

6. LangChain official docs. *Router*.
   Link: https://docs.langchain.com/oss/python/langchain/multi-agent/router
   Why it matters:
   Recommends routing when input categories are clear and specialized tools exist. This matches TCM QA better than a free-form agent for every query.

7. LangChain official docs. *SelfQueryRetriever*.
   Link: https://reference.langchain.com/python/langchain-classic/retrievers/self_query/base/SelfQueryRetriever
   Why it matters:
   Validates the pattern of turning natural-language questions into structured retrieval parameters. In this project, that means entity, predicate, source, and evidence constraints.

8. Azure AI Search official docs. *Agentic retrieval*.
   Link: https://learn.microsoft.com/en-us/azure/search/search-get-started-agentic-retrieval?pivots=rest
   Why it matters:
   Emphasizes decomposition of complex questions into subqueries, parallel execution against knowledge sources, and synthesized citation-backed responses.

## Conclusions

### 1. Top-K should not be treated as one scalar knob

Best practice is to separate:

- candidate window size
- final output size
- per-intent filtered size

Recommended shape:

- `candidate_k`: wider, for recall
- `final_k`: smaller, for answer context

### 2. Deep mode should not use raw diversified top-k blindly

The agent should first infer retrieval intent and produce structured constraints, then run retrieval under those constraints.

For example:

- question: "六味地黄丸的组成是什么"
- retrieval plan:
  - entity = `六味地黄丸`
  - predicates = [`使用药材`]
  - graph strategy = evidence-heavy, low diversity across predicates, allow higher `top_k`

### 3. Best architecture is hybrid, not pure free-form agent

Recommended stack:

1. lightweight router / planner
2. specialized retrieval tools
3. optional iterative refinement if evidence is insufficient
4. grounded synthesis with citations

This is more stable than letting a general agent improvise every retrieval step.

### 4. For graph retrieval, predicate coverage is the right diversification unit

The graph is not a normal vector corpus. The main redundancy source is repeated edges of the same semantic class.

So diversification should primarily target:

- predicate coverage
- target deduplication inside the same predicate
- source-book coverage for trust

## Practical Design Recommendation

### Quick Mode

- deterministic pipeline
- no general agent loop
- default `final_k = 12`
- use relation-cluster aggregation plus diversified reranking

### Deep Mode

- planner/router first
- planner outputs structured retrieval strategy
- specialized retrieval tools execute
- retrieval can be retried if evidence is weak or coverage is incomplete
- synthesis step must cite evidence

### Suggested Retrieval Strategy Schema

```json
{
  "intent": "formula_composition",
  "entities": ["六味地黄丸"],
  "predicate_allowlist": ["使用药材"],
  "predicate_blocklist": [],
  "graph_candidate_k": 40,
  "graph_final_k": 12,
  "vector_candidate_k": 8,
  "sources": ["graph_sqlite", "graph_nebula", "qa_vector_db"],
  "min_source_book_count": 1,
  "prefer_high_confidence": true,
  "prefer_multi_book_support": true,
  "need_followup_retrieval": false
}
```

## Engineering Guardrails

- Do not let the agent directly choose arbitrary SQL or graph queries.
- Let the agent choose from a constrained retrieval schema.
- Keep retrieval tools typed and auditable.
- Keep answer synthesis separate from retrieval planning.
- Track latency and evidence coverage separately.
