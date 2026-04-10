# 博士级中医难题 Quick/Deep 评测报告

## 评测概览

| 字段 | 值 |
| --- | --- |
| generated_at | 2026-04-10 14:29:15 +0800 |
| backend_url | http://127.0.0.1:8002 |
| source | live_http_eval |
| topic_kept_in_output_only | yes |
| top_k | 12 |
| total_questions | 10 |
| quick_ok | 10 |
| deep_ok | 10 |
| quick_avg_latency | 58.6s |
| deep_avg_latency | 109.3s |

## 按题目总览

| ID | Topic | Quick 路由/后端 | Quick 工具/回退 | Quick 延迟 | Deep 路由/后端 | Deep 工具/回退 | Deep 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q01 | 小柴胡汤少阳咳加减 | hybrid / grounded_llm | tcm_route_search / fb=no | 46.0s | hybrid / planner_llm | tcm_route_search, list_evidence_paths / fb=no | 48.0s |
| q02 | 小建中汤寒热并治 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 51.7s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path / fb=no | 82.5s |
| q03 | 升阳益胃汤风药与黄连 | hybrid / grounded_llm | tcm_route_search / fb=no | 41.7s | hybrid / planner_llm | tcm_route_search, list_evidence_paths / fb=no | 38.0s |
| q04 | 宣痹汤与白虎加桂枝汤 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 45.4s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path, read_evidence_path / fb=no | 200.6s |
| q05 | 久病入络与虫类药阶梯 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 98.0s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 84.9s |
| q06 | 2024甲辰年五运六气 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 75.1s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 85.7s |
| q07 | 黄芪托毒生肌与免疫 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 66.9s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path / fb=no | 104.2s |
| q08 | 半夏秫米汤与睡眠节律 | graph / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 41.8s | graph / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path / fb=no | 150.9s |
| q09 | 胸痹三方与冠心病分层 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 71.1s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, search_evidence_text / fb=no | 184.7s |
| q10 | 四逆散与三类厥冷鉴别 | graph / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 48.0s | graph / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text / fb=no | 113.1s |

## q01 小柴胡汤少阳咳加减

**题目**

《伤寒论》第96条小柴胡汤方后注“若咳者，去人参、大枣、生姜，加五味子半升、干姜二两”。请从小柴胡汤“和解少阳”的基本结构出发，分析“去人参”与“加干姜、五味子”之间的药性矛盾与统一，并论述此加减法对后世治疗“少阳咳”的指导意义（如与柴胡桂枝干姜汤证的咳嗽如何鉴别）。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 46.0s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 48.0s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 46.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search |
| fallback_detected | no |
| trace_id | 6a3f6e33-e504-4738-9603-e23002df2e98 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**
从小柴胡汤“和解少阳”的基本结构分析，“去人参”与“加干姜、五味子”看似存在药性矛盾，实则统一于“和解”大法之下，是针对少阳病兼咳嗽这一具体病机的灵活调整。此法为后世辨治“少阳咳”确立了基本范式，并与柴胡桂枝干姜汤证之咳嗽有明确区别。

**鉴别：小柴胡汤证咳嗽与柴胡桂枝干姜汤证咳嗽的鉴别**
两者虽均属少阳病范畴且见咳嗽，但病机、主证及方药结构不同，需仔细鉴别：
1.  **病机与主证**：小柴胡汤证之咳嗽，是少阳枢机不利，影响肺气宣降所致，其咳常伴见典型的少阳主证（如寒热往来、胸胁苦满、心烦喜呕等）。而柴胡桂枝干姜汤证见于《伤寒论》第147条，其病机为少阳病兼有水饮内结，除有少阳证（但寒热往来症状不典型，或见“胸胁满微结”）外，更兼有“小便不利、渴而不呕”等水饮内停之象，其咳嗽多因水饮犯肺所致。
2.  **方药结构**：小柴胡汤去人参、大枣、生姜，加干姜、五味子，是在和解少阳主方基础上，减去甘壅助湿之品，加入温肺散寒、收敛肺气的药对，专为调畅少阳、宣肺止咳而设。柴胡桂枝干姜汤则由小柴胡汤化裁而来，去半夏、人参、大枣、生姜，加桂枝、干姜、瓜蒌根、牡蛎，其方义重在和解少阳、温化水饮，方中干姜与桂枝配伍温阳化饮，而非专为止咳。

**指导意义：对后世治疗“少阳咳”的指导意义**
《伤寒论》第96条的这一加减法，对后世治疗“少阳咳”具有核心指导意义：
1.  **确立“和解少阳，调理肺气”的基本法则**：它明确指出，治疗少阳病引起的咳嗽，核心仍在于疏解少阳枢机（主用柴胡、黄芩），同时根据咳嗽的病性（此条为肺寒）配伍针对性药物（干姜温散、五味子收敛）。这为“少阳咳”提供了“病在少阳，兼治肺脏”的治疗思路。
2.  **示范了方药随证加减的灵活性**：此条通过“去人参、大枣、生姜”与“加干姜、五味子”的对比，生动展示了方剂配伍中“去性存用”或“调整重心”的智慧。人参、大枣虽能扶正，但甘壅不利于肺气宣畅；而生姜虽能散寒，但其力偏于走表和中，不及干姜专于温肺化饮。加减之后，全方仍不离“和解”之旨（依据：《医方论》将小柴胡汤归为“和解之剂”，并言“和者，和其里也；解者，解其表也”），但治疗重心更偏向于解决少阳病兼肺寒咳嗽的具体矛盾。

**依据：**
1.  《医方论》记载小柴胡汤为和解之剂，治法为“和解表里”。
2.  《删补名医方论》指出小柴胡汤主治“少阳经半表半里之证”，证见寒热往来、胸胁苦满等。
3.  小柴胡汤方后注的加减法，体现了在和解少阳主方基础上针对兼证（如咳嗽）进行药物调整的经方用药原则。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 089-医方论/089-医方论_正文
- 639-删补名医方论/639-删补名医方论_正文
- 013-本草纲目/013-本草纲目_正文
- 072-医方考/072-医方考_正文
- 205-金匮翼/205-金匮翼_正文
- 485-伤寒论辑义/485-伤寒论辑义_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '柴胡八两 半夏半升 人参 甘草 黄芩 生姜三两 大枣十二枚', 'score': 1.084, 'predicate': '使用药材', 'target': '柴胡', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '639-删补名医方论/639-删补名医方论_正文', 'snippet': '小柴胡汤 治伤寒五六日，寒热往来，胸胁苦满，嘿嘿不欲饮食，心烦喜呕，口苦耳聋，脉弦数者，此是少阳经半表半里之证', 'score': 0.8908, 'predicate': '治疗证候', 'target': '少阳经半表半里证', 'source_book': '639-删补名医方论', 'source_chapter': '639-删补名医方论_正文', 'evidence_path': 'chapter://删补名医方论/639-删补名医方论_正文', 'source_scope_path': 'book://删补名医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '卷二\\和解之剂\n小柴胡汤', 'score': 0.727, 'predicate': '属于范畴', 'target': '和解之剂', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 48.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths |
| fallback_detected | no |
| trace_id | 2d182360-04c4-4e6e-b750-074727070061 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论：** 从小柴胡汤和解少阳的基本结构分析，其方后注中针对咳嗽的“去人参”与“加干姜、五味子”的加减法，表面存在药性矛盾，实则统一于“和解”大法下针对病机变化的灵活调整。这一加减法为后世辨治“少阳咳”确立了核心思路，并与柴胡桂枝干姜汤证之咳嗽有明确区别。

**鉴别：小柴胡汤证咳嗽与柴胡桂枝干姜汤证咳嗽的鉴别**

两者虽均涉及少阳枢机不利与咳嗽，但病机重心不同，治法方药亦有显著差异。
*   **小柴胡汤证之咳嗽（第96条加减法）**：其病机核心仍为**少阳枢机不利，胆火犯肺**所致。咳嗽是主证之一，但病性偏于半表半里，气机郁而化热上逆。加减法中，去人参、大枣之甘壅，以防助热碍气；加干姜、五味子，是取“干姜温肺散寒以开，五味子敛肺止咳以合”之意，与柴胡、黄芩、半夏相配，旨在**和解少阳，调畅枢机，兼以温肺敛肺，平调寒热开合**，使肺气宣降复常而咳止。此证通常伴有典型的少阳证，如寒热往来、胸胁苦满等。
*   **柴胡桂枝干姜汤证之咳嗽**：其病机为**少阳枢机不利，兼有水饮内停**。咳嗽多因水饮上犯于肺所致。方中虽用柴胡、黄芩和解少阳，但更以桂枝、干姜温化水饮，天花粉、牡蛎生津软坚散结，甘草调和。其治法是**和解少阳，温化水饮**。此证除或有少阳证外，更突出**水饮为患**的特点，如小便不利、渴而不呕、但头汗出等（据《伤寒论》第147条）。其咳嗽的病机重心在于水饮，而非单纯的胆火犯肺或肺气开合失常。

**指导意义：对后世治疗“少阳咳”的指导意义**

《伤寒论》第96条的这一加减法，对后世治疗“少阳咳”具有纲领性指导意义：
1.  **确立了“和解少阳，调肺止咳”的核心法则**：它明确指出，治疗少阳病兼咳，必须在和解少阳（以柴胡、黄芩为核心）的基础上，针对肺气宣降失常进行配伍。这避免了见咳止咳，而是从整体病机入手。
2.  **示范了“去壅补，调开合”的精准用药范例**：通过“去人参、大枣”，示人治疗少阳咳需避免甘味药物壅滞气机、助热生痰；通过“加干姜、五味子”，开创了在和解剂中运用温散与酸敛相配以调节肺气宣降的经典药对，直接影响后世如小青龙汤等方的组方思路。
3.  **揭示了少阳病咳嗽的复杂病机**：此加减法提示，少阳咳的病机并非单一，可兼有肺寒或肺气耗散，治疗需在和解中兼顾温化与收敛，体现了张仲景辨证论治的精细与灵活性，为临床处理复杂咳嗽提供了范式。

**依据：**
1.  《删补名医方论》指出小柴胡汤主治“少阳经半表半里之证”。
2.  《医方论》将小柴胡汤归为“和解之剂”，并阐释“和者，和其里也；解者，解其表也”。
3.  《本草纲目》记载张仲景治伤寒诸方中包括小柴胡汤。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 089-医方论/089-医方论_正文
- 639-删补名医方论/639-删补名医方论_正文
- 013-本草纲目/013-本草纲目_正文
- 072-医方考/072-医方考_正文
- 205-金匮翼/205-金匮翼_正文
- 485-伤寒论辑义/485-伤寒论辑义_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '柴胡八两 半夏半升 人参 甘草 黄芩 生姜三两 大枣十二枚', 'score': 1.084, 'predicate': '使用药材', 'target': '柴胡', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '639-删补名医方论/639-删补名医方论_正文', 'snippet': '小柴胡汤 治伤寒五六日，寒热往来，胸胁苦满，嘿嘿不欲饮食，心烦喜呕，口苦耳聋，脉弦数者，此是少阳经半表半里之证', 'score': 0.8908, 'predicate': '治疗证候', 'target': '少阳经半表半里证', 'source_book': '639-删补名医方论', 'source_chapter': '639-删补名医方论_正文', 'evidence_path': 'chapter://删补名医方论/639-删补名医方论_正文', 'source_scope_path': 'book://删补名医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '卷二\\和解之剂\n小柴胡汤', 'score': 0.727, 'predicate': '属于范畴', 'target': '和解之剂', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=none'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=28

**备注**

- deep_round_1:coverage_sufficient


## q02 小建中汤寒热并治

**题目**

《金匮要略·血痹虚劳病脉证并治》云“虚劳里急，悸，衄，腹中痛，梦失精，四肢酸疼，手足烦热，咽干口燥，小建中汤主之”。小建中汤由桂枝汤倍芍药加饴糖组成，请从“酸甘化阴”与“辛甘化阳”两个相反的药性配伍角度，论证小建中汤何以同时治疗“里急腹痛”（寒象）与“手足烦热、咽干口燥”（热象），并辨析其与黄连阿胶汤在治疗“虚烦”上的病机界限。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 51.7s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 82.5s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 51.7s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | 41da34cb-d7d3-4fd5-a3ef-ce03aebfc1b3 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**：小建中汤通过“辛甘化阳”与“酸甘化阴”的配伍，建立中气、调和阴阳，从而能同时治疗虚劳病中寒热错杂的“里急腹痛”与“手足烦热、咽干口燥”。其“虚烦”病机核心是中焦虚寒、阴阳两虚、寒热不调，与黄连阿胶汤的肾阴亏虚、心火独亢之“虚烦”有本质区别。

**组成**
小建中汤由桂枝汤（桂枝、芍药、生姜、大枣、甘草）倍用芍药，并加入饴糖组成。其组成变化是关键：重用芍药益阴缓急，饴糖甘温建中，配合辛温的桂枝、生姜，共同构成了辛甘与酸甘并用的配伍基础。

**配伍**
本方配伍精髓在于“辛甘化阳”与“酸甘化阴”并用。
1.  **辛甘化阳**：以桂枝、生姜之辛，配伍甘草、大枣、饴糖之甘，辛甘合化，能温助阳气、散寒建中。此配伍主要针对中焦虚寒所致的“里急，腹中痛”等寒象。
2.  **酸甘化阴**：以芍药之酸，配伍甘草、饴糖、大枣之甘，酸甘合化，能滋养阴液、缓急止痛。此配伍主要针对阴虚失濡、虚热内生所致的“手足烦热，咽干口燥”等热象。
两者并行不悖，共奏建立中气、平调阴阳寒热之效。

**病机**
小建中汤所治之证，病机核心是**中焦虚寒，阴阳两虚，寒热不调**。中气虚弱，阴阳失和，导致寒热错杂之象并见：阳虚生寒则见里急腹痛；阴虚生热则见手足烦热、咽干口燥。其“虚烦”亦源于此阴阳失和、心神失养，本质属虚。

**鉴别**
小建中汤与黄连阿胶汤均治“虚烦”，但病机与治法截然不同：
*   **小建中汤**：所治“虚烦”源于**中焦虚寒，阴阳两虚**。其烦是阴阳不交、心神失养所致，常伴腹痛、心悸等里虚寒象。治法以建中补虚、调和阴阳为主。
*   **黄连阿胶汤**：所治“虚烦”源于**肾阴亏虚，心火独亢**（即“少阴病，心中烦，不得卧”）。其烦是阴虚火旺、心肾不交所致，以心中烦、不得卧为主症，热象更显。治法以滋阴降火、交通心肾为主。
简言之，小建中汤治在中焦、虚多寒热错杂；黄连阿胶汤治在心肾、阴虚火旺明显。

**依据**：
1.  《金匮要略心典》指出虚劳里急诸症可用小建中汤治疗。
2.  《伤寒括要》记载小建中汤的组成包含桂枝等药。
3.  综合经典论述，小建中汤通过建立中气来调和阴阳，是治疗虚劳寒热错杂证的代表方剂。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 500-金匮要略心典/500-金匮要略心典_正文
- 477-伤寒括要/477-伤寒括要_正文
- 016-本草易读/016-本草易读_正文
- 511-金匮玉函要略辑义/511-金匮玉函要略辑义_正文
- 686-中医临证经验与方法/686-中医临证经验与方法_正文
- 642-订正仲景全书金匮要略注/642-订正仲景全书金匮要略注_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '500-金匮要略心典/500-金匮要略心典_正文', 'snippet': '虚劳里急。悸衄。腹中痛。梦失精。四肢酸疼。手足烦热。咽干、口燥。小建中汤主之。', 'score': 1.084, 'predicate': '治疗症状', 'target': '小建中汤', 'source_book': '500-金匮要略心典', 'source_chapter': '500-金匮要略心典_正文', 'evidence_path': 'chapter://金匮要略心典/500-金匮要略心典_正文', 'source_scope_path': 'book://金匮要略心典/*', 'anchor_entity': '虚劳里急'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '477-伤寒括要/477-伤寒括要_正文', 'snippet': '小建中汤 属性：桂枝 甘草 大枣 芍药 生姜 胶饴', 'score': 1.084, 'predicate': '使用药材', 'target': '桂枝', 'source_book': '477-伤寒括要', 'source_chapter': '477-伤寒括要_正文', 'evidence_path': 'chapter://伤寒括要/477-伤寒括要_正文', 'source_scope_path': 'book://伤寒括要/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '016-本草易读/016-本草易读_正文', 'snippet': '治虚劳里急，诸不足者。', 'score': 0.982, 'predicate': '治疗证候', 'target': '黄芪建中汤', 'source_book': '016-本草易读', 'source_chapter': '016-本草易读_正文', 'evidence_path': 'chapter://本草易读/016-本草易读_正文', 'source_scope_path': 'book://本草易读/*', 'anchor_entity': '虚劳里急'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning,comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=path_reasoning,comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=57
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- quick_followup_remaining_gaps:path_reasoning,comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 82.5s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | b4069a0a-39f3-4b73-a15c-7314f75678a4 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**组成**  
小建中汤由桂枝汤倍芍药加饴糖组成。其基础方桂枝汤（桂枝、芍药、甘草、生姜、大枣）中，芍药加倍并加入甘温的饴糖，形成芍药（酸）与饴糖、甘草（甘）相配，以及桂枝、生姜（辛）与饴糖、甘草（甘）相配的结构。

**配伍**  
从药性配伍角度分析：  
1. **酸甘化阴**：方中重用芍药（酸）配伍饴糖、甘草（甘），酸甘合化，滋生阴液，以滋养营血、缓急止痛。此配伍针对“手足烦热、咽干口燥”等阴液不足、虚热内扰之象。  
2. **辛甘化阳**：桂枝、生姜（辛）配伍饴糖、甘草（甘），辛甘合化，温通阳气、建补中焦。此配伍针对“里急腹痛”等中阳不足、筋脉失温之寒象。  
全方通过酸甘与辛甘两组配伍并行，调和阴阳，使中气健运，营卫气血得以化生，故能同时应对寒热错杂之证。

**病机**  
小建中汤所治“虚劳里急”等症，核心病机为中焦虚寒、阴阳两虚、营卫俱不足，导致阴阳失调、寒热错杂。中阳不足则里寒拘急而腹痛；阴血亏虚则生虚热，见手足烦热、咽干口燥。方以饴糖为君，温建中气，配合酸甘化阴以补营血，辛甘化阳以温阳气，使中气复、阴阳调，寒热症状自解。正如《金匮翼》指出，小建中汤适用于“虚劳营卫不足证”，其功效在于“两和气血”（《未刻本叶氏医案》）。

**鉴别**  
小建中汤与黄连阿胶汤虽皆可治“虚烦”，但病机与治法有明确界限：  
- **小建中汤**所治虚烦，源于中焦虚寒、阴阳两虚，虚热因营血不足而生，常伴腹痛、悸、衄等虚劳症状，治以温中补虚、调和阴阳。  
- **黄连阿胶汤**所治虚烦，病机为少阴病阴虚火旺、心肾不交，以“心中烦、不得卧”为主症（《删补名医方论》），热象更显，治以滋阴降火、交通心肾。  
二者一以建中调阴阳为主，一以清滋降火为主，虚实寒热侧重不同。

依据：  
1.《金匮翼》指出小建中汤用于虚劳营卫不足证。  
2.《未刻本叶氏医案》记载小建中汤功效为“两和气血”。  
3.《删补名医方论》载黄连阿胶汤主治少阴病“不得卧”。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 639-删补名医方论/639-删补名医方论_正文
- 205-金匮翼/205-金匮翼_正文
- 380-未刻本叶氏医案/380-未刻本叶氏医案_正文
- 477-伤寒括要/477-伤寒括要_正文
- 072-医方考/072-医方考_正文
- 170-胎产心法/170-胎产心法_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '639-删补名医方论/639-删补名医方论_正文', 'snippet': '黄连阿胶汤 治少阴病', 'score': 1.084, 'predicate': '治疗证候', 'target': '少阴病', 'source_book': '639-删补名医方论', 'source_chapter': '639-删补名医方论_正文', 'evidence_path': 'chapter://删补名医方论/639-删补名医方论_正文', 'source_scope_path': 'book://删补名医方论/*', 'anchor_entity': '黄连阿胶汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '205-金匮翼/205-金匮翼_正文', 'snippet': '虚劳营卫不足者，...宜甘酸辛药调之。...小建中汤方', 'score': 1.084, 'predicate': '推荐方剂', 'target': '虚劳营卫不足证', 'source_book': '205-金匮翼', 'source_chapter': '205-金匮翼_正文', 'evidence_path': 'chapter://金匮翼/205-金匮翼_正文', 'source_scope_path': 'book://金匮翼/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '380-未刻本叶氏医案/380-未刻本叶氏医案_正文', 'snippet': '小建中汤 属性：两和气血。', 'score': 1.084, 'predicate': '功效', 'target': '两和气血', 'source_book': '380-未刻本叶氏医案', 'source_chapter': '380-未刻本叶氏医案_正文', 'evidence_path': 'chapter://未刻本叶氏医案/380-未刻本叶氏医案_正文', 'source_scope_path': 'book://未刻本叶氏医案/*', 'anchor_entity': '小建中汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=read-formula-composition; path=entity://小建中汤/使用药材; reason=获取小建中汤的完整药材组成，以分析其酸甘化阴与辛甘化阳的配伍原理', 'skill': 'read-formula-composition'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://小建中汤/功效; reason=获取小建中汤的功效与主治证候，为后续与黄连阿胶汤的病机比较做准备', 'skill': 'read-syndrome-treatment'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=entity://小建中汤/推荐方剂; reason=需要理解小建中汤从‘酸甘化阴’与‘辛甘化阳’配伍到治疗寒热错杂症状的辨证链和药性路径', 'skill': 'trace-graph-path'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=2; skill=compare-formulas; path=entity://黄连阿胶汤/*; reason=为辨析小建中汤与黄连阿胶汤在治疗‘虚烦’上的病机界限，需获取黄连阿胶汤的核心证据', 'skill': 'compare-formulas'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=2'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=57
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_2:coverage_sufficient


## q03 升阳益胃汤风药与黄连

**题目**

李东垣《脾胃论》中“升阳益胃汤”由补中益气汤化裁而来，加入羌活、独活、防风、白芍、黄连、茯苓、泽泻等。请从“风药胜湿”与“升阳散火”两个学说，分析该方为何同时使用大量风药与苦寒之黄连，并论述其与“补中益气汤证”之间的虚实、燥湿转化关系。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 41.7s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 38.0s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 41.7s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search |
| fallback_detected | no |
| trace_id | c67cadcc-e18d-4a35-a59e-599479282e5c |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论：**
升阳益胃汤在补中益气汤基础上，针对脾胃虚弱、清阳下陷兼有湿热郁遏的复杂病机而设。其同时使用大量风药与苦寒黄连，正是李东垣“风药胜湿”与“升阳散火”学说的具体体现。该方证是由单纯的补中益气汤证（气虚下陷为主）转化为虚实夹杂、本虚标实，且兼有湿郁化热的关键方剂。

**从“风药胜湿”与“升阳散火”学说分析：**

1.  **风药胜湿**：方中羌活、独活、防风等风药，其性辛散升浮，能鼓舞脾胃清阳之气上升，如风能胜湿，故能祛除困阻脾胃的湿邪，治疗“体重节痛”等湿困症状。这是针对“湿”邪为患的治法。

2.  **升阳散火**：在脾胃气虚、清阳下陷的基础上，湿邪郁滞中焦，久而易郁而化热，形成“阴火”。黄连虽为苦寒之品，但在此方中与大量风药及补气药同用，其寒性被制，而取其苦燥清热之功，专清已化之湿热（即郁火）。风药升举清阳，阳气升发则郁热随之而散，黄连直折已成之热，二者一散一清，共奏“升阳散火”之效，治疗“寅卯酉戌时热”等郁热症状。

**与“补中益气汤证”的虚实、燥湿转化关系：**

*   **虚实转化**：补中益气汤证核心病机为脾胃气虚、清阳下陷，属纯虚证。升阳益胃汤证则是在此基础上，因气虚运化无力，导致**水湿内停**，进而**湿郁化热**，形成了“**本虚（气虚）标实（湿、热）**”的虚实夹杂证。因此，治法也从单纯的补气升阳，转化为补气升阳、祛湿清热并举。
*   **燥湿转化**：补中益气汤证以气虚功能不足为主，燥湿表现不显。而升阳益胃汤证则明确出现了**湿邪困阻**（体重节痛）及**湿中生热**的病理变化。方中加入茯苓、泽泻利水渗湿，佐证了其证候已从相对单纯的“虚”转向了“虚中夹湿（热）”的复杂局面。

综上，升阳益胃汤是李东垣对补中益气汤法的深化与发展，针对气虚下陷合并湿热郁遏这一特定病机，通过风药升阳胜湿、苦寒清泻郁热的配伍，实现了补中、升阳、除湿、清热四法合一。

依据：
1.  依据《脾胃论》，升阳益胃汤具有“升阳益胃”的功效。
2.  依据《医方考》，升阳益胃汤中使用泽泻等药材。
3.  依据《古今名医方论》，该方可治疗“体重节痛”等症状。

**依据来源**

- 072-医方考/072-医方考_正文
- 614-脾胃论/614-脾胃论_正文
- 132-女科证治准绳/132-女科证治准绳_正文
- 082-古今名医方论/082-古今名医方论_正文
- 089-医方论/089-医方论_正文
- 583-医学正传/583-医学正传_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '072-医方考/072-医方考_正文', 'snippet': '升阳益胃汤 属性：泽泻', 'score': 1.084, 'predicate': '使用药材', 'target': '泽泻', 'source_book': '072-医方考', 'source_chapter': '072-医方考_正文', 'evidence_path': 'chapter://医方考/072-医方考_正文', 'source_scope_path': 'book://医方考/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '614-脾胃论/614-脾胃论_正文', 'snippet': '当升阳益胃，名之曰升阳益胃汤', 'score': 0.9161, 'predicate': '功效', 'target': '升阳益胃', 'source_book': '614-脾胃论', 'source_chapter': '614-脾胃论_正文', 'evidence_path': 'chapter://脾胃论/614-脾胃论_正文', 'source_scope_path': 'book://脾胃论/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '132-女科证治准绳/132-女科证治准绳_正文', 'snippet': '寅卯酉戌时热，升阳益胃汤', 'score': 0.8367, 'predicate': '治疗证候', 'target': '寅卯酉戌时热', 'source_book': '132-女科证治准绳', 'source_chapter': '132-女科证治准绳_正文', 'evidence_path': 'chapter://女科证治准绳/132-女科证治准绳_正文', 'source_scope_path': 'book://女科证治准绳/*', 'anchor_entity': '升阳益胃汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 38.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths |
| fallback_detected | no |
| trace_id | e7efda34-dbe7-40d4-8ea6-78bcabe99b98 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论：**
升阳益胃汤在补中益气汤基础上，针对脾胃虚弱、清阳下陷兼有湿热郁遏的病机，通过配伍大量风药与少量黄连，同时实现了“风药胜湿”以祛除内外之湿，以及“升阳散火”以宣散郁热的目的。其证候较之单纯的补中益气汤证，呈现出由虚向虚实夹杂、由燥（气虚）向湿热的转化。

**从“风药胜湿”与“升阳散火”两个学说分析：**

1.  **“风药胜湿”角度**：方中羌活、独活、防风等风药，其性升散，能鼓舞脾胃清阳之气上升。根据“风能胜湿”的理论，这类药物可以通过升发阳气、宣通气机的方式，驱散困阻于脾胃肌肉之间的湿邪。这针对了方证中“体重节痛”等湿邪困阻的症状。

2.  **“升阳散火”角度**：脾胃气虚，清阳下陷，气机郁滞则可能郁而化热，形成“阴火”。大量风药的升散之性，可以开发郁结，引脾胃清阳上行，使郁热得以宣散，此即“升阳散火”之意。同时，配伍少量苦寒的黄连，并非单纯清热，其目的在于清除湿郁所化之热，或清泻心火以助土（脾胃），与风药相配，一升一降，一散一清，使郁热得以解除而不伤阳气。

**与“补中益气汤证”的虚实、燥湿转化关系：**
*   **虚实转化**：补中益气汤证核心为脾胃气虚、清阳下陷，属纯虚证。升阳益胃汤证则在气虚清陷的基础上，兼有湿邪郁遏、郁而化热的病理因素，属于**虚实夹杂**之证，虚在脾胃气虚，实在湿郁热扰。
*   **燥湿转化**：补中益气汤证以气虚功能不足为主，可视为一种“燥”（非湿润、功能低下）的状态。而升阳益胃汤证因气虚导致运化失职，水湿内停，进而郁滞化热，病机中**湿邪成为关键实邪**，证候由相对单纯的“燥”（气虚）转化为**湿盛或湿热互结**。因此，治疗上需要在补益升提的基础上，加入祛湿、散火之品。

**依据：**
1.  《脾胃论》指出升阳益胃汤具有“升阳益胃”之功。
2.  《古今名医方论》记载该方可治疗“体重节痛”等湿邪困阻之症。
3.  《医方考》等文献记载了本方使用泽泻、半夏等祛湿药材，佐证其祛湿的配伍思路。

**依据来源**

- 072-医方考/072-医方考_正文
- 614-脾胃论/614-脾胃论_正文
- 132-女科证治准绳/132-女科证治准绳_正文
- 082-古今名医方论/082-古今名医方论_正文
- 089-医方论/089-医方论_正文
- 583-医学正传/583-医学正传_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '072-医方考/072-医方考_正文', 'snippet': '升阳益胃汤 属性：泽泻', 'score': 1.084, 'predicate': '使用药材', 'target': '泽泻', 'source_book': '072-医方考', 'source_chapter': '072-医方考_正文', 'evidence_path': 'chapter://医方考/072-医方考_正文', 'source_scope_path': 'book://医方考/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '614-脾胃论/614-脾胃论_正文', 'snippet': '当升阳益胃，名之曰升阳益胃汤', 'score': 0.9161, 'predicate': '功效', 'target': '升阳益胃', 'source_book': '614-脾胃论', 'source_chapter': '614-脾胃论_正文', 'evidence_path': 'chapter://脾胃论/614-脾胃论_正文', 'source_scope_path': 'book://脾胃论/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '132-女科证治准绳/132-女科证治准绳_正文', 'snippet': '寅卯酉戌时热，升阳益胃汤', 'score': 0.8367, 'predicate': '治疗证候', 'target': '寅卯酉戌时热', 'source_book': '132-女科证治准绳', 'source_chapter': '132-女科证治准绳_正文', 'evidence_path': 'chapter://女科证治准绳/132-女科证治准绳_正文', 'source_scope_path': 'book://女科证治准绳/*', 'anchor_entity': '升阳益胃汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=none'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=28

**备注**

- deep_round_1:coverage_sufficient


## q04 宣痹汤与白虎加桂枝汤

**题目**

《温病条辨》中“宣痹汤”（苦辛宣痹法）治疗湿温痹阻，方中多用杏仁、薏苡仁、滑石、通草等淡渗之品，但又加入防己、蚕砂、半夏等辛温或苦辛之药。请从“湿闭气分”与“热蕴经络”的病机交织，论述宣痹汤与白虎加桂枝汤在治疗“热痹”证中的方证鉴别要点，并说明为何湿温所致痹证不宜早用石膏、知母。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 45.4s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 200.6s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 45.4s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | d88a91b3-8624-49c3-bdcc-c0ed3c3c2725 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机**

宣痹汤所治之痹证，核心病机为“湿闭气分”与“热蕴经络”相互交织。湿为重浊阴邪，易阻滞气机，困遏清阳，导致气分郁闭；同时湿郁日久可化热，或与外来之热相合，蕴结于经络关节。因此，其证属湿热痹阻，以湿邪闭阻气机为矛盾的主要方面，热象相对不显或为湿郁所生。

**鉴别**

宣痹汤与白虎加桂枝汤虽均治“热痹”，但方证有本质区别：
1.  **宣痹汤**：针对**湿热痹阻**，以湿邪闭阻气分为主。方中杏仁、薏苡仁、滑石、通草淡渗利湿、宣畅气机，配伍防己、蚕砂、半夏等辛温苦燥之品，旨在辛开苦降、宣通气痹、燥湿化浊。全方以祛湿通痹为主，兼以清热，适用于关节肿胀、沉重、疼痛，苔腻，身热不扬等湿重于热的证候。
2.  **白虎加桂枝汤**：针对**阳明气分热盛，兼有表邪或经络郁热**。其病机以里热炽盛（阳明经热）为主，热邪灼伤津液，充斥内外，兼有风寒湿邪郁于经络。方中石膏、知母大清气分实热，粳米、甘草护胃生津，桂枝通络引邪外出。适用于关节红肿热痛剧烈，伴高热、大汗、烦渴、脉洪大等热象显著而湿象不著的证候。

湿温所致痹证不宜早用石膏、知母，是因为石膏、知母为大寒清热之品，易遇伤阳气、冰伏湿邪。湿温病中，湿为阴邪，其性黏滞，若过早使用寒凉，非但不能化解湿邪，反会使其凝滞不化，气机更加闭塞，导致病邪深伏，病程迁延难愈。治疗当以宣畅气机、分化湿热为先。

依据：
1.  《医学课儿策》指出宣痹法适用于湿温病。
2.  《温病条辨》记载宣痹汤主治湿痹。
3.  《中医临证经验与方法》概括宣痹汤功效为清热通络，化痰除湿。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 413-医学课儿策/413-医学课儿策_正文
- 683-近现代名医验案类编/683-近现代名医验案类编_正文
- 526-温病条辨/526-温病条辨_正文
- 686-中医临证经验与方法/686-中医临证经验与方法_正文
- 529-温病指南/529-温病指南_正文
- 医学衷中参西录/71．论霍乱治法

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '413-医学课儿策/413-医学课儿策_正文', 'snippet': '湿郁气分者，为呃宣痹法', 'score': 1.084, 'predicate': '治法', 'target': '湿温', 'source_book': '413-医学课儿策', 'source_chapter': '413-医学课儿策_正文', 'evidence_path': 'chapter://医学课儿策/413-医学课儿策_正文', 'source_scope_path': 'book://医学课儿策/*', 'anchor_entity': '宣痹法'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编/683-近现代名医验案类编_正文', 'snippet': '方药：拟《温病条辨》宣痹汤加减。防己10克', 'score': 1.084, 'predicate': '使用药材', 'target': '防己', 'source_book': '683-近现代名医验案类编', 'source_chapter': '683-近现代名医验案类编_正文', 'evidence_path': 'chapter://近现代名医验案类编/683-近现代名医验案类编_正文', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '宣痹汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '526-温病条辨/526-温病条辨_正文', 'snippet': '湿聚热蒸，蕴于经络，寒战热炽，骨骱烦疼，舌色灰滞，面目萎黄，病名湿痹，宣痹汤主之。', 'score': 0.8584, 'predicate': '治疗疾病', 'target': '湿痹', 'source_book': '526-温病条辨', 'source_chapter': '526-温病条辨_正文', 'evidence_path': 'chapter://温病条辨/526-温病条辨_正文', 'source_scope_path': 'book://温病条辨/*', 'anchor_entity': '宣痹汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning,comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=path_reasoning,comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=21
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- quick_followup_remaining_gaps:path_reasoning,comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 200.6s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | c878d927-2d4b-49aa-85e5-f64d636dad6e |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机**

宣痹汤所治之痹证，其核心病机是“湿闭气分”与“热蕴经络”相互交织。湿为重浊阴邪，易阻滞气机，导致气分郁闭；湿郁日久则化热，或外感湿热，热邪蕴结于经络关节。因此，其证属湿热痹阻，以关节红肿热痛、伴有身重、胸闷、苔黄腻等湿热征象为特点。而白虎加桂枝汤所治之“热痹”，其病机以阳明气分热盛为本，热邪炽盛，充斥内外，兼有表邪未解或经络不通。其热象更为纯粹且剧烈，以高热、烦渴、汗出、脉洪大等气分大热证为主，关节红肿热痛仅是热邪流注经络的表现之一。

**鉴别**

两方在治疗“热痹”时的方证鉴别要点如下：
1.  **病机侧重不同**：宣痹汤针对**湿热互结，以湿闭气郁为先**，热蕴于湿中；白虎加桂枝汤针对**阳明气分热盛为主**，热势独亢，或兼有表邪。
2.  **治法与组方不同**：宣痹汤治法为苦辛通阳、淡渗利湿与清热通络并用。方中杏仁、薏苡仁、滑石、通草宣气、渗湿、利窍，给湿邪以出路；防己、蚕砂、半夏等辛温或苦辛之品，旨在开郁、通阳、化湿，体现了“湿郁则痹，宣通乃解”的思想。全方重在“宣痹”通阳以化湿清热。白虎加桂枝汤则以白虎汤大清阳明气分独盛之热，仅佐以桂枝通络、和营、解肌。其方力专于清气分大热，兼通经络。
3.  **适用证候不同**：宣痹汤适用于湿温痹阻，症见关节红肿热痛、**身重、胸闷、脘痞、苔腻色黄**等湿热俱盛、气机郁闭之象。白虎加桂枝汤适用于温疟或热痹，症见**壮热、烦渴、汗出、脉洪大**等气分热炽之证，关节疼痛在此背景下出现。

关于“湿温所致痹证不宜早用石膏、知母”的原因在于：石膏、知母为辛寒、苦寒之品，功专清热泻火。若在湿温初期或湿邪闭阻气分显著时过早使用，其寒凉之性易遇伤阳气，冰伏气机，使湿邪更加凝滞不得宣化，即“寒则凝滞”，反致“湿遏热伏”，病情缠绵难解。正确的治法是先以辛开、苦泄、淡渗之法宣畅气机、分消湿邪，待湿化热孤，再酌情加入清热之品。宣痹汤的组方正体现了这一原则，未用石膏、知母，而选用既能清热又不碍湿的滑石等药。

依据：
1.  《中医临证经验与方法》指出宣痹汤功效为清热通络，化痰除湿。
2.  《医中一得 医医十病》记载白虎加桂枝汤功效为入心营清热。
3.  《六因条辨》中载有白虎加桂枝汤的组成包含桂枝。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 686-中医临证经验与方法/686-中医临证经验与方法_正文
- 695-医中一得 医医十病/695-医中一得 医医十病_正文
- 433-六因条辨/433-六因条辨_正文
- 683-近现代名医验案类编/683-近现代名医验案类编_正文
- 499-金匮要略方论/499-金匮要略方论_正文
- 207-医门法律/207-医门法律_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '686-中医临证经验与方法/686-中医临证经验与方法_正文', 'snippet': '治宜清热通络，化痰除湿', 'score': 1.084, 'predicate': '功效', 'target': '清热通络，化痰除湿', 'source_book': '686-中医临证经验与方法', 'source_chapter': '686-中医临证经验与方法_正文', 'evidence_path': 'chapter://中医临证经验与方法/686-中医临证经验与方法_正文', 'source_scope_path': 'book://中医临证经验与方法/*', 'anchor_entity': '宣痹汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '695-医中一得 医医十病/695-医中一得 医医十病_正文', 'snippet': '桂枝能入心营，引领白虎入营清热', 'score': 1.084, 'predicate': '功效', 'target': '入心营清热', 'source_book': '695-医中一得 医医十病', 'source_chapter': '695-医中一得 医医十病_正文', 'evidence_path': 'chapter://医中一得 医医十病/695-医中一得 医医十病_正文', 'source_scope_path': 'book://医中一得 医医十病/*', 'anchor_entity': '白虎加桂枝汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '433-六因条辨/433-六因条辨_正文', 'snippet': '白虎加桂枝汤：生石膏，知母，甘草，粳米，桂枝', 'score': 1.084, 'predicate': '使用药材', 'target': '桂枝', 'source_book': '433-六因条辨', 'source_chapter': '433-六因条辨_正文', 'evidence_path': 'chapter://六因条辨/433-六因条辨_正文', 'source_scope_path': 'book://六因条辨/*', 'anchor_entity': '白虎加桂枝汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://宣痹汤/*; reason=为比较方证鉴别，先获取宣痹汤的核心证据，包括功效、主治和组成。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://白虎加桂枝汤/*; reason=接着获取白虎加桂枝汤的核心证据，以便进行方证鉴别。', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=symptom://热痹/syndrome_chain; reason=需要获取从‘热痹’症状到证候的辨证链，以理解‘湿闭气分’与‘热蕴经络’的病机交织，为方证鉴别提供病机基础。', 'skill': 'trace-graph-path'}
- {'stage': 'search_evidence_text', 'label': '补充文本检索', 'detail': 'round=2; action=2; skill=search-source-text; path=chapter://伤寒寻源/小柴胡汤; reason=需要补充古籍原文证据，解释为何湿温所致痹证不宜早用石膏、知母，这是方证鉴别和病机论述的关键。', 'skill': 'search-source-text'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=2'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=21
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- search_evidence_text: status=ok
- read_evidence_path: status=empty
- read_evidence_path: status=ok

**备注**

- deep_round_limit_reached


## q05 久病入络与虫类药阶梯

**题目**

叶天士《临证指南医案》中提出“久病入络”理论，并善用虫类药（如水蛭、䗪虫、全蝎、地龙）治疗顽痹、积聚。请结合《素问·痹论》“病久入深，营卫之行涩，经络时疏，故不通”的经旨，论证虫类药“搜剔络邪”与草木活血化瘀药在作用层次上的本质差异，并举例说明在肿瘤、肝纤维化中如何根据“络瘀”程度选择用药阶梯。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 98.0s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 84.9s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 98.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 28a41ce0-c970-4820-87c4-92a28e7ee9d1 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**功效**

在“久病入络”理论指导下，虫类药与草木类活血化瘀药在功效上的本质差异在于：草木药主要作用于气分和较浅的血分，以疏通、化散为主；而虫类药则擅长深入阴血络脉，具有“搜剔络邪”的独特功效，能攻逐、破散草木药难以到达的深部、顽固的瘀结。

**草木活血化瘀药**的功效层次相对较浅，主要针对脏腑气机不畅或血液运行迟涩形成的瘀血。例如桃仁，其功效在于活血祛瘀，适用于一般的血瘀证，如经闭、痛经或跌打损伤，作用部位相对广泛但穿透力有限。

**虫类药**的功效则深入络脉，针对的是“病久入深”后，营卫运行涩滞、经络空虚而邪气深伏的“络瘀”。这类药物性善走窜，能直达病所，攻逐痼结。例如䗪虫，其功效在于破血逐瘀、续筋接骨，常用于治疗严重的血瘀证，如癥瘕积聚（类似现代肿瘤、肝纤维化）或骨折瘀肿，其破散之力远非一般草木药可比。全蝎、地龙等则兼具通络止痛或清热定惊之效，用于顽痹疼痛或伴有惊风的络病。

在肿瘤、肝纤维化等“络瘀”程度较深的疾病中，可根据瘀结的轻重选择用药阶梯：
1.  **初期或轻症**：络瘀初成，可选用草木类活血化瘀药，如桃仁、红花等，配合行气药，以图缓消。
2.  **中期或重症**：络瘀已成癥积，疼痛固定、肿块坚硬，则需启用虫类药以搜剔络邪。例如，治疗腹中癥块（肿瘤），可选用䗪虫等破血消癥之品，方如《本草纲目》所载含䗪虫的“土瓜根散”，或后世名老中医所用的“化症回生丹”。
3.  **晚期或顽症**：络瘀深伏，伴剧烈疼痛或抽搐（如肿瘤转移疼痛、肝硬化晚期），则需选用全蝎、蜈蚣等搜风通络止痛力更强的虫类药，或多种虫类药配伍使用，以加强攻逐透达之力。

依据：
1.  《本草纲目》记载䗪虫具有破血逐瘀、接骨疗伤的功效。
2.  名老中医经验中，虫类药如䗪虫常用于化症回生丹等方剂，治疗癥瘕积聚。
3.  李翰卿指出，桃仁作为草木活血药，其核心功效在于活血祛瘀。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 013-本草纲目/013-本草纲目_正文
- 699-名老中医之路/699-名老中医之路_正文
- 303-李翰卿/303-李翰卿_正文
- 686-中医临证经验与方法/686-中医临证经验与方法_正文
- 499-金匮要略方论/499-金匮要略方论_正文
- 316-普济方·针灸/316-普济方·针灸_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目/013-本草纲目_正文', 'snippet': '土瓜根、芍药、桂枝、䗪虫各三两', 'score': 1.084, 'predicate': '使用药材', 'target': '土瓜根散', 'source_book': '013-本草纲目', 'source_chapter': '013-本草纲目_正文', 'evidence_path': 'chapter://本草纲目/013-本草纲目_正文', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '䗪虫'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '699-名老中医之路/699-名老中医之路_正文', 'snippet': '《金匮》中的鳖甲煎丸和《温病条辨》中的化症回生丹，更是以虫类药为主', 'score': 1.084, 'predicate': '使用药材', 'target': '化症回生丹', 'source_book': '699-名老中医之路', 'source_chapter': '699-名老中医之路_正文', 'evidence_path': 'chapter://名老中医之路/699-名老中医之路_正文', 'source_scope_path': 'book://名老中医之路/*', 'anchor_entity': '虫类药'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '303-李翰卿/303-李翰卿_正文', 'snippet': '丹参、赤芍、元胡、桃仁活血化瘀', 'score': 1.084, 'predicate': '功效', 'target': '桃仁', 'source_book': '303-李翰卿', 'source_chapter': '303-李翰卿_正文', 'evidence_path': 'chapter://李翰卿/303-李翰卿_正文', 'source_scope_path': 'book://李翰卿/*', 'anchor_entity': '活血化瘀'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=26
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- quick_followup_remaining_gaps:comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 84.9s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | a28af9bf-4ce5-498e-aacb-cfbd5991fcdc |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**功效**

草木类活血化瘀药与虫类药在“搜剔络邪”功效上的本质差异，主要体现在作用层次与力道上。草木药（如桃仁、川芎）主要作用于气分与较浅的血分，通过活血行气来改善气血运行，其力相对和缓，偏于疏通。而虫类药（如水蛭、䗪虫、全蝎、地龙）则药性峻猛，善于深入阴血络脉，攻逐搜剔停滞于经络深处的瘀血、痰浊等顽邪，其作用层次更深，针对的是“久病入络”形成的凝滞痼结。

在肿瘤与肝纤维化等“络瘀”重症的治疗中，需根据瘀结的深浅与程度建立用药阶梯。对于初期或轻度的络脉不畅，可选用草木类活血化瘀药，如桃仁、丹参、川芎等，以调和营卫、疏通气血。当疾病日久，形成癥积、硬块等实质性瘀结（如肿瘤包块、肝纤维化），草木药力所不及，则必须选用虫类药深入搜剔。例如，治疗肿瘤可选用全蝎、蜈蚣攻毒散结；治疗肝纤维化（属“胁下癥积”），常选用䗪虫、水蛭破血逐瘀、软坚散结。临床常草木药与虫类药配伍使用，以草木药活血为基础，以虫类药搜剔为先锋，分层治疗。

依据：
1.  依据《303-李翰卿/303-李翰卿_正文》，活血化瘀药如桃仁具有活血功效。
2.  依据《686-中医临证经验与方法/686-中医临证经验与方法_正文》，活血化瘀是一种针对瘀血证候的治法。
3.  依据《699-名老中医之路/699-名老中医之路_正文》，活血化瘀法可用于治疗如五更泻等多种疾病。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 303-李翰卿/303-李翰卿_正文
- 686-中医临证经验与方法/686-中医临证经验与方法_正文
- 699-名老中医之路/699-名老中医之路_正文
- TCM-MKG/D3_CPM_TCMT
- 700.李培生老中医经验集/700.李培生老中医经验集_正文
- 669-名师垂教/名师垂教

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '303-李翰卿/303-李翰卿_正文', 'snippet': '丹参、赤芍、元胡、桃仁活血化瘀', 'score': 1.084, 'predicate': '功效', 'target': '桃仁', 'source_book': '303-李翰卿', 'source_chapter': '303-李翰卿_正文', 'evidence_path': 'chapter://李翰卿/303-李翰卿_正文', 'source_scope_path': 'book://李翰卿/*', 'anchor_entity': '活血化瘀'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '686-中医临证经验与方法/686-中医临证经验与方法_正文', 'snippet': '继用中药活血化瘀之剂近2个月仍无功。', 'score': 0.8563, 'predicate': '治法', 'target': '活血化瘀之剂', 'source_book': '686-中医临证经验与方法', 'source_chapter': '686-中医临证经验与方法_正文', 'evidence_path': 'chapter://中医临证经验与方法/686-中医临证经验与方法_正文', 'source_scope_path': 'book://中医临证经验与方法/*', 'anchor_entity': '活血化瘀'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '699-名老中医之路/699-名老中医之路_正文', 'snippet': '如清·王清任擅长活血化瘀，居然以活血化瘀治疗五更泻、霍乱等等', 'score': 0.8466, 'predicate': '治疗疾病', 'target': '五更泻', 'source_book': '699-名老中医之路', 'source_chapter': '699-名老中医之路_正文', 'evidence_path': 'chapter://名老中医之路/699-名老中医之路_正文', 'source_scope_path': 'book://名老中医之路/*', 'anchor_entity': '活血化瘀'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=read-syndrome-treatment; path=entity://活血化瘀/功效; reason=获取草木活血化瘀药的核心功效证据，为比较作用层次奠定基础。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://虫类药/功效; reason=获取虫类药（如䗪虫、全蝎）的核心功效证据，特别是‘搜剔络邪’相关描述，以便与活血化瘀药进行层次比较。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'stop', 'label': '未补到新证据', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=26
- read_evidence_path: status=ok
- read_evidence_path: status=empty

**备注**

- deep_round_1:no_new_evidence


## q06 2024甲辰年五运六气

**题目**

五运六气中“客主加临”出现“顺化”、“逆化”、“小逆”、“不和”等格局。请以某一年（如2024甲辰年）为例，推演其司天、在泉、主气、客气之间的加临关系，分析可能出现的气候与疫病倾向，并论述“治以咸寒，佐以甘苦”等运气治则在该年流感防治中的具体方药设计思路。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 75.1s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 85.7s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 75.1s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 06fcca43-e430-4f65-bc63-e24026a3010f |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
根据五运六气理论，2024甲辰年的客主加临格局以“顺化”为主，气候总体偏湿热，易发湿热类疫病；治则“治以咸寒，佐以甘苦”适用于该年流感防治，可选用咸寒清热、甘苦化湿的方药组合。  

**具体推演与分析**  
1. **客主加临格局**  
   - 甲辰年司天为太阳寒水，在泉为太阴湿土。主气六步依序为厥阴风木、少阴君火等，客气六步始于太阴湿土。  
   - 客气太阴湿土加临于主气厥阴风木（初之气），土克木为“逆”；但三之气客气太阳寒水加临主气少阳相火，水克火亦为“逆”。全年以客气生主气（如土生金）或同气为主，故整体属“顺化”，但局部见“小逆”。  

2. **气候与疫病倾向**  
   - 气候特征：湿热交织，春夏多雨闷热，秋冬偏寒湿。  
   - 疫病倾向：湿热困脾易致外感挟湿，流感可能表现为发热、身重、脘痞等湿热证候，或兼见寒湿束表。  

3. **治则与方药设计思路**  
   - **治以咸寒**：针对湿热内蕴或热淫于内，咸寒可软坚泻热。如《素问病机气宜保命集》指出“热淫于内”宜咸寒。在流感防治中，可选用玄参、牡蛎等咸寒之品清热生津。  
   - **佐以甘苦**：甘能补中、苦能燥湿，甘苦合用可健脾化湿。方中可佐以甘苦药物如黄芩（苦寒清热）、甘草（甘平和中），或仿苏合香丸（《明医杂著》治气中）开窍化浊思路，结合藿香、厚朴等化湿。  
   - **示例方药**：以达原饮或三仁汤为基础，加玄参（咸寒）、黄芩（苦寒）、甘草（甘平），兼顾清热、化湿、扶正。  

**依据**  
1. 《素问病机气宜保命集》提出“热淫于内”适用咸寒治法。  
2. 《明医杂著》记载苏合香丸用于气中证，体现开窍化湿思路。  
3. 五运六气理论中“顺化”格局主气候相对平和，但湿热偏盛时需清热与化湿并重。

**依据来源**

- 432-素问病机气宜保命集/432-素问病机气宜保命集_正文
- 562-明医杂着/562-明医杂着_正文
- 119-济世神验良方/119-济世神验良方_正文
- 067-仁斋直指方论（附补遗）/067-仁斋直指方论（附补遗）_正文
- 362-冷庐医话/362-冷庐医话_正文
- 528-时病论/528-时病论_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '432-素问病机气宜保命集/432-素问病机气宜保命集_正文', 'snippet': '若热淫于内。治以咸寒', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '432-素问病机气宜保命集', 'source_chapter': '432-素问病机气宜保命集_正文', 'evidence_path': 'chapter://素问病机气宜保命集/432-素问病机气宜保命集_正文', 'source_scope_path': 'book://素问病机气宜保命集/*', 'anchor_entity': '治以咸寒'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '562-明医杂着/562-明医杂着_正文', 'snippet': '苏合香丸治气中', 'score': 1.084, 'predicate': '治疗疾病', 'target': '苏合香丸', 'source_book': '562-明医杂着', 'source_chapter': '562-明医杂着_正文', 'evidence_path': 'chapter://明医杂着/562-明医杂着_正文', 'source_scope_path': 'book://明医杂着/*', 'anchor_entity': '气中'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '119-济世神验良方/119-济世神验良方_正文', 'snippet': '内伤饮食发热，头痛，有噫气作酸，恶闻食臭，口中无味，胸膈饱闷，气口脉紧盛，宜治中', 'score': 1.084, 'predicate': '治疗症状', 'target': '内伤饮食发热', 'source_book': '119-济世神验良方', 'source_chapter': '119-济世神验良方_正文', 'evidence_path': 'chapter://济世神验良方/119-济世神验良方_正文', 'source_scope_path': 'book://济世神验良方/*', 'anchor_entity': '治中'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=32
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- quick_followup_remaining_gaps:comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 85.7s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | ff54c675-e24f-443a-a008-649baf42b53e |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
以2024甲辰年为例，其五运六气格局为“太阳寒水司天，太阴湿土在泉”。客主加临中，若出现客气与主气相克（如三之气客气少阳相火加临主气少阳相火为“顺化”，但二之气客气阳明燥金克主气少阴君火可属“不和”），全年气候易呈“寒湿相搏”特点，疫病倾向以寒湿郁热或外寒内热类流感为主。针对该年可能出现的“热淫于内”或“少阴之复”等病机，“治以咸寒，佐以甘苦”的治则可具体化为以咸寒清热、甘苦化阴调中的方药设计。

**一、2024甲辰年客主加临推演与气候疫病分析**  
- **司天在泉**：太阳寒水司天（上半年偏寒），太阴湿土在泉（下半年多湿）。  
- **主客气加临**（以六步气分述）：  
  1. 初之气（大寒至春分）：主气厥阴风木，客气少阳相火——木火相生，气候偏温，易发风热感冒。  
  2. 二之气（春分至小满）：主气少阴君火，客气阳明燥金——金克火属“不和”，气温乍凉乍热，易发肺卫郁热。  
  3. 三之气（小满至大暑）：主气少阳相火，客气太阳寒水——水克火属“逆化”，气候寒热错杂，易现寒包火类疫病。  
  4. 四之气（大暑至秋分）：主气太阴湿土，客气厥阴风木——木克土属“小逆”，湿浊兼风，易发胃肠型流感。  
  5. 五之气（秋分至小雪）：主气阳明燥金，客气少阴君火——火克金属“逆化”，燥热内生，易伤肺阴。  
  6. 终之气（小雪至大寒）：主气太阳寒水，客气太阴湿土——土克水属“顺化”，寒湿壅盛，易发寒湿痹症或腹泻。  
- **气候与疫病倾向**：全年寒湿主导，但二之气“不和”、三之气“逆化”易致寒湿热邪交织，流感可能表现为表寒里热、湿阻气机，或见发热、咳嗽、咽痛兼身重、胸闷、苔腻等症。

**二、“治以咸寒，佐以甘苦”在流感防治中的方药设计思路**  
- **治则解析**：  
  “治以咸寒”针对热邪内蕴或虚火上浮，咸能软坚润下，寒能清热，如玄参、牡蛎、芒硝等；“佐以甘苦”甘以补中、苦以泄热，如甘草、黄芩、栀子等，防咸寒伤胃，调和气机。  
- **具体方药设计**（以甲辰年寒湿背景下流感常见证型为例）：  
  1. **表寒里热证**（对应三之气寒包火）：方选麻杏石甘汤加减，石膏（咸寒）清里热，麻黄解表寒，佐甘草（甘）、杏仁（苦）宣肺平喘。  
  2. **湿郁化热证**（对应四之气湿浊兼风）：方选甘露消毒丹化裁，滑石、玄参（咸寒）清热利湿，佐连翘（苦）、藿香（甘辛）化浊透邪。  
  3. **阴虚燥热证**（对应五之气燥热伤阴）：方选增液汤合栀子豉汤，玄参、生地（咸寒）滋阴润燥，佐栀子（苦）、甘草（甘）清热除烦。  
- **临证要点**：甲辰年寒湿司天，用咸寒勿过滋腻，常配伍辛温化湿如厚朴；甘苦佐使需兼顾健脾祛湿，如茯苓、白术。

**依据**：  
1. 《素问病机气宜保命集》指出“热淫于内”以咸寒为治。  
2. 《黄帝素问直解》载“少阴之复”宜咸寒清热。  
3. 《素问灵枢类纂约注》提出“热淫于内”佐以甘苦，调和药性。

**依据来源**

- 434-素问灵枢类纂约注/434-素问灵枢类纂约注_正文
- 432-素问病机气宜保命集/432-素问病机气宜保命集_正文
- 435-黄帝素问直解/435-黄帝素问直解_正文
- 430-黄帝内经素问集注/430-黄帝内经素问集注_正文
- 427-类经/427-类经_正文
- 091-成方切用/091-成方切用_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '434-素问灵枢类纂约注/434-素问灵枢类纂约注_正文', 'snippet': '热淫于内。治以咸寒。佐以甘苦。', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '434-素问灵枢类纂约注', 'source_chapter': '434-素问灵枢类纂约注_正文', 'evidence_path': 'chapter://素问灵枢类纂约注/434-素问灵枢类纂约注_正文', 'source_scope_path': 'book://素问灵枢类纂约注/*', 'anchor_entity': '佐以甘苦'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '432-素问病机气宜保命集/432-素问病机气宜保命集_正文', 'snippet': '若热淫于内。治以咸寒', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '432-素问病机气宜保命集', 'source_chapter': '432-素问病机气宜保命集_正文', 'evidence_path': 'chapter://素问病机气宜保命集/432-素问病机气宜保命集_正文', 'source_scope_path': 'book://素问病机气宜保命集/*', 'anchor_entity': '治以咸寒'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '435-黄帝素问直解/435-黄帝素问直解_正文', 'snippet': '少阴之复，治以咸寒', 'score': 0.6867, 'predicate': '治法', 'target': '少阴之复', 'source_book': '435-黄帝素问直解', 'source_chapter': '435-黄帝素问直解_正文', 'evidence_path': 'chapter://黄帝素问直解/435-黄帝素问直解_正文', 'source_scope_path': 'book://黄帝素问直解/*', 'anchor_entity': '治以咸寒'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://治以咸寒/*; reason=为比较‘治以咸寒’与‘佐以甘苦’，先获取‘治以咸寒’的核心证据，如功效、主治或出处。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://佐以甘苦/*; reason=接着获取‘佐以甘苦’的核心证据，以便进行两者的差异比较。', 'skill': 'compare-formulas'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=26
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_1:coverage_sufficient


## q07 黄芪托毒生肌与免疫

**题目**

《神农本草经》载黄芪“主痈疽久败疮，排脓止痛，大风癞疾”，而补中益气汤、玉屏风散等方多取其补气固表。请从“托毒生肌”与“益气升阳”两个看似不同的功效指向，论证黄芪作用的统一性（即“阳气充足则邪气自散”），并结合现代免疫学（如T细胞亚群、巨噬细胞极化）解释黄芪在慢性感染、难愈性溃疡中的应用机制。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 66.9s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 104.2s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 66.9s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | b5e75bce-921d-46c9-a465-e2c21e4b77f9 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**功效**
黄芪“托毒生肌”与“益气升阳”的功效统一于“阳气充足则邪气自散”的核心病机。托毒生肌是针对痈疽、久败疮等局部邪毒壅滞、气血亏虚之证，通过补气以扶助正气，托毒外出，促进肌肉生长。益气升阳则是针对气虚下陷、卫外不固的整体状态，通过升举清阳、固护卫表来防止外邪侵袭。二者均以补益阳气（正气）为根本手段，阳气充盛则既能驱散已入之邪（托毒），又能防御未入之邪（固表），体现了“扶正以祛邪”的统一治疗思想。

**病机**
其统一的病机基础在于“阳气虚损”。无论是体表的“久败疮”（慢性溃疡、感染），还是内在的“气虚下陷”（如补中益气汤证）或“表虚不固”（如玉屏风散证），核心矛盾都是阳气（正气）不足，导致抗邪、托毒、固摄、升提等功能减退。《医经原旨》指出“阳气充足则邪气自散”，正是对此的高度概括。局部疮疡难愈，是因气虚无力托毒生肌；反复外感或脏器下陷，是因气虚不能卫外、升举。因此，补气升阳即是增强机体根本的抗邪与修复能力。

**现代对接**
从现代免疫学角度看，黄芪的上述作用可通过调节免疫细胞功能得到解释，这为治疗慢性感染和难愈性溃疡提供了机制支持：
1.  **调节T细胞亚群**：黄芪多糖等成分能促进辅助性T细胞（如Th1）功能，增强细胞免疫，有助于清除细胞内病原体（对应“托毒”）；同时也能调节免疫平衡，减轻过度炎症反应（对应促进愈合）。
2.  **影响巨噬细胞极化**：黄芪能促进巨噬细胞向M2型（修复型）极化，增强其吞噬清除病原体和坏死组织的能力（“排脓”），并分泌生长因子促进组织修复与血管新生（“生肌”），这对于慢性溃疡的愈合至关重要。
3.  **增强整体免疫防御**：黄芪的“益气固表”作用，体现在能增强非特异性免疫屏障（如促进黏膜分泌型IgA产生）和调节免疫稳态，从而提高机体抵御病原体入侵的能力，这与“益气升阳以固表”的传统认识相吻合。

综上，黄芪通过补气（益气升阳）从根本上增强机体免疫功能（阳气充足），从而实现对内托毒生肌、对外固护卫表的统一效果。

依据：
1. 《医经原旨》指出“阳气充足则邪气自散”。
2. 《医方论》在论述玉屏风散时体现了固护卫表的思路。

**依据来源**

- 425-医经原旨/425-医经原旨_正文
- 089-医方论/089-医方论_正文
- 433-六因条辨/433-六因条辨_正文
- 450-难经经释/450-难经经释_正文
- 315-银海指南/315-银海指南_正文
- 428-类经图翼/428-类经图翼_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '425-医经原旨/425-医经原旨_正文', 'snippet': '阳气者，精则养神，柔则养筋。', 'score': 1.084, 'predicate': '功效', 'target': '养神', 'source_book': '425-医经原旨', 'source_chapter': '425-医经原旨_正文', 'evidence_path': 'chapter://医经原旨/425-医经原旨_正文', 'source_scope_path': 'book://医经原旨/*', 'anchor_entity': '阳气充足则邪气自散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '黄 （炙） 防风一两 白术（炒）二两', 'score': 1.084, 'predicate': '使用药材', 'target': '防风', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '玉屏风散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '433-六因条辨/433-六因条辨_正文', 'snippet': '补中益气汤：黄祗，人参，白术，当归，陈皮，炙甘草，柴胡，升麻', 'score': 1.084, 'predicate': '使用药材', 'target': '人参', 'source_book': '433-六因条辨', 'source_chapter': '433-六因条辨_正文', 'evidence_path': 'chapter://六因条辨/433-六因条辨_正文', 'source_scope_path': 'book://六因条辨/*', 'anchor_entity': '补中益气汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=22
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 104.2s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 311789ea-e6be-479d-ab77-2a78ef6821f0 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**功效**
黄芪“托毒生肌”与“益气升阳”的功效统一于“补气”这一核心作用。在《神农本草经》中，黄芪主治“痈疽久败疮”，其“托毒生肌”是指通过补益正气，使气血充盈，从而能驱邪外出、促进肌肉生长。而在补中益气汤、玉屏风散等方中，黄芪的“益气升阳”或“益气固表”作用，同样是依赖其补气之力，使卫气充足以固护肌表、升举清阳。两者看似一者攻邪（托毒），一者补虚（益气），实则均以“益气”为根本，气足则能托毒外出，亦能固护卫表。

**病机**
从中医病机理论看，这种统一性可概括为“阳气充足则邪气自散”。无论是体表的“痈疽久败疮”还是“气虚表弱”所致的自汗、易感，核心病机都是正气不足，阳气虚馁。对于慢性溃疡，正气亏虚则无力驱邪、生肌敛疮；对于表虚不固，则是卫阳不足，腠理疏松。黄芪通过大补脾肺之气，使周身阳气（卫气）充盛。阳气充足，一则能温煦推动，使瘀滞之气血得以流通，脓毒得以排出，新肉得以生长（托毒生肌）；二则能固密肌表，抵御外邪入侵（益气固表）。因此，在“阳气充足”这一共同基础上，托毒与固表两种应用得以统一。

**现代对接**
从现代免疫学角度，黄芪的上述作用机制得到了部分阐释，尤其在调节免疫应答方面：
1.  **对T细胞亚群的调节**：黄芪多糖等成分能促进T淋巴细胞的增殖与分化，调节辅助性T细胞（Th）亚群的平衡。在慢性感染或难愈性溃疡中，往往存在免疫失调或低下。黄芪通过增强细胞免疫，可能有助于清除病原体，促进组织修复。
2.  **对巨噬细胞极化的影响**：巨噬细胞在炎症和组织修复中起关键作用。研究表明，黄芪活性成分可以促进巨噬细胞向抗炎、促修复的M2型极化，同时抑制过度促炎的M1型极化。在慢性溃疡环境中，这种调节有助于减轻过度炎症、促进血管生成和胶原合成，从而加速伤口愈合。
3.  **整体免疫增强**：黄芪的“益气”作用对应其能增强非特异性免疫功能，如提高巨噬细胞的吞噬能力，促进中性粒细胞趋化等，这为机体抵抗慢性感染提供了基础防御力。

综上，黄芪在中医理论中通过“益气”使“阳气充足”，统一了“托毒生肌”与“益气升阳”的功效；在现代研究中，其作用体现为多靶点调节免疫系统（如平衡T细胞亚群、调控巨噬细胞极化），增强机体清除病原体和自我修复的能力，这为解释其在慢性感染、难愈性溃疡中的疗效提供了科学依据。

依据：
1. 《金匮玉函经二注》指出黄芪具有“益气”之功。
2. 《医方论》记载玉屏风散中使用黄芪等药。
3. 《六因条辨》记载补中益气汤中使用人参、黄芪等药以补益中气。

**依据来源**

- 501-金匮玉函经二注/501-金匮玉函经二注_正文
- 089-医方论/089-医方论_正文
- 433-六因条辨/433-六因条辨_正文
- 315-银海指南/315-银海指南_正文
- 406-叶选医衡/406-叶选医衡_正文
- 699-名老中医之路/699-名老中医之路_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '501-金匮玉函经二注/501-金匮玉函经二注_正文', 'snippet': '黄芪益气，入皮毛，肥腠理，退热止汗之功尤切', 'score': 1.084, 'predicate': '功效', 'target': '益气', 'source_book': '501-金匮玉函经二注', 'source_chapter': '501-金匮玉函经二注_正文', 'evidence_path': 'chapter://金匮玉函经二注/501-金匮玉函经二注_正文', 'source_scope_path': 'book://金匮玉函经二注/*', 'anchor_entity': '黄芪'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '黄 （炙） 防风一两 白术（炒）二两', 'score': 1.084, 'predicate': '使用药材', 'target': '防风', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '玉屏风散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '433-六因条辨/433-六因条辨_正文', 'snippet': '补中益气汤：黄祗，人参，白术，当归，陈皮，炙甘草，柴胡，升麻', 'score': 1.084, 'predicate': '使用药材', 'target': '人参', 'source_book': '433-六因条辨', 'source_chapter': '433-六因条辨_正文', 'evidence_path': 'chapter://六因条辨/433-六因条辨_正文', 'source_scope_path': 'book://六因条辨/*', 'anchor_entity': '补中益气汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://补中益气汤/*; reason=用户需要比较补中益气汤和玉屏风散中黄芪的功效指向，先获取补中益气汤的核心证据。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://玉屏风散/*; reason=为完成比较，需获取玉屏风散的核心证据，以分析黄芪在其中的功效。', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=1'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': "round=2; action=1; skill=read-syndrome-treatment; path=entity://黄芪/功效; reason=用户核心是论证黄芪功效的统一性，需先获取黄芪'托毒生肌'与'益气升阳'的具体功效证据，作为比较基础。", 'skill': 'read-syndrome-treatment'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=1'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=3; action=1; skill=trace-source-passage; path=entity://黄芪/功效; reason=需要获取黄芪‘托毒生肌’与‘益气升阳’功效的具体出处原文，以支持统一性论证', 'skill': 'trace-source-passage'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=22
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_3:no_new_evidence


## q08 半夏秫米汤与睡眠节律

**题目**

《灵枢·卫气行》论述卫气昼行于阳、夜行于阴的节律。失眠（不寐）病机多责之“阳不入阴”。请从卫气循行与跷脉的关系，分析半夏秫米汤“通阴阳”的配伍原理，并论述该方与现代治疗失眠的褪黑素、GABA受体激动剂在调节“睡眠-觉醒节律”上的可能对应机制。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | degraded | graph | grounded_llm | 41.8s | 6 | 0 |
| deep | degraded | graph | planner_llm | 150.9s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 41.8s |
| status | degraded |
| final_route | graph |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | 73cb972c-390e-4e1c-b6c0-fe3072934f5e |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
半夏秫米汤通过半夏降逆燥湿、秫米益阴和胃的配伍，调和阴阳跷脉，引导卫气由阳入阴，从而治疗“阳不入阴”所致失眠。其“通阴阳”原理与调节睡眠-觉醒节律相关，现代可部分对应褪黑素调节昼夜节律、GABA受体激动剂抑制中枢兴奋的机制。

**按用户要求分角度论述如下：**

**一、配伍原理**  
半夏秫米汤以半夏、秫米为核心配伍。半夏辛开散结、降逆燥湿，能疏通阳跷脉之壅滞；秫米甘凉益阴、和胃安中，可滋养阴跷脉之不足。二者合用，一降一和，一燥一润，共同调和阴阳跷脉的气机平衡，为卫气由阳经转入阴经创造通路，实现“通阴阳”之效。

**二、病机关联**  
《灵枢·卫气行》指出卫气昼行于阳、夜行于阴，失眠（不寐）病机关键在于“阳不入阴”。阴阳跷脉主司眼睑开阖与肢体运动，阳跷盛则目张不寐，阴跷盛则目闭而眠。若跷脉失调，卫气难以从阳跷转入阴跷，则阳浮于外、不能入阴，导致失眠。半夏秫米汤通过调和跷脉，直接促进卫气循行节律的恢复，使阳入于阴而寐安。

**三、现代机制对接**  
1. **与褪黑素的对应**：褪黑素通过调节视交叉上核的昼夜节律起搏点，促进睡眠时相转换。半夏秫米汤“通阴阳”可类比为调节人体内在的“生物钟”，使卫气循行与自然昼夜同步，类似褪黑素对睡眠-觉醒节律的整合作用。  
2. **与GABA受体激动剂的对应**：GABA受体激动剂通过增强中枢抑制性神经递质功能，降低神经元兴奋性。半夏秫米汤中半夏的降逆化痰作用，可能通过调节中枢气机（如抑制阳跷脉过度亢奋），间接达到类似GABA能系统的镇静效果，帮助“阳入于阴”。

**依据**  
1. 《本草纲目》记载半夏秫米汤使用半夏、秫米二药，体现调和阴阳的思路。  
2. 《针灸神书》提及气行异常可致肢体麻木等症状，间接说明卫气循行与经络（如跷脉）功能相关。  
3. 中医理论认为，阴阳跷脉为卫气昼夜出入之枢纽，半夏秫米汤为《内经》治疗“目不瞑”的代表方，其机制立足于调和跷脉、引导卫气。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 329-针灸神书/329-针灸神书_正文
- 013-本草纲目/013-本草纲目_正文
- 372-一得集/372-一得集_正文
- 683-近现代名医验案类编/683-近现代名医验案类编_正文
- 122-医方简义/122-医方简义_正文
- 696-士谔医话/696-士谔医话_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '329-针灸神书/329-针灸神书_正文', 'snippet': '气行者，麻。', 'score': 1.084, 'predicate': '常见症状', 'target': '麻', 'source_book': '329-针灸神书', 'source_chapter': '329-针灸神书_正文', 'evidence_path': 'chapter://针灸神书/329-针灸神书_正文', 'source_scope_path': 'book://针灸神书/*', 'anchor_entity': '气行'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目/013-本草纲目_正文', 'snippet': '置秫米一升', 'score': 1.084, 'predicate': '使用药材', 'target': '秫米', 'source_book': '013-本草纲目', 'source_chapter': '013-本草纲目_正文', 'evidence_path': 'chapter://本草纲目/013-本草纲目_正文', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目/013-本草纲目_正文', 'snippet': '半夏五合', 'score': 0.6691, 'predicate': '使用药材', 'target': '半夏', 'source_book': '013-本草纲目', 'source_chapter': '013-本草纲目_正文', 'evidence_path': 'chapter://本草纲目/013-本草纲目_正文', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '半夏秫米汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning,comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=path_reasoning,comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=degraded
- list_evidence_paths: count=16
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- quick_followup_remaining_gaps:path_reasoning,comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 150.9s |
| status | degraded |
| final_route | graph |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | a4733d21-c2c6-46a0-b684-74aba97478e3 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
半夏秫米汤通过半夏降逆和胃、秫米养阴安中，调和脾胃、交通阴阳，使卫气循跷脉正常出入，从而治疗“阳不入阴”之失眠。与现代褪黑素调节昼夜节律、GABA受体激动剂抑制觉醒系统相比，该方侧重于从脾胃气机与阴阳通路层面整体调节“睡眠-觉醒节律”。

**配伍**  
半夏秫米汤仅半夏、秫米两味。半夏辛开降逆，能通泄阳明胃气，破除湿痰壅滞；秫米甘凉益阴，和胃安中，兼制半夏之燥。二者配伍，辛甘相合，通滞养阴，使中焦气机转枢得利，为阴阳交通创造通路。依据《本草纲目》记载，该方使用秫米以和阴养胃。

**病机**  
失眠“阳不入阴”与卫气循行、跷脉功能密切相关。卫气昼行阳经、夜行五脏，依赖跷脉（尤其是阴跷、阳跷）作为出入阴阳之门户。若脾胃失和、痰湿中阻，可致跷脉气机不畅，卫气夜间不能由阳入阴，出现“目不得瞑”。半夏秫米汤通过“交通阴阳，引阳入阴”（《近现代名医验案类编》），调和脾胃以疏通阴阳交通之路，使卫气循行复常。

**现代对接**  
1. **与褪黑素的对应**：褪黑素通过松果体分泌调节昼夜节律，类似中医“天人相应”中阳气入阴的时序调节。半夏秫米汤虽不直接补充褪黑素，但通过调和脾胃气机，可能影响中枢生物钟的同步性，改善节律失调型失眠。  
2. **与GABA受体激动剂的对应**：GABA受体激动剂通过抑制觉醒系统促进入睡，类似中医“潜阳入阴”中抑制阳亢、促进阴静的作用。半夏秫米汤中半夏的降逆化痰可能调节神经递质平衡，间接增强抑制性信号，但其作用途径更为整体，重在恢复阴阳出入的动态平衡。

**依据**  
1. 《本草纲目》指出半夏秫米汤使用秫米以和阴养胃。  
2. 《近现代名医验案类编》记载该方能“交通阴阳，引阳入阴”。  
3. 《医学衷中参西录》提及该方用于“目不得瞑”（失眠）。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 329-针灸神书/329-针灸神书_正文
- 013-本草纲目/013-本草纲目_正文
- 683-近现代名医验案类编/683-近现代名医验案类编_正文
- 584-医学衷中参西录/584-医学衷中参西录_正文
- 122-医方简义/122-医方简义_正文
- 360-徐批叶天士晚年方案真本/360-徐批叶天士晚年方案真本_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '329-针灸神书/329-针灸神书_正文', 'snippet': '气行者，麻。', 'score': 1.084, 'predicate': '常见症状', 'target': '麻', 'source_book': '329-针灸神书', 'source_chapter': '329-针灸神书_正文', 'evidence_path': 'chapter://针灸神书/329-针灸神书_正文', 'source_scope_path': 'book://针灸神书/*', 'anchor_entity': '气行'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目/013-本草纲目_正文', 'snippet': '置秫米一升', 'score': 1.084, 'predicate': '使用药材', 'target': '秫米', 'source_book': '013-本草纲目', 'source_chapter': '013-本草纲目_正文', 'evidence_path': 'chapter://本草纲目/013-本草纲目_正文', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编/683-近现代名医验案类编_正文', 'snippet': '半夏秫米汤交通阴阳，引阳入阴', 'score': 1.084, 'predicate': '功效', 'target': '交通阴阳，引阳入阴', 'source_book': '683-近现代名医验案类编', 'source_chapter': '683-近现代名医验案类编_正文', 'evidence_path': 'chapter://近现代名医验案类编/683-近现代名医验案类编_正文', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '半夏秫米汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=trace-graph-path; path=symptom://失眠/syndrome_chain; reason=用户需要从卫气循行与跷脉关系分析方剂原理，需先获取失眠到证候的辨证链，以建立病理机制基础。', 'skill': 'trace-graph-path'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://半夏秫米汤/功效; reason=在获取辨证链后，需明确半夏秫米汤的‘通阴阳’功效，为后续与现代药物的比较提供核心依据。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=compare-formulas; path=entity://半夏秫米汤/*; reason=用户需要比较半夏秫米汤与现代药物在调节节律上的机制，先获取半夏秫米汤的详细证据（如功效、配伍）以支持比较。', 'skill': 'compare-formulas'}
- {'stage': 'search_evidence_text', 'label': '补充文本检索', 'detail': 'round=2; action=2; skill=search-source-text; path=book://HERB2/*; reason=为比较提供现代药物在调节睡眠-觉醒节律方面的证据，补充西医机制信息。', 'skill': 'search-source-text'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=2'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=degraded
- list_evidence_paths: count=16
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- search_evidence_text: status=empty
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- deep_round_4:coverage_sufficient


## q09 胸痹三方与冠心病分层

**题目**

张仲景《金匮要略·胸痹心痛短气病脉证治》中，栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方均治胸痹，但用药有从“辛温通阳”到“理气化痰”再到“破气逐饮”的递进。请从“阳气不通—痰浊壅盛—饮邪结聚”的病机演变，论证三方证的阶梯性差异，并说明现代冠心病（稳定型心绞痛、不稳定型心绞痛、急性心肌梗死）可如何参照此辨证体系。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 71.1s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 184.7s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 71.1s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | e41bf3fd-d7c0-4bbf-a585-388c39242c18 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机演变与三方证的阶梯性差异**

从“阳气不通”到“痰浊壅盛”再到“饮邪结聚”，三方证呈现了胸痹病机由浅入深、由气及痰饮的阶梯性演变。

1.  **栝楼薤白白酒汤证（阳气不通）**：此为胸痹的基础证型，核心病机为胸阳不振，阳气痹阻不通。方中以栝楼实宽胸涤痰，薤白辛温通阳、行气导滞，白酒（现多用黄酒或米酒）轻扬上行以助药势，共奏宣痹通阳之效。其证以胸背痛、喘息咳唾、短气为主，痰浊未盛。

2.  **栝楼薤白半夏汤证（痰浊壅盛）**：此证在胸阳不振的基础上，痰浊壅盛的程度加重。病机已从单纯的“阳气不通”发展为“痰浊壅盛”，痹阻更甚。相较于前方，本方增加了半夏，旨在增强燥湿化痰、降逆散结之力，以应对痰浊壅塞、胸阳被遏更重的情况，症见胸痹不得卧、心痛彻背等。

3.  **枳实薤白桂枝汤证（饮邪结聚）**：此证病机进一步深化，不仅有痰浊，更兼有“饮邪结聚”或“气滞痰阻”结于胸中，病势更实。方中不仅用栝楼、薤白，更增入枳实、厚朴以破气除满、消痞散结，桂枝则通阳平冲。其证可见胸满、胁下逆抢心等气机壅滞、冲逆明显的症状，病位涉及胸胁，病势更为急迫。

**现代冠心病对接此辨证体系的参照**

张仲景的这一辨证体系，为现代冠心病的辨证论治提供了清晰的阶梯框架，可与疾病的不同阶段及严重程度相参照。

*   **稳定型心绞痛**：多对应于**栝楼薤白白酒汤证**或轻度的**栝楼薤白半夏汤证**。其病机以胸阳不振、痰瘀初结为主，病情相对稳定，疼痛发作有规律。治疗重在宣通胸阳，辅以化痰活血。
*   **不稳定型心绞痛**：多与**栝楼薤白半夏汤证**或**枳实薤白桂枝汤证**更为契合。此阶段痰浊、血瘀、气滞交织，痹阻心脉的程度加重，病情不稳定，易于进展。治疗需在通阳基础上，加强化痰散结（如用半夏）、理气破滞（如用枳实、厚朴）之力。
*   **急性心肌梗死**：常属胸痹重症，病机多属痰浊、瘀血、寒凝等实邪**闭阻心脉**，可参照**枳实薤白桂枝汤证**中“饮邪结聚”、“气机壅逆”的病机特点，但邪实更甚，常需在此类方基础上合用活血化瘀、芳香温通甚至回阳救逆之品，并必须结合现代医学急救手段。

**依据**：
1. 《证治汇补》记载薤白半夏汤（即栝楼薤白半夏汤类方）用于治疗“食痹”，体现了其治疗痰气交阻所致痹痛的应用。
2. 相关古籍对栝楼（栝蒌）药用部位的辨析，佐证了其在胸痹方中涤痰散结的核心作用。

---
🚨 **重要医疗声明**：您提及的情况涉及需要专业医疗判断的高风险场景。本系统仅提供中医历史文献知识，无法替代执业医师的诊断与治疗方案。请立即就医或拨打急救电话，不要仅依靠本工具的信息做出医疗决策。

**依据来源**

- 289-证治汇补/289-证治汇补_正文
- 药征续编/辨误
- 118-增订医方歌诀/攻下之剂
- 473-伤寒证治准绳/一身尽痛为湿
- 633-证治准绳·伤寒/一身尽痛为湿
- 642-订正仲景全书金匮要略注/正误

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '289-证治汇补/289-证治汇补_正文', 'snippet': '薤白半夏汤治之', 'score': 1.084, 'predicate': '治疗疾病', 'target': '食痹', 'source_book': '289-证治汇补', 'source_chapter': '289-证治汇补_正文', 'evidence_path': 'chapter://证治汇补/289-证治汇补_正文', 'source_scope_path': 'book://证治汇补/*', 'anchor_entity': '薤白半夏汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'doc', 'source': '078-药征续编.txt#10', 'snippet': '古籍：药征续编\n篇名：辨误\n属性：《尔雅》曰∶果 之实栝蒌。郭璞曰∶今齐人呼之为天瓜。李巡曰∶栝蒌子名也。据此说，则根名果 ，子名栝蒌。凡仲景之方，栝蒌桂枝汤，栝蒌瞿麦丸，柴胡去半夏加栝蒌汤，及牡蛎泽泻散，柴胡桂枝干姜汤二方内，栝蒌皆当作果 。若作栝蒌，则当须加根字。不然，与子相混，不可不改焉。又小陷胸汤，瓜蒌薤白白酒汤，瓜蒌薤白半夏汤，枳实薤白桂枝汤方内，瓜蒌实皆当作栝蒌也，实字当削之。李时珍曰∶栝蒌即果 二字音转也，亦作KT，后人又转为瓜蒌，愈转愈失其真矣。时珍之说非也，栝蒌决非果 音转也，《尔雅》岂以音转注之乎？瓜蒌 KT ，后世假栝蒌之音者也。 KT 本见《灵枢经》，盖俗字，误见于经，', 'match_snippet': '古籍：药征续编\n篇名：辨误\n属性：《尔雅》曰∶果 之实栝蒌。郭璞曰∶今齐人呼之为天瓜。李巡曰∶栝蒌子名也。据此说，则根名果 ，子名栝蒌。凡仲景之方，栝蒌桂枝汤...', 'score': None, 'source_file': '078-药征续编.txt', 'source_page': 10, 'file_path': 'classic://药征续编/0010-01', 'source_book': '药征续编', 'source_chapter': '辨误', 'evidence_path': 'chapter://药征续编/辨误', 'source_scope_path': 'book://药征续编/*'}
- {'evidence_type': 'factual_grounding', 'source_type': 'doc', 'source': '118-增订医方歌诀.txt#4', 'snippet': '古籍：增订医方歌诀\n篇名：攻下之剂\n属性：海蛤散（许叔微《普济本事方》）治血结胸，（治妇人伤寒血结胸膈，痛不可近者。陶节庵大便（每服二中；\n鸡子清调服，则不伤肺胃之阴，允为伤寒邪热炽络，血痹着上焦之良治。王海藏治血结胸，有桂枝红花汤加海蛤、桃仁，原欲表里上下一齐尽解之意，然总不如此方之妙。）结胸灸法（许叔微《普济本事方》）诚良妙，巴豆（十四枚）黄连（大者七寸）和成膏，填入脐心用艾灸，腹中鸣响结胸消。（上药为末，水调和，填入脐心，以艾灸其上，腹中有声，其病去矣。不拘壮数，病退为度。才灸了，便以温汤浸手帕拭之，恐生疮也。此法稳妙，凡胸中病，俱可根据此为治。）十枣汤（张仲景《金匮要略》）用芫（花）遂', 'match_snippet': '古籍：增订医方歌诀\n篇名：攻下之剂\n属性：海蛤散（许叔微《普济本事方》）治血结胸，（治妇人伤寒血结胸膈，痛不可近者。陶节庵大便（每服二中；\n鸡子清调服，则不伤肺胃之阴，允为伤寒邪热炽络，血痹着上焦之良治。王海藏治血结胸...', 'score': None, 'source_file': '118-增订医方歌诀.txt', 'source_page': 4, 'file_path': 'classic://增订医方歌诀/0004-01', 'source_book': '118-增订医方歌诀', 'source_chapter': '攻下之剂', 'evidence_path': 'chapter://增订医方歌诀/攻下之剂', 'source_scope_path': 'book://增订医方歌诀/*'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning,comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=path_reasoning,comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=27
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- quick_followup_remaining_gaps:path_reasoning,comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 184.7s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | efa124ba-0ddb-489d-ac9f-7627b5a9e8e2 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机演变与三方证的阶梯性差异**

**阳气不通（栝楼薤白白酒汤证）**：此方为胸痹基础证，核心病机在于胸中阳气痹阻不通。方中以薤白、白酒辛温通阳，宣痹散结，栝楼宽胸涤痰，共奏“泄胸中痹气”之效，针对以胸闷、短气为主的轻证。

**痰浊壅盛（栝楼薤白半夏汤证）**：此证在阳气不通基础上，痰浊之邪明显壅盛。其病机演进为痰浊痹阻更甚，临床可见胸痛加剧，或伴见“食痹”（即因痰湿中阻影响饮食）等症。故于前方基础上加半夏，增强化痰降逆、消痞散结之力，侧重“理气化痰”。

**饮邪结聚（枳实薤白桂枝汤证）**：此证病机进一步加重，由痰浊凝滞发展为“饮邪结聚”，气机壅滞更为严重，病位可由胸中扩展到胁下，出现心中痞、胁下逆抢心等症。方中用枳实破气消积、桂枝通阳平冲，重在“破气逐饮”，攻逐结聚之邪。

**现代冠心病辨证参照**

此三方证的病机递进，可为现代冠心病不同临床阶段的中医辨证提供重要参照。
*   **稳定型心绞痛**：其病机多对应于“阳气不通”或兼有轻度“痰浊”，可参照栝楼薤白白酒汤或栝楼薤白半夏汤的证治思路，以通阳宣痹、化痰散结为主。
*   **不稳定型心绞痛**：其病机常属“痰浊壅盛”或初现“饮邪结聚”之象，疼痛更为显著且不稳定。可重点参照栝楼薤白半夏汤加强化痰，或参照枳实薤白桂枝汤思路，适当加入破气除痞、通阳逐饮之品。
*   **急性心肌梗死**：其病机多属“痰浊”、“饮邪”与“瘀血”互结，痹阻心脉甚则阳气暴脱，证情危重。在“饮邪结聚”的枳实薤白桂枝汤证基础上，必须结合活血化瘀、回阳救逆等法进行急救与综合治疗。

依据：
1. 《本经逢原》指出栝楼薤白白酒汤能“泄胸中痹气”，对应阳气不通之机。
2. 《证治汇补》记载栝楼薤白半夏汤可治“食痹”，体现其痰浊壅盛、影响中焦的病机特点。
3. 《高注金匮要略》明示枳实薤白桂枝汤使用“枳实”等药，其“破气”之功正是针对饮邪结聚、气机严重壅滞之证。

---
🚨 **重要医疗声明**：您提及的情况涉及需要专业医疗判断的高风险场景。本系统仅提供中医历史文献知识，无法替代执业医师的诊断与治疗方案。请立即就医或拨打急救电话，不要仅依靠本工具的信息做出医疗决策。

**依据来源**

- 019-本经逢原/019-本经逢原_正文
- 515-高注金匮要略/515-高注金匮要略_正文
- 289-证治汇补/289-证治汇补_正文
- 中医临证经验与方法/中医临证经验与方法
- 中国医籍考/方论（二）
- 047-药征/047-药征_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '019-本经逢原/019-本经逢原_正文', 'snippet': '薤白白酒汤专用以泄胸中痹气也', 'score': 1.084, 'predicate': '功效', 'target': '泄胸中痹气', 'source_book': '019-本经逢原', 'source_chapter': '019-本经逢原_正文', 'evidence_path': 'chapter://本经逢原/019-本经逢原_正文', 'source_scope_path': 'book://本经逢原/*', 'anchor_entity': '栝楼薤白白酒汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '515-高注金匮要略/515-高注金匮要略_正文', 'snippet': '枳实（四枚） 薤白（半斤） 桂枝（一两） 浓朴（四两） 栝蒌实（一枚捣）', 'score': 1.084, 'predicate': '使用药材', 'target': '枳实', 'source_book': '515-高注金匮要略', 'source_chapter': '515-高注金匮要略_正文', 'evidence_path': 'chapter://高注金匮要略/515-高注金匮要略_正文', 'source_scope_path': 'book://高注金匮要略/*', 'anchor_entity': '枳实薤白桂枝汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '289-证治汇补/289-证治汇补_正文', 'snippet': '薤白半夏汤治之', 'score': 1.084, 'predicate': '治疗疾病', 'target': '食痹', 'source_book': '289-证治汇补', 'source_chapter': '289-证治汇补_正文', 'evidence_path': 'chapter://证治汇补/289-证治汇补_正文', 'source_scope_path': 'book://证治汇补/*', 'anchor_entity': '栝楼薤白半夏汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://栝楼薤白半夏汤/*; reason=获取第一个比较对象（栝楼薤白半夏汤）的核心证据，如功效、主治，以支持病机分析。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://枳实薤白桂枝汤/*; reason=获取第二个比较对象（枳实薤白桂枝汤）的核心证据，以对比三方阶梯性差异。', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=symptom://胸痹/syndrome_chain; reason=需要获取从症状到证候的病机演变路径，以支持三方阶梯性差异的论证。', 'skill': 'trace-graph-path'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=2; skill=read-syndrome-treatment; path=entity://栝楼薤白白酒汤/功效; reason=问题涉及三方比较，但当前证据缺少栝楼薤白白酒汤的核心功效信息，需补充以完成完整对比。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=2'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=27
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- search_evidence_text: status=ok

**备注**

- deep_round_4:no_new_evidence


## q10 四逆散与三类厥冷鉴别

**题目**

《伤寒论》四逆散（甘草、枳实、柴胡、芍药）被后世视为“疏肝理气之祖”，但其原条文主治“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。请从“阳郁于里”而非“阳虚”的角度，解释四逆散证“四逆”的病理机制，并论述其与四逆汤证、当归四逆汤证在手足逆冷上的鉴别要点，以及为何方中不用附子、干姜而用柴胡、枳实。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | degraded | graph | grounded_llm | 48.0s | 6 | 0 |
| deep | degraded | graph | planner_llm | 113.1s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 48.0s |
| status | degraded |
| final_route | graph |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 0e0359d1-c244-462c-99df-1056a0bb219d |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**主治**
四逆散主治少阴病，见四肢逆冷，并伴有或咳、或悸、或小便不利、或腹中痛、或泄利下重等或然症。其核心病机并非少阴阳虚，而是阳气内郁，不能通达四肢所致。

**病机**
四逆散证的“四逆”（手足逆冷），其病理机制关键在于“阳郁于里”。此证并非阳气虚衰，而是由于气机郁滞（尤其是肝气郁结），导致阳气被郁遏在体内，不能外达于四肢末梢，从而出现手足不温的“热厥”表现。依据《景岳全书》所述，此为“阳邪亢盛，血脉不通而四肢厥逆者，谓之热厥”。方中不用附子、干姜等大辛大热之药回阳救逆，而选用柴胡疏肝解郁、透达阳气，枳实行气破结、宣通郁滞，正是针对“阳郁”这一核心病机，使气机调畅，郁阳得伸，则四肢自温。

**鉴别**
四逆散证、四逆汤证与当归四逆汤证在手足逆冷上的鉴别要点如下：
1.  **四逆散证**：属“阳郁厥逆”。手足冷程度相对较轻，多不过腕踝，且胸胁脘腹常有胀闷不舒等气郁症状，其本质为热郁于内，故舌象、脉象多无明显虚寒之象。
2.  **四逆汤证**：属“阳虚寒盛厥逆”。因少阴阳气衰微，阴寒内盛所致。手足逆冷严重，常冷过肘膝，全身伴有一派虚寒征象，如畏寒蜷卧、下利清谷、脉微欲绝等。
3.  **当归四逆汤证**：属“血虚寒凝厥逆”。因营血不足，复感寒邪，寒凝经脉，气血运行不畅所致。手足厥寒多伴有麻木、疼痛，或青紫，但全身无明显的阳虚阴盛之里寒证，脉象细涩。

依据：
1. 《伤寒论纲目》载四逆散主治“少阴病。四逆。其人或咳。或悸。或小便不利。或腹中痛。或泄利下重者”。
2. 《景岳全书》指出，若“阳邪亢盛，血脉不通而四肢厥逆者，谓之热厥，宜四逆散”。

**依据来源**

- 303-李翰卿/303-李翰卿_正文
- 609-伤寒论纲目/609-伤寒论纲目_正文
- 089-医方论/089-医方论_正文
- 637-景岳全书/637-景岳全书_正文
- 682-戴丽三医疗经验选/682-戴丽三医疗经验选_正文
- 596-医学摘粹/596-医学摘粹_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '303-李翰卿/303-李翰卿_正文', 'snippet': '甘草有和胃、解毒、泻火、补中等功用', 'score': 1.084, 'predicate': '功效', 'target': '解毒', 'source_book': '303-李翰卿', 'source_chapter': '303-李翰卿_正文', 'evidence_path': 'chapter://李翰卿/303-李翰卿_正文', 'source_scope_path': 'book://李翰卿/*', 'anchor_entity': '甘草'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '609-伤寒论纲目/609-伤寒论纲目_正文', 'snippet': '少阴病。四逆。其人或咳。或悸。或小便不利。或腹中痛。或泄利下重者。四逆散主之。', 'score': 1.084, 'predicate': '治疗症状', 'target': '四逆', 'source_book': '609-伤寒论纲目', 'source_chapter': '609-伤寒论纲目_正文', 'evidence_path': 'chapter://伤寒论纲目/609-伤寒论纲目_正文', 'source_scope_path': 'book://伤寒论纲目/*', 'anchor_entity': '四逆散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '柴胡八两 半夏半升 人参 甘草 黄芩 生姜三两 大枣十二枚', 'score': 1.0321, 'predicate': '使用药材', 'target': '小柴胡汤', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '甘草'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=origin,source_trace,comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=origin,source_trace,comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=degraded
- list_evidence_paths: count=128
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- quick_followup_remaining_gaps:comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 113.1s |
| status | degraded |
| final_route | graph |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | 95217217-cf0f-4915-b59b-ff9174cdb1b8 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**主治**
四逆散在《伤寒论》中主治“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。（依据《伤寒论纲目》）

**病机**
四逆散证的“四逆”（手足逆冷），其核心病机是“阳郁于里”，而非阳气虚衰。具体而言，是由于气机郁滞，特别是肝气郁结，导致阳气被郁遏在体内，不能通达于四肢末端，从而出现手足不温。这种“热厥”是阳邪亢盛、血脉不通所致（依据《景岳全书》）。方中不用附子、干姜等大辛大热之药来回阳救逆，正是因为其根本并非阳虚。相反，选用柴胡是为了疏达郁结的阳邪，用枳实是为了散结泄热，两者配合使郁滞的气机得以宣通，被郁遏的阳气得以外达，则手足自然转温（依据《医方论》）。

**鉴别**
四逆散证、四逆汤证与当归四逆汤证均可见手足逆冷，但病因病机与治法迥异：
1.  **四逆散证**：属“热厥”或“气厥”。病机为阳气内郁，气机不畅。手足冷程度相对较轻，常伴有胸胁胀闷、腹痛、泄利下重等气郁症状。治宜透邪解郁，疏肝理脾。
2.  **四逆汤证**：属“寒厥”。病机为少阴阳气衰微，阴寒内盛。手足厥冷程度严重，常伴有畏寒蜷卧、下利清谷、脉微欲绝等全身虚寒征象。治宜回阳救逆（依据《经方实验录》提及四逆汤证）。
3.  **当归四逆汤证**：属“血虚寒厥”。病机为营血虚弱，寒凝经脉。手足厥寒，并可伴有肢体疼痛、舌淡苔白、脉细等血虚血寒之象。治宜温经散寒，养血通脉（依据《章次公医案》提及当归四逆汤证）。

**依据**：
1. 《医方论》指出四逆散“用枳实以散郁热，仍用柴胡以达阳邪，阳邪外泄，则手足自温矣”。
2. 《景岳全书》将四逆散所治四肢厥逆明确归类为“热厥”。
3. 《伤寒论纲目》摘录了四逆散主治的原文。

**依据来源**

- 089-医方论/089-医方论_正文
- 679-章次公医案/679-章次公医案_正文
- 672-经方实验录/672-经方实验录_正文
- 367-临证指南医案/367-临证指南医案_正文
- 609-伤寒论纲目/609-伤寒论纲目_正文
- 637-景岳全书/637-景岳全书_正文

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论/089-医方论_正文', 'snippet': '四逆散乃表里并治之剂。故但用枳实以散郁热，仍用柴胡以达阳邪，阳邪外泄，则手足自温矣', 'score': 1.084, 'predicate': '功效', 'target': '表里并治，散郁热，达阳邪', 'source_book': '089-医方论', 'source_chapter': '089-医方论_正文', 'evidence_path': 'chapter://医方论/089-医方论_正文', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '四逆散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '679-章次公医案/679-章次公医案_正文', 'snippet': '盖当归四逆汤证也', 'score': 1.084, 'predicate': '治疗证候', 'target': '当归四逆汤', 'source_book': '679-章次公医案', 'source_chapter': '679-章次公医案_正文', 'evidence_path': 'chapter://章次公医案/679-章次公医案_正文', 'source_scope_path': 'book://章次公医案/*', 'anchor_entity': '当归四逆汤证'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '672-经方实验录/672-经方实验录_正文', 'snippet': '所犯为四逆汤证，则投以四逆汤', 'score': 1.084, 'predicate': '治疗证候', 'target': '四逆汤', 'source_book': '672-经方实验录', 'source_chapter': '672-经方实验录_正文', 'evidence_path': 'chapter://经方实验录/672-经方实验录_正文', 'source_scope_path': 'book://经方实验录/*', 'anchor_entity': '四逆汤证'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=origin,source_trace,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=read-formula-origin; path=book://伤寒论纲目/*; reason=已具备可读书目/章节路径，直接追出处原文或条文', 'skill': 'read-formula-origin'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-formula-origin; path=entity://四逆散/*; reason=先获取四逆散在《伤寒论》中的原始出处和条文，为解释‘阳郁于里’的病理机制提供文献基础。', 'skill': 'read-formula-origin'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=compare-formulas; path=entity://四逆散/*; reason=获取四逆散核心证据，为比较做准备', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=2; skill=compare-formulas; path=entity://四逆汤证/*; reason=获取四逆汤证证据，用于手足逆冷鉴别', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=1'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=degraded
- list_evidence_paths: count=128
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_limit_reached
