# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\traceable_classics_benchmark_debug.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 4326.7 | 10573.7 | 0.2143 | 0.2143 | 0.5 | 0.5 | 0.0714 | 0.0714 | 0.0714 | 0.2857 | 0.0714 | 0.1488 | 0.5 | 0.5 |
| classics_vector_hybrid | 3424.8 | 9243.5 | 0.2143 | 0.3571 | 0.7143 | 0.7143 | 0.0714 | 0.1429 | 0.1429 | 0.1429 | 0.1429 | 0.0536 | 0.7143 | 0.7143 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_f1d58e32c014_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 8496.5 | 809.8 |
| tcb_f1d58e32c014_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1404.9 | 5608.1 |
| tcb_7d966a168564_ans | formula_composition | answer_trace | False | False | False | True | True | True | True | True | 3073.0 | 4324.8 |
| tcb_7d966a168564_src | formula_composition | source_locate | False | False | False | True | True | True | True | True | 1118.3 | 984.8 |
| tcb_99b9dada3796_ans | formula_indication_symptom | answer_trace | False | False | False | False | False | False | False | False | 2857.0 | 3026.2 |
| tcb_99b9dada3796_src | formula_indication_symptom | source_locate | False | False | False | False | False | False | False | False | 1168.6 | 9243.5 |
| tcb_854f4052ab6b_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2834.9 | 5481.6 |
| tcb_854f4052ab6b_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6340.5 | 2578.7 |
| tcb_4712928b3239_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 2803.0 | 2646.9 |
| tcb_4712928b3239_src | herb_effect | source_locate | True | False | False | False | False | False | False | False | 5827.9 | 2656.1 |
| tcb_50d2b0055a8b_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2837.3 | 2802.1 |
| tcb_50d2b0055a8b_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 4219.8 | 2674.3 |
| tcb_6bd56843dec4_ans | entity_alias | answer_trace | True | True | True | True | True | False | False | False | 7018.8 | 2580.6 |
| tcb_6bd56843dec4_src | entity_alias | source_locate | False | False | False | False | False | False | False | False | 10573.7 | 2529.8 |
