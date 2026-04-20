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
| files_first_nonvector | 1315.3 | 0.0833 | 0.9167 | 0.1667 | 0.9167 | 0.2 | 0.4919 |
| classics_vector_hybrid | 4358.9 | 0.0833 | 0.8333 | 0.1667 | 0.8333 | 0.1667 | 0.4859 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_keyword | vector_topk_book | vector_topk_keyword | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_002 | origin_quote | False | True | False | True | 3018.7 | 10053.1 |
| cvf_003 | formula_role | False | True | False | True | 136.1 | 19820.0 |
| cvf_004 | definition | True | False | True | True | 264.5 | 1881.3 |
| cvf_007 | formula_comparison | False | True | False | True | 784.9 | 1698.3 |
| cvf_008 | herb_property | False | True | False | True | 192.8 | 682.3 |
| cvf_010 | formula_definition | False | True | False | True | 3627.8 | 3617.0 |
| cvf_011 | book_source | True | True | False | False | 2351.3 | 5455.1 |
| cvf_015 | source_text | False | True | True | True | 86.3 | 1581.4 |
| cvf_022 | formula_composition | False | True | False | True | 463.3 | 872.5 |
| cvf_029 | theory_quote | False | True | False | False | 4240.3 | 4068.0 |
| cvf_038 | source_text | False | True | False | True | 538.2 | 868.2 |
| cvf_045 | generic | False | True | False | True | 79.3 | 1709.9 |
