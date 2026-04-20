# Section Summary Ablation Benchmark

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\section_summary_ablation_10.json |
| total_queries | 10 |
| baseline_index | D:\毕业设计数据处理\langchain-miniopenclaw\backend\workspace\section_summary_ablation_tmp\run_20260415_141402_9a44e564\baseline\retrieval_local_index.fts.db |
| enhanced_index | D:\毕业设计数据处理\langchain-miniopenclaw\backend\workspace\section_summary_ablation_tmp\run_20260415_141402_9a44e564\enhanced\retrieval_local_index.fts.db |

## Aggregate

| Condition | avg_latency_ms | avg_score | top1_book | top3_book | top1_section | top3_section | rebuild_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_no_llm_summary | 6794.2 | 3.7 | 0.00% | 0.00% | 90.00% | 90.00% | 1872028.8 |
| enhanced_llm_summary | 8218.4 | 4.0 | 10.00% | 10.00% | 90.00% | 90.00% | 1577158.9 |

## Per Query

| ID | baseline_latency | baseline_score | enhanced_latency | enhanced_score | delta_score |
| --- | --- | --- | --- | --- | --- |
| sum_001 | 35928.6 | 2.75 | 30418.8 | 2.75 | 0.0 |
| sum_002 | 4053.4 | 6.5 | 3869.0 | 6.5 | 0.0 |
| sum_003 | 2161.5 | 4.0 | 2117.1 | 3.75 | -0.25 |
| sum_004 | 1963.7 | 5.25 | 20243.7 | 2.75 | -2.5 |
| sum_005 | 2134.9 | 2.75 | 7248.3 | 1.5 | -1.25 |
| sum_006 | 2024.9 | 3.25 | 2025.9 | 7.75 | 4.5 |
| sum_007 | 9319.0 | 4.0 | 6189.4 | 5.25 | 1.25 |
| sum_008 | 1916.1 | 4.5 | 1862.3 | 4.5 | 0.0 |
| sum_009 | 6465.8 | 0.0 | 6267.9 | 0.0 | 0.0 |
| sum_010 | 1974.5 | 4.0 | 1941.5 | 5.25 | 1.25 |
