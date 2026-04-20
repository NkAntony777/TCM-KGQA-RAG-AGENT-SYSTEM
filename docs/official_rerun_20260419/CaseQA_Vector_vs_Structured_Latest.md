# Case QA Vector vs Structured Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\caseqa_vector_vs_structured_seed_12.json |
| top_k | 3 |
| candidate_k | 20 |
| structured_index | D:\毕业设计数据处理\langchain-miniopenclaw\backend\storage\qa_structured_index.sqlite |

## Aggregate

| Method | cases | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_precision | avg_keypoint_recall | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms | p95_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| structured_nonvector | 48 | 0.875 | 0.9375 | 0.7625 | 0.2669 | 0.5959 | 0.3372 | 0.6875 | 4174.2 | 14255.8 |
| vector_caseqa | 48 | 0.8542 | 0.9375 | 0.6844 | 0.2809 | 0.5292 | 0.3366 | 0.75 | 20152.2 | 52593.9 |

## By Category

| Category | Method | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| case_basic | structured | 0.8333 | 1.0 | 0.7 | 0.1366 | 0.5 | 5316.9 |
| case_basic | vector | 0.3333 | 0.6667 | 0.25 | 0.2034 | 0.8333 | 21319.1 |
| case_digestive | structured | 1.0 | 1.0 | 0.8 | 0.1649 | 1.0 | 10344.7 |
| case_digestive | vector | 1.0 | 1.0 | 0.5667 | 0.0898 | 0.6667 | 16975.8 |
| case_syndrome_formula | structured | 0.8333 | 0.9167 | 0.7222 | 0.2771 | 0.75 | 3043.8 |
| case_syndrome_formula | vector | 0.8333 | 0.9167 | 0.4986 | 0.2181 | 0.8333 | 29599.3 |
| compare_boundary | structured | 0.75 | 0.75 | 0.75 | 0.3232 | 0.5 | 2093.2 |
| compare_boundary | vector | 1.0 | 1.0 | 0.875 | 0.3933 | 0.75 | 10961.1 |
| formula_origin | structured | 0.8333 | 0.8333 | 0.6111 | 0.3605 | 0.8333 | 1672.9 |
| formula_origin | vector | 1.0 | 1.0 | 0.9167 | 0.4969 | 0.8333 | 13634.8 |
| formula_role | structured | 1.0 | 1.0 | 0.9445 | 0.5099 | 1.0 | 3800.8 |
| formula_role | vector | 1.0 | 1.0 | 1.0 | 0.4473 | 0.8333 | 16133.5 |
| generic_reason | structured | 1.0 | 1.0 | 0.6667 | 0.4766 | 1.0 | 5703.0 |
| generic_reason | vector | 1.0 | 1.0 | 0.6667 | 0.4014 | 0.6667 | 18523.5 |
| open_query | structured | 0.875 | 1.0 | 0.875 | 0.4503 | 0.25 | 5322.1 |
| open_query | vector | 0.875 | 1.0 | 0.8333 | 0.451 | 0.5 | 19406.3 |

## Per Case

| case_id | category | mode | structured_topk_hit | structured_keypoint_f1 | vector_topk_hit | vector_keypoint_f1 | structured_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cqv_001 | case_basic | case | True | 0.3226 | True | 0.2804 | 2385.9 | 23498.5 |
| cqv_002 | case_basic | case | True | 0.2222 | False | 0.1333 | 663.5 | 15039.7 |
| cqv_003 | case_digestive | case | True | 0.3448 | True | 0.1905 | 14255.8 | 11012.0 |
| cqv_004 | case_syndrome_formula | case | True | 0.0667 | True | 0.1481 | 150.2 | 17511.5 |
| cqv_005 | case_syndrome_formula | case | False | 0.0 | True | 0.4058 | 36.0 | 9491.0 |
| cqv_006 | formula_role | qa | True | 0.5143 | True | 0.4275 | 2520.2 | 8323.6 |
| cqv_007 | formula_origin | qa | True | 0.5 | True | 0.5 | 741.4 | 6113.0 |
| cqv_008 | formula_origin | qa | True | 0.1481 | True | 0.5 | 604.9 | 4923.7 |
| cqv_009 | generic_reason | qa | True | 0.4138 | True | 0.5 | 7754.8 | 2144.2 |
| cqv_010 | compare_boundary | qa | True | 0.5479 | True | 0.7097 | 854.6 | 10888.6 |
| cqv_011 | open_query | qa | True | 0.6557 | True | 0.4275 | 7829.1 | 12743.1 |
| cqv_012 | open_query | qa | True | 0.1667 | True | 0.125 | 467.4 | 18435.3 |
| cqv_013 | case_basic | case | True | 0.0714 | True | 0.4444 | 18360.2 | 7715.9 |
| cqv_014 | case_basic | case | True | 0.0781 | True | 0.08 | 3851.5 | 1433.3 |
| cqv_015 | case_digestive | case | True | 0.0 | True | 0.0 | 1586.4 | 11390.2 |
| cqv_016 | case_digestive | case | True | 0.15 | True | 0.0789 | 15191.8 | 28525.1 |
| cqv_017 | case_syndrome_formula | case | True | 0.15 | True | 0.5288 | 7977.4 | 19147.8 |
| cqv_018 | case_syndrome_formula | case | True | 0.2632 | True | 0.3571 | 3238.0 | 7465.0 |
| cqv_019 | case_syndrome_formula | case | True | 0.3684 | True | 0.0781 | 1451.8 | 12203.7 |
| cqv_020 | case_syndrome_formula | case | True | 0.3352 | True | 0.1395 | 1650.6 | 33113.2 |
| cqv_021 | formula_role | qa | True | 0.375 | True | 0.4242 | 2571.9 | 17731.8 |
| cqv_022 | formula_role | qa | True | 0.5854 | True | 0.5714 | 2550.1 | 17953.8 |
| cqv_023 | formula_origin | qa | True | 0.6667 | True | 0.8 | 912.1 | 12141.0 |
| cqv_024 | formula_origin | qa | False | 0.0 | True | 0.4286 | 1368.5 | 8974.5 |
| cqv_025 | compare_boundary | qa | True | 0.3448 | True | 0.4706 | 2936.1 | 10109.9 |
| cqv_026 | compare_boundary | qa | False | 0.0 | True | 0.25 | 2414.1 | 13676.7 |
| cqv_027 | open_query | qa | True | 0.3077 | True | 0.6519 | 8177.9 | 25084.2 |
| cqv_028 | open_query | qa | True | 0.5854 | True | 0.5593 | 7359.9 | 13449.7 |
| cqv_029 | generic_reason | qa | True | 0.5053 | True | 0.5 | 1464.5 | 14680.2 |
| cqv_030 | generic_reason | qa | True | 0.5106 | True | 0.2041 | 7889.8 | 38746.0 |
| cqv_031 | case_basic | case | True | 0.0 | True | 0.2051 | 4595.7 | 76202.9 |
| cqv_032 | case_basic | case | True | 0.125 | False | 0.0769 | 2044.4 | 4024.5 |
| cqv_033 | formula_role | qa | True | 0.4615 | True | 0.2609 | 2667.3 | 5071.5 |
| cqv_034 | open_query | qa | True | 0.42 | True | 0.5217 | 1128.0 | 20585.1 |
| cqv_035 | formula_origin | qa | True | 0.6061 | True | 0.3684 | 1335.5 | 21549.2 |
| cqv_036 | formula_role | qa | True | 0.6566 | True | 0.7857 | 3608.4 | 33724.1 |
| cqv_037 | compare_boundary | qa | True | 0.4 | True | 0.1429 | 2168.1 | 9169.1 |
| cqv_038 | formula_origin | qa | True | 0.2424 | True | 0.3846 | 5075.2 | 28107.2 |
| cqv_039 | open_query | qa | True | 0.433 | True | 0.4752 | 8973.5 | 30562.2 |
| cqv_040 | open_query | qa | True | 0.7143 | True | 0.5393 | 1226.5 | 9466.3 |
| cqv_041 | case_syndrome_formula | case | True | 0.5275 | True | 0.1449 | 1156.5 | 30574.4 |
| cqv_042 | case_syndrome_formula | case | True | 0.5455 | True | 0.1471 | 3468.9 | 26933.6 |
| cqv_043 | case_syndrome_formula | case | True | 0.1818 | False | 0.0645 | 1556.0 | 52593.9 |
| cqv_044 | case_syndrome_formula | case | True | 0.4406 | True | 0.3636 | 1345.9 | 38963.2 |
| cqv_045 | case_syndrome_formula | case | True | 0.3684 | True | 0.0 | 1741.9 | 62555.7 |
| cqv_046 | case_syndrome_formula | case | True | 0.0779 | True | 0.24 | 12751.9 | 44638.4 |
| cqv_047 | formula_role | qa | True | 0.4667 | True | 0.2143 | 8886.9 | 13996.0 |
| cqv_048 | open_query | qa | True | 0.32 | True | 0.3077 | 7414.9 | 24924.5 |
