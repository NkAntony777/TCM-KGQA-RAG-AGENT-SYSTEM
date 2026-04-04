# Top K 策略与深度模式最佳实践

更新时间：2026-04-04

本文档先于后续代码实现，目的不是立刻改算法细节，而是先把检索策略和深度模式的开发边界定清楚。

参考研究记录：

- [research_20260404_topk_and_deep_mode_best_practices.md](../sources/research_20260404_topk_and_deep_mode_best_practices.md)
- [research_20260404_relation_cluster_rerank.md](../sources/research_20260404_relation_cluster_rerank.md)
- [research_20260404_files_and_chromafs.md](../sources/research_20260404_files_and_chromafs.md)

## 一、结论先行

### 1. 默认 Top K 不建议继续整体抬高

当前建议：

- 快速模式默认 `final_top_k = 12`
- 不建议把全局默认直接继续抬到 `20+`

原因：

- 图谱候选边已经非常密，直接提高默认 `top_k`，会把更多边缘关系、命名变体、重复关系一并带入
- 用户真正需要的是“更有用的前 12 条”，而不是“更长但更乱的前 20 条”
- 深度模式真正需要的是“按意图定向提高某一类检索的 `top_k`”，不是无脑提高全局默认值

### 2. 必须区分三种 K

后续实现中，不允许再把 `top_k` 当成单一概念。

需要拆成：

- `candidate_k`
  用于召回候选关系簇，偏大，保障 recall
- `final_k`
  用于最终进入回答上下文的关系簇数量，偏小，保障 precision
- `intent_k`
  用于某个问题意图下的局部检索数量，例如“组成类问题”只在 `使用药材` 子空间里提高 `k`

建议默认值：

- 快速模式：`candidate_k = 48~64`，`final_k = 12`
- 深度模式综合问题：`candidate_k = 48~80`，`final_k = 8~12`
- 深度模式组成类问题：在 `predicate=使用药材` 子空间下，`final_k = 12~20`

## 二、Top K 最佳实践

### 1. 先做关系簇聚合，再做 Top K

图谱中最大的噪声不是“完全无关边”，而是“同语义边被多本古籍重复抽取”。

因此必须先把原始边聚合为关系簇：

- 聚合键：`(predicate, target, direction)`
- 聚合后保留：
  - `evidence_count`
  - `source_book_count`
  - `avg_confidence`
  - `max_confidence`
  - 代表性 `source_text`

没有这一步，任何 `top_k` 都会被重复边污染。

### 2. 排序不能只看 confidence

后续正式排序应综合以下信号：

- 问题意图匹配度
- 关系类型优先级
- 最高证据置信度
- 平均证据置信度
- 覆盖书数
- 证据条数
- 目标实体类型
- 是否为当前问题要求的谓词

推荐做法：

- 用 `RRF` 融合多种排序视角
- 再做一次覆盖重排，优先让不同 `predicate` 在前几个槽位出现

### 3. 多样化的主维度应当是 predicate

在这个项目里，多样化不应该主要围绕词面相似度，而应该围绕“关系类型覆盖”。

因为用户最容易被以下几类关系同时满足：

- 组成
- 功效
- 治疗证候
- 治疗症状
- 治疗疾病
- 归经
- 治法
- 别名
- 范畴

所以快速模式里的多样化应当优先保证：

- 前几个结果不要被单一高频 `predicate` 独占
- 小 `top_k` 也能保留 3 到 5 个不同关系面向

### 4. MMR / xQuAD / RRF 的落地映射

后续实现应采用下面的工程化映射：

- `MMR`
  作用在同类候选之间，减少重复 target 或近重复关系
- `xQuAD`
  作用在前几个展示位，优先覆盖不同 `predicate`
- `RRF`
  作用在多信号融合阶段，减少手写权重过多带来的脆弱性

## 三、深度模式最佳实践

### 1. 深度模式不应直接消费“全局 diversified top-k”

深度模式的关键不是“拿更多关系”，而是“先定检索策略，再检索”。

也就是说：

- 快速模式
  统一排序后直接返回
- 深度模式
  先识别问题意图，再针对该意图定向检索

### 2. 推荐采用“Router / Planner + Specialized Retrieval Tools”

不推荐一上来就让通用 Agent 自由决定所有检索步骤。

更稳的方案是：

1. `Router / Planner`
   识别问题意图，生成结构化检索策略
2. `Graph Retrieval Tool`
   执行图谱定向检索
3. `Vector QA Retrieval Tool`
   召回外部问答向量库中的高相似问答
4. `Evidence Merge Tool`
   合并图谱与向量证据
5. `Answer Synthesizer`
   只基于证据生成答案和引用

### 3. 深度模式必须让 Agent 自定义检索策略，但不能放飞

应该允许 Agent 根据问题生成结构化策略，而不是直接放开原始查询。

推荐的 Agent 输出 schema：

```json
{
  "intent": "formula_composition",
  "entities": ["六味地黄丸"],
  "predicate_allowlist": ["使用药材"],
  "predicate_blocklist": [],
  "graph_candidate_k": 40,
  "graph_final_k": 12,
  "vector_candidate_k": 8,
  "sources": ["graph_sqlite", "graph_nebula", "qa_vector_db"],
  "min_source_book_count": 1,
  "prefer_high_confidence": true,
  "prefer_multi_book_support": true,
  "need_followup_retrieval": false
}
```

这样可以保证：

- Agent 能按问题类型定制检索
- 系统仍然保留可控边界
- 检索行为可审计、可复现、可测试

### 4. 深度模式的推荐问题意图模板

建议后续至少支持这些意图：

- `formula_composition`
  主要看 `使用药材`
- `formula_efficacy`
  主要看 `功效`
- `formula_indication`
  主要看 `治疗证候`、`治疗症状`、`治疗疾病`
- `formula_origin`
  主要看出处、书名覆盖和原文证据
- `syndrome_to_formula`
  从症状或证候出发找方剂
- `compare_entities`
  比较两个方剂、药材或证候
- `open_ended_grounded_qa`
  综合型问题，允许多轮检索

### 5. 示例：为什么“组成问题”不应受全局去重策略限制

问题：

- “六味地黄丸的组成是什么？”

错误做法：

- 先做全局 diversified top-k
- 再从里面找 `使用药材`

这样会让 `功效`、`治疗证候`、`别名` 占据部分槽位，影响组成类问题的召回深度。

正确做法：

1. Agent 识别这是 `formula_composition`
2. 策略层给出 `predicate_allowlist=["使用药材"]`
3. 只在该谓词子空间内做关系簇去重和排序
4. 必要时把该子空间的 `final_k` 提高到 `12~20`

结论：

深度模式中，Agent 应该能绕开“全局多样化约束”，改用“意图约束下的局部排序”。

## 四、推荐实现路线

### 阶段 A：先稳住快速模式

- 默认 `final_top_k` 调整为 `12`
- 保持关系簇聚合
- 保持多样化排序
- 增加调试接口，输出：
  - 原始边数
  - 关系簇数
  - 被截断前的候选数
  - 最终 `top_k` 结果

### 阶段 B：定义深度模式策略层

- 新增 `retrieval_strategy` 数据结构
- 让 Agent 只输出结构化策略，不直接输出底层查询
- 为每种意图定义默认模板

### 阶段 C：接入多源检索

- 图谱 SQLite
- 图谱 Nebula
- 外部 Qwen embedding 问答向量库

深度模式中应优先做：

- 图谱定向检索
- 向量问答补充
- 证据合并去重
- 引文式回答生成

### 阶段 D：补评测

后续评测重点不应只看命中率，还要看：

- 关系类型覆盖率
- 重复率
- 平均证据覆盖书数
- 回答引用密度
- 问题意图匹配率
- 平均响应延迟

## 五、当前建议

在正式继续写代码前，先将以下策略定为开发约束：

- 快速模式默认 `final_top_k = 12`
- 快速模式继续使用关系簇聚合 + 多样化排序
- 深度模式必须先生成结构化检索策略，再执行检索
- 深度模式允许按意图提高局部 `top_k`
- 深度模式允许按意图限制 `predicate_allowlist`
- 不允许把“提高全局 top_k”当作深度模式的主要解决方案

## 六、Files Are All You Need 与 ChromaFs 的借鉴意义

### 1. 核心思想

近期两类工作都在强调同一个方向：

- `Files are all you need`
  强调 Agent 系统应尽量把异构资源统一到文件或代码式接口上，以获得更强的可维护性、可组合性和可审计性
- `ChromaFs`
  强调 Agent 未必需要真实文件系统，只需要一个“文件系统抽象”，让 `ls / grep / cat / find` 这类操作可以映射到已有索引和存储系统

这与本项目非常契合。

我们后续的核心问题不是“让 Agent 更自由”，而是“让 Agent 以受控、可验证、低延迟的方式探索证据”。

### 2. 对本项目最有价值的借鉴点

#### 借鉴点 A：统一证据接口

后续不应让 Agent 直接面向：

- SQLite 图谱
- Nebula 图谱
- 向量库
- 原始古籍分块

分别写不同的调用逻辑。

更合理的做法是统一成一个“证据文件系统”抽象，例如：

- `/entities/六味地黄丸/relations/使用药材.json`
- `/entities/六味地黄丸/relations/功效.json`
- `/syndromes/肝肾不足/formulas.json`
- `/books/医方论/六味地黄丸.md`
- `/qa_vector/六味地黄丸/related_qa.json`

这样 Agent 的工作从“乱用多个工具”变成“浏览证据目录、读取证据文件、再决定下一步”。

#### 借鉴点 B：读多写少、只读优先

Mintlify 的 ChromaFs 明确采用只读文件系统，Agent 可以探索，但不能修改底层内容。

本项目也应该保持这个原则：

- 深度模式的检索层默认只读
- Agent 只能读取证据，不能直接修改图谱、向量库或古籍文本
- 图谱写入、发布、重建仍然由独立流水线负责

这会显著降低 Agent 失控改数据的风险。

#### 借鉴点 C：把“结构浏览”与“语义检索”合并

ChromaFs 的一个关键点是：

- `ls`、`find` 走目录树或缓存元数据
- `grep` 走索引粗筛 + 内存细筛
- `cat` 负责按 chunk 重组完整页面

对我们来说，可以直接映射为：

- `ls entity`
  列出一个实体有哪些关系类型
- `cat relation`
  读取某个关系簇的完整证据
- `grep evidence`
  在出处原文中做关键词过滤
- `find source`
  查找某关系关联了哪些古籍、哪些章节

这比只返回扁平 JSON 更适合深度模式 Agent 逐步推进检索。

#### 借鉴点 D：把上下文工程显式化

`Everything is Context` 这一路论文的重点，不只是“文件系统”本身，而是：

- context construction
- context loading
- context evaluation

这对本项目非常重要。

后续深度模式应当把上下文组织拆成三个阶段：

1. Context Constructor
   组装候选证据
2. Context Loader
   把证据裁剪成回答上下文
3. Context Evaluator
   检查当前证据是否足够回答问题，是否需要追加检索

### 3. 可行性判断

我认为可行，而且价值很高，但不建议一步到位重构成完整虚拟文件系统。

建议分三步落地：

#### 第一步：先做“虚拟证据目录”层

先不真的实现 shell，也不真的支持 `ls/cat/grep` 命令。

只需要先在代码里定义统一的证据路径和对象模型，例如：

- `entity://六味地黄丸/使用药材`
- `entity://六味地黄丸/功效`
- `book://医方论/六味地黄丸`
- `qa://六味地黄丸/similar`

这样深度模式的 Agent 就已经能通过“路径 + 读取”来工作。

#### 第二步：再做受控文件系统式工具

后续如果验证有效，可以再增加：

- `list_evidence_paths`
- `read_evidence_path`
- `search_evidence_text`

这三类工具。

它们本质上就是 ChromaFs 思路在本项目里的最小版落地。

#### 第三步：最后再考虑 shell 化

只有当深度模式里 Agent 的探索路径明显受益时，才考虑进一步做真正的 `ls/cat/find/grep` 风格接口。

否则维护成本会大于收益。

### 4. 当前结论

结论不是“直接照搬 Mintlify 的 ChromaFs”，而是：

- 借鉴它的统一抽象
- 借鉴它的只读设计
- 借鉴它的低延迟文件系统幻觉
- 借鉴它把检索系统包装成 Agent 易用接口的思路

不直接照搬的部分是：

- 我们不是纯文档站点，而是图谱 + 向量库 + 古籍证据的混合系统
- 我们更适合先做“证据对象层”和“策略层”，再考虑文件系统皮肤

### 5. 后续建议

后续深度模式开发时，建议新增一条技术路线：

- `retrieval_strategy`
  决定搜什么
- `evidence_object`
  决定返回什么结构
- `evidence_path`
  决定 Agent 如何遍历证据

也就是说，深度模式不只要有“检索策略”，还要有“证据对象与路径抽象”。
