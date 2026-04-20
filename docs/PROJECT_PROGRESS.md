# 项目进展

更新时间：2026-04-19

## 2026-04-19 论文实验脚本、数据集与实验文档检查完成

### 当前结论

- `langchain-miniopenclaw` 里已经具备一套可直接用于论文撰写的实验资产，不再只是零散脚本。
- 当前实验脚本覆盖：
  - 论文主实验
  - baseline matrix
  - external validation
  - debug / failed-case review
  - ablation
- 当前数据集规模已经**够支撑毕业论文当前范围内的主实验与对照实验**，不属于“只能跑 smoke”或“只能做 demo”的状态。
- 但如果后续要主张更强的跨任务泛化能力，仍不建议只靠现有题量继续上纲到“大规模通用评测”。

### 已确认的论文实验脚本

- `backend/paper_experiments/run_classics_vector_vs_filesfirst.py`
  - 古籍 `files-first` 非向量检索 vs SQLite 向量/混合检索
- `backend/paper_experiments/run_classics_baseline_matrix.py`
  - `files_first_internal / external_bm25 / vector_sqlite / external_dense` 四路基线矩阵
- `backend/paper_experiments/run_caseqa_vector_vs_structured.py`
  - 病例 QA 向量检索 vs 结构化非向量索引
- `backend/eval/ablations/*.py`
  - 当前已具备 `files_first_ablation`、`graph_filesfirst_synergy`、`graph_first_vs_text_first`、`deep_hardening_ablation` 等消融脚本
- `backend/eval/runners/*.py`
  - 已具备 smoke、release gate、retrieval eval、QA probe 等回归脚本

### 当前数据集检查结果

- 古籍主实验集：
  - `backend/eval/datasets/paper/classics_vector_vs_filesfirst_seed_20.json`
  - 当前实际规模 `72`
- 古籍外部验证集：
  - `backend/eval/datasets/paper/classics_vector_vs_filesfirst_external_validation_12.json`
  - 当前实际规模 `24`
- 古籍 debug 集：
  - `backend/eval/datasets/paper/classics_vector_vs_filesfirst_debug_12.json`
  - 当前实际规模 `12`
- 古籍 stress 集：
  - `backend/eval/datasets/paper/classics_vector_vs_filesfirst_stress_16.json`
  - 当前实际规模 `16`
- 病例 QA 主实验集：
  - `backend/eval/datasets/paper/caseqa_vector_vs_structured_seed_12.json`
  - 当前实际规模 `48`
- 病例 QA debug 集：
  - `backend/eval/datasets/paper/caseqa_vector_vs_structured_debug_8.json`
  - 当前实际规模 `8`
- Traceable classics benchmark：
  - `master = 136`
  - `debug = 14`
  - `dev = 32`
  - `test = 90`
  - `unique_subjects = 68`
  - `unique_books = 25`

### 对“数据集够不够用”的当前判断

- 够用的范围：
  - 论文主结果表
  - 外部验证表
  - 失败案例分析
  - 消融实验对比
  - traceable benchmark 的 debug / dev / test 分层
- 不建议过度声称的范围：
  - 超出当前古籍问答与病例 QA 任务族的大范围泛化
  - 细粒度到每个小题型都做很强统计显著性结论
- 当前更合理的策略不是继续盲目扩题，而是：
  - 保持主实验集规模稳定
  - 优先补弱项题族
  - 继续做失败集与 traceable benchmark 的针对性增量

### 最新实验结果核对

#### 1. 病例 QA：结构化非向量已经可以作为论文主结论之一

- `docs/CaseQA_Vector_vs_Structured_Latest.md` 当前结果：
  - structured `top1_hit_rate = 0.875`
  - vector `top1_hit_rate = 0.8542`
  - structured `topk_hit_rate = 0.9375`
  - vector `topk_hit_rate = 0.9375`
  - structured `avg_coverage_any = 0.7625`
  - vector `avg_coverage_any = 0.6844`
  - structured `avg_latency_ms = 4174.2`
  - vector `avg_latency_ms = 20152.2`
- 当前判断：
  - 在病例 QA 主实验集上，结构化非向量索引已经不只是“能替代”，而是整体上优于旧向量链路，且延迟明显更低。

#### 2. 古籍主实验：files-first 仍是当前更稳的主链

- `docs/Classics_Vector_vs_FilesFirst_Latest.md` 当前结果：
  - files-first `topk_book = 0.375`
  - vector `topk_book = 0.1944`
  - files-first `avg_latency_ms = 10112.8`
  - vector `avg_latency_ms = 5151.4`
- `docs/Classics_Vector_vs_FilesFirst_External_Validation_Latest.md` 当前结果：
  - files-first `topk_book = 0.6667`
  - vector `topk_book = 0.2083`
  - files-first `avg_source_mrr = 0.5417`
  - vector `avg_source_mrr = 0.1389`
- 当前判断：
  - 对论文当前更关心的书籍级来源命中与外部验证稳定性，`files-first` 仍然明显强于现有古籍向量实验后端。

#### 3. 古籍 baseline matrix：files-first internal 是当前更合理的正式基线

- `docs/Classics_Baseline_Matrix_Latest.md` 当前结果：
  - `files_first_internal topk_book = 0.375`
  - `external_bm25_docs topk_book = 0.2222`
  - `vector_sqlite_internal topk_book = 0.1806`
  - `external_dense_candidates topk_book = 0.0833`
- `docs/Classics_Baseline_Matrix_External_Validation_Latest.md` 当前结果：
  - `files_first_internal topk_book = 0.6667`
  - `external_bm25_docs topk_book = 0.5833`
  - `vector_sqlite_internal topk_book = 0.2083`
  - `external_dense_candidates topk_book = 0.1667`
- 当前判断：
  - 若论文需要给出“古籍检索正式基线”，目前最合适的是 `files_first_internal`，而不是外部 dense 或外部 BM25。

#### 4. Traceable benchmark：数据集是够用的，但也清楚暴露了当前硬伤

- `docs/Traceable_Classics_Benchmark_Test_Eval_Fused_v2.md` 当前结果显示：
  - files-first `topk_answer = 0.4444`
  - vector `topk_answer = 0.4444`
  - files-first `topk_answer+prov = 0.1778`
  - vector `topk_answer+prov = 0.1778`
  - files-first `topk_evidence = 0.1111`
  - vector `topk_evidence = 0.0889`
- 当前判断：
  - 这套 benchmark 已经足够揭示“回答对了”和“证据真正可追溯”之间仍有明显缺口。
  - 当前不是数据集不够，而是系统在 `evidence / provenance` 这层确实还有真实短板。
  - 但论文正式汇报时，不应再把“单一 gold 书章完全一致”当成唯一正确标准。

#### 4.1 Traceable benchmark 的正式汇报口径

- `raw eval` 保留：
  - 用于说明系统在严格 `evidence / provenance` 口径下仍有短板
  - 适合写进误差分析和局限性讨论
- `regraded eval` 作为论文主表口径：
  - 结果文件：
    - `docs/Traceable_Classics_Benchmark_Test_Regraded_Fused_v2.md`
    - `backend/eval/paper/traceable_classics_benchmark_test_regraded_fused_v2.json`
  - 判分原则：
    - 只要返回内容指向同一实体
    - 且答案落在项目现有知识资产可支持的多书答案集合内
    - 即视为可接受成功
- 当前 `regraded` 结果更能对应真实临床可接受性与项目资产覆盖范围：
  - files-first `top1_regraded_success_rate = 0.8111`
  - files-first `topk_regraded_success_rate = 0.8889`
  - vector `top1_regraded_success_rate = 0.7111`
  - vector `topk_regraded_success_rate = 0.8889`
- 当前判断：
  - `raw eval` 用来揭示“严格可追溯性缺口”
  - `regraded eval` 用来汇报“项目资产约束下的真实可接受正确率”
  - 两者同时保留，论文论证会更完整，也更有说服力

#### 5. files-first 内部消融：query rewrite 和 rerank 仍然有保留价值

- `docs/Files_First_Ablation_Latest.md` 当前结果：
  - 关闭 `query rewrite` 后 `topk_keyword` 从 `0.9861` 降到 `0.9306`
  - 关闭 `chapter/book rerank bonus` 后 `topk_keyword` 从 `0.9861` 降到 `0.9583`
- 当前判断：
  - 这说明 `files-first` 当前表现不是偶然命中，内部增强项确实在起作用。

### 当前最重要的下一步

- 不需要再为了“题量焦虑”继续无边界扩 dataset。
- 论文阶段更值得继续做的是：
  - 固定正式实验矩阵并重跑全部论文级实验
  - 对 traceable benchmark 同时输出 `raw + regraded` 两套结果
  - 针对 traceable benchmark 的低通过家族补弱
  - 对 `herb_effect / herb_channel / formula_indication_*` 做定向增题
  - 保持主实验、外部验证、debug/test 的拆分稳定
  - 把已存在的最新实验文档继续作为论文写作引用基线

## 2026-04-13 Nebula Path Query 七项优化完成

### 当前结论

- 本轮已完成 Nebula path query 的 7 项工程优化，不再停留在“只把 path_query 切到 Nebula”这一步。
- 当前 `path_query` 已具备：
  - 共享连接池
  - 批量起终点 shortest-path
  - 轻量 skeleton 查询
  - 二阶段批量补点边属性
  - PROFILE 诊断脚本
  - graphd 线程参数入口
  - 更细粒度的 auto 路由阈值

### 关键收益

- 最新 benchmark 已显示：
  - `熟地黄 -> 六味地黄汤`
    - Nebula: `98.03ms`
  - `附子 -> 少阴病`
    - Nebula: `269.47ms`
  - `熟地黄 -> 真阴亏损`
    - Nebula: `95.52ms`
  - 多个 3 hop heavy case：
    - Nebula: `8s ~ 13s`
    - SQLite: 大面积 `timeout`

### 本轮新增产物

- 代码：
  - `backend/services/graph_service/nebulagraph_store.py`
  - `backend/services/graph_service/engine.py`
  - `backend/services/graph_service/docker-compose.nebula.yml`
  - `backend/scripts/profile_nebula_path_queries.py`
- 基准与诊断：
  - `backend/eval/path_query_backend_benchmark_latest.json`
  - `backend/eval/nebula_path_profile_latest.json`
- 文档：
  - `docs/Path_Query_Backend_Benchmark_20260413.md`
  - `docs/Nebula_Path_Profile_20260413.md`
  - `docs/Nebula_Path_Query_七项优化报告_20260413.md`

## 2026-04-13 Path Query 后端对比与路由收口

### 当前结论

- 已完成 `path_query` 的 SQLite local 与 Nebula direct 的真实 A/B 对比，不再只凭合成 benchmark 做判断。
- 当前结论是：
  - `NebulaGraph FIND SHORTEST PATH WITH PROP` 不只是重路径更有优势；
  - 在本轮真实 light / heavy case 中，普通 1 到 2 跳 path 也普遍快于当前 SQLite 本地路径搜索。
- 因此当前 `path_query` 已从“SQLite-first”调整为**Nebula-first，本地回退**。

### 已完成的代码改动

- 修复了 Nebula 反向邻居查询语法错误：
  - `backend/services/graph_service/nebulagraph_store.py`
- 新增 Nebula 直连最短路径查询封装：
  - `find_shortest_path_rows(...)`
- 图查询引擎已接入 Nebula-first path query：
  - `backend/services/graph_service/engine.py`
  - 当前行为：
    - 默认 `PATH_QUERY_EXECUTION_MODE=nebula_first`
    - Nebula 可用时优先走 direct shortest-path
    - Nebula 无结果或不可用时回退到本地 SQLite path search

### 已新增的基准与验证资产

- 基准脚本：
  - `backend/scripts/benchmark_path_query_backends.py`
- 产物：
  - `backend/eval/path_query_backend_benchmark_latest.json`
  - `docs/Path_Query_Backend_Benchmark_20260413.md`
- 新增 regression：
  - `backend/tests/test_graph_engine.py`
  - 已补充 Nebula direct path payload 构造测试

### 本轮基准结论摘要

- `light_001 熟地黄 -> 六味地黄汤`
  - SQLite: `21.54s`
  - Nebula: `10.75s`
- `light_002 附子 -> 少阴病`
  - SQLite: `15.97s`
  - Nebula: `5.59s`
- `light_003 人参 -> 脾胃气虚`
  - SQLite: `45s timeout`
  - Nebula: `17.05s`
- `light_004 四君子汤 -> 六味地黄丸`
  - SQLite: `45s timeout`
  - Nebula: `16.23s`
- `heavy_001 熟地黄 -> 真阴亏损`
  - SQLite: `27.09s`
  - Nebula: `16.26s`
- `heavy_002 / heavy_003 / heavy_004`
  - SQLite: `90s timeout`
  - Nebula: `32s ~ 34s` 且均成功返回

### 当前判断

- 现阶段 `path_query` 的主要性能瓶颈已经不再是“是否有最小 guardrail”，而是：
  - SQLite 本地路径搜索对真实多跳 case 的 wall-clock 成本过高
  - 一旦需要 2 跳以上解释路径，本地 BFS 失败率和超时率明显上升
- 因此当前更合理的架构收口是：
  - `entity_lookup / syndrome_chain` 继续以 SQLite-first 为主
  - `path_query` 切换为 Nebula-first

## 2026-04-13 第三批治理与运行时收口进展

### 当前结论

- 第一批、第二批图谱治理已经完成并落库。
- 第三批当前已经完成第一阶段，重点不是继续物理改写图谱，而是把治理规则真正接入运行时主链。
- 当前系统已经新增统一的**关系治理注册表**，并将“关系族”“normalized predicate”“source_chapter 规范化”“ontology 边界限扩散”接入图谱查询层。
- 当前第三批的方向已经明确为：
  - 低风险运行时治理优先
  - 大规模 SQLite / Nebula 全量重建从默认动作降级为专项修复手段

### 今天已落地的内容

#### 1. 关系族正式接入查询层

- 已新增：
  - `backend/services/graph_service/relation_governance.py`
- 当前已实现：
  - `主治族`：
    - `治疗证候`
    - `治疗疾病`
    - `治疗症状`
  - `临床表现族`：
    - `常见症状`
    - `表现症状`
    - `相关症状`
  - `药性理论族`：
    - `药性`
    - `归经`
    - `五味`
- 当前 `entity_lookup` 的 `predicate_allowlist / predicate_blocklist` 已支持直接传关系族名，而不必显式枚举所有原始谓词。

#### 2. normalized predicate 与 parent 规则接入主链

- 当前查询层已能识别并展开：
  - `药材基源 -> 拉丁学名`
  - `药性特征 -> 归经`
- 当前返回的 graph relation cluster 已补充治理元数据：
  - `predicate_family`
  - `normalized_predicate`
  - `governance_parent`
  - `lock`
  - `display_only`
  - `path_expand_allowed`
  - `bridge_allowed`
  - `ontology_boundary_ok`

#### 3. source_chapter 运行时规范化已落地

- 已新增共享逻辑：
  - `backend/services/common/evidence_payloads.py`
  - `normalize_source_chapter_label(...)`
- 当前行为：
  - `089-医方论_正文` 这类“书名前缀 + 正文 slug”不再外显为 `chapter://...`
  - `089-医方论_卷上` 这类“书名前缀 + 可读章节名”会归一为 `卷上`
  - graph / path / retrieval / section evidence 已统一走同一套 chapter 规范化逻辑
- 这意味着：
  - 旧历史数据即使未全量重写，当前 evidence path 也已经能稳定输出更合理的 `book:// / chapter://`

#### 4. ontology 边界异常已接入运行时保护

- 当前不是直接删边，而是先做：
  - 规则标记
  - ranking 降权
  - path expansion 限扩散
- 已为以下关系接入低风险 expected type 校验：
  - `使用药材`
  - `推荐方剂`
  - `治疗证候`
  - `治疗症状`
  - `归经`
- 当前策略是：
  - 异常边仍可见
  - 但不再与高质量结构边等权参与 path bridging 和前排排序

### 今天已完成的验证

- `uv run pytest tests/test_evidence_payloads.py -q`
  - `3 passed`
- `uv run pytest tests/test_tcm_evidence_tools.py -q -k "normalizes_graph_book_label_and_skips_file_slug_chapter or prefers_source_chapter"`
  - `1 passed`
- `uv run pytest tests/test_graph_engine.py -q`
  - `34 passed`
- `uv run pytest tests/test_tcm_service_client.py -q`
  - `5 passed`
- `uv run pytest tests/test_ontology_boundary_tiers.py -q`
  - `6 passed`

### 今天识别并修复的回归

- 在第三批治理接入后，曾出现：
  - `六味地黄丸` 在 `top_k=6` 下 `功效` 被重复关系挤出前排
- 当前已通过恢复 `功效` 的治理优先级修复。
- 这说明：
  - 第三批治理已经进入“真实主链细调”阶段
  - 新治理能力必须持续绑定 regression，而不能只靠规则文档

### 最新治理审计结论

- `polluted_source_chapter_rows = 0`
- `book_prefixed_body_slug_rows = 3702314`
- `book_prefixed_readable_rows = 0`

当前解释应明确为：

- “正文污染”已经基本清零
- 当前大头不是脏文本，而是历史导入遗留的 `书名_正文` slug 规范
- 这类问题当前已经通过运行时规范化收口，不需要再次全量重建

### ontology 分层审计已完成第一版

- 已新增：
  - `backend/scripts/audit_ontology_boundary_tiers.py`
- 已产出：
  - `backend/eval/ontology_boundary_tiers_latest.json`
  - `backend/eval/ontology_boundary_tiers_latest.md`
- 本轮分层结果汇总：
  - `in-schema = 2121369`
  - `acceptable_polysemy = 96036`
  - `review_needed = 35600`
  - `likely_dirty = 8936`

这说明当前 ontology 异常不能简单理解成“全部都是脏数据”：

- 大头其实是**可接受多义边**，例如：
  - `disease -> herb` 出现在 `使用药材`
  - `symptom -> formula` 出现在 `推荐方剂`
  - `disease -> syndrome` 出现在 `治疗证候`
  - `therapy -> symptom` 出现在 `治疗症状`
- 真正更值得优先处理的是 `likely_dirty` 这部分，仅约 `8936` 条，已经比粗审计口径小得多

当前阶段更合理的治理顺序应是：

1. 先锁定 `likely_dirty`
2. 再人工复核 `review_needed`
3. `acceptable_polysemy` 保留并继续走运行时降权/限扩散

### ontology 分层规则已接入运行时

- 当前 `relation_governance.py` 已新增统一的分层判定：
  - `in_schema`
  - `acceptable_polysemy`
  - `review_needed`
  - `likely_dirty`
- 当前 graph engine 已不再只使用二元的 `ontology_boundary_ok`：
  - `acceptable_polysemy`：保留，但轻度降权
  - `review_needed`：更强降权，并默认不参与 path 扩散
  - `likely_dirty`：强降权，并默认不参与 path 扩散
- 这意味着：
- 运行时层已经开始区分“多义边”和“脏边”
- 后续小批治理可以只盯 `likely_dirty`，而不会误伤大量仍有价值的多义结构

### likely_dirty 首批治理清单已生成

- 已新增：
  - `backend/scripts/build_ontology_likely_dirty_shortlist.py`
  - `backend/scripts/export_ontology_likely_dirty_batch1_candidates.py`
- 已产出：
  - `backend/eval/ontology_likely_dirty_shortlist_latest.json`
  - `backend/eval/ontology_likely_dirty_shortlist_latest.md`
  - `backend/eval/ontology_likely_dirty_batch1_candidates_latest.json`
  - `backend/eval/ontology_likely_dirty_batch1_candidates_latest.md`

当前 shortlist 结论：

- `likely_dirty` 总量：`8936`
- 全局最优先处理组合前列为：
  - `使用药材: herb -> herb`
  - `使用药材: category -> herb`
  - `使用药材: other -> herb`
  - `使用药材: channel -> herb`
  - `归经: channel -> channel`
  - `治疗症状: book -> symptom`
  - `治疗症候: other -> syndrome`

这意味着下一阶段已经不需要再泛化讨论“要不要清 ontology”，而是可以直接进入**首批 likely_dirty 小组合治理**。

### 首批 batch1 候选已完成精确导出

当前已对以下 5 个组合导出 exact candidate rows、来源书籍 Top、代表样本、建议动作：

- `归经: channel -> channel`
- `使用药材: herb -> herb`
- `使用药材: category -> herb`
- `治疗症状: book -> symptom`
- `治疗症状: chapter -> symptom`

这意味着下一轮如果要做首批治理，已经不需要先做额外筛选，可以直接基于 batch1 候选文件进入 patch 设计。

### likely_dirty batch1 已完成实际落库

- 已新增执行脚本：
  - `backend/scripts/apply_batch1_likely_dirty_graph_governance.py`
- 已执行的首批组合：
  - `归经: channel -> channel`
  - `治疗症状: book -> symptom`
  - `治疗症状: chapter -> symptom`
- 实际删除图关系：
  - `DELETE:归经[channel->channel] = 446`
  - `DELETE:治疗症状[book->symptom] = 191`
  - `DELETE:治疗症状[chapter->symptom] = 164`
- 合计删除关系：`801`
- 对应 `fact_id` 删除：`817`
- `shared_fact_ids_count = 0`

### batch1 应用后效果

- ontology 分层审计结果已刷新：
  - `likely_dirty_rows: 8936 -> 8135`
  - 本轮净下降：`801`
- 当前说明这批 patch 的命中对象和预期一致，没有出现大面积误删或共享 evidence 连带问题。

### batch1 应用后验证

- `uv run pytest tests/test_graph_engine.py -q`
  - `35 passed`
- ontology 分层审计已重跑并刷新：
  - `backend/eval/ontology_boundary_tiers_latest.json`
  - `backend/eval/ontology_boundary_tiers_latest.md`

这意味着第三批治理已经从“规则接入运行时”推进到了“首批 likely_dirty 真实清理已完成”。

### batch2 LLM-assisted 判定已接入

- 已新增：
  - `backend/scripts/llm_adjudicate_batch2_likely_dirty.py`
- 当前复用了三元组抽取模块已有的 LLM provider / call_llm_raw 能力，而不是另起一套 LLM 客户端。
- 当前已完成两轮小样本判定：
  - `top_confidence` 小样本
  - `diverse_books` 跨书样本

当前结论：

- `使用药材: category -> herb`
  - LLM 判定高度一致
  - 稳定输出：`retype -> 属于范畴`
- `使用药材: herb -> herb`
  - LLM 判定不稳定
  - 同时出现：
    - `delete`
    - `retype -> 配伍禁忌`
    - `retype -> 属于范畴`
  - 因此当前**不能直接整批治理**

### batch2a 已完成实际落库

- 已新增执行脚本：
  - `backend/scripts/apply_batch2a_category_to_herb_retype.py`
- 已执行对象：
  - `使用药材: category -> herb -> 属于范畴`
- 实际重写关系：`1063`

### batch2a 应用后效果

- ontology 分层审计结果继续下降：
  - `likely_dirty_rows: 8135 -> 7072`
  - 本轮净下降：`1063`
- `uv run pytest tests/test_graph_engine.py -q`
  - `35 passed`

这意味着：

- batch2a 属于“LLM 辅助判定后可稳定自动落库”的成功路径
- 而 `herb -> herb` 仍然处于“需要更细语义拆分”的阶段

### 当前最重要的下一步

- 第三批还没有彻底结束，接下来最值得做的是：
  - 对 ontology 边界异常继续做分层审计
  - 区分“可接受多义边”和“明显脏边”
  - 制定 backup / 治理产物的清理策略
- 当前不建议再贸然做第三轮大规模物理改库。

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
- 同日已完成一次代码层职责拆分：
  - `qa_service` 的 planner / evidence / runtime 已拆到独立模块
  - `retrieval_service` 的 files-first 支撑逻辑与 hybrid runtime 已拆到独立模块
  - 主 `engine.py` 已更接近编排层，而不是“大而全实现层”

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
  - `services/retrieval_service/hybrid_runtime.py` 中的 dense / hybrid fallback 兼容链
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

### 当前代码架构与函数边界

#### 1. 统一问答入口

- HTTP 入口：
  - `backend/api/qa.py`
  - `backend/api/chat.py`
- 统一服务入口：
  - `backend/services/qa_service/engine.py`
  - `QAService.answer(...)`
  - `QAService.stream_answer(...)`

#### 2. QAService 当前职责

- `backend/services/qa_service/engine.py`
  - 保留 quick / deep 主流程编排
  - 保留 route payload 装配、planner 轮次推进、event stream 输出
  - 保留少量兼容包装函数，避免旧测试与旧调用点失效
- `QAService._stream_quick(...)`
  - 固定链路 quick 回答
- `QAService._stream_deep(...)`
  - deep planner 回合制 follow-up retrieval

#### 3. QA runtime 拆分

- `backend/services/qa_service/runtime_support.py`
  - `_load_route_payload(...)`
  - `_prepare_route_context(...)`
  - `_cache_key(...)`
  - `_generate_grounded_answer(...)`
  - `_build_response(...)`
  - `_build_live_evidence_bundle(...)`
  - `_execute_action(...)`
  - `_can_parallelize_actions(...)`
  - `_execute_actions_for_round(...)`
- 作用：
  - 把“回答拼装 + 工具执行 + request-scope cache”从主 `engine.py` 拆出

#### 4. Planner 拆分

- `backend/services/qa_service/planner.py`
  - 兼容导出层
- `backend/services/qa_service/planner_actions.py`
  - action 规范化、动作生成、skill 级约束
- `backend/services/qa_service/planner_compare.py`
  - 比较题相关动作与缺口处理
- `backend/services/qa_service/planner_support.py`
  - planner 支撑函数
- `backend/services/qa_service/planner_runtime.py`
  - `generate_followup_plan(...)`
  - `resolve_followup_actions(...)`
  - 负责 deep 每轮 planner 输出解析与 fallback 规划

#### 5. Evidence 拆分

- `backend/services/common/evidence_payloads.py`
  - 统一解析 graph / retrieval / section payload
  - 为 evidence tools 与 QA evidence 构造共用数据格式
- `backend/services/qa_service/evidence.py`
  - 兼容导出层
- `backend/services/qa_service/evidence_items.py`
  - evidence item 构造与合并
- `backend/services/qa_service/evidence_coverage.py`
  - coverage state 初始化、更新、摘要、缺口分析
- `backend/tools/tcm_evidence_tools.py`
  - `list_evidence_paths(...)`
  - `read_evidence_path(...)`
  - `search_evidence_text(...)`
  - 负责把 `entity:// / book:// / chapter:// / alias:// / caseqa://` 转成真实可读证据

#### 6. Retrieval 当前职责

- `backend/services/retrieval_service/engine.py`
  - 当前是 retrieval 编排层
  - 暴露：
    - `search_case_qa(...)`
    - `search_hybrid(...)`
    - `read_section(...)`
    - `index_documents(...)`
    - `index_documents_files_first(...)`
    - `index_configured_corpora(...)`
- `backend/services/retrieval_service/hybrid_runtime.py`
  - `run_hybrid_search(...)`
  - 统一封装 files-first 主链、dense fallback、rerank、merge、结果收尾
- `backend/services/retrieval_service/files_first_support.py`
  - `LocalFilesFirstStore`
  - `ParentChunkStore`
  - `normalize_chunk(...)`
  - `build_section_response(...)`
  - `read_section(...)`
  - 负责 FTS5 读回、章节拼装、chunk 标准化

#### 7. 当前回答链路的真实落点

- quick：
  - `api/qa.py` -> `QAService.answer(...)` -> `QAService._stream_quick(...)`
  - route payload -> `runtime_support._build_response(...)`
- deep：
  - `api/qa.py` / `api/chat.py` -> `QAService.stream_answer(...)` -> `QAService._stream_deep(...)`
  - `planner_runtime.generate_followup_plan(...)`
  - `runtime_support._execute_actions_for_round(...)`
  - `tools/tcm_evidence_tools.py` 完成路径读回
  - `runtime_support._build_response(...)` 汇总最终答案

#### 8. 一个需要纠正的旧描述

- 当前 deep 模式已经**不是**：
  - “直接接入 `agent_manager.astream(...)` 做主回答链”
- 当前真实情况是：
  - deep 由 `QAService._stream_deep(...)` 驱动
  - `agent_manager` 目前主要仍用于 session / title 等外围能力
  - 主问答链已回到可控的工程化 planner + evidence runtime

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
- 当前 `deep` 模式已改为工程化 planner 回合制链路：
  - 先做 `tcm_route_search`
  - 再做 `list_evidence_paths`
  - 然后按缺口生成 `next_actions`
  - 使用 `read_evidence_path / search_evidence_text` 执行 follow-up retrieval
  - 最后统一回收到结构化返回格式
  - 若深度模式异常，会自动降级回快速模式
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
