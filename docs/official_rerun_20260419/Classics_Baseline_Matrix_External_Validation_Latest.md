# Classics Baseline Matrix

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_external_validation_12.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | topk_book | topk_chapter | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_internal | 11190.1 | 15462.4 | 0.6667 | None | None | None | None | None | None | 0.5417 | 0.5667 |
| external_bm25_docs | 3560.1 | 3922.0 | 0.5833 | None | None | None | None | None | None | 0.4722 | 0.5036 |
| vector_sqlite_internal | 6167.2 | 15174.8 | 0.2083 | None | None | None | None | None | None | 0.1389 | 0.1567 |
| external_dense_candidates | 2960.7 | 6580.1 | 0.1667 | None | None | None | None | None | None | 0.0972 | 0.1177 |
