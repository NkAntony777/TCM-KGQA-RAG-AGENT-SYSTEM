# Classics Framework Baselines

## Overview

| Field | Value |
| --- | --- |
| dataset | backend\eval\datasets\paper\classics_vector_vs_filesfirst_external_validation_12.json |
| sqlite_db | D:\毕业设计数据处理\langchain-miniopenclaw\backend\storage\classics_vector_store.sqlite |
| row_count | 170319 |
| top_k | 3 |
| candidate_k | 20 |
| max_docs | None |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_keyword | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| llamaindex_sqlite_dense | 1557.9 | 6793.4 | 0.4583 | None | 0.9167 | 0.375 | 0.3994 |
| haystack_inmemory_bm25 | 1397.8 | 1841.5 | 0.1667 | None | 0.625 | 0.1667 | 0.1667 |
