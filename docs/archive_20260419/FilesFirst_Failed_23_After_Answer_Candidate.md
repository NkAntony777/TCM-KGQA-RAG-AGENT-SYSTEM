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
| files_first_nonvector | 13968.4 | 26163.6 | 0.087 | 0.087 | 0.1304 | 0.1304 | 0.0 | 0.0 | 0.087 | 0.0 | 0.0 | 0.0 | 0.1304 | 0.1304 |
| classics_vector_hybrid | 3235.3 | 8035.5 | 0.6087 | 0.6522 | 0.6957 | 0.8261 | 0.1739 | 0.2174 | 0.6087 | 0.3043 | 0.2609 | 0.25 | 0.7609 | 0.7807 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21030.3 | 1101.8 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 10290.3 | 3267.3 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 10124.4 | 1039.6 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 11271.1 | 2615.1 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 8927.4 | 2831.8 |
| tcb_b26bf7448135_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 13178.7 | 856.0 |
| tcb_cfc87926e240_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 21330.8 | 832.9 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 9796.2 | 943.9 |
| tcb_633f9691b540_src | formula_composition | source_locate | False | False | False | False | True | False | True | True | 30352.2 | 955.0 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | False | False | False | False | True | True | True | True | 10736.4 | 7885.7 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 26163.6 | 8277.9 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 13981.3 | 2789.5 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 11428.5 | 5399.2 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | False | False | False | False | True | True | True | True | 12450.7 | 4245.4 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 15122.3 | 2673.7 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | False | False | False | False | True | True | True | True | 13579.4 | 2849.7 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 9180.8 | 2627.4 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7333.0 | 3174.3 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 19177.9 | 2521.3 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4391.7 | 3135.1 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | False | False | False | False | True | True | True | True | 12123.3 | 8035.5 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | False | False | False | False | False | 17607.0 | 2804.9 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | False | False | False | False | False | 11695.2 | 3549.6 |
