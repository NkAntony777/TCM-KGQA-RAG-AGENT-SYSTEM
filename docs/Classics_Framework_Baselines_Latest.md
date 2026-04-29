# Classics Framework Baselines

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| sqlite_db | D:\毕业设计数据处理\langchain-miniopenclaw\backend\storage\classics_vector_store.sqlite |
| row_count | 170319 |
| top_k | 3 |
| candidate_k | 20 |
| max_docs | None |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_keyword | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| llamaindex_sqlite_dense | 2225.7 | 11872.1 | 0.3611 | 1.0 | 0.9861 | 0.4514 | 0.4692 |
| haystack_inmemory_bm25 | 1239.9 | 1581.5 | 0.0833 | 0.5833 | 0.7639 | 0.1458 | 0.1692 |
