# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | eval\datasets\paper\classics_vector_vs_filesfirst_external_validation_12.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | top1_book_hit_rate | top1_keyword_hit_rate | topk_book_hit_rate | topk_keyword_hit_rate | avg_book_hit_rate_case | avg_keyword_hit_rate_case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 6571.5 | 0.4167 | 0.5 | 0.5 | 0.5833 | 0.5 | 0.4097 |
| classics_vector_hybrid | 7023.5 | 0.1667 | 0.6667 | 0.3333 | 0.75 | 0.3333 | 0.4514 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_keyword | vector_topk_book | vector_topk_keyword | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_e301 | formula_reverse_lookup | False | True | False | True | 17080.1 | 27790.3 |
| cvf_e302 | formula_indication | True | True | True | True | 5089.8 | 4114.2 |
| cvf_e303 | formula_explanation | True | False | True | False | 7259.0 | 3766.4 |
| cvf_e304 | herb_property | False | False | True | True | 6792.1 | 1647.5 |
| cvf_e305 | herb_property | False | False | False | True | 5431.6 | 4286.7 |
| cvf_e306 | formula_alias | True | True | False | False | 579.4 | 3994.7 |
| cvf_e307 | formula_indication | False | True | False | True | 4254.5 | 7089.2 |
| cvf_e308 | formula_reverse_lookup | True | True | False | False | 8968.2 | 5142.6 |
| cvf_e309 | theory_summary | True | True | False | True | 3004.7 | 10044.6 |
| cvf_e310 | formula_indication | True | False | False | True | 6500.4 | 6135.9 |
| cvf_e311 | theory_summary | False | False | True | True | 5505.9 | 6221.1 |
| cvf_e312 | formula_definition | False | True | False | True | 8392.5 | 4048.9 |
