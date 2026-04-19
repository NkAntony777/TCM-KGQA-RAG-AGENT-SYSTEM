# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\traceable_classics_benchmark_test.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 3773.6 | 7927.3 | 0.1889 | 0.2222 | 0.4556 | 0.5333 | 0.0667 | 0.1 | 0.1 | 0.3889 | 0.1 | 0.2125 | 0.4926 | 0.5023 |
| classics_vector_hybrid | 3620.4 | 13597.7 | 0.3222 | 0.4111 | 0.5778 | 0.7111 | 0.0889 | 0.1333 | 0.1333 | 0.3222 | 0.1333 | 0.1884 | 0.637 | 0.658 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 16083.0 | 5808.9 |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1461.3 | 1327.0 |
| tcb_4a4a5c3997dc_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 5923.8 | 1389.3 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 3547.4 | 18731.4 |
| tcb_8eb0acc00c51_ans | formula_composition | answer_trace | True | False | False | True | True | False | False | False | 4368.7 | 1307.9 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1407.2 | 812.6 |
| tcb_c32415309f9c_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | True | 5476.9 | 4251.7 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 3560.2 | 3198.6 |
| tcb_50943261620b_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 3514.9 | 3703.8 |
| tcb_50943261620b_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1381.0 | 927.1 |
| tcb_b26bf7448135_ans | formula_composition | answer_trace | True | False | False | True | True | False | False | False | 4322.5 | 8749.6 |
| tcb_b26bf7448135_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1417.6 | 1262.3 |
| tcb_cfc87926e240_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 4301.8 | 2501.9 |
| tcb_cfc87926e240_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1393.7 | 1271.2 |
| tcb_91bf32d2db51_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 4334.9 | 1220.9 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1419.1 | 1290.6 |
| tcb_ec10c69b71ec_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 4404.5 | 1214.1 |
| tcb_ec10c69b71ec_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 1327.4 | 2338.1 |
| tcb_633f9691b540_ans | formula_composition | answer_trace | True | False | False | True | True | False | False | True | 4331.7 | 1039.2 |
| tcb_633f9691b540_src | formula_composition | source_locate | False | False | False | True | True | False | False | True | 1431.3 | 1370.9 |
| tcb_700db3c80463_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 2803.7 | 1117.5 |
| tcb_700db3c80463_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 964.5 | 1222.9 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 2837.2 | 13597.7 |
| tcb_f294b450c3a9_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 1254.2 | 7574.8 |
| tcb_ac97e3080292_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | True | 3239.8 | 1940.1 |
| tcb_ac97e3080292_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 1237.2 | 1487.3 |
| tcb_889dd6053c26_ans | formula_composition | answer_trace | False | False | False | True | True | False | False | True | 3749.6 | 1435.6 |
| tcb_889dd6053c26_src | formula_composition | source_locate | False | False | False | True | True | False | False | True | 1298.9 | 1457.3 |
| tcb_a4e18ed83cf5_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 3986.1 | 1432.3 |
| tcb_a4e18ed83cf5_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1315.4 | 1399.6 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 4350.8 | 4997.2 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1300.1 | 4291.4 |
| tcb_8b7d5252a7c4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | False | 3420.5 | 1908.8 |
| tcb_8b7d5252a7c4_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 1239.9 | 830.3 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 2833.4 | 3182.8 |
| tcb_c9b6a12de297_src | formula_composition | source_locate | True | False | False | False | True | False | False | False | 1244.7 | 4071.5 |
| tcb_f20182fbd7fe_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 3158.0 | 953.9 |
| tcb_f20182fbd7fe_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 940.1 | 1477.9 |
| tcb_ac3f235205d0_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 4140.0 | 1120.6 |
| tcb_ac3f235205d0_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 1270.0 | 888.5 |
| tcb_443cc336bdc4_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 4312.8 | 1031.7 |
| tcb_443cc336bdc4_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 1329.7 | 756.4 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 2978.7 | 4228.6 |
| tcb_3ec534d39839_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 1410.9 | 2508.2 |
| tcb_45683ebb7cd4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 2828.5 | 1658.0 |
| tcb_45683ebb7cd4_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 952.1 | 771.1 |
| tcb_9a1922ea01c6_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | False | 5986.8 | 748.3 |
| tcb_9a1922ea01c6_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | False | 1257.2 | 778.7 |
| tcb_54e3746df3e7_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | True | 4469.2 | 1091.9 |
| tcb_54e3746df3e7_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | True | 1199.2 | 919.5 |
| tcb_dc58e9ffe950_ans | formula_effect | answer_trace | False | False | False | False | False | False | False | False | 2751.1 | 2595.4 |
| tcb_dc58e9ffe950_src | formula_effect | source_locate | False | False | False | False | False | False | False | False | 1969.7 | 2365.9 |
| tcb_3a8a62ca1e8d_ans | formula_effect | answer_trace | False | False | False | True | False | False | False | True | 3005.5 | 1315.6 |
| tcb_3a8a62ca1e8d_src | formula_effect | source_locate | False | False | False | True | False | False | False | False | 999.3 | 762.6 |
| tcb_c56a22b411b4_ans | formula_effect | answer_trace | True | True | True | True | True | True | True | True | 2891.6 | 4733.4 |
| tcb_c56a22b411b4_src | formula_effect | source_locate | True | True | True | True | True | True | True | True | 1246.7 | 3038.4 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | True | True | True | True | True | True | True | True | 5681.4 | 3779.1 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 2237.5 | 2725.5 |
| tcb_91327991d2cb_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2904.3 | 2567.8 |
| tcb_91327991d2cb_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6376.8 | 6490.5 |
| tcb_63df381a166e_ans | herb_effect | answer_trace | False | False | False | False | True | True | True | True | 3222.2 | 2649.2 |
| tcb_63df381a166e_src | herb_effect | source_locate | False | False | False | False | True | True | True | True | 5439.6 | 3264.9 |
| tcb_431c6aea962b_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 2861.1 | 2524.5 |
| tcb_431c6aea962b_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 6889.2 | 8654.0 |
| tcb_e43471a1cf0e_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2882.4 | 18377.9 |
| tcb_e43471a1cf0e_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7927.3 | 22653.5 |
| tcb_2c940960356d_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2813.6 | 2896.0 |
| tcb_2c940960356d_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6532.9 | 2651.4 |
| tcb_1d14845d9935_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3482.3 | 2584.1 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 4204.2 | 2882.6 |
| tcb_79ecb812a6a1_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2807.5 | 6250.0 |
| tcb_79ecb812a6a1_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 5376.4 | 4677.0 |
| tcb_0eea6b4e36fc_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3300.9 | 3372.8 |
| tcb_0eea6b4e36fc_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 12263.8 | 6215.6 |
| tcb_06c12f6a4138_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 3395.9 | 2934.1 |
| tcb_06c12f6a4138_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 5147.1 | 4004.2 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7447.4 | 3226.2 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 8840.7 | 2563.8 |
| tcb_0aef840312e6_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3308.1 | 2657.6 |
| tcb_0aef840312e6_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 3711.9 | 2164.2 |
| tcb_aa8592a392f3_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2870.6 | 2564.5 |
| tcb_aa8592a392f3_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 4291.2 | 3551.1 |
| tcb_b9534cb4fec8_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 6186.0 | 3206.0 |
| tcb_b9534cb4fec8_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 1986.1 | 3618.7 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4763.1 | 3132.2 |
| tcb_556d7be9d41b_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 6299.5 | 4668.3 |
| tcb_22e18a957ac2_ans | herb_channel | answer_trace | True | True | True | True | True | True | True | True | 5521.8 | 16568.7 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | False | False | False | False | True | True | True | True | 3377.8 | 8144.2 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | False | False | False | False | False | 7001.0 | 4710.1 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | False | False | False | False | False | 16692.6 | 3497.3 |
