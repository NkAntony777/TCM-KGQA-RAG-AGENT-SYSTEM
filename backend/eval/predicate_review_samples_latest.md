# Predicate Review Samples

| 字段 | 值 |
| --- | --- |
| generated_at | 2026-04-13 14:31:17 +0800 |
| source_json | predicate_normalization_candidates_latest.json |
| candidate_count | 30 |

## 审阅优先级建议

- 先审 `manual_review_required` 与 `risk=high`。
- 再审 `family_only` 是否只是查询层归族，不触发物理改写。
- 最后确认低风险直接归一项是否真的满足值域与类型一致性。

## 高风险 / 人工审核样本

### `药性`

| 字段 | 值 |
| --- | --- |
| count | 47833 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `property`: 25711
- `medicine` -> `property`: 18548
- `food` -> `property`: 2289
- `formula` -> `property`: 663
- `herb` -> `processing_method`: 132
- `other` -> `property`: 127

**样本条目**

- `木瓜` --药性--> `温` (`food` -> `property`, 004-食疗本草)
- `芰实` --药性--> `平` (`food` -> `property`, 004-食疗本草)
- `荏子` --药性--> `温` (`medicine` -> `property`, 004-食疗本草)
- `荏子叶` --药性--> `温` (`medicine` -> `property`, 004-食疗本草)
- `菘菜` --药性--> `温` (`food` -> `property`, 004-食疗本草)
- `蒲桃` --药性--> `平` (`food` -> `property`, 004-食疗本草)

### `食忌`

| 字段 | 值 |
| --- | --- |
| count | 30188 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `food`: 13818
- `herb` -> `food`: 2138
- `disease` -> `food`: 2106
- `food` -> `food`: 1784
- `medicine` -> `food`: 1644
- `food` -> `other`: 1032

**样本条目**

- `甘草` --食忌--> `猪肉` (`herb` -> `food`, 011-本草品汇精要)
- `豆黄` --食忌--> `猪肉` (`herb` -> `food`, 011-本草品汇精要)
- `半夏` --食忌--> `饴糖羊肉` (`medicine` -> `food`, 041-炮炙大法)
- `商陆` --食忌--> `犬肉` (`medicine` -> `food`, 041-炮炙大法)
- `地黄` --食忌--> `萝卜` (`medicine` -> `food`, 041-炮炙大法)
- `天门冬` --食忌--> `鲤鱼` (`medicine` -> `food`, 041-炮炙大法)

### `配伍禁忌`

| 字段 | 值 |
| --- | --- |
| count | 22241 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `herb`: 6423
- `medicine` -> `herb`: 2445
- `herb` -> `other`: 1850
- `medicine` -> `medicine`: 1588
- `medicine` -> `other`: 1577
- `herb` -> `property`: 1026

**样本条目**

- `甘遂` --配伍禁忌--> `甘草` (`medicine` -> `herb`, 016-本草易读)
- `苦参` --配伍禁忌--> `藜芦` (`herb` -> `herb`, 044-要药分剂)
- `细辛` --配伍禁忌--> `反藜芦` (`herb` -> `herb`, 542-寿世保元)
- `香附` --配伍禁忌--> `忌铁器` (`herb` -> `other`, 542-寿世保元)
- `薤白` --配伍禁忌--> `牛肉` (`herb` -> `food`, 011-本草品汇精要)
- `阿胶` --配伍禁忌--> `畏大黄` (`medicine` -> `other`, 011-本草品汇精要)

### `关联术语`

| 字段 | 值 |
| --- | --- |
| count | 11123 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `other`: 11123

**样本条目**

- `一扫光药膏` --关联术语--> `黄水疮` (`formula` -> `other`, TCM-MKG)
- `一把抓` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `脾胃不和证` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `积滞` (`formula` -> `other`, TCM-MKG)
- `一捻金胶囊` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)

### `升降浮沉`

| 字段 | 值 |
| --- | --- |
| count | 2311 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `property`: 1313
- `medicine` -> `property`: 813
- `property` -> `property`: 169
- `food` -> `property`: 6
- `other` -> `property`: 4
- `formula` -> `property`: 3

**样本条目**

- `巴戟天` --升降浮沉--> `可升可降` (`herb` -> `property`, 044-要药分剂)
- `远志` --升降浮沉--> `可升可降` (`herb` -> `property`, 044-要药分剂)
- `川芎` --升降浮沉--> `升` (`herb` -> `property`, 017-本草新编)
- `浓朴` --升降浮沉--> `可升可降` (`medicine` -> `property`, 017-本草新编)
- `女贞子` --升降浮沉--> `降` (`herb` -> `property`, 637-景岳全书)
- `川芎` --升降浮沉--> `升` (`herb` -> `property`, 637-景岳全书)

### `出处`

| 字段 | 值 |
| --- | --- |
| count | 214 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `book`: 142
- `book` -> `book`: 19
- `book` -> `other`: 9
- `other` -> `book`: 9
- `formula` -> `chapter`: 7
- `herb` -> `book`: 7

**样本条目**

- `三化汤` --出处--> `拔粹` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `乌药平气汤` --出处--> `三因方` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `二陈汤` --出处--> `疟门` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `五丹丸` --出处--> `血证类` (`formula` -> `chapter`, 067-仁斋直指方论（附补遗）)
- `五积散` --出处--> `中寒门` (`formula` -> `chapter`, 067-仁斋直指方论（附补遗）)
- `五积散` --出处--> `和剂方` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)

### `利水化饮`

| 字段 | 值 |
| --- | --- |
| count | 7 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `therapy`: 7

**样本条目**

- `大腹皮` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `白术` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `砂仁` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `苍术` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `莱菔子` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `防己` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)

### `理气活血`

| 字段 | 值 |
| --- | --- |
| count | 4 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `therapy`: 4

**样本条目**

- `丹参` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `薄荷` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `陈皮` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `青皮` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)

### `欲解时`

| 字段 | 值 |
| --- | --- |
| count | 1 |
| proposed_action | keep |
| proposed_target | - |
| risk | high |

**类型分布**

- `disease` -> `other`: 1

**样本条目**

- `太阴病` --欲解时--> `从亥至丑上` (`disease` -> `other`, 638-订正仲景全书伤寒论注)

## 全量关系样本摘要

| predicate | count | action | target | risk |
| --- | ---: | --- | --- | --- |
| 使用药材 | 1510375 | keep | - | low |
| 治疗症状 | 659252 | keep | - | low |
| 作用靶点 | 305445 | keep | - | medium |
| 治疗疾病 | 292621 | keep | - | low |
| 功效 | 167536 | keep | - | low |
| 用法 | 154143 | keep | - | low |
| 含有成分 | 120520 | keep | - | medium |
| 常见症状 | 97745 | keep | - | low |
| 属于范畴 | 76063 | keep | - | low |
| 现代适应证 | 69429 | keep | - | medium |
| 治疗证候 | 66088 | keep | - | low |
| 药性 | 47833 | manual_review_required | - | high |
| 别名 | 42722 | keep | - | low |
| 治法 | 38418 | keep | - | low |
| 五味 | 35835 | keep | - | low |
| 食忌 | 30188 | manual_review_required | - | high |
| 关联靶点 | 24403 | keep | - | medium |
| 配伍禁忌 | 22241 | manual_review_required | - | high |
| 归经 | 21092 | keep | - | low |
| 关联术语 | 11123 | manual_review_required | - | high |
| 推荐方剂 | 5134 | keep | - | low |
| 药性特征 | 2383 | family_only | 药性 | medium |
| 升降浮沉 | 2311 | manual_review_required | - | high |
| 药味 | 2047 | family_only | 五味 | medium |
| 药材基源 | 1789 | keep | - | medium |
| 出处 | 214 | manual_review_required | - | high |
| 利水化饮 | 7 | manual_review_required | - | high |
| 理气活血 | 4 | manual_review_required | - | high |
| 适应证 | 3 | family_only | 现代适应证 | medium |
| 欲解时 | 1 | keep | - | high |

## 全量关系样本明细

### `使用药材`

| 字段 | 值 |
| --- | --- |
| count | 1510375 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `herb`: 1457544
- `therapy` -> `herb`: 18611
- `disease` -> `herb`: 13341
- `syndrome` -> `herb`: 3936
- `symptom` -> `herb`: 3328
- `herb` -> `herb`: 2748

**样本条目**

- `七宝美髯丹` --使用药材--> `何首乌` (`formula` -> `herb`, 089-医方论)
- `七宝美髯丹` --使用药材--> `当归` (`formula` -> `herb`, 089-医方论)
- `七宝美髯丹` --使用药材--> `枸杞` (`formula` -> `herb`, 089-医方论)
- `七宝美髯丹` --使用药材--> `牛膝` (`formula` -> `herb`, 089-医方论)
- `七宝美髯丹` --使用药材--> `白茯苓` (`formula` -> `herb`, 089-医方论)
- `七宝美髯丹` --使用药材--> `破故纸` (`formula` -> `herb`, 089-医方论)

### `治疗症状`

| 字段 | 值 |
| --- | --- |
| count | 659252 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `symptom`: 465289
- `herb` -> `symptom`: 79119
- `therapy` -> `symptom`: 41638
- `medicine` -> `symptom`: 39347
- `other` -> `symptom`: 12872
- `channel` -> `symptom`: 8425

**样本条目**

- `三才封髓丹` --治疗症状--> `梦遗走泄` (`formula` -> `symptom`, 089-医方论)
- `唐郑相国方` --治疗症状--> `喘咳` (`formula` -> `symptom`, 089-医方论)
- `唐郑相国方` --治疗症状--> `腰脚痛` (`formula` -> `symptom`, 089-医方论)
- `四君子汤加竹沥姜汁方` --治疗症状--> `半身不遂` (`formula` -> `symptom`, 089-医方论)
- `四逆汤` --治疗症状--> `四肢厥逆` (`formula` -> `symptom`, 089-医方论)
- `大陷胸丸` --治疗症状--> `上焦喘满` (`formula` -> `symptom`, 089-医方论)

### `作用靶点`

| 字段 | 值 |
| --- | --- |
| count | 305445 |
| proposed_action | keep |
| proposed_target | - |
| risk | medium |

**类型分布**

- `ingredient` -> `gene`: 305445

**样本条目**

- `AABTWRKUKUPMJG-UHFFFAOYSA-N` --作用靶点--> `GRHPR` (`ingredient` -> `gene`, TCM-MKG)
- `AABWXKZJSNWRSH-UHFFFAOYSA-N` --作用靶点--> `APEX1` (`ingredient` -> `gene`, TCM-MKG)
- `AABWXKZJSNWRSH-UHFFFAOYSA-N` --作用靶点--> `SLC9A2` (`ingredient` -> `gene`, TCM-MKG)
- `AAGFPTSOPGCENQ-UHFFFAOYSA-N` --作用靶点--> `OSR1` (`ingredient` -> `gene`, TCM-MKG)
- `AAGFPTSOPGCENQ-UHFFFAOYSA-N` --作用靶点--> `PGBD1` (`ingredient` -> `gene`, TCM-MKG)
- `AAGFPTSOPGCENQ-UHFFFAOYSA-N` --作用靶点--> `CA5B` (`ingredient` -> `gene`, TCM-MKG)

### `治疗疾病`

| 字段 | 值 |
| --- | --- |
| count | 292621 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `disease`: 214960
- `herb` -> `disease`: 34386
- `medicine` -> `disease`: 21866
- `therapy` -> `disease`: 10092
- `disease` -> `disease`: 2172
- `other` -> `disease`: 1242

**样本条目**

- `三白汤` --治疗疾病--> `内伤` (`formula` -> `disease`, 089-医方论)
- `大顺散` --治疗疾病--> `暑月伤寒` (`formula` -> `disease`, 089-医方论)
- `导气汤` --治疗疾病--> `疝` (`formula` -> `disease`, 089-医方论)
- `小陷胸汤` --治疗疾病--> `小结胸` (`formula` -> `disease`, 089-医方论)
- `橘核丸` --治疗疾病--> `疝` (`formula` -> `disease`, 089-医方论)
- `水解散` --治疗疾病--> `瘟疫` (`formula` -> `disease`, 089-医方论)

### `功效`

| 字段 | 值 |
| --- | --- |
| count | 167536 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `herb` -> `therapy`: 40449
- `medicine` -> `therapy`: 27081
- `formula` -> `therapy`: 26833
- `herb` -> `property`: 21051
- `formula` -> `property`: 20834
- `herb` -> `other`: 10590

**样本条目**

- `七味白术散` --功效--> `去热治泻` (`formula` -> `other`, 089-医方论)
- `七宝美髯丹` --功效--> `温补命肾、兼摄纳下元` (`formula` -> `other`, 089-医方论)
- `三承气汤` --功效--> `救人于存亡危急之时` (`formula` -> `other`, 089-医方论)
- `人参养营汤` --功效--> `三阴并补，气血交养` (`formula` -> `other`, 089-医方论)
- `侯氏黑散` --功效--> `平肝息风` (`formula` -> `therapy`, 089-医方论)
- `倒仓法` --功效--> `补脾、祛除垢滞` (`therapy` -> `other`, 089-医方论)

### `用法`

| 字段 | 值 |
| --- | --- |
| count | 154143 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `processing_method`: 99112
- `herb` -> `processing_method`: 28464
- `medicine` -> `processing_method`: 17806
- `therapy` -> `processing_method`: 4534
- `disease` -> `processing_method`: 1521
- `food` -> `processing_method`: 735

**样本条目**

- `大头天行疫病方` --用法--> `白水煎` (`formula` -> `processing_method`, 071-医方集宜)
- `普济消毒饮子` --用法--> `白水煎` (`formula` -> `processing_method`, 071-医方集宜)
- `漏芦方` --用法--> `白水煎` (`formula` -> `processing_method`, 071-医方集宜)
- `疫病肿大方` --用法--> `姜汁为丸，井花水调蜜化下` (`formula` -> `processing_method`, 071-医方集宜)
- `葳蕤散` --用法--> `白水煎` (`formula` -> `processing_method`, 071-医方集宜)
- `虾蟆瘟敷药` --用法--> `捣汁调敷` (`formula` -> `processing_method`, 071-医方集宜)

### `含有成分`

| 字段 | 值 |
| --- | --- |
| count | 120520 |
| proposed_action | keep |
| proposed_target | - |
| risk | medium |

**类型分布**

- `herb` -> `ingredient`: 120520

**样本条目**

- `一支箭` --含有成分--> `ASUTZQLVASHGKV-JDFRZJQESA-N` (`herb` -> `ingredient`, TCM-MKG)
- `一支箭` --含有成分--> `CKAHWDNDUGDSLE-ARLBYUKCSA-N` (`herb` -> `ingredient`, TCM-MKG)
- `一支箭` --含有成分--> `VHYYSQODIQWPDO-PILAGYSTSA-N` (`herb` -> `ingredient`, TCM-MKG)
- `一支箭` --含有成分--> `WXZAKVLYZHWSNF-KBRIMQKVSA-N` (`herb` -> `ingredient`, TCM-MKG)
- `一支箭` --含有成分--> `XGVJWXAYKUHDOO-DANNLKNASA-N` (`herb` -> `ingredient`, TCM-MKG)
- `一支箭` --含有成分--> `YLWAQARRNQVEHD-GQAVTEOGSA-N` (`herb` -> `ingredient`, TCM-MKG)

### `常见症状`

| 字段 | 值 |
| --- | --- |
| count | 97745 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `disease` -> `symptom`: 56334
- `syndrome` -> `symptom`: 16653
- `symptom` -> `symptom`: 6889
- `channel` -> `symptom`: 6637
- `other` -> `symptom`: 4258
- `formula` -> `symptom`: 2197

**样本条目**

- `阳毒` --常见症状--> `发热` (`syndrome` -> `symptom`, 089-医方论)
- `阳毒` --常见症状--> `斑疹` (`syndrome` -> `symptom`, 089-医方论)
- `阳毒` --常见症状--> `烦躁` (`syndrome` -> `symptom`, 089-医方论)
- `阳陷入阴` --常见症状--> `面黄、气弱、发热` (`syndrome` -> `symptom`, 089-医方论)
- `阴毒` --常见症状--> `下利` (`syndrome` -> `symptom`, 089-医方论)
- `阴毒` --常见症状--> `腹痛` (`syndrome` -> `symptom`, 089-医方论)

### `属于范畴`

| 字段 | 值 |
| --- | --- |
| count | 76063 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `category`: 25825
- `herb` -> `category`: 16918
- `disease` -> `category`: 7316
- `channel` -> `category`: 4645
- `other` -> `category`: 3188
- `medicine` -> `category`: 2124

**样本条目**

- `三家洗碗水` --属于范畴--> `水部第五卷水之二` (`herb` -> `category`, 013-本草纲目)
- `两头蛇` --属于范畴--> `鳞部第四十三卷\鳞之二` (`herb` -> `category`, 013-本草纲目)
- `五敛子` --属于范畴--> `果部第三十一卷果之三` (`herb` -> `category`, 013-本草纲目)
- `仙人杖` --属于范畴--> `木部木之五` (`herb` -> `category`, 013-本草纲目)
- `便闭` --属于范畴--> `小儿初生诸病` (`symptom` -> `category`, 013-本草纲目)
- `剪刀股` --属于范畴--> `金石部金石之一` (`herb` -> `category`, 013-本草纲目)

### `现代适应证`

| 字段 | 值 |
| --- | --- |
| count | 69429 |
| proposed_action | keep |
| proposed_target | - |
| risk | medium |

**类型分布**

- `formula` -> `disease`: 69429

**样本条目**

- `一扫光药膏` --现代适应证--> `继发性皮肤脓疱病` (`formula` -> `disease`, TCM-MKG)
- `一扫光药膏` --现代适应证--> `播散性皮肤单纯疱疹感染合并其他皮肤病` (`formula` -> `disease`, TCM-MKG)
- `一扫光药膏` --现代适应证--> `眼睑的特应性湿疹` (`formula` -> `disease`, TCM-MKG)
- `一扫光药膏` --现代适应证--> `眼睑脂溢性皮炎` (`formula` -> `disease`, TCM-MKG)
- `一扫光药膏` --现代适应证--> `其他特指的眼睑皮炎或湿疹` (`formula` -> `disease`, TCM-MKG)
- `一扫光药膏` --现代适应证--> `未特指的眼睑皮炎或湿疹` (`formula` -> `disease`, TCM-MKG)

### `治疗证候`

| 字段 | 值 |
| --- | --- |
| count | 66088 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `syndrome`: 53968
- `disease` -> `syndrome`: 4235
- `herb` -> `syndrome`: 2453
- `symptom` -> `syndrome`: 1559
- `therapy` -> `syndrome`: 898
- `disease` -> `formula`: 608

**样本条目**

- `三才封髓丹` --治疗证候--> `龙雷之火不安` (`formula` -> `syndrome`, 089-医方论)
- `三黄石膏汤` --治疗证候--> `三焦郁热，毒火炽盛` (`formula` -> `syndrome`, 089-医方论)
- `人参固本丸` --治疗证候--> `火旺克金` (`formula` -> `syndrome`, 089-医方论)
- `六味地黄丸` --治疗证候--> `肝肾不足` (`formula` -> `syndrome`, 089-医方论)
- `四逆散` --治疗证候--> `热结于内，阳气不能外达` (`formula` -> `syndrome`, 089-医方论)
- `四逆汤` --治疗证候--> `伤寒少阴症` (`formula` -> `syndrome`, 089-医方论)

### `药性`

| 字段 | 值 |
| --- | --- |
| count | 47833 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `property`: 25711
- `medicine` -> `property`: 18548
- `food` -> `property`: 2289
- `formula` -> `property`: 663
- `herb` -> `processing_method`: 132
- `other` -> `property`: 127

**样本条目**

- `木瓜` --药性--> `温` (`food` -> `property`, 004-食疗本草)
- `芰实` --药性--> `平` (`food` -> `property`, 004-食疗本草)
- `荏子` --药性--> `温` (`medicine` -> `property`, 004-食疗本草)
- `荏子叶` --药性--> `温` (`medicine` -> `property`, 004-食疗本草)
- `菘菜` --药性--> `温` (`food` -> `property`, 004-食疗本草)
- `蒲桃` --药性--> `平` (`food` -> `property`, 004-食疗本草)

### `别名`

| 字段 | 值 |
| --- | --- |
| count | 42722 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `herb` -> `herb`: 18697
- `formula` -> `formula`: 6422
- `medicine` -> `medicine`: 2916
- `disease` -> `disease`: 2325
- `herb` -> `other`: 2302
- `medicine` -> `other`: 2223

**样本条目**

- `乌喙` --别名--> `两头尖` (`herb` -> `herb`, 013-本草纲目)
- `五倍子` --别名--> `草零` (`herb` -> `other`, 013-本草纲目)
- `五敛子` --别名--> `五棱子` (`herb` -> `herb`, 013-本草纲目)
- `五敛子` --别名--> `阳桃` (`herb` -> `herb`, 013-本草纲目)
- `何首乌` --别名--> `交藤` (`herb` -> `herb`, 013-本草纲目)
- `何首乌` --别名--> `地精` (`herb` -> `herb`, 013-本草纲目)

### `治法`

| 字段 | 值 |
| --- | --- |
| count | 38418 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `formula` -> `therapy`: 13594
- `disease` -> `therapy`: 12867
- `therapy` -> `therapy`: 3776
- `syndrome` -> `therapy`: 3063
- `symptom` -> `therapy`: 2497
- `channel` -> `therapy`: 710

**样本条目**

- `五积散` --治法--> `发表温中` (`formula` -> `therapy`, 089-医方论)
- `伤寒` --治法--> `发表用麻黄、桂枝，温中用干姜、附子` (`disease` -> `therapy`, 089-医方论)
- `大承气汤` --治法--> `攻下` (`formula` -> `therapy`, 089-医方论)
- `小柴胡汤` --治法--> `和解表里` (`formula` -> `therapy`, 089-医方论)
- `水解散` --治法--> `发表攻里` (`formula` -> `therapy`, 089-医方论)
- `痰火内蕴外风乘之证` --治法--> `化痰` (`syndrome` -> `therapy`, 089-医方论)

### `五味`

| 字段 | 值 |
| --- | --- |
| count | 35835 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `herb` -> `property`: 19967
- `medicine` -> `property`: 12542
- `food` -> `property`: 1787
- `other` -> `property`: 488
- `category` -> `property`: 258
- `channel` -> `property`: 246

**样本条目**

- `龙葵` --五味--> `苦` (`medicine` -> `property`, 004-食疗本草)
- `龟甲` --五味--> `酸` (`medicine` -> `property`, 004-食疗本草)
- `地笋` --五味--> `甘` (`herb` -> `property`, 011-本草品汇精要)
- `婆娑石` --五味--> `淡` (`medicine` -> `property`, 011-本草品汇精要)
- `炉甘石` --五味--> `甘` (`medicine` -> `property`, 011-本草品汇精要)
- `白豆蔻` --五味--> `辛` (`herb` -> `property`, 011-本草品汇精要)

### `食忌`

| 字段 | 值 |
| --- | --- |
| count | 30188 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `food`: 13818
- `herb` -> `food`: 2138
- `disease` -> `food`: 2106
- `food` -> `food`: 1784
- `medicine` -> `food`: 1644
- `food` -> `other`: 1032

**样本条目**

- `甘草` --食忌--> `猪肉` (`herb` -> `food`, 011-本草品汇精要)
- `豆黄` --食忌--> `猪肉` (`herb` -> `food`, 011-本草品汇精要)
- `半夏` --食忌--> `饴糖羊肉` (`medicine` -> `food`, 041-炮炙大法)
- `商陆` --食忌--> `犬肉` (`medicine` -> `food`, 041-炮炙大法)
- `地黄` --食忌--> `萝卜` (`medicine` -> `food`, 041-炮炙大法)
- `天门冬` --食忌--> `鲤鱼` (`medicine` -> `food`, 041-炮炙大法)

### `关联靶点`

| 字段 | 值 |
| --- | --- |
| count | 24403 |
| proposed_action | keep |
| proposed_target | - |
| risk | medium |

**类型分布**

- `disease` -> `gene`: 24403

**样本条目**

- `不稳定性心绞痛` --关联靶点--> `ACE` (`disease` -> `gene`, TCM-MKG)
- `不稳定性心绞痛` --关联靶点--> `ADAMTS7` (`disease` -> `gene`, TCM-MKG)
- `不稳定性心绞痛` --关联靶点--> `ADM` (`disease` -> `gene`, TCM-MKG)
- `不稳定性心绞痛` --关联靶点--> `AGER` (`disease` -> `gene`, TCM-MKG)
- `不稳定性心绞痛` --关联靶点--> `AGT` (`disease` -> `gene`, TCM-MKG)
- `不稳定性心绞痛` --关联靶点--> `AGTR1` (`disease` -> `gene`, TCM-MKG)

### `配伍禁忌`

| 字段 | 值 |
| --- | --- |
| count | 22241 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `herb`: 6423
- `medicine` -> `herb`: 2445
- `herb` -> `other`: 1850
- `medicine` -> `medicine`: 1588
- `medicine` -> `other`: 1577
- `herb` -> `property`: 1026

**样本条目**

- `甘遂` --配伍禁忌--> `甘草` (`medicine` -> `herb`, 016-本草易读)
- `苦参` --配伍禁忌--> `藜芦` (`herb` -> `herb`, 044-要药分剂)
- `细辛` --配伍禁忌--> `反藜芦` (`herb` -> `herb`, 542-寿世保元)
- `香附` --配伍禁忌--> `忌铁器` (`herb` -> `other`, 542-寿世保元)
- `薤白` --配伍禁忌--> `牛肉` (`herb` -> `food`, 011-本草品汇精要)
- `阿胶` --配伍禁忌--> `畏大黄` (`medicine` -> `other`, 011-本草品汇精要)

### `归经`

| 字段 | 值 |
| --- | --- |
| count | 21092 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `herb` -> `channel`: 11612
- `medicine` -> `channel`: 5954
- `other` -> `channel`: 617
- `channel` -> `channel`: 446
- `property` -> `channel`: 414
- `formula` -> `channel`: 326

**样本条目**

- `咸` --归经--> `肾` (`other` -> `other`, 013-本草纲目)
- `天门冬` --归经--> `手太阴经、足少阴经` (`herb` -> `channel`, 013-本草纲目)
- `甘` --归经--> `脾` (`other` -> `other`, 013-本草纲目)
- `白芷` --归经--> `阳明经` (`herb` -> `channel`, 013-本草纲目)
- `石胆` --归经--> `少阳胆经` (`herb` -> `channel`, 013-本草纲目)
- `缩砂密` --归经--> `手足太阳经` (`herb` -> `channel`, 013-本草纲目)

### `关联术语`

| 字段 | 值 |
| --- | --- |
| count | 11123 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `other`: 11123

**样本条目**

- `一扫光药膏` --关联术语--> `黄水疮` (`formula` -> `other`, TCM-MKG)
- `一把抓` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `脾胃不和证` (`formula` -> `other`, TCM-MKG)
- `一捻金` --关联术语--> `积滞` (`formula` -> `other`, TCM-MKG)
- `一捻金胶囊` --关联术语--> `消食导滞` (`formula` -> `other`, TCM-MKG)

### `推荐方剂`

| 字段 | 值 |
| --- | --- |
| count | 5134 |
| proposed_action | keep |
| proposed_target | - |
| risk | low |

**类型分布**

- `disease` -> `formula`: 3434
- `symptom` -> `formula`: 462
- `syndrome` -> `formula`: 407
- `symptom` -> `therapy`: 195
- `formula` -> `formula`: 174
- `therapy` -> `formula`: 148

**样本条目**

- `蚱蝉` --推荐方剂--> `蚱蝉丸` (`herb` -> `formula`, 013-本草纲目)
- `蚱蝉` --推荐方剂--> `蚱蝉散` (`herb` -> `formula`, 013-本草纲目)
- `蚱蝉` --推荐方剂--> `蚱蝉汤` (`herb` -> `formula`, 013-本草纲目)
- `湿疟` --推荐方剂--> `除湿汤` (`disease` -> `formula`, 205-金匮翼)
- `治疗暴赤目痛方` --推荐方剂--> `四物汤` (`formula` -> `formula`, 013-本草纲目)
- `治走马牙疳方` --推荐方剂--> `甘露饮` (`formula` -> `formula`, 013-本草纲目)

### `药性特征`

| 字段 | 值 |
| --- | --- |
| count | 2383 |
| proposed_action | family_only |
| proposed_target | 药性 |
| risk | medium |

**类型分布**

- `herb` -> `property`: 2383

**样本条目**

- `一支箭` --药性特征--> `Liver meridian` (`herb` -> `property`, TCM-MKG)
- `丁茄` --药性特征--> `Stomach meridian` (`herb` -> `property`, TCM-MKG)
- `丁茄` --药性特征--> `Lung meridian` (`herb` -> `property`, TCM-MKG)
- `丁香` --药性特征--> `Stomach meridian` (`herb` -> `property`, TCM-MKG)
- `丁香` --药性特征--> `Spleen meridian` (`herb` -> `property`, TCM-MKG)
- `丁香` --药性特征--> `Kidney meridian` (`herb` -> `property`, TCM-MKG)

### `升降浮沉`

| 字段 | 值 |
| --- | --- |
| count | 2311 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `property`: 1313
- `medicine` -> `property`: 813
- `property` -> `property`: 169
- `food` -> `property`: 6
- `other` -> `property`: 4
- `formula` -> `property`: 3

**样本条目**

- `巴戟天` --升降浮沉--> `可升可降` (`herb` -> `property`, 044-要药分剂)
- `远志` --升降浮沉--> `可升可降` (`herb` -> `property`, 044-要药分剂)
- `川芎` --升降浮沉--> `升` (`herb` -> `property`, 017-本草新编)
- `浓朴` --升降浮沉--> `可升可降` (`medicine` -> `property`, 017-本草新编)
- `女贞子` --升降浮沉--> `降` (`herb` -> `property`, 637-景岳全书)
- `川芎` --升降浮沉--> `升` (`herb` -> `property`, 637-景岳全书)

### `药味`

| 字段 | 值 |
| --- | --- |
| count | 2047 |
| proposed_action | family_only |
| proposed_target | 五味 |
| risk | medium |

**类型分布**

- `herb` -> `property`: 2047

**样本条目**

- `一支箭` --药味--> `Sweet medicinal` (`herb` -> `property`, TCM-MKG)
- `一支箭` --药味--> `Bitter medicinal` (`herb` -> `property`, TCM-MKG)
- `一枝蒿` --药味--> `Pungent medicinal` (`herb` -> `property`, TCM-MKG)
- `一枝黄花` --药味--> `Pungent medicinal` (`herb` -> `property`, TCM-MKG)
- `一枝黄花` --药味--> `Bitter medicinal` (`herb` -> `property`, TCM-MKG)
- `丁公藤` --药味--> `Pungent medicinal` (`herb` -> `property`, TCM-MKG)

### `药材基源`

| 字段 | 值 |
| --- | --- |
| count | 1789 |
| proposed_action | keep |
| proposed_target | - |
| risk | medium |

**类型分布**

- `herb` -> `origin`: 1789

**样本条目**

- `一支箭` --药材基源--> `Ophioglossum pedunculosum` (`herb` -> `origin`, TCM-MKG)
- `一枝蒿` --药材基源--> `Artemisia rupestris` (`herb` -> `origin`, TCM-MKG)
- `一枝黄花` --药材基源--> `Solidago decurrens` (`herb` -> `origin`, TCM-MKG)
- `一枝黄花` --药材基源--> `Solidago altissima` (`herb` -> `origin`, TCM-MKG)
- `丁公藤` --药材基源--> `Erycibe obtusifolia` (`herb` -> `origin`, TCM-MKG)
- `丁公藤` --药材基源--> `Erycibe schmidtii` (`herb` -> `origin`, TCM-MKG)

### `出处`

| 字段 | 值 |
| --- | --- |
| count | 214 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `formula` -> `book`: 142
- `book` -> `book`: 19
- `book` -> `other`: 9
- `other` -> `book`: 9
- `formula` -> `chapter`: 7
- `herb` -> `book`: 7

**样本条目**

- `三化汤` --出处--> `拔粹` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `乌药平气汤` --出处--> `三因方` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `二陈汤` --出处--> `疟门` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)
- `五丹丸` --出处--> `血证类` (`formula` -> `chapter`, 067-仁斋直指方论（附补遗）)
- `五积散` --出处--> `中寒门` (`formula` -> `chapter`, 067-仁斋直指方论（附补遗）)
- `五积散` --出处--> `和剂方` (`formula` -> `book`, 067-仁斋直指方论（附补遗）)

### `利水化饮`

| 字段 | 值 |
| --- | --- |
| count | 7 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `therapy`: 7

**样本条目**

- `大腹皮` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `白术` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `砂仁` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `苍术` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `莱菔子` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `防己` --利水化饮--> `利水化饮` (`herb` -> `therapy`, 686-中医临证经验与方法)

### `理气活血`

| 字段 | 值 |
| --- | --- |
| count | 4 |
| proposed_action | manual_review_required |
| proposed_target | - |
| risk | high |

**类型分布**

- `herb` -> `therapy`: 4

**样本条目**

- `丹参` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `薄荷` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `陈皮` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)
- `青皮` --理气活血--> `理气活血` (`herb` -> `therapy`, 686-中医临证经验与方法)

### `适应证`

| 字段 | 值 |
| --- | --- |
| count | 3 |
| proposed_action | family_only |
| proposed_target | 现代适应证 |
| risk | medium |

**类型分布**

- `therapy` -> `syndrome`: 3

**样本条目**

- `柔肝熄风法` --适应证--> `真阴亏损，虚风内动，瘛疭瘫痪，神疲乏力，或自汗盗汗，手足心热，舌绛少苔或光剥无苔，脉虚大无根或虚而无力` (`therapy` -> `syndrome`, 686-中医临证经验与方法)
- `益气散风法` --适应证--> `气血俱虚，寒湿内蕴，外受风寒，偏瘫身重，心中寒，气短乏力，手足厥冷，舌苔薄白，脉沉细弦` (`therapy` -> `syndrome`, 686-中医临证经验与方法)
- `苦寒泻火法` --适应证--> `肝胆实火，筋脉失养，头晕头痛，烦躁易怒，轻度偏瘫，恶热，尿黄赤，舌质红苔黄或黄白，脉弦数者` (`therapy` -> `syndrome`, 686-中医临证经验与方法)

### `欲解时`

| 字段 | 值 |
| --- | --- |
| count | 1 |
| proposed_action | keep |
| proposed_target | - |
| risk | high |

**类型分布**

- `disease` -> `other`: 1

**样本条目**

- `太阴病` --欲解时--> `从亥至丑上` (`disease` -> `other`, 638-订正仲景全书伤寒论注)
