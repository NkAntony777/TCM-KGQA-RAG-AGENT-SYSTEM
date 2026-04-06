---
name: read-syndrome-treatment
description: 当用户问功效、治法、主治、治疗证候、适用边界时使用。优先读取实体下的功效、治法、治疗证候等结构化路径，避免把比较题和出处题混在一起。
---

# Read Syndrome Treatment

## Trigger Phrases
- 功效
- 治法
- 主治
- 适用于
- 治疗什么证候
- 适用边界

## Preferred Tools
- `read_evidence_path`

## Preferred Paths
- `entity://<实体>/功效`
- `entity://<实体>/治法`
- `entity://<实体>/治疗证候`

## Workflow
1. 根据问题优先级选择功效、治法、主治相关路径。
2. 先读取结构化图谱证据，必要时再交给出处类 skill 补文献。
3. 对“适用边界”类问题，优先提炼病机、证候、治法差异。

## Output Focus
- 功效
- 治法
- 主治证候
- 适用边界

## Stop Rule
- 已拿到 1 到 3 条核心结构化证据后停止。
- 若问题要求出处，交给出处类 skill 继续补证据。
