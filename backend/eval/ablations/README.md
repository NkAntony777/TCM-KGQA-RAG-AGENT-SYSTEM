# Ablation Scripts

本目录集中放置本项目的消融实验脚本。

## 已提供脚本

- `vector_vs_nonvector.py`
  - 向量兼容链路 vs 非向量化主链
- `graph_first_vs_text_first.py`
  - 图谱优先 vs 文本优先
- `path_backend_ablation.py`
  - SQLite path vs Nebula path
- `deep_hardening_ablation.py`
  - Deep hardening 前后对比
- `compare_refiner_ablation.py`
  - compare entity refinement on/off 的近似对照
- `coverage_facets_ablation.py`
  - facet-aware coverage vs legacy-like coverage

## 相关脚本

以下两个脚本虽然位于 `backend/scripts/`，但也属于消融实验组成部分：

- `backend/scripts/benchmark_section_summary_ablation.py`
- `backend/scripts/benchmark_qa_section_summary_ablation.py`
