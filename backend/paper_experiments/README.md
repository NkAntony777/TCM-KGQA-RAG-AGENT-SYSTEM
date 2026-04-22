# Paper Experiments

本目录用于集中放置毕业论文/论文写作阶段使用的实验脚本与说明，避免与日常回归脚本、临时 benchmark 脚本混在一起。

## 当前设计原则

1. 论文实验优先使用**可复现**的数据集和统一输出格式。
2. 优先复用已有实验逻辑，不直接破坏原有 `eval/ablations` 与 `scripts/` 目录。
3. 每个实验应尽量同时输出：
   - `json`
   - `markdown`
4. 论文实验分为两层：
   - retrieval-level
   - end-to-end QA-level

## 已有可复用脚本

当前仓库中已经存在、可直接复用或改造的脚本包括：

- `backend/eval/ablations/vector_vs_nonvector.py`
  - 整体问答链路上的向量兼容开关 vs 非向量主链开关
- `backend/scripts/compare_qa_retrieval_modes.py`
  - 病例 QA 向量检索 vs 结构化非向量检索的直接对比
- `backend/scripts/benchmark_section_summary_ablation.py`
  - retrieval 层消融
- `backend/scripts/benchmark_qa_section_summary_ablation.py`
  - QA 层消融
- `backend/scripts/benchmark_path_query_backends.py`
  - SQLite path vs Nebula path

## 当前目录下新增脚本

- `run_caseqa_vector_vs_structured.py`
  - 论文版病例 QA 检索对比实验
  - 对比对象：
    - 原始 Chroma/HNSW 向量病例 QA 库
    - 后续构建的 `qa_structured_index.sqlite` 非向量结构化索引
- `run_classics_vector_vs_filesfirst.py`
  - 论文版古籍语料对比实验
  - 对比对象：
    - `files-first` 非向量检索
    - 基于 SQLite 实验后端的古籍向量/混合检索
- `import_classics_rows_to_milvus.py`
  - 将 `classics-vector.rows.jsonl` 导入 Milvus / 本地 Milvus Lite
  - 目的：
    - 让古籍向量索引适配当前系统的 `MilvusHybridStore`
    - 便于系统级向量化实验和后续主链接入
- `import_classics_rows_to_sqlite.py`
  - 将 `classics-vector.rows.jsonl` 导入 SQLite 实验后端
  - 目的：
    - 在不依赖 Milvus 的情况下稳定承载古籍向量实验
    - 为论文中的“古籍向量化 vs files-first”实验提供本地可复现向量检索后端
- `analyze_paired_significance.py`
  - 对论文实验 JSON 做 paired bootstrap / sign test 分析
  - 当前支持：
    - `classics_vector_vs_filesfirst_latest.json`
    - `caseqa_vector_vs_structured_latest.json`
    - `classics_baseline_matrix_latest.json`（可指定 pair）
- `run_end_to_end_qa_paper_eval.py`
  - 论文版 end-to-end QA 评测入口
  - 直接调用 `/api/qa/answer`，检查最终回答、route、证据书籍和 tool trace
- `run_medical_guard_eval.py`
  - 论文版医疗边界/拒答评测
  - 对 `medical_guard` 规则做正式数据集评测并输出 JSON/Markdown

## 推荐论文实验顺序

1. `run_caseqa_vector_vs_structured.py`
   - 先验证病例 QA 这条最强对照点
2. 复用 `eval/ablations/vector_vs_nonvector.py`
   - 做系统级向量兼容开关 vs 非向量主链
3. 复用 `benchmark_section_summary_ablation.py`
   - 做检索增强消融
4. 复用 `benchmark_path_query_backends.py`
   - 做图谱后端实验
5. `run_end_to_end_qa_paper_eval.py`
   - 补最终回答层与 route/evidence 一体化评测
6. `run_medical_guard_eval.py`
   - 补安全边界实验
7. `analyze_paired_significance.py`
   - 补统计显著性与区间分析

## 数据集建议

论文版病例 QA 对比数据集建议同时覆盖：

1. 纯病例风格检索题
   - 含年龄、性别、舌、脉、主诉、现病史
2. 方剂/证候相关病例问答
   - 需要从病例中归纳证候或方剂参考
3. 容易误召回的开放问句
   - 用于观察向量检索的漂移和结构化检索的范围控制

当前推荐种子数据集：

- `backend/eval/datasets/paper/caseqa_vector_vs_structured_seed_12.json`

## 说明

当前“论文实验代码目录”只是开始收口，不代表原有脚本作废。
后续若继续扩展，建议新增：

- `run_end_to_end_vector_vs_nonvector.py`
- `run_graph_first_vs_text_first.py`
- `run_paper_master_suite.py`
