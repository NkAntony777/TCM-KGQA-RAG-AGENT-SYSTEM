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
| files_first_nonvector | 1751.2 | 0.0833 | 0.75 | 0.0833 | 0.75 | 0.1 | 0.4143 |
| classics_vector_hybrid | 2015.0 | 0.0833 | 0.8333 | 0.1667 | 0.8333 | 0.1667 | 0.4859 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_keyword | vector_topk_book | vector_topk_keyword | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_002 | origin_quote | False | True | False | True | 2991.1 | 1171.0 |
| cvf_003 | formula_role | False | True | False | True | 91.7 | 4364.1 |
| cvf_004 | definition | True | False | True | True | 53.3 | 1631.1 |
| cvf_007 | formula_comparison | False | True | False | True | 41.7 | 1208.1 |
| cvf_008 | herb_property | False | True | False | True | 43.5 | 681.4 |
| cvf_010 | formula_definition | False | False | False | True | 3052.6 | 3226.8 |
| cvf_011 | book_source | False | False | False | False | 1513.7 | 4591.7 |
| cvf_015 | source_text | False | True | True | True | 77.0 | 1151.5 |
| cvf_022 | formula_composition | False | True | False | True | 35.9 | 671.6 |
| cvf_029 | theory_quote | False | True | False | False | 13008.0 | 3521.2 |
| cvf_038 | source_text | False | True | False | True | 90.2 | 772.8 |
| cvf_045 | generic | False | True | False | True | 15.7 | 1189.1 |
