# Graph Governance Phase 3 Runtime Report

生成时间：2026-04-13

## 本轮目标

第三批不再做大规模物理改写，而是优先完成两类运行时治理：

1. `source_chapter` 规范化
2. ontology 边界异常的标记与降权

## 已落实

### 1. source_chapter 运行时规范化

已新增共享规范化逻辑：

- `services/common/evidence_payloads.py`
  - `normalize_source_chapter_label()`

当前行为：

- `089-医方论_正文` 这类“书名前缀 + 正文 slug”会被归一为空 chapter
- `089-医方论_卷上` 这类“书名前缀 + 可读篇章名”会被归一为 `卷上`
- graph / path / syndrome / retrieval / section evidence 全部统一走该规范化逻辑

效果：

- 逻辑 evidence path 不再暴露 `chapter://医方论/089-医方论_正文`
- 对这类样本只输出 `book://医方论/*`
- 不需要重建 SQLite / Nebula

### 2. ontology 边界运行时治理

已新增关系治理能力：

- `services/graph_service/relation_governance.py`
  - 为 `使用药材`、`推荐方剂`、`治疗证候`、`治疗症状`、`归经` 添加低风险 expected type 规则
  - 提供 `ontology_boundary_ok()` 判断

已接入：

- `services/graph_service/engine.py`
  - entity lookup 对关系行做 governance 注解
  - relation cluster 暴露 `ontology_boundary_ok`
  - 边界异常关系在 ranking 中降权
  - path expansion 默认跳过 `ontology_boundary_ok = false` 的关系

说明：

- 本轮没有删除任何 ontology 异常边
- 只是把异常边从“等权参与主链”改成“可见但降权/限扩散”

## 回归验证

执行结果：

- `uv run pytest tests/test_evidence_payloads.py -q`
  - `3 passed`
- `uv run pytest tests/test_graph_engine.py -q`
  - `34 passed`
- `uv run pytest tests/test_tcm_service_client.py -q`
  - `5 passed`
- `uv run pytest tests/test_tcm_evidence_tools.py -q -k "normalizes_graph_book_label_and_skips_file_slug_chapter or prefers_source_chapter"`
  - `1 passed`

中途发现并修复的回归：

- `六味地黄丸` 在 `top_k=6` 下曾丢失 `功效`
- 已通过提高 `功效` 的治理优先级修复

## 最新审计摘录

来源：

- `eval/graph_governance_audit_latest.json`

关键结果：

- `polluted_source_chapter_rows = 0`
- `book_prefixed_body_slug_rows = 3,702,314`
- `book_prefixed_readable_rows = 0`

解释：

- 当前 source_chapter 的主要问题已经不再是“正文污染”
- 而是大规模历史 slug 规范不统一
- 本轮已在运行时层面把这类 slug 收口，不必再次全量重建

ontology 审计当前仍显示大量边界异常样本，例如：

- `使用药材` 总异常量：`52,831`
- `治疗证候` 总异常量：`12,120`
- `推荐方剂` 总异常量：`4,727`

这些数字说明：

- 知识底座仍有明显抽取边界问题
- 但已经不必立刻物理清库
- 更合理的做法是继续“专项审计 -> 小批修复 -> 运行时保护”

## 下一步建议

1. 做 ontology 专项审计分层
   - 区分“可接受多义边”与“明显脏边”
   - 不再用一个粗规则混看所有异常

2. 做 source_chapter / source_book 规范化视图
   - 仅在 query / evidence path / citation 展示层生效
   - 不触碰原始库

3. 做 backup residue 清理策略
   - 当前 audit 仍显示较多历史 `.bak` 文件
   - 应做白名单保留 + 归档/清理策略
