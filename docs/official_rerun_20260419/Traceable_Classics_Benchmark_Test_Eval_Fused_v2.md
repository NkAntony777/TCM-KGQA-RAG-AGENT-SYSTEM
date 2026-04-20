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
| files_first_nonvector | 9446.3 | 15747.1 | 0.2778 | 0.3333 | 0.5778 | 0.6667 | 0.0778 | 0.1111 | 0.2889 | 0.4444 | 0.1778 | 0.2505 | 0.6222 | 0.6335 |
| classics_vector_hybrid | 6535.9 | 20481.1 | 0.3111 | 0.3889 | 0.5778 | 0.6778 | 0.0889 | 0.0889 | 0.3111 | 0.4444 | 0.1778 | 0.2496 | 0.6222 | 0.637 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| tcb_432ab8d9b2c4_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 21529.8 | 1978.2 |
| tcb_432ab8d9b2c4_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 7739.0 | 1900.7 |
| tcb_4a4a5c3997dc_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | False | 7852.1 | 51411.6 |
| tcb_4a4a5c3997dc_src | formula_composition | source_locate | False | False | False | True | False | False | False | False | 7281.1 | 5463.9 |
| tcb_8eb0acc00c51_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | True | 9911.8 | 2041.4 |
| tcb_8eb0acc00c51_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 9805.4 | 12459.2 |
| tcb_c32415309f9c_ans | formula_composition | answer_trace | True | False | False | False | False | False | False | False | 10079.8 | 11191.4 |
| tcb_c32415309f9c_src | formula_composition | source_locate | True | False | False | False | False | False | False | True | 9804.2 | 2278.5 |
| tcb_50943261620b_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 9524.9 | 2459.3 |
| tcb_50943261620b_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 7600.3 | 1932.5 |
| tcb_b26bf7448135_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | False | 6769.3 | 3929.6 |
| tcb_b26bf7448135_src | formula_composition | source_locate | True | False | True | True | True | False | True | False | 8038.9 | 1858.9 |
| tcb_cfc87926e240_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 7679.4 | 1971.0 |
| tcb_cfc87926e240_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 10996.6 | 1925.6 |
| tcb_91bf32d2db51_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 8061.4 | 2042.6 |
| tcb_91bf32d2db51_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 15747.1 | 5952.3 |
| tcb_ec10c69b71ec_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 12010.7 | 2243.6 |
| tcb_ec10c69b71ec_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 11166.1 | 1861.2 |
| tcb_633f9691b540_ans | formula_composition | answer_trace | True | False | True | True | True | False | True | True | 17614.6 | 1932.5 |
| tcb_633f9691b540_src | formula_composition | source_locate | True | False | True | True | True | False | True | True | 17054.8 | 14430.3 |
| tcb_700db3c80463_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | True | 9935.6 | 13525.0 |
| tcb_700db3c80463_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 10109.5 | 3408.8 |
| tcb_f294b450c3a9_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 6441.2 | 7539.4 |
| tcb_f294b450c3a9_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 6819.8 | 12486.5 |
| tcb_ac97e3080292_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 11776.3 | 5103.5 |
| tcb_ac97e3080292_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 10937.1 | 1948.2 |
| tcb_889dd6053c26_ans | formula_composition | answer_trace | False | False | False | True | True | False | True | True | 10985.3 | 2830.7 |
| tcb_889dd6053c26_src | formula_composition | source_locate | False | False | False | True | True | False | True | True | 12638.3 | 6540.6 |
| tcb_a4e18ed83cf5_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | True | 12386.5 | 1904.7 |
| tcb_a4e18ed83cf5_src | formula_composition | source_locate | False | False | False | False | False | False | False | True | 11376.0 | 12186.5 |
| tcb_f6e60ecfa98e_ans | formula_composition | answer_trace | True | False | True | False | True | False | True | False | 12559.7 | 4770.8 |
| tcb_f6e60ecfa98e_src | formula_composition | source_locate | True | False | True | False | True | False | True | False | 12370.1 | 3977.2 |
| tcb_8b7d5252a7c4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 14235.7 | 1982.4 |
| tcb_8b7d5252a7c4_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 11059.5 | 1957.8 |
| tcb_c9b6a12de297_ans | formula_composition | answer_trace | True | False | False | False | True | False | False | False | 10268.2 | 8248.7 |
| tcb_c9b6a12de297_src | formula_composition | source_locate | True | False | False | False | True | False | False | False | 10507.8 | 8789.8 |
| tcb_f20182fbd7fe_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 11271.0 | 2186.6 |
| tcb_f20182fbd7fe_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 12494.9 | 1822.2 |
| tcb_ac3f235205d0_ans | formula_composition | answer_trace | False | False | False | False | False | False | False | False | 12558.2 | 1838.9 |
| tcb_ac3f235205d0_src | formula_composition | source_locate | False | False | False | False | False | False | False | False | 13321.6 | 1861.3 |
| tcb_443cc336bdc4_ans | formula_composition | answer_trace | False | False | False | False | True | False | False | False | 14726.5 | 1913.6 |
| tcb_443cc336bdc4_src | formula_composition | source_locate | False | False | False | False | True | False | False | True | 11565.0 | 15199.5 |
| tcb_3ec534d39839_ans | formula_composition | answer_trace | True | True | True | True | True | True | True | True | 8682.8 | 5930.7 |
| tcb_3ec534d39839_src | formula_composition | source_locate | True | True | True | True | True | True | True | True | 8830.6 | 5886.5 |
| tcb_45683ebb7cd4_ans | formula_composition | answer_trace | False | False | False | True | False | False | False | True | 11633.5 | 2379.4 |
| tcb_45683ebb7cd4_src | formula_composition | source_locate | False | False | False | True | False | False | False | True | 10629.9 | 8609.6 |
| tcb_9a1922ea01c6_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | True | 12260.9 | 20481.1 |
| tcb_9a1922ea01c6_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | True | 11567.3 | 1686.4 |
| tcb_54e3746df3e7_ans | formula_indication_symptom | answer_trace | False | False | False | True | False | False | False | True | 11350.1 | 2059.1 |
| tcb_54e3746df3e7_src | formula_indication_symptom | source_locate | False | False | False | True | False | False | False | True | 16900.7 | 2517.5 |
| tcb_dc58e9ffe950_ans | formula_effect | answer_trace | False | False | False | False | False | False | False | False | 11753.0 | 48739.1 |
| tcb_dc58e9ffe950_src | formula_effect | source_locate | False | False | False | False | False | False | False | False | 14472.8 | 2352.1 |
| tcb_3a8a62ca1e8d_ans | formula_effect | answer_trace | False | False | False | True | False | False | False | True | 11684.4 | 1167.4 |
| tcb_3a8a62ca1e8d_src | formula_effect | source_locate | False | False | False | True | False | False | False | True | 11856.3 | 1154.5 |
| tcb_c56a22b411b4_ans | formula_effect | answer_trace | True | True | True | True | True | True | True | True | 10671.3 | 4901.1 |
| tcb_c56a22b411b4_src | formula_effect | source_locate | True | True | True | True | True | True | True | True | 10924.6 | 7393.9 |
| tcb_6d98aea0c9f2_ans | formula_method | answer_trace | True | True | True | True | True | True | True | True | 9642.4 | 4794.8 |
| tcb_6d98aea0c9f2_src | formula_method | source_locate | True | True | True | True | True | True | True | True | 11820.4 | 4946.1 |
| tcb_91327991d2cb_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2926.9 | 2506.7 |
| tcb_91327991d2cb_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7375.7 | 2614.7 |
| tcb_63df381a166e_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3401.3 | 2827.9 |
| tcb_63df381a166e_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7711.4 | 2697.4 |
| tcb_431c6aea962b_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | True | 2955.7 | 22927.3 |
| tcb_431c6aea962b_src | herb_effect | source_locate | False | False | False | True | False | False | False | True | 6504.6 | 4553.2 |
| tcb_e43471a1cf0e_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2931.0 | 2692.1 |
| tcb_e43471a1cf0e_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 7622.4 | 2512.6 |
| tcb_2c940960356d_ans | herb_effect | answer_trace | False | False | False | False | True | False | False | False | 2949.4 | 2488.8 |
| tcb_2c940960356d_src | herb_effect | source_locate | False | False | False | False | True | False | False | False | 8383.5 | 49298.7 |
| tcb_1d14845d9935_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3608.7 | 2720.2 |
| tcb_1d14845d9935_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 8787.3 | 13648.2 |
| tcb_79ecb812a6a1_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 2893.9 | 2616.7 |
| tcb_79ecb812a6a1_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 8236.0 | 2826.6 |
| tcb_0eea6b4e36fc_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 3380.7 | 2608.3 |
| tcb_0eea6b4e36fc_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 10047.3 | 5195.1 |
| tcb_06c12f6a4138_ans | herb_effect | answer_trace | False | False | False | True | False | False | False | False | 3267.7 | 2809.9 |
| tcb_06c12f6a4138_src | herb_effect | source_locate | False | False | False | True | False | False | False | False | 8407.9 | 2736.7 |
| tcb_9b00e8ff191a_ans | herb_effect | answer_trace | False | False | False | False | True | False | False | False | 3745.9 | 2662.5 |
| tcb_9b00e8ff191a_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 8816.9 | 3745.7 |
| tcb_0aef840312e6_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | False | 6472.7 | 5180.7 |
| tcb_0aef840312e6_src | herb_effect | source_locate | False | False | False | False | False | False | False | False | 8017.3 | 5638.3 |
| tcb_aa8592a392f3_ans | herb_effect | answer_trace | False | False | False | False | False | False | False | True | 3022.5 | 2646.1 |
| tcb_aa8592a392f3_src | herb_effect | source_locate | False | False | False | False | False | False | False | True | 9032.8 | 2755.0 |
| tcb_b9534cb4fec8_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 7407.4 | 8800.3 |
| tcb_b9534cb4fec8_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 5995.8 | 3738.5 |
| tcb_556d7be9d41b_ans | herb_channel | answer_trace | False | False | False | False | False | False | False | False | 6574.1 | 5900.6 |
| tcb_556d7be9d41b_src | herb_channel | source_locate | False | False | False | False | False | False | False | False | 6252.6 | 3621.1 |
| tcb_22e18a957ac2_ans | herb_channel | answer_trace | True | True | True | True | False | False | False | False | 8505.0 | 5387.8 |
| tcb_22e18a957ac2_src | herb_channel | source_locate | True | True | True | True | False | False | False | False | 6034.7 | 19351.8 |
| tcb_89d570c7a54e_ans | entity_alias | answer_trace | False | False | False | True | True | False | True | True | 8307.0 | 5972.8 |
| tcb_89d570c7a54e_src | entity_alias | source_locate | False | False | False | True | True | False | True | True | 9294.4 | 4259.4 |
