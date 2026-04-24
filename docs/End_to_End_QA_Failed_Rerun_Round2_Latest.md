# End-to-End QA Failed Case Rerun

## Overview

| Field | Value |
| --- | --- |
| source_report | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\end_to_end_failed_rerun_latest.json |
| timeout_s | 540.0 |
| workers | 4 |
| total_rerun | 85 |
| recovered | 12 |
| still_failed | 73 |
| recovered_rate | 0.1412 |

## By Dataset

| Dataset | Total | Recovered | Still Failed |
| --- | ---: | ---: | ---: |
| tcmeval_pa_full.json | 79 | 11 | 68 |
| tcmeval_sdt_train_full.json | 6 | 1 | 5 |

## Top Remaining Issues

- answer_option_letters_missing_any:C: 21
- answer_option_letters_missing_any:E: 12
- answer_option_letters_missing_any:D: 9
- answer_option_letters_missing_any:B: 5
- answer_option_letters_missing_any:A: 4
- request_error:ReadTimeout: 4
- answer_option_letters_missing_any:ABDE: 3
- answer_missing_any:黄芩、槐米: 3
- answer_missing_any:凡加工炮制毒性中药，必须按照当地卫生行政部门制定的炮制规范的规定进行: 2
- answer_missing_any:三棱: 2
- answer_missing_any:晚上服用: 2
- answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年: 2
- answer_missing_any:妊娠慎用药: 2
- answer_missing_any:1.5~4.5g: 2
- answer_missing_any:用量可较重: 2
- answer_missing_any:用量则更大些: 2
- answer_option_letters_missing_any:BC: 2
- answer_missing_any:6 g: 2
- answer_option_letters_missing_any:ABCDE: 2
- answer_missing_any:1/2-3/4: 2

## Results

- tcmeval_pa_full.json::tcmpa_107[deep] recovered route=hybrid original=answer_option_letters_missing_any:A rerun=ok latency_ms=70947.2
- tcmeval_pa_full.json::tcmpa_108[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:无麻醉药品处方权的医师在夜班急救需给病人使用罂粟壳时，可限开 1 日量 rerun=answer_option_letters_missing_any:D,answer_missing_any:无麻醉药品处方权的医师在夜班急救需给病人使用罂粟壳时，可限开 1 日量 latency_ms=288206.7
- tcmeval_pa_full.json::tcmpa_109[quick] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:麻醉药品专用处方应由药剂科留存 2 年备查 rerun=answer_option_letters_missing_any:E,answer_missing_any:麻醉药品专用处方应由药剂科留存 2 年备查 latency_ms=169306.0
- tcmeval_pa_full.json::tcmpa_110[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:凡加工炮制毒性中药，必须按照当地卫生行政部门制定的炮制规范的规定进行 rerun=answer_missing_any:凡加工炮制毒性中药，必须按照当地卫生行政部门制定的炮制规范的规定进行 latency_ms=194324.0
- tcmeval_pa_full.json::tcmpa_110[quick] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:凡加工炮制毒性中药，必须按照当地卫生行政部门制定的炮制规范的规定进行 rerun=answer_option_letters_missing_any:E,answer_missing_any:凡加工炮制毒性中药，必须按照当地卫生行政部门制定的炮制规范的规定进行 latency_ms=133958.4
- tcmeval_pa_full.json::tcmpa_135[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米等 rerun=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米等 latency_ms=323791.8
- tcmeval_pa_full.json::tcmpa_136[deep] recovered route=hybrid original=answer_option_letters_missing_any:B,answer_missing_any:天花粉 rerun=ok latency_ms=155238.5
- tcmeval_pa_full.json::tcmpa_136[quick] still_failed route=hybrid original=answer_option_letters_missing_any:B,answer_missing_any:天花粉 rerun=answer_option_letters_missing_any:B,answer_missing_any:天花粉 latency_ms=107722.2
- tcmeval_pa_full.json::tcmpa_137[deep] recovered route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:三棱 rerun=ok latency_ms=300742.2
- tcmeval_pa_full.json::tcmpa_137[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:三棱 rerun=answer_option_letters_missing_any:D,answer_missing_any:三棱 latency_ms=158200.6
- tcmeval_pa_full.json::tcmpa_141[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:妊娠慎用药 rerun=answer_option_letters_missing_any:C,answer_missing_any:妊娠慎用药 latency_ms=530476.3
- tcmeval_pa_full.json::tcmpa_141[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:妊娠慎用药 rerun=answer_option_letters_missing_any:C,answer_missing_any:妊娠慎用药 latency_ms=312674.4
- tcmeval_pa_full.json::tcmpa_143[deep] still_failed route=graph original=answer_option_letters_missing_any:B rerun=answer_option_letters_missing_any:B,answer_missing_any:光敏反应 latency_ms=98724.5
- tcmeval_pa_full.json::tcmpa_150[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:晚上服用 rerun=answer_option_letters_missing_any:C,answer_missing_any:晚上服用 latency_ms=90268.8
- tcmeval_pa_full.json::tcmpa_150[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:晚上服用 rerun=answer_option_letters_missing_any:C,answer_missing_any:晚上服用 latency_ms=100924.8
- tcmeval_pa_full.json::tcmpa_154[deep] still_failed route=hybrid original=answer_option_letters_missing_any:ABDE,answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年 rerun=answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年 latency_ms=104282.2
- tcmeval_pa_full.json::tcmpa_154[quick] still_failed route=hybrid original=answer_option_letters_missing_any:ABDE,answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年 rerun=answer_option_letters_missing_any:ABDE,answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年 latency_ms=139433.1
- tcmeval_pa_full.json::tcmpa_156[deep] still_failed route=hybrid original=answer_option_letters_missing_any:ABCD rerun=answer_option_letters_missing_any:ABCD latency_ms=85004.8
- tcmeval_pa_full.json::tcmpa_160[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:3~9g rerun=answer_missing_any:3~9g latency_ms=107015.2
- tcmeval_pa_full.json::tcmpa_161[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1.5~4.5g rerun=answer_missing_any:1.5~4.5g latency_ms=154951.2
- tcmeval_pa_full.json::tcmpa_161[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1.5~4.5g rerun=answer_option_letters_missing_any:C,answer_missing_any:1.5~4.5g latency_ms=59976.6
- tcmeval_pa_full.json::tcmpa_162[deep] still_failed route=hybrid original=answer_option_letters_missing_any:B,answer_missing_any:9~45g rerun=answer_option_letters_missing_any:B,answer_missing_any:9~45g latency_ms=164988.2
- tcmeval_pa_full.json::tcmpa_167[deep] still_failed route=graph original=answer_option_letters_missing_any:E,answer_missing_any:可低于新病者的剂量 rerun=answer_option_letters_missing_any:E,answer_missing_any:可低于新病者的剂量 latency_ms=28989.8
- tcmeval_pa_full.json::tcmpa_173[deep] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:用量可较重 rerun=answer_option_letters_missing_any:D,answer_missing_any:用量可较重 latency_ms=178449.7
- tcmeval_pa_full.json::tcmpa_173[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:用量可较重 rerun=answer_option_letters_missing_any:D,answer_missing_any:用量可较重 latency_ms=65297.3
- tcmeval_pa_full.json::tcmpa_174[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:用量则更大些 rerun=answer_option_letters_missing_any:E,answer_missing_any:用量则更大些 latency_ms=421238.0
- tcmeval_pa_full.json::tcmpa_174[quick] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:用量则更大些 rerun=answer_option_letters_missing_any:E,answer_missing_any:用量则更大些 latency_ms=143562.3
- tcmeval_pa_full.json::tcmpa_181[deep] still_failed route=hybrid original=answer_option_letters_missing_any:A,answer_missing_any:运用中医药学综合知识及管理学知识指导临床用药 rerun=answer_missing_any:运用中医药学综合知识及管理学知识指导临床用药 latency_ms=296875.1
- tcmeval_pa_full.json::tcmpa_191[deep] still_failed route=hybrid original=answer_option_letters_missing_any:A rerun=answer_option_letters_missing_any:A,answer_missing_any:黄芪 latency_ms=136564.8
- tcmeval_pa_full.json::tcmpa_192[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:饮用大量浓茶 rerun=answer_option_letters_missing_any:D,answer_missing_any:饮用大量浓茶 latency_ms=153261.6
- tcmeval_pa_full.json::tcmpa_194[deep] recovered route=hybrid original=answer_option_letters_missing_any:A,answer_missing_any:洗胃 rerun=ok latency_ms=205993.1
- tcmeval_pa_full.json::tcmpa_202[deep] still_failed route=hybrid original=answer_option_letters_missing_any:BC rerun=answer_option_letters_missing_any:BC latency_ms=55278.1
- tcmeval_pa_full.json::tcmpa_202[quick] still_failed route=hybrid original=answer_option_letters_missing_any:BC rerun=answer_option_letters_missing_any:BC latency_ms=34901.9
- tcmeval_pa_full.json::tcmpa_211[deep] still_failed route=hybrid original=answer_option_letters_missing_any:ABCDE rerun=answer_option_letters_missing_any:ABCDE latency_ms=184665.6
- tcmeval_pa_full.json::tcmpa_219[deep] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:6 g rerun=answer_option_letters_missing_any:D,answer_missing_any:6 g latency_ms=68203.9
- tcmeval_pa_full.json::tcmpa_219[quick] still_failed route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:6 g rerun=answer_option_letters_missing_any:D,answer_missing_any:6 g latency_ms=65172.7
- tcmeval_pa_full.json::tcmpa_233[deep] recovered route=hybrid original=answer_option_letters_missing_any:D,answer_missing_any:1/3-1/2 rerun=ok latency_ms=54554.4
- tcmeval_pa_full.json::tcmpa_234[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1/2-3/4 rerun=answer_option_letters_missing_any:C,answer_missing_any:1/2-3/4 latency_ms=94145.4
- tcmeval_pa_full.json::tcmpa_234[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1/2-3/4 rerun=answer_option_letters_missing_any:C,answer_missing_any:1/2-3/4 latency_ms=75351.9
- tcmeval_pa_full.json::tcmpa_235[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:3 倍 rerun=answer_option_letters_missing_any:C,answer_missing_any:3 倍 latency_ms=160647.2
- tcmeval_pa_full.json::tcmpa_237[deep] still_failed route=graph original=answer_option_letters_missing_any:D,answer_missing_any:300 g rerun=answer_option_letters_missing_any:D,answer_missing_any:300 g latency_ms=188326.3
- tcmeval_pa_full.json::tcmpa_237[quick] still_failed route=graph original=answer_option_letters_missing_any:D,answer_missing_any:300 g rerun=answer_option_letters_missing_any:D,answer_missing_any:300 g latency_ms=81494.0
- tcmeval_pa_full.json::tcmpa_259[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:2/3 rerun=answer_option_letters_missing_any:C,answer_missing_any:2/3 latency_ms=65133.8
- tcmeval_pa_full.json::tcmpa_259[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:2/3 rerun=answer_option_letters_missing_any:C,answer_missing_any:2/3 latency_ms=45268.3
- tcmeval_pa_full.json::tcmpa_261[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1/2~3/4 rerun=answer_missing_any:1/2~3/4 latency_ms=48027.6
- tcmeval_pa_full.json::tcmpa_261[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1/2~3/4 rerun=answer_option_letters_missing_any:C,answer_missing_any:1/2~3/4 latency_ms=91366.3
- tcmeval_pa_full.json::tcmpa_275[quick] still_failed route=graph original=answer_option_letters_missing_any:ABE rerun=answer_option_letters_missing_any:ABE latency_ms=108873.5
- tcmeval_pa_full.json::tcmpa_289[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:苦杏仁成人一日用量可达 30g rerun=answer_option_letters_missing_any:C,answer_missing_any:苦杏仁成人一日用量可达 30g latency_ms=116121.8
- tcmeval_pa_full.json::tcmpa_293[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 rerun=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 latency_ms=387558.8
- tcmeval_pa_full.json::tcmpa_293[quick] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 rerun=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 latency_ms=117743.1
- tcmeval_pa_full.json::tcmpa_295[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E rerun=answer_option_letters_missing_any:E,answer_missing_any:维生素 latency_ms=265736.1
- tcmeval_pa_full.json::tcmpa_295[quick] still_failed route=hybrid original=answer_option_letters_missing_any:E rerun=answer_option_letters_missing_any:E latency_ms=131535.5
- tcmeval_pa_full.json::tcmpa_297[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:有毒饮片必要时可双签字放行；毒性饮片超限不同意修改即使双签字也不能放行 rerun=answer_missing_any:有毒饮片必要时可双签字放行；毒性饮片超限不同意修改即使双签字也不能放行 latency_ms=265538.9
- tcmeval_pa_full.json::tcmpa_302[deep] still_failed route=hybrid original=answer_option_letters_missing_any:B,answer_missing_any:0.015～0.03g rerun=answer_option_letters_missing_any:B,answer_missing_any:0.015～0.03g latency_ms=64410.0
- tcmeval_pa_full.json::tcmpa_302[quick] still_failed route=hybrid original=answer_option_letters_missing_any:B,answer_missing_any:0.015～0.03g rerun=answer_option_letters_missing_any:B,answer_missing_any:0.015～0.03g latency_ms=55617.3
- tcmeval_pa_full.json::tcmpa_315[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:0.6～1.5g rerun=answer_option_letters_missing_any:C,answer_missing_any:0.6～1.5g latency_ms=57869.9
- tcmeval_pa_full.json::tcmpa_315[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:0.6～1.5g rerun=answer_option_letters_missing_any:C,answer_missing_any:0.6～1.5g latency_ms=83332.7
- tcmeval_pa_full.json::tcmpa_320[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:5～10g rerun=answer_option_letters_missing_any:C,answer_missing_any:5～10g latency_ms=57187.9
- tcmeval_pa_full.json::tcmpa_321[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:2～5g rerun=answer_option_letters_missing_any:C,answer_missing_any:2～5g latency_ms=227967.6
- tcmeval_pa_full.json::tcmpa_324[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1.5～3g rerun=answer_option_letters_missing_any:C,answer_missing_any:1.5～3g latency_ms=106224.6
- tcmeval_pa_full.json::tcmpa_324[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:1.5～3g rerun=answer_option_letters_missing_any:C,answer_missing_any:1.5～3g latency_ms=56330.1
- tcmeval_pa_full.json::tcmpa_326[deep] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:3～6g rerun=answer_option_letters_missing_any:C,answer_missing_any:3～6g latency_ms=108529.9
- tcmeval_pa_full.json::tcmpa_326[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:3～6g rerun=answer_option_letters_missing_any:C,answer_missing_any:3～6g latency_ms=155315.6
- tcmeval_pa_full.json::tcmpa_33[quick] recovered route=graph original=answer_option_letters_missing_any:B rerun=ok latency_ms=16045.2
- tcmeval_pa_full.json::tcmpa_39[quick] still_failed route=hybrid original=answer_option_letters_missing_any:C,answer_missing_any:每张处方不超过 2 日常用量 rerun=answer_option_letters_missing_any:C,answer_missing_any:每张处方不超过 2 日常用量 latency_ms=49805.3
- tcmeval_pa_full.json::tcmpa_4[deep] recovered route=graph original=answer_option_letters_missing_any:D rerun=ok latency_ms=15416.4
- tcmeval_pa_full.json::tcmpa_4[quick] recovered route=graph original=answer_option_letters_missing_any:D,answer_missing_any:使药 rerun=ok latency_ms=64666.3
- tcmeval_pa_full.json::tcmpa_51[deep] still_failed route=hybrid original=answer_option_letters_missing_any:A,answer_missing_any:3 -9g rerun=answer_option_letters_missing_any:A,answer_missing_any:3 -9g latency_ms=98890.0
- tcmeval_pa_full.json::tcmpa_51[quick] still_failed route=hybrid original=answer_option_letters_missing_any:A,answer_missing_any:3 -9g rerun=answer_option_letters_missing_any:A,answer_missing_any:3 -9g latency_ms=98879.7
- tcmeval_pa_full.json::tcmpa_56[quick] still_failed route=graph original=answer_option_letters_missing_any:ABCDE rerun=answer_option_letters_missing_any:ABCDE latency_ms=26024.6
- tcmeval_pa_full.json::tcmpa_62[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 rerun=answer_option_letters_missing_any:E,answer_missing_any:黄芩、槐米 latency_ms=405638.5
- tcmeval_pa_full.json::tcmpa_67[deep] recovered route=graph original=answer_option_letters_missing_any:ABCDE rerun=ok latency_ms=45215.1
- tcmeval_pa_full.json::tcmpa_68[deep] recovered route=graph original=answer_option_letters_missing_any:BCE rerun=ok latency_ms=44836.1
- tcmeval_pa_full.json::tcmpa_68[quick] still_failed route=graph original=answer_option_letters_missing_any:BCE rerun=answer_option_letters_missing_any:BCE latency_ms=69341.7
- tcmeval_pa_full.json::tcmpa_69[deep] still_failed route=hybrid original=answer_option_letters_missing_any:ABDE rerun=answer_option_letters_missing_any:ABDE latency_ms=67399.9
- tcmeval_pa_full.json::tcmpa_69[quick] still_failed route=hybrid original=answer_option_letters_missing_any:ABDE rerun=answer_option_letters_missing_any:ABDE latency_ms=65154.8
- tcmeval_pa_full.json::tcmpa_75[quick] recovered route=graph original=answer_option_letters_missing_any:E rerun=ok latency_ms=32074.4
- tcmeval_pa_full.json::tcmpa_81[deep] still_failed route=hybrid original=answer_option_letters_missing_any:E,answer_missing_any:三棱 rerun=answer_option_letters_missing_any:E,answer_missing_any:三棱 latency_ms=185520.3
- tcmeval_pa_full.json::tcmpa_88[quick] still_failed route=hybrid original=answer_option_letters_missing_any:A,answer_missing_any:川乌 rerun=answer_option_letters_missing_any:A,answer_missing_any:川乌 latency_ms=154553.8
- tcmeval_sdt_train_full.json::病例126_pathogenesis[deep] still_failed route= original=request_error:ReadTimeout rerun=request_error:ReadTimeout latency_ms=540008.5
- tcmeval_sdt_train_full.json::病例17_pathogenesis[deep] still_failed route= original=request_error:ReadTimeout rerun=request_error:ReadTimeout latency_ms=540031.7
- tcmeval_sdt_train_full.json::病例192_pathogenesis[deep] still_failed route= original=request_error:ReadTimeout rerun=request_error:ReadTimeout latency_ms=540009.6
- tcmeval_sdt_train_full.json::病例49_syndrome[deep] still_failed route=graph original=request_error:ReadTimeout rerun=answer_missing_any:肝旺湿热|心脾两虚 latency_ms=80581.8
- tcmeval_sdt_train_full.json::病例65_pathogenesis[deep] still_failed route= original=request_error:ReadTimeout rerun=request_error:ReadTimeout latency_ms=540034.5
- tcmeval_sdt_train_full.json::病例74_pathogenesis[deep] recovered route=hybrid original=request_error:ReadTimeout rerun=ok latency_ms=225821.4
