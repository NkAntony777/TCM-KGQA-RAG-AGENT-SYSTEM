# QA 向量库接入开发方案

更新时间：2026-04-04

## 📌 结论

`E:\tcm_vector_db` 已确认不是 `FAISS`、不是 `Milvus`、也不是自定义 SQLite 向量表，而是一个本地持久化的 `ChromaDB` 数据库。

更精确地说，它的结构是：

- 元数据存储：`SQLite`
- 向量索引：`hnswlib` 本地持久化索引
- 逻辑组织：`10` 个手工分片的 `Chroma collection`
- 部署方式：`PersistentClient` 风格的单机本地库

这个库的业务定位也已经基本坐实：

- 它不是古籍证据库
- 它不是方剂百科知识库
- 它不是通用文档 chunk 检索库
- 它更像“病例/医案输入 -> 辨证、方剂、中药答案”的 QA / 相似医案向量库

因此，后续接入时不能把它当作当前 `retrieval-service` 的普通文档索引来平移接入。

当前项目中，这个库已经不再通过 `chromadb.PersistentClient` 直接读取，而是改为：

- `SQLite` 读取 collection / segment / metadata
- `hnswlib` 直接读取持久化向量索引
- 在 `retrieval-service` 内部以 `native_hnsw_sqlite` 只读适配器方式接入

这么做不是“重复造轮子”，而是被底层兼容性现实倒逼出来的工程选择。

## 🔧 已落实的兼容方案

### 为什么没有继续直接用 chromadb client

实测发现，直接使用 `chromadb` 官方 client 读取当前库，会连续遇到以下问题：

- 新版本 `chromadb` 读取 `collections.config_json_str='{}'` 时会在 `CollectionConfigurationInternal` 反序列化阶段报错
- 老版本 `chromadb` 与当前环境的 `numpy 2.x` 不兼容
- 即使绕过 `numpy / onnxruntime`，仍会继续遇到 schema 代差，例如 `collections.topic` 字段问题

这说明：

- 这套库的“写入时 Chroma 版本”
- 当前项目环境的“运行时 Chroma 版本”
- 当前环境的依赖版本

三者并不稳定同构。

因此，当前正式方案改为：

- 不再依赖 `chromadb` client 做线上读取
- 直接使用 `sqlite + hnswlib` 读取现有库
- 保持只读，不触碰原库 schema

### 当前适配器能力

当前 `ChromaCaseQAStore` 已具备：

- 发现 `tcm_shard_0..9`
- 读取 collection -> vector segment / metadata segment 映射
- 直接加载持久化 `hnswlib` 索引
- 从 `embedding_metadata` 回填 `document / answer`
- 统一输出 `case_reference` 候选结果
- 在 `retrieval-service` 中通过 `/api/v1/retrieval/search/case-qa` 暴露

## 🚀 已落实的性能优化

### 1. 从“全量硬 fan-out”升级为“分片预选 + 分波次 fan-out”

当前实现不再一上来并行加载全部分片，而是：

1. 先利用 `embedding_fulltext_search` 的 `fts5 trigram` 索引做轻量 shard 预选
2. 优先查询更可能命中的 shard
3. 再按内存预算分波次加载 HNSW 索引

这样做的意义是：

- 先用廉价的 SQLite / FTS 检查“哪些 shard 更像有料”
- 避免把大量低价值 shard 一次性装入内存
- 为后续“命中足够时早停”预留空间

### 2. 内存安全的分波次并发

当前实现增加了两类约束：

- `query_workers`
- `batch_load_target_bytes`

也就是：

- 并发数不再单独决定执行计划
- 每一波最多装载多少索引字节量，也会一起参与调度

这能显著降低以下风险：

- 多个大 shard 同时 `load_index`
- `level0` 大块内存申请失败
- 一次查询把整个进程内存打满

### 3. 小容量热缓存 + 淘汰

当前不会无限缓存所有已加载分片，而是只保留少量热分片：

- `max_loaded_collections`

超过上限时，会释放较旧的已加载索引，避免“第一次查完后，进程里永远挂着一堆大索引”。

### 4. 内存失败后的重试降级

如果某一波中仍出现：

- `Not enough memory`
- `loadPersistedIndex failed to allocate`

当前实现会：

1. 先记录该 shard
2. 释放非活跃索引
3. 再对该 shard 做单独重试

这比简单报错退出更稳，也更适合深度模式这种“允许补充证据稍慢，但不能直接挂掉”的场景。

## 📊 当前实测观察

在当前机器与当前真实库上，使用测试问题：

- `如何治疗食生米病`

做 10 shard 检索时，优化前后对比为：

- 优化前：约 `47.6s`
- 优化后：约 `35.1s`

同时：

- 优化前存在部分 shard 的 HNSW 内存加载失败告警
- 优化后该测试中未再出现该类告警

需要强调：

- 这还不是最终性能形态
- 目前收益主要来自“更稳的装载调度”
- 后续如果要继续压缩时延，关键仍在“进一步减少需要真正打开的 shard 数量”

## 🧭 当前推荐执行策略

### 快速模式

快速模式仍然不建议默认接入该库。

原因没有变化：

- 它是案例参考源，不是事实主证据源
- 首次查询延迟依旧明显高于图谱与普通文档检索
- 即便优化后，也不适合放入低延迟主链路

### 深度模式

深度模式当前建议采用：

- 先图谱 / 文档拿事实依据
- 再按需调用 `case_qa`
- `case_qa` 仅作为案例参考补充

并且建议让 Agent 在这些情况下优先启用：

- 病例描述长
- 用户问题偏“辨证 -> 方剂/治法”
- 用户显式询问“类似医案 / 类似治疗思路”

## ⚠️ 当前仍存在的性能边界

### 1. 首次冷启动仍然偏慢

即使已经做了分片预选和分波次装载，首次真正打开 HNSW shard 依然有明显成本。

这意味着：

- 深度模式需要接受比快速模式更高的首包延迟
- 不应该把该源塞进默认快速问答链路

### 2. FTS 预选还只是第一版

当前 shard 预选使用的是：

- query 短语抽取
- `embedding_fulltext_search` 命中统计

它已经足以减少无效加载，但还不是最终形态。

后续可以继续优化为：

- 更好的症状词 / 证候词抽取
- 根据 query 类型区分 document 命中与 answer 命中权重
- 引入 shard 命中历史统计，做动态优先级

### 3. 目前仍是“query-time fan-out”

当前没有单独维护 shard centroid、路由索引或二级 ANN。

因此本质上仍是：

- query-time 选择 shard
- query-time 打开 shard
- query-time 汇总候选

后续若深度模式调用频繁，应优先考虑：

- shard 路由索引
- 热 shard 常驻
- 后台预热
- 单独的 QA case retrieval service

## 🔬 已确认的底层事实

### 库文件与布局

- 根目录存在 [chroma.sqlite3](E:/tcm_vector_db/chroma.sqlite3)
- 根目录存在多个 UUID 命名的向量索引目录
- 每个向量目录都包含：
  - `data_level0.bin`
  - `header.bin`
  - `length.bin`
  - `link_lists.bin`
  - `index_metadata.pickle`

这正是 Chroma 的 `hnsw-local-persisted` 存储布局。

### SQLite 元数据表

`chroma.sqlite3` 中存在典型的 Chroma 表：

- `collections`
- `segments`
- `embeddings`
- `embedding_metadata`
- `collection_metadata`
- `segment_metadata`
- `embedding_fulltext_search`
- `migrations`
- `tenants`
- `databases`

### Chroma 迁移信息

迁移表显示该库已经包含：

- `default_tenant`
- `default_database`
- `collections.config_json_str`
- `collections.schema_str`
- `embedding_fulltext_search using fts5`

因此可以确认这是较新的 Chroma schema，不是早期的旧版布局。

### Collection 与分片结构

当前存在 `10` 个 collection：

- `tcm_shard_0`
- `tcm_shard_1`
- `tcm_shard_2`
- `tcm_shard_3`
- `tcm_shard_4`
- `tcm_shard_5`
- `tcm_shard_6`
- `tcm_shard_7`
- `tcm_shard_8`
- `tcm_shard_9`

每个 collection 都有：

- `1` 个 `METADATA` segment
- `1` 个 `VECTOR` segment

这说明它不是单 collection 的内部物理分片，而是应用层主动拆成了 10 个 collection。

### 数据规模

当前总记录数：

- `3,677,130`

每条记录都有两个关键 metadata 字段：

- `chroma:document`
- `answer`

向量维度：

- `1024`

### 数据语义

从样本看：

- `chroma:document` 主要是病例描述、主诉、现病史、体格检查等输入
- `answer` 主要是：
  - `诊断`
  - `证型`
  - `治法`
  - `方剂`
  - `中药`

因此这个库最合理的业务名称应该是：

- `病例 QA 向量库`
- 或 `相似医案向量库`

而不是“中医知识百科向量库”。

## 🧭 业务定位

### 适合回答的问题

这个库适合增强以下问题：

- 长病例描述类问题
- 从症状/证候推断方剂的参考类问题
- “有没有相似医案/相似辨证方案”的问题
- 深度模式中需要补充“临床相似案例”的问题

### 不适合作为主证据的问题

这个库不适合作为以下问题的主检索源：

- “六味地黄丸的组成是什么”
- “逍遥散出自哪本古籍”
- “柴胡的归经和功效是什么”
- “两个方剂有什么区别”
- “某条古籍原文怎么说”

这些问题的主证据仍应来自：

- 图谱关系簇
- 古籍文本检索
- 结构化出处证据

## 🏗️ 推荐接入架构

```mermaid
flowchart TD
    accTitle: QA Vector DB Integration Architecture
    accDescr: The deep mode planner decides whether to use the local Chroma case QA database as a supplemental evidence source, while graph and classic document retrieval remain primary sources for factual TCM knowledge questions.

    user_query["用户问题"]
    analysis["query_analysis<br/>实体 + 意图 + 路由倾向"]
    planner["retrieval_strategy<br/>决定是否启用病例 QA 检索"]
    graph["图谱检索"]
    docs["古籍/文档检索"]
    caseqa["ChromaCaseQAStore<br/>10-shard fan-out search"]
    filter["结果过滤<br/>仅保留病例 QA 语料"]
    merge["证据合并与去重"]
    answer["答案生成<br/>区分事实证据与案例参考"]

    user_query --> analysis
    analysis --> planner
    planner --> graph
    planner --> docs
    planner --> caseqa
    caseqa --> filter
    graph --> merge
    docs --> merge
    filter --> merge
    merge --> answer

    classDef core fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef support fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef output fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d

    class user_query,analysis,planner,merge,answer core
    class graph,docs,caseqa,filter support
    class answer output
```

## ⚙️ 工程化设计原则

### 1. 只读接入

当前项目对该库的第一阶段接入必须是只读：

- 不写入
- 不重建
- 不迁移
- 不混改 schema

原因：

- 这个库体量大
- 数据来源混合
- 当前主要目标是检索接入，不是库治理

### 2. 独立数据源，不并入通用文档源

不要把它直接塞进现有 `retrieval-service` 的普通文档索引里。

正确做法是把它定义成新的 source：

- `qa_case_vector_db`

这样才能在策略层明确控制：

- 哪些问题该查
- 哪些问题不该查
- 查到后如何降权

### 3. Fan-out 查询 + 统一重排

因为当前是 `10` 个 collection 分片，后续查询必须：

1. 对 `tcm_shard_0..9` 并发查询
2. 汇总每个 shard 的候选
3. 再统一重排

不能假设这是一个单 collection。

### 4. 明确“案例参考”与“事实依据”的区别

这个库返回的是相似病例和推荐方案，不应被模型误当成古籍事实依据。

因此证据对象必须增加类型标记，例如：

- `evidence_type = case_reference`

而图谱/古籍证据应保持：

- `evidence_type = factual_grounding`

最终回答时也要明确区分：

- 哪些是图谱或古籍依据
- 哪些只是相似医案参考

## 🧱 推荐实现对象模型

### Source 标识

- `graph_sqlite`
- `graph_nebula`
- `classic_docs`
- `qa_vector_db`
- `qa_case_vector_db`

### Evidence Path

建议为该库新增独立路径协议：

- `caseqa://{query}/similar`
- `caseqa://{embedding_id}`
- `caseqa://{collection}/{embedding_id}`

### Evidence Object

建议统一返回结构：

```json
{
  "source": "qa_case_vector_db",
  "evidence_type": "case_reference",
  "collection": "tcm_shard_4",
  "embedding_id": "id_1599955",
  "query_text": "用户原问题",
  "document": "病例输入或问题描述",
  "answer": "诊断/证型/方剂/中药输出",
  "score": 0.83,
  "metadata": {
    "is_case_qa": true,
    "filter_passed": true
  }
}
```

## 🧪 查询策略建议

### 快速模式

当前不建议让快速模式默认查这个库。

原因：

- 快速模式追求稳定、简洁、低延迟
- 这个库的结果更偏案例相似，不是直接事实
- 快速模式当前主链路应以图谱和古籍为主

因此快速模式建议：

- 默认不查 `qa_case_vector_db`
- 只有后续确认某些问法收益显著，再按意图选择性启用

### 深度模式

深度模式应把它作为补充源，而不是主源。

推荐启用条件：

- `syndrome_to_formula`
- `open_ended_grounded_qa`
- 长病例描述
- 多症状组合、需要相似案例参考的问题

不推荐默认启用条件：

- `formula_composition`
- `formula_origin`
- `formula_efficacy`
- `compare_entities`

## 🧹 数据过滤策略

当前库中存在少量异质样本，不全是标准病例 QA。

因此接入时必须先做过滤。

### 第一阶段过滤建议

优先保留满足以下条件的记录：

- `document` 包含“基于输入的患者医案记录”
- 或 `document` 包含“基本信息”“主诉”“现病史”“体格检查”
- `answer` 包含：
  - `诊断`
  - 或 `证型`
  - 或 `方剂`
  - 或 `中药`

### 第一阶段排除建议

优先排除：

- 明显不是病例 QA 的纯知识句
- 没有结构化治疗输出的短答案
- 与当前查询类型完全不匹配的样本

## 📈 排序与融合建议

该库的排序不应只看向量相似度。

建议在 shard 汇总后增加二次排序：

- 向量相似度
- `answer` 结构完整度
- 是否包含 `证型`
- 是否包含 `方剂`
- 是否包含 `中药`
- 是否与当前意图匹配
- 是否命中当前问题中的核心症状/证候词

推荐做法：

- shard 内先取 `top_n`
- 全局汇总后用 `RRF` 或轻量规则重排
- 最终只保留少量高质量案例参考

## 🔌 实现阶段建议

### 阶段 A：文档与调研定基线

当前阶段已完成：

- 确认数据库类型
- 确认分片结构
- 确认数据规模
- 确认语料业务定位

### 阶段 B：做只读适配器

新增：

- `ChromaCaseQAStore`

职责：

- 打开本地 Chroma persistent store
- 枚举 `tcm_shard_0..9`
- 并发查询
- 返回统一格式结果

### 阶段 C：做工具层封装

新增：

- `tcm_case_qa_search`

职责：

- 接收 query
- 执行 10-shard 检索
- 过滤与重排
- 输出统一 evidence objects

### 阶段 D：接入策略层

在 `retrieval_strategy` 中增加：

- 是否启用 `qa_case_vector_db`
- 针对病例类问题增加局部 `candidate_k/final_k`

### 阶段 E：接入深度模式

让深度模式在这些意图下可选调用：

- `syndrome_to_formula`
- `open_ended_grounded_qa`

### 阶段 F：补测试与回归

至少补：

- shard fan-out 查询测试
- 过滤逻辑测试
- 深度模式启用条件测试
- 不同意图下的 source 选择测试

## ⚠️ 关键风险

### 1. 依赖缺失

当前 backend 环境里还没有 `chromadb`。

### 2. Embedding 模型一致性

这个库的向量维度是 `1024`。

后续查询时必须确认：

- 当前查询 embedding 是否仍然使用同一个模型
- 输出维度是否仍然是 `1024`

如果模型不同，就不能直接做向量查询。

### 3. 数据分布污染

当前库中存在少量异质数据。

如果不做过滤，回答链路会把不合适的结果混进来。

### 4. 延迟风险

10-shard fan-out 查询天然会增加延迟。

因此必须：

- 并发查询
- 控制每 shard 候选数
- 汇总后再统一裁剪

## ✅ 当前正式建议

当前建议定为正式开发约束：

- 将 `E:\tcm_vector_db` 明确定义为 `ChromaDB` 本地持久化病例 QA 向量库
- 不将其作为快速模式默认主检索源
- 不将其混入普通古籍/知识文档检索
- 在深度模式中将其作为“相似医案参考源”
- 通过 `10` 个 shard fan-out 查询接入
- 通过过滤和重排控制噪声
- 在回答层显式区分“事实依据”和“案例参考”

## 📍 下一步实现优先级

1. 安装并验证 `chromadb`
2. 实现只读 `ChromaCaseQAStore`
3. 做 `tcm_case_qa_search` 工具
4. 把 `qa_case_vector_db` 接入 `retrieval_strategy`
5. 只在深度模式指定意图下启用
6. 补测试与调试输出
