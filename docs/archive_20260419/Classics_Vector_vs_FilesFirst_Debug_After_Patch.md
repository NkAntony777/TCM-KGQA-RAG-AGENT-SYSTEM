# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | eval\datasets\paper\classics_vector_vs_filesfirst_debug_12.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | top1_book_hit_rate | top1_keyword_hit_rate | topk_book_hit_rate | topk_keyword_hit_rate | avg_book_hit_rate_case | avg_keyword_hit_rate_case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 2678.2 | 0.0833 | 0.8333 | 0.0833 | 0.8333 | 0.1 | 0.4976 |
| classics_vector_hybrid | 2112.2 | 0.0833 | 0.8333 | 0.1667 | 0.8333 | 0.1667 | 0.4859 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_keyword | vector_topk_book | vector_topk_keyword | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_002 | origin_quote | False | True | False | True | 2988.7 | 1152.8 |
| cvf_003 | formula_role | False | True | False | True | 92.4 | 4547.0 |
| cvf_004 | definition | True | False | True | True | 54.5 | 1629.0 |
| cvf_007 | formula_comparison | False | True | False | True | 50.3 | 1423.0 |
| cvf_008 | herb_property | False | True | False | True | 43.1 | 1076.2 |
| cvf_010 | formula_definition | False | True | False | True | 3566.2 | 3248.5 |
| cvf_011 | book_source | False | False | False | False | 2129.2 | 4772.6 |
| cvf_015 | source_text | False | True | True | True | 68.2 | 1099.6 |
| cvf_022 | formula_composition | False | True | False | True | 45.9 | 732.9 |
| cvf_029 | theory_quote | False | True | False | False | 22989.3 | 3525.5 |
| cvf_038 | source_text | False | True | False | True | 94.8 | 782.1 |
| cvf_045 | generic | False | True | False | True | 15.9 | 1357.1 |
