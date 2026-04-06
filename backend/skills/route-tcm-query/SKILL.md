---
name: route-tcm-query
description: 中医问答入口技能。用户问题涉及方剂、证候、功效、组成、出处、比较、古籍、教材、病例参考时使用。先识别意图、实体、比较对象和是否需要出处，再优先调用 tcm_route_search，不要跳过首轮路由。
---

# Route TCM Query

## Preferred Tools
- `tcm_route_search`
- `list_evidence_paths`

## Workflow
1. 先识别问题类型：组成、功效、主治、出处、比较、证候到方剂、病例参考。
2. 提取核心实体、比较对象、症状/证候词、出处信号词。
3. 第一动作固定为 `tcm_route_search(query, top_k)`。
4. 读取返回的 `route`、`retrieval_strategy`、`evidence_paths`、`final_route`。
5. 如果问题是单跳且证据已足够，直接交给 grounded answer。
6. 如果问题是多跳或证据不全，再转给更细的 skill。

## Output Focus
- `intent`
- `entity_name`
- `compare_entities`
- `evidence_paths`
- `final_route`

## Stop Rule
- 已得到稳定路由和可用 evidence_paths 后停止。
- 不直接承担多轮补检索。
