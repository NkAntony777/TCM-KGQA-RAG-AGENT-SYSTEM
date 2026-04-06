---
name: external-source-verification
description: 只有在用户明确要求联网、核验外部事实、查询最新官方信息，或本地知识库没有覆盖该问题时使用。优先核验官方来源或一手来源，不要默认替代本地中医知识链路。
---

# External Source Verification

## Preferred Tools
- `web_search`
- `fetch_url`

## Workflow
1. 只有在用户明确说“搜索”“联网”“查官网”“给链接”“核验”，或问题明显依赖最新信息时触发。
2. 外部核验默认是补充，不应取代本地 `tcm_route_search` 主链路。
3. 优先找官方、机构、一手来源；避免 SEO 聚合页。
4. 对时间敏感信息，答案里必须带时间说明。

## Output Focus
- 官方来源
- 一手链接
- 时间说明

## Stop Rule
- 已拿到可核验的一手来源后停止。
- 如果本地已有稳定证据且用户未要求联网，不触发本 skill。
