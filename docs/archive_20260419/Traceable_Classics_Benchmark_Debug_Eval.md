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
| files_first_nonvector | 5063.8 | 16329.4 | 0.1429 | 0.1429 | 0.2857 | 0.2857 | 0.0714 | 0.0714 | 0.0714 | 0.0714 | 0.0714 | 0.0714 | 0.2857 | 0.2857 |
| classics_vector_hybrid | 2976.5 | 7239.5 | 0.1429 | 0.3571 | 0.4286 | 0.4286 | 0.0 | 0.0 | 0.0 | 0.1429 | 0.0 | 0.1429 | 0.4286 | 0.4286 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_f1d58e32c014_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 9113.0 | 1608.3 |
| tcb_f1d58e32c014_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1415.4 | 986.1 |
| tcb_7d966a168564_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | True | 3071.4 | 962.0 |
| tcb_7d966a168564_src | formula_composition | source_locate | False | False | False | False | True | False | False | True | 1056.7 | 1042.0 |
| tcb_99b9dada3796_ans | formula_indication_symptom | answer_trace | False | False | False | False | False | False | False | False | 4376.3 | 4458.3 |
| tcb_99b9dada3796_src | formula_indication_symptom | source_locate | False | False | False | False | False | False | False | False | 1145.2 | 1663.0 |
| tcb_854f4052ab6b_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2776.6 | 2526.4 |
| tcb_854f4052ab6b_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 5811.4 | 2540.4 |
| tcb_4712928b3239_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2784.0 | 7239.5 |
| tcb_4712928b3239_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7662.3 | 2950.1 |
| tcb_50d2b0055a8b_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2765.1 | 4450.1 |
| tcb_50d2b0055a8b_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6012.4 | 2612.2 |
| tcb_6bd56843dec4_ans | entity_alias | answer_trace | True | True | True | True | True | False | False | False | 6574.6 | 6053.3 |
| tcb_6bd56843dec4_src | entity_alias | source_locate | False | False | False | False | False | False | False | False | 16329.4 | 2578.7 |
