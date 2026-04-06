---
name: read-formula-origin
description: 当用户问出处、出自、古籍、原文、教材来源、哪本书时使用。优先读取 book:// 或 qa:// 路径，补充书名、篇章、原文片段与该方剂/功效/组成的对应关系。
---

# Read Formula Origin

## Preferred Tools
- `read_evidence_path`
- `search_evidence_text`

## Workflow
1. 先找 `book://` 路径；没有时再看 `qa://`。
2. 优先调用 `read_evidence_path(book://...)`，查询词附加“出处 原文 古籍 教材”。
3. 如果 `book://` 缺失，再用 `search_evidence_text` 在 `book://` / `qa://` 范围补检索。
4. 只要拿到出处，优先提炼书名、篇章/页码、原文片段、与问题的关系。
5. 不要只说“出自古籍”，必须尽量具体到书名和位置。

## Output Focus
- 书名
- 篇章或页码
- 原文片段
- 与当前问题的关系

## Stop Rule
- 已拿到书名 + 篇章/页码 + 原文片段后停止。
- 如果来源冲突，保留更直接的片段并显式说明冲突。
