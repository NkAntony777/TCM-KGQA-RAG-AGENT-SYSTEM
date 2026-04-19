# Paper Dataset Design

## 1. 文档目的

本文档用于说明论文阶段两套主实验数据集的设计原则：

- `classics_vector_vs_filesfirst_seed_20.json`
- `caseqa_vector_vs_structured_seed_12.json`

虽然文件名中保留了历史命名，但当前内容已经扩展为论文正式实验可用版本。

当前规模：

- `classics_vector_vs_filesfirst_seed_20.json`
  - 当前已扩到 `72` 条
- `caseqa_vector_vs_structured_seed_12.json`
  - 当前已扩到 `48` 条
- `classics_vector_vs_filesfirst_external_validation_12.json`
  - 当前已扩到 `24` 条

## 2. 设计总原则

两套数据集都遵循以下原则：

1. 保留现有实验脚本可直接读取的字段，避免因为扩充数据集而重新改代码。
2. 增加辅助字段：
   - `difficulty`
   - `eval_focus`
   用于论文写作与后续题型分析。
3. 对于存在多种合理答案口径的问题，避免把 gold 设计成唯一刚性答案。
4. 在不破坏现有实验脚本的前提下，允许补充：
   - `expected_chapters_any`
   - `gold_answer_outline`
   - `notes`
   用于后续人工复核、误差分析与论文讨论。
5. 同时覆盖：
   - 基础题
   - 综合题
   - 比较题
   - 来源题
   - 推理题
6. 同时包含：
   - 主实验核心题
   - 某类能力专门评测题

## 3. 古籍主实验集设计

### 3.1 任务目标

用于比较：

- 古籍 `files-first` 非向量检索
- 古籍 SQLite 本地向量实验后端

### 3.2 当前覆盖能力

1. 方剂出处检索
2. 古籍原文定位
3. 药材性味归经与功效
4. 方剂组成与主治
5. 方剂比较与适用边界
6. 解释型 / 理论型问题
7. 经典条文引用

### 3.3 当前题型结构

- `origin`
- `origin_quote`
- `source_text`
- `book_source`
- `book_quote`
- `formula_composition`
- `formula_definition`
- `formula_indication`
- `formula_origin`
- `formula_role`
- `formula_summary`
- `formula_comparison`
- `herb_property`
- `definition`
- `reasoning`
- `generic`

### 3.4 难度分层

- `easy`
  - 明确实体 + 明确知识点
- `medium`
  - 明确实体 + 需要一点结构整合
- `hard`
  - 需要出处 + 解释
  - 或比较 / 理论 / 条文联合检索

## 4. 病例 QA 主实验集设计

### 4.1 任务目标

用于比较：

- 原始病例 QA 向量库
- 结构化非向量病例 QA 索引

### 4.2 当前覆盖能力

1. 病例基本要素检索
2. 病例到证候
3. 病例到方剂参考
4. 开放式方剂知识问答
5. 处方出处类问答
6. 比较题
7. 长文本噪声鲁棒性

### 4.3 当前题型结构

- `case_basic`
- `case_digestive`
- `case_syndrome_formula`
- `formula_role`
- `formula_origin`
- `compare_boundary`
- `open_query`
- `generic_reason`

### 4.4 难度分层

- `easy`
  - 明显症状、舌脉线索直接匹配
- `medium`
  - 需要一定结构整合
- `hard`
  - 比较题
  - 开放推理题
  - 长文本噪声病例题

## 5. 当前仍然存在的不足

虽然当前两套数据集已经比最初的 seed 版更完整，但仍然建议在论文正式定稿前继续保持以下原则：

1. 古籍主实验集尽量维持在 `70+` 的规模
2. 病例 QA 主实验集尽量维持在 `45+` 的规模
3. 外部验证集尽量维持在 `20+` 的规模
4. 若继续扩题，应优先补足题型分布，而不是重复堆叠同一实体
5. 后续仍可继续补字段：
   - `negative_expectations`
   - `expected_route_hint`
   - `manual_review_notes`

## 6. 当前使用建议

当前版本适合：

- 跑第一轮正式主实验
- 做脚本联调
- 观察向量与非向量差异
- 作为论文写作中的正式主实验数据基础

当前已不再是“过小 seed 集”，已经可以支持：

- 主结果表
- 分题型柱状图
- 外部验证对照图
- 消融实验统计表

后续如果还扩题，建议只做小幅增量扩充，不再做无边界扩张。

## 7. Traceable Classics Benchmark（2026-04-18）

为支撑“答案准确性 + 可追溯性”主张，当前目录新增一套基于项目真实知识资产自动构建的古籍 benchmark：

- `traceable_classics_benchmark_master.json`
- `traceable_classics_benchmark_debug.json`
- `traceable_classics_benchmark_dev.json`
- `traceable_classics_benchmark_test.json`
- `traceable_classics_benchmark_manifest.json`

### 7.1 数据来源

- 图谱事实来源：`services/graph_service/data/graph_runtime.json`
- 图谱在线校验：Nebula `tcm_kg`
- 古籍证据定位：`storage/retrieval_local_index.fts.db`

### 7.2 设计目标

该 benchmark 不再只评估“召回了没有”，而是同时评估：

1. 回答关键点是否正确
2. 证据片段是否真实存在于古籍索引中
3. 书名与章节是否可定位
4. 图谱事实是否能在在线 Nebula 服务中复核

### 7.3 当前字段

在旧版 `expected_books_any / expected_keywords_any` 兼容字段之外，新增：

- `task_family`
- `difficulty`
- `preferred_terms`
- `gold_answer_outline`
- `gold_evidence_any`
- `gold_relation_tuples`
- `provenance`
- `split`

### 7.4 当前规模

以 `traceable_classics_benchmark_manifest.json` 为准。当前版本包含：

- `68` 个唯一 subject
- `136` 条 case
- `25` 本古籍来源
- `answer_trace / source_locate` 两类任务各半

### 7.5 当前限制

- 目前 coverage 最强的是：
  - `formula_composition`
  - `herb_effect`
  - `herb_channel`
- `formula_indication_disease`、`herb_property`、`herb_flavor` 在当前 Nebula 发布图和古籍索引联动条件下通过率较低，后续可继续扩充。
