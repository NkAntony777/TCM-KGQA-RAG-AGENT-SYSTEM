# LikelyDirty 首批治理清单（2026-04-13）

适用子项目：`langchain-miniopenclaw/backend`

来源：

- `backend/eval/ontology_likely_dirty_shortlist_latest.json`
- `backend/eval/ontology_likely_dirty_shortlist_latest.md`

## 1. 目标

在 ontology 异常已经完成三层分流后，下一步真正适合进入小批治理的对象是：

- `likely_dirty`

这一层当前总量为：

- `8936`

这已经足够小，可以进入“高频组合优先、小步快跑”的治理节奏，而不必再对整个异常池做大范围动作。

## 2. 全局优先级最高的组合

当前最值得优先处理的前 12 个组合为：

| predicate | subject_type | object_type | count |
| --- | --- | --- | ---: |
| 使用药材 | herb | herb | 2748 |
| 使用药材 | category | herb | 1063 |
| 使用药材 | other | herb | 946 |
| 使用药材 | channel | herb | 699 |
| 归经 | channel | channel | 446 |
| 使用药材 | herb | formula | 432 |
| 治疗症状 | book | symptom | 191 |
| 归经 | channel | herb | 167 |
| 治疗症状 | chapter | symptom | 164 |
| 治疗证候 | other | syndrome | 155 |
| 归经 | channel | other | 149 |
| 治疗症状 | category | symptom | 149 |

## 3. 建议的首批治理范围

### 第一批建议直接打的组合

这几类最像结构污染，且误伤风险相对低：

1. `归经: channel -> channel`
2. `使用药材: herb -> herb`
3. `使用药材: category -> herb`
4. `治疗症状: book -> symptom`
5. `治疗症状: chapter -> symptom`

理由：

- 结构上最不符合当前图谱主链语义
- 高频明显
- 样本看起来更接近抽取层误配，而不是可接受多义

### 第二批建议先抽样复核的组合

这几类虽然也在 `likely_dirty`，但更适合先抽样确认：

1. `使用药材: other -> herb`
2. `治疗证候: other -> syndrome`
3. `使用药材: herb -> formula`
4. `归经: channel -> herb`

原因是：

- `other` 类型本身混杂，需要先看是否是未标准化实体
- `herb -> formula` 可能掺杂少量真正的引用/配伍上下文

## 4. 按谓词拆解的观察

### 4.1 使用药材

- `likely_dirty = 5888`
- 最主要污染组合：
  - `herb -> herb`
  - `category -> herb`
  - `other -> herb`
  - `channel -> herb`
  - `herb -> formula`

建议：

- 第一优先级：`herb -> herb`、`category -> herb`
- 第二优先级：`other -> herb`、`channel -> herb`

### 4.2 归经

- `likely_dirty = 883`
- 最主要污染组合：
  - `channel -> channel`
  - `channel -> herb`
  - `channel -> other`
  - `channel -> property`

建议：

- 第一优先级：`channel -> channel`
- 第二优先级：其余 `channel -> *`

### 4.3 治疗症状

- `likely_dirty = 1187`
- 最主要污染组合：
  - `book -> symptom`
  - `chapter -> symptom`
  - `category -> symptom`
  - `symptom -> disease`
  - `symptom -> channel`

建议：

- 第一优先级：`book -> symptom`、`chapter -> symptom`
- 第二优先级：`category -> symptom`

## 5. 当前不建议做的事

1. 不建议直接清全部 `likely_dirty`
2. 不建议同时动 `review_needed`
3. 不建议回头去碰 `acceptable_polysemy`

## 6. 下一步最合理的执行方式

建议下一轮直接做一个“小批 patch 生成器”，仅针对首批低风险组合：

- `归经: channel -> channel`
- `使用药材: herb -> herb`
- `使用药材: category -> herb`
- `治疗症状: book -> symptom`
- `治疗症状: chapter -> symptom`

执行方式建议：

- 先导出受影响样本
- 再做人工快速复核
- 通过后再做增量 patch / 局部修复

当前状态补充：

- 精确导出脚本已完成：
  - `backend/scripts/export_ontology_likely_dirty_batch1_candidates.py`
- 已生成：
  - `backend/eval/ontology_likely_dirty_batch1_candidates_latest.json`
  - `backend/eval/ontology_likely_dirty_batch1_candidates_latest.md`

也就是说，“先导出受影响样本”这一步已经完成。

## 7. batch1 实际执行结果

当前已经实际落库的首批组合为：

- `归经: channel -> channel`
- `治疗症状: book -> symptom`
- `治疗症状: chapter -> symptom`

执行脚本：

- `backend/scripts/apply_batch1_likely_dirty_graph_governance.py`

执行结果：

- `归经: channel -> channel` 删除 `446`
- `治疗症状: book -> symptom` 删除 `191`
- `治疗症状: chapter -> symptom` 删除 `164`
- 合计删除 `801` 条图关系
- 对应删除 `817` 个 fact_id
- `shared_fact_ids_count = 0`

## 8. batch1 执行后效果

重新审计后：

- `likely_dirty_rows` 从 `8936` 降到 `8135`
- 净下降 `801`

这说明：

- 本轮 patch 与 shortlist 命中一致
- 没有出现“看起来删了很多，但 dirty 统计不动”的假治理

## 9. 下一批建议

下一轮最值得继续打的对象变成：

1. `使用药材: herb -> herb`
2. `治疗证候: other -> syndrome`
3. `治疗症状: category -> symptom`

补充说明：

- `使用药材: category -> herb` 已在 batch2a 中完成改挂到 `属于范畴`
- `使用药材: herb -> herb` 经过 LLM 跨书判定后仍不稳定，当前不能整批 apply
- 下一步最合理的是继续把 `herb -> herb` 再细分为：
  - 炮制/制法原料
  - 组成列举
  - 真正需要改挂到其他关系的配伍类

## 10. batch2a 执行结果

当前已完成：

- `使用药材: category -> herb -> 属于范畴`

执行脚本：

- `backend/scripts/apply_batch2a_category_to_herb_retype.py`

实际重写：

- `1063` 条关系

执行后审计：

- `likely_dirty_rows: 8135 -> 7072`

## 7. 一句话结论

现在已经到了可以真正开始做“小批 likely_dirty 治理”的阶段，而且第一批该打哪几类，已经很清楚了。
