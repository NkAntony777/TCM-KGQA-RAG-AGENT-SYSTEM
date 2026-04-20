# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\traceable_classics_benchmark_filesfirst_failed_23.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 12953.0 | 25046.7 | 0.1304 | 0.1304 | 0.1739 | 0.1739 | 0.0 | 0.0 | 0.1304 | 0.0435 | 0.0435 | 0.0217 | 0.1739 | 0.1739 |
| classics_vector_hybrid | 3162.0 | 6752.6 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 14360.1 | 834.0 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 8800.0 | 2708.0 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 8922.7 | 833.7 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 12055.0 | 2656.2 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 9634.9 | 2367.6 |
| tcb_b26bf7448135_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 10021.8 | 837.6 |
| tcb_cfc87926e240_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 7681.9 | 847.8 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 9417.2 | 801.5 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 15271.7 | 1197.2 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | False | False | False | False | True | True | True | True | 10091.3 | 6752.6 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 11365.9 | 3350.2 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 14659.1 | 1869.6 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 23547.0 | 2878.0 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | False | False | False | False | True | True | True | True | 8690.5 | 3840.9 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 25046.7 | 2709.5 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | False | False | False | False | True | True | True | True | 25662.8 | 2720.7 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 12537.6 | 2950.6 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7203.2 | 2936.4 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 16978.5 | 5302.3 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4378.9 | 4441.0 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | False | False | False | False | True | True | True | True | 14299.4 | 11419.7 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | False | False | False | False | False | 13478.8 | 2624.5 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | False | False | False | False | False | 13813.7 | 5846.4 |
