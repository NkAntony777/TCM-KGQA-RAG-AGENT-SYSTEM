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
| files_first_nonvector | 8353.0 | 13426.7 | 0.5652 | 0.5652 | 0.7391 | 0.7391 | 0.1304 | 0.1304 | 0.5217 | 0.4348 | 0.2609 | 0.2935 | 0.7391 | 0.7356 |
| classics_vector_hybrid | 4347.1 | 8370.6 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 10890.3 | 8370.6 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 9377.6 | 18690.0 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 8026.5 | 3410.1 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 9517.5 | 4679.2 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5542.7 | 2625.6 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 7242.1 | 869.2 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5353.0 | 894.2 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 6830.7 | 1583.8 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 13426.7 | 3417.7 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 6900.7 | 5434.1 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 9027.7 | 2821.5 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 9374.7 | 1793.3 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 8455.8 | 2912.1 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 8146.4 | 3928.7 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 8752.0 | 3130.8 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | False | False | False | False | True | True | True | True | 16399.5 | 2784.6 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6656.0 | 2632.9 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7286.5 | 3928.5 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6161.9 | 4030.2 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4975.3 | 3821.4 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | True | True | True | True | 7144.4 | 8051.8 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | False | False | False | False | 7053.1 | 6557.2 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 9578.1 | 3614.9 |
