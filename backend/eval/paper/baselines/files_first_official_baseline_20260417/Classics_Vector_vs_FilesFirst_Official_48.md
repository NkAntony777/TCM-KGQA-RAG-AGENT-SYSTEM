# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | top1_book_hit_rate | top1_keyword_hit_rate | topk_book_hit_rate | topk_keyword_hit_rate | avg_book_hit_rate_case | avg_keyword_hit_rate_case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 3815.8 | 0.125 | 0.9375 | 0.375 | 0.9792 | 0.2674 | 0.6876 |
| classics_vector_hybrid | 6490.9 | 0.0625 | 0.9583 | 0.2292 | 0.9583 | 0.1512 | 0.5908 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_keyword | vector_topk_book | vector_topk_keyword | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_001 | origin | False | True | False | True | 13988.8 | 10134.8 |
| cvf_002 | origin_quote | False | True | False | True | 1902.5 | 3724.5 |
| cvf_003 | formula_role | False | True | False | True | 4249.9 | 22276.7 |
| cvf_004 | definition | True | False | True | True | 547.1 | 8229.9 |
| cvf_005 | formula_origin | True | True | False | True | 995.5 | 7988.1 |
| cvf_006 | formula_summary | False | True | False | True | 3570.3 | 13022.9 |
| cvf_007 | formula_comparison | False | True | False | True | 4159.3 | 4385.8 |
| cvf_008 | herb_property | False | True | False | True | 1727.8 | 26516.1 |
| cvf_009 | formula_indication | True | True | False | True | 7450.4 | 15914.0 |
| cvf_010 | formula_definition | False | True | True | True | 2340.6 | 3153.7 |
| cvf_011 | book_source | False | True | False | True | 5951.9 | 5028.3 |
| cvf_012 | book_source | True | True | True | True | 1302.5 | 3770.9 |
| cvf_013 | reasoning | True | True | False | True | 10148.7 | 2634.5 |
| cvf_014 | reasoning | False | True | False | True | 11467.0 | 10933.7 |
| cvf_015 | source_text | True | True | False | True | 3280.7 | 3814.5 |
| cvf_016 | source_text | True | True | True | True | 2592.3 | 2513.5 |
| cvf_017 | book_quote | False | True | False | False | 3658.7 | 2078.2 |
| cvf_018 | book_quote | False | True | True | True | 2529.0 | 1967.6 |
| cvf_019 | formula_comparison | True | True | True | True | 4233.3 | 6374.7 |
| cvf_020 | generic | False | True | False | False | 4231.0 | 20081.0 |
| cvf_021 | formula_composition | False | True | False | True | 1139.3 | 23513.1 |
| cvf_022 | formula_composition | True | True | False | True | 3420.7 | 866.7 |
| cvf_023 | herb_property | False | True | True | True | 2244.9 | 8737.5 |
| cvf_024 | herb_property | False | True | False | True | 3051.9 | 3476.7 |
| cvf_025 | formula_origin | False | True | True | True | 3798.6 | 1630.8 |
| cvf_026 | formula_origin | True | True | False | True | 2745.8 | 1251.2 |
| cvf_027 | formula_definition | False | True | False | True | 1841.5 | 2162.4 |
| cvf_028 | formula_definition | False | True | False | True | 980.1 | 4117.7 |
| cvf_029 | theory_quote | False | True | False | True | 2869.9 | 4352.3 |
| cvf_030 | theory_quote | True | True | False | True | 5985.7 | 5297.9 |
| cvf_031 | formula_role | False | True | True | True | 6102.8 | 1865.0 |
| cvf_032 | formula_role | True | True | False | True | 1848.4 | 2855.6 |
| cvf_033 | reasoning | True | True | False | True | 12037.7 | 3605.8 |
| cvf_034 | reasoning | False | True | False | True | 2068.5 | 1474.5 |
| cvf_035 | formula_summary | True | True | True | True | 2961.9 | 1185.8 |
| cvf_036 | formula_summary | True | True | False | True | 3079.5 | 1604.5 |
| cvf_037 | source_text | False | True | False | True | 1743.1 | 4354.7 |
| cvf_038 | source_text | False | True | False | True | 1678.0 | 3096.0 |
| cvf_039 | book_quote | False | True | False | True | 3810.7 | 7866.7 |
| cvf_040 | book_quote | True | True | False | True | 1052.5 | 5695.6 |
| cvf_041 | formula_comparison | False | True | False | True | 10160.1 | 9592.9 |
| cvf_042 | formula_comparison | True | True | True | True | 3267.6 | 2276.8 |
| cvf_043 | herb_property | False | True | False | True | 2719.6 | 1648.5 |
| cvf_044 | herb_property | False | True | False | True | 2204.6 | 670.6 |
| cvf_045 | generic | False | True | False | True | 2294.4 | 19134.4 |
| cvf_046 | generic | False | True | False | True | 3417.5 | 11535.3 |
| cvf_047 | formula_indication | True | True | False | True | 1063.2 | 1974.6 |
| cvf_048 | formula_indication | False | True | False | True | 3243.4 | 1174.0 |
