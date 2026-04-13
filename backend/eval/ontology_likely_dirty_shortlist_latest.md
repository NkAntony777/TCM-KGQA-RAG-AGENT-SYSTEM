# Ontology Likely-Dirty Shortlist

- 生成时间：`2026-04-13 19:44:33 +0800`
- 来源审计时间：`2026-04-13 19:41:03 +0800`
- 涉及谓词数：`5`
- likely_dirty 总量：`8936`

## 全局优先处理组合

| predicate | subject_type | object_type | count |
| --- | --- | --- | ---: |
| 使用药材 | herb | herb | 2748 |
| 使用药材 | category | herb | 1063 |
| 使用药材 | other | herb | 946 |
| 使用药材 | channel | herb | 699 |
| 归经 | channel | channel | 446 |
| 使用药材 | herb | formula | 432 |
| 治疗症状 | book | symptom | 191 |
| 归经 | channel | herb | 167 |
| 治疗症状 | chapter | symptom | 164 |
| 治疗证候 | other | syndrome | 155 |
| 归经 | channel | other | 149 |
| 治疗症状 | category | symptom | 149 |

## 治疗证候

- likely_dirty：`923`
- 建议动作：`candidate_for_small_batch_cleanup`

| subject_type | object_type | count |
| --- | --- | ---: |
| other | syndrome | 155 |
| symptom | herb | 145 |
| symptom | formula | 80 |
| syndrome | formula | 44 |
| herb | processing_method | 34 |
| medicine | processing_method | 33 |

来源书籍 Top:
- `137-儿科要略`: `65`
- `008-汤液本草`: `58`
- `013-本草纲目`: `37`
- `037-本草害利`: `35`
- `027-本草述钩元`: `32`

代表样本:
- `formula -> therapy`: `三才配合龟甲、磁朱，及复脉汤去姜、桂，入鸡子黄之属 -> 安摄其子母` @ `280-医学从众录`
- `channel -> herb`: `三焦 -> 全当归` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 制香附` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 棉 皮` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 焦山栀` @ `475-重订通俗伤寒论`

## 治疗症状

- likely_dirty：`1187`
- 建议动作：`candidate_for_small_batch_cleanup`

| subject_type | object_type | count |
| --- | --- | ---: |
| book | symptom | 191 |
| chapter | symptom | 164 |
| category | symptom | 149 |
| symptom | disease | 132 |
| symptom | channel | 121 |
| symptom | formula | 75 |

来源书籍 Top:
- `299-针灸大成`: `127`
- `013-本草纲目`: `94`
- `353-凌门传授铜人指穴`: `78`
- `300-针灸逢源`: `62`
- `573-古今医鉴`: `59`

代表样本:
- `book -> symptom`: `《温热论》 -> 舌生芒刺` @ `402-热病衡正`
- `book -> symptom`: `《温病条辨》 -> 舌苔老黄，甚则黑有芒刺` @ `402-热病衡正`
- `book -> symptom`: `《病源论》 -> 马啮及马骨所伤刺` @ `054-医心方`
- `book -> symptom`: `《痈肿杂效方》 -> 热肿` @ `075-肘后备急方`
- `book -> symptom`: `《肘后方》 -> 大渴不止` @ `384-吴医汇讲`

## 归经

- likely_dirty：`883`
- 建议动作：`candidate_for_small_batch_cleanup`

| subject_type | object_type | count |
| --- | --- | ---: |
| channel | channel | 446 |
| channel | herb | 167 |
| channel | other | 149 |
| channel | property | 114 |

来源书籍 Top:
- `226-外科大成`: `138`
- `299-针灸大成`: `78`
- `316-普济方·针灸`: `44`
- `301-针灸甲乙经`: `32`
- `306-刺灸心法要诀`: `26`

代表样本:
- `channel -> channel`: `丁心 -> 心经` @ `295-针灸大全`
- `channel -> channel`: `三焦 -> 关冲` @ `331-针灸问对`
- `channel -> channel`: `三焦 -> 少阳` @ `366-侣山堂类辩`
- `channel -> channel`: `三焦 -> 手少阳` @ `103-华佗神方`
- `channel -> channel`: `三焦 -> 手少阳` @ `454-难经集注`

## 使用药材

- likely_dirty：`5888`
- 建议动作：`candidate_for_small_batch_cleanup`

| subject_type | object_type | count |
| --- | --- | ---: |
| herb | herb | 2748 |
| category | herb | 1063 |
| other | herb | 946 |
| channel | herb | 699 |
| herb | formula | 432 |

来源书籍 Top:
- `013-本草纲目`: `953`
- `647-万病回春`: `295`
- `051-千金翼方`: `281`
- `643-证治准绳·疡医`: `207`
- `608-丹台玉案`: `164`

代表样本:
- `other -> herb`: `一妇怀孕内热咳嗽 -> 条芩` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 枳壳` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 栝蒌仁` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 桑白皮` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 甘草` @ `396-孙文垣医案`

## 推荐方剂

- likely_dirty：`55`
- 建议动作：`candidate_for_small_batch_cleanup`

| subject_type | object_type | count |
| --- | --- | ---: |
| disease | herb | 28 |
| disease | food | 21 |
| therapy | food | 4 |

来源书籍 Top:
- `182-陈氏幼科秘诀`: `27`
- `523-千金食治`: `20`
- `542-寿世保元`: `3`
- `322-重订囊秘喉书`: `2`
- `303-李翰卿`: `1`

代表样本:
- `disease -> herb`: `五更泻 -> 补骨脂、肉豆蔻` @ `303-李翰卿`
- `disease -> food`: `产后 -> 白粥干菜` @ `123-女科切要`
- `therapy -> food`: `妊娠一月 -> 大麦` @ `542-寿世保元`
- `therapy -> food`: `妊娠四月 -> 稻粳` @ `542-寿世保元`
- `therapy -> food`: `妊娠四月 -> 鱼雁` @ `542-寿世保元`
