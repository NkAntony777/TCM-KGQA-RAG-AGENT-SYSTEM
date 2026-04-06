---
name: search-source-text
description: 当现有书目路径不足、需要补古籍原文、教材出处、定义解释或文献佐证时使用。优先在已有 `book://`、`qa://` 范围内搜索，不要脱离当前证据上下文盲搜。
---

# Search Source Text

## Trigger Phrases
- 出处
- 原文
- 原句
- 哪本书
- 教材
- 文献记载

## Preferred Tools
- `search_evidence_text`

## Preferred Paths
- `book://<书名>/*`
- `qa://<实体>/similar`

## Workflow
1. 先检查当前是否已有 `book://` 或 `qa://` 路径。
2. 搜索词附加“出处 原文 古籍 教材 佐证”等限定词。
3. 优先返回直接命中书名、篇章、原文片段的文本证据。
4. 若文本与实体不一致，宁可放弃，也不要返回错书错方的片段。

## Output Focus
- 书名
- 篇章或页码
- 原文片段
- 与当前问题的对应关系

## Stop Rule
- 已拿到 1 到 2 条可引用文本片段后停止。
- 若结果与核心实体不一致，停止并标记证据不足。
