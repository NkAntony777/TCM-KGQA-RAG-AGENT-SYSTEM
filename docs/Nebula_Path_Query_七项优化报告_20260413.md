# Nebula Path Query 七项优化报告

更新时间：2026-04-13

## 背景

在上一轮对比中，已经确认 `path_query` 不只是 heavy path，连 light path 也普遍是 `NebulaGraph` 更快、更稳。因此本轮目标不是“是否切 Nebula”，而是继续把 Nebula 侧工程接入做深，进一步缩短真实路径查询耗时。

## 本轮落地的 7 项优化

### 1. 连接池复用

- 文件：
  - `backend/services/graph_service/nebulagraph_store.py`
- 变更：
  - 从“每次查询新建 `ConnectionPool` 再关闭”改为类级共享连接池。
- 收益：
  - 消除高频建池/销毁开销。
  - 对 light path 和频繁 smoke / regression 提升尤其明显。

### 2. 批量起终点 shortest-path

- 文件：
  - `backend/services/graph_service/nebulagraph_store.py`
  - `backend/services/graph_service/engine.py`
- 变更：
  - `find_shortest_path_rows(...)` 支持 `start_entity_name / end_entity_name` 传入列表。
  - `NebulaPrimaryGraphEngine._direct_path_query_via_nebula(...)` 从逐对 `3 x 3` 串行查询改为单次批量 shortest-path。
- 收益：
  - 减少候选点组合导致的多次 round-trip。

### 3. shortest-path 热路径去掉 `WITH PROP`

- 文件：
  - `backend/services/graph_service/nebulagraph_store.py`
  - `backend/services/graph_service/engine.py`
- 变更：
  - shortest-path 默认改为轻量 skeleton 查询，不再直接让 Nebula 在热路径返回完整属性。
- 收益：
  - 减少 path 返回 payload。
  - 降低 graphd 侧单次路径查询负担。

### 4. 批量二阶段补证据

- 文件：
  - `backend/services/graph_service/nebulagraph_store.py`
  - `backend/services/graph_service/engine.py`
- 变更：
  - 新增批量顶点补全：
    - `fetch_vertices_by_vids(...)`
  - 新增批量边属性补全：
    - `fetch_edges_by_refs(...)`
  - 路径结果改为：
    - 先解码 path skeleton
    - 再批量回填点名、边谓词、来源、fact_id、source_text
- 收益：
  - 不再对每一跳逐边走 SQLite `first_edge_between(...)`
  - 真正把 `path executor` 收口到 Nebula 主侧

### 5. Nebula path PROFILE 工具

- 文件：
  - `backend/scripts/profile_nebula_path_queries.py`
  - `docs/Nebula_Path_Profile_20260413.md`
- 变更：
  - 新增可复用诊断脚本，固定输出代表性 path case 的：
    - `whole_latency_us`
    - `row_size`
    - `operator_count`
    - `top_operator`
- 收益：
  - 后续调 `graphd` 配置或查询形状时有可复用诊断基线。

### 6. graphd 线程参数接入 compose

- 文件：
  - `backend/services/graph_service/docker-compose.nebula.yml`
- 变更：
  - 增加：
    - `--num_operator_threads=${NEBULA_NUM_OPERATOR_THREADS:-8}`
- 收益：
  - 让路径查询算子线程数可配置，不需要后续再手工改 compose。

### 7. 更细的 auto 路由启发式

- 文件：
  - `backend/services/graph_service/engine.py`
  - `backend/tests/test_graph_engine.py`
- 变更：
  - `PATH_QUERY_EXECUTION_MODE` 仍支持：
    - `local_first`
    - `nebula_first`
    - `auto`
  - 新增 auto 路由阈值：
    - `NEBULA_PATH_QUERY_AUTO_MIN_HOPS`
    - `NEBULA_PATH_QUERY_AUTO_MIN_CANDIDATE_PAIRS`
- 收益：
  - 未来即使需要从 `nebula_first` 回到更保守模式，也已有较清晰的自动切流启发式。

## 最新 benchmark 结果

来源：

- `backend/eval/path_query_backend_benchmark_latest.json`
- `docs/Path_Query_Backend_Benchmark_20260413.md`

### light path

- `熟地黄 -> 六味地黄汤`
  - SQLite: `45s timeout`
  - Nebula: `98.03ms`
- `附子 -> 少阴病`
  - SQLite: `17.29s`
  - Nebula: `269.47ms`
- `人参 -> 脾胃气虚`
  - SQLite: `45s timeout`
  - Nebula: `607.91ms`
- `四君子汤 -> 六味地黄丸`
  - SQLite: `45s timeout`
  - Nebula: `82.95ms`

### heavy path

- `熟地黄 -> 真阴亏损`
  - SQLite: `29.30s`
  - Nebula: `95.52ms`
- `黄芪 -> 虚风内动`
  - SQLite: `90s timeout`
  - Nebula: `11.05s`
- `桂枝 -> 虚风内动`
  - SQLite: `90s timeout`
  - Nebula: `8.13s`
- `附子 -> 虚风内动`
  - SQLite: `90s timeout`
  - Nebula: `13.12s`

## 当前结论

- 经过这轮收口后，`path_query` 已经不是“仅 heavy path 值得 Nebula”。
- 当前真实结果说明：
  - light path 已明显适合 Nebula
  - 2 hop 与 3 hop path 的收益非常大
  - SQLite 本地路径搜索在真实运行态下仍有大面积 timeout 面

## 当前建议

### 默认运行策略

- 保持：
  - `PATH_QUERY_EXECUTION_MODE=nebula_first`
- 保留：
  - 本地 SQLite fallback

### 后续仍可继续优化的点

- 对 heavy case 继续做 source-aware path rerank，减少多个等长路径的噪声路径前排。
- 若后续继续压缩耗时，可再评估：
  - path 查询的 `path_limit` 分 lane 动态调小
  - 对 3 hop 以上路径增加 predicate 级 beam pruning
  - graphd 线程数与 CPU 资源的进一步匹配调优
