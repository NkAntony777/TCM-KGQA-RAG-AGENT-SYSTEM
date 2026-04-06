---
name: find-case-reference
description: 当用户问题需要病例参考、类似医案、临床案例、主诉现病史体征对照时使用。优先查询 caseqa:// 或 search_evidence_text，返回相似案例摘要，不把病例参考当成事实主结论。
---

# Find Case Reference

## Trigger Phrases
- 病例
- 医案
- 主诉
- 现病史
- 舌脉
- 类似案例

## Preferred Tools
- `read_evidence_path`
- `search_evidence_text`

## Preferred Paths
- `caseqa://<实体>/similar`
- `caseqa://query/similar`

## Workflow
1. 仅在问题明确需要病例、医案、主诉现病史、舌脉、临床参考时触发。
2. 优先读取 `caseqa://` 路径；没有时用 `search_evidence_text` 并限制在病例范围。
3. 返回时保留病例标题/文档、核心主诉、辨证摘要、处理结果或参考意义。
4. 病例证据只作为补充参考，不能替代方剂/出处/功效的事实证据。

## Output Focus
- 病例标题
- 主诉摘要
- 辨证摘要
- 参考意义

## Stop Rule
- 拿到 1 到 3 条相似案例摘要后停止。
- 如果相似度不高，显式说明“为相似案例，不是直接同案”。
