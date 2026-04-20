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
| files_first_nonvector | 6862.0 | 13504.4 | 0.2889 | 0.3111 | 0.6111 | 0.6556 | 0.0889 | 0.1 | 0.2889 | 0.4556 | 0.1778 | 0.2579 | 0.6333 | 0.6365 |
| classics_vector_hybrid | 4802.1 | 13655.7 | 0.3222 | 0.4111 | 0.5778 | 0.7111 | 0.0889 | 0.1333 | 0.3667 | 0.3222 | 0.1778 | 0.1884 | 0.637 | 0.658 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 11245.5 | 2152.7 |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 4896.3 | 1465.3 |
| tcb_4a4a5c3997dc_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | False | 14961.4 | 1373.7 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 7165.8 | 2578.8 |
| tcb_8eb0acc00c51_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | False | 5824.7 | 887.8 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 5708.7 | 951.2 |
| tcb_c32415309f9c_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 14401.6 | 2766.5 |
| tcb_c32415309f9c_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 6618.1 | 3588.9 |
| tcb_50943261620b_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 5770.9 | 1177.8 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 6122.6 | 952.5 |
| tcb_b26bf7448135_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | False | 9563.9 | 2347.9 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 5077.2 | 2932.2 |
| tcb_cfc87926e240_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 5094.1 | 1810.0 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5638.8 | 3795.8 |
| tcb_91bf32d2db51_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 4903.0 | 1731.6 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 5821.5 | 862.7 |
| tcb_ec10c69b71ec_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 6532.0 | 880.5 |
| tcb_ec10c69b71ec_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 7312.6 | 1503.1 |
| tcb_633f9691b540_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | True | 7530.7 | 2782.2 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 9267.8 | 847.6 |
| tcb_700db3c80463_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 6224.5 | 1168.3 |
| tcb_700db3c80463_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 6527.9 | 5163.4 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 6982.5 | 9620.0 |
| tcb_f294b450c3a9_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 6480.3 | 4205.4 |
| tcb_ac97e3080292_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | True | 7102.0 | 3036.1 |
| tcb_ac97e3080292_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 7193.6 | 5485.4 |
| tcb_889dd6053c26_ans | formula_composition | answer_trace | False | False | False | True | True | False | True | True | 8146.8 | 1405.6 |
| tcb_889dd6053c26_src | formula_composition | source_locate | False | False | False | True | True | False | True | True | 6468.5 | 12818.5 |
| tcb_a4e18ed83cf5_ans | formula_composition | answer_trace | False | False | False | False | True | False | True | False | 7438.0 | 1549.9 |
| tcb_a4e18ed83cf5_src | formula_composition | source_locate | False | False | False | False | True | False | True | False | 7023.5 | 2982.3 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 9210.0 | 2599.3 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 7795.9 | 2341.8 |
| tcb_8b7d5252a7c4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | False | 6228.6 | 3053.1 |
| tcb_8b7d5252a7c4_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 6450.7 | 3117.3 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 7560.9 | 4245.3 |
| tcb_c9b6a12de297_src | formula_composition | source_locate | True | False | False | False | True | False | False | False | 7047.6 | 7514.8 |
| tcb_f20182fbd7fe_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 7760.9 | 2727.5 |
| tcb_f20182fbd7fe_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 16105.7 | 4026.7 |
| tcb_ac3f235205d0_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 7872.7 | 17684.0 |
| tcb_ac3f235205d0_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 6245.0 | 2393.7 |
| tcb_443cc336bdc4_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 6803.1 | 13655.7 |
| tcb_443cc336bdc4_src | formula_composition | source_locate | False | False | False | False | True | False | False | False | 8182.2 | 3150.7 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 7279.5 | 3664.7 |
| tcb_3ec534d39839_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 8060.9 | 3422.2 |
| tcb_45683ebb7cd4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 6173.0 | 11021.3 |
| tcb_45683ebb7cd4_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 5843.6 | 1388.2 |
| tcb_9a1922ea01c6_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | False | 13504.4 | 7617.4 |
| tcb_9a1922ea01c6_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | False | 7276.8 | 9700.4 |
| tcb_54e3746df3e7_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | True | 6638.7 | 3727.2 |
| tcb_54e3746df3e7_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | True | 8029.0 | 1268.1 |
| tcb_dc58e9ffe950_ans | formula_effect | answer_trace | False | False | False | False | False | False | False | False | 6556.3 | 2585.4 |
| tcb_dc58e9ffe950_src | formula_effect | source_locate | False | False | False | False | False | False | False | False | 6489.9 | 3132.1 |
| tcb_3a8a62ca1e8d_ans | formula_effect | answer_trace | False | False | False | True | False | False | False | True | 7794.7 | 919.9 |
| tcb_3a8a62ca1e8d_src | formula_effect | source_locate | False | False | False | True | False | False | False | False | 9781.2 | 2993.0 |
| tcb_c56a22b411b4_ans | formula_effect | answer_trace | True | True | True | True | True | True | True | True | 6378.2 | 6163.1 |
| tcb_c56a22b411b4_src | formula_effect | source_locate | True | True | True | True | True | True | True | True | 6384.0 | 4004.4 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | False | False | False | False | True | True | True | True | 8338.9 | 5176.9 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 8514.5 | 3956.9 |
| tcb_91327991d2cb_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2797.7 | 3920.7 |
| tcb_91327991d2cb_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 15913.6 | 2784.4 |
| tcb_63df381a166e_ans | herb_effect | answer_trace | False | False | False | False | True | True | True | True | 3078.7 | 5183.6 |
| tcb_63df381a166e_src | herb_effect | source_locate | False | False | False | False | True | True | True | True | 7102.8 | 4181.0 |
| tcb_431c6aea962b_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 2841.1 | 2704.8 |
| tcb_431c6aea962b_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 6481.9 | 7104.6 |
| tcb_e43471a1cf0e_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2835.0 | 2698.5 |
| tcb_e43471a1cf0e_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6704.3 | 20877.2 |
| tcb_2c940960356d_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2741.7 | 2711.1 |
| tcb_2c940960356d_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6485.6 | 2497.4 |
| tcb_1d14845d9935_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3298.8 | 8105.1 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6450.2 | 2547.2 |
| tcb_79ecb812a6a1_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2750.3 | 2632.2 |
| tcb_79ecb812a6a1_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6650.4 | 4465.3 |
| tcb_0eea6b4e36fc_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3144.7 | 3281.7 |
| tcb_0eea6b4e36fc_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6724.2 | 10546.8 |
| tcb_06c12f6a4138_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 3098.8 | 3436.9 |
| tcb_06c12f6a4138_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 7685.3 | 7190.4 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 7213.9 | 12121.4 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6752.6 | 7841.4 |
| tcb_0aef840312e6_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3264.2 | 2858.4 |
| tcb_0aef840312e6_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 5924.1 | 14263.4 |
| tcb_aa8592a392f3_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2769.5 | 2638.4 |
| tcb_aa8592a392f3_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 6943.0 | 4625.4 |
| tcb_b9534cb4fec8_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 5039.5 | 4885.7 |
| tcb_b9534cb4fec8_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 6171.1 | 4111.0 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 4372.5 | 4003.5 |
| tcb_556d7be9d41b_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 5190.2 | 10637.0 |
| tcb_22e18a957ac2_ans | herb_channel | answer_trace | True | True | True | True | True | True | True | True | 5526.7 | 7293.1 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | True | True | True | True | 6924.4 | 20972.9 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | False | False | False | False | 9146.2 | 6451.0 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | False | False | False | False | 6205.1 | 10539.3 |
