# Case QA Vector vs Structured Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\caseqa_vector_vs_structured_debug_8.json |
| top_k | 3 |
| candidate_k | 20 |
| structured_index | D:\毕业设计数据处理\langchain-miniopenclaw\backend\storage\qa_structured_index.sqlite |

## Aggregate

| Method | cases | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_precision | avg_keypoint_recall | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms | p95_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| structured_nonvector | 8 | 0.75 | 1.0 | 0.8313 | 0.2871 | 0.6042 | 0.359 | 0.75 | 2697.8 | 8293.4 |
| vector_caseqa | 8 | 0.875 | 1.0 | 0.6687 | 0.2792 | 0.6244 | 0.3721 | 0.875 | 18242.7 | 37626.0 |

## By Category

| Category | Method | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| case_basic | structured | 0.5 | 1.0 | 0.7 | 0.1613 | 1.0 | 3352.9 |
| case_basic | vector | 0.5 | 1.0 | 0.35 | 0.2427 | 1.0 | 21996.0 |
| case_syndrome_formula | structured | 0.5 | 1.0 | 0.625 | 0.2009 | 0.5 | 994.2 |
| case_syndrome_formula | vector | 1.0 | 1.0 | 0.325 | 0.1698 | 1.0 | 21865.5 |
| compare_boundary | structured | 1.0 | 1.0 | 1.0 | 0.5479 | 1.0 | 1457.2 |
| compare_boundary | vector | 1.0 | 1.0 | 1.0 | 0.7097 | 1.0 | 17072.1 |
| formula_origin | structured | 1.0 | 1.0 | 1.0 | 0.5 | 1.0 | 726.5 |
| formula_origin | vector | 1.0 | 1.0 | 1.0 | 0.5 | 1.0 | 17055.3 |
| formula_role | structured | 1.0 | 1.0 | 1.0 | 0.5143 | 1.0 | 2411.4 |
| formula_role | vector | 1.0 | 1.0 | 1.0 | 0.4275 | 1.0 | 6051.2 |
| open_query | structured | 1.0 | 1.0 | 1.0 | 0.5854 | 0.0 | 8293.4 |
| open_query | vector | 1.0 | 1.0 | 1.0 | 0.5143 | 0.0 | 18040.0 |

## Per Case

| case_id | category | mode | structured_topk_hit | structured_keypoint_f1 | vector_topk_hit | vector_keypoint_f1 | structured_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cqv_001 | case_basic | case | True | 0.3226 | True | 0.2804 | 2437.7 | 29923.3 |
| cqv_004 | case_syndrome_formula | case | True | 0.0667 | True | 0.2 | 260.6 | 6105.0 |
| cqv_006 | formula_role | qa | True | 0.5143 | True | 0.4275 | 2411.4 | 6051.2 |
| cqv_007 | formula_origin | qa | True | 0.5 | True | 0.5 | 726.5 | 17055.3 |
| cqv_010 | compare_boundary | qa | True | 0.5479 | True | 0.7097 | 1457.2 | 17072.1 |
| cqv_020 | case_syndrome_formula | case | True | 0.3352 | True | 0.1395 | 1727.9 | 37626.0 |
| cqv_028 | open_query | qa | True | 0.5854 | True | 0.5143 | 8293.4 | 18040.0 |
| cqv_031 | case_basic | case | True | 0.0 | True | 0.2051 | 4268.1 | 14068.7 |
