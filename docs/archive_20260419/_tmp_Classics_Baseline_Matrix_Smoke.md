# Classics Baseline Matrix

## Overview

| Field | Value |
| --- | --- |
| dataset | eval\datasets\paper\classics_vector_vs_filesfirst_external_validation_12.json |
| top_k | 3 |
| candidate_k | 12 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_keyword | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_internal | 6624.3 | 13269.4 | 0.625 | None | 0.875 | 0.5208 | 0.5404 |
| external_bm25_docs | 656.9 | 1157.9 | 0.5833 | None | 0.9583 | 0.4722 | 0.5036 |
| vector_sqlite_internal | 8218.1 | 51619.5 | 0.25 | None | 0.9583 | 0.1597 | 0.183 |
| external_dense_candidates | 455.1 | 830.2 | 0.125 | None | 0.5417 | 0.0764 | 0.0914 |
