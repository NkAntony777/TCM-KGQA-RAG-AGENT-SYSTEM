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
| files_first_nonvector | 8046.8 | 10917.3 | 0.6087 | 0.6087 | 0.7826 | 0.7826 | 0.1739 | 0.1739 | 0.5652 | 0.4783 | 0.3043 | 0.337 | 0.7826 | 0.7791 |
| classics_vector_hybrid | 3530.9 | 7042.5 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 10917.3 | 1374.7 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 8645.0 | 2870.7 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 5862.8 | 966.3 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 8516.5 | 3020.8 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 6189.4 | 1055.5 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 5769.9 | 1479.3 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5368.4 | 961.7 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5722.2 | 838.9 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 9302.4 | 812.8 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 6373.3 | 5374.6 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 9531.1 | 2938.9 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 8695.7 | 5458.3 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 7288.1 | 2764.8 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 9064.3 | 8988.2 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 8615.1 | 5969.6 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 10766.1 | 4713.1 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 5940.7 | 2630.3 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7276.5 | 4455.2 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 9046.0 | 3601.0 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 5534.6 | 4785.1 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | True | True | True | True | 6454.0 | 7042.5 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | False | False | False | False | 16808.6 | 5598.7 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 7388.5 | 3509.5 |
