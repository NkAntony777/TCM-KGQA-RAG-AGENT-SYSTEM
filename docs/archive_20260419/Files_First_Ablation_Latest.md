# Files-First Internal Ablation

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Condition | avg_latency_ms | top1_book | top1_keyword | topk_book | topk_keyword | avg_book_case | avg_keyword_case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 完整 files-first | 9857.3 | 0.2639 | 0.9583 | 0.375 | 0.9861 | 0.2488 | 0.7645 |
| 关闭 direct recall | 8934.9 | 0.25 | 0.9583 | 0.4028 | 0.9861 | 0.2512 | 0.7638 |
| 关闭 lexical sanity | 9629.7 | 0.25 | 0.9444 | 0.375 | 0.9722 | 0.2488 | 0.7575 |
| 关闭 query rewrite | 9383.8 | 0.25 | 0.9028 | 0.3611 | 0.9306 | 0.2413 | 0.7286 |
| 关闭 chapter/book rerank bonus | 9702.6 | 0.25 | 0.9444 | 0.375 | 0.9583 | 0.2438 | 0.7561 |

## Delta vs Baseline

| Condition | delta_latency_ms | delta_topk_book | delta_topk_keyword |
| --- | ---: | ---: | ---: |
| 关闭 direct recall | -922.4 | 0.0278 | 0.0 |
| 关闭 lexical sanity | -227.6 | 0.0 | -0.0139 |
| 关闭 query rewrite | -473.5 | -0.0139 | -0.0555 |
| 关闭 chapter/book rerank bonus | -154.7 | 0.0 | -0.0278 |
