# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_seed_20.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 10112.8 | 23056.8 | 0.2639 | 0.375 | 1.0 | 1.0 | None | None | 0.375 | 0.9861 | 0.3611 | 0.7222 | 0.3796 | 0.3856 |
| classics_vector_hybrid | 5151.4 | 18527.8 | 0.0972 | 0.1944 | 0.9583 | 1.0 | None | None | 0.1944 | 0.9722 | 0.1944 | 0.6036 | 0.3866 | 0.4002 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_001 | origin | retrieval | False | None | False | True | False | None | False | True | 26866.0 | 9943.7 |
| cvf_002 | origin_quote | retrieval | False | None | False | True | False | None | False | True | 18297.0 | 13094.2 |
| cvf_003 | formula_role | retrieval | False | None | False | True | False | None | False | True | 10052.7 | 37423.0 |
| cvf_004 | definition | retrieval | True | None | True | False | True | None | True | True | 6436.3 | 1819.6 |
| cvf_005 | formula_origin | retrieval | False | None | False | True | False | None | False | True | 11987.4 | 1202.3 |
| cvf_006 | formula_summary | retrieval | False | None | False | True | False | None | False | True | 12735.0 | 2562.6 |
| cvf_007 | formula_comparison | retrieval | False | None | False | True | False | None | False | True | 10019.4 | 8694.7 |
| cvf_008 | herb_property | retrieval | False | None | False | True | False | None | False | True | 7299.5 | 3046.8 |
| cvf_009 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 23829.7 | 18527.8 |
| cvf_010 | formula_definition | retrieval | False | None | False | True | True | None | True | True | 8186.4 | 3241.1 |
| cvf_011 | book_source | retrieval | False | None | False | True | False | None | False | True | 11864.7 | 5037.6 |
| cvf_012 | book_source | retrieval | False | None | False | True | True | None | True | True | 7191.8 | 7679.9 |
| cvf_013 | reasoning | retrieval | False | None | False | True | False | None | False | True | 16927.9 | 2553.4 |
| cvf_014 | reasoning | retrieval | False | None | False | True | False | None | False | True | 23056.8 | 6309.3 |
| cvf_015 | source_text | retrieval | False | None | False | True | False | None | False | True | 15364.8 | 1496.0 |
| cvf_016 | source_text | retrieval | False | None | False | True | False | None | False | True | 7961.5 | 4509.1 |
| cvf_017 | book_quote | retrieval | False | None | False | True | False | None | False | False | 9482.5 | 4003.7 |
| cvf_018 | book_quote | retrieval | False | None | False | True | True | None | True | True | 8458.0 | 2090.9 |
| cvf_019 | formula_comparison | retrieval | True | None | True | True | False | None | False | True | 9970.3 | 5927.8 |
| cvf_020 | generic | retrieval | False | None | False | True | False | None | False | False | 9889.4 | 2186.6 |
| cvf_021 | formula_composition | retrieval | False | None | False | True | False | None | False | True | 7119.5 | 9131.8 |
| cvf_022 | formula_composition | retrieval | False | None | False | True | False | None | False | True | 9290.0 | 10875.5 |
| cvf_023 | herb_property | retrieval | False | None | False | True | True | None | True | True | 6815.0 | 935.6 |
| cvf_024 | herb_property | retrieval | False | None | False | True | False | None | False | True | 6829.5 | 783.3 |
| cvf_025 | formula_origin | retrieval | False | None | False | True | True | None | True | True | 9617.6 | 1881.2 |
| cvf_026 | formula_origin | retrieval | False | None | False | True | False | None | False | True | 9365.5 | 3828.3 |
| cvf_027 | formula_definition | retrieval | False | None | False | True | False | None | False | True | 7778.5 | 20235.8 |
| cvf_028 | formula_definition | retrieval | False | None | False | True | False | None | False | True | 6932.2 | 2982.0 |
| cvf_029 | theory_quote | retrieval | False | None | False | True | False | None | False | True | 8619.1 | 2835.2 |
| cvf_030 | theory_quote | retrieval | False | None | False | True | False | None | False | True | 11833.1 | 5279.2 |
| cvf_031 | formula_role | retrieval | False | None | False | True | True | None | True | True | 12869.9 | 1673.3 |
| cvf_032 | formula_role | retrieval | False | None | False | True | False | None | False | True | 7621.5 | 642.2 |
| cvf_033 | reasoning | retrieval | False | None | False | True | False | None | False | True | 23487.8 | 7493.4 |
| cvf_034 | reasoning | retrieval | True | None | True | True | False | None | False | True | 7827.7 | 21036.3 |
| cvf_035 | formula_summary | retrieval | False | None | False | True | True | None | True | True | 12350.3 | 5431.1 |
| cvf_036 | formula_summary | retrieval | False | None | False | True | False | None | False | True | 12630.1 | 9178.4 |
| cvf_037 | source_text | retrieval | False | None | False | True | False | None | False | True | 7655.4 | 581.5 |
| cvf_038 | source_text | retrieval | False | None | False | True | False | None | False | True | 7519.0 | 756.1 |
| cvf_039 | book_quote | retrieval | False | None | False | True | False | None | False | True | 9562.5 | 5776.7 |
| cvf_040 | book_quote | retrieval | False | None | False | True | False | None | False | True | 6861.2 | 1387.7 |
| cvf_041 | formula_comparison | retrieval | False | None | False | True | False | None | False | True | 21771.8 | 2206.6 |
| cvf_042 | formula_comparison | retrieval | False | None | False | True | False | None | False | True | 8967.2 | 1713.0 |
| cvf_043 | herb_property | retrieval | False | None | False | True | False | None | False | True | 7014.5 | 2532.5 |
| cvf_044 | herb_property | retrieval | False | None | False | True | False | None | False | True | 6821.0 | 698.4 |
| cvf_045 | generic | retrieval | False | None | False | True | False | None | False | True | 8135.6 | 1354.2 |
| cvf_046 | generic | retrieval | False | None | False | True | False | None | False | True | 9123.5 | 7045.7 |
| cvf_047 | formula_indication | retrieval | False | None | False | True | False | None | False | True | 6944.7 | 2054.9 |
| cvf_048 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 9818.1 | 2985.7 |
| cvf_049 | book_quote | retrieval | False | None | False | True | False | None | False | True | 12038.9 | 1291.1 |
| cvf_050 | book_quote | retrieval | False | None | False | True | False | None | False | True | 8612.9 | 1346.7 |
| cvf_051 | formula_definition | retrieval | True | None | True | True | False | None | False | True | 8791.3 | 7426.5 |
| cvf_052 | book_source | retrieval | True | None | True | True | False | None | False | True | 6812.0 | 4167.6 |
| cvf_053 | herb_property | retrieval | True | None | True | True | True | None | True | True | 6825.5 | 617.9 |
| cvf_054 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 7728.0 | 3539.3 |
| cvf_055 | reasoning | retrieval | True | None | True | True | False | None | False | True | 9067.0 | 1642.9 |
| cvf_056 | formula_definition | retrieval | True | None | True | True | True | None | True | True | 7122.6 | 3590.0 |
| cvf_057 | book_quote | retrieval | True | None | True | True | False | None | False | True | 7143.5 | 1886.2 |
| cvf_058 | formula_origin | retrieval | True | None | True | True | True | None | True | True | 7281.5 | 6779.8 |
| cvf_059 | formula_definition | retrieval | True | None | True | True | False | None | False | True | 9747.7 | 4348.9 |
| cvf_060 | book_quote | retrieval | True | None | True | True | False | None | False | True | 7094.6 | 1424.2 |
| cvf_061 | formula_definition | retrieval | True | None | True | True | False | None | False | True | 7151.7 | 1970.4 |
| cvf_062 | formula_composition | retrieval | True | None | True | True | False | None | False | True | 7757.2 | 11111.8 |
| cvf_063 | reasoning | retrieval | True | None | True | True | False | None | False | True | 9799.3 | 2925.3 |
| cvf_064 | definition | retrieval | True | None | True | True | True | None | True | True | 13691.6 | 2197.7 |
| cvf_065 | formula_composition | retrieval | True | None | True | True | False | None | False | True | 7407.7 | 14658.2 |
| cvf_066 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 7328.1 | 2009.2 |
| cvf_067 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 8071.7 | 6308.2 |
| cvf_068 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 7718.8 | 1306.2 |
| cvf_069 | herb_property | retrieval | True | None | True | True | False | None | False | True | 6857.0 | 8960.0 |
| cvf_070 | formula_origin | retrieval | True | None | True | True | True | None | True | True | 8110.9 | 3576.7 |
| cvf_071 | reasoning | retrieval | True | None | True | True | True | None | True | True | 8994.8 | 2291.4 |
| cvf_072 | reasoning | retrieval | True | None | True | True | False | None | False | True | 9909.9 | 861.1 |
