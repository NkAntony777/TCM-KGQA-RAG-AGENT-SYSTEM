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

### 7.6 正式评测口径

Traceable benchmark 当前应明确区分两套口径：

1. `strict raw eval`
   - 目的：
     - 检查返回片段是否直接命中预设证据与来源
   - 用途：
     - 误差分析
     - 可追溯性短板展示
2. `asset-supported regraded eval`
   - 目的：
     - 检查返回答案是否属于项目现有资产可支持的合理答案集合
   - 用途：
     - 论文主表
     - 系统有效性主结论

当前 `regraded` 的核心原则是：

- 不再把单一本书、单一章节当作唯一正确答案
- 只要返回答案与题目指涉的是同一实体或同一方药事实
- 且该答案可在项目现有图谱候选库与古籍资产中找到支持
- 就计入可接受成功

因此，traceable benchmark 的正式论文写法应为：

- 主文结果表：优先引用 `regraded eval`
- 补充材料或误差分析：补充展示 `raw eval`

## 8. 2026-04-19 检查结论：当前数据集是否够用

### 8.1 当前判断

当前答案是：**够用，但不建议继续靠盲目扩题来制造“更严谨”的错觉。**

现有规模已经足以支撑：

1. 古籍主实验
2. 古籍外部验证
3. 病例 QA 主实验
4. debug / stress / failed-case 分析
5. traceable benchmark 的 debug / dev / test 分层评测

### 8.2 为什么说已经够用

当前不是只有单一 seed 集，而是已经形成了分层实验资产：

- 古籍主实验集：`72`
- 古籍外部验证集：`24`
- 古籍 debug 集：`12`
- 古籍 stress 集：`16`
- 病例 QA 主实验集：`48`
- 病例 QA debug 集：`8`
- traceable benchmark：
  - `master = 136`
  - `debug = 14`
  - `dev = 32`
  - `test = 90`

这套组合已经足以支撑论文中的：

- 主结果表
- 外部验证表
- 消融对照表
- 失败案例章节
- 误差分析与系统限制讨论

### 8.3 当前“不够”的地方是什么

如果后续目标是以下更强主张，现有数据仍然不建议直接上升到结论：

1. 覆盖所有古籍问答子任务的强统计显著性比较
2. 覆盖更广领域的通用中医问答泛化
3. 对每个细粒度题族都给出高置信度排名结论

也就是说，当前“不够”的不是论文主实验，而是更大口径的通用化主张。

### 8.4 后续增量原则

后续如需继续补题，优先级应为：

1. 补弱项任务族，而不是继续重复堆 `formula_composition`
2. 补 traceable benchmark 中 `evidence / provenance` 最薄弱的 case
3. 保持 `main / external / debug / stress / traceable` 的职责边界稳定

当前更推荐的补题方向：

- `formula_indication_*`
- `herb_effect`
- `herb_channel`
- 多书同名、别名歧义、证据定位难例
