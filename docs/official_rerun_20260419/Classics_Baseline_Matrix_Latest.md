# Classics Baseline Matrix

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_internal | 10241.0 | 23180.8 | 0.375 | 1.0 | None | None | None | None | None | 0.3796 | 0.3856 |
| external_bm25_docs | 4052.6 | 5037.1 | 0.2222 | 0.7917 | None | None | None | None | None | 0.3079 | 0.3191 |
| vector_sqlite_internal | 3301.8 | 9481.3 | 0.1944 | 1.0 | None | None | None | None | None | 0.3866 | 0.4002 |
| external_dense_candidates | 1809.0 | 9471.7 | 0.0833 | 0.875 | None | None | None | None | None | 0.2894 | 0.2955 |
