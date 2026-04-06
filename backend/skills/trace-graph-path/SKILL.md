---
name: trace-graph-path
description: 当用户问辨证链、路径、为什么从症状推到证候或从证候参考某方时使用。优先读取 `symptom://` 或实体级路径证据，输出链路节点与关系，而不是只给结论。
---

# Trace Graph Path

## Trigger Phrases
- 路径
- 链路
- 辨证链
- 为什么
- 为何会参考
- 怎么辨到

## Preferred Tools
- `read_evidence_path`

## Preferred Paths
- `symptom://<症状>/syndrome_chain`
- `entity://<实体>/推荐方剂`

## Workflow
1. 优先找症状到证候、证候到方剂的结构化路径。
2. 若已有 graph path 证据，提炼节点、边和最终结论。
3. 若用户要求出处，再交给 `trace-source-passage` 补原文支撑。

## Output Focus
- 路径节点
- 路径关系
- 为什么得出该结论
- 链路对应出处

## Stop Rule
- 已有至少一条完整链路后停止。
- 若只有结论没有链路，继续补一次图谱路径证据。
