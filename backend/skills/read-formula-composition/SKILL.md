---
name: read-formula-composition
description: 当用户问方剂组成、药材、配伍、君臣佐使、加减基础时使用。优先从 entity://<方剂>/使用药材 读取证据，必要时回退到 tcm_route_search 或 list_evidence_paths，不要直接给结论而不取证。
---

# Read Formula Composition

## Preferred Tools
- `read_evidence_path`
- `list_evidence_paths`
- `tcm_route_search`

## Workflow
1. 确认已知核心方剂名；若未知，先回到 `route-tcm-query` 获取实体。
2. 优先读取 `entity://<方剂>/使用药材`。
3. 如果未命中，先调用 `list_evidence_paths`，再找同实体的组成相关路径。
4. 仍未命中时，重新做一次 `tcm_route_search`，不要直接猜组成。
5. 返回时优先保留药材名、配伍信息、来源书名/篇章。

## Output Focus
- 药材名
- 配伍信息
- 来源书名
- 来源篇章

## Stop Rule
- 已拿到主要药材和至少一条来源后停止。
- 若只有部分药材，明确说明“当前证据仅覆盖部分组成”。
