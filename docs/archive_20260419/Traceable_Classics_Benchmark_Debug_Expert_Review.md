# Traceable Classics Debug Expert Review

本文件用于人工复核 benchmark 的 `debug` 子集结果，判断当前系统返回是否属于：

- 真错
- 证据不足
- 命中不同书/不同章节但仍可接受

## Aggregate

- Files-first avg latency: `5063.8 ms`
- Files-first topk provenance hit: `0.0714`
- Files-first topk answer+provenance hit: `0.0714`
- Vector avg latency: `2976.5 ms`
- Vector topk provenance hit: `0.0`
- Vector topk answer+provenance hit: `0.0`

## tcb_f1d58e32c014_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `耳鸣耳聋通治方由哪些药材组成？请依据古籍回答并给出出处。`
- Expected Books: `070-奇效良方, 奇效良方, 奇效良方`
- Expected Chapters: `耳鸣耳聋通治方`
- Gold Answer Outline: `白蒺藜`

### Gold Evidence

```text
辣桂 川芎 当归 石菖蒲 细辛 木通 木香 白蒺藜（炒，去刺） 麻黄（去节） 甘 草（炙，各一钱）
```

### Files-first Metrics
- topk book hit: `Yes`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `62.0`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：治 耳，出脓及黄水。
白矾（粘，一钱） 胭脂（一字） 麝香（少许）上为细末，先用绵杖子缠去耳中脓水尽，另用绵杖子送药入耳中，令到底掺之。一方加黄丹龙骨。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 2
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `62.0`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：一豆三猫不出油，麝香少许用真修。
炼蜜为丸麦粒大，绵裹锭子耳中投。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 3
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `62.0`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：治耳聋。
石菖蒲（十两，一寸九节者） 苍术（五两，生用）上锉成块子，置于瓶内，以米泔浸七日取出，去苍术，只将菖蒲于甑上蒸，三两时取出焙干，捣为细末，每服二钱，糯米饮调服，日进三服。或将蒸熟者作指顶大块子，食后置口中，时时嚼动，咽津亦可。
<目录>卷之五十八\耳鸣耳聋门（附论）
```

### Vector Metrics
- topk book hit: `Yes`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.0277569392348087`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：密陀僧（一钱） 轻粉（半钱） 麝香（一字）上为细末，先以绵拭耳内脓，却掺药。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 2
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.027263007840342125`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：龙骨 枯矾 胭脂 海螵蛸（各等分） 麝香（少许）上为细末，先缴耳净，将药干掺耳中。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 3
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.025165372447512224`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：治风虚耳聋。
方见风门。
<目录>卷之五十八\耳鸣耳聋门（附论）
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_f1d58e32c014_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于耳鸣耳聋通治方组成的记载出自哪本书哪一篇？`
- Expected Books: `070-奇效良方, 奇效良方, 奇效良方`
- Expected Chapters: `耳鸣耳聋通治方`
- Gold Answer Outline: `白蒺藜`

### Gold Evidence

```text
辣桂 川芎 当归 石菖蒲 细辛 木通 木香 白蒺藜（炒，去刺） 麻黄（去节） 甘 草（炙，各一钱）
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
- Score: `47.44`
- Snippet:

```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```
#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
- Score: `47.44`
- Snippet:

```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```
#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
- Score: `43.84`
- Snippet:

```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Metrics
- topk book hit: `Yes`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.03278688524590164`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：治风虚耳聋。
方见风门。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 2
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.029083245521601686`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：上用绿矾为末，水调灌耳，立出。
<目录>卷之五十八\耳鸣耳聋门（附论）
```
#### Top 3
- Book: `奇效良方`
- Chapter: `耳鸣耳聋通治方`
- Score: `0.027912386121341344`
- Snippet:

```text
古籍：奇效良方
篇名：耳鸣耳聋通治方
属性：上用甘遂半寸，绵裹插两耳中，却将甘草口中嚼，自然听。
<目录>卷之五十八\耳鸣耳聋门（附论）
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_7d966a168564_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `如圣散由哪些药材组成？请依据古籍回答并给出出处。`
- Expected Books: `074-普济方, 普济方, 普济方`
- Expected Chapters: `沙石淋`
- Gold Answer Outline: `麦门冬`

### Gold Evidence

```text
马蔺花 麦门冬 甜葶苈 白茅根 车前子 檀香 连翘（各等分炒）
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `万氏秘传片玉心书`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：万氏秘传片玉心书
篇名：如圣散
属性：用妇人尿桶中白垢，刮取锻尽烟一钱，铜绿二分，麝香半分，共为末，以腊茶浸米泔水洗净血后，搽此药。
宣风散槟榔二个，陈皮、甘草各两半，牵牛（半生半炒），共为末，蜜水调，食前服。
<目录>卷五\牙齿门
```
#### Top 2
- Book: `仙传外科集验方`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：仙传外科集验方
篇名：如圣散
属性：治急时气缠喉风，渐入咽塞，水谷不下，牙关紧急，不省人事，并皆治之。
雄黄 藜芦（生） 白矾 牙皂（去皮、炙黄）加蝎梢七枝。
上为细末，每用一字，吹入鼻中，吐出顽痰愈矣。
又方∶用白药、山豆根同煎噙之，灌漱后咽下一二口即愈。
<目录>增添别本经验诸方
```
#### Top 3
- Book: `冯氏锦囊秘录`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：冯氏锦囊秘录
篇名：如圣散
属性：治破伤风，止血定疼。
苍术（六两） 川乌头（泡，去皮，四两） 防风 草乌头（泡，去皮） 细辛（二两五钱）天麻 川芎 两头尖（泡，去皮，四两） 白芷（各一两五钱） 蝎梢（微炒） 雄黄乳香（各五钱） 为末。每服一钱，酒调下。
\x一方\x治破伤风，用全蝎十个，为末，酒调，一日三次服之。
<目录>杂症大小合参卷八\方脉破伤风
```

### Vector Metrics
- topk book hit: `Yes`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `Yes`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `祖剂`
- Chapter: `如圣散`
- Score: `0.030798389007344232`
- Snippet:

```text
古籍：祖剂
篇名：如圣散
属性：用白茅根马蔺花麦门冬去心车前子甜葶苈苦葶苈炒檀香连翘各等分上为细末每服四煎热服如渴加黄芩同煎入烧盐少许服治沙淋小腹胀满<目录>卷之四
```
#### Top 2
- Book: `洪氏集验方`
- Chapter: `如圣散`
- Score: `0.030679156908665108`
- Snippet:

```text
古籍：洪氏集验方
篇名：如圣散
属性：治小儿一切头疮。
松脂（半两，研细） 轻粉（半两）上件和匀，油调敷之。
<目录>卷第五
```
#### Top 3
- Book: `鸡峰普济方`
- Chapter: `如圣散`
- Score: `0.030536130536130537`
- Snippet:

```text
古籍：鸡峰普济方
篇名：如圣散
属性：治风毒上攻头目遍痛焰硝（二分） 青黛（一分） 郁金 薄荷叶 川芎（各二分） 硼砂（一字）上为末鼻内搐之<目录>卷第三\伤寒中暑附
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_7d966a168564_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于如圣散组成的记载出自哪本书哪一篇？`
- Expected Books: `074-普济方, 普济方, 普济方`
- Expected Chapters: `沙石淋`
- Gold Answer Outline: `麦门冬`

### Gold Evidence

```text
马蔺花 麦门冬 甜葶苈 白茅根 车前子 檀香 连翘（各等分炒）
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `万氏秘传片玉心书`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：万氏秘传片玉心书
篇名：如圣散
属性：用妇人尿桶中白垢，刮取锻尽烟一钱，铜绿二分，麝香半分，共为末，以腊茶浸米泔水洗净血后，搽此药。
宣风散槟榔二个，陈皮、甘草各两半，牵牛（半生半炒），共为末，蜜水调，食前服。
<目录>卷五\牙齿门
```
#### Top 2
- Book: `仙传外科集验方`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：仙传外科集验方
篇名：如圣散
属性：治急时气缠喉风，渐入咽塞，水谷不下，牙关紧急，不省人事，并皆治之。
雄黄 藜芦（生） 白矾 牙皂（去皮、炙黄）加蝎梢七枝。
上为细末，每用一字，吹入鼻中，吐出顽痰愈矣。
又方∶用白药、山豆根同煎噙之，灌漱后咽下一二口即愈。
<目录>增添别本经验诸方
```
#### Top 3
- Book: `冯氏锦囊秘录`
- Chapter: `如圣散`
- Score: `62.0`
- Snippet:

```text
古籍：冯氏锦囊秘录
篇名：如圣散
属性：治破伤风，止血定疼。
苍术（六两） 川乌头（泡，去皮，四两） 防风 草乌头（泡，去皮） 细辛（二两五钱）天麻 川芎 两头尖（泡，去皮，四两） 白芷（各一两五钱） 蝎梢（微炒） 雄黄乳香（各五钱） 为末。每服一钱，酒调下。
\x一方\x治破伤风，用全蝎十个，为末，酒调，一日三次服之。
<目录>杂症大小合参卷八\方脉破伤风
```

### Vector Metrics
- topk book hit: `Yes`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `Yes`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `洪氏集验方`
- Chapter: `如圣散`
- Score: `0.030886196246139225`
- Snippet:

```text
古籍：洪氏集验方
篇名：如圣散
属性：治小儿一切头疮。
松脂（半两，研细） 轻粉（半两）上件和匀，油调敷之。
<目录>卷第五
```
#### Top 2
- Book: `祖剂`
- Chapter: `如圣散`
- Score: `0.03055037313432836`
- Snippet:

```text
古籍：祖剂
篇名：如圣散
属性：用白茅根马蔺花麦门冬去心车前子甜葶苈苦葶苈炒檀香连翘各等分上为细末每服四煎热服如渴加黄芩同煎入烧盐少许服治沙淋小腹胀满<目录>卷之四
```
#### Top 3
- Book: `鸡峰普济方`
- Chapter: `如圣散`
- Score: `0.030536130536130537`
- Snippet:

```text
古籍：鸡峰普济方
篇名：如圣散
属性：治风毒上攻头目遍痛焰硝（二分） 青黛（一分） 郁金 薄荷叶 川芎（各二分） 硼砂（一字）上为末鼻内搐之<目录>卷第三\伤寒中暑附
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_99b9dada3796_ans

- Category: `formula_indication_symptom`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `十全大补汤主要适用于什么病证或症状？请依据古籍回答并给出出处。`
- Expected Books: `416-续名医类案, 续名医类案, 续名医类案`
- Expected Chapters: `腰胁痛`
- Gold Answer Outline: `寒热`

### Gold Evidence

```text
又用十全大补汤而寒热退
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `养生类要`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：养生类要
篇名：十全大补汤
属性：治男妇诸虚不足五劳七伤生血气补脾胃即前八物汤一两加黄 一钱二分肉桂八分姜枣煎服<目录>前集\解饮食诸毒
```
#### Top 2
- Book: `冯氏锦囊秘录`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：冯氏锦囊秘录
篇名：十全大补汤
属性：治劳伤困倦，虚症峰起，发热作渴，喉痛舌裂，心神昏乱，眩晕眼花，寐而不寐，食而不化。
人参 白术（土炒） 黄 （蜜炙） 熟地（酒炒，各二钱） 茯苓（一钱） 当归（一钱五分） 白芍 川芎 甘草（炙，各八分） 肉桂（去皮，五分） 水煎服。
丹溪曰∶实火可泻，芩连之属∶虚火可补，参 之属。凡人根本受伤，虚火游行，泄越于外。
```
#### Top 3
- Book: `医方考`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：医方考
篇名：十全大补汤
属性：人参 白术（炒） 白芍药（炒） 茯苓（去皮） 黄 （炙） 当归 甘草（炙） 熟地黄 川芎（各一钱） 桂心（二分）痢疾已愈，气血大虚者，此方主之。
大虚者必大补，故用人参、黄 、白术、茯苓、甘草以补气；用当归、川芎、芍药、地黄、桂心以补血。
<目录>卷二\痢门第十一
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `时方歌括`
- Chapter: `十全大补汤`
- Score: `0.03177805800756621`
- Snippet:

```text
古籍：时方歌括
篇名：十全大补汤
属性：气血双补。十补不一泻法。
<目录>卷上\补可扶弱
```
#### Top 2
- Book: `成方切用`
- Chapter: `十全大补汤`
- Score: `0.031754032258064516`
- Snippet:

```text
古籍：成方切用
篇名：十全大补汤
属性：治痘症十日以上，血气虚弱者。
方见卷一上治气门四君子汤附方<目录>卷十一上\婴孩门
```
#### Top 3
- Book: `医方考`
- Chapter: `十全大补汤`
- Score: `0.03036576949620428`
- Snippet:

```text
古籍：医方考
篇名：十全大补汤
属性：人参 白术（炒） 白芍药（炒） 茯苓（去皮） 黄 （炙） 当归 甘草（炙） 熟地黄 川芎（各一钱） 桂心（二分）痢疾已愈，气血大虚者，此方主之。
大虚者必大补，故用人参、黄 、白术、茯苓、甘草以补气；用当归、川芎、芍药、地黄、桂心以补血。
<目录>卷二\痢门第十一
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_99b9dada3796_src

- Category: `formula_indication_symptom`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于十全大补汤主治的记载出自哪本书哪一篇？`
- Expected Books: `416-续名医类案, 续名医类案, 续名医类案`
- Expected Chapters: `腰胁痛`
- Gold Answer Outline: `寒热`

### Gold Evidence

```text
又用十全大补汤而寒热退
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `养生类要`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：养生类要
篇名：十全大补汤
属性：治男妇诸虚不足五劳七伤生血气补脾胃即前八物汤一两加黄 一钱二分肉桂八分姜枣煎服<目录>前集\解饮食诸毒
```
#### Top 2
- Book: `冯氏锦囊秘录`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：冯氏锦囊秘录
篇名：十全大补汤
属性：治劳伤困倦，虚症峰起，发热作渴，喉痛舌裂，心神昏乱，眩晕眼花，寐而不寐，食而不化。
人参 白术（土炒） 黄 （蜜炙） 熟地（酒炒，各二钱） 茯苓（一钱） 当归（一钱五分） 白芍 川芎 甘草（炙，各八分） 肉桂（去皮，五分） 水煎服。
丹溪曰∶实火可泻，芩连之属∶虚火可补，参 之属。凡人根本受伤，虚火游行，泄越于外。
```
#### Top 3
- Book: `医方考`
- Chapter: `十全大补汤`
- Score: `62.0`
- Snippet:

```text
古籍：医方考
篇名：十全大补汤
属性：人参 白术（炒） 白芍药（炒） 茯苓（去皮） 黄 （炙） 当归 甘草（炙） 熟地黄 川芎（各一钱） 桂心（二分）痢疾已愈，气血大虚者，此方主之。
大虚者必大补，故用人参、黄 、白术、茯苓、甘草以补气；用当归、川芎、芍药、地黄、桂心以补血。
<目录>卷二\痢门第十一
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `成方切用`
- Chapter: `十全大补汤`
- Score: `0.031754032258064516`
- Snippet:

```text
古籍：成方切用
篇名：十全大补汤
属性：治痘症十日以上，血气虚弱者。
方见卷一上治气门四君子汤附方<目录>卷十一上\婴孩门
```
#### Top 2
- Book: `时方歌括`
- Chapter: `十全大补汤`
- Score: `0.03131881575727918`
- Snippet:

```text
古籍：时方歌括
篇名：十全大补汤
属性：气血双补。十补不一泻法。
<目录>卷上\补可扶弱
```
#### Top 3
- Book: `太平惠民和剂局方`
- Chapter: `十全大补汤`
- Score: `0.030679156908665108`
- Snippet:

```text
古籍：太平惠民和剂局方
篇名：十全大补汤
内容：治男子、妇人诸虚不足，五劳七伤，不进饮食，久病虚损，时发潮热，气疼痛，夜梦遗精，面色萎黄，脚膝无力，一切病后气不如旧，忧愁思虑伤动血脾肾气弱，五心烦闷，并皆治之。此药性温不热，平补有效，养气育神，醒邪，温暖脾肾，其效不可具述。
人参 肉桂（去粗皮，不见火） 川芎 地黄（洗，酒蒸，焙） 茯苓（焙） 白术（焙）甘上一十味，锉为粗末。每服二大钱，水一盏，生姜三片，枣子二个，同煎至七分，不拘时候温服。
<目录>卷之五\〔吴直阁增诸家名方
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_854f4052ab6b_ans

- Category: `herb_effect`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `牛膝在古籍中的主要功效是什么？请给出依据。`
- Expected Books: `597-冯氏锦囊秘录, 冯氏锦囊秘录, 冯氏锦囊秘录`
- Expected Chapters: `五淋散`
- Gold Answer Outline: `治淋之圣药`

### Gold Evidence

```text
故牛膝为治淋之圣药。
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：吴普本草
篇名：牛膝
内容：\x《御览》卷九百九十二\x神农∶甘。一经∶酸。黄帝、扁鹊∶甘。李氏∶温。雷公∶酸，无毒。生河内或临邛。
叶如蓝，茎本赤。二月、八月采。
<目录>草木类
```
#### Top 2
- Book: `新修本草`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：新修本草
篇名：牛膝
内容：为君，味苦、酸，平，无毒。主寒湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热火烂，堕胎。疗伤中少气，男子阴消，老人失溺，补中续绝，填骨髓，除脑中痛及腰脊痛，妇人月水不通，血结，益精，利阴气，止发白。久服轻身耐老。一名百倍。生河内川谷及临朐。二恶萤火、陆英、龟甲，畏白前。今出近道蔡州者，最长大柔润，其茎有节，似牛膝，故以为名也。
```
#### Top 3
- Book: `本草乘雅半偈`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：本草乘雅半偈
篇名：牛膝
内容：（本经上品）【气味】苦酸平，无毒。
【主治】主寒湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热，火烂，堕胎。久服轻身耐老。
【核】曰∶出河内川谷及临朐，今江淮、闽越、关中亦有，不及怀庆者佳。深秋收子，初春排种其苗，方茎暴节，叶叶对生，颇似苋叶。六七月节上生花作穗，遂结实如小鼠负虫，有涩毛，贴茎倒生。根柔润而细，一直下生，长
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `牛膝`
- Score: `0.0315136476426799`
- Snippet:

```text
古籍：吴普本草
篇名：牛膝
内容：\x《御览》卷九百九十二\x神农∶甘。一经∶酸。黄帝、扁鹊∶甘。李氏∶温。雷公∶酸，无毒。生河内或临邛。
叶如蓝，茎本赤。二月、八月采。
<目录>草木类
```
#### Top 2
- Book: `神农本草经`
- Chapter: `牛膝`
- Score: `0.031024531024531024`
- Snippet:

```text
古籍：神农本草经
篇名：牛膝
内容：味苦，酸（《御览》作辛）。主寒（《御览》作伤寒）湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热火烂，堕胎。久服，轻身、耐老（《御览》作能老）。一名百倍，生川谷。
《吴普》曰∶牛膝，神农∶甘；一经∶酸；黄帝、扁鹊∶甘；李氏，温。雷公∶酸，无毒。生河内或临邛。叶如夏蓝；茎本赤。二月、八月采（《御览》）。
《名医》曰∶生河内及临朐。二月、八月、十月采根，阴干。
案∶《广雅》云∶牛茎，牛膝也；陶弘景云∶其茎有节，似膝，故以为名也。膝，当为膝。
<目录
```
#### Top 3
- Book: `神农本草经`
- Chapter: `营实`
- Score: `0.030776515151515152`
- Snippet:

```text
古籍：神农本草经
篇名：营实
内容：味酸，温。主痈疽恶创，结肉跌筋，败创，热气，阴蚀不疗，利关节。一名墙薇，一名墙麻，一名牛棘。生川谷。
《吴普》曰∶蔷薇，一名牛勒，一名牛膝，一名蔷薇，一名山枣（《御览》）。
《名医》曰∶一名牛勒，一名蔷蘼，一名山棘，生零陵及蜀郡，八月、九月采，阴干。
案∶陶弘景云∶即是墙薇子。
<目录>卷一\上经
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_854f4052ab6b_src

- Category: `herb_effect`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于牛膝功效的记载出自哪本书哪一篇？`
- Expected Books: `597-冯氏锦囊秘录, 冯氏锦囊秘录, 冯氏锦囊秘录`
- Expected Chapters: `五淋散`
- Gold Answer Outline: `治淋之圣药`

### Gold Evidence

```text
故牛膝为治淋之圣药。
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：吴普本草
篇名：牛膝
内容：\x《御览》卷九百九十二\x神农∶甘。一经∶酸。黄帝、扁鹊∶甘。李氏∶温。雷公∶酸，无毒。生河内或临邛。
叶如蓝，茎本赤。二月、八月采。
<目录>草木类
```
#### Top 2
- Book: `新修本草`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：新修本草
篇名：牛膝
内容：为君，味苦、酸，平，无毒。主寒湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热火烂，堕胎。疗伤中少气，男子阴消，老人失溺，补中续绝，填骨髓，除脑中痛及腰脊痛，妇人月水不通，血结，益精，利阴气，止发白。久服轻身耐老。一名百倍。生河内川谷及临朐。二恶萤火、陆英、龟甲，畏白前。今出近道蔡州者，最长大柔润，其茎有节，似牛膝，故以为名也。
```
#### Top 3
- Book: `本草乘雅半偈`
- Chapter: `牛膝`
- Score: `62.0`
- Snippet:

```text
古籍：本草乘雅半偈
篇名：牛膝
内容：（本经上品）【气味】苦酸平，无毒。
【主治】主寒湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热，火烂，堕胎。久服轻身耐老。
【核】曰∶出河内川谷及临朐，今江淮、闽越、关中亦有，不及怀庆者佳。深秋收子，初春排种其苗，方茎暴节，叶叶对生，颇似苋叶。六七月节上生花作穗，遂结实如小鼠负虫，有涩毛，贴茎倒生。根柔润而细，一直下生，长
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `牛膝`
- Score: `0.031754032258064516`
- Snippet:

```text
古籍：吴普本草
篇名：牛膝
内容：\x《御览》卷九百九十二\x神农∶甘。一经∶酸。黄帝、扁鹊∶甘。李氏∶温。雷公∶酸，无毒。生河内或临邛。
叶如蓝，茎本赤。二月、八月采。
<目录>草木类
```
#### Top 2
- Book: `神农本草经`
- Chapter: `牛膝`
- Score: `0.03128054740957967`
- Snippet:

```text
古籍：神农本草经
篇名：牛膝
内容：味苦，酸（《御览》作辛）。主寒（《御览》作伤寒）湿痿痹，四肢拘挛，膝痛不可屈伸，逐血气，伤热火烂，堕胎。久服，轻身、耐老（《御览》作能老）。一名百倍，生川谷。
《吴普》曰∶牛膝，神农∶甘；一经∶酸；黄帝、扁鹊∶甘；李氏，温。雷公∶酸，无毒。生河内或临邛。叶如夏蓝；茎本赤。二月、八月采（《御览》）。
《名医》曰∶生河内及临朐。二月、八月、十月采根，阴干。
案∶《广雅》云∶牛茎，牛膝也；陶弘景云∶其茎有节，似膝，故以为名也。膝，当为膝。
<目录
```
#### Top 3
- Book: `神农本草经`
- Chapter: `营实`
- Score: `0.030776515151515152`
- Snippet:

```text
古籍：神农本草经
篇名：营实
内容：味酸，温。主痈疽恶创，结肉跌筋，败创，热气，阴蚀不疗，利关节。一名墙薇，一名墙麻，一名牛棘。生川谷。
《吴普》曰∶蔷薇，一名牛勒，一名牛膝，一名蔷薇，一名山枣（《御览》）。
《名医》曰∶一名牛勒，一名蔷蘼，一名山棘，生零陵及蜀郡，八月、九月采，阴干。
案∶陶弘景云∶即是墙薇子。
<目录>卷一\上经
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_4712928b3239_ans

- Category: `herb_effect`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `龙胆在古籍中的主要功效是什么？请给出依据。`
- Expected Books: `013-本草纲目, 本草纲目, 本草纲目`
- Expected Chapters: `龙胆`
- Gold Answer Outline: `益肝胆之气而泄火`

### Gold Evidence

```text
好古曰∶益肝胆之气而泄火
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `龙胆`
- Score: `62.0`
- Snippet:

```text
古籍：吴普本草
篇名：龙胆
内容：\x按∶此药参见本书“大豆黄卷”条，《本经》首载此药。\x<目录>草木类
```
#### Top 2
- Book: `新修本草`
- Chapter: `龙胆`
- Score: `62.0`
- Snippet:

```text
古籍：新修本草
篇名：龙胆
内容：味苦，寒、大寒，无毒。主骨间寒热，惊痫，邪气，续绝伤，定五脏，杀蛊毒。除胃中伏热，时气温热，热泄下痢，去肠中小虫，益肝胆气，止惊惕。久服益智，不忘，轻身耐老。一朐，二月、八月、十一月、十二月采根，阴干。
贯众为之使，恶防葵、地黄。今出近道，吴兴为胜。状似牛膝，味甚苦，故以胆为名。
<目录>卷第六
```
#### Top 3
- Book: `本草乘雅半偈`
- Chapter: `龙胆`
- Score: `62.0`
- Snippet:

```text
古籍：本草乘雅半偈
篇名：龙胆
内容：（本经上品）【气味】苦涩，大寒，无毒。
【主治】主骨间寒热，惊痫邪气，续绝伤，定五脏，杀蛊毒。
【核】曰∶处处有之，吴兴者为胜。宿根黄白，直下抽根一二十条，类牛膝而短。直上生苗，高尺余，类嫩蒜而细。七月开花，类牵牛，作铃铎状；茎类竹枝，冬后结子，茎便焦枯。一种味极苦涩，经冬不凋，名石龙胆，类同而种别。修治，取阴干者，铜刀
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `神农本草经`
- Chapter: `龙胆`
- Score: `0.031754032258064516`
- Snippet:

```text
古籍：神农本草经
篇名：龙胆
内容：味苦涩。主骨间寒热，惊痫邪气，续绝伤，定五脏，杀蛊毒。久服，益智、不忘，轻身、耐老。一名陵游，生山谷。
《名医》曰∶生齐朐及冤句。二月、八月、十一月、十二月采根，阴干。
<目录>卷一\上经
```
#### Top 2
- Book: `新修本草`
- Chapter: `惊邪`
- Score: `0.030090497737556562`
- Snippet:

```text
古籍：新修本草
篇名：惊邪
内容：雄黄（《本经》平寒，《别录》大温）丹砂（《本经》微寒）紫石英（《本经》温）茯神（《别录》平）龙齿（《本经》平）龙胆（《本经》寒，《别录》大寒）防葵（《本经》寒）马目毒公（《本经》温，《别录》微温）升麻（《别录》平微寒）麝香（《本经》温）人参（《本经》微寒，《别录》微温）沙参（《本经》微寒）桔梗（《本经》微温）白薇（《本经》平，《别录》大寒）远志（《本经》温）柏实（《本经》平）鬼箭（《本经》寒）鬼督邮（《别录》平）小草（《本经》温）卷柏（《本经
```
#### Top 3
- Book: `吴普本草`
- Chapter: `龙胆`
- Score: `0.02844551282051282`
- Snippet:

```text
古籍：吴普本草
篇名：龙胆
内容：\x按∶此药参见本书“大豆黄卷”条，《本经》首载此药。\x<目录>草木类
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_4712928b3239_src

- Category: `herb_effect`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于龙胆功效的记载出自哪本书哪一篇？`
- Expected Books: `013-本草纲目, 本草纲目, 本草纲目`
- Expected Chapters: `龙胆`
- Gold Answer Outline: `益肝胆之气而泄火`

### Gold Evidence

```text
好古曰∶益肝胆之气而泄火
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `神农本草经`
- Chapter: `龙胆`
- Score: `62.0`
- Snippet:

```text
古籍：神农本草经
篇名：龙胆
内容：味苦涩。主骨间寒热，惊痫邪气，续绝伤，定五脏，杀蛊毒。久服，益智、不忘，轻身、耐老。一名陵游，生山谷。
《名医》曰∶生齐朐及冤句。二月、八月、十一月、十二月采根，阴干。
<目录>卷一\上经
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `吴普本草`
- Chapter: `龙胆`
- Score: `0.031024531024531024`
- Snippet:

```text
古籍：吴普本草
篇名：龙胆
内容：\x按∶此药参见本书“大豆黄卷”条，《本经》首载此药。\x<目录>草木类
```
#### Top 2
- Book: `神农本草经`
- Chapter: `龙胆`
- Score: `0.030621785881252923`
- Snippet:

```text
古籍：神农本草经
篇名：龙胆
内容：味苦涩。主骨间寒热，惊痫邪气，续绝伤，定五脏，杀蛊毒。久服，益智、不忘，轻身、耐老。一名陵游，生山谷。
《名医》曰∶生齐朐及冤句。二月、八月、十一月、十二月采根，阴干。
<目录>卷一\上经
```
#### Top 3
- Book: `新修本草`
- Chapter: `惊邪`
- Score: `0.028991596638655463`
- Snippet:

```text
古籍：新修本草
篇名：惊邪
内容：雄黄（《本经》平寒，《别录》大温）丹砂（《本经》微寒）紫石英（《本经》温）茯神（《别录》平）龙齿（《本经》平）龙胆（《本经》寒，《别录》大寒）防葵（《本经》寒）马目毒公（《本经》温，《别录》微温）升麻（《别录》平微寒）麝香（《本经》温）人参（《本经》微寒，《别录》微温）沙参（《本经》微寒）桔梗（《本经》微温）白薇（《本经》平，《别录》大寒）远志（《本经》温）柏实（《本经》平）鬼箭（《本经》寒）鬼督邮（《别录》平）小草（《本经》温）卷柏（《本经
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_50d2b0055a8b_ans

- Category: `herb_effect`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `槟榔在古籍中的主要功效是什么？请给出依据。`
- Expected Books: `637-景岳全书, 景岳全书, 景岳全书`
- Expected Chapters: `岭表十说（吴兴章杰）`
- Gold Answer Outline: `下气消食去痰`

### Gold Evidence

```text
槟榔最能下气消食去痰
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `得配本草`
- Chapter: `槟榔`
- Score: `62.0`
- Snippet:

```text
古籍：得配本草
篇名：槟榔
内容：苦、辛、温。入手足阳明经气分。泄胃中至高之气，坠诸药至于下极，达膜原而散疫邪。
治泻痢，破滞气，攻坚积，止诸痛，消痰癖，杀三虫，除水胀，疗瘴疟。得童便，治香港脚上冲。（或入姜汁。）得橘皮，治金疮呕恶。配良姜，治心脾作痛。配麦冬，治大便秘及血淋。配枳实、黄连，治伤寒痞满。
鸡心状正稳心不虚，破之作锦纹者为佳。勿见火，煎汤，洗毛
```
#### Top 2
- Book: `新修本草`
- Chapter: `槟榔`
- Score: `62.0`
- Snippet:

```text
古籍：新修本草
篇名：槟榔
内容：味辛，温，无毒。主消谷，逐水，除痰 ，杀三虫，去伏尸，疗寸白。生南海。
此有三、四种∶出交州，形小而味甘；广州以南者，形大而味涩，核亦大；尤大者，名楮者，南人名纳子，俗人吸为槟榔孙，亦可食。
〔谨案〕槟榔， 者极大，停数日便烂。今入北来者，皆先灰汁煮熟，仍火熏使干，始堪停久，其中仁，主腹胀，生捣末服，利水谷道，敷疮生肌肉，止
```
#### Top 3
- Book: `本草乘雅半偈`
- Chapter: `槟榔`
- Score: `62.0`
- Snippet:

```text
古籍：本草乘雅半偈
篇名：槟榔
内容：（别录中品）右迁环位，槟榔两得之矣。岁次玄枵，月旅蕤宾，五月律也。
【气味】苦辛涩温，无毒。
【主治】主消谷逐水，除痰 ，杀三虫、伏尸，寸白。
【核】曰∶出南海、交州、广州，及昆仑，今领外州郡皆有。子状非凡，木亦特异。初生似笋，渐积老成，引茎直上，旁无枝柯，本末若一，其中虚，其外坚，皮似青桐而浓，节似菌竹而概。大者三围，
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `汤液本草`
- Chapter: `槟榔`
- Score: `0.030330882352941176`
- Snippet:

```text
古籍：汤液本草
篇名：槟榔
内容：气温，味辛、苦，味浓气轻，阴中阳也。纯阳，无毒。
《象》云∶治后重如神。性如铁石之沉重，能坠诸药至于下极。杵细用。
《心》云∶苦以破滞，辛以散邪，专破滞气下行。
《珍》云∶破滞气，泄胸中至高之气。
《本草》云∶主消谷逐水，除痰癖，下三虫，去伏尸，疗寸白虫。
<目录>卷之五\木部
```
#### Top 2
- Book: `本草经集注`
- Chapter: `龙眼`
- Score: `0.028006267136701922`
- Snippet:

```text
古籍：本草经集注
篇名：龙眼
内容：味甘，平，无毒。主治五脏邪气，安志厌食，除虫去毒。久服强魂魄，聪察，轻身，不老，通神明。一名益智。其大者似槟榔。生南海山谷。
广州别有龙眼，似荔枝而小，非益智，恐彼人别名，今者为益智耳。食之并利人。（《新修》一二四页，《大观》卷十三，《政和》三三○页）<目录>草木上品
```
#### Top 3
- Book: `神农本草经`
- Chapter: `龙眼`
- Score: `0.027106227106227107`
- Snippet:

```text
古籍：神农本草经
篇名：龙眼
内容：味甘，平。主五脏邪气，安志厌食。久服，强魂、聪明、轻身、不老，通神明。一名益智。生山谷。
《吴普》曰∶龙眼，一名益智。《要术》∶一名比目（《御览》）。
《名医》曰∶其大者，似槟榔。生南海松树上。五月采，阴干。
案∶《广雅》云∶益智，龙眼也。刘达注《吴都赋》云∶龙眼，如荔枝而小，圆如弹丸，味甘，胜荔枝，苍梧、交址、南海、合浦，皆献之，山中之家亦种之。
<目录>卷二\中经
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_50d2b0055a8b_src

- Category: `herb_effect`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于槟榔功效的记载出自哪本书哪一篇？`
- Expected Books: `637-景岳全书, 景岳全书, 景岳全书`
- Expected Chapters: `岭表十说（吴兴章杰）`
- Gold Answer Outline: `下气消食去痰`

### Gold Evidence

```text
槟榔最能下气消食去痰
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
#### Top 1
- Book: `一得集`
- Chapter: `一得集`
- Score: `11.785647350132898`
- Snippet:

```text
古籍：一得集
篇名：一得集
[书名]：一得集作者：
朝代：
年份：
```
#### Top 2
- Book: `丁甘仁医案`
- Chapter: `丁甘仁医案`
- Score: `11.693524272817788`
- Snippet:

```text
古籍：丁甘仁医案
篇名：丁甘仁医案
[书名]：丁甘仁医案作者：
朝代：
年份：
```
#### Top 3
- Book: `万氏秘传片玉心书`
- Chapter: `万氏秘传片玉心书`
- Score: `11.575895666620072`
- Snippet:

```text
古籍：万氏秘传片玉心书
篇名：万氏秘传片玉心书
[书名]：万氏秘传片玉心书作者：李子毅朝代：清年份：公元1644-1911年<目录>卷一
```

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `汤液本草`
- Chapter: `槟榔`
- Score: `0.031054405392392875`
- Snippet:

```text
古籍：汤液本草
篇名：槟榔
内容：气温，味辛、苦，味浓气轻，阴中阳也。纯阳，无毒。
《象》云∶治后重如神。性如铁石之沉重，能坠诸药至于下极。杵细用。
《心》云∶苦以破滞，辛以散邪，专破滞气下行。
《珍》云∶破滞气，泄胸中至高之气。
《本草》云∶主消谷逐水，除痰癖，下三虫，去伏尸，疗寸白虫。
<目录>卷之五\木部
```
#### Top 2
- Book: `本草经集注`
- Chapter: `龙眼`
- Score: `0.029386529386529386`
- Snippet:

```text
古籍：本草经集注
篇名：龙眼
内容：味甘，平，无毒。主治五脏邪气，安志厌食，除虫去毒。久服强魂魄，聪察，轻身，不老，通神明。一名益智。其大者似槟榔。生南海山谷。
广州别有龙眼，似荔枝而小，非益智，恐彼人别名，今者为益智耳。食之并利人。（《新修》一二四页，《大观》卷十三，《政和》三三○页）<目录>草木上品
```
#### Top 3
- Book: `神农本草经`
- Chapter: `龙眼`
- Score: `0.028782894736842105`
- Snippet:

```text
古籍：神农本草经
篇名：龙眼
内容：味甘，平。主五脏邪气，安志厌食。久服，强魂、聪明、轻身、不老，通神明。一名益智。生山谷。
《吴普》曰∶龙眼，一名益智。《要术》∶一名比目（《御览》）。
《名医》曰∶其大者，似槟榔。生南海松树上。五月采，阴干。
案∶《广雅》云∶益智，龙眼也。刘达注《吴都赋》云∶龙眼，如荔枝而小，圆如弹丸，味甘，胜荔枝，苍梧、交址、南海、合浦，皆献之，山中之家亦种之。
<目录>卷二\中经
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_6bd56843dec4_ans

- Category: `entity_alias`
- Task Family: `answer_trace`
- Difficulty: `easy`
- Query: `地肤在古籍中的别名是什么？请给出出处。`
- Expected Books: `013-本草纲目, 本草纲目, 本草纲目`
- Expected Chapters: `地肤`
- Gold Answer Outline: `落帚子`

### Gold Evidence

```text
大明曰∶地肤即落帚子也
```

### Files-first Metrics
- topk book hit: `Yes`
- topk chapter hit: `Yes`
- topk evidence hit: `Yes`
- topk provenance hit: `Yes`
- topk answer hit: `Yes`
- topk answer+provenance hit: `Yes`

### Files-first Top Rows
#### Top 1
- Book: `本草纲目`
- Chapter: `地肤`
- Score: `62.0`
- Snippet:

```text
古籍：本草纲目
篇名：地肤
内容：（《本经》上品）【释名】地葵（《本经》）、地麦》）、王 （《尔雅》）、王帚（郭璞）、扫帚（弘景）、益明（《药性》）、白地草（《纲目》）、时珍曰∶地肤、地麦，因其子形似也。地葵，因其苗味似也。鸭舌，因其形似也。妓女，因其枝繁而头多也。益明，因其子功能明目也。子落则老，茎可为帚，故有帚、 诸名。
【集解】《别录》曰∶地肤子生荆州
```
#### Top 2
- Book: `千金翼方`
- Chapter: `地肤子`
- Score: `59.31999999999999`
- Snippet:

```text
古籍：千金翼方
篇名：地肤子
内容：味苦，寒，无毒。主膀胱热，利小便，补中，益精气，去皮肤中热气，散恶疮疝瘕，强阴。久服耳目聪明，轻身耐老，使人润泽。一名地葵，一名地麦。生荆州平泽及田野，八月十月采实，阴干。
<目录>卷第二·本草上\草部上品之下
```
#### Top 3
- Book: `三因极一病证方论`
- Chapter: `地肤子汤`
- Score: `55.96`
- Snippet:

```text
古籍：三因极一病证方论
篇名：地肤子汤
属性：治下焦有热，及诸淋闭不通。
地肤子（三两） 知母 黄芩 猪苓(去皮) 瞿麦 枳实(麸炒) 升麻 通草 葵子(炒)海藻(洗去腥，各二两)上为锉散。每服四钱，水一盏半，煎七分，去滓，空心服。大便俱闭者，加大黄。女人房劳，小便难，大腹满痛，脉沉细者，用猪肾半只，水二盏，煎盏半，去肾，下药，煎七分服。
<目录>卷之十二\
```

### Vector Metrics
- topk book hit: `Yes`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `神农本草经`
- Chapter: `地肤子`
- Score: `0.030886196246139225`
- Snippet:

```text
古籍：神农本草经
篇名：地肤子
内容：味苦，寒。主膀胱热，利小便，补中，益精气。久服，耳目聪明、轻身、耐老。一名地葵（《御览》引云∶一名地华，一名地脉。《大观本》无一名地华四字；脉，作麦，皆黑字）。
生平泽及田野。
《名医》曰∶一名地麦，生荆州，八月、十月采实，阴干。
案∶《广雅》云∶地葵，地肤也；《列仙传》云∶文宾服地肤；郑樵云∶地肤，曰落帚，亦曰地扫；《尔雅》云∶ ，马帚，即此也；今人亦用为帚。
<目录>卷一\上经
```
#### Top 2
- Book: `本草图经`
- Chapter: `地肤子`
- Score: `0.029957522915269395`
- Snippet:

```text
古籍：本草图经
篇名：地肤子
内容：\r地肤子\ph115.bmp\r，生荆州平泽及田野，今蜀川、关中近地皆有之。初生薄地，五、六寸；根形如蒿，茎赤，叶青，大似荆芥；三月开黄白花。八月、九月采实，阴干用。神仙七精散云∶地肤子，星之精也。或曰其苗即独扫也，一名鸭舌草。陶隐居谓∶茎苗可为扫帚者。苏恭云∶苗极弱，不能胜举。二说不同。而今医家便以为独扫是也。密州所上者，其说益明。云根作丛生，每窠有二、三十茎，茎有赤有黄，七月开黄花，其实地肤也。至八月而秸秆成，可采，正与此地独扫相类。
```
#### Top 3
- Book: `本草纲目`
- Chapter: `药名同异`
- Score: `0.02967032967032967`
- Snippet:

```text
古籍：本草纲目
篇名：药名同异
内容：〔五物同名〕独摇草（羌活 鬼臼 鬼督邮 天麻 薇衔）〔四物同名〕堇（堇菜 蒴 乌头 石龙芮） 苦菜（贝母 龙葵 苦苣 败酱） 鬼目（白英 羊蹄 紫葳 麂目） 红豆（赤小豆 红豆蔻 相思子 海红豆） 白药（桔梗 白药子栝蒌 会州白药） 豚耳〔三物同名〕美草（甘草 旋花 山姜） 山姜（美草 苍术 杜若） 蜜香（木香 多香木 沉香） 女萎（萎蕤 蔓楚 紫葳） 鬼督邮（徐长卿 赤箭 独摇草） 王孙（黄猢狲 牡蒙） 百枝（萆 防风 狗脊） 接骨草（
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?

## tcb_6bd56843dec4_src

- Category: `entity_alias`
- Task Family: `source_locate`
- Difficulty: `easy`
- Query: `古籍中关于地肤别名的记载出自哪本书哪一篇？`
- Expected Books: `013-本草纲目, 本草纲目, 本草纲目`
- Expected Chapters: `地肤`
- Gold Answer Outline: `落帚子`

### Gold Evidence

```text
大明曰∶地肤即落帚子也
```

### Files-first Metrics
- topk book hit: `No`
- topk chapter hit: `No`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Files-first Top Rows
No rows.

### Vector Metrics
- topk book hit: `No`
- topk chapter hit: `Yes`
- topk evidence hit: `No`
- topk provenance hit: `No`
- topk answer hit: `No`
- topk answer+provenance hit: `No`

### Vector Top Rows
#### Top 1
- Book: `神农本草经`
- Chapter: `地肤子`
- Score: `0.030886196246139225`
- Snippet:

```text
古籍：神农本草经
篇名：地肤子
内容：味苦，寒。主膀胱热，利小便，补中，益精气。久服，耳目聪明、轻身、耐老。一名地葵（《御览》引云∶一名地华，一名地脉。《大观本》无一名地华四字；脉，作麦，皆黑字）。
生平泽及田野。
《名医》曰∶一名地麦，生荆州，八月、十月采实，阴干。
案∶《广雅》云∶地葵，地肤也；《列仙传》云∶文宾服地肤；郑樵云∶地肤，曰落帚，亦曰地扫；《尔雅》云∶ ，马帚，即此也；今人亦用为帚。
<目录>卷一\上经
```
#### Top 2
- Book: `本草图经`
- Chapter: `地肤子`
- Score: `0.029709507042253523`
- Snippet:

```text
古籍：本草图经
篇名：地肤子
内容：\r地肤子\ph115.bmp\r，生荆州平泽及田野，今蜀川、关中近地皆有之。初生薄地，五、六寸；根形如蒿，茎赤，叶青，大似荆芥；三月开黄白花。八月、九月采实，阴干用。神仙七精散云∶地肤子，星之精也。或曰其苗即独扫也，一名鸭舌草。陶隐居谓∶茎苗可为扫帚者。苏恭云∶苗极弱，不能胜举。二说不同。而今医家便以为独扫是也。密州所上者，其说益明。云根作丛生，每窠有二、三十茎，茎有赤有黄，七月开黄花，其实地肤也。至八月而秸秆成，可采，正与此地独扫相类。
```
#### Top 3
- Book: `本草品汇精要`
- Chapter: `草之草`
- Score: `0.029273504273504274`
- Snippet:

```text
古籍：本草品汇精要
篇名：草之草
内容：\x无毒 丛生\x地肤子（出神农本经）主膀胱热利小便补中益精气久服耳目聪明轻身耐老（以上朱字神农本经）去皮肤中热气散恶疮疝瘕强阴使人润泽（以上黑字名医所录）【名】地葵 涎衣草 益明地麦 鸭舌草 落帚【苗】（图经曰）地肤子星之精也初生薄地高四五尺根形如蒿茎赤叶青大似荆芥三月开黄白花子青色或曰其苗即独帚也密州一种根作丛生每窠有二三十茎茎有赤有黄七月开黄花其实地肤也至八月而 干成可采正与此地独帚相类按陶隐居谓茎苗可谓扫帚苏恭云苗极弱不能胜举二
```

### Expert Notes

- Is files-first answer acceptable even if not in gold chapter/book?
- Is vector answer acceptable even if not in gold chapter/book?
- Should this case's gold set be expanded?
