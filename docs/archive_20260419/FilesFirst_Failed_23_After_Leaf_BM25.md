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
| files_first_nonvector | 13184.2 | 22893.8 | 0.3043 | 0.3478 | 0.4783 | 0.5217 | 0.087 | 0.1304 | 0.3043 | 0.3913 | 0.1739 | 0.279 | 0.5 | 0.5057 |
| classics_vector_hybrid | 2764.1 | 5214.2 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 11603.0 | 1290.1 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 19921.2 | 2741.3 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 6856.9 | 1365.9 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 6329.8 | 2574.0 |
| tcb_50943261620b_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21857.1 | 847.2 |
| tcb_b26bf7448135_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21853.3 | 2407.9 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5639.9 | 1100.9 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21507.5 | 831.9 |
| tcb_633f9691b540_src | formula_composition | source_locate | False | False | False | True | True | False | True | True | 21471.8 | 801.4 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 22893.8 | 5214.2 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 13091.2 | 2631.6 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21419.9 | 2391.5 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 6128.8 | 2974.0 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 16902.4 | 3621.1 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | True | True | True | True | True | True | True | True | 26206.3 | 2599.9 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | False | False | False | False | True | True | True | True | 10936.5 | 2507.6 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7683.8 | 4367.0 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7103.6 | 2615.1 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7579.9 | 3007.1 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4489.1 | 3184.1 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | False | False | False | False | True | True | True | True | 4617.6 | 7078.2 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | False | False | False | False | 10201.6 | 3905.8 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 6942.1 | 3515.5 |
