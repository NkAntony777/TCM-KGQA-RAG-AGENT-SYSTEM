# 项目进展

更新时间：2026-04-07

## 当前状态

三元组流水线控制台已经具备以下能力：

- chunk 级 checkpoint 与断点续跑
- chunk 失败重试
- 低产出 chunk 进入重试队列
- 实时日志与状态流
- 发布到 runtime JSON
- 发布到 NebulaGraph
- 发布状态持久化与前端展示

## 2026-04-07 非向量检索主链进展

### 当前结论

- 本项目已经**基本实现非向量化主检索骨架**，核心方向已经明确为：
  - `graph + files-first + 结构化索引 + skill + planner`
- 当前已经不是“只有向量库才能回答”的阶段。
- 截至 2026-04-07 当前代码状态已经进一步收口为：
  - `quick / deep` 默认 retrieval 主路径已切到 `files_first`
  - `case QA` 默认主路径已切到结构化非向量索引
  - 旧 `dense` 与旧 case 向量链路仅作为**显式兼容 fallback** 保留，默认不再参与主链

### 当前已经落地的非向量能力

- 经典古籍 files-first 索引已建成并可读回整节：
  - `backend/storage/retrieval_local_index.fts.db`
- HERB2 现代证据语料已转为可读文档并进入 files-first 索引。
- `chapter://`、`book://`、`entity://`、`alias://` 路径体系已接入深度模式 follow-up retrieval。
- 运行时别名系统已接入：
  - `expand-entity-alias`
  - 查询扩展
  - 旧名/异名回溯
- QA 结构化非向量索引已建成：
  - `backend/storage/qa_structured_index.sqlite`
  - 已支持 `jieba + alias + 规则重排`
- 当前 `case QA` 默认已优先命中该结构化索引，返回 `structured_case_qa`。
- deep 模式 planner 已开始从“整题泛搜”转为“按缺口拆解动作”：
  - 比较题优先补未覆盖实体
  - 路径题拆成链路证据与出处证据

### 当前已修复的关键退化点

- 已确认并修复一个关键架构问题：
  - 之前 `graph/retrieval service` 端口不可达时，`tcm_service_client` 会错误退回 `mock_data`
  - 现已改为优先退回**本地真实 graph engine / retrieval engine**
- 这意味着：
  - 即使 8101 / 8102 未启动，8002 主链也不再自动退回假数据
  - deep follow-up retrieval 可以继续读取本地真实图谱与本地真实 files-first 检索层
- 同时已新增保护：
  - 当本地 retrieval 的 dense embedding 不可用时，会优先降级到 `files_first`
  - 不再因为 embedding 接口不可用直接拖垮整个 deep 链路
  - 当主链明确指定 `files_first` 时，默认**不再偷偷回退 dense**
  - 当 `case QA` 结构化索引无结果时，默认**不再自动回退向量库**

### 当前仍保留的过渡依赖

- 当前系统**还没有完全去掉 dense**。
- 现实状态应理解为：
  - 非向量链路已经成为默认主链
  - dense 已不再是默认主路径
  - 但旧引擎内部仍保留 dense / case 向量兼容代码，尚未物理删除
- 当前仍残留 dense 的位置主要有：
  - `services/retrieval_service/engine.py` 的旧 `search_hybrid`
  - `services/retrieval_service/chroma_case_store.py` 的旧 case 向量检索兼容层
- 因此，当前准确表述应是：
  - **项目已把 graph + files-first + structured index 落为默认主链；dense 与旧 case 向量链路仍作为兼容层保留，但默认关闭主导权。**

### 当前最重要的下一步

- 不再继续把工程重点放在“再补一个 planner 技巧”上。
- 当前最重要的是把以下三层彻底收口：
  - 图谱命中实体
  - 稳定产出正确 `entity:// / book:// / chapter://`
  - files-first 在正确范围内补原文
- 下一阶段目标：
  - 继续稳定 `entity:// / book:// / chapter://` 读回质量
  - 做 8002 实际 HTTP 评测，确认运行进程与本地直调一致
  - 让 deep 的 `why_this_step / new_evidence / coverage_after_step` 输出更稳定

## 2026-04-06 问答链路增量进展

- 当前多数实体问答已默认偏向 `hybrid`，不再默认落到纯 `retrieval`
- 当前已修复高难学术问题中的医疗边界误拒：
  - 涉及 `剂量 / 煎煮法 / 阈值效应 / AQP` 的研究型问题允许进入问答链路
- 当前意图识别已增强：
  - 运行时图谱词典
  - 方剂后缀正则识别
  - 可选 `jieba` 分词增强
- 当前检索层已新增 lexical sanity gate：
  - 若召回文档不包含问题核心实体锚点，则直接过滤
- 当前评测基线已同步迁移到新的产品语义：
  - 多数带实体的出处 / 原文 / 定义 / 文献类问题，默认评测期望改为 `hybrid`
- 本轮详细记录见：
  - [问答路由与评测基线更新_20260406.md](./问答路由与评测基线更新_20260406.md)
  - [无向量检索替代方案_20260407.md](./无向量检索替代方案_20260407.md)

## 本轮已落实的行为

### 回答链路与深度模式骨架

- 图谱实体查询默认 `top_k` 已按快速模式方向收敛到 `12`。
- 图谱实体查询已支持 `predicate_allowlist / predicate_blocklist`，为深度模式的定向检索做准备。
- 路由工具已新增结构化 `retrieval_strategy` 输出，而不再只有粗粒度 route。
- 路由工具现已新增 `query_analysis` 输出，暴露：
  - matched entities
  - entity types
  - intent candidates
  - matched keywords
  - graph / retrieval score
  - route reason
- 当前 `retrieval_strategy` 已能识别组成、功效、主治、出处、路径等基础意图，并给出：
  - graph query kind
  - entity / symptom / path target
  - predicate allowlist
  - candidate / final k
  - sources
  - evidence paths
- 当前已引入第一版“证据路径”抽象，用于让后续深度模式 Agent 以路径方式浏览证据，而不是直接耦合底层存储。

### 统一问答接口与双模式问答

- 当前 backend 已新增统一问答接口：
  - `/api/qa/answer`
- 当前接口支持：
  - `mode = quick`
  - `mode = deep`
- 当前 `quick` 模式已经按“固定工程链路”落地：
  - 医疗边界前置检查
  - `tcm_route_search` 路由与检索编排
  - 结构化证据抽取
  - 基于意图的确定性答案拼装
  - 区分 `factual_evidence` 与 `case_references`
- 当前 `deep` 模式已经接入现有 `agent_manager.astream(...)`：
  - 由 Agent 参与工具调用与答案生成
  - 最终仍回收到统一的结构化返回格式
  - 若深度模式不可用，会自动降级回快速模式
- 当前统一问答返回中已明确包含：
  - `answer`
  - `mode`
  - `status`
  - `route`
  - `query_analysis`
  - `retrieval_strategy`
  - `evidence_paths`
  - `factual_evidence`
  - `case_references`
  - `citations`
  - `service_trace_ids`
  - `service_backends`

### 快速模式当前定位

- 当前快速模式不是 Agent 自由规划模式，而是稳定优先的工程化链路。
- 其目标不是“最聪明”，而是：
  - 稳定返回
  - 证据可解释
  - 延迟可控
  - 明确区分事实依据与案例参考
- 当前已经能覆盖的主要问题类型包括：
  - 方剂组成
  - 方剂功效
  - 主治/适应证
  - 症状/证候到方剂
  - 图谱路径类问题
  - 带相似案例参考的病例风格问题

### 意图识别模块适配

- 已吸收 `E:\TCM_Web_System_v2` 中最有价值的骨架：
  - 分类器与路由器解耦
  - 词典匹配优先于纯关键词硬编码
  - Aho-Corasick 风格的多实体命中
  - 多标签意图候选而不是单标签硬分流
- 当前项目中已经落地新的 `TCMIntentClassifier`，位置：
  - `backend/router/tcm_intent_classifier.py`
- 当前分类器不是照搬旧项目的疾病标签，而是改写为当前图谱问答所需的标签：
  - `formula_composition`
  - `formula_efficacy`
  - `formula_indication`
  - `formula_origin`
  - `syndrome_to_formula`
  - `compare_entities`
  - `graph_path`
  - `open_ended_grounded_qa`
- 当前词典识别采用“轻量实体词典 + Aho-Corasick（若环境存在）+ 规则抽取兜底”。
- 如果运行环境没有 `ahocorasick`，系统会自动回退到子串扫描，不阻塞当前问答链路。
- `query_router.py` 与 `retrieval_strategy.py` 现已共享同一份分类结果，避免路由与策略层各自猜意图、各自漂移。

### 新增设计文档

- 详见 [意图识别模块适配方案.md](./意图识别模块适配方案.md)
- 详见 [QA向量库接入开发方案.md](./QA向量库接入开发方案.md)

### 外部 QA 向量库定位已确认

- `E:\tcm_vector_db` 已确认是本地持久化 `ChromaDB`，不是 `FAISS`、不是 `Milvus`。
- 其底层结构为：
  - `chroma.sqlite3` 元数据库
  - `hnsw-local-persisted` 向量索引目录
  - `10` 个手工分片 collection：`tcm_shard_0..9`
- 当前总记录数约 `367.7` 万条，向量维度为 `1024`。
- 当前每条记录主要包含：
  - `chroma:document`
  - `answer`
- 结合样本内容，已确认其业务定位更接近“病例/医案 QA 向量库”或“相似医案检索库”，而不是古籍知识库。
- 因此，后续接入原则已经明确：
  - 不作为快速模式默认主检索源
  - 不混入普通古籍/知识文档检索
  - 主要作为深度模式的“案例参考证据源”
  - 需要按 `10` shard fan-out 查询，再做统一过滤与重排

### 外部 QA 向量库已完成第一阶段接入

- 当前项目已经新增只读 `ChromaCaseQAStore`，位置：
  - `backend/services/retrieval_service/chroma_case_store.py`
- 当前接入方式不是依赖 `chromadb` client，而是改为：
  - `sqlite` 读取元数据
  - `hnswlib` 直接读取持久化索引
- 原因已经明确：
  - 当前库的实际 schema / config 与不同版本 `chromadb` client 存在兼容性断层
  - 继续硬依赖 client 会把运行稳定性绑死在环境版本上
- 当前系统已经新增：
  - `/api/v1/retrieval/search/case-qa`
  - `tcm_case_qa_search`
  - 旧 `qa_case_vector_db` 兼容 source（现已退居 fallback）
  - `caseqa://` evidence path 体系
- 当前深度模式链路已经可以把该库作为“相似医案参考源”接入，而不是把它误当作古籍事实源。

### 外部 QA 非向量替代链路已完成第一阶段

- 当前项目已经完成 QA 结构化非向量索引的第一阶段建设：
  - `backend/storage/qa_structured_index.sqlite`
- 当前规模：
  - `qa_records = 3162928`
  - `case_records = 481894`
- 当前已接入：
  - alias 扩展
  - `jieba` 中文切词增强
  - origin / composition / indication / case 的规则重排
- 当前作用：
  - 用于与原向量式 case QA 做横向对比
  - 当前已接管病例类问答的默认主路径
  - 向量 case QA 现仅保留为可选兼容 fallback

### 外部 QA 向量库检索性能优化已落地

- 当前 case QA 检索已经从“固定 fan-out 并行查全部分片”升级为：
  - `FTS shard 预选`
  - `按索引体积分波次 fan-out`
  - `小容量热缓存 + 淘汰`
  - `内存失败后的单 shard 重试`
- 当前目标不是单纯拉高并发，而是避免首次查询时多个大 shard 同时加载导致的内存冲击。
- 在当前真实库测试中，问题：
  - `如何治疗食生米病`
- 10 shard 检索耗时从约 `47.6s` 降到约 `35.1s`，并消除了同一测试下出现的 HNSW 内存加载失败告警。
- 这说明当前瓶颈并不是“SQLite 慢”，而是：
  - 大 shard HNSW 冷加载成本高
  - fan-out 查询需要更谨慎的调度和路由

### 自动选书

- 新建提取任务时，如果没有手动选择书籍，会进入自动批处理模式。
- 自动批处理模式会优先选取推荐书籍。
- 自动批处理模式会自动排除历史上已经完整处理过的书籍。
- 当前每批默认处理 `7` 本书。

### 自动续批

- 自动续批只作用于“新任务 + 未手动选书”的模式。
- 当前批次完成后，会自动挑选下一批未处理书籍继续执行。
- 每一批都会生成独立的 run 目录，避免单个 run 目录承载过多数据。

### 续跑语义

- `resume` 会先继续指定的已有 run。
- 当前 run 完成后，如果仍有未处理书籍，系统会继续自动开启下一批。
- 因此，`resume` 现在也接入了自动续批链路。
- 续跑当前 run 和后续新批次 run 仍然是不同的运行目录，不会合并到同一个 run 中。

## 当前默认参数

- 请求超时：`314` 秒
- 请求间隔：`1.1` 秒
- 并行 workers：`11`
- 重试 workers：`max(1, parallel_workers // 2)`，因此当前默认是 `5`

## 发布链路

- 发布 JSON：增量写入 runtime JSON，不覆盖历史已发布内容。
- 发布 Nebula：优先使用清洗后的图文件；若清洗文件不存在，则回退到原始图文件。
- Nebula 发布状态会持久化到每个 run 的 `publish_status.json`。

## 回答链路开发约束

### 图谱关系 Top-K 去重策略

- 当前图谱是多来源累积图，同一实体的同一类关系会被不同古籍反复抽取，天然存在海量重复边。
- 如果 `entity_lookup` 或后续问答链路直接对原始边做全局 `top_k`，高频重复边会挤占展示位，导致“功效”“治疗证候”“治法”等高价值关系被淹没。
- 因此，正式开发阶段必须采用“两阶段选择”。
- 第一阶段：先按 `(predicate, target, direction)` 做关系级去重或聚合，保留该关系簇中证据质量最高的一条边，同时累计证据数、来源书目数、最高置信度。
- 第二阶段：再对去重后的关系簇做展示层 `top_k`，而不是对原始边直接 `top_k`。
- 对问答系统而言，展示给模型和用户的应当是“关系簇”，不是“原始重复边”。

### 当前已落地的排序策略

- 当前实现已经从“原始边直接截断”升级为“关系簇聚合 + 融合排序 + 覆盖重排”。
- 关系簇聚合：按 `(predicate, target, direction)` 聚合，并汇总 `evidence_count`、`source_book_count`、`avg_confidence`、`max_confidence`。
- 融合排序：使用 `RRF` 融合多种排序视角，包括问题意图匹配、证据质量、来源覆盖度、关系类型优先级。
- 覆盖重排：使用受 `MMR / xQuAD` 启发的贪心重排，在前几个展示位优先拉入未覆盖的关系类型，减少“使用药材”之类高频关系独占 `top_k` 的问题。
- 当前目标不是单纯追求置信度最高，而是同时保证：信息质量高、来源覆盖广、关系类型丰富、与当前问题更贴近。

### 相关算法依据

- `MMR`：强调相关性与新颖性的平衡，适合抑制重复边反复占位。
- `xQuAD`：强调对不同“aspect”的覆盖；在本项目中可自然映射为不同关系类型（`predicate`）。
- `RRF`：适合在没有统一监督分数的情况下融合多个排序信号，工程上稳定且调参成本低。

### 后续严肃开发要求

- 在快速模式中，默认启用关系簇去重，保证固定工程链路返回的结构化知识具有可读性和覆盖度。
- 在深度模式中，Agent 检索图谱时也要优先消费去重后的关系簇，否则推理上下文会被重复证据浪费。
- 后续要补充关系簇排序指标，不只看 `confidence`，还要综合关系类型优先级、证据覆盖书数、证据条数、问题意图匹配度。
- 后续要把“原始边数量”和“去重后关系簇数量”同时暴露给调试接口，方便观察图谱噪声和检索质量。
- 后续要为关键实体查询增加回归测试，验证在海量重复边场景下，`top_k` 结果仍能覆盖“功效”“治疗证候”“使用药材”等核心关系类型。

### 当前已识别的关键性能问题

- 当前关系簇聚合仍在 Python 层执行，输入是单实体的高阶邻接边集合。对于高出度实体，这会带来额外的内存与排序开销。
- 从测试表现看，`graph_engine` 全量测试在真实 runtime 图上耗时仍偏高，说明查询期聚合和排序还存在优化空间。
- 后续应优先评估把“关系簇聚合”和“覆盖统计”下推到 SQLite 聚合查询层，减少 Python 层处理的候选边数量。
- 当前 deep 模式的主要瓶颈已不再只是 planner，而是：
  - `entity://` 路径命中后的读取稳定性
  - `route.final_route` 是否稳定维持在 `hybrid`
  - alias 扩展是否会把出处题带到错误书目范围
- 当前真实评测已经证明：
  - 如果图谱命中、路径生成、files-first 读段三者没有接牢，deep 会退化成“带一点图谱提示的 retrieval”
- 因此后续优化优先级应调整为：
  - 先修证据层
  - 再修路由稳定性
  - 最后再继续增强 planner
- 当前意图分类器仍是“轻量词典 + 规则”版本，覆盖度足够支撑当前快速/深度双模式骨架，但还未接入完整实体词表和外部问答向量库的语义反馈信号。
- 后续如果要覆盖更大的古籍实体空间，应优先补齐实体词典自动构建，而不是继续堆更多正则。
- 外部 QA 向量库虽然已经完成第一阶段接入，但首次冷启动的 HNSW shard 加载依然昂贵，深度模式必须接受高于快速模式的检索延迟。
- 当前 shard 预选仍是第一版，主要依赖 `embedding_fulltext_search` 的 trigram FTS 与轻量 query 短语抽取，后续还有继续优化空间。
- 该库依然采用 `10` 个 collection 分片，本质上仍是 query-time fan-out；如果后续深度模式调用频率升高，需要继续评估 shard 路由索引、预热与独立 service 化。
- 该库中存在少量异质样本，当前虽然已有基础过滤逻辑，但后续仍应继续强化 query intent 与案例输出结构之间的匹配约束。

## 已确认的实现边界

- 已处理历史书籍会在自动新任务中被跳过，避免重复处理。
- 手动选择书籍时，系统按用户选择执行，不自动替换为推荐书籍。
- 自动续批采用新的 run 目录，但仍在同一个后台任务线程内串行衔接。
- `resume` 默认会继续后续批次；如后续需要，也可以再加前端开关控制这一行为。

## 后续可选工作

- 新增并维护 [TOP_K策略与深度模式最佳实践.md](./TOP_K策略与深度模式最佳实践.md)，作为后续检索策略与深度模式的正式设计基线
- 用已发布图谱或字典构建脚本自动生成更完整的方剂 / 药材 / 证候 / 症状词典
- 在深度模式中把 `query_analysis` 作为 Planner 的输入，而不只作为调试输出
- 给外部 Qwen embedding 问答库定义统一的 `qa://` 证据路径和实体对齐策略
- 继续优化 case QA shard 预选策略，减少深度模式中不必要的 HNSW shard 打开次数
- 为 case QA 检索增加更细粒度的调试指标，例如：
  - 命中 shard 数
  - 跳过 shard 数
  - FTS 预选分数
  - 索引冷加载耗时
- 为“每批书籍数量”提供前端可配置入口
- 为 `resume` 增加前端可见的“完成当前 run 后继续下一批”开关
- 在历史页增加自动批次链路的关联展示
