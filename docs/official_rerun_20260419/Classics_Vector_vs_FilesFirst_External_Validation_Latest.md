# Classics Vector vs Files-First Experiment

## Overview

| Field | Value |
| --- | --- |
| dataset | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\datasets\paper\classics_vector_vs_filesfirst_external_validation_12.json |
| top_k | 3 |
| candidate_k | 20 |

## Aggregate

| Method | avg_latency_ms | p95_latency_ms | top1_book | topk_book | top1_chapter | topk_chapter | top1_evidence | topk_evidence | topk_provenance | topk_answer | topk_answer+prov | avg_answer_recall | avg_source_mrr | avg_source_ndcg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| files_first_nonvector | 11649.5 | 17634.5 | 0.4583 | 0.6667 | None | None | None | None | 0.6667 | 0.875 | 0.5833 | 0.7604 | 0.5417 | 0.5667 |
| classics_vector_hybrid | 5207.4 | 6755.5 | 0.0833 | 0.2083 | None | None | None | None | 0.2083 | 0.875 | 0.1667 | 0.5799 | 0.1389 | 0.1567 |

## Per Case

| case_id | category | task_family | files_first_topk_book | files_first_topk_evidence | files_first_topk_prov | files_first_topk_answer | vector_topk_book | vector_topk_evidence | vector_topk_prov | vector_topk_answer | files_first_latency | vector_latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| cvf_e301 | formula_reverse_lookup | retrieval | False | None | False | True | False | None | False | True | 18395.5 | 6320.8 |
| cvf_e302 | formula_indication | retrieval | True | None | True | True | True | None | True | True | 10751.9 | 5091.9 |
| cvf_e303 | formula_explanation | retrieval | True | None | True | False | True | None | True | False | 13882.7 | 531.1 |
| cvf_e304 | herb_property | retrieval | False | None | False | True | True | None | True | True | 9508.2 | 6708.7 |
| cvf_e305 | herb_property | retrieval | False | None | False | True | False | None | False | True | 8992.0 | 4648.9 |
| cvf_e306 | formula_alias | retrieval | True | None | True | True | False | None | False | False | 6709.4 | 5519.7 |
| cvf_e307 | formula_indication | retrieval | False | None | False | True | False | None | False | True | 9682.9 | 6755.5 |
| cvf_e308 | formula_reverse_lookup | retrieval | True | None | True | True | False | None | False | False | 9318.1 | 4861.2 |
| cvf_e309 | theory_summary | retrieval | True | None | True | True | False | None | False | True | 10271.9 | 5543.1 |
| cvf_e310 | formula_indication | retrieval | True | None | True | False | False | None | False | True | 13158.3 | 6192.2 |
| cvf_e311 | theory_summary | retrieval | False | None | False | False | True | None | True | True | 12183.7 | 6316.3 |
| cvf_e312 | formula_definition | retrieval | False | None | False | True | False | None | False | True | 13642.6 | 3812.2 |
| cvf_e313 | formula_reverse_lookup | retrieval | True | None | True | True | False | None | False | True | 10010.3 | 3960.2 |
| cvf_e314 | formula_reverse_lookup | retrieval | True | None | True | True | False | None | False | True | 10497.7 | 1675.1 |
| cvf_e315 | formula_reverse_lookup | retrieval | False | None | False | True | False | None | False | True | 12621.0 | 5403.1 |
| cvf_e316 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 12874.2 | 21121.6 |
| cvf_e317 | herb_property | retrieval | True | None | True | True | True | None | True | True | 17634.5 | 6215.8 |
| cvf_e318 | herb_property | retrieval | True | None | True | True | False | None | False | True | 7971.7 | 1232.4 |
| cvf_e319 | herb_property | retrieval | True | None | True | True | False | None | False | True | 8938.1 | 4274.5 |
| cvf_e320 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 13104.6 | 5697.0 |
| cvf_e321 | formula_reverse_lookup | retrieval | True | None | True | True | False | None | False | True | 10305.5 | 3022.3 |
| cvf_e322 | formula_indication | retrieval | True | None | True | True | False | None | False | True | 14496.4 | 5341.4 |
| cvf_e323 | formula_reverse_lookup | retrieval | False | None | False | True | False | None | False | True | 11749.0 | 4235.4 |
| cvf_e324 | theory_summary | retrieval | True | None | True | True | False | None | False | True | 12888.9 | 496.7 |
