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
| files_first_nonvector | 11016.6 | 21563.2 | 0.5652 | 0.5652 | 0.7391 | 0.7391 | 0.1739 | 0.1739 | 0.5217 | 0.4783 | 0.3043 | 0.337 | 0.7391 | 0.7356 |
| classics_vector_hybrid | 3269.4 | 6590.4 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 14198.1 | 2698.0 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 8043.7 | 2583.7 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 7161.4 | 839.0 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 9620.6 | 2519.1 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 15042.7 | 6590.4 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 8442.8 | 2713.1 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5734.0 | 1106.8 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21563.2 | 830.0 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 10298.5 | 1395.0 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 29364.1 | 5261.2 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 11396.9 | 3448.8 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 8300.4 | 1933.1 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 13818.5 | 5489.8 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 21032.9 | 5171.3 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 11675.7 | 2644.8 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 10572.6 | 2505.4 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6891.2 | 2512.4 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7513.6 | 2540.1 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 5793.1 | 3237.8 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4362.3 | 3088.2 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | True | True | True | True | 4786.5 | 6883.9 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | False | False | False | False | 10156.7 | 5650.9 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 7611.5 | 3553.9 |
