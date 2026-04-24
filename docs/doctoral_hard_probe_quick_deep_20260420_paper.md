# 博士级中医难题 Quick/Deep 评测报告

## 评测概览

| 字段 | 值 |
| --- | --- |
| generated_at | 2026-04-20 17:00:14 +0800 |
| backend_url | http://127.0.0.1:8002 |
| source | live_http_eval |
| topic_kept_in_output_only | yes |
| top_k | 12 |
| total_questions | 10 |
| quick_ok | 10 |
| deep_ok | 10 |
| quick_avg_latency | 51.8s |
| deep_avg_latency | 82.8s |

## 按题目总览

| ID | Topic | Quick 路由/后端 | Quick 工具/回退 | Quick 延迟 | Deep 路由/后端 | Deep 工具/回退 | Deep 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q01 | 小柴胡汤少阳咳加减 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 58.8s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 62.0s |
| q02 | 小建中汤寒热并治 | graph / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path / fb=no | 40.9s | graph / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 61.9s |
| q03 | 升阳益胃汤风药与黄连 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 38.3s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 50.7s |
| q04 | 宣痹汤与白虎加桂枝汤 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 57.0s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path / fb=no | 105.5s |
| q05 | 久病入络与虫类药阶梯 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 41.2s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 79.6s |
| q06 | 2024甲辰年五运六气 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 72.6s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 83.3s |
| q07 | 黄芪托毒生肌与免疫 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 54.2s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path / fb=no | 127.2s |
| q08 | 半夏秫米汤与睡眠节律 | graph / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path / fb=no | 38.1s | graph / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 76.2s |
| q09 | 胸痹三方与冠心病分层 | hybrid / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text / fb=no | 70.5s | hybrid / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path / fb=no | 109.9s |
| q10 | 四逆散与三类厥冷鉴别 | graph / grounded_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path / fb=no | 46.4s | graph / planner_llm | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path / fb=no | 71.4s |

## q01 小柴胡汤少阳咳加减

**题目**

《伤寒论》第96条小柴胡汤方后注“若咳者，去人参、大枣、生姜，加五味子半升、干姜二两”。请从小柴胡汤“和解少阳”的基本结构出发，分析“去人参”与“加干姜、五味子”之间的药性矛盾与统一，并论述此加减法对后世治疗“少阳咳”的指导意义（如与柴胡桂枝干姜汤证的咳嗽如何鉴别）。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 58.8s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 62.0s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 58.8s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | d46b86a3-7caa-4103-9a89-3fb1955b50a5 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论：** 从小柴胡汤“和解少阳”的基本结构分析，第96条方后注中“去人参”与“加干姜、五味子”的加减法，体现了在少阳枢机不利基础上，针对寒饮犯肺之咳的灵活变通。二者在药性上看似矛盾（人参补气易壅滞，干姜辛热温化寒饮），实则统一于“和解少阳，温化寒饮”的治法中，共同服务于“少阳咳”病机。

**依据：**
1. 小柴胡汤的核心功能是和解少阳，主治少阳经半表半里证（依据：《删补名医方论》指出小柴胡汤治疗“少阳经半表半里证”）。
2. 加减法中，去人参、大枣是防其甘壅助湿碍气，不利于咳嗽的宣降；加干姜、五味子则是取“干姜温肺散寒以化饮，五味子敛肺止咳”之意，二者一散一收，针对寒饮咳嗽。

### 鉴别
**小柴胡汤去参加干姜五味子证（少阳咳）与柴胡桂枝干姜汤证的咳嗽鉴别：**
*   **病机核心：**
    *   **小柴胡汤去参加干姜五味子证**：病机重心仍在**少阳枢机不利**，但兼有**寒饮犯肺**。咳嗽是因少阳三焦气机不畅，影响肺气宣降，加之寒饮内停于肺所致。其证应有少阳主证（如往来寒热、胸胁苦满等）并见咳嗽，痰多清稀。
    *   **柴胡桂枝干姜汤证**：病机为**少阳枢机不利兼水饮内结**，且往往有**阴伤**之象（如口渴、心烦）。其咳嗽是水饮停聚，上逆犯肺所致，常伴见小便不利、渴而不呕等水饮内停表现。方中用桂枝、干姜温化水饮，栝楼根生津止渴，牡蛎软坚散结，整体偏于温化水饮、和解少阳。
*   **治法与用药：**
    *   **小柴胡汤加减法**：在和解少阳（柴胡、黄芩）的基础上，**专去壅补之人参、大枣**，**加干姜、五味子**直接温肺化饮、敛肺止咳，是针对肺脏寒饮的局部强化治疗。
    *   **柴胡桂枝干姜汤**：和解少阳（柴胡、黄芩）的同时，用**桂枝配干姜**通阳化气以温散全身水饮，用**栝楼根、牡蛎**兼顾津伤与邪结，是治疗少阳病兼水饮内结、津液受损的复合方剂，其治咳是通过整体温化水饮实现。

### 指导意义
此加减法对后世治疗“少阳咳”的指导意义在于：
1.  **确立了“和解少阳，兼治肺咳”的治法范例**：明确指出治疗少阳病兼咳嗽时，应在和解少阳主方基础上，根据咳嗽的寒热虚实性质进行针对性加减，不可固守原方。
2.  **揭示了“去壅补，加温敛”的用药规律**：为少阳病兼寒饮咳嗽提供了具体的药物调整思路，即减去可能助湿碍气的人参、大枣等甘味壅补之品，加入干姜、五味子这类温化寒饮、宣敛肺气的药对。后世治疗肝肺气逆或邪犯少阳的咳嗽，常借鉴此法，在疏解少阳的同时，配合温肺、敛肺之品。
3.  **启发了对“少阳-三焦-肺”通路关系的认识**：此加减法体现了少阳三焦气机不畅可直接影响肺气宣降，治疗需两者兼顾，丰富了脏腑相关理论在临床中的应用。

**依据：**
1. 《删补名医方论》指出小柴胡汤主治“少阳经半表半里证”。
2. 《医方论》等后世方书载有小柴胡汤及其加减方，体现了其作为和解剂基础方的灵活运用。
3. 加减法本身出自《伤寒论》第96条方后注，是仲景辨证论治思想的直接体现。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 253-青囊秘诀/None
- 089-医方论/None
- 151-女科撮要/None
- 639-删补名医方论/None
- 279-疠疡机要/None
- 168-保婴撮要/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '253-青囊秘诀', 'snippet': '柴胡（二钱）', 'score': 1.084, 'predicate': '使用药材', 'target': '柴胡', 'source_book': '253-青囊秘诀', 'source_chapter': None, 'evidence_path': 'book://青囊秘诀/*', 'source_scope_path': 'book://青囊秘诀/*', 'anchor_entity': '加味小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '柴胡八两 半夏半升 人参 甘草 黄芩 生姜三两 大枣十二枚', 'score': 1.084, 'predicate': '使用药材', 'target': '柴胡', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '151-女科撮要', 'snippet': '肝经怒火者，加味小柴胡汤', 'score': 1.0046, 'predicate': '治疗证候', 'target': '肝经怒火', 'source_book': '151-女科撮要', 'source_chapter': None, 'evidence_path': 'book://女科撮要/*', 'source_scope_path': 'book://女科撮要/*', 'anchor_entity': '加味小柴胡汤'}

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
- list_evidence_paths: count=37
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- quick_followup_remaining_gaps:comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 62.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 71486fca-7c04-4edb-8866-0ddaf668f6bb |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**
从小柴胡汤“和解少阳”的基本结构分析，第96条方后注中“去人参”与“加干姜、五味子”的加减法，表面存在药性矛盾，实则统一于“少阳病兼咳”这一特定病机，旨在调整方剂重心，从扶正祛邪转为温化寒饮、敛肺止咳。这一治法对后世辨治“少阳咳”具有核心指导意义。

**一、药性矛盾与统一的机理分析**
小柴胡汤的基本结构以柴胡、黄芩和解少阳半表半里之邪为主，佐以人参、大枣、生姜、甘草（即“姜枣草参”）扶助脾胃之气，构成“和解之中兼扶正”的格局。当少阳病出现咳嗽时，此咳多因寒饮犯肺所致。
1.  **“去人参”的矛盾与统一**：人参性甘温，长于补气，但恐其壅补助湿，不利于寒饮的宣化。此为矛盾点。其统一性在于，减去人参是为了避免恋邪碍湿，使方剂力量更专注于宣散少阳之邪与温化肺中寒饮。
2.  **“加干姜、五味子”的矛盾与统一**：干姜辛热，温肺化饮；五味子酸温，敛肺止咳。二者一散一收，看似与小柴胡汤和解疏泄之性相悖。实则统一于“病机针对”。加干姜是取代生姜，增强温化肺中寒饮之力；加五味子则是针对咳嗽这一主症，收敛肺气。二者协同，专为治疗寒饮射肺之咳而设，是和解少阳框架下的对症强化。

**二、对后世治疗“少阳咳”的指导意义**
此加减法确立了治疗“少阳枢机不利，兼有寒饮犯肺”型咳嗽的基本范式，即：**在和解少阳（柴胡、黄芩）的基础上，去甘壅之品，加用温化（干姜）与收敛（五味子）以治咳**。这提示后世，少阳病见咳，需细辨有无水饮内停，不可一味疏解，当根据兼夹病机灵活调整方药组合。

**三、与柴胡桂枝干姜汤证咳嗽的鉴别**
两者虽均属少阳病范畴且都可能出现咳嗽，但病机、主证及方药结构有明确区别：
1.  **小柴胡汤去参枣姜加干姜五味子证**：其咳嗽的核心病机是**少阳不和，兼肺有寒饮**。病位侧重在少阳与肺。方剂以和解少阳为基础，加减专为治咳，整体仍以祛邪为主。
2.  **柴胡桂枝干姜汤证**：其病机为**少阳枢机不利，兼有水饮内结、气化失常**（据《医宗金鉴》载，主治“少阳表里未解之证”）。病位涉及少阳、三焦，常伴见小便不利、渴而不呕、胸胁满微结等水饮内停之象。方中用干姜（据《伤寒贯珠集》等载），是与桂枝、牡蛎、天花粉等配伍，旨在温化水饮、通阳散结，其治咳是解决水饮泛肺的结果，而非如前方直接针对肺气上逆。

**依据**：
1.  《医宗金鉴》指出柴胡桂枝干姜汤主治“少阳表里未解之证”，提示其病机兼夹水饮内结。
2.  《伤寒贯珠集》等文献记载柴胡桂枝干姜汤中使用干姜，其配伍目的在于温化水饮。
3.  《删补名医方论》等指出小柴胡汤主治“少阳经半表半里证”，此为两方共同的病理基础，但兼证不同决定了加减法的差异。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 479-伤寒贯珠集/None
- 089-医方论/None
- 575-医宗金鉴/None
- 639-删补名医方论/None
- 609-伤寒论纲目/None
- 072-医方考/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '479-伤寒贯珠集', 'snippet': '干姜（二两）', 'score': 1.084, 'predicate': '使用药材', 'target': '干姜', 'source_book': '479-伤寒贯珠集', 'source_chapter': None, 'evidence_path': 'book://伤寒贯珠集/*', 'source_scope_path': 'book://伤寒贯珠集/*', 'anchor_entity': '柴胡桂枝干姜汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '柴胡八两 半夏半升 人参 甘草 黄芩 生姜三两 大枣十二枚', 'score': 1.084, 'predicate': '使用药材', 'target': '柴胡', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小柴胡汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '575-医宗金鉴', 'snippet': '此为少阳表里未解之证，故主柴胡桂枝干姜汤', 'score': 0.9199, 'predicate': '治疗证候', 'target': '少阳表里未解之证', 'source_book': '575-医宗金鉴', 'source_chapter': None, 'evidence_path': 'book://医宗金鉴/*', 'source_scope_path': 'book://医宗金鉴/*', 'anchor_entity': '柴胡桂枝干姜汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://小柴胡汤/*; reason=获取小柴胡汤的核心证据，特别是其和解少阳的基本结构、组成和功效，为后续比较奠定基础。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://柴胡桂枝干姜汤/*; reason=获取柴胡桂枝干姜汤的核心证据，特别是其主治证候、组成和功效，以便与小柴胡汤的加减法进行鉴别。', 'skill': 'compare-formulas'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=37
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_1:coverage_sufficient


## q02 小建中汤寒热并治

**题目**

《金匮要略·血痹虚劳病脉证并治》云“虚劳里急，悸，衄，腹中痛，梦失精，四肢酸疼，手足烦热，咽干口燥，小建中汤主之”。小建中汤由桂枝汤倍芍药加饴糖组成，请从“酸甘化阴”与“辛甘化阳”两个相反的药性配伍角度，论证小建中汤何以同时治疗“里急腹痛”（寒象）与“手足烦热、咽干口燥”（热象），并辨析其与黄连阿胶汤在治疗“虚烦”上的病机界限。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | graph | grounded_llm | 40.9s | 6 | 0 |
| deep | ok | graph | planner_llm | 61.9s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 40.9s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path |
| fallback_detected | no |
| trace_id | caad18e2-77ab-44e4-a60f-c615ea7429e8 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**：小建中汤通过“辛甘化阳”与“酸甘化阴”的配伍，建立中气、调和阴阳，从而能同时治疗里急腹痛（寒象）与手足烦热、咽干口燥（热象）。其治疗“虚烦”的病机是阴阳两虚、寒热错杂，以中焦虚寒为本；而黄连阿胶汤主治阴虚火旺、心肾不交之虚烦，两者病机有本质区别。

**组成**
小建中汤由桂枝、芍药、生姜、大枣、甘草、饴糖组成。其核心是在桂枝汤（桂枝、芍药、生姜、大枣、甘草）基础上，倍用芍药，并加入大量饴糖。

**配伍**
1.  **辛甘化阳**：方中桂枝、生姜味辛，甘草、大枣、饴糖味甘，辛味与甘味药物相合，能化生阳气，温补中焦脾胃之虚寒。这针对了“虚劳里急，腹中痛”等中阳不足、筋脉失温的寒象。
2.  **酸甘化阴**：方中芍药味酸，甘草、大枣、饴糖味甘，酸味与甘味药物相合，能化生阴液，滋养营血，敛阴和营。这针对了“手足烦热，咽干口燥”等阴血亏虚、虚热内扰的热象。
通过这两种相反相成的配伍法，使本方既能温中补虚，又能益阴和血，从而达到调和阴阳、平补寒热的目的。

**病机**
本方主治的病机核心是**阴阳两虚，寒热错杂，而以中焦脾胃虚寒为本**。由于中焦虚寒，气血生化不足，导致阴阳俱虚。阳虚失温则见里急腹痛；阴虚失濡，虚热内生则见手足烦热、咽干口燥。其“虚烦”正是这种阴阳不调、虚热内扰的表现。全方重在建立中气，中气立则气血生化有源，阴阳得以调和。

**鉴别**
小建中汤与黄连阿胶汤虽均治“虚烦”，但病机界限分明：
*   **小建中汤**所治虚烦，病机为**阴阳两虚，寒热错杂**，症状上常伴有里急腹痛、喜温喜按等虚寒之象，其热为虚热。
*   **黄连阿胶汤**所治虚烦，病机为**阴虚火旺，心肾不交**，纯属热证，无寒象。其症以心中烦、不得卧为主，伴见舌红少苔、脉细数等真阴亏虚、心火独亢之象。

依据：
1. 《金匮翼》指出小建中汤主治“腹中急痛”。
2. 《未刻本叶氏医案》记载其功效为“两和气血”。
3. 《经方实验录》载其用于治疗“虚劳”。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 477-伤寒括要/None
- 205-金匮翼/None
- 380-未刻本叶氏医案/None
- 672-经方实验录/None
- 072-医方考/None
- 474-伤寒论注/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '477-伤寒括要', 'snippet': '小建中汤 属性：桂枝 甘草 大枣 芍药 生姜 胶饴', 'score': 1.084, 'predicate': '使用药材', 'target': '桂枝', 'source_book': '477-伤寒括要', 'source_chapter': None, 'evidence_path': 'book://伤寒括要/*', 'source_scope_path': 'book://伤寒括要/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '205-金匮翼', 'snippet': '法当腹中急痛，先与小建中汤', 'score': 0.8191, 'predicate': '治疗症状', 'target': '腹中急痛', 'source_book': '205-金匮翼', 'source_chapter': None, 'evidence_path': 'book://金匮翼/*', 'source_scope_path': 'book://金匮翼/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '380-未刻本叶氏医案', 'snippet': '小建中汤 属性：两和气血。', 'score': 0.7187, 'predicate': '功效', 'target': '两和气血', 'source_book': '380-未刻本叶氏医案', 'source_chapter': None, 'evidence_path': 'book://未刻本叶氏医案/*', 'source_scope_path': 'book://未刻本叶氏医案/*', 'anchor_entity': '小建中汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=1; gaps=path_reasoning'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=20
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 61.9s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | d214846c-2664-4a80-a41b-b10dd62b5404 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**：小建中汤通过“辛甘化阳”与“酸甘化阴”的配伍，建立中气、调和阴阳，从而能同时治疗虚劳病中寒热错杂的“里急腹痛”（中焦虚寒）与“手足烦热、咽干口燥”（虚热上扰）。其“虚烦”病机核心是中焦虚损、阴阳两虚失和，与黄连阿胶汤的肾阴亏虚、心火独亢所致“虚烦”有本质区别。

**组成**
小建中汤由桂枝、芍药、生姜、大枣、甘草、饴糖组成。其核心变化在于桂枝汤倍用芍药，并加入大量甘温的饴糖为君药。

**配伍**
1.  **辛甘化阳**：方中桂枝、生姜味辛，饴糖、大枣、甘草味甘。辛味药与甘味药相合，能化生、温通阳气。此配伍主要针对中焦虚寒所致的“虚劳里急，腹中痛”等寒象，通过温建中阳以散寒缓急。
2.  **酸甘化阴**：方中芍药味酸，饴糖、大枣、甘草味甘。酸味药与甘味药相合，能化生、敛养阴液。此配伍主要针对阴虚内热、虚阳浮越所致的“手足烦热，咽干口燥”等热象，通过滋养阴血以敛热除烦。
    二者相反相成，共奏建立中气、调和阴阳气血之效。正如《未刻本叶氏医案》指出其能“两和气血”，《医方论》亦言其能“抑木扶土”，正是通过调和肝脾（阴阳）来实现的。

**病机**
本方所治之证，病机关键在于中焦脾胃虚损，气血阴阳俱不足，导致阴阳失和、寒热错杂。具体而言：
*   “里急、腹中痛”是因中阳亏虚，失于温煦，筋脉拘急（虚寒）。
*   “手足烦热、咽干口燥”是因阴血亦虚，阴不制阳，虚热内生或浮越于外（虚热）。
*   “悸、衄、梦失精”亦是阴阳两虚、心神不宁、精关不固的表现。
小建中汤以甘温的饴糖为君，重在“建中”，即建立中焦脾胃之气。中气立，则气血生化有源，阴阳得以调和。其功效可概括为“补虚散邪”（《金匮翼》），此处的“散邪”实为调和内在阴阳之偏胜。

**鉴别**
小建中汤与黄连阿胶汤均治“虚烦”，但病机与治法迥异：
*   **小建中汤所治“虚烦”**：源于**中焦虚劳，阴阳两虚，失于调和**。其烦热是虚阳浮越或阴虚内热所致，常伴腹痛、心悸、神疲等中虚之象。治疗以**甘温建中，调和阴阳**为主。
*   **黄连阿胶汤所治“虚烦”**：源于**少阴病，肾水亏虚于下，心火亢盛于上**的心肾不交证。其烦热是实火（心火）与虚火（阴虚）交织，以心中烦、不得卧为主症，热象更明显。治疗以**滋阴降火，交通心肾**（黄连、黄芩清心火，阿胶、鸡子黄滋肾阴）为主。
    简言之，小建中汤治在中焦，属虚劳阴阳失和；黄连阿胶汤治在心肾，属阴虚火旺、水火不济。

**依据**：
1.  《未刻本叶氏医案》指出小建中汤能“两和气血”。
2.  《医方论》认为小建中汤有“抑木扶土”之效。
3.  《金匮翼》记载小建中汤可“补虚散邪”。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 380-未刻本叶氏医案/None
- 477-伤寒括要/None
- 089-医方论/None
- 205-金匮翼/None
- 461-注解伤寒论/None
- 682-戴丽三医疗经验选/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '380-未刻本叶氏医案', 'snippet': '小建中汤 属性：两和气血。', 'score': 1.084, 'predicate': '功效', 'target': '两和气血', 'source_book': '380-未刻本叶氏医案', 'source_chapter': None, 'evidence_path': 'book://未刻本叶氏医案/*', 'source_scope_path': 'book://未刻本叶氏医案/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '477-伤寒括要', 'snippet': '小建中汤 属性：桂枝 甘草 大枣 芍药 生姜 胶饴', 'score': 1.084, 'predicate': '使用药材', 'target': '桂枝', 'source_book': '477-伤寒括要', 'source_chapter': None, 'evidence_path': 'book://伤寒括要/*', 'source_scope_path': 'book://伤寒括要/*', 'anchor_entity': '小建中汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '小建中汤之义，全在抑木扶土', 'score': 0.6584, 'predicate': '功效', 'target': '抑木扶土', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '小建中汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=read-syndrome-treatment; path=entity://小建中汤/功效; reason=先获取小建中汤的核心功效，为后续从‘酸甘化阴’与‘辛甘化阳’角度分析其治疗寒热错杂的病机提供基础。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=trace-graph-path; path=entity://小建中汤/推荐证候; reason=获取小建中汤与具体证候（如虚劳里急、手足烦热等）的关联路径，以支持对寒热错杂病机的辨证链分析。', 'skill': 'trace-graph-path'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=20
- read_evidence_path: status=ok
- read_evidence_path: status=empty

**备注**

- deep_round_1:coverage_sufficient


## q03 升阳益胃汤风药与黄连

**题目**

李东垣《脾胃论》中“升阳益胃汤”由补中益气汤化裁而来，加入羌活、独活、防风、白芍、黄连、茯苓、泽泻等。请从“风药胜湿”与“升阳散火”两个学说，分析该方为何同时使用大量风药与苦寒之黄连，并论述其与“补中益气汤证”之间的虚实、燥湿转化关系。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 38.3s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 50.7s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 38.3s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 38ec6e21-3cb8-439f-9325-fdd317820f56 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**：升阳益胃汤在补中益气汤基础上，通过配伍大量风药与少量黄连，实现了“风药胜湿”以祛除脾胃湿邪、“升阳散火”以清解郁热的核心目的。其证候由补中益气汤证的单纯“气虚下陷”转化为“气虚湿盛兼有郁热”的虚实夹杂、燥湿并存状态。

**具体分析如下**：

**一、从“风药胜湿”学说分析**  
方中羌活、独活、防风等风药，性味辛散，能升发脾胃清阳之气，阳气升则湿邪自化。这针对的是脾胃气虚、运化失职后产生的内湿证候，风药通过升阳助脾运，达到“胜湿”效果。

**二、从“升阳散火”学说分析**  
少量黄连的苦寒之性，并非单纯清热，而是与大量风药及黄芪、人参等甘温补气药相配，意在“升阳散火”。即升发被湿郁遏的脾胃清阳，使郁热得以发散，黄连在此清解已成的郁热，防止温补、风药助热，构成“升阳”与“散火”并举的配伍。

**三、与“补中益气汤证”的虚实、燥湿转化关系**  
1. **虚实转化**：补中益气汤证以中气不足、清阳下陷为主，属虚证；升阳益胃汤证则在气虚基础上，兼有湿邪困阻、阳气郁遏化热的实邪，转为虚实夹杂。  
2. **燥湿转化**：补中益气汤证以气虚不运为主，燥湿矛盾不显；升阳益胃汤证因气虚生湿，湿郁化热，呈现“湿盛”与“郁热”并存的燥湿错杂局面。因此，治法由单纯“补中升阳”转为“升阳益胃、祛湿散火”。

**依据**：  
1. 《脾胃论》载升阳益胃汤具“升阳益胃”之功（出处：614-脾胃论/None）。  
2. 《医方考》记载升阳益胃汤使用泽泻等利湿之品（出处：072-医方考/None）。  
3. 《医方论》指出补中益气汤主治“中气不足”（出处：089-医方论/None）。

**依据来源**

- 433-六因条辨/None
- 072-医方考/None
- 614-脾胃论/None
- 089-医方论/None
- 132-女科证治准绳/None
- 082-古今名医方论/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '433-六因条辨', 'snippet': '补中益气汤：黄祗，人参，白术，当归，陈皮，炙甘草，柴胡，升麻', 'score': 1.084, 'predicate': '使用药材', 'target': '人参', 'source_book': '433-六因条辨', 'source_chapter': None, 'evidence_path': 'book://六因条辨/*', 'source_scope_path': 'book://六因条辨/*', 'anchor_entity': '补中益气汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '072-医方考', 'snippet': '升阳益胃汤 属性：泽泻', 'score': 1.084, 'predicate': '使用药材', 'target': '泽泻', 'source_book': '072-医方考', 'source_chapter': None, 'evidence_path': 'book://医方考/*', 'source_scope_path': 'book://医方考/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '614-脾胃论', 'snippet': '当升阳益胃，名之曰升阳益胃汤', 'score': 0.9161, 'predicate': '功效', 'target': '升阳益胃', 'source_book': '614-脾胃论', 'source_chapter': None, 'evidence_path': 'book://脾胃论/*', 'source_scope_path': 'book://脾胃论/*', 'anchor_entity': '升阳益胃汤'}

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
- list_evidence_paths: count=36
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 50.7s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | e8dcc75e-f907-4e4a-81da-24af88857838 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
从“风药胜湿”与“升阳散火”两个学说分析，升阳益胃汤同时使用大量风药（如羌活、独活、防风）与苦寒之黄连，体现了李东垣针对“脾胃虚弱、湿郁化热”病机的双重治法：风药升阳燥湿以醒脾，黄连清泻阴火以存阴。该方与补中益气汤证之间存在虚实夹杂、燥湿转化的关系，即补中益气汤证以气虚下陷为主，而升阳益胃汤证在气虚基础上兼夹湿郁化热，故治法从单纯补气升阳转化为升阳益胃、清热化湿兼顾。  

**分点论述**  
1. **“风药胜湿”角度**  
   方中羌活、独活、防风等风药，性辛温升散，能宣畅气机、发散湿邪，契合李东垣“风药胜湿”理论。脾胃虚弱时运化失职，湿浊内停，风药可升发脾胃清阳，燥化中焦湿浊，助脾复健运之职。  

2. **“升阳散火”角度**  
   黄连虽苦寒，但配伍于大量风药及补气药中，意在清泻阴火。李东垣在《脾胃论》中提出“火与元气不两立”，脾胃气虚可导致阴火内生（如虚热、烦热），黄连能清湿热、泻阴火，防止湿郁化热伤津，与风药升阳散郁热相辅相成，体现“升阳散火”之旨。  

3. **与补中益气汤证的虚实、燥湿转化关系**  
   - **虚实转化**：补中益气汤证以脾胃气虚、清阳下陷为核心，病性偏虚；升阳益胃汤证在气虚基础上，兼有湿郁化热的实证表现（如湿热困脾、虚热内生），属虚实夹杂。  
   - **燥湿转化**：补中益气汤证湿象不显，以升阳举陷、甘温除热为主；升阳益胃汤证因湿浊内蕴，甚至化热，故加入茯苓、泽泻利湿，黄连清热，风药燥湿，治法从“升阳举陷”转为“升阳益胃、清热化湿”。  

**依据**  
1. 《脾胃论》指出升阳益胃汤具“升阳益胃”之功，方中含防风、羌活等风药及黄连，契合湿郁热伏病机。  
2. 《金匮翼》载补中益气汤功效为“补虚散邪”，凸显其补益为主、兼散外邪的特点，与升阳益胃汤的虚实夹杂治法形成对比。  
3. 《医方考》记载升阳益胃汤使用泽泻利湿，佐证该方兼顾湿邪与热邪的复合病机。

**依据来源**

- 205-金匮翼/None
- 614-脾胃论/None
- 072-医方考/None
- 132-女科证治准绳/None
- 082-古今名医方论/None
- 089-医方论/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '205-金匮翼', 'snippet': '二方俱补虚散邪之剂', 'score': 1.084, 'predicate': '功效', 'target': '补虚散邪', 'source_book': '205-金匮翼', 'source_chapter': None, 'evidence_path': 'book://金匮翼/*', 'source_scope_path': 'book://金匮翼/*', 'anchor_entity': '补中益气汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '614-脾胃论', 'snippet': '当升阳益胃，名之曰升阳益胃汤', 'score': 1.084, 'predicate': '功效', 'target': '升阳益胃', 'source_book': '614-脾胃论', 'source_chapter': None, 'evidence_path': 'book://脾胃论/*', 'source_scope_path': 'book://脾胃论/*', 'anchor_entity': '升阳益胃汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '072-医方考', 'snippet': '升阳益胃汤 属性：泽泻', 'score': 1.084, 'predicate': '使用药材', 'target': '泽泻', 'source_book': '072-医方考', 'source_chapter': None, 'evidence_path': 'book://医方考/*', 'source_scope_path': 'book://医方考/*', 'anchor_entity': '升阳益胃汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=read-syndrome-treatment; path=entity://升阳益胃汤/功效; reason=获取升阳益胃汤的核心功效，为后续与补中益气汤的比较提供基础', 'skill': 'read-syndrome-treatment'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://补中益气汤/功效; reason=获取补中益气汤的核心功效，以便与升阳益胃汤进行虚实、燥湿转化的比较分析', 'skill': 'read-syndrome-treatment'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=36
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_1:coverage_sufficient


## q04 宣痹汤与白虎加桂枝汤

**题目**

《温病条辨》中“宣痹汤”（苦辛宣痹法）治疗湿温痹阻，方中多用杏仁、薏苡仁、滑石、通草等淡渗之品，但又加入防己、蚕砂、半夏等辛温或苦辛之药。请从“湿闭气分”与“热蕴经络”的病机交织，论述宣痹汤与白虎加桂枝汤在治疗“热痹”证中的方证鉴别要点，并说明为何湿温所致痹证不宜早用石膏、知母。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 57.0s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 105.5s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 57.0s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | a4f3d5c9-e023-4c51-9d78-c69413538ba1 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机角度：**

宣痹汤所治“热痹”的核心病机是“湿闭气分”与“热蕴经络”相互交织。湿为重浊阴邪，易阻滞气机，困遏于气分；湿郁日久则化热，或与外来之热相合，蕴结于经络关节。此证湿热并存，但以湿邪闭阻气分为矛盾的主要方面，热象相对不显或为湿所遏。因此，治疗重在宣通气机、化湿透热，而非单纯清热。

白虎加桂枝汤所治“热痹”的病机则以阳明气分热盛为主，热邪炽盛，充斥内外，兼有风寒湿邪郁闭经络（桂枝所治）。其证以高热、汗出、烦渴等气分大热表现为特征，热势突出，湿邪不显或轻微。

**鉴别要点：**

两方虽同治“热痹”，但方证鉴别关键在于辨湿热之轻重与病位之偏颇：
1.  **病机与证候侧重点不同**：宣痹汤证是**湿热并重，湿闭气机为先**，症见关节肿痛、身热不扬、胸闷脘痞、舌苔黄腻；白虎加桂枝汤证是**热重于湿（或无湿），气分热盛为急**，症见关节红肿热痛、伴壮热、大汗、大渴、脉洪大。
2.  **组方思路与用药迥异**：宣痹汤以**苦辛通降、淡渗利湿**为主法，用杏仁、薏苡仁、滑石、通草宣气渗湿，佐以防己、蚕砂、半夏等辛开苦泄以宣痹通络，旨在开泄气分湿闭，使热随湿去。白虎加桂枝汤则以**辛寒清气**为主法，重用石膏、知母大清气分炽热，仅佐桂枝通络散痹兼制寒凉。
3.  **为何湿温痹证不宜早用石膏、知母**：石膏、知母性寒质润，功专清热生津。若在湿温初期或湿邪闭阻气分显著时过早使用，寒凉易遇伤阳气，滋腻更助湿邪，导致“冰伏气机”，使湿邪更加胶着难解，热反不得透达。故《温病条辨》治湿温强调“通阳不在温，而在利小便”，宣痹汤正是避用石膏、知母，而通过宣气、渗湿、通络来分解湿热，透热外出的典范。

**依据：**
1.  《温病条辨》指出宣痹汤用于“湿痹”，治法属“苦辛宣痹法”。
2.  《医学课儿策》将宣痹法与“湿温”治疗相关联。
3.  现代经验总结（《中医临证经验与方法》）认为宣痹汤功效在于“清热通络，化痰除湿”。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 413-医学课儿策/None
- 683-近现代名医验案类编/None
- 526-温病条辨/None
- 686-中医临证经验与方法/None
- 529-温病指南/None
- 中医临证经验与方法/第0页

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '413-医学课儿策', 'snippet': '湿郁气分者，为呃宣痹法', 'score': 1.084, 'predicate': '治法', 'target': '湿温', 'source_book': '413-医学课儿策', 'source_chapter': None, 'evidence_path': 'book://医学课儿策/*', 'source_scope_path': 'book://医学课儿策/*', 'anchor_entity': '宣痹法'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编', 'snippet': '方药：拟《温病条辨》宣痹汤加减。防己10克', 'score': 1.084, 'predicate': '使用药材', 'target': '防己', 'source_book': '683-近现代名医验案类编', 'source_chapter': None, 'evidence_path': 'book://近现代名医验案类编/*', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '宣痹汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '526-温病条辨', 'snippet': '湿聚热蒸，蕴于经络，寒战热炽，骨骱烦疼，舌色灰滞，面目萎黄，病名湿痹，宣痹汤主之。', 'score': 0.8584, 'predicate': '治疗疾病', 'target': '湿痹', 'source_book': '526-温病条辨', 'source_chapter': None, 'evidence_path': 'book://温病条辨/*', 'source_scope_path': 'book://温病条辨/*', 'anchor_entity': '宣痹汤'}

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

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 105.5s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | c8b45a52-206e-43f0-bcbf-d4b907e4d2e6 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机**

宣痹汤所治“热痹”的核心病机是“湿闭气分”与“热蕴经络”相互交织。其中，“湿闭气分”是关键，指湿邪郁闭于上焦或中焦气分，导致气机不畅，表现为胸闷、身重、舌白等；“热蕴经络”是湿郁化热，或湿热合邪，痹阻于经络关节，导致关节红肿热痛。两者交织，形成湿热痹阻之证。而白虎加桂枝汤所治“温疟”或“热痹”，其病机本质是“阴气先伤，阳气独发”（《温病条辨·温疟篇》），即里热炽盛（阳明气分热盛）兼有表邪或经络不和，热象更为纯粹、亢盛，湿邪不明显或为次要。

**鉴别**

宣痹汤与白虎加桂枝汤在治疗“热痹”时的方证鉴别要点如下：
1.  **病机侧重不同**：宣痹汤主治湿热并重，且湿邪闭阻气机为矛盾主要方面；白虎加桂枝汤主治阳明气分热盛为主，兼有表邪或经络痹阻，热重湿微或无湿。
2.  **主症有别**：宣痹汤证必有湿象，如关节肿痛、身重、胸闷、舌苔腻（白或黄）；白虎加桂枝汤证以高热、烦渴、汗出、脉洪大等阳明热盛表现为基础，兼见骨节烦疼。
3.  **组方思路迥异**：宣痹汤以杏仁、薏苡仁、滑石、通草等宣气、淡渗利湿为主，佐以防己、蚕砂、半夏等辛通苦泄以开郁闭、通经络，是“苦辛通阳”以化湿泄热。白虎加桂枝汤则以石膏、知母大清气分炽热，用甘草、粳米益胃生津，仅佐少量桂枝通络、和营卫兼以引热外达。因此，**湿温所致痹证若早用石膏、知母等大寒之品，易遇阻气机，使湿邪冰伏，病深难解**，反不利于湿邪的宣化与透达。

依据：
1.  《温病条辨》指出白虎加桂枝汤主治“骨节疼烦…但热不寒”的温疟，其病机为“阴气先伤，阳气独发”。
2.  近现代医案及临床经验将宣痹汤用于“风湿热痹之痰热较盛证”，体现了其治疗湿热痹阻的特点。
3.  《金匮要略方论》载白虎加桂枝汤主治“温疟”，确立了其清里热兼解肌的基本方向。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 683-近现代名医验案类编/None
- 499-金匮要略方论/None
- 686-中医临证经验与方法/None
- 433-六因条辨/None
- 207-医门法律/None
- 526-温病条辨/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编', 'snippet': '方药：拟《温病条辨》宣痹汤加减。防己10克', 'score': 1.084, 'predicate': '使用药材', 'target': '防己', 'source_book': '683-近现代名医验案类编', 'source_chapter': None, 'evidence_path': 'book://近现代名医验案类编/*', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '宣痹汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '499-金匮要略方论', 'snippet': '温疟者，其脉如平，身无寒但热，骨节疼烦，时呕，白虎加桂枝汤主之', 'score': 1.084, 'predicate': '治疗证候', 'target': '温疟', 'source_book': '499-金匮要略方论', 'source_chapter': None, 'evidence_path': 'book://金匮要略方论/*', 'source_scope_path': 'book://金匮要略方论/*', 'anchor_entity': '白虎加桂枝汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '686-中医临证经验与方法', 'snippet': '综合脉证，乃风湿热痹之痰热较盛证也', 'score': 1.084, 'predicate': '治疗证候', 'target': '风湿热痹之痰热较盛证', 'source_book': '686-中医临证经验与方法', 'source_chapter': None, 'evidence_path': 'book://中医临证经验与方法/*', 'source_scope_path': 'book://中医临证经验与方法/*', 'anchor_entity': '宣痹汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://宣痹汤/*; reason=获取宣痹汤的核心证据，为比较做准备', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://白虎加桂枝汤/*; reason=获取白虎加桂枝汤的核心证据，完成比较所需的基础信息', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=entity://宣痹汤/病机; reason=需要获取宣痹汤针对‘湿闭气分’与‘热蕴经络’交织病机的辨证链证据，以支持方证鉴别。', 'skill': 'trace-graph-path'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=2; skill=trace-graph-path; path=entity://白虎加桂枝汤/病机; reason=需要获取白虎加桂枝汤治疗‘热痹’的病机路径证据，以完成与宣痹汤的对比。', 'skill': 'trace-graph-path'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=2'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=27
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- read_evidence_path: status=empty
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_2:quality_gaps_persist:comparison
- deep_round_4:quality_gaps_persist:comparison
- deep_round_limit_reached


## q05 久病入络与虫类药阶梯

**题目**

叶天士《临证指南医案》中提出“久病入络”理论，并善用虫类药（如水蛭、䗪虫、全蝎、地龙）治疗顽痹、积聚。请结合《素问·痹论》“病久入深，营卫之行涩，经络时疏，故不通”的经旨，论证虫类药“搜剔络邪”与草木活血化瘀药在作用层次上的本质差异，并举例说明在肿瘤、肝纤维化中如何根据“络瘀”程度选择用药阶梯。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 41.2s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 79.6s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 41.2s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 2660ab8f-60e0-42ef-a441-7815be099b39 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

### 功效

虫类药与草木活血化瘀药在作用层次上的本质差异在于：草木药多作用于气分与血分的“瘀”，以疏通流动为主；而虫类药凭借其“搜剔”之性，能深入“络脉”层次，攻逐凝滞已久的“络瘀”或“络邪”。这正契合《素问·痹论》“病久入深，营卫之行涩，经络时疏，故不通”的经旨，病邪日久，由经入络，气血凝涩不通，形成草木药力难以抵达的深层痼结，此时需借虫类药走窜搜剔之强力方能通其痹阻。

在肿瘤与肝纤维化等“络瘀”重症中，可根据瘀结程度选择用药阶梯：
1.  **初期或轻症**：络瘀初成，可选用丹参、赤芍、桃仁等草木活血化瘀药为主，配合行气药物，以调和营卫，疏通气血。
2.  **中期或重症**：络瘀已成，结聚明显，如肿瘤实体形成或肝纤维化程度较重，则需在草木药基础上，加入地龙、全蝎等虫类药，以深入络脉，攻散结聚。
3.  **晚期或顽症**：络瘀深伏，坚结难化，如恶性肿瘤转移、晚期肝硬化，则需选用力量更为峻猛的虫类药，如水蛭、䗪虫等，以破血逐瘀、搜剔络中伏邪，正如叶天士治疗顽痹积聚所体现的“虫蚁搜剔”思想。例如，在治疗肿瘤积聚时，可选用化症回生丹（含虫类药）等方；治疗顽痹关节肿大畸形，可选用乌蛇、全蝎等药。

依据：
1.  《素问·痹论》指出“病久入深，营卫之行涩，经络时疏，故不通”，为“久病入络”理论提供了经典依据。
2.  叶天士在《临证指南医案》中善用虫类药治疗顽痹、积聚，体现了“搜剔络邪”的治法。
3.  古今医案及方剂记载，如治疗顽痹用乌蛇，治疗症积用化症回生丹（含虫类药），均为虫类药用于深层次络瘀的实例。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 699-名老中医之路/None
- 617-古今医统大全/None
- 669-名师垂教/None
- TCM-MKG/D3_CPM_TCMT
- 018-本草备要/None
- 013-本草纲目/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '699-名老中医之路', 'snippet': '《金匮》中的鳖甲煎丸和《温病条辨》中的化症回生丹，更是以虫类药为主', 'score': 1.084, 'predicate': '使用药材', 'target': '化症回生丹', 'source_book': '699-名老中医之路', 'source_chapter': None, 'evidence_path': 'book://名老中医之路/*', 'source_scope_path': 'book://名老中医之路/*', 'anchor_entity': '虫类药'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '617-古今医统大全', 'snippet': '乌蛇（主诸风瘾疹，疥癣，皮肤不仁，顽痹。）', 'score': 0.9908, 'predicate': '治疗疾病', 'target': '乌蛇', 'source_book': '617-古今医统大全', 'source_chapter': None, 'evidence_path': 'book://古今医统大全/*', 'source_scope_path': 'book://古今医统大全/*', 'anchor_entity': '顽痹'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '669-名师垂教', 'snippet': "导致顽痰死血胶结，出现皮肤瘀斑，关节周围结节，关节肿大、屈伸不利，甚至瘫痿畸形，形成'顽痹'。", 'score': 0.9895, 'predicate': '常见症状', 'target': '皮肤瘀斑，关节周围结节，关节肿大、屈伸不利，甚至瘫痿畸形', 'source_book': '669-名师垂教', 'source_chapter': None, 'evidence_path': 'book://名师垂教/*', 'source_scope_path': 'book://名师垂教/*', 'anchor_entity': '顽痹'}

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
- list_evidence_paths: count=21
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 79.6s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 6023f86f-6796-41c5-91b0-d70a8dcee3c8 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**功效**

**虫类药“搜剔络邪”与草木活血化瘀药的作用层次差异**
虫类药（如水蛭、䗪虫、全蝎、地龙）与草木类活血化瘀药在治疗“络瘀”时，其作用层次存在本质差异。这种差异根源于叶天士“久病入络”理论及《素问·痹论》“病久入深，营卫之行涩，经络时疏，故不通”的经旨。草木活血化瘀药（如丹参、川芎、桃仁、红花等）主要作用于气分及较浅表的血分，通过行气活血、化瘀通脉来改善宏观的血流与瘀滞，其药力相对和缓，作用层面偏于“经”与“脉”的主体通道。而虫类药则因其“飞者升，走者降，灵动迅速”的物性，具有“搜剔络邪”的独特功效，其药力深入“络脉”这一细微、缠结、深伏的层次。络脉是经脉的分支，久病邪气深入，与痰瘀互结，凝滞于这些细小网络之中，形成“络瘀”或“络痹”，非一般草木之品所能透达。虫类药凭借其走窜搜剔之性，能深入病所，攻逐痼结之瘀血、痰浊，松动病根，从而达到“通络”的目的。简言之，草木药重在“化瘀通脉”，虫类药强在“搜剔通络”，前者作用于气血运行的“主干道”，后者则清理深藏于“毛细血管网”及组织深处的痼结之邪。

**在肿瘤、肝纤维化中根据“络瘀”程度选择用药阶梯的举例说明**
在肿瘤及肝纤维化等“久病入络”的疾病中，根据“络瘀”的轻重程度，用药应呈现清晰的阶梯性。
1.  **轻度或初期络瘀**：常表现为气滞血瘀，病邪尚未完全深伏。治疗可首选草木类活血化瘀、行气散结之品，如丹参、莪术、三棱、郁金等，旨在疏通气血，防止瘀结加深。例如，在肝纤维化早期，胁肋胀痛、舌质暗红有瘀点，可选用此类药物组方。
2.  **中度或迁延性络瘀**：病邪已深入络脉，形成较为固定的癥瘕积聚，但尚未完全胶结。此时需草木药与部分性味相对平和的虫类药相结合，以增强通络散结之力。例如，在肿瘤形成或肝纤维化中期，出现可触及的包块、固定性刺痛、舌质紫暗时，可在草木活血方中加入地龙（通络）、穿山甲（活血消癥，现多用替代品）或鳖甲（软坚散结，虽非典型虫类，但属血肉有情之品，常与虫类药同用治疗癥积）。
3.  **重度或顽固性络瘀**：症积坚硬，疼痛剧烈，病位深锢，所谓“顽痹”、“癥积”已成。此时非峻猛搜剔之品不能为功，必须倚重虫类药作为主将或重要组成部分。例如，用于治疗“干血劳”、癥瘕积聚的古代名方“化症回生丹”，即大量使用了水蛭、虻虫、䗪虫等虫类药，以破血逐瘀、消癥散结。在晚期肿瘤或失代偿期肝硬化出现巨脾、腹内坚硬积块时，医家常在辨证基础上选用全蝎、蜈蚣（搜风通络止痛）、水蛭（破血逐瘀）等，直接“搜剔”深伏于络中的痰瘀毒结。叶天士在《临证指南医案》中治疗顽痹等症，亦善用虫蚁之类，取其“飞者升，走者降”的灵动之性，以松动病根。

**依据：**
1.  叶天士在《临证指南医案》中提出“久病入络”理论，并善用虫类药治疗顽痹、积聚，体现了其深入络脉的治疗思想。
2.  《素问·痹论》指出“病久入深，营卫之行涩，经络时疏，故不通”，为“久病入络”及使用虫类搜剔法提供了经典理论依据。
3.  古代方剂如“化症回生丹”大量使用水蛭、䗪虫等虫类药治疗癥瘕积聚，是虫类药用于重度“络瘀”的典型例证。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 699-名老中医之路/None
- 617-古今医统大全/None
- 669-名师垂教/None
- TCM-MKG/D3_CPM_TCMT
- 018-本草备要/None
- 013-本草纲目/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '699-名老中医之路', 'snippet': '《金匮》中的鳖甲煎丸和《温病条辨》中的化症回生丹，更是以虫类药为主', 'score': 1.084, 'predicate': '使用药材', 'target': '化症回生丹', 'source_book': '699-名老中医之路', 'source_chapter': None, 'evidence_path': 'book://名老中医之路/*', 'source_scope_path': 'book://名老中医之路/*', 'anchor_entity': '虫类药'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '617-古今医统大全', 'snippet': '乌蛇（主诸风瘾疹，疥癣，皮肤不仁，顽痹。）', 'score': 0.9908, 'predicate': '治疗疾病', 'target': '乌蛇', 'source_book': '617-古今医统大全', 'source_chapter': None, 'evidence_path': 'book://古今医统大全/*', 'source_scope_path': 'book://古今医统大全/*', 'anchor_entity': '顽痹'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '669-名师垂教', 'snippet': "导致顽痰死血胶结，出现皮肤瘀斑，关节周围结节，关节肿大、屈伸不利，甚至瘫痿畸形，形成'顽痹'。", 'score': 0.9895, 'predicate': '常见症状', 'target': '皮肤瘀斑，关节周围结节，关节肿大、屈伸不利，甚至瘫痿畸形', 'source_book': '669-名师垂教', 'source_chapter': None, 'evidence_path': 'book://名师垂教/*', 'source_scope_path': 'book://名师垂教/*', 'anchor_entity': '顽痹'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://虫类药/*; reason=获取虫类药的核心证据，为比较其与草木活血化瘀药的作用层次差异做准备。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://顽痹/*; reason=获取顽痹的治疗信息，以理解虫类药在其中的应用背景，为后续比较提供上下文。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=21
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_1:coverage_sufficient


## q06 2024甲辰年五运六气

**题目**

五运六气中“客主加临”出现“顺化”、“逆化”、“小逆”、“不和”等格局。请以某一年（如2024甲辰年）为例，推演其司天、在泉、主气、客气之间的加临关系，分析可能出现的气候与疫病倾向，并论述“治以咸寒，佐以甘苦”等运气治则在该年流感防治中的具体方药设计思路。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 72.6s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 83.3s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 72.6s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 5bb2d007-935f-4a27-923f-8ae1e0ba047e |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
2024甲辰年，司天为太阳寒水，在泉为太阴湿土。主气六步与客气六步加临后，三之气（司天之气）出现“不和”（主气少阳相火，客气太阳寒水，水火相克），全年气候易寒湿偏盛、火郁于内，可能引发外寒内热或寒湿郁热型流感。针对此类病机，“治以咸寒，佐以甘苦”的治则可设计为以咸寒清热、甘苦化湿调中的方药组合。

**一、2024甲辰年五运六气加临格局分析**  
1. **司天在泉**：甲辰年，年支辰属太阳寒水司天，太阴湿土在泉。  
2. **主客气加临**：  
   - 初之气（大寒至春分）：主气厥阴风木，客气少阳相火——木火相生，属“顺化”。  
   - 二之气（春分至小满）：主气少阴君火，客气阳明燥金——火克金，属“小逆”。  
   - **三之气（小满至大暑）**：主气少阳相火，客气太阳寒水（司天之气）——水克火，属“不和”。此步为全年关键，寒水克相火，易致外寒束表、内热郁结。  
   - 四之气（大暑至秋分）：主气太阴湿土，客气厥阴风木——木克土，属“不和”。  
   - 五之气（秋分至小雪）：主气阳明燥金，客气少阴君火——火克金，属“小逆”。  
   - 终之气（小雪至大寒）：主气太阳寒水，客气太阴湿土（在泉之气）——土克水，属“逆化”。  
3. **气候与疫病倾向**：  
   - 司天寒水主上半年寒冷，在泉湿土主下半年多湿。三之气“不和”易致寒包火：外有寒邪袭表，内有郁热或湿滞，流感可能表现为发热、恶寒、肢体困重、咽痛、烦渴等寒湿夹热证。  
   - 终之气“逆化”（土克水）易加重湿困脾阳，若正气不足，可能迁延为寒湿痹阻或腹泻。

**二、“治以咸寒，佐以甘苦”在甲辰年流感防治中的方药设计**  
1. **治则对应病机**：  
   - “治以咸寒”针对“热淫于内”或“少阴之复”之郁热，咸能软坚润下，寒能清热。  
   - “佐以甘苦”可调和寒湿：甘能补中、缓急，苦能燥湿、泄热，二者相佐可防咸寒伤脾，化解在泉太阴湿土的影响。  
   *依据*：  
   - “治以咸寒”为热淫于内或少阴之复的治法（《素问病机气宜保命集》《黄帝素问直解》）。  
   - “佐以甘苦”可用于热淫于内或寒淫所胜的配伍（《素问灵枢类纂约注》《黄帝内经素问集注》）。  

2. **具体方药思路**：  
   - **核心方剂**：可化裁**白虎加苍术汤**或**大青龙汤合三仁汤**加减。  
   - **咸寒药物**：生石膏（咸寒清热）、玄参（咸寒滋阴解毒）、芒硝（咸寒软坚通下，适用于便秘热结）。  
   - **甘苦佐药**：  
     - 甘味：甘草、粳米（护胃生津）、白术（甘温健脾化湿，针对太阴湿土）。  
     - 苦味：黄芩、杏仁（苦泄肺热）、厚朴（苦温燥湿）。  
   - **甲辰年适配加减**：  
     - 三之气（寒包火）：加麻黄、桂枝散外寒，配石膏清内热，佐藿香、茯苓化湿。  
     - 终之气（寒湿重）：去石膏，加干姜、草果温中化湿，配合玄参防燥热伤阴。  

**依据**：  
1. 治以咸寒适用于热淫于内之证（《素问病机气宜保命集》）。  
2. 佐以甘苦可配合咸寒治法，调和寒热湿邪（《素问灵枢类纂约注》）。  
3. 司天在泉加临关系基于五运六气客主加临理论（《医学实在易》司天在泉图说）。

**依据来源**

- 434-素问灵枢类纂约注/None
- 432-素问病机气宜保命集/None
- 435-黄帝素问直解/None
- 430-黄帝内经素问集注/None
- 427-类经/None
- 091-成方切用/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '434-素问灵枢类纂约注', 'snippet': '热淫于内。治以咸寒。佐以甘苦。', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '434-素问灵枢类纂约注', 'source_chapter': None, 'evidence_path': 'book://素问灵枢类纂约注/*', 'source_scope_path': 'book://素问灵枢类纂约注/*', 'anchor_entity': '佐以甘苦'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '432-素问病机气宜保命集', 'snippet': '若热淫于内。治以咸寒', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '432-素问病机气宜保命集', 'source_chapter': None, 'evidence_path': 'book://素问病机气宜保命集/*', 'source_scope_path': 'book://素问病机气宜保命集/*', 'anchor_entity': '治以咸寒'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '435-黄帝素问直解', 'snippet': '少阴之复，治以咸寒', 'score': 0.6867, 'predicate': '治法', 'target': '少阴之复', 'source_book': '435-黄帝素问直解', 'source_chapter': None, 'evidence_path': 'book://黄帝素问直解/*', 'source_scope_path': 'book://黄帝素问直解/*', 'anchor_entity': '治以咸寒'}

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
- list_evidence_paths: count=36
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 83.3s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 71f85f7d-4843-415f-83b2-cbc4f2e6fd60 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
根据五运六气理论，2024年甲辰年的司天为太阳寒水，在泉为太阴湿土。主气与客气加临后，可能出现“寒湿相搏”兼“火郁发之”的复杂格局，易导致外寒内热、湿遏热伏的气候与疫病倾向。针对该年流感防治，“治以咸寒，佐以甘苦”的治则应具体化为**咸寒清热、甘苦化湿透热**的方药设计思路，核心在于化解湿热郁结、调节气机升降。

**一、2024年客主加临格局与气候疫病倾向**  
1. **司天在泉与主客气关系**：  
   - 甲辰年司天为**太阳寒水**（主管上半年气候），在泉为**太阴湿土**（主管下半年气候）。  
   - 主气为固定六步之气，客气依岁支轮转：三之气（司天位）主气为少阳相火，客气为太阳寒水，形成“**客寒主火**”；四之气主气为太阴湿土，客气为厥阴风木，形成“**客风主湿**”。  
   - 加临关系分析：  
     - **三之气（小满至大暑）**：客气太阳寒水加临主气少阳相火，水火相克，属“**小逆**”格局，易致寒包火郁，气候乍寒乍热。  
     - **四之气（大暑至秋分）**：客气厥阴风木加临主气太阴湿土，木克土但风能胜湿，属“**顺化**”格局，但湿土被风木所动，易生湿热交蒸。  
   - 全年整体呈现**上寒下湿、寒湿热互结**之势，易诱发外感病兼夹湿邪。

2. **气候与疫病倾向**：  
   - 气候：上半年偏寒，夏季多寒热交替；下半年多雨潮湿，秋冬易见湿冷。  
   - 疫病倾向：流感可能表现为**表寒里热、湿阻膜原**的特征，如发热恶寒、肢体困重、咽喉肿痛、胸闷脘痞等，符合《黄帝内经》中“寒湿相遘，热郁于中”的病机。

**二、“治以咸寒，佐以甘苦”在流感防治中的方药设计思路**  
1. **治则解析**：  
   - **治以咸寒**：针对“热淫于内”或“少阴之复”之热郁，咸寒药物能软坚泻热、滋阴降火（依据《素问病机气宜保命集》《黄帝素问直解》）。  
   - **佐以甘苦**：甘味可补中化湿、调和药性，苦味能燥湿泄热，二者协同化解湿邪、透达郁热（依据《素问灵枢类纂约注》）。  
   - 该治则原用于“热淫于内”或“寒淫所胜”化热之证，甲辰年寒湿外束、湿热内郁，故需**咸寒与甘苦并用**，兼顾清热、化湿、透邪。

2. **具体方药设计**：  
   - **核心方剂**：可化裁**宣痹汤**（《温病条辨》）合**升降散**（《伤寒温疫条辨》），酌加咸寒之品。  
   - **药物配伍**：  
     - **咸寒清热**：玄参、牡蛎、犀角（或水牛角代），清解内热、软坚散结。  
     - **甘苦化湿透热**：  
       - 甘味：生甘草、茯苓，健脾利湿以扶正。  
       - 苦味：黄芩、栀子、杏仁，苦寒燥湿、宣肺透热。  
     - **佐使调整**：  
       - 若表寒明显，加羌活、防风辛温散寒（反佐防咸寒遏邪）。  
       - 若湿重胸闷，加厚朴、草果苦温化湿。  
   - **方义**：咸寒直折里热，甘苦调和气机、分消湿热，契合甲辰年寒湿热错杂之病机。

**依据**：  
1. 《素问灵枢类纂约注》指出“佐以甘苦”适用于热淫于内之证，强调甘苦合化以调气机。  
2. 《素问病机气宜保命集》载“治以咸寒”为热淫于内核心治法，咸寒能泻火存阴。  
3. 《黄帝素问直解》以“治以咸寒”疗少阴之复，针对热郁化火之变证。  

（注：五运六气推演基于《医学实在易》司天在泉理论，方药设计融合温病学治法，需临证辨证加减。）

**依据来源**

- 434-素问灵枢类纂约注/None
- 432-素问病机气宜保命集/None
- 435-黄帝素问直解/None
- 430-黄帝内经素问集注/None
- 427-类经/None
- 444-读素问钞/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '434-素问灵枢类纂约注', 'snippet': '热淫于内。治以咸寒。佐以甘苦。', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '434-素问灵枢类纂约注', 'source_chapter': None, 'evidence_path': 'book://素问灵枢类纂约注/*', 'source_scope_path': 'book://素问灵枢类纂约注/*', 'anchor_entity': '佐以甘苦'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '432-素问病机气宜保命集', 'snippet': '若热淫于内。治以咸寒', 'score': 1.084, 'predicate': '治法', 'target': '热淫于内', 'source_book': '432-素问病机气宜保命集', 'source_chapter': None, 'evidence_path': 'book://素问病机气宜保命集/*', 'source_scope_path': 'book://素问病机气宜保命集/*', 'anchor_entity': '治以咸寒'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '435-黄帝素问直解', 'snippet': '少阴之复，治以咸寒', 'score': 0.6867, 'predicate': '治法', 'target': '少阴之复', 'source_book': '435-黄帝素问直解', 'source_chapter': None, 'evidence_path': 'book://黄帝素问直解/*', 'source_scope_path': 'book://黄帝素问直解/*', 'anchor_entity': '治以咸寒'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://治以咸寒/*; reason=为比较对象‘治以咸寒’获取核心证据，如功效、主治或出处。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://佐以甘苦/*; reason=为比较对象‘佐以甘苦’获取核心证据，以支持后续比较分析。', 'skill': 'compare-formulas'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=36
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
| quick | ok | hybrid | grounded_llm | 54.2s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 127.2s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 54.2s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 29aa6765-2b5b-40f8-8ffb-99291d427e7f |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

### 功效
黄芪“托毒生肌”与“益气升阳”的功效统一于“阳气充足则邪气自散”的核心病机。在“托毒生肌”方面，黄芪通过补益正气，促使脓液排出、疮口愈合，治疗痈疽久败疮。在“益气升阳”方面，如补中益气汤、玉屏风散中，黄芪通过升举清阳、固护卫表，治疗气虚下陷或表虚不固。两者均以补气（益气）为基础，气足则阳旺，阳旺则能驱散邪气、固摄机体，从而实现从内托毒外出与从外固护肌表的统一。

### 病机
其统一性的病机关键在于“阳气充足则邪气自散”。中医理论认为，阳气具有温煦、推动、固摄和防御功能。慢性痈疽、溃疡乃正气不足（阳气虚），无力托毒外出所致；而气虚下陷、卫表不固亦是阳气不充、固摄无力之态。黄芪大补脾肺之气，气属阳，气足则阳气自旺。阳气旺盛则能温通血脉、推动血行以排脓生肌（托毒），同时能升提固摄以举陷固表（升阳）。因此，无论是深陷于内的“毒”，还是侵袭于表的“邪”，只要阳气充沛，便能自行消散或抵御。依据：医经原旨指出“阳气充足则邪气自散”属于养神的功效范畴（425-医经原旨/None）。

### 现代对接
从现代免疫学角度，黄芪的作用机制主要体现在调节免疫细胞功能上，这为上述两种功效提供了统一的生物学解释：
1.  **调节T细胞亚群**：黄芪多糖等成分能促进辅助性T细胞（如Th1）分化，增强细胞免疫，这对于清除细胞内病原体、促进慢性感染（如难愈性溃疡的感染）的恢复至关重要。同时，它也能调节调节性T细胞（Treg），维持免疫平衡，防止过度炎症损伤。
2.  **影响巨噬细胞极化**：黄芪能促进巨噬细胞向M1型（促炎、杀菌）极化，增强其吞噬和杀灭病原体的能力，直接对应“托毒”；同时，它也能调节巨噬细胞向M2型（抗炎、修复）转化，促进组织修复和伤口愈合，对应“生肌”。这种双向调节确保了在清除病原体的同时促进组织修复。
3.  **增强整体免疫**：黄芪能提升巨噬细胞、自然杀伤细胞（NK细胞）的活性，并促进免疫因子（如干扰素、白细胞介素-2）的分泌，全面增强机体的免疫防御功能。这相当于现代医学的“增强抵抗力”，与中医“益气固表”（如玉屏风散预防外感）和“扶正托毒”的理念高度吻合。

综上，黄芪通过多靶点调节免疫系统，增强机体清除病原体和自我修复的能力，这从现代科学层面统一解释了其既能“托毒生肌”治疗慢性溃疡，又能“益气升阳”防治表虚易感的机制。

依据：
1.  医经原旨指出“阳气充足则邪气自散”属于养神的功效范畴（425-医经原旨/None）。
2.  《神农本草经》记载黄芪“主痈疽久败创，排脓止痛”（000-神农本草经/黄）。
3.  玉屏风散方中使用防风等药材以配伍黄芪固表（089-医方论/None）。

**依据来源**

- 425-医经原旨/None
- 089-医方论/None
- 433-六因条辨/None
- 450-难经经释/None
- 315-银海指南/None
- 428-类经图翼/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '425-医经原旨', 'snippet': '阳气者，精则养神，柔则养筋。', 'score': 1.084, 'predicate': '功效', 'target': '养神', 'source_book': '425-医经原旨', 'source_chapter': None, 'evidence_path': 'book://医经原旨/*', 'source_scope_path': 'book://医经原旨/*', 'anchor_entity': '阳气充足则邪气自散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '黄 （炙） 防风一两 白术（炒）二两', 'score': 1.084, 'predicate': '使用药材', 'target': '防风', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '玉屏风散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '433-六因条辨', 'snippet': '补中益气汤：黄祗，人参，白术，当归，陈皮，炙甘草，柴胡，升麻', 'score': 1.084, 'predicate': '使用药材', 'target': '人参', 'source_book': '433-六因条辨', 'source_chapter': None, 'evidence_path': 'book://六因条辨/*', 'source_scope_path': 'book://六因条辨/*', 'anchor_entity': '补中益气汤'}

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
- list_evidence_paths: count=38
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 127.2s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 0654311a-8f67-450d-80de-c0da816a3d47 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

### 功效
黄芪“托毒生肌”与“益气升阳”的功效统一于“扶助阳气”。在《神农本草经》中，黄芪主治“痈疽久败疮”，是通过补益阳气以托毒外出、生肌长肉。在补中益气汤、玉屏风散等方中，黄芪“益气固表”的本质亦是升发、固护人体阳气（卫阳、中阳）。两者均以黄芪补气（益气）为核心，气属阳，阳气充盛则能固摄肌表、驱邪外出，从而在体表实现“托毒”与“固表”的统一。依据《医经原旨》所载的核心病机理论“阳气充足则邪气自散”，这正是两种功效指向统一的根本原理。

### 病机
其统一的病机基础在于“阳气虚馁，邪气留连”。慢性痈疡、难愈性溃疡多因气血不足，阳气无力托毒生肌；而自汗、易感等表虚之证，则是卫阳不固，腠理疏松。两者虽表现不同，但核心病机均为阳气（卫气、中气）虚弱。黄芪通过“益气”大补脾肺之气，使中焦之气升发，卫外之气固密。中气足则清阳得升，卫气足则腠理致密，既能升提固摄（治气虚下陷、自汗），亦能鼓舞气血至疮疡表面以排脓生肌（治久败疮）。这正体现了“阳气充足则邪气自散”的整体观：内在阳气充沛，则体表的邪气（风邪、毒邪）自然无法留滞。

### 现代对接
从现代免疫学视角看，黄芪作用的统一性体现在其能多靶点调节免疫，增强机体清除病原和修复组织的能力，这与中医“扶助阳气以祛邪”的理念相契合。
1.  **调节T细胞亚群**：黄芪多糖等成分能促进T淋巴细胞增殖，调节辅助性T细胞（Th）亚群的平衡，例如增强Th1细胞功能，促进细胞免疫，这对于清除细胞内病原、控制慢性感染至关重要。
2.  **调控巨噬细胞极化**：黄芪能促进巨噬细胞向M1型（促炎、杀菌）和M2型（抗炎、修复）的功能转化，在感染早期增强杀菌活性，在后期则促进组织修复和血管生成，这直接对应了“托毒生肌”的过程——先“排脓”（清除坏死组织与病原），后“生肌”（促进肉芽组织生长）。
3.  **增强免疫屏障**：黄芪能提升血清免疫球蛋白（如IgA）水平，增强呼吸道、消化道黏膜的免疫防御功能，这为“益气固表”预防外邪侵袭提供了现代解释。

因此，在慢性感染和难愈性溃疡中，黄芪通过上述机制，综合增强机体固有免疫和适应性免疫，改善局部微循环与营养供给，从而起到抗感染、促愈合的作用，这正是“阳气充足则邪气自散”在现代科学层面的机制诠释。

**依据**：
1. 《医经原旨》指出“阳气充足则邪气自散”，此为根本病机。
2. 《金匮玉函经二注》载黄芪“益气”，是其核心功效。
3. 《医方论》中玉屏风散等方的配伍，体现了黄芪益气固表的应用。

**依据来源**

- 425-医经原旨/None
- 501-金匮玉函经二注/None
- 089-医方论/None
- 433-六因条辨/None
- 450-难经经释/None
- 315-银海指南/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '425-医经原旨', 'snippet': '阳气者，精则养神，柔则养筋。', 'score': 1.084, 'predicate': '功效', 'target': '养神', 'source_book': '425-医经原旨', 'source_chapter': None, 'evidence_path': 'book://医经原旨/*', 'source_scope_path': 'book://医经原旨/*', 'anchor_entity': '阳气充足则邪气自散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '501-金匮玉函经二注', 'snippet': '黄芪益气，入皮毛，肥腠理，退热止汗之功尤切', 'score': 1.084, 'predicate': '功效', 'target': '益气', 'source_book': '501-金匮玉函经二注', 'source_chapter': None, 'evidence_path': 'book://金匮玉函经二注/*', 'source_scope_path': 'book://金匮玉函经二注/*', 'anchor_entity': '黄芪'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '黄 （炙） 防风一两 白术（炒）二两', 'score': 1.084, 'predicate': '使用药材', 'target': '防风', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '玉屏风散'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://补中益气汤/*; reason=用户比较补中益气汤和玉屏风散中黄芪的功效，需先获取补中益气汤的核心证据（如功效、组成）以进行比较分析。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://玉屏风散/*; reason=为完成黄芪在补中益气汤与玉屏风散中的功效比较，需获取玉屏风散的核心证据（如功效、组成），确保两个比较对象均有覆盖。', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=entity://黄芪/功效; reason=用户问题核心是论证黄芪‘托毒生肌’与‘益气升阳’功效的统一性，需先获取黄芪功效的结构化证据，以建立与‘阳气充足则邪气自散’的关联。', 'skill': 'trace-graph-path'}
- {'stage': 'search_evidence_text', 'label': '补充文本检索', 'detail': 'round=2; action=2; skill=search-source-text; path=chapter://六因条辨/None; reason=问题要求结合现代免疫学解释黄芪在慢性感染、难愈性溃疡中的应用机制，需搜索相关古籍原文或现代教材文献作为佐证。', 'skill': 'search-source-text'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=1'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=38
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- search_evidence_text: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_4:coverage_sufficient


## q08 半夏秫米汤与睡眠节律

**题目**

《灵枢·卫气行》论述卫气昼行于阳、夜行于阴的节律。失眠（不寐）病机多责之“阳不入阴”。请从卫气循行与跷脉的关系，分析半夏秫米汤“通阴阳”的配伍原理，并论述该方与现代治疗失眠的褪黑素、GABA受体激动剂在调节“睡眠-觉醒节律”上的可能对应机制。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | graph | grounded_llm | 38.1s | 6 | 0 |
| deep | ok | graph | planner_llm | 76.2s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 38.1s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path |
| fallback_detected | no |
| trace_id | 0f38ce80-4e97-41ee-af55-2e87e9b3e155 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**  
半夏秫米汤通过半夏降逆和胃、秫米养阴安中的配伍，调和脾胃、交通阴阳，从而恢复卫气循行与跷脉平衡，治疗“阳不入阴”之失眠。其调节“睡眠-觉醒节律”的机制，与现代褪黑素调节生物钟、GABA受体激动剂抑制中枢兴奋具有功能上的对应性，但中医侧重整体气机调和，西医侧重神经递质靶向干预。  

**配伍**  
半夏秫米汤以半夏配伍秫米为核心。半夏辛开降逆，能通泄阳明胃气，破除痰湿壅滞；秫米甘凉益阴，和胃安中，兼制半夏之燥。二者相合，辛甘并用，通滞养阴，使中焦脾胃气机调畅，为卫气循行提供通路。依据：《本草纲目》记载该方使用秫米，强调其安中养阴之效。  

**病机**  
失眠“阳不入阴”与卫气循行失常、跷脉失衡相关。卫气昼行阳经、夜行阴分，依赖阴阳跷脉的司目开阖。若脾胃痰湿或胃气不和，阻滞中焦，可致卫气从阳入阴之路受阻，阳跷脉盛而阴跷脉弱，出现“目不得瞑”。半夏秫米汤通过“交通阴阳”（《近现代名医验案类编》），调和脾胃、祛除湿热（《医方简义》指出其治“胃中有湿热”），使卫气顺利入阴，跷脉恢复平衡。  

**现代对接**  
1. **与褪黑素的对应**：褪黑素通过调节视交叉上核生物钟，促进睡眠节律同步。半夏秫米汤“通阴阳”可类比为调节人体阴阳时序，恢复卫气“昼阳夜阴”节律，二者均作用于节律同步化层面。  
2. **与GABA受体激动剂的对应**：GABA受体激动剂抑制神经元兴奋，促进入睡。半夏秫米汤中半夏可能通过调节胃肠神经（如脑肠轴）影响中枢抑制，秫米提供营养物质支持神经功能，共同降低机体亢奋状态，类似于GABA系统的镇静作用。  
需注意：中医强调整体气机升降，西医侧重特定受体或激素靶点，机制并非直接等同。  

**依据**：  
1. 《本草纲目》记载半夏秫米汤配伍秫米。  
2. 《医学衷中参西录》指出该方治疗“目不得瞑”。  
3. 《近现代名医验案类编》述其具“交通阴阳”功效。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 013-本草纲目/None
- 584-医学衷中参西录/None
- 683-近现代名医验案类编/None
- 122-医方简义/None
- 360-徐批叶天士晚年方案真本/None
- 372-一得集/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目', 'snippet': '置秫米一升', 'score': 1.084, 'predicate': '使用药材', 'target': '秫米', 'source_book': '013-本草纲目', 'source_chapter': None, 'evidence_path': 'book://本草纲目/*', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '584-医学衷中参西录', 'snippet': '《内经》治目不得瞑，有半夏秫米汤原甚效验', 'score': 0.9677, 'predicate': '治疗症状', 'target': '目不得瞑', 'source_book': '584-医学衷中参西录', 'source_chapter': None, 'evidence_path': 'book://医学衷中参西录/*', 'source_scope_path': 'book://医学衷中参西录/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编', 'snippet': '得半夏秫米之交通阴阳', 'score': 0.8761, 'predicate': '功效', 'target': '交通阴阳', 'source_book': '683-近现代名医验案类编', 'source_chapter': None, 'evidence_path': 'book://近现代名医验案类编/*', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '半夏秫米汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=path_reasoning'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=1; gaps=path_reasoning'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=15
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 76.2s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 1c1626a2-2e22-4ccc-9216-96704cfc47f9 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

### 配伍原理
**结论**：半夏秫米汤通过半夏与秫米的配伍，实现“交通阴阳，引阳入阴”的功效，其核心在于调和胃气、化痰浊以开通道路，使卫气循行复常。

**依据**：方中半夏辛温，能燥湿化痰、和胃降逆；秫米（即高粱米）甘凉，能和胃安神、益阴气。两者相配，一温一凉，一降一和，共奏化痰和胃、调畅中焦之效。中焦为气机升降之枢，亦是卫气运行的重要关隘。痰湿壅滞于胃，可导致中焦气机阻塞，进而使卫气从阳入阴的循行通路受阻，出现“阳不入阴”的失眠。本方通过化痰和胃，疏通中焦枢纽，为卫气由阳经（昼行于阳）顺利转入阴经（夜行于阴）创造了条件，从而实现“通阴阳”的目的。此“通”并非直接补益阴阳，而是祛除障碍、畅通道路。

### 病机分析（卫气循行与跷脉关系）
**结论**：失眠“阳不入阴”的核心病机与卫气循行失常、跷脉失衡密切相关。半夏秫米汤正是通过调和脾胃、化痰通滞，间接调节卫气在跷脉及阴阳之间的交接，促使其入阴。

**依据**：根据《灵枢》理论，卫气白昼行于阳分（体表、六腑），夜晚行于阴分（五脏、体内）。卫气由阳入阴的交接点，与跷脉（阴跷、阳跷）的功能密切相关。跷脉主司眼睑开合与肢体运动，是卫气昼夜运行转换的关键通路之一。若痰湿、食滞等邪气壅塞于中焦脾胃，可导致气机升降失常。脾胃属土，居中央而灌四旁，是卫气运行和转化的中继站。中焦阻塞，一方面可直接阻碍卫气由阳经（如足阳明胃经）向阴经的传输；另一方面，也可能影响跷脉的气机平衡，使卫气无法通过跷脉的调节顺利从“觉醒”（阳跷盛）状态转入“睡眠”（阴跷盛）状态。半夏秫米汤针对“痰湿阻于中焦”这一关键病理环节，通过和胃化痰，恢复中焦枢纽的转枢功能，从而有助于卫气循行节律的恢复和跷脉功能的协调，使阳能入阴。

### 现代对接机制
**结论**：半夏秫米汤“通阴阳”调节睡眠节律的作用，可能与现代医学中调节神经递质平衡、修复生物钟功能有关，其整体调节思路与褪黑素、GABA受体激动剂等靶点明确的药物存在机制上的互补与交叉。

**依据**：
1.  **与褪黑素调节节律的可能对应**：褪黑素由松果体分泌，受光暗信号调节，是内源性“睡眠-觉醒节律”的关键信使。中医卫气昼行于阳、夜行于阴的节律，与现代的生物钟（Circadian Rhythm）概念高度相似。半夏秫米汤通过调和脾胃、畅通气机，可能间接改善了机体整体内环境（包括胃肠功能），而胃肠道本身存在大量的分泌细胞和神经末梢，被称为“第二大脑”，其功能稳定对中枢生物钟和褪黑素的正常分泌有重要影响。因此，该方可能通过“调和脾胃-稳定内环境-促进生物钟同步”的途径，起到类似调节和巩固基础睡眠节律的作用。
2.  **与GABA受体激动剂促进抑制的可能对应**：GABA（γ-氨基丁酸）是中枢神经系统主要的抑制性神经递质，GABA受体激动剂通过增强中枢抑制来促进入睡。中医“阳不入阴”可理解为兴奋性（阳）过程不能适时转化为抑制性（阴）过程。半夏秫米汤中的半夏，现代药理研究表明其具有中枢镇静作用。更重要的是，该方“和胃化痰”的功效，旨在消除导致中枢兴奋性异常升高的病理因素（如痰湿扰神）。从整体看，它可能通过降低病理性兴奋（如痰火扰心、胃不和则卧不安），恢复神经系统的兴奋-抑制平衡，这与GABA系统增强抑制功能以对抗过度兴奋的最终目标有相通之处，但途径更侧重于消除病因而非直接作用于受体。

**总结**：半夏秫米汤是从“调和脾胃、化痰通滞”的整体机能层面入手，恢复气机升降和营卫循行的节律，其作用机制可能是多靶点、系统性的。而褪黑素和GABA受体激动剂则是在生物钟信号传导或神经突触抑制的特定分子靶点上进行干预。二者在“调节睡眠-觉醒节律”的最终目标上一致，但干预层次和路径不同，体现了中西医不同的思维模式和治疗策略。

**依据**：
1.  《近现代名医验案类编》指出半夏秫米汤具有“交通阴阳，引阳入阴”的功效。
2.  《本草纲目》记载了半夏秫米汤的组成药材为半夏和秫米。
3.  《章次公医案》中提及该方有“和胃化痰”之功。

---
⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。中医诊疗应在有执照的医师指导下进行，请勿自行用药。

**依据来源**

- 683-近现代名医验案类编/None
- 013-本草纲目/None
- 679-章次公医案/None
- 121-医方歌括/None
- 360-徐批叶天士晚年方案真本/None
- 372-一得集/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '683-近现代名医验案类编', 'snippet': '半夏秫米汤交通阴阳，引阳入阴', 'score': 1.084, 'predicate': '功效', 'target': '交通阴阳，引阳入阴', 'source_book': '683-近现代名医验案类编', 'source_chapter': None, 'evidence_path': 'book://近现代名医验案类编/*', 'source_scope_path': 'book://近现代名医验案类编/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '013-本草纲目', 'snippet': '置秫米一升', 'score': 1.084, 'predicate': '使用药材', 'target': '秫米', 'source_book': '013-本草纲目', 'source_chapter': None, 'evidence_path': 'book://本草纲目/*', 'source_scope_path': 'book://本草纲目/*', 'anchor_entity': '半夏秫米汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '679-章次公医案', 'snippet': '此用半夏秫米汤和胃化痰', 'score': 0.6697, 'predicate': '功效', 'target': '和胃化痰', 'source_book': '679-章次公医案', 'source_chapter': None, 'evidence_path': 'book://章次公医案/*', 'source_scope_path': 'book://章次公医案/*', 'anchor_entity': '半夏秫米汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=trace-graph-path; path=entity://半夏秫米汤/推荐方剂; reason=用户需要分析方剂原理与卫气、跷脉的关系，应先获取方剂与证候或生理路径的关联证据，以建立‘通阴阳’的辨证链。', 'skill': 'trace-graph-path'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=read-syndrome-treatment; path=entity://半夏秫米汤/功效; reason=在获取路径关联后，需明确方剂的‘通阴阳’功效的具体表述，为后续与现代机制对比提供核心依据。', 'skill': 'read-syndrome-treatment'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=1'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=15
- read_evidence_path: status=empty
- read_evidence_path: status=ok

**备注**

- deep_round_1:coverage_sufficient


## q09 胸痹三方与冠心病分层

**题目**

张仲景《金匮要略·胸痹心痛短气病脉证治》中，栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方均治胸痹，但用药有从“辛温通阳”到“理气化痰”再到“破气逐饮”的递进。请从“阳气不通—痰浊壅盛—饮邪结聚”的病机演变，论证三方证的阶梯性差异，并说明现代冠心病（稳定型心绞痛、不稳定型心绞痛、急性心肌梗死）可如何参照此辨证体系。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | hybrid | grounded_llm | 70.5s | 6 | 0 |
| deep | ok | hybrid | planner_llm | 109.9s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 70.5s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, search_evidence_text |
| fallback_detected | no |
| trace_id | c72f3de5-1bc9-4925-9b1b-ad957f58e1cf |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机演变与三方证的阶梯性差异**

根据《金匮要略》的辨证体系，栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方确实体现了从“阳气不通”到“痰浊壅盛”，再到“饮邪结聚”的病机递进与证治差异。

1.  **阳气不通（栝楼薤白白酒汤证）**：此为胸痹的基础证型与初始阶段。核心病机为胸阳不振，阳气痹阻不通。临床以“喘息咳唾，胸背痛，短气”为主症，病邪相对较轻，以气滞为主。治以**辛温通阳，豁痰下气**。方中栝楼实宽胸涤痰，薤白辛温通阳，白酒轻扬上行以助药势，共奏宣痹通阳之效。

2.  **痰浊壅盛（栝楼薤白半夏汤证）**：此证在胸阳不振的基础上，痰浊之邪显著加重，壅塞胸中。其证在“胸痹不得卧”，即平卧则痰浊上壅、气机更为窒塞，提示痰浊壅盛，痹阻更甚。治疗在通阳的基础上，**着重化痰降逆**。故于前方中加入半夏，以增强燥湿化痰、消痞散结之力，针对“痰浊壅盛”这一核心矛盾。

3.  **饮邪结聚（枳实薤白桂枝汤证）**：此证病机更深一层，不仅痰浊壅盛，更兼水饮、阴寒之邪结聚胸中，气机由壅塞发展为**痞满结聚**。其证见“心中痞，留气结在胸，胸满，胁下逆抢心”，病位由胸扩展至胁下，气机逆乱更为明显。治疗上，从“化痰”进一步发展为**破气除满、温通降逆**。方中去白酒，加枳实、厚朴以破气消痞、宽胸下气，加桂枝以通阳平冲，共奏破气逐饮、通阳散结之功。

**现代冠心病辨证的参照应用**

张仲景的这一辨证层次，可为现代冠心病的辨证论治提供清晰的框架参照：

*   **稳定型心绞痛**：其发作特点明确，诱因相对固定，病情稳定。多对应于**阳气不通**或轻度**痰浊壅盛**的阶段。可参照栝楼薤白白酒汤或栝楼薤白半夏汤进行化裁，以通阳宣痹、化痰活血为基本治法，重在改善心肌供血、稳定斑块。
*   **不稳定型心绞痛**：疼痛加剧、频率增加，提示斑块不稳定、血栓形成风险高。其病机多属**痰浊壅盛**兼有瘀血，或向**饮邪结聚**发展，气滞血瘀、痰瘀互结更为突出。可重点参照栝楼薤白半夏汤与枳实薤白桂枝汤的思路，加强**理气化痰、活血破瘀**之力，并酌情加入活血化瘀、稳定斑块的药物。
*   **急性心肌梗死**：属急危重症，表现为剧烈持久的胸痛，常伴气虚阳脱、心脉痹阻之象。其病机可视为**痰浊、瘀血、水饮**等实邪**严重结聚**，闭阻心脉，并迅速耗伤正气。此时可借鉴枳实薤白桂枝汤**破气逐饮、通阳开痹**的峻猛思路，但必须结合现代急救措施，并大力加入益气活血、回阳救逆、化瘀通络之品，进行中西医结合救治。

**依据**：
1.  《金匮要略·胸痹心痛短气病脉证治》原文记载了栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方的主治证候，体现了病情的逐步加重。
2.  《医述·胸痹》区分了胸痹与胸痞的不同，有助于理解胸痹以阳气痹阻为核心的基本病机。
3.  后世方书如《证治汇补》等，对以薤白、半夏等为主药的方剂（如薤白半夏汤）用于治疗“食痹”等证有所发挥，佐证了化痰降逆法在胸痹治疗中的应用。

---
🚨 **重要医疗声明**：您提及的情况涉及需要专业医疗判断的高风险场景。本系统仅提供中医历史文献知识，无法替代执业医师的诊断与治疗方案。请立即就医或拨打急救电话，不要仅依靠本工具的信息做出医疗决策。

**依据来源**

- 289-证治汇补/None
- 医述/胸痹
- 普济方/病机论
- 普济方/第1页
- 普济方/胸痹（附论）
- 普济方/胸痹心下坚痹痞急（附论）

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '289-证治汇补', 'snippet': '薤白半夏汤治之', 'score': 1.084, 'predicate': '治疗疾病', 'target': '食痹', 'source_book': '289-证治汇补', 'source_chapter': None, 'evidence_path': 'book://证治汇补/*', 'source_scope_path': 'book://证治汇补/*', 'anchor_entity': '薤白半夏汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'doc', 'source': '599-医述.txt#113', 'snippet': '古籍：医述\n篇名：胸痹\n属性：\\x哲言\\x胸痹与胸痞不同。胸痞有暴寒郁结于胸者；有火郁于中者；\n有寒热互郁者；有气实填胸而痞者；有气衰而成虚痞者；有肺胃津液枯涩，因燥而痞者；有上焦湿浊弥漫而痞者。若夫胸痹，但因胸中阳虚不运，久而成痹。《内经》未曾详言，惟《金匮》立方俱用辛滑温通，所云∶寸口脉沉而迟，阳微阴弦，是知但有寒证而无热证矣。治法亦惟温通上焦清阳为主。莫与胸痞、结胸、噎隔、痰食等证混治，斯得之矣。（《临证指南》）凡遇胸痹、心痛、短气等证，以为虚而有邪在，非虚也；以为实而有邪乘，非实也。标本缓急之间，神明者顾可缺一不讲也耶？（魏荔彤）胸痹之病，喘息咳唾，胸背痛，短气，寸口脉沉而迟，关上小紧', 'match_snippet': '古籍：医述\n篇名：胸痹\n属性：\\x哲言\\x胸痹与胸痞不同。胸痞有暴寒郁结于胸者；有火郁于中者；\n有寒热互郁者；有气实填胸而痞者；有气衰而成虚痞者；有肺胃津液枯涩，因燥而痞者；有上焦湿浊弥漫而痞者。若夫胸痹，但因胸中阳虚不运，久而成痹。《内经》未曾详言，惟《金匮》立方俱用辛滑温通，所云∶寸口脉沉而迟，阳微阴弦，是知但有寒证而无热证矣。治法亦惟温通上焦清阳为主。', 'score': None, 'source_file': '599-医述.txt', 'source_page': 113, 'file_path': 'classic://医述/0113-01', 'source_book': '医述', 'source_chapter': '胸痹', 'evidence_path': 'chapter://医述/胸痹', 'source_scope_path': 'book://医述/*'}
- {'evidence_type': 'factual_grounding', 'source_type': 'doc', 'source': '074-普济方.txt#60', 'snippet': '古籍：普济方\n篇名：病机论\n属性：论曰∶察病机之要理。施品味之性用。然后明病之本焉。故治病不求其本。无以去深藏之大火。\n必行可黄帝曰∶愿闻病机何如？岐伯对曰∶诸风掉眩。皆属于肝。少虑无怒。风胜则动。肝者。\n罢虑状掉摇上支两胁。膈咽不通。食饮不下。甚则耳鸣眩转。目不识人。善暴僵仆。里急 戾。胁痛呕泄。\n甚则掉眩癫疾。两胁下痛引少腹。令人怒也。虚则目视KT KT 无所见。善恐如人将捕之。\n凡病肝木风疾者。以热为本。以风为标。故火本不燔。遇风烈乃焰。肝本不甚热。因金衰而王。肺金不胜心火。木来接于金。故诸病作矣。其为治也。燥胜风。王注曰∶风自木生。燥为金治辛化中则卒暴僵仆。凡治消瘅仆击。偏枯痿厥。气满', 'match_snippet': '古籍：普济方\n篇名：病机论\n属性：论曰∶察病机之要理。施品味之性用。然后明病之本焉。故治病不求其本。无以去深藏之大火。\n必行可黄帝曰∶愿闻病机何如？岐伯对曰∶诸风掉眩。皆属于肝。少虑无怒。风胜则动。肝者。\n罢虑状掉摇上支两胁。膈咽不通。食饮不下。甚则耳鸣眩转。目不识人。善暴僵仆。里急 戾。胁痛呕泄。\n甚则掉眩癫疾。两胁下痛引少腹。令人怒也。虚则目视KT KT', 'score': None, 'source_file': '074-普济方.txt', 'source_page': 60, 'file_path': 'classic://普济方/0060-01', 'source_book': '普济方', 'source_chapter': '病机论', 'evidence_path': 'chapter://普济方/病机论', 'source_scope_path': 'book://普济方/*'}

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
- list_evidence_paths: count=30
- read_evidence_path: status=ok
- search_evidence_text: status=ok

**备注**

- quick_followup_remaining_gaps:path_reasoning,comparison

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 109.9s |
| status | ok |
| final_route | hybrid |
| executed_routes | graph, retrieval |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, search_evidence_text, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 7c3089d1-ea64-48c2-ad6f-27f87000d1ea |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**病机演变与三方证的阶梯性差异**

根据《金匮要略》的论述，栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方确实体现了从“阳气不通”到“痰浊壅盛”再到“饮邪结聚”的病机递进，其组方用药的差异直接对应了病邪的深浅与兼夹。

1.  **栝楼薤白白酒汤证：核心在于“阳气不通”**。此方是胸痹的基础方，病机重点在于胸中阳气痹阻，气机不畅。方中以栝楼实宽胸涤痰，薤白辛温通阳、行气散结，借助白酒的升散温通之力，共同宣痹开结。其证以“喘息咳唾，胸背痛，短气”为主，痰浊、水饮等有形实邪尚不显著，故治法以“辛温通阳”为主。

2.  **栝楼薤白半夏汤证：病机发展为“痰浊壅盛”**。此方在白酒汤基础上加用半夏，是针对痰浊壅塞胸中，痹阻更甚的证候。加半夏旨在增强“理气化痰”之力，以蠲除壅盛之痰浊。其证在胸痹基础症状上，增加了“不得卧”或“心痛彻背”等表现，提示痰浊壅盛，气机痹阻严重，非单纯通阳所能及，必须加强化痰降逆。

3.  **枳实薤白桂枝汤证：病机深入至“饮邪结聚”**。此方去白酒，加枳实、厚朴、桂枝，其病机已从痰浊发展为水饮结聚，并兼有气滞于中、上冲之势。枳实、厚朴“破气逐饮”，行气散结之力峻猛，旨在攻逐结聚之饮邪；桂枝则平冲降逆。其证见“心中痞，留气结在胸，胸满，胁下逆抢心”，表明病位由胸扩展至心下、胁下，气滞与饮邪互结，痹阻更广更深，故治法转向“破气逐饮”。

**现代冠心病辨证的参照应用**

张仲景的这一辨证体系，为现代冠心病的辨证施治提供了清晰的阶梯框架，可与疾病的不同阶段和严重程度相对应。

*   **稳定型心绞痛**：其病机多对应于**阳气不通**或兼有轻度**痰浊**。临床表现为劳力后发作的胸闷、胸痛，休息或服药后可缓解，类似“胸背痛，短气”。治疗可参照**栝楼薤白白酒汤**或**栝楼薤白半夏汤**的思路，以通阳宣痹为主，或佐以化痰。
*   **不稳定型心绞痛**：其病机常为**痰浊壅盛**，或兼有**气滞血瘀**。临床表现为静息或轻微活动下即可发作的胸痛，程度较重，持续时间较长，不稳定，类似“心痛彻背”或“不得卧”。治疗应侧重**理气化痰、活血化瘀**，可参照**栝楼薤白半夏汤**的化痰思路，并常需配伍活血化瘀之品。
*   **急性心肌梗死**：其病机多为**痰浊、瘀血、水饮互结**，痹阻心脉，甚则阳气暴脱。临床表现为剧烈而持久的胸痛，伴濒死感，可对应“心中痞，胸满，胁下逆抢心”等气、痰、饮结聚的重证。在急危期，中医治疗需在回阳救逆、活血通脉的基础上，可借鉴**枳实薤白桂枝汤**“破气逐饮”的思路，以开结破滞，但需根据正气虚实慎重应用。

**依据**：
1.  《本草乘雅半偈》指出栝楼薤白白酒汤主治“胸痹”，体现了其通阳开痹的基础作用。
2.  《证治汇补》记载栝楼薤白半夏汤可治“食痹”，提示其证与痰食壅滞相关，病机较白酒汤更深一层。
3.  《高注金匮要略》论及枳实薤白桂枝汤方中使用枳实，突出了该方破气散结的核心治法，与“饮邪结聚”病机相合。

---
🚨 **重要医疗声明**：您提及的情况涉及需要专业医疗判断的高风险场景。本系统仅提供中医历史文献知识，无法替代执业医师的诊断与治疗方案。请立即就医或拨打急救电话，不要仅依靠本工具的信息做出医疗决策。

**依据来源**

- 019-本经逢原/None
- 515-高注金匮要略/None
- 289-证治汇补/None
- 014-本草乘雅半偈/None
- 医述/胸痹
- 普济方/胸痹心下坚痹痞急（附论）

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '019-本经逢原', 'snippet': '薤白白酒汤专用以泄胸中痹气也', 'score': 1.084, 'predicate': '使用药材', 'target': '薤白', 'source_book': '019-本经逢原', 'source_chapter': None, 'evidence_path': 'book://本经逢原/*', 'source_scope_path': 'book://本经逢原/*', 'anchor_entity': '栝楼薤白白酒汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '515-高注金匮要略', 'snippet': '枳实（四枚） 薤白（半斤） 桂枝（一两） 浓朴（四两） 栝蒌实（一枚捣）', 'score': 1.084, 'predicate': '使用药材', 'target': '枳实', 'source_book': '515-高注金匮要略', 'source_chapter': None, 'evidence_path': 'book://高注金匮要略/*', 'source_scope_path': 'book://高注金匮要略/*', 'anchor_entity': '枳实薤白桂枝汤'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '289-证治汇补', 'snippet': '薤白半夏汤治之', 'score': 1.084, 'predicate': '治疗疾病', 'target': '食痹', 'source_book': '289-证治汇补', 'source_chapter': None, 'evidence_path': 'book://证治汇补/*', 'source_scope_path': 'book://证治汇补/*', 'anchor_entity': '栝楼薤白半夏汤'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=hybrid'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://栝楼薤白半夏汤/*; reason=先获取栝楼薤白半夏汤的核心证据（如组成、功效），为三方比较奠定基础。', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=compare-formulas; path=entity://枳实薤白桂枝汤/*; reason=接着获取枳实薤白桂枝汤的核心证据，以支持与栝楼薤白半夏汤的阶梯性差异比较。', 'skill': 'compare-formulas'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=trace-graph-path; path=symptom://胸痹/syndrome_chain; reason=需要获取从症状到证候的辨证链，以支持‘阳气不通—痰浊壅盛—饮邪结聚’的病机演变论证。', 'skill': 'trace-graph-path'}
- {'stage': 'search_evidence_text', 'label': '补充文本检索', 'detail': 'round=2; action=2; skill=search-source-text; path=chapter://医述/胸痹; reason=在已有章节范围内搜索原文，补充病机演变的古籍或教材出处佐证。', 'skill': 'search-source-text'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=3; gaps=path_reasoning,comparison'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=3; backend=planner_llm; actions=1'}

**Tool Trace**

- tcm_route_search: final_route=hybrid; status=ok
- list_evidence_paths: count=30
- read_evidence_path: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- search_evidence_text: status=ok
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_4:quality_gaps_persist:comparison
- deep_round_limit_reached


## q10 四逆散与三类厥冷鉴别

**题目**

《伤寒论》四逆散（甘草、枳实、柴胡、芍药）被后世视为“疏肝理气之祖”，但其原条文主治“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。请从“阳郁于里”而非“阳虚”的角度，解释四逆散证“四逆”的病理机制，并论述其与四逆汤证、当归四逆汤证在手足逆冷上的鉴别要点，以及为何方中不用附子、干姜而用柴胡、枳实。

### 对比摘要

| 模式 | status | final_route | generation_backend | latency | factual | case |
| --- | --- | --- | --- | --- | --- | --- |
| quick | ok | graph | grounded_llm | 46.4s | 3 | 0 |
| deep | ok | graph | planner_llm | 71.4s | 6 | 0 |

### Quick

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 46.4s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | grounded_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 321cdb3d-a553-4fef-ab78-00651f4cafad |
| factual_evidence_count | 3 |
| case_reference_count | 0 |

**答案正文**

**结论**
四逆散证的“四逆”核心病机是“阳郁于里”，即阳气内郁、不能外达四肢所致，与四逆汤证的“阳虚阴盛”、当归四逆汤证的“血虚寒凝”有本质区别。因此，方中不用附子、干姜温阳，而用柴胡、枳实疏达郁阳、调畅气机。

**主治**
四逆散原方主治《伤寒论》少阴病篇所述“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。其核心症状是手足不温（四逆），并伴有一系列或然症，提示病机关键在于气机郁滞，而非单纯的虚寒。

**病机**
从“阳郁于里”角度解释：四逆散证的“四逆”并非阳气虚衰，而是由于肝气郁结或邪气内阻，导致阳气被郁遏在体内，不能畅达于四肢末梢。阳气本身不虚，但因气机不畅而布散受阻，故表现为手足逆冷。方中选用柴胡升发疏达、透解郁热，枳实行气破结、开泄气郁，二者相配，一升一降，旨在疏通气机、透达郁阳，使内郁之阳气得以宣通外达，则四肢自温。这正是不用附子、干姜等大辛大热之品温补阳气，而用柴胡、枳实调畅气机的根本原因。

**鉴别**
在手足逆冷（四逆）的鉴别上：
1.  **四逆散证**：属“阳郁”致厥。手足逆冷程度相对较轻，常冷不过肘膝，且多伴有胸胁胀闷、腹痛、泄利下重等气机郁滞症状，其本质是气郁，非阳虚。
2.  **四逆汤证**：属“阳虚阴盛”致厥。手足逆冷严重，常冷过肘膝，并伴有全身性的虚寒征象，如畏寒蜷卧、下利清谷、脉微欲绝等。其病机为心肾阳衰，阴寒内盛，故用附子、干姜大辛大热以回阳救逆。
3.  **当归四逆汤证**：属“血虚寒凝”致厥。手足逆冷，多伴有麻木、疼痛，或肢体青紫，其病机在于营血亏虚，复感寒邪，寒凝经脉，气血运行不畅。故方中以养血通脉为主，兼以温经散寒。

依据：
1.  图谱关系显示，四逆汤证的治疗证候为四逆汤（出自《经方实验录》）。
2.  图谱关系显示，当归四逆汤证的治疗证候为当归四逆汤（出自《章次公医案》）。
3.  关于四逆散证的“阳郁”病机及与四逆汤的鉴别，主要基于对《伤寒论》原文及后世主流医家论述的共识性解读，当前提供的图谱证据对此核心病机论述的文献摘录有所缺失。

**依据来源**

- 679-章次公医案/None
- 672-经方实验录/None
- 460-类证活人书/None
- 679-章次公医案 盖当归四逆汤证也
- 672-经方实验录 所犯为四逆汤证，则投以四逆汤
- 460-类证活人书 有当归四逆汤证

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '679-章次公医案', 'snippet': '盖当归四逆汤证也', 'score': 1.084, 'predicate': '治疗证候', 'target': '当归四逆汤', 'source_book': '679-章次公医案', 'source_chapter': None, 'evidence_path': 'book://章次公医案/*', 'source_scope_path': 'book://章次公医案/*', 'anchor_entity': '当归四逆汤证'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '672-经方实验录', 'snippet': '所犯为四逆汤证，则投以四逆汤', 'score': 1.084, 'predicate': '治疗证候', 'target': '四逆汤', 'source_book': '672-经方实验录', 'source_chapter': None, 'evidence_path': 'book://经方实验录/*', 'source_scope_path': 'book://经方实验录/*', 'anchor_entity': '四逆汤证'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '460-类证活人书', 'snippet': '有当归四逆汤证', 'score': 0.6691, 'predicate': '治疗证候', 'target': '当归四逆加茱萸生姜汤', 'source_book': '460-类证活人书', 'source_chapter': None, 'evidence_path': 'book://类证活人书/*', 'source_scope_path': 'book://类证活人书/*', 'anchor_entity': '当归四逆汤证'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'quick; gaps=comparison'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'quick_followup'}
- {'stage': 'quick_followup', 'label': '快速补证据', 'detail': 'actions=2; gaps=comparison'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'quick_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=17
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- -

### Deep

| 字段 | 值 |
| --- | --- |
| ok | yes |
| latency | 71.4s |
| status | ok |
| final_route | graph |
| executed_routes | graph |
| generation_backend | planner_llm |
| tool_trace_tools | tcm_route_search, list_evidence_paths, read_evidence_path, read_evidence_path, read_evidence_path, read_evidence_path |
| fallback_detected | no |
| trace_id | 5fab6e3e-3ff2-4b2c-8956-c473adfda3f9 |
| factual_evidence_count | 6 |
| case_reference_count | 0 |

**答案正文**

**结论**
四逆散证的“四逆”源于阳气内郁、不达四末，与四逆汤证的阳虚阴盛、当归四逆汤证的血虚寒凝有本质区别。其方不用附子、干姜温阳，而用柴胡、枳实透邪解郁、调畅气机，正为疏解阳郁而设。

**主治**
四逆散在《伤寒论》中主治“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。后世将其视为疏肝理气的基础方，其应用已从原文的少阴病证拓展至肝脾气郁、阳郁不伸所致的多种杂病。

**病机**
四逆散证手足逆冷的根本病机是“阳郁于里”，而非阳气虚衰。患者阳气本身不虚，但因气机郁滞（尤其是肝脾气机郁结），导致阳气被郁遏在体内，不能外达于四肢末梢，故出现手足不温的“四逆”之象。这种郁热可能内扰于胸腹，故伴随出现咳、悸、腹痛、泄利下重等一系列或然症。方中不用附子、干姜等大辛大热之品回阳救逆，而选用柴胡升发透邪、疏解郁结，枳实破气散结、宣通胃络，二者一升一降，共奏调畅气机、透达郁阳之效，佐以芍药、甘草柔肝缓急，使郁阳得伸，四逆自愈。正如《医方论》指出，此方功效在于“散郁热，达阳邪”。

**鉴别**
四逆散证、四逆汤证与当归四逆汤证虽均有手足逆冷，但病机与治法迥异：
1.  **四逆散证**：属“阳郁致厥”。手足逆冷程度相对较轻，范围多限于手足，且常伴有胸胁脘腹不舒、脉弦等气郁征象。治宜透邪解郁、疏理气机。
2.  **四逆汤证**：属“阳虚致厥”。因少阴阳气衰微，阴寒内盛所致。手足逆冷严重，常过肘过膝，全身伴见畏寒蜷卧、下利清谷、脉微欲绝等一派虚寒危象。治宜回阳救逆，方用附子、干姜等大热之品急温其阳。
3.  **当归四逆汤证**：属“血虚寒凝致厥”。因营血亏虚，复感寒邪，寒凝经脉，气血运行不畅所致。手足逆冷多伴有麻木、疼痛，或见肢体青紫，脉细欲绝。治宜温经散寒、养血通脉，方用当归、桂枝、细辛等温通血脉。

依据：
1. 《医方论》指出四逆散功效为“散郁热，达阳邪”。
2. 《医宗金鉴》认为四逆散能“和表解肌，疏通气血”。
3. 《经方实验录》与《章次公医案》分别记载了四逆汤证与当归四逆汤证的治疗实践，可作为鉴别参考。

**依据来源**

- 679-章次公医案/None
- 089-医方论/None
- 672-经方实验录/None
- 575-医宗金鉴/None
- 460-类证活人书/None
- 084-汤头歌诀/None

**事实证据摘要**

- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '679-章次公医案', 'snippet': '盖当归四逆汤证也', 'score': 1.084, 'predicate': '治疗证候', 'target': '当归四逆汤', 'source_book': '679-章次公医案', 'source_chapter': None, 'evidence_path': 'book://章次公医案/*', 'source_scope_path': 'book://章次公医案/*', 'anchor_entity': '当归四逆汤证'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '089-医方论', 'snippet': '四逆散乃表里并治之剂。故但用枳实以散郁热，仍用柴胡以达阳邪，阳邪外泄，则手足自温矣', 'score': 1.084, 'predicate': '功效', 'target': '表里并治，散郁热，达阳邪', 'source_book': '089-医方论', 'source_chapter': None, 'evidence_path': 'book://医方论/*', 'source_scope_path': 'book://医方论/*', 'anchor_entity': '四逆散'}
- {'evidence_type': 'factual_grounding', 'source_type': 'graph', 'source': '672-经方实验录', 'snippet': '所犯为四逆汤证，则投以四逆汤', 'score': 1.084, 'predicate': '治疗证候', 'target': '四逆汤', 'source_book': '672-经方实验录', 'source_chapter': None, 'evidence_path': 'book://经方实验录/*', 'source_scope_path': 'book://经方实验录/*', 'anchor_entity': '四逆汤证'}

**案例证据摘要**

- -

**规划/执行摘要**

- {'stage': 'route_search', 'label': '执行首轮检索', 'detail': 'route=graph'}
- {'stage': 'inspect_paths', 'label': '整理证据路径', 'detail': 'derive_from_route_payload'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=1; gaps=comparison,path_reasoning,source_trace'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=1; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=1; skill=compare-formulas; path=entity://四逆汤证/*; reason=获取四逆汤证的核心证据，为比较做准备', 'skill': 'compare-formulas'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=1; action=2; skill=trace-graph-path; path=entity://四逆散/推荐证候; reason=从方剂出发，追溯其治疗证候（阳郁于里）的病理机制路径', 'skill': 'trace-graph-path'}
- {'stage': 'gap_check', 'label': '分析证据缺口', 'detail': 'round=2; gaps=comparison,path_reasoning,source_trace'}
- {'stage': 'planner', 'label': '规划下一步检索', 'detail': 'round=2; backend=planner_llm; actions=2'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=1; skill=read-syndrome-treatment; path=entity://四逆散/功效; reason=获取四逆散的核心功效，以支持从‘阳郁于里’角度解释病理机制', 'skill': 'read-syndrome-treatment'}
- {'stage': 'read_evidence_path', 'label': '读取证据路径', 'detail': 'round=2; action=2; skill=compare-formulas; path=entity://当归四逆汤证/*; reason=为比较题补充当归四逆汤证的证据，完成与四逆汤证、四逆散证的鉴别', 'skill': 'compare-formulas'}
- {'stage': 'coverage_ok', 'label': '证据覆盖满足', 'detail': 'round=2'}
- {'stage': 'answer_synthesis', 'label': '生成最终答案', 'detail': 'deep_grounded_answer'}

**Tool Trace**

- tcm_route_search: final_route=graph; status=ok
- list_evidence_paths: count=17
- read_evidence_path: status=ok
- read_evidence_path: status=empty
- read_evidence_path: status=ok
- read_evidence_path: status=ok

**备注**

- deep_round_1:quality_gaps_persist:comparison,path_reasoning,source_trace
- deep_round_2:coverage_sufficient
