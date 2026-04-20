# Case QA Vector vs Structured Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\caseqa_vector_vs_structured_seed_12.json |
| top_k | 3 |
| candidate_k | 12 |
| structured_index | D:\毕业设计数据处理\langchain-miniopenclaw\backend\storage\qa_structured_index.sqlite |

## Aggregate

| Method | cases | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_precision | avg_keypoint_recall | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms | p95_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| structured_nonvector | 48 | 0.875 | 0.9375 | 0.7625 | 0.2669 | 0.5959 | 0.3372 | 0.6875 | 4006.1 | 13871.5 |
| vector_caseqa | 48 | 0.8542 | 0.9167 | 0.6615 | 0.2799 | 0.5043 | 0.3314 | 0.7292 | 11923.1 | 25506.1 |

## By Category

| Category | Method | top1_hit_rate | topk_hit_rate | avg_coverage_any | avg_keypoint_f1 | preferred_hit_rate | avg_latency_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| case_basic | structured | 0.8333 | 1.0 | 0.7 | 0.1366 | 0.5 | 5564.9 |
| case_basic | vector | 0.3333 | 0.5 | 0.2167 | 0.1683 | 0.6667 | 14115.6 |
| case_digestive | structured | 1.0 | 1.0 | 0.8 | 0.1649 | 1.0 | 10192.2 |
| case_digestive | vector | 1.0 | 1.0 | 0.4333 | 0.0885 | 0.6667 | 17688.6 |
| case_syndrome_formula | structured | 0.8333 | 0.9167 | 0.7222 | 0.2771 | 0.75 | 2919.3 |
| case_syndrome_formula | vector | 0.8333 | 0.9167 | 0.4986 | 0.2181 | 0.8333 | 13863.0 |
| compare_boundary | structured | 0.75 | 0.75 | 0.75 | 0.3232 | 0.5 | 2130.0 |
| compare_boundary | vector | 1.0 | 1.0 | 0.875 | 0.3933 | 0.75 | 10854.5 |
| formula_origin | structured | 0.8333 | 0.8333 | 0.6111 | 0.3605 | 0.8333 | 1522.2 |
| formula_origin | vector | 1.0 | 1.0 | 0.8333 | 0.4689 | 0.8333 | 9899.6 |
| formula_role | structured | 1.0 | 1.0 | 0.9445 | 0.5099 | 1.0 | 3606.5 |
| formula_role | vector | 1.0 | 1.0 | 1.0 | 0.4695 | 0.8333 | 8768.9 |
| generic_reason | structured | 1.0 | 1.0 | 0.6667 | 0.4766 | 1.0 | 5117.8 |
| generic_reason | vector | 1.0 | 1.0 | 0.6667 | 0.4014 | 0.6667 | 7143.2 |
| open_query | structured | 0.875 | 1.0 | 0.875 | 0.4503 | 0.25 | 4831.3 |
| open_query | vector | 0.875 | 1.0 | 0.8333 | 0.451 | 0.5 | 11416.9 |

## Per Case

| case_id | category | mode | structured_topk_hit | structured_keypoint_f1 | vector_topk_hit | vector_keypoint_f1 | structured_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cqv_001 | case_basic | case | True | 0.3226 | True | 0.2804 | 2383.7 | 25506.1 |
| cqv_002 | case_basic | case | True | 0.2222 | False | 0.1333 | 671.7 | 15889.9 |
| cqv_003 | case_digestive | case | True | 0.3448 | True | 0.1905 | 13871.5 | 16080.5 |
| cqv_004 | case_syndrome_formula | case | True | 0.0667 | True | 0.1481 | 210.8 | 562.7 |
| cqv_005 | case_syndrome_formula | case | False | 0.0 | True | 0.4058 | 47.4 | 10561.1 |
| cqv_006 | formula_role | qa | True | 0.5143 | True | 0.4275 | 2646.5 | 6732.5 |
| cqv_007 | formula_origin | qa | True | 0.5 | True | 0.5 | 704.5 | 3505.8 |
| cqv_008 | formula_origin | qa | True | 0.1481 | True | 0.5 | 734.7 | 6857.2 |
| cqv_009 | generic_reason | qa | True | 0.4138 | True | 0.5 | 7545.1 | 6062.5 |
| cqv_010 | compare_boundary | qa | True | 0.5479 | True | 0.7097 | 782.7 | 8330.6 |
| cqv_011 | open_query | qa | True | 0.6557 | True | 0.4275 | 7556.2 | 6283.8 |
| cqv_012 | open_query | qa | True | 0.1667 | True | 0.125 | 413.8 | 23174.4 |
| cqv_013 | case_basic | case | True | 0.0714 | True | 0.4444 | 18778.8 | 5811.7 |
| cqv_014 | case_basic | case | True | 0.0781 | True | 0.08 | 4125.2 | 1335.2 |
| cqv_015 | case_digestive | case | True | 0.0 | True | 0.0 | 1575.2 | 13667.4 |
| cqv_016 | case_digestive | case | True | 0.15 | True | 0.075 | 15130.0 | 23318.0 |
| cqv_017 | case_syndrome_formula | case | True | 0.15 | True | 0.5288 | 7571.5 | 16346.8 |
| cqv_018 | case_syndrome_formula | case | True | 0.2632 | True | 0.3571 | 3044.8 | 5931.0 |
| cqv_019 | case_syndrome_formula | case | True | 0.3684 | True | 0.0781 | 1460.8 | 9473.3 |
| cqv_020 | case_syndrome_formula | case | True | 0.3352 | True | 0.1395 | 1295.8 | 26004.8 |
| cqv_021 | formula_role | qa | True | 0.375 | True | 0.4242 | 2248.3 | 20980.3 |
| cqv_022 | formula_role | qa | True | 0.5854 | True | 0.5714 | 2498.6 | 3046.0 |
| cqv_023 | formula_origin | qa | True | 0.6667 | True | 0.8 | 864.0 | 18333.4 |
| cqv_024 | formula_origin | qa | False | 0.0 | True | 0.4286 | 1457.7 | 5900.2 |
| cqv_025 | compare_boundary | qa | True | 0.3448 | True | 0.4706 | 3000.7 | 9545.3 |
| cqv_026 | compare_boundary | qa | False | 0.0 | True | 0.25 | 2625.0 | 19337.5 |
| cqv_027 | open_query | qa | True | 0.3077 | True | 0.6519 | 7871.1 | 7076.6 |
| cqv_028 | open_query | qa | True | 0.5854 | True | 0.5593 | 5086.4 | 12176.3 |
| cqv_029 | generic_reason | qa | True | 0.5053 | True | 0.5 | 1448.7 | 4800.5 |
| cqv_030 | generic_reason | qa | True | 0.5106 | True | 0.2041 | 6359.5 | 10566.5 |
| cqv_031 | case_basic | case | True | 0.0 | False | 0.0 | 4453.0 | 21405.3 |
| cqv_032 | case_basic | case | True | 0.125 | False | 0.0714 | 2977.2 | 14745.6 |
| cqv_033 | formula_role | qa | True | 0.4615 | True | 0.2609 | 2627.0 | 6474.4 |
| cqv_034 | open_query | qa | True | 0.42 | True | 0.5217 | 1125.6 | 17655.9 |
| cqv_035 | formula_origin | qa | True | 0.6061 | True | 0.2 | 1313.0 | 6367.8 |
| cqv_036 | formula_role | qa | True | 0.6566 | True | 0.9189 | 3065.0 | 8877.8 |
| cqv_037 | compare_boundary | qa | True | 0.4 | True | 0.1429 | 2111.6 | 6204.6 |
| cqv_038 | formula_origin | qa | True | 0.2424 | True | 0.3846 | 4059.2 | 18433.0 |
| cqv_039 | open_query | qa | True | 0.433 | True | 0.4752 | 8740.9 | 10810.2 |
| cqv_040 | open_query | qa | True | 0.7143 | True | 0.5393 | 1199.4 | 8737.1 |
| cqv_041 | case_syndrome_formula | case | True | 0.5275 | True | 0.1449 | 1086.1 | 17459.8 |
| cqv_042 | case_syndrome_formula | case | True | 0.5455 | True | 0.1471 | 3312.0 | 28147.8 |
| cqv_043 | case_syndrome_formula | case | True | 0.1818 | False | 0.0645 | 1477.5 | 9769.6 |
| cqv_044 | case_syndrome_formula | case | True | 0.4406 | True | 0.3636 | 1250.1 | 5620.6 |
| cqv_045 | case_syndrome_formula | case | True | 0.3684 | True | 0.0 | 1629.6 | 21435.2 |
| cqv_046 | case_syndrome_formula | case | True | 0.0779 | True | 0.24 | 12645.8 | 15043.9 |
| cqv_047 | formula_role | qa | True | 0.4667 | True | 0.2143 | 8553.7 | 6502.4 |
| cqv_048 | open_query | qa | True | 0.32 | True | 0.3077 | 6657.2 | 5421.0 |
