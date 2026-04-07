---
name: expand-entity-alias
description: 当用户问题涉及古籍旧名、异名、别名切换，或 files-first 没有稳定命中时使用。先读取 alias:// 路径，把当前实体扩展成可检索的别名集合，再继续追出处或原文。
---

# Expand Entity Alias

## Trigger Phrases
- 别名
- 异名
- 又名
- 古名
- 旧名
- 同名

## Preferred Tools
- `read_evidence_path`

## Preferred Paths
- `alias://<实体>`
- `entity://<实体>/*`

## Workflow
1. 先调用 `read_evidence_path(alias://...)` 读取当前实体的别名集合。
2. 优先提取能直接用于检索的别名，不要只返回“存在别名”。
3. 如果当前问题是出处、原文、古籍问题，把别名加入后续查询词。
4. 别名足够时停止，不要重复追无关路径。

## Output Focus
- 可直接检索的别名
- 别名对应的来源书目
- 哪个别名更适合继续检索古籍

## Stop Rule
- 已拿到 2 到 4 个可用别名后停止。
- 如果没有别名证据，不继续空转。

## Examples
- 六味地黄丸还有什么别名
- 地黄丸是不是六味地黄丸
- 八味丸和金匮肾气丸是什么关系
