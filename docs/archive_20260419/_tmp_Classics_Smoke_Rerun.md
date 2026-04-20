# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_debug_12.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 11854.9 | 28434.7 | 0.8333 | 0.8333 | None | None | None | None | 0.8333 | 0.9167 | 0.8333 | 0.8195 | 0.8333 | 0.8333 |
| classics_vector_hybrid | 8331.5 | 51344.3 | 0.6667 | 0.6667 | None | None | None | None | 0.6667 | 0.75 | 0.4167 | 0.5099 | 0.6667 | 0.6667 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_s201 | formula_indication | retrieval | True | None | True | True | True | None | True | True | 18633.1 | 51344.3 |
| cvf_s202 | formula_indication | retrieval | True | None | True | True | True | None | True | False | 7536.7 | 13126.0 |
| cvf_s203 | formula_indication | retrieval | True | None | True | True | True | None | True | False | 6813.3 | 3047.0 |
| cvf_s204 | formula_definition | retrieval | True | None | True | True | True | None | True | True | 10443.3 | 2739.7 |
| cvf_s205 | formula_explanation | retrieval | False | None | False | False | False | None | False | True | 28434.7 | 5643.9 |
| cvf_s206 | formula_indication | retrieval | False | None | False | True | False | None | False | True | 18771.4 | 4140.0 |
| cvf_s207 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 9385.5 | 6545.8 |
| cvf_s208 | herb_property | retrieval | True | None | True | True | False | None | False | True | 11563.4 | 6102.2 |
| cvf_s209 | herb_property | retrieval | True | None | True | True | True | None | True | True | 8213.3 | 2975.0 |
| cvf_s210 | formula_alias | retrieval | True | None | True | True | True | None | True | True | 6379.2 | 1424.9 |
| cvf_s211 | formula_explanation | retrieval | True | None | True | True | True | None | True | True | 8155.4 | 1372.4 |
| cvf_s212 | formula_definition | retrieval | True | None | True | True | True | None | True | False | 7929.8 | 1517.1 |
