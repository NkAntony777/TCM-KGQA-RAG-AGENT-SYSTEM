<skills>
  <summary>Available local skills that the agent can inspect with read_file.</summary>
  <skill name="compare-formulas" path="skills/compare-formulas/SKILL.md">
    <description>当用户比较两个或多个方剂、证候方案、功效差异、适用边界时使用。分别读取各实体证据，再补充出处或教材对照信息，不要只用单一实体证据回答比较题。</description>
  </skill>
  <skill name="external-source-verification" path="skills/external-source-verification/SKILL.md">
    <description>只有在用户明确要求联网、核验外部事实、查询最新官方信息，或本地知识库没有覆盖该问题时使用。优先核验官方来源或一手来源，不要默认替代本地中医知识链路。</description>
  </skill>
  <skill name="find-case-reference" path="skills/find-case-reference/SKILL.md">
    <description>当用户问题需要病例参考、类似医案、临床案例、主诉现病史体征对照时使用。优先查询 caseqa:// 或 search_evidence_text，返回相似案例摘要，不把病例参考当成事实主结论。</description>
  </skill>
  <skill name="read-formula-composition" path="skills/read-formula-composition/SKILL.md">
    <description>当用户问方剂组成、药材、配伍、君臣佐使、加减基础时使用。优先从 entity://<方剂>/使用药材 读取证据，必要时回退到 tcm_route_search 或 list_evidence_paths，不要直接给结论而不取证。</description>
  </skill>
  <skill name="read-formula-origin" path="skills/read-formula-origin/SKILL.md">
    <description>当用户问出处、出自、古籍、原文、教材来源、哪本书时使用。优先读取 book:// 或 qa:// 路径，补充书名、篇章、原文片段与该方剂/功效/组成的对应关系。</description>
  </skill>
  <skill name="route-tcm-query" path="skills/route-tcm-query/SKILL.md">
    <description>中医问答入口技能。用户问题涉及方剂、证候、功效、组成、出处、比较、古籍、教材、病例参考时使用。先识别意图、实体、比较对象和是否需要出处，再优先调用 tcm_route_search，不要跳过首轮路由。</description>
  </skill>
  <skill name="trace-source-passage" path="skills/trace-source-passage/SKILL.md">
    <description>当答案已经有初步结论，但还缺可引用的书名、篇章、原文片段时使用。优先从 graph/doc/book 证据中抽取最适合展示给用户的出处片段。</description>
  </skill>
</skills>
