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
| files_first_nonvector | 11587.2 | 26660.1 | 0.5217 | 0.6087 | 0.6957 | 0.7826 | 0.1304 | 0.2174 | 0.5652 | 0.4348 | 0.3043 | 0.3225 | 0.7391 | 0.747 |
| classics_vector_hybrid | 4048.7 | 9984.7 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 10999.9 | 1301.7 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 5862.0 | 8784.2 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21554.9 | 2368.0 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 7140.9 | 12263.5 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 7459.9 | 1293.3 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 5780.3 | 1147.7 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 6242.7 | 920.8 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5975.9 | 3907.9 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 9155.1 | 801.3 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 15450.3 | 5217.7 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 11358.1 | 5909.9 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 8382.3 | 1764.1 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 13840.0 | 3063.3 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 26660.1 | 6208.1 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | True | True | True | True | True | True | True | True | 25850.9 | 2722.9 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 17176.2 | 2740.3 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6265.5 | 9984.7 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7233.6 | 2543.3 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6548.1 | 2715.1 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4410.3 | 3463.8 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | True | True | True | True | 9130.8 | 6962.8 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | False | False | False | False | False | 27022.4 | 3424.7 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 7005.9 | 3610.8 |
