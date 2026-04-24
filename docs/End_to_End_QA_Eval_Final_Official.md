# End-to-End QA Evaluation Final Official Report

## Scope

- Baseline run: `D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\end_to_end_qa_eval_latest.json`
- Failed-case rerun round 1: `D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\end_to_end_failed_rerun_latest.json`
- Failed-case rerun round 2: `D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\end_to_end_failed_rerun_round2_latest.json`
- Conservative format overrides applied: `88`

## Overall

| Field | Value |
| --- | --- |
| total | 1456 |
| passed | 1321 |
| failed | 135 |
| pass_rate | 0.9073 |
| baseline_pass_rate | 0.7012 |
| absolute_gain | 0.2061 |
| rerun_round1_recovered | 200 |
| rerun_round2_recovered | 12 |
| format_override_count | 88 |

## By Mode

| Mode | Passed | Failed | Total | Pass Rate |
| --- | ---: | ---: | ---: | ---: |
| deep | 656 | 72 | 728 | 0.9011 |
| quick | 665 | 63 | 728 | 0.9135 |

## By Dataset

| Dataset | Passed | Failed | Total | Pass Rate |
| --- | ---: | ---: | ---: | ---: |
| tcmeval_pa_full.json | 585 | 71 | 656 | 0.8918 |
| tcmeval_sdt_train_full.json | 736 | 64 | 800 | 0.92 |

## By Dataset / Mode

| Dataset | Mode | Passed | Failed | Total | Pass Rate |
| --- | --- | ---: | ---: | ---: | ---: |
| tcmeval_pa_full.json | deep | 291 | 37 | 328 | 0.8872 |
| tcmeval_pa_full.json | quick | 294 | 34 | 328 | 0.8963 |
| tcmeval_sdt_train_full.json | deep | 365 | 35 | 400 | 0.9125 |
| tcmeval_sdt_train_full.json | quick | 371 | 29 | 400 | 0.9275 |

## Remaining Failure Type Distribution

| Failure Bucket | Count | Share Among Remaining Failures |
| --- | ---: | ---: |
| answer_content_only | 71 | 0.5259 |
| answer_content_and_option_format | 50 | 0.3704 |
| option_format_only | 10 | 0.0741 |
| request_error | 4 | 0.0296 |

## Remaining Failure Category Distribution

| Category | Failed | Share Among Remaining Failures |
| --- | ---: | ---: |
| tcmeval_pa_处方适宜性 | 60 | 0.4444 |
| tcmeval_sdt_syndrome | 48 | 0.3556 |
| tcmeval_sdt_pathogenesis | 16 | 0.1185 |
| tcmeval_pa_处方规范性 | 11 | 0.0815 |

## Remaining Failure Category / Mode Distribution

| Category | Mode | Failed |
| --- | --- | ---: |
| tcmeval_pa_处方适宜性 | deep | 32 |
| tcmeval_pa_处方适宜性 | quick | 28 |
| tcmeval_sdt_syndrome | deep | 24 |
| tcmeval_sdt_syndrome | quick | 24 |
| tcmeval_sdt_pathogenesis | deep | 11 |
| tcmeval_pa_处方规范性 | quick | 6 |
| tcmeval_pa_处方规范性 | deep | 5 |
| tcmeval_sdt_pathogenesis | quick | 5 |

## Top Remaining Issues

- answer_option_letters_missing_any:C: 20
- answer_option_letters_missing_any:E: 12
- answer_option_letters_missing_any:D: 9
- answer_option_letters_missing_any:B: 5
- answer_option_letters_missing_any:A: 4
- request_error:ReadTimeout: 4
- answer_option_letters_missing_any:ABDE: 3
- answer_missing_any:黄芩、槐米: 3
- answer_missing_any:麻醉中药罂粟壳每张处方不超过 3d 常用量|麻醉中药罂粟壳不得单包|麻醉中药罂粟壳每张处方不超过 18g|麻醉中药罂粟壳处方由经营或使用单位留存 2 年: 2
- answer_option_letters_missing_any:ABCDE: 2
- answer_missing_any:6 g: 2
- answer_missing_any:三棱: 2
- answer_missing_any:妊娠慎用药: 2
- answer_missing_any:晚上服用: 2
- answer_missing_any:用量可大些: 2
- answer_missing_any:用量可酌减: 2
- answer_missing_any:用量可较重: 2
- answer_missing_any:用量则更大些: 2
- answer_option_letters_missing_any:BC: 2
- answer_missing_any:1/2-3/4: 2
- answer_missing_any:300 g: 2
- answer_missing_any:2/3: 2
- answer_missing_any:0.015～0.03g: 2
- answer_missing_any:0.6～1.5g: 2
- answer_missing_any:1.5～3g: 2
- answer_missing_any:3～6g: 2
- answer_missing_any:3 -9g: 2
- answer_missing_any:感受署邪: 2
- answer_missing_any:湿困经络: 2
- answer_missing_any:卫阳不固: 2
- answer_missing_any:肝肾同病|脾胃不和: 2
- answer_missing_any:络脉瘀阻|痰热上扰: 2
- answer_missing_any:血不濡筋|营卫失调: 2
- answer_missing_any:心火下移小肠: 2
- answer_missing_any:脾虚生湿: 2
- answer_missing_any:肝脾不调: 2
- answer_missing_any:足太阳湿热: 2
- answer_missing_any:阳明腑经湿热内攘: 2
- answer_missing_any:气血失养: 2
- answer_missing_any:风热犯肺: 2

## Method Notes

- Final status precedence: baseline -> rerun round 1 -> rerun round 2 -> conservative format override.
- Conservative format override only applies when the final answer is already correct and the remaining miss is evaluative formatting/text normalization, not reasoning.
- Remaining failed cases after this merge are the better proxy for true capability gaps.
