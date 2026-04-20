# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| top_k | 3 |
| candidate_k | 12 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_keyword | topk_keyword | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 3842.8 | 12738.7 | 0.2639 | 0.375 | 1.0 | 1.0 | 0.9583 | 0.9861 | 0.3796 | 0.3856 |
| classics_vector_hybrid | 8616.4 | 46761.4 | 0.0833 | 0.1944 | 0.9583 | 1.0 | 0.9722 | 0.9722 | 0.3889 | 0.402 |

## Per Case

| case_id | category | files_first_topk_book | files_first_topk_chapter | files_first_source_mrr | vector_topk_book | vector_topk_chapter | vector_source_mrr | files_first_latency | vector_latency |
| --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: |
| cvf_001 | origin | False | None | 0.0 | False | None | 0.0 | 14054.2 | 9104.8 |
| cvf_002 | origin_quote | False | None | 0.0 | False | None | 0.0 | 1898.1 | 14677.6 |
| cvf_003 | formula_role | False | None | 0.0 | False | None | 0.0 | 3971.7 | 66142.2 |
| cvf_004 | definition | True | None | 1.0 | True | None | 1.0 | 775.4 | 1931.6 |
| cvf_005 | formula_origin | False | None | 0.0 | False | None | 0.0 | 984.5 | 1531.3 |
| cvf_006 | formula_summary | False | None | 0.0 | False | None | 0.0 | 3610.9 | 7272.5 |
| cvf_007 | formula_comparison | False | None | 0.0 | False | None | 0.0 | 4380.4 | 1463.4 |
| cvf_008 | herb_property | False | None | 0.0 | False | None | 0.0 | 1709.1 | 674.4 |
| cvf_009 | formula_indication | True | None | 1.0 | False | None | 0.0 | 16740.8 | 12275.3 |
| cvf_010 | formula_definition | False | None | 0.0 | True | None | 0.5 | 8003.3 | 3482.1 |
| cvf_011 | book_source | False | None | 0.0 | False | None | 0.0 | 6938.0 | 25868.5 |
| cvf_012 | book_source | False | None | 0.0 | True | None | 0.3333 | 1319.6 | 13958.5 |
| cvf_013 | reasoning | False | None | 0.0 | False | None | 0.0 | 3751.4 | 3094.5 |
| cvf_014 | reasoning | False | None | 0.0 | False | None | 0.0 | 11568.1 | 6149.9 |
| cvf_015 | source_text | False | None | 0.0 | False | None | 0.0 | 3340.8 | 1308.7 |
| cvf_016 | source_text | False | None | 0.0 | False | None | 0.0 | 2025.7 | 1168.0 |
| cvf_017 | book_quote | False | None | 0.0 | False | None | 0.0 | 3895.7 | 960.8 |
| cvf_018 | book_quote | False | None | 0.0 | True | None | 0.3333 | 2634.1 | 14184.7 |
| cvf_019 | formula_comparison | True | None | 0.3333 | False | None | 0.0 | 4399.8 | 25730.9 |
| cvf_020 | generic | False | None | 0.0 | False | None | 0.0 | 4625.0 | 18878.5 |
| cvf_021 | formula_composition | False | None | 0.0 | False | None | 0.0 | 1899.4 | 9227.6 |
| cvf_022 | formula_composition | False | None | 0.0 | False | None | 0.0 | 3755.6 | 10587.4 |
| cvf_023 | herb_property | False | None | 0.0 | True | None | 1.0 | 968.6 | 2794.2 |
| cvf_024 | herb_property | False | None | 0.0 | False | None | 0.0 | 996.3 | 637.2 |
| cvf_025 | formula_origin | False | None | 0.0 | True | None | 0.5 | 4249.8 | 5963.7 |
| cvf_026 | formula_origin | False | None | 0.0 | False | None | 0.0 | 3512.3 | 1627.9 |
| cvf_027 | formula_definition | False | None | 0.0 | False | None | 0.0 | 1999.4 | 20583.6 |
| cvf_028 | formula_definition | False | None | 0.0 | False | None | 0.0 | 1086.7 | 51746.8 |
| cvf_029 | theory_quote | False | None | 0.0 | False | None | 0.0 | 3434.1 | 46761.4 |
| cvf_030 | theory_quote | False | None | 0.0 | False | None | 0.0 | 6301.7 | 49367.4 |
| cvf_031 | formula_role | False | None | 0.0 | True | None | 0.5 | 8985.1 | 13056.1 |
| cvf_032 | formula_role | False | None | 0.0 | False | None | 0.0 | 2107.4 | 720.0 |
| cvf_033 | reasoning | False | None | 0.0 | False | None | 0.0 | 13527.5 | 2752.3 |
| cvf_034 | reasoning | True | None | 0.5 | False | None | 0.0 | 1969.2 | 8889.4 |
| cvf_035 | formula_summary | False | None | 0.0 | True | None | 0.5 | 3882.8 | 1288.1 |
| cvf_036 | formula_summary | False | None | 0.0 | False | None | 0.0 | 3109.4 | 1266.1 |
| cvf_037 | source_text | False | None | 0.0 | False | None | 0.0 | 4191.8 | 742.4 |
| cvf_038 | source_text | False | None | 0.0 | False | None | 0.0 | 1911.8 | 720.3 |
| cvf_039 | book_quote | False | None | 0.0 | False | None | 0.0 | 3979.7 | 19003.7 |
| cvf_040 | book_quote | False | None | 0.0 | False | None | 0.0 | 1511.3 | 8475.3 |
| cvf_041 | formula_comparison | False | None | 0.0 | False | None | 0.0 | 10222.9 | 2510.7 |
| cvf_042 | formula_comparison | False | None | 0.0 | False | None | 0.0 | 3209.8 | 1620.0 |
| cvf_043 | herb_property | False | None | 0.0 | False | None | 0.0 | 1058.0 | 894.1 |
| cvf_044 | herb_property | False | None | 0.0 | False | None | 0.0 | 1061.8 | 624.0 |
| cvf_045 | generic | False | None | 0.0 | False | None | 0.0 | 2408.3 | 10389.6 |
| cvf_046 | generic | False | None | 0.0 | False | None | 0.0 | 3395.7 | 6820.2 |
| cvf_047 | formula_indication | False | None | 0.0 | False | None | 0.0 | 1086.4 | 10412.7 |
| cvf_048 | formula_indication | True | None | 0.5 | False | None | 0.0 | 4047.9 | 1287.3 |
| cvf_049 | book_quote | False | True | 1.0 | False | True | 1.0 | 7556.2 | 8036.5 |
| cvf_050 | book_quote | False | True | 1.0 | False | True | 1.0 | 3006.3 | 1975.9 |
| cvf_051 | formula_definition | True | True | 1.0 | False | True | 1.0 | 3024.1 | 9025.2 |
| cvf_052 | book_source | True | True | 1.0 | False | True | 1.0 | 1072.5 | 464.5 |
| cvf_053 | herb_property | True | True | 1.0 | True | True | 1.0 | 973.9 | 553.9 |
| cvf_054 | formula_indication | True | True | 1.0 | False | True | 1.0 | 2069.6 | 3310.0 |
| cvf_055 | reasoning | True | True | 1.0 | False | True | 1.0 | 3228.3 | 1327.3 |
| cvf_056 | formula_definition | True | True | 1.0 | True | True | 1.0 | 1124.9 | 3523.6 |
| cvf_057 | book_quote | True | True | 1.0 | False | True | 1.0 | 1203.2 | 1882.7 |
| cvf_058 | formula_origin | True | True | 1.0 | True | True | 1.0 | 1505.3 | 2310.3 |
| cvf_059 | formula_definition | True | True | 1.0 | False | True | 1.0 | 4073.1 | 17782.0 |
| cvf_060 | book_quote | True | True | 1.0 | False | True | 1.0 | 1107.0 | 4040.9 |
| cvf_061 | formula_definition | True | True | 1.0 | False | True | 1.0 | 1279.9 | 1707.9 |
| cvf_062 | formula_composition | True | True | 1.0 | False | True | 1.0 | 2072.8 | 611.4 |
| cvf_063 | reasoning | True | True | 1.0 | False | True | 1.0 | 4706.6 | 2727.7 |
| cvf_064 | definition | True | True | 1.0 | True | True | 0.3333 | 12738.7 | 2034.8 |
| cvf_065 | formula_composition | True | True | 1.0 | False | True | 1.0 | 5497.5 | 1377.9 |
| cvf_066 | formula_indication | True | True | 1.0 | False | True | 1.0 | 1546.8 | 8004.6 |
| cvf_067 | formula_indication | True | True | 1.0 | False | True | 1.0 | 2217.2 | 3317.9 |
| cvf_068 | formula_indication | True | True | 1.0 | False | True | 1.0 | 2044.0 | 1278.6 |
| cvf_069 | herb_property | True | True | 1.0 | True | True | 1.0 | 1080.6 | 12266.8 |
| cvf_070 | formula_origin | True | True | 1.0 | True | True | 1.0 | 2379.9 | 2362.7 |
| cvf_071 | reasoning | True | True | 1.0 | False | True | 1.0 | 4654.1 | 1453.8 |
| cvf_072 | reasoning | True | True | 1.0 | False | True | 1.0 | 6020.0 | 8376.8 |
