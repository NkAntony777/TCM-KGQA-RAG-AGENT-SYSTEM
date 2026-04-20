# Paper Experiment Rerun Summary

更新时间：2026-04-19

## 1. 本次正式重跑范围

本次重跑只覆盖当前论文主张直接依赖的实验，不包含历史路径查询 benchmark、临时 debug 导出和失败案例整理脚本。

本次正式重跑包含：

1. 病例 QA 主实验
2. 古籍主实验
3. 古籍外部验证
4. 古籍 baseline matrix
5. 古籍 baseline matrix 外部验证
6. files-first 内部消融
7. traceable benchmark 严格评测
8. traceable benchmark 重打分评测

## 2. 核心结果

### 2.1 病例 QA 主实验

- structured:
  - `top1_hit_rate = 0.875`
  - `topk_hit_rate = 0.9375`
  - `avg_coverage_any = 0.7625`
  - `avg_latency_ms = 4174.2`
- vector:
  - `top1_hit_rate = 0.8542`
  - `topk_hit_rate = 0.9375`
  - `avg_coverage_any = 0.6844`
  - `avg_latency_ms = 20152.2`

结论：

- 结构化非向量在病例 QA 主实验上整体优于旧向量链路
- 在命中率接近的情况下，延迟优势非常明显

### 2.2 古籍主实验

- files-first:
  - `topk_provenance_hit_rate = 0.375`
  - `topk_answer_provenance_hit_rate = 0.3611`
  - `avg_source_mrr = 0.3796`
  - `avg_latency_ms = 10112.8`
- vector:
  - `topk_provenance_hit_rate = 0.1944`
  - `topk_answer_provenance_hit_rate = 0.1944`
  - `avg_source_mrr = 0.3866`
  - `avg_latency_ms = 5151.4`

结论：

- files-first 在来源命中和答案加来源联合命中上更强
- vector 在本轮主集上延迟更低，且 source MRR 略高
- 因此论文表述应强调：
  - files-first 更适合来源敏感场景
  - vector 更适合宽松语义召回

### 2.3 古籍外部验证

- files-first:
  - `topk_provenance_hit_rate = 0.6667`
  - `topk_answer_provenance_hit_rate = 0.5833`
  - `avg_source_mrr = 0.5417`
  - `avg_latency_ms = 11649.5`
- vector:
  - `topk_provenance_hit_rate = 0.2083`
  - `topk_answer_provenance_hit_rate = 0.1667`
  - `avg_source_mrr = 0.1389`
  - `avg_latency_ms = 5207.4`

结论：

- files-first 的来源敏感优势在外部验证集上仍成立

### 2.4 古籍 baseline matrix

主实验集：

- `files_first_internal topk_book_hit_rate = 0.375`
- `external_bm25_docs topk_book_hit_rate = 0.2222`
- `vector_sqlite_internal topk_book_hit_rate = 0.1806`
- `external_dense_candidates topk_book_hit_rate = 0.0833`

外部验证集：

- `files_first_internal topk_book_hit_rate = 0.6667`
- `external_bm25_docs topk_book_hit_rate = 0.5833`
- `vector_sqlite_internal topk_book_hit_rate = 0.2083`
- `external_dense_candidates topk_book_hit_rate = 0.1667`

结论：

- 若论文需要古籍正式基线，当前最合理的是 `files_first_internal`

### 2.5 files-first 内部消融

- baseline `topk_keyword_hit_rate = 0.9861`
- `query_rewrite_off topk_keyword_hit_rate = 0.9306`
- `rerank_bonus_off topk_keyword_hit_rate = 0.9583`

结论：

- query rewrite 和 rerank bonus 都有真实贡献
- files-first 当前表现不是偶然命中

### 2.6 traceable benchmark

严格 raw：

- files-first:
  - `topk_answer_hit_rate = 0.4444`
  - `topk_evidence_hit_rate = 0.1111`
  - `topk_provenance_hit_rate = 0.2889`
  - `topk_answer_provenance_hit_rate = 0.1778`
- vector:
  - `topk_answer_hit_rate = 0.4444`
  - `topk_evidence_hit_rate = 0.0889`
  - `topk_provenance_hit_rate = 0.3111`
  - `topk_answer_provenance_hit_rate = 0.1778`

重打分 regraded：

- files-first:
  - `top1_regraded_success_rate = 0.8111`
  - `topk_regraded_success_rate = 0.8889`
- vector:
  - `top1_regraded_success_rate = 0.7111`
  - `topk_regraded_success_rate = 0.8889`

结论：

- raw 结果用于说明严格可追溯性缺口仍存在
- regraded 结果用于论文主文汇报更合理，因为它符合“项目资产内多书可接受答案”的正式口径

## 3. 论文写作建议

主文建议重点引用：

1. 病例 QA 主实验
2. 古籍主实验
3. 古籍外部验证
4. 古籍 baseline matrix
5. traceable benchmark regraded

补充材料或误差分析建议引用：

1. traceable benchmark raw
2. files-first 内部消融

## 4. 结果文件

为避免与历史 `latest / tmp / failed / debug` 文件混淆，本轮正式结果已统一复制到：

- `docs/official_rerun_20260419/`
- `backend/eval/paper/official_rerun_20260419/`

写论文时，建议优先从这两个目录取文件。

- 病例 QA 主实验：
  - `backend/eval/paper/caseqa_vector_vs_structured_latest.json`
  - `docs/CaseQA_Vector_vs_Structured_Latest.md`
- 古籍主实验：
  - `backend/eval/paper/classics_vector_vs_filesfirst_latest.json`
  - `docs/Classics_Vector_vs_FilesFirst_Latest.md`
- 古籍外部验证：
  - `backend/eval/paper/classics_vector_vs_filesfirst_external_validation_latest.json`
  - `docs/Classics_Vector_vs_FilesFirst_External_Validation_Latest.md`
- 古籍 baseline matrix：
  - `backend/eval/paper/classics_baseline_matrix_latest.json`
  - `docs/Classics_Baseline_Matrix_Latest.md`
- 古籍 baseline matrix 外部验证：
  - `backend/eval/paper/classics_baseline_matrix_external_validation_latest.json`
  - `docs/Classics_Baseline_Matrix_External_Validation_Latest.md`
- files-first 内部消融：
  - `backend/eval/ablations/files_first_ablation_latest.json`
  - `docs/Files_First_Ablation_Latest.md`
- traceable raw：
  - `backend/eval/paper/traceable_classics_benchmark_test_eval_fused_v2.json`
  - `docs/Traceable_Classics_Benchmark_Test_Eval_Fused_v2.md`
- traceable regraded：
  - `backend/eval/paper/traceable_classics_benchmark_test_regraded_fused_v2.json`
  - `docs/Traceable_Classics_Benchmark_Test_Regraded_Fused_v2.md`
