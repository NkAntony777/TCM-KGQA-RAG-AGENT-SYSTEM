# 重构计划与测试矩阵

更新时间：2026-05-08

## 2026-05-08 执行进展

本轮已完成低风险重构切片，并继续完成两项高风险边界拆分。重点是冻结行为、拆出纯解析/计划/执行模块，并维护测试矩阵：

- P0 已完成一部分：README 口径已校准；`_tmp_pytest`、`pytest-cache-files-*` 已加入测试/静态分析排除，`test_no_mock_fallback.py` 对不可访问运行产物目录更稳健。
- P1 已完成一部分：新增 `backend/tools/evidence_path_resolver.py`，统一解析和排序 `entity://`、`alias://`、`book://`、`chapter://`、`qa://`、`caseqa://`、`path://`；`EvidenceNavigator.read_evidence_path` 改为基于解析对象派发。
- P2 已完成一部分：新增 `backend/tools/tcm_route_planning.py`，把 route plan 生成从 `TCMRouteSearchTool` 中抽离；旧 `_build_route_plan` 仍保留为兼容 adapter。
- P3 已完成一部分：新增 `backend/services/retrieval_service/retrieval_responses.py`，集中构造 retrieval 空结果响应，降低 fallback 分支重复。
- P2 继续推进：新增 `backend/tools/tcm_route_execution.py`，把 graph/retrieval/case-QA 执行编排、降级判断、payload metadata 拼装从 `TCMRouteSearchTool` 中抽离；`TCMRouteSearchTool` 仍保留旧 helper 名和服务调用 patch 点作为兼容 adapter。
- P3 继续推进：新增 `backend/services/retrieval_service/query_service.py`，引入 `RetrievalQueryService` 作为在线查询边界；`RetrievalEngine.search_hybrid/search_case_qa/read_section/rewrite_query` 仍保留为兼容转发，索引构建和 vector compatibility flags 未改变。
- P3 继续推进：`RetrievalQueryService` 已拆成 `FilesFirstSearchService`、`CaseQASearchService`、`SectionReadService`、`QueryRewriteService` 四个子服务；聚合层只负责组合，`RetrievalEngine` 继续作为兼容入口。
- P3 继续推进：新增 `backend/services/retrieval_service/vector_compatibility.py`，将 files-first vector fusion 判断、dense 候选水合和 RRF 合并从 `hybrid_runtime.py` 抽离；默认 files-first 与 dense fallback 开关语义不变。
- P3 继续推进：新增 `backend/services/retrieval_service/files_first_metadata.py`，将古籍 header 解析、`classic://` 章节 key、章节正文合并、章节 summary/topic/entity metadata 生成从 `files_first_support.py` 抽离；`files_first_support.py` 继续重导出旧函数名以兼容维护脚本和实验代码。
- P3 继续推进：扩展 `backend/services/retrieval_service/files_first_schema.py`，集中 `FILES_FIRST_SCHEMA_VERSION`、必需列集合、schema status、legacy docs 读取、schema version 写入和 in-place legacy migration；`LocalFilesFirstStore` 只保留迁移编排和 metadata/nav-group 回调。
- P3 继续推进：新增 `backend/services/retrieval_service/files_first_build_rows.py`，将 rebuild 阶段 docs row、FTS row 构造和批量插入 SQL 从 `files_first_support.py` 抽离；`rebuild()` 主循环现在只负责 batch、checkpoint、进度、索引/nav-group 编排。
- P3 继续推进：新增 `backend/services/retrieval_service/files_first_build_state.py`，集中 rebuild state JSON 读写、resume 判断、docs/nav-groups/interrupted/failed/completed 状态 patch 和返回 payload 构造；`rebuild()` 不再散落状态字符串和 JSON 写入。
- P4 已完成一部分：新增 `backend/services/graph_service/fallback_adapter.py`，Nebula primary 不再直接调用 SQLite fallback 的私有方法或内部 store，而是通过 `LocalGraphFallbackAdapter` 访问公开 fallback 边界。
- P5 已完成第一层状态收敛：新增 `backend/scripts/pipeline_console/runtime_state.py`，集中持有 pipeline console 的 job lock、current job、日志文件、cancel event、job thread、book status lock 和 runtime graph mutation lock；`pipeline_server.py` 旧全局名仍保留，并通过同步 helper 吸收旧测试/脚本对 `_current_job` 的兼容性重绑定。
- P3 继续推进：新增 `backend/services/retrieval_service/files_first_nav_groups.py`，将 nav-group seed rows、manifest 统计、payload 构建 wrapper、`nav_groups`/`book_outlines` 写入 SQL 从 `files_first_support.py` 抽离；`LocalFilesFirstStore._rebuild_nav_groups()` 只保留编排入口。
- P3 继续推进：`backend/services/retrieval_service/files_first_reader.py` 引入 `FilesFirstReaderContext` 和 `SummaryCache` 协议，读段逻辑不再依赖 `Any` 或 store 私有方法；`LocalFilesFirstStore` 新增公开 `resolve_section_metadata()` 作为兼容边界。
- P3 继续推进：新增 `backend/services/retrieval_service/files_first_seed_queries.py`，把 `LocalFilesFirstStore.search()` 中的 direct seed 与 descriptive clause seed SQL 拆出，为后续安全拆分 FTS/ranking/final scoring 打基础。
- 测试矩阵继续收敛：新增 `backend/tests/test_temp_utils.py`，统一项目内 `_tmp_test` 目录和 `connect_test_sqlite()` row factory 约定，减少 Windows Temp/SQLite 权限与 tuple row 误报。
- P5 继续推进：新增 `backend/scripts/pipeline_console/state_transitions.py`，先抽象 cancel 状态迁移；`job_state.mark_cancel_requested()` 在锁内委托纯状态迁移函数，保持现有行为不变。
- P3 高风险拆分继续推进：新增 `backend/services/retrieval_service/files_first_fts_queries.py`，将 `LocalFilesFirstStore.search()` 中 nav-group FTS 与 docs FTS SQL 执行循环抽离为候选生成边界；新增 `backend/services/retrieval_service/files_first_ranking.py`，将 synthetic section 合成、同 section 去重、book narrowing、coverage tie-break、最终结果格式化抽离为纯 ranking 边界。
- P5 状态迁移继续推进：`state_transitions.py` 增加 done/cleaning/publishing/finished/error 状态迁移，`extraction_completion.py` 改为委托状态迁移函数；完成、取消、partial、error 形状由独立单元测试锁定。
- 权限误报治理继续推进：`test_files_first_support.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_retrieval_engine.py`、`test_qa_structured_store.py`、`test_pipeline_server.py`、`test_tcm_triple_console.py` 已从系统 `tempfile`/`tmp_path` 迁到项目内 `_tmp_test`，减少 Windows sandbox 临时目录 `.lock`、SQLite/open/write 权限误报。
- P3 高风险拆分继续推进：新增 `backend/services/retrieval_service/files_first_search_plan.py`，将 `search()` 中 query context、focus/book/ranking terms、match queries、descriptive clauses、direct seed terms 与 seed target book 选择抽离为纯 planning 边界；`LocalFilesFirstStore.search()` 现在主要保留 schema/store 编排、metadata candidate、seed query、FTS query 和 ranking orchestration。
- P5 状态迁移继续推进：`state_transitions.py` 增加 `mark_started()`，`job_state.mark_started_and_sync()` 统一启动状态写入与 `_current_job` 同步；`extraction_job_runner.py` 不再裸调用初始 `sync_state()`。
- P3 adapter 化继续推进：新增 `backend/services/retrieval_service/files_first_rebuild.py`，将 `LocalFilesFirstStore.rebuild()` 的 reuse-existing-docs、resume temp DB、docs batch insert、nav-groups、schema version、state transition 和 replace-file 编排抽离；`LocalFilesFirstStore.rebuild()` 变为薄委托。
- P3 adapter 化继续推进：新增 `backend/services/retrieval_service/files_first_search.py`，将 `LocalFilesFirstStore.search()` 的 schema check、metadata candidates、seed query、FTS candidate query 和 ranking orchestration 抽离；`LocalFilesFirstStore.search()` 变为薄委托。
- P4 继续推进：`backend/services/graph_service/fallback_adapter.py` 新增 `GraphFallbackBackend` 协议，并补齐 `health/entity_lookup/path_query/syndrome_chain` 公共 fallback 方法；`NebulaPrimaryGraphEngine` 现在可直接注入协议对象，健康检查、实体查询、路径查询和证候链 fallback 均通过 adapter 边界，不再混用 `fallback_engine` 公共方法与私有 helper。
- 权限误报治理继续推进：`test_graph_engine.py`、`test_nebulagraph_store.py` 已从系统 `tempfile.TemporaryDirectory()` 迁到项目内 `_tmp_test`，graph/evidence 矩阵不再依赖 Windows 系统 Temp 写入权限。
- P5 状态迁移继续推进：`state_transitions.py` 增加 `mark_total_triples()`、`mark_chunk_retries()`、`mark_provider_metrics()`、`mark_publish_status()`；`extraction_job_runner.py`、`extraction_completion.py`、`extraction_finalizers.py` 中跨线程可见的运行指标、重试次数、发布状态和完成书籍数写入继续收敛到状态迁移边界。
- 权限误报治理完成一轮收尾：`test_alias_service.py`、`test_chat_api.py`、`test_chroma_case_store.py`、`test_modern_dataset_importers.py`、`test_release_gate.py`、`test_security_hardening.py` 已迁到项目内 `_tmp_test`，并补齐清理；当前 `backend/tests` 不再包含 `tempfile.TemporaryDirectory()`、`tempfile.mkdtemp()`、`NamedTemporaryFile` 或 pytest `tmp_path` 形参。
- P3 support 收尾继续推进：新增 `backend/services/retrieval_service/files_first_lifecycle.py`，将 files-first 构建进度格式化、stage banner、Windows 文件 unlink/replace retry 从 `files_first_support.py` 抽离；`LocalFilesFirstStore` 只保留 rebuild context 兼容转发。
- 测试矩阵同步重构：`test_tcm_route_execution.py` 负责执行/降级语义，`test_tcm_router_smoke.py` 降级为 router/strategy 和 `TCMRouteSearchTool` 兼容入口合同测试；新增 `test_retrieval_query_service.py` 覆盖 `RetrievalQueryService` 在线查询边界。
- Graph 兼容补强：`services.graph_service.engine` 恢复 `_ordered_path_neighbors` 兼容导出，避免旧测试和实验脚本导入失效。

本轮验证结果：

- `55 passed`：`test_no_mock_fallback.py`、`test_tcm_service_client.py`、`test_tcm_router_smoke.py`、`test_tcm_evidence_tools.py`、`test_evidence_path_resolver.py`、`test_tcm_route_planning.py`、`test_tcm_route_execution.py`
- `26 passed`：`test_tcm_router_smoke.py`、`test_tcm_route_execution.py`、`test_retrieval_query_service.py`
- `26 passed`：`test_retrieval_engine.py`、`test_files_first_support.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制失败，sandbox 外用项目解释器同命令重跑通过
- `31 passed`：`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_files_first_support.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制失败，sandbox 外用项目解释器同命令重跑通过
- `33 passed`：`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_files_first_support.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制失败，sandbox 外用项目解释器同命令重跑通过
- `38 passed`：`test_files_first_metadata.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 临时目录重跑通过
- `40 passed`：`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 临时目录重跑通过
- `42 passed`：`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 临时目录重跑通过
- `45 passed`：`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内受 Windows Temp/SQLite 临时目录权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 临时目录重跑通过
- `11 passed`：`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_build_state.py`、`test_pipeline_state_transitions.py`，覆盖 nav-group SQL/write 抽离、reader 协议化、search seed SQL 抽离、build-state 兼容和 cancel 状态迁移。
- `51 passed`：`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内和项目内 `_tmp_pytest` 均受 Windows 临时目录/SQLite 权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 重跑通过。
- `3 passed`：`test_pipeline_state_transitions.py`、`test_pipeline_server.py::PipelineServerTests::test_cancel_job_marks_current_state_as_cancelling`，sandbox 内受 Windows 临时目录权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 重跑通过。
- `14 passed`：`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`、`test_pipeline_state_transitions.py`，sandbox 内通过，覆盖 FTS SQL 候选生成、ranking 后处理、旧 search 兼容入口和 pipeline 状态迁移纯函数。
- `56 passed`：`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内通过。
- `76 passed`：`test_pipeline_state_transitions.py`、`test_pipeline_server.py`、`test_tcm_triple_console.py`，sandbox 内通过。
- `14 passed`：`test_files_first_search_plan.py`、`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`，sandbox 内通过，覆盖 search planning、FTS candidates、ranking 和旧 search 入口。
- `61 passed`：`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_search_plan.py`、`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内通过。
- `77 passed`：`test_pipeline_state_transitions.py`、`test_pipeline_server.py`、`test_tcm_triple_console.py`，sandbox 内通过。
- `13 passed`：`test_files_first_rebuild.py`、`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_support.py`，sandbox 内通过，覆盖 rebuild orchestration 和旧 store 入口。
- `9 passed`：`test_files_first_search.py`、`test_files_first_rebuild.py`、`test_files_first_support.py`，sandbox 内通过，覆盖 search/rebuild adapter thin entry。
- `66 passed`：`test_files_first_search.py`、`test_files_first_rebuild.py`、`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_search_plan.py`、`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内通过。
- `58 passed`：`test_qa_service.py`、`test_deep_mode_regression.py`、`test_qa_api.py`、`test_qa_multiple_choice_format.py`、`test_qa_probe_suite.py`
- `59 passed`：`test_graph_engine.py`、`test_nebulagraph_store.py`、`test_evidence_payloads.py`、`test_ontology_boundary_tiers.py`，因 Windows 临时目录权限限制在 sandbox 外用 `backend/.venv/Scripts/python.exe` 重跑通过
- `60 passed`：`test_graph_fallback_adapter.py`、`test_graph_engine.py`、`test_nebulagraph_store.py`、`test_evidence_payloads.py`、`test_ontology_boundary_tiers.py`，sandbox 内受 Windows Temp 权限限制，sandbox 外用项目解释器同命令重跑通过
- `61 passed`：`test_graph_fallback_adapter.py`、`test_graph_engine.py`、`test_nebulagraph_store.py`、`test_evidence_payloads.py`、`test_ontology_boundary_tiers.py`，sandbox 内通过，覆盖协议化 fallback adapter、Nebula primary 协议注入、SQLite runtime graph、Nebula store、evidence payload 和 ontology governance。
- `71 passed`：`test_pipeline_server.py`、`test_tcm_triple_console.py`，sandbox 内受 Windows Temp 权限限制，sandbox 外用项目解释器和项目内 `_tmp_pytest` 临时目录重跑通过
- `80 passed`：`test_pipeline_state_transitions.py`、`test_pipeline_server.py`、`test_tcm_triple_console.py`，sandbox 内通过，覆盖 pipeline 状态迁移、server 兼容入口和 triple console start/resume/auto-batch/publish/cancel 行为。
- `16 passed`：`test_alias_service.py`、`test_chroma_case_store.py`、`test_chat_api.py`、`test_modern_dataset_importers.py`、`test_release_gate.py`、`test_security_hardening.py`，sandbox 内通过，覆盖项目内临时目录测试矩阵和系统 Temp 误报收尾。
- `68 passed`：`test_files_first_lifecycle.py`、`test_files_first_search.py`、`test_files_first_rebuild.py`、`test_files_first_build_state.py`、`test_files_first_build_rows.py`、`test_files_first_schema.py`、`test_files_first_metadata.py`、`test_files_first_nav_groups.py`、`test_files_first_reader.py`、`test_files_first_seed_queries.py`、`test_files_first_search_plan.py`、`test_files_first_fts_queries.py`、`test_files_first_ranking.py`、`test_files_first_support.py`、`test_vector_compatibility.py`、`test_retrieval_query_service.py`、`test_retrieval_engine.py`、`test_section_summary_cache.py`、`test_qa_structured_store.py`、`test_chroma_case_store.py`，sandbox 内通过，覆盖 lifecycle/rebuild/search/schema/nav/reader/planning/FTS/ranking/vector compatibility/structured case-QA。
- Ruff targeted check passed for all changed Python files.

仍保留的兼容层与后续工作：

- `TCMRouteSearchTool` 已拆出 planner/executor，但旧 helper 包装和服务调用 patch 点仍保留，方便旧测试、脚本和实验代码平滑迁移。
- `RetrievalEngine` 已引入在线查询子服务边界，vector compatibility 的 files-first fusion 也已从 `hybrid_runtime.py` 抽离；`files_first_support.py` 已先拆出纯 metadata/path 解析模块、schema/migration 边界、rebuild row 构造边界和 build-state 边界，后续若继续拆 retrieval，应优先拆 section readback、ranking helpers，而不是改变检索策略。
- `NebulaPrimaryGraphEngine` 已通过 `LocalGraphFallbackAdapter` 解除对 fallback 私有方法的直接依赖；更进一步的 `GraphQueryBackend` 协议化可作为后续类型/接口收敛，不应和查询算法优化混做。
- `pipeline_server.py` 已完成第一层 runtime state 容器化，但完整显式状态机尚未执行；start/resume/auto-batch/publish/cancel 的行为仍由旧入口兼容承载。

## 当前结论

本项目的主要技术债不是功能缺失，而是多个已演进成功的链路仍保留旧兼容边界，导致编排层偏厚、状态共享较多、测试与实验脚本直接依赖内部实现。下一阶段重构应优先保护证据层可靠性，而不是继续增加 planner 复杂度。

准确现状：

- 已经基本实现 `graph + files-first + structured indexes + skills + planner` 的非向量检索方法。
- `files-first`、HERB2 converted evidence、`book://`、`chapter://`、`entity://`、`alias://` 路径已经可用。
- runtime alias expansion 已经接入检索栈。
- structured non-vector QA index 已是 case-QA 默认主路径。
- dense/vector 路径仍存在于 legacy retrieval engine、case-QA vector fallback、Milvus/Chroma 兼容和论文对照实验中，尚未完全移除。
- sidecar 不可用时必须回退到本地真实引擎，不能回退 mock demo 数据。

## 技术债与强耦合点

1. QA 编排层仍有兼容性门面

`backend/services/qa_service/engine.py` 已经拆出 `quick_flow`、`deep_flow`、`runtime_support`、`planner_runtime`，但 `QAService` 仍保留大量私有方法转发以兼容旧测试和旧调用点。风险是后续开发容易继续把新逻辑挂回 `QAService`，重新变成上帝对象。

2. 路由、策略、工具执行耦合过紧

`backend/tools/tcm_route_tool.py` 同时负责意图分析、route decision、retrieval strategy、graph/retrieval/case-QA 执行、降级记录和返回 payload 拼装。它是当前 `final_route`、fallback 行为和 evidence path 的关键耦合点。任何改动都必须绑定 route smoke、evidence tools 和 QA 回归。

3. RetrievalEngine 混合了查询、索引、兼容和质量门

`backend/services/retrieval_service/engine.py` 同时暴露查询、case-QA、files-first 读段、索引构建、query rewrite、rerank、lexical sanity gate、dense compatibility。`backend/services/retrieval_service/hybrid_runtime.py` 中也同时包含 files-first 主链、sparse fallback、dense fallback、vector fusion 和结果收尾。风险是“修 fallback”时把 dense 重新变成唯一可用路径。

4. Files-first 支撑层过大

`backend/services/retrieval_service/files_first_support.py` 现在主要承担 `LocalFilesFirstStore` 兼容门面、schema health/migration callback 和少量 nav-group progress callback。章节 metadata/path 纯函数、schema/migration、rebuild orchestration、rebuild docs/FTS row 构造、rebuild state、nav group SQL/write、section readback、search orchestration、search seed query、search planning、FTS section/leaf query loop、ranking/final scoring helpers、生命周期/进度工具已抽出。后续若继续拆，应优先评估 health/migration 和 nav-group progress callback 是否仍有实际维护收益，而不是改变检索策略。

5. Graph engine 对 fallback engine 的私有方法依赖较多

`backend/services/graph_service/nebula_primary_engine.py` 已通过 `GraphFallbackBackend`/`LocalGraphFallbackAdapter` 收敛 fallback 入口；Nebula 主引擎不再直接调用 fallback engine 的公共查询方法或私有 helper，而是依赖协议边界。剩余风险主要是 `nebula_*_support.py` 仍通过 `engine.fallback` 参与 relation clustering、path payload 和 source-book hint 逻辑，后续若继续拆 graph，应优先把 Nebula query orchestration 与 payload/evidence enrichment 分层，而不是改变 fallback 行为。

6. Pipeline console 仍是单例状态模型

`backend/scripts/pipeline_server.py` 已拆出 `pipeline_console/*`，并新增 runtime state 容器集中持有 job/cancel/log/lock 状态；`state_transitions.py` 已覆盖启动、取消、提取、进度、重试、provider metrics、发布状态、done/cleaning/publishing/finished/error 等跨线程可见状态写入。但旧全局名和兼容包装函数仍保留，`extraction_job_runner.py` 仍通过 `ExtractionJobContext` 回调注入 `pipeline_server` 私有函数。风险集中在 resume、auto batch、publish queue、cancel 和 per-run isolation。

7. 脚本和实验代码直接 import 生产内部实现

`scripts/`、`paper_experiments/`、`eval/` 大量直接 import `services.*` 甚至私有函数。短期可接受，但需要把稳定服务 API 与实验工具 API 分层，否则生产重构会反复被实验脚本阻塞。

8. 运行产物与源码树混杂

仓库内存在 `.venv`、`.test_tmp`、`storage`、`workspace` 等运行或测试产物。它们已经影响递归扫描和静态分析。后续应将工具默认排除清单固化到 pytest、ruff、vulture 和自定义审计脚本中。

## 重构阶段计划

### P0：冻结行为与文档口径

目标：先防偏移，再重构。

- 固化当前 README 口径：非向量是主方向和主要默认路径，但 dense-compatible 尚未完全移除。
- 为 route payload 建立契约测试，覆盖 `route`、`final_route`、`executed_routes`、`degradation`、`service_backends`、`evidence_paths`。
- 给 fallback 行为加反向测试：sidecar down -> local real engine；local dense unavailable -> degrade to files_first or empty real result；禁止 mock。
- 把 `.venv`、`.test_tmp`、`storage`、`workspace` 从所有本地分析脚本中默认排除。

### P1：证据层可靠性优先

目标：graph hit 能稳定变成可读本地证据。

- 抽出 evidence path resolver：统一解析 `entity://`、`alias://`、`book://`、`chapter://`、`caseqa://`。
- 抽出 section reader：把 `files_first_store.read_section`、parent chunk 拼接、source scope filtering 分开。
- 明确 source scope 数据结构，减少 alias/source-scope drift。
- 增加 regression：graph entity 命中后必须生成可读 `entity://` 或 `chapter://` 证据；`final_route=hybrid` 时 graph 和 files-first 证据都应可追踪。

### P2：路由与工具执行解耦

目标：让路由决策纯化，执行与降级独立。

- 将 `TCMRouteSearchTool` 拆成 `RoutePlanner`、`RouteExecutor`、`RoutePayloadBuilder`。
- `derive_retrieval_strategy` 只产出 strategy，不触发 side effect。
- 降级策略统一为 `DegradationPolicy`，避免 graph/retrieval/hybrid 分支各写一套。
- 保持旧 `TCMRouteSearchTool` 作为兼容 adapter，直到测试全部迁移。

### P3：RetrievalEngine 分层

目标：避免 dense compatibility 污染 files-first 主链。

- 拆出 `FilesFirstSearchService`、`CaseQASearchService`、`VectorCompatibilityService`、`RetrievalIndexingService`。
- `search_hybrid(search_mode="files_first")` 内部先走 files-first service，只有显式策略允许时才进入 vector compatibility。
- 把 `vector_compatibility_enabled`、`files_first_dense_fallback_enabled`、`case_qa_vector_fallback_enabled` 的行为写成表驱动测试。
- 索引构建与在线查询分离，避免运行时服务加载不必要的 embedding/indexing 依赖。
- 继续拆 `files_first_support.py` 时只在有明确调用方收益时处理 health/migration 与 nav-group progress callback；保持 `files_first_lifecycle.py` 作为文件生命周期/构建进度边界，保持 `files_first_rebuild.py` 作为 rebuild orchestration 边界，保持 `files_first_search.py` 作为 search orchestration 边界，保持 `files_first_metadata.py` 作为古籍路径和章节 metadata 的稳定边界，保持 `files_first_schema.py` 作为 schema/migration 的稳定边界，保持 `files_first_build_rows.py` 作为 rebuild docs/FTS row 的稳定边界，保持 `files_first_build_state.py` 作为 rebuild state 的稳定边界，保持 `files_first_nav_groups.py` 作为 nav-group SQL/write 边界，保持 `files_first_reader.py` 作为 section readback 边界，保持 `files_first_seed_queries.py` 作为 search seed query 边界，保持 `files_first_search_plan.py` 作为 search planning 边界，保持 `files_first_fts_queries.py` 作为 FTS candidate query 边界，保持 `files_first_ranking.py` 作为 ranking/final scoring 边界。

### P4：Graph primary/fallback 接口稳定化

目标：Nebula 与 SQLite fallback 共享公开协议，而不是互调私有方法。

- 已定义 `GraphFallbackBackend` 协议：覆盖 fallback 公共查询方法、entity resolution、relation clustering、path payload、edge evidence、source-book hint 和 query text helper。
- 保持 `LocalGraphFallbackAdapter` 作为 SQLite runtime graph 的兼容门面；旧 `fallback_engine=` 构造方式仍可用，新代码可直接注入协议对象。
- path_query 保持 Nebula-first 可选，本地 runtime graph 必须一直可用。
- 把 relation cluster 聚合下推到 SQLite 查询层作为专项性能优化，不和协议重构混做。

### P5：Pipeline console 状态机化

目标：保留当前行为，降低单例线程状态风险。

- 把 `_current_job`、日志、cancel event、publish queue 收敛为 `PipelineConsoleRuntime`；当前已完成 job/log/cancel/lock 的第一层容器化，publish queue 已有 `PublishQueueRuntime`，后续需要统一两者的生命周期边界。
- 将 start/resume/auto-batch/publish 的状态迁移写成显式状态机；当前 start/cancel/extracting/resume/book-progress/current-task/retry/provider/publish/done/error 等状态写入已抽到 `state_transitions.py`，后续继续收敛时应优先处理 runner context 依赖注入和 publish runtime 生命周期，而不是重写调度算法。
- 每批自动任务继续独立 run directory，严禁 append 到上一批 run。
- 对 resume 行为保留当前语义：先续指定 run，再默认接后续自动批次。

## 测试矩阵

### 每次小重构必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_no_mock_fallback.py tests/test_tcm_service_client.py tests/test_tcm_router_smoke.py tests/test_tcm_route_execution.py tests/test_tcm_evidence_tools.py tests/test_evidence_path_resolver.py -q
```

覆盖：无 mock fallback、sidecar/local backend、route adapter 合同、route execution/final_route/degradation、evidence path、alias/source scope。

### Route planner/executor 改动必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_tcm_router_smoke.py tests/test_tcm_route_planning.py tests/test_tcm_route_execution.py -q
```

覆盖：router/strategy 纯计划、执行层服务依赖注入、graph/retrieval/case-QA 降级、`TCMRouteSearchTool` 旧入口兼容。

### QA 与 deep mode 改动必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_qa_service.py tests/test_deep_mode_regression.py tests/test_qa_api.py tests/test_qa_multiple_choice_format.py tests/test_qa_probe_suite.py -q
```

覆盖：quick/deep 输出、planner fallback、grounded answer、API 契约、格式约束。

### Retrieval/files-first 改动必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_files_first_search.py tests/test_files_first_rebuild.py tests/test_files_first_build_state.py tests/test_files_first_build_rows.py tests/test_files_first_schema.py tests/test_files_first_metadata.py tests/test_vector_compatibility.py tests/test_retrieval_query_service.py tests/test_retrieval_engine.py tests/test_files_first_support.py tests/test_section_summary_cache.py tests/test_qa_structured_store.py tests/test_chroma_case_store.py -q
```

覆盖：`RetrievalQueryService` 在线查询边界、vector compatibility fusion、`RetrievalEngine` 兼容入口、files-first build state/build rows/schema/migration/search/readback、section summary cache、structured case-QA、legacy vector fallback 边界。

Files-first support/search 拆分时追加：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_files_first_nav_groups.py tests/test_files_first_reader.py tests/test_files_first_seed_queries.py tests/test_files_first_build_state.py tests/test_pipeline_state_transitions.py -q -p no:cacheprovider
```

覆盖：nav-group seed/write SQL、reader 协议化与公开 metadata 解析边界、direct/clause seed query、项目内临时目录/SQLite row factory 工具、pipeline cancel 状态迁移。

Files-first FTS/ranking 高风险拆分时追加：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_files_first_search_plan.py tests/test_files_first_fts_queries.py tests/test_files_first_ranking.py tests/test_files_first_support.py tests/test_retrieval_engine.py tests/test_qa_structured_store.py -q -p no:cacheprovider
```

覆盖：query planning、seed target book 选择、FTS SQL 候选生成、invalid MATCH error 语义、synthetic section 合成、同 section 去重优先级、book narrowing、coverage tie-break、`LocalFilesFirstStore.search()` 旧入口和 structured case-QA 主路径。

Files-first metadata/path 纯函数拆分时追加：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_files_first_build_state.py tests/test_files_first_build_rows.py tests/test_files_first_schema.py tests/test_files_first_metadata.py tests/test_files_first_support.py -q
```

覆盖：rebuild state/resume/checkpoint/result payload、docs/FTS row 构造和插入、schema status、legacy schema migration、古籍 header 解析、`classic://` 章节 key、章节正文合并、summary/topic/entity metadata、`files_first_support.py` 旧函数名兼容导出。

### Graph/evidence 改动必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_graph_fallback_adapter.py tests/test_graph_engine.py tests/test_nebulagraph_store.py tests/test_evidence_payloads.py tests/test_ontology_boundary_tiers.py -q
```

覆盖：SQLite runtime graph、Nebula primary/fallback adapter、evidence payload normalization、ontology governance。

### Triple pipeline 改动必跑

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_server.py tests/test_tcm_triple_console.py -q
```

覆盖：start/resume/auto-batch、per-run isolation、retry workers、publish queue、pipeline console compatibility。

Pipeline 状态迁移拆分时追加：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_state_transitions.py tests/test_pipeline_server.py tests/test_tcm_triple_console.py -q -p no:cacheprovider
```

覆盖：cancel/done/partial/error/cleaning/publishing/finished 状态形状、pipeline server 兼容入口、triple console pipeline 行为。

### 发布前质量门

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check .
```

前端涉及 UI/API 类型时追加：

```powershell
cd frontend
npm run build
```

如 `uv` 或 pytest 在 sandbox 内因 Windows cache/temp 权限失败，先尝试项目本地 cache；仍失败时用 `backend/.venv/Scripts/python.exe -m pytest ...` 在 sandbox 外重跑，并记录原因是 Windows cache/temp 权限限制，不是代码失败。

## 重构验收标准

- 默认 case-QA 仍走 structured non-vector index。
- 默认 files-first 查询在 dense embedding 不可用时仍能返回真实降级结果或明确空结果，不静默切到 mock。
- `final_route`、`executed_routes`、`degradation` 可解释且前后端字段不漂移。
- `entity://`、`book://`、`chapter://`、`alias://` 读回可定位到本地可读证据。
- deep mode 回退率不升高，`planner_deterministic_fallback` 不应成为常态。
- pipeline 自动批次仍每批独立 run directory，resume 语义不变。
- 文档不得声称“完全去向量化”或“dense 已移除”。
