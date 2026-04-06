---
name: compare-formulas
description: 当用户比较两个或多个方剂、证候方案、功效差异、适用边界时使用。分别读取各实体证据，再补充出处或教材对照信息，不要只用单一实体证据回答比较题。
---

# Compare Formulas

## Trigger Phrases
- 区别
- 比较
- 不同
- 共同点
- 适用边界
- 为什么一个更适合

## Preferred Tools
- `read_evidence_path`
- `search_evidence_text`

## Preferred Paths
- `entity://<方剂A>/*`
- `entity://<方剂B>/*`
- `book://<书名>/*`

## Workflow
1. 明确比较对象，至少分别取两个对象的证据。
2. 优先读取每个对象的 `entity://<实体>/*`、功效、主治、组成相关路径。
3. 比较维度至少覆盖共同点、差异点、适用证候/病机边界。
4. 如果用户要求依据，再补一次 `book://` 或 `qa://` 文本证据。
5. 不要把“都能治疗某证”当成比较完成；必须指出为什么不同。

## Output Focus
- 共同点
- 差异点
- 适用边界
- 对应出处

## Stop Rule
- 每个比较对象至少各有一条核心证据后停止。
- 如果某一方证据明显不足，明确标注该比较结论依据有限。

## Examples
- 四君子汤和六君子汤有什么区别
- 逍遥散与柴胡疏肝散适用边界有何不同
