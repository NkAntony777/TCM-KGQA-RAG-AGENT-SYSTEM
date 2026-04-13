# LikelyDirty Batch1 执行报告（2026-04-13）

适用子项目：`langchain-miniopenclaw/backend`

## 1. 本轮目标

在完成 ontology 分层审计和 batch1 候选导出后，本轮正式执行首批 low-risk `likely_dirty` 清理。

执行原则：

- 只打最脏的三类
- 先删除明显错误关系
- 不碰 `acceptable_polysemy`
- 不碰 `review_needed`

## 2. 实际执行对象

执行脚本：

- `backend/scripts/apply_batch1_likely_dirty_graph_governance.py`

实际落库的三类组合：

1. `归经: channel -> channel`
2. `治疗症状: book -> symptom`
3. `治疗症状: chapter -> symptom`

## 3. dry-run 结果

dry-run 已确认：

- `DELETE:归经[channel->channel] = 446`
- `DELETE:治疗症状[book->symptom] = 191`
- `DELETE:治疗症状[chapter->symptom] = 164`
- 合计图关系：`801`
- 对应 `fact_id`：`817`
- `shared_fact_ids_count = 0`

这说明：

- 本轮没有 evidence 共享冲突
- 可以安全执行 apply

## 4. apply 结果

执行完成后，已生成 manifest：

- `backend/services/graph_service/data/graph_runtime.governance_batch1_likely_dirty.20260413_195752.json`

实际效果与 dry-run 一致：

- 删除图关系：`801`
- 删除 `fact_id`：`817`

## 5. 执行后验证

### 5.1 graph 回归

- `uv run pytest tests/test_graph_engine.py -q`
  - `35 passed`

### 5.2 ontology 审计

重跑：

- `backend/scripts/audit_ontology_boundary_tiers.py`

结果：

- `likely_dirty_rows: 8936 -> 8135`
- 净下降：`801`

这说明：

- 统计口径与实际删除关系数完全对齐
- 本轮治理是有效治理，不是“名义改动”

## 6. 本轮为何选这三类

### 6.1 归经: channel -> channel

这类样本本质是：

- 经脉到经脉
- 穴位到经脉
- 经脉到穴位

它们不是药物归经语义，继续挂在 `归经` 主边上只会污染 graph 主链。

### 6.2 治疗症状: book -> symptom

这类样本本质是：

- 某书提到某症状
- 某书论及某证状

不是“书治疗症状”。

### 6.3 治疗症状: chapter -> symptom

这类样本本质是：

- 某篇章描述症状
- 某章节列举症状

不是“篇章治疗症状”。

## 7. 当前阶段判断

到这一步，第三批治理已经进入新的阶段：

- 不是只有规则和审计
- 而是已经完成了首批真实 dirty 清理

这说明当前治理链条已经闭环：

1. 分层审计
2. shortlist
3. exact candidate export
4. dry-run
5. apply
6. regression
7. 审计回看

## 8. 下一步建议

下一轮优先对象：

1. `使用药材: herb -> herb`
2. `使用药材: category -> herb`
3. `治疗证候: other -> syndrome`
4. `治疗症状: category -> symptom`

其中前两项需要更谨慎：

- `herb -> herb` 有些可能是配伍/列举，应优先考虑“改边”而不是直接删
- `category -> herb` 具有分类知识价值，原则上更适合改挂到分类型关系

## 9. 一句话结论

`likely_dirty` 的首批 low-risk patch 已经成功落库，且验证结果干净，第三批治理现在可以继续进入第二批 dirty 组合处理。 
