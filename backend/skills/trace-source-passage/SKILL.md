---
name: trace-source-passage
description: 当答案已经有初步结论，但还缺可引用的书名、篇章、原文片段时使用。优先从 graph/doc/book 证据中抽取最适合展示给用户的出处片段。
---

# Trace Source Passage

## Preferred Tools
- `read_evidence_path`
- `search_evidence_text`

## Workflow
1. 在已有事实证据基础上工作，不单独承担首轮检索。
2. 优先挑选同时满足以下条件的证据：有 `source_book`，有 `source_chapter` 或页码，片段直接支持当前结论。
3. 如果同时有 graph 与 doc 证据，优先保留更具体、更短、更贴近问题的片段。
4. 输出目标是“能引用”的出处，而不是堆更多文本。

## Output Focus
- 书名
- 篇章或页码
- 可引用片段

## Stop Rule
- 选出 1 到 3 条最适合展示的出处片段后停止。
