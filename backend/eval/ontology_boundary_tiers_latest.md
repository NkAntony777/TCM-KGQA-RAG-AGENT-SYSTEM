# Ontology Boundary Tier Audit

- 生成时间：`2026-04-13 21:15:15 +0800`
- 数据库：`D:\毕业设计数据处理\langchain-miniopenclaw\backend\services\graph_service\data\graph_runtime.db`
- 受审谓词数：`5`
- in-schema：`2121369`
- acceptable_polysemy：`96036`
- review_needed：`35600`
- likely_dirty：`7072`

## 治疗证候

- 期望 subject types：`formula, herb, medicine`
- 期望 object types：`syndrome`
- in-schema：`56848`
- acceptable_polysemy：`6692`
- review_needed：`1625`
- likely_dirty：`923`

| tier | subject_type | object_type | count |
| --- | --- | --- | ---: |
| acceptable_polysemy | disease | syndrome | 4235 |
| acceptable_polysemy | symptom | syndrome | 1559 |
| acceptable_polysemy | therapy | syndrome | 898 |
| review_needed | disease | formula | 608 |
| review_needed | syndrome | syndrome | 380 |
| review_needed | disease | therapy | 218 |
| review_needed | disease | herb | 196 |
| likely_dirty | other | syndrome | 155 |
| likely_dirty | symptom | herb | 145 |
| review_needed | syndrome | herb | 116 |

### acceptable_polysemy
- `disease -> syndrome`: `AD病 -> 少阴病` @ `048-思考中医`
- `disease -> syndrome`: `KT逆 -> 实证` @ `583-医学正传`
- `disease -> syndrome`: `KT逆 -> 虚证` @ `583-医学正传`
- `symptom -> syndrome`: `一妇心痛唇红虫痛症 -> 虫痛之症` @ `396-孙文垣医案`
- `symptom -> syndrome`: `一月两至 -> 血热` @ `200-邯郸遗稿`

### review_needed
- `disease -> formula`: `HT症 -> 甘桔汤` @ `341-喉舌备要秘旨`
- `syndrome -> syndrome`: `《巢氏病源》小儿遗尿候 -> 膀胱有冷不能约于水` @ `156-幼幼新书`
- `syndrome -> syndrome`: `上盛下虚 -> 阳盛阴虚` @ `613-药症忌宜`
- `disease -> formula`: `上马痈、下马痈 -> 内托羌活汤` @ `575-医宗金鉴`
- `disease -> formula`: `上马痈、下马痈 -> 托里透脓汤` @ `575-医宗金鉴`

### likely_dirty
- `formula -> therapy`: `三才配合龟甲、磁朱，及复脉汤去姜、桂，入鸡子黄之属 -> 安摄其子母` @ `280-医学从众录`
- `channel -> herb`: `三焦 -> 全当归` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 制香附` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 棉 皮` @ `475-重订通俗伤寒论`
- `channel -> herb`: `三焦 -> 焦山栀` @ `475-重订通俗伤寒论`
## 治疗症状

- 期望 subject types：`formula, herb, medicine`
- 期望 object types：`symptom`
- in-schema：`583755`
- acceptable_polysemy：`49019`
- review_needed：`25291`
- likely_dirty：`832`

| tier | subject_type | object_type | count |
| --- | --- | --- | ---: |
| acceptable_polysemy | therapy | symptom | 41638 |
| review_needed | other | symptom | 12872 |
| review_needed | channel | symptom | 8425 |
| acceptable_polysemy | disease | symptom | 5962 |
| review_needed | symptom | therapy | 1707 |
| acceptable_polysemy | food | symptom | 1419 |
| review_needed | symptom | symptom | 912 |
| review_needed | syndrome | symptom | 760 |
| review_needed | symptom | herb | 615 |
| likely_dirty | category | symptom | 149 |

### acceptable_polysemy
- `disease -> symptom`: `HT风 -> 得之数` @ `442-内经药瀹`
- `therapy -> symptom`: `KT粪杓上竹箍烧灰 -> 赤白蛇缠` @ `255-急救广生集`
- `therapy -> symptom`: `《千金》灸法 -> 口中肿，腥臭` @ `156-幼幼新书`
- `therapy -> symptom`: `《千金方》狂癫吐舌灸法 -> 狂癫吐舌` @ `054-医心方`
- `therapy -> symptom`: `《千金方》狂言妄语灸法 -> 狂言妄语` @ `054-医心方`

### review_needed
- `symptom -> therapy`: `一二岁者目赤 -> 大指小指间后寻` @ `298-针灸聚英`
- `symptom -> therapy`: `一切内伤 -> 内关穴` @ `577-医学入门`
- `symptom -> therapy`: `一切冷惫 -> 关元` @ `298-针灸聚英`
- `symptom -> therapy`: `一切气症 -> 气海针灸` @ `297-针灸易学`
- `symptom -> herb`: `一切气痛 -> 丁香` @ `013-本草纲目`

### likely_dirty
- `symptom -> formula`: `一切气痛 -> 木香磨酒` @ `573-古今医鉴`
- `formula -> disease`: `三白散 -> 冒暑霍乱` @ `013-本草纲目`
- `other -> other`: `三里 -> 手足不` @ `299-针灸大成`
- `symptom -> disease`: `上胞肿 -> 脾伤` @ `188-慈幼便览`
- `symptom -> disease`: `下胞青色 -> 胃有风` @ `188-慈幼便览`
## 归经

- 期望 subject types：`herb, medicine`
- 期望 object types：`channel, other, property`
- in-schema：`17584`
- acceptable_polysemy：`499`
- review_needed：`2126`
- likely_dirty：`437`

| tier | subject_type | object_type | count |
| --- | --- | --- | ---: |
| review_needed | other | channel | 617 |
| review_needed | property | channel | 414 |
| acceptable_polysemy | formula | channel | 326 |
| review_needed | disease | channel | 315 |
| review_needed | category | channel | 217 |
| review_needed | symptom | channel | 193 |
| acceptable_polysemy | food | channel | 173 |
| likely_dirty | channel | herb | 167 |
| review_needed | therapy | channel | 151 |
| likely_dirty | channel | other | 149 |

### acceptable_polysemy
- `formula -> channel`: `丁香柿蒂汤 -> 足阳明、少阴` @ `087-医方集解`
- `formula -> channel`: `三仙丹 -> 足阳明、手足太阴` @ `087-医方集解`
- `formula -> channel`: `三因独活寄生汤 -> 足少阴厥阴` @ `560-玉机微义`
- `formula -> channel`: `三因肾着汤 -> 足少阴` @ `560-玉机微义`
- `formula -> channel`: `三解汤 -> 足少阳经` @ `087-医方集解`

### review_needed
- `syndrome -> channel`: `《巢氏病源》小儿遗尿候 -> 足太阴经` @ `156-幼幼新书`
- `syndrome -> channel`: `《巢氏病源》小儿遗尿候 -> 足少阴经` @ `156-幼幼新书`
- `book -> other`: `《神农指迷》 -> 脏腑学说` @ `699-名老中医之路`
- `other -> channel`: `一月胎胚 -> 足厥阴肝经` @ `180-张氏妇科`
- `therapy -> channel`: `三关 -> 左手应心肝，右手应脾肺` @ `299-针灸大成`

### likely_dirty
- `channel -> property`: `三焦 -> 相火之宅` @ `447-难经正义`
- `channel -> other`: `三焦经 -> 阳池` @ `455-难经古义`
- `channel -> property`: `厥阴 -> 多血少气` @ `441-内经评文`
- `channel -> herb`: `厥阴经 -> 柴胡` @ `008-汤液本草`
- `channel -> herb`: `厥阴经 -> 青皮` @ `008-汤液本草`
## 使用药材

- 期望 subject types：`formula, medicine`
- 期望 object types：`herb`
- in-schema：`1459341`
- acceptable_polysemy：`39216`
- review_needed：`5930`
- likely_dirty：`4825`

| tier | subject_type | object_type | count |
| --- | --- | --- | ---: |
| acceptable_polysemy | therapy | herb | 18611 |
| acceptable_polysemy | disease | herb | 13341 |
| acceptable_polysemy | syndrome | herb | 3936 |
| acceptable_polysemy | symptom | herb | 3328 |
| likely_dirty | herb | herb | 2748 |
| review_needed | formula | medicine | 2327 |
| likely_dirty | other | herb | 946 |
| review_needed | formula | formula | 757 |
| likely_dirty | channel | herb | 699 |
| likely_dirty | herb | formula | 432 |

### acceptable_polysemy
- `disease -> herb`: `HT皮疮 -> 大黄` @ `282-医门补要`
- `disease -> herb`: `HT皮疮 -> 生石膏` @ `282-医门补要`
- `disease -> herb`: `HT皮疮 -> 芙蓉叶` @ `282-医门补要`
- `disease -> herb`: `HT皮疮 -> 青黛` @ `282-医门补要`
- `disease -> herb`: `HT皮疮 -> 黄柏` @ `282-医门补要`

### review_needed
- `book -> herb`: `《丹溪心法》 -> 大黄` @ `277-医略`
- `book -> herb`: `《丹溪心法》 -> 黄芩` @ `277-医略`
- `book -> herb`: `《丹溪心法》 -> 黄连` @ `277-医略`
- `book -> herb`: `《别录》 -> 赤小豆` @ `013-本草纲目`
- `book -> herb`: `《别录》 -> 青葙` @ `013-本草纲目`

### likely_dirty
- `other -> herb`: `一妇怀孕内热咳嗽 -> 条芩` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 枳壳` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 栝蒌仁` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 桑白皮` @ `396-孙文垣医案`
- `other -> herb`: `一妇怀孕内热咳嗽 -> 甘草` @ `396-孙文垣医案`
## 推荐方剂

- 期望 subject types：`disease, syndrome`
- 期望 object types：`formula`
- in-schema：`3841`
- acceptable_polysemy：`610`
- review_needed：`628`
- likely_dirty：`55`

| tier | subject_type | object_type | count |
| --- | --- | --- | ---: |
| acceptable_polysemy | symptom | formula | 462 |
| review_needed | symptom | therapy | 195 |
| review_needed | formula | formula | 174 |
| acceptable_polysemy | therapy | formula | 148 |
| review_needed | herb | formula | 92 |
| review_needed | disease | therapy | 45 |
| review_needed | medicine | formula | 42 |
| likely_dirty | disease | herb | 28 |
| review_needed | book | formula | 24 |
| likely_dirty | disease | food | 21 |

### acceptable_polysemy
- `symptom -> formula`: `三焦胀 -> 枳壳青皮饮` @ `257-症因脉治`
- `symptom -> formula`: `上气喘嗽烦热食即吐逆 -> 沙糖姜汁煎方` @ `013-本草纲目`
- `symptom -> formula`: `下痢禁口 -> 沙糖乌梅煎` @ `013-本草纲目`
- `symptom -> formula`: `下血不止 -> 济阴返魂丹` @ `254-急救良方`
- `symptom -> formula`: `不能食而瘦 -> 四君子汤` @ `215-杂病广要`

### review_needed
- `formula -> formula`: `Ƭˮ塣 -> Сð` @ `203-婴童类萃`
- `formula -> formula`: `《三因》白花蛇膏方 -> 通天再造散` @ `013-本草纲目`
- `formula -> syndrome`: `丁香柿蒂汤 -> 阴饮上逆` @ `494-伤寒指掌`
- `formula -> formula`: `三品一条枪 -> 健脾之药` @ `223-疡医大全`
- `formula -> formula`: `三品一条枪 -> 玉红膏` @ `223-疡医大全`

### likely_dirty
- `disease -> herb`: `五更泻 -> 补骨脂、肉豆蔻` @ `303-李翰卿`
- `disease -> food`: `产后 -> 白粥干菜` @ `123-女科切要`
- `therapy -> food`: `妊娠一月 -> 大麦` @ `542-寿世保元`
- `therapy -> food`: `妊娠四月 -> 稻粳` @ `542-寿世保元`
- `therapy -> food`: `妊娠四月 -> 鱼雁` @ `542-寿世保元`
