# Files-first Failed Case Comparison

本文件收录 `files-first` 在重判分后仍失败的题目，并并排给出 `files-first` 与 `vector` 的返回内容，供人工审核是否真的回答错误。

Total failed cases: `23`

## tcb_432ab8d9b2c4_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于疮科通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `鸡内金, 矾金, 芙蓉叶, 雄黄, 羌活, 黄柏, 防风, 当归尾, 连翘, 苍术, 陈皮, 甘草, 肉桂, 黄芪, 白芷, 升麻`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `疮科通治方`
```text
古籍：奇效良方
篇名：疮科通治方
属性：治一切恶疮，头上疮。
上平胃散，入腻粉清油调敷之，甚妙。
<目录>卷之五十四\疮疡门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `疮科通治方`
```text
古籍：奇效良方
篇名：疮科通治方
属性：上以甘草半两，豆粉一两，分作二服，酸齑水下。
<目录>卷之五十四\疮疡门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `疮科通治方`
```text
古籍：奇效良方
篇名：疮科通治方
属性：上以百芨末半钱，水盏内沉下，澄去水，却于皮纸上摊开，贴在疮上。
<目录>卷之五十四\疮疡门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_4a4a5c3997dc_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `丁皮, 丁香, 丁香皮, 三棱, 丹参, 乌头, 乌梅, 乌梅肉, 乌梢蛇, 乌药, 乳香, 乳香末, 五倍子, 五味子, 五灵脂, 京三棱`
- Acceptable Books: `071-医方集宜, 医方集宜, 511-金匮玉函要略辑义, 金匮玉函要略辑义, 097-验方新编, 验方新编, 079-仁术便览, 仁术便览, 070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `思考中医`
- Chapter: `思考中医`
```text
古籍：思考中医
篇名：思考中医
接下来我们看引起质变的第二个因素，即数变到质变。由数的变化而致质的变化，在上述这两个方剂中表现得尤其充分。我们看炙甘草汤，炙甘草汤上面已经敲定了，是一个养阴的方剂。方中大枣用量是三十枚。三十是一个什么数呢？三十是一个“群阴会”。我们将十个基数中的阴数也就是偶数二、四、六、八、十相加，会得到一个什么数呢？正好是三十。十基数中的阴数总和就是三十，所以我们把它叫“群阴会”。既然是这样一个数，那当然就有养阴的作用。这个数用在炙甘草汤中，就正好与它的主治
```

#### Top 2
- Book: `千金翼方`
- Chapter: `吴茱萸散`
```text
古籍：千金翼方
篇名：吴茱萸散
内容：主风跛蹇偏枯，半身不遂，昼夜呻吟，医所不能治方∶吴茱萸 干姜 白蔹 牡桂 附子（炮，去皮） 薯蓣 天雄（炮，去皮） 干漆（熬）秦艽（各半两） 狗脊（一分） 防风（一两）上一十一味，捣筛为散，以酒服方寸匕，日三服。
<目录>卷第十六·中风上\诸散第二
```

#### Top 3
- Book: `医心方`
- Chapter: `治杂利方第十九`
```text
古籍：医心方
篇名：治杂利方第十九
内容：《病源论》云∶杂利谓利色无定，水谷或脓或血，或青或黄，或赤或白，变杂无常，或杂色热不《短剧方》治杂下方，第一下赤，二下白，三下黄，四下青，五下黑，六固病下，下如瘀赤如舍水，十四下已则烦，十五息下一作一止，十六而不欲食，十七食无数但下者，十八下但欲饮黄连（一两） 黄柏（一两） 熟艾（一两） 附子（一两） 甘草（一两） 干姜（二两） 乌梅（二凡七物，合捣下筛，蜜和丸如大豆，饮服十丸，渐至二十丸，日三。（今按∶《葛氏方》云《范汪方》乌梅丸，
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_8eb0acc00c51_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于调经通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `吴茱萸, 麦门冬, 半夏, 牡丹皮, 白芍药, 肉桂, 人参, 当归, 川芎, 阿胶, 甘草, 熟地黄, 芍药, 木香, 茯苓, 桃仁`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `调经通治方`
```text
古籍：奇效良方
篇名：调经通治方
属性：治血脉不通。
当归 穿山甲（灰炒） 辰砂（另研，一钱） 麝香（少许）上为细末，研匀，每服二钱，食前热酒调服。
<目录>卷之六十三\妇人门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `调经通治方`
```text
古籍：奇效良方
篇名：调经通治方
属性：香附子（二两，炒赤） 莲壳（五个，烧存性）上为细末，每服二钱，空心陈米饮调下。
<目录>卷之六十三\妇人门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `调经通治方`
```text
古籍：奇效良方
篇名：调经通治方
属性：治妇人血海虚寒，月水不调。
川芎 当归 芍药 蓬术（各一钱半） 人参 牛膝（各二钱） 桂心 牡丹皮（各一钱） 甘草（半钱）上作一服，水二盅，煎至一盅，不拘时服。
<目录>卷之六十三\妇人门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_c32415309f9c_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于一方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `丁香, 三家水, 三家盐, 三家鸡卵, 三棱, 不蛀皂角, 丝瓜小小蔓藤, 乌梅, 乌贼鱼骨, 乌鸡, 乱发, 乳香, 二陈汤, 云母粉, 五倍子, 五叶藤`
- Acceptable Books: `074-普济方, 普济方, 198-济阴纲目, 济阴纲目, 215-杂病广要, 杂病广要, 583-医学正传, 医学正传, 603-医碥, 医碥, 647-万病回春, 万病回春, 568-杂病治例, 杂病治例, 065-卫生易简方, 卫生易简方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `本草纲目`
- Chapter: `引据古今医家书目`
```text
古籍：本草纲目
篇名：引据古今医家书目
黄帝《素问》（王冰注）唐玄宗《开元广济方》《天宝单方图》唐德宗《贞元广利方》《太仓公方》宋太宗《太平圣惠方》《扁鹊方》（三卷）张仲景《金匮玉函方》《华佗方》（十卷）张仲景《伤寒论》（成无己注）《支太医方》张文仲《随身备急方》《徐文伯方》初虞世《古今录验方》《秦承祖方》王焘《外台秘要方》华佗《中藏经》姚和众《延龄至宝方》《范汪东阳方》孙真人《千金备急方》《孙真人食忌》孙真人《千金翼方》《孙真人枕中记》《席延赏方》孙真人《千金髓方》《叶天师
```

#### Top 2
- Book: `汤液本草`
- Chapter: `《汤液本草》后序`
```text
古籍：汤液本草
篇名：《汤液本草》后序
内容：刘禹锡云∶《神农本经》以朱书，《名医别录》以墨书，传写既久，朱墨错乱，遂令后人以为非神农书，以此故也。至于《素问》本经，议者以为战国时书，加以“补亡”数篇，则显然非《太素》中语，宜其以为非轩岐书也。陈无择云∶王叔和《脉诀》即高阳生剽窃。是亦后人增益者杂之也。何以知其然？予观刘元宾注本，杂病生死歌后，比之他本即少八句。观此八句，不甚滑溜，与上文书意重叠，后人安得不疑？与《本草经》朱书杂乱，《素问》之补亡混淆，何以异哉！宜乎，识者非之
```

#### Top 3
- Book: `本草纲目`
- Chapter: `引据古今医家书目`
```text
古籍：本草纲目
篇名：引据古今医家书目
内容：时珍曰∶自陶弘景以下，唐、宋诸本草引用医书，凡八十四家，而唐慎微居多。时珍今所引，除旧本外，凡二百七十七家。
黄帝《素问》（王冰注）唐玄宗《开元广济方》《天宝单方图》唐德宗《贞元广利方》《太仓公方》宋太宗《太平圣惠方》《扁鹊方》（三卷）张仲景《金匮玉函方》《华佗方》（十卷）张仲景《伤寒论》（成无己注）《支太医方》张文仲《随身备急方》《徐文伯方》初虞世《古今录验方》《秦承祖方》王焘《外台秘要方》华佗《中藏经》姚和众《延龄至宝方》《范
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_50943261620b_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于痨瘵通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `芒硝, 苦参, 青葙子, 艾叶, 甘草, 大黄, 石膏, 青蒿心, 童子小便, 生地黄, 东引桃枝, 天灵盖, 紫河车, 石蜥蜴, 獭肝, 赤足蜈蚣`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `痨瘵通治方`
```text
古籍：奇效良方
篇名：痨瘵通治方
属性：治证同前。
北柴胡（去苗） 桔梗（炒） 麦门冬（去心） 木通 秦艽（以上各半两） 地骨皮 桑皮（三钱，水一大盏，生<目录>卷之二十二\痨瘵门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `痨瘵通治方`
```text
古籍：奇效良方
篇名：痨瘵通治方
属性：主冷痰虚热，诸劳寒热。
沉香 附子（炮，各等分）上 咀，煎露一宿，空心服。
<目录>卷之二十二\痨瘵门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `痨瘵通治方`
```text
古籍：奇效良方
篇名：痨瘵通治方
属性：治劳热。
柴胡（去苗） 人参上各等分 咀，每服三钱，水一中盏，生姜三片，枣一枚，煎至六分，去滓，不拘时服。
<目录>卷之二十二\痨瘵门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_b26bf7448135_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于诸虚通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `人参, 白术末, 茯神, 香附子, 甘草, 肉苁蓉, 枸杞子, 鸡头实, 粳米, 补骨脂, 附子, 葫芦巴, 白槟榔, 巴戟, 沉香, 硫黄`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `诸虚通治方`
```text
古籍：奇效良方
篇名：诸虚通治方
属性：上以百花上露饮之。
<目录>卷之二十一\诸虚门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `诸虚通治方`
```text
古籍：奇效良方
篇名：诸虚通治方
属性：用菟丝子一斗，酒浸良久，漉出曝干，又浸令酒尽为度，捣为细末，每服二钱，以酒调好<目录>卷之二十一\诸虚门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `诸虚通治方`
```text
古籍：奇效良方
篇名：诸虚通治方
属性：乌梅肉 甘草（各二两） 百药煎（一两） 白芷（半两） 白檀（三钱）上为细末，用沸汤点服一二钱，食前服。
<目录>卷之二十一\诸虚门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_cfc87926e240_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于牙齿通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `牡丹皮, 升麻, 当归, 生地黄, 黄连, 木香, 当归身, 茴香叶, 川芎, 防风, 白芷, 细辛, 地骨皮, 槐花, 甘草, 雄黄`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `牙齿通治方`
```text
古籍：奇效良方
篇名：牙齿通治方
属性：上用川升麻煎汤，漱咽解毒。
<目录>卷之六十二\牙齿门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `牙齿通治方`
```text
古籍：奇效良方
篇名：牙齿通治方
属性：上用藜芦为末，塞于牙孔中，勿咽汁，神效。
<目录>卷之六十二\牙齿门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `牙齿通治方`
```text
古籍：奇效良方
篇名：牙齿通治方
属性：治牙齿疼痛。
防风 鹤虱（各三钱）上作一服，用水二盅，煎至一盅，不拘时噙饮。
<目录>卷之六十二\牙齿门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_91bf32d2db51_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于正骨通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `大黄, 柴胡, 当归, 桃仁, 红花, 川芎, 白芍药, 百合, 荆芥, 没药, 乳香, 川椒, 芍药, 自然铜, 葱白, 锻石`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `正骨通治方`
```text
古籍：奇效良方
篇名：正骨通治方
属性：上以鸡内金，焙为末敷之，立止。
<目录>卷之五十六\正骨兼金镞门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `正骨通治方`
```text
古籍：奇效良方
篇名：正骨通治方
属性：轻粉 血竭 密陀僧 干胭脂（各一钱） 乳香（二钱）上研细，每用干掺，仍以膏药贴之。
<目录>卷之五十六\正骨兼金镞门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `正骨通治方`
```text
古籍：奇效良方
篇名：正骨通治方
属性：上用鲤鱼目烧灰，研敷患处，汗出即愈。诸鱼目皆可用， 鱼目尤佳。
<目录>卷之五十六\正骨兼金镞门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_633f9691b540_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于五痹通治方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `当归, 赤芍药, 黄芪, 片姜黄, 羌活, 甘草, 白术, 防己, 秦艽, 附子, 防风, 草乌, 南星, 地龙, 破故纸, 五灵脂`
- Acceptable Books: `070-奇效良方, 奇效良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `奇效良方`
- Chapter: `五痹通治方`
```text
古籍：奇效良方
篇名：五痹通治方
属性：治寒证麻痹。
方见寒门<目录>卷之三十八\五痹门（附论）
```

#### Top 2
- Book: `奇效良方`
- Chapter: `五痹通治方`
```text
古籍：奇效良方
篇名：五痹通治方
属性：治五种痹痛，身腿臂间发作不定者。
川芎 附子（炮，去皮脐） 黄 （去芦） 白术 当归 柴胡（去芦） 防风（去芦）熟地上作一服，用水二盅，生姜三片，红枣一枚，煎一盅，空心服。
<目录>卷之三十八\五痹门（附论）
```

#### Top 3
- Book: `奇效良方`
- Chapter: `五痹通治方`
```text
古籍：奇效良方
篇名：五痹通治方
属性：治筋痹，肢节束痛。
羚羊角 薄桂 附子 独活（以上各一两三钱半） 白芍药 防风 川芎（以上各一两）上锉碎，每服三大钱，水一盏半，生姜三片，煎至八分，去滓，温服。日一二服。
<目录>卷之三十八\五痹门（附论）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_f294b450c3a9_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Query: `云台膏由哪些药材组成？请依据古籍回答并给出出处。`
- Acceptable Answers: `丁香, 丹皮, 乌梅, 乌药, 五倍子, 五味子, 僵蚕, 党参, 全蝎, 净松香, 凤仙, 凤仙草, 制乳香, 制厚朴, 制没药, 半夏`
- Acceptable Books: `337-理瀹骈文, 理瀹骈文, 228-发背对口治诀论, 发背对口治诀论`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `云台膏`
```text
古籍：理瀹骈文
篇名：云台膏
属性：（一名 膏言一已足也○此膏寒热攻补并用初起能消已成能溃巳溃能提毒尽自敛不必服解表托里之药亦不假刀针升降可以眠食故元气不伤虚人无补亦能收功）通治发背搭手对口发疽颈核乳痈（乳红肿热痛者用清阳膏皮色不变属气滞者用金仙膏真阴寒症用散阴膏）肚痈腰痈。
一切无名肿毒。附骨流注。与恶毒顽疮。蛇犬伤等症。凡属阳者并治。即半阴半阳之症亦治。
```

#### Top 2
- Book: `发背对口治诀论`
- Chapter: `附∶杨州存济堂药局膏药方`
```text
古籍：发背对口治诀论
篇名：附∶杨州存济堂药局膏药方
属性：\x云台膏\x（一名夔膏，言一已足也 此膏寒热、攻补并用，初起能消，已成能溃，已溃能提，毒尽自敛，不必服解表托里之药，亦不假刀针、升降丹、药捻等物，始终此只一膏，极为简便神速。重证外加糁药，敷药助之。已验过数万人，无不愈者。且能定痛，可以服食，故元气不伤、虚人无补，亦能收功）通治发背、搭手、对口、发
```

#### Top 3
- Book: `理瀹骈文`
- Chapter: `存济堂药局修合施送方并加药法`
```text
古籍：理瀹骈文
篇名：存济堂药局修合施送方并加药法
属性：余为理瀹骈文。既明经文内外治一贯之理。复详前贤外治用药之法。所以开外治之一门文人而喜医者读吾文可知其理。并有所取法。莫不能自为方矣。方出于矩篇中。所引古方。
即有未尽验者要皆矩也。余方何足道以局所用录存焉。古有百草膏。杂取山上鲜草。不问芳草毒草。并而熬膏。能治百病。乃知膏别有道。不必以汤头拘。膏包百病
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `云台膏`
```text
古籍：理瀹骈文
篇名：云台膏
生大二两） 生黄 当归（各一两六钱） 茅苍术 羌活 独活 防风 连翘 香附 乌药 陈皮青皮 天花粉 川芎 白芷 山栀 赤芍 苦杏仁 桃仁 生草乌 生川乌 生南星生半夏 生黄柏 黄连 细辛 五倍子 僵蚕 生山甲 蜈蚣 全蝎 露蜂房（有子者佳）黄芩 蝉蜕 蛇蜕 干地龙 蟾皮 生牡蛎 皂角 红花 蓖麻仁（各一两○蓖麻仁或用三两） 发团（二两四钱）○拟增甘遂大戟延胡灵脂远志郁金荆芥蒲黄各一两原有蜘蛛（七个）生姜 葱白 大蒜头（各四两） 槐枝 柳枝 桑枝（
```

#### Top 2
- Book: `理瀹骈文`
- Chapter: `云台膏`
```text
古籍：理瀹骈文
篇名：云台膏
属性：（一名 膏言一已足也○此膏寒热攻补并用初起能消已成能溃巳溃能提毒尽自敛不必服解表托里之药亦不假刀针升降可以眠食故元气不伤虚人无补亦能收功）通治发背搭手对口发疽颈核乳痈（乳红肿热痛者用清阳膏皮色不变属气滞者用金仙膏真阴寒症用散阴膏）肚痈腰痈。
一切无名肿毒。附骨流注。与恶毒顽疮。蛇犬伤等症。凡属阳者并治。即半阴半阳之症亦治。疔毒加拔疔药贴。
生大二两） 生黄 当归（各一两六钱） 茅苍术 羌活 独活 防风 连翘 香附 乌药 陈皮青皮 天花粉 川
```

#### Top 3
- Book: `发背对口治诀论`
- Chapter: `附∶杨州存济堂药局膏药方`
```text
古籍：发背对口治诀论
篇名：附∶杨州存济堂药局膏药方
属性：\x云台膏\x（一名夔膏，言一已足也 此膏寒热、攻补并用，初起能消，已成能溃，已溃能提，毒尽自敛，不必服解表托里之药，亦不假刀针、升降丹、药捻等物，始终此只一膏，极为简便神速。重证外加糁药，敷药助之。已验过数万人，无不愈者。且能定痛，可以服食，故元气不伤、虚人无补，亦能收功）通治发背、搭手、对口、发疽、颈核、乳痈、肚痈、腰痈、一切无名肿毒、附骨流注与恶毒顽疮、蛇犬伤等证。凡属阳者并治，即半阴半阳之证亦治，疗毒加拔疔药
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_f6e60ecfa98e_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Query: `添加回生集续补经验良方由哪些药材组成？请依据古籍回答并给出出处。`
- Acceptable Answers: `三奈, 上冰片, 上厥粉, 丝瓜穣, 丹参, 丹砂, 乳没, 云苓, 五倍子, 五加皮, 人指甲灰, 元胡索, 全当归, 冰片, 制甘石, 制苍术`
- Acceptable Books: `116-回生集, 回生集`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `回生集`
- Chapter: `添加紧要良方`
```text
古籍：回生集
篇名：添加紧要良方
属性：青黛（三钱） 真紫竹根（三钱） 马全子（三钱）以上三味。煎水服之。毒即可从大便中出。
<目录>卷上\内症门
```

#### Top 2
- Book: `回生集`
- Chapter: `添加紧要良方`
```text
古籍：回生集
篇名：添加紧要良方
属性：用水龙骨。（即旧船上捻船之桐油锻石也）晒干研细末。用韭菜汁浸透晒干。再以牛胆浸湿拌匀。又晒干研末。KT 之即愈。
<目录>卷上\内症门
```

#### Top 3
- Book: `回生集`
- Chapter: `添加紧要良方`
```text
古籍：回生集
篇名：添加紧要良方
属性：当归 熟地（各二钱） 白芍（一钱） 川芎（一钱五分）上水煎服。
<目录>卷下\外症门
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：用陈松萝茶末。掺之愈。
<目录>卷下\小儿门
```

#### Top 2
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：当归 熟地（各二钱） 白芍（一钱） 川芎（一钱五分）上水煎服。
<目录>卷下\小儿门
```

#### Top 3
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：用上好黄丹一味。掺二三次即愈。
<目录>卷下\小儿门
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_f6e60ecfa98e_src

- Category: `formula_composition`
- Task Family: `source_locate`
- Query: `古籍中关于添加回生集续补经验良方组成的记载出自哪本书哪一篇？`
- Acceptable Answers: `三奈, 上冰片, 上厥粉, 丝瓜穣, 丹参, 丹砂, 乳没, 云苓, 五倍子, 五加皮, 人指甲灰, 元胡索, 全当归, 冰片, 制甘石, 制苍术`
- Acceptable Books: `116-回生集, 回生集`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `三十年临证经验集`
- Chapter: `三十年临证经验集`
```text
古籍：三十年临证经验集
篇名：三十年临证经验集
虚劳独特之脉，仲景于《金匮要略》中已有论述：“男子平人，脉大为劳，极虚亦为劳。”论者每以脉大无力之劳为气虚，极虚之劳为肾虚。喻嘉言则曰：“虚劳之脉多见浮大。”又曰：“浮大弦紧，外象有余，其实中藏不足。”而《馤塘医话》于“补编”中所言虚劳之脉，大符临床实际：“虚劳之脉必数，而有浮大、细小之别。浮大而数，阴虚甚也；
```

#### Top 2
- Book: `热病衡正`
- Chapter: `热病衡正`
```text
古籍：热病衡正
篇名：热病衡正
⑥时逸人：《中医伤寒与温病》，上海科技出版社，1958⑦同⑤⑧杨宇：陆九芝用葛根芩连汤治湿温刍议，陕西中医(2)：3，1983。
⑨陆九芝：《世补斋医书·前集上》“夏暑发自阳明”质疑“夏暑发自阳明”是叶天士提出的著名论点，后世咸宗之，如《温病学》说：“暑为火热之气，传变迅速，故其侵犯人体，多径入气分而无卫分过程，所以初起即见高
```

#### Top 3
- Book: `章次公医案`
- Chapter: `章次公医案`
```text
古籍：章次公医案
篇名：章次公医案
55．王男。主症在胃，进食无论量之多寡皆胀，自觉脘与腹汩汩有声，其外观并不胀满。此非水而是气。征之时吞酸而不吐不痛，关键在消化不良。炮附块9克，姜半夏12克，蓬莪术9克，海南片9克，生莱菔子9克(研)，淡吴萸6克，川椒目5克，沉香曲9克，台乌药9克，上肉桂末1．2克(分2次吞下)。二诊：药两服，进食胸次梗介不得下者，大见轻
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：用陈松萝茶末。掺之愈。
<目录>卷下\小儿门
```

#### Top 2
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：当归 熟地（各二钱） 白芍（一钱） 川芎（一钱五分）上水煎服。
<目录>卷下\小儿门
```

#### Top 3
- Book: `回生集`
- Chapter: `添加回生集续补经验良方`
```text
古籍：回生集
篇名：添加回生集续补经验良方
属性：用上好黄丹一味。掺二三次即愈。
<目录>卷下\小儿门
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_c9b6a12de297_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Query: `扶阳益火膏的一个组成药材是什么？请依据古籍回答并给出出处。`
- Acceptable Answers: `丹参, 丹皮, 五倍子, 五味子, 仙茅, 侧柏叶, 元参, 党参, 冬霜叶, 冬青枝, 凤仙草, 北细辛, 半夏, 南星, 南薄荷, 发团`
- Acceptable Books: `337-理瀹骈文, 理瀹骈文`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `扶阳益火膏`
```text
古籍：理瀹骈文
篇名：扶阳益火膏
属性：（旧名离济膏又名温肾固真膏专补命门之火制水以生土较散阴膏多补涩可作暖脐膏用并可与温肺温胃健脾膏参用寒痧抽吊盖文中药末贴少年火旺勿用）治元阳衰耗脐眼对脐）或脾寒便溏。泄泻浮肿作胀。（贴脐眼对脐参用健脾膏）或肾气虚寒。腰脊重痛。（贴腰脊） 腹脐腿足常冷。（贴脐眼及膝盖）或肾气衰败。茎痿精寒。（贴脐下）或精滑随触随泄。（贴对
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `扶阳益火膏`
```text
古籍：理瀹骈文
篇名：扶阳益火膏
属性：（旧名离济膏又名温肾固真膏专补命门之火制水以生土较散阴膏多补涩可作暖脐膏用并可与温肺温胃健脾膏参用寒痧抽吊盖文中药末贴少年火旺勿用）治元阳衰耗脐眼对脐）或脾寒便溏。泄泻浮肿作胀。（贴脐眼对脐参用健脾膏）或肾气虚寒。腰脊重痛。（贴腰脊） 腹脐腿足常冷。（贴脐眼及膝盖）或肾气衰败。茎痿精寒。（贴脐下）或精滑随触随泄。（贴对脐及脐下）或夜多漩溺。（气虚膀胱不藏）甚则脬冷遗尿不禁。（水衰火实则二便不通火衰火实则二便不禁○亦贴对脐脐下）或冷淋。（
```

#### Top 2
- Book: `普济方`
- Chapter: `补益轻身延年`
```text
古籍：普济方
篇名：补益轻身延年
属性：（附论）夫人禀中和气。生两仪间。处寒暑四时之宜。法阴阳五行之度。莫不精气内朗。形神外融。
存少性。知表里乱其以善摄反观之之基。
诚宜朽。
\x方\x\x应验打老丹 补丹田。安魂魄。壮筋骨。暖下元。添精髓。身轻体健。益寿延年。\x\x除百病。
白茯苓（去皮） 甘菊花 川芎 干山药 乌药 金铃子 复盆子 钟乳粉（研） 山茱萸云子桂心天雄（炮如无附子代之） 巴戟（水浸去心） 鹿茸（去毛） 远志（去心） 白术 麦门冬（去心） 牡蛎（ ） 生地黄
```

#### Top 3
- Book: `本草品汇精要`
- Chapter: `石之石`
```text
古籍：本草品汇精要
篇名：石之石
内容：\x无毒 土石生\x阳起石（出神农本经）主崩中漏下破子脏中血症瘕结气寒热腹痛无子阴痿不起补不足（以上朱字神农本经）疗男子茎头寒阴下湿痒去臭汗消水肿久服不饥令人有子（以上黑字名医所录）【名】白石 石生 阳起石【地】（图经曰）生齐山山谷及琅邪或云山阳起山今惟出齐州他处不复有或云邢州鹊山亦有之然不甚好今齐州城西唯一土山石出其中彼人谓之阳起山其山常有温暖气虽盛冬大雪遍境独此山无积白盖石气熏蒸使然也山唯一穴官中常禁闭至初冬则州发丁夫遣人监视取之岁
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_3ec534d39839_ans

- Category: `formula_composition`
- Task Family: `answer_trace`
- Query: `滋阴壮水膏由哪些药材组成？请依据古籍回答并给出出处。`
- Acceptable Answers: `三棱, 丹参, 丹皮, 乌梅, 侧柏叶, 元参, 党参, 全蝎, 冬青枝, 凤仙, 前胡, 半夏, 吴萸, 地骨皮, 大戟, 大蒜头`
- Acceptable Books: `337-理瀹骈文, 理瀹骈文`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `滋阴壮水膏`
```text
古籍：理瀹骈文
篇名：滋阴壮水膏
属性：（旧名坎济膏○世人知百病生于心而不知百病生于肾饮酒食肉醉饱入房嗜欲妄为伤精则肾水空虚不能平其心火心火纵炎伤其肺金是绝水之源金水衰亏不能胜其肝木肝木盛则克脾土而反生火火独旺而不生化故阳有余阴不足独热而不久矣○左肾属水右尺洪大或数用此补阴降火○此方滋肾而兼五脏与清肺清胃清肝三膏可参用）治男子阴虚火旺。午后惊悸喘息。眼花耳鸣
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `理瀹骈文`
- Chapter: `滋阴壮水膏`
```text
古籍：理瀹骈文
篇名：滋阴壮水膏
属性：（旧名坎济膏○世人知百病生于心而不知百病生于肾饮酒食肉醉饱入房嗜欲妄为伤精则肾水空虚不能平其心火心火纵炎伤其肺金是绝水之源金水衰亏不能胜其肝木肝木盛则克脾土而反生火火独旺而不生化故阳有余阴不足独热而不久矣○左肾属水右尺洪大或数用此补阴降火○此方滋肾而兼五脏与清肺清胃清肝三膏可参用）治男子阴虚火旺。午后惊悸喘息。眼花耳鸣。两颧发赤。喉舌生疮。盗汗梦遗。（梦遗属相火所迫不梦而遗乃心肾虚弱文中有五倍涂脐法可糁）腰痛脊酸。（肾虚也有臀尖痛者阴虚
```

#### Top 2
- Book: `名师垂教`
- Chapter: `名师垂教`
```text
古籍：名师垂教
篇名：名师垂教
老师：我认为要把眼光移向临床：临床上到底有没有肝肾阴虚与肝郁气滞两种病机共存，且都是主要病机的病证?请注意，我指的不是肝肾阴虚兼肝郁气滞，也不是肝郁气滞兼肝肾阴虚，而是两种病机共存并列，分不出孰主孰次的情形。如本例患者，其胸胁隐痛、小腹灼热入夜加重，伴双目干涩，夜梦纷纭，口干苦等，显然属于肝肾阴虚；而其胃脘满闷、嗳气频作、小腹（月真）胀等，则又属于肝郁气滞。这两组主观性症状，患者的感受一样地苦不堪言；经反复询问，连她本人都分辨不清楚孰主孰次，医
```

#### Top 3
- Book: `李翰卿`
- Chapter: `李翰卿`
```text
古籍：李翰卿
篇名：李翰卿
(4)可与清热泄热药同用。如高热神昏谵语者，宜去厚朴之类温燥之弊，配用石膏、知母、生地、黄连、黄芩、黄柏等。
(5)可与滋阴生津药同用。如大热伤阴，津亏而燥者，应与生地、麦冬、元参、石斛等同用。
(6)泻下之后宜续服和胃之剂。使用泻下剂后，便下热臭者，为药已中病，可再服1一2剂，以防热结未清而复骤；如便下清稀而无热臭或热臭不重者，恐误下，即宜停用，并续服和胃之剂以顾护胃气。
(7)注意承气证之假象。虽有上述之证，但伴有腹胀，肠鸣音亢进者，为承气证之
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_6d98aea0c9f2_ans

- Category: `formula_method`
- Task Family: `answer_trace`
- Query: `养荣承气汤体现的一个治法要点是什么？请依据古籍回答并给出出处。`
- Acceptable Answers: `润燥兼下结热法, 润燥泄热以微下, 清下, 缓下, 镇润以缓下, 养血与通便并用`
- Acceptable Books: `475-重订通俗伤寒论, 重订通俗伤寒论, 549-重订广温热论, 重订广温热论`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `重订广温热论`
- Chapter: `论温热即是伏火（添加）`
```text
古籍：重订广温热论
篇名：论温热即是伏火（添加）
热结旁流，按之硬痛，必有燥矢；均宜调胃承气汤，咸苦下之。脘腹均按痛，痞满燥实坚悉具──痞满为湿热气结，燥实坚为燥矢，甚则上蒸心包，下烁肝肾，烦躁谵语，舌卷囊缩，宜大承气汤加犀、连急下之。阴伤者，加鲜生地、元参、知母、川柏之类足矣。盖速下其邪，即所以存津液也。
少腹按痛，大便色黑如漆，反觉易行，若其人喜笑若狂，
```

#### Top 2
- Book: `重订通俗伤寒论`
- Chapter: `第三节·攻下剂`
```text
古籍：重订通俗伤寒论
篇名：第三节·攻下剂
犀连承气汤 心与小肠并治法 俞氏经验方犀角汁（两瓢冲） 小川连（八分） 小枳实（钱半） 鲜地汁（六瓢冲） 生锦纹（三钱） 真金汁（一两冲）【秀按】心与小肠相表里。热结在腑。上蒸心包。症必神昏谵语。甚则不语如尸。世俗所谓蒙闭证也。便通者宜芳香开窍。以通神明。若便秘而妄开之。势必将小肠结热。一齐而送入心窍。是开门揖盗也
```

#### Top 3
- Book: `重订广温热论`
- Chapter: `验方`
```text
古籍：重订广温热论
篇名：验方
\x加减小陷胸合半夏泻心汤\x 栝蒌仁（五钱） 仙露夏（二钱） 小川连（一钱） 条芩（二钱） 淡竹沥（一瓢） 生姜汁（四滴）\x昌阳泻心汤\x 鲜石菖蒲（钱半） 条芩（一钱） 仙露夏（一钱） 苏叶（四分） 小川连（六分） 真川朴（八分） 紫菀（三钱）先用鲜竹茹五钱，鲜枇杷叶一两去毛抽筋，活水芦根二两，煎汤代水。
\x按∶\x此
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `重订通俗伤寒论`
- Chapter: `第三节·攻下剂`
```text
古籍：重订通俗伤寒论
篇名：第三节·攻下剂
犀连承气汤 心与小肠并治法 俞氏经验方犀角汁（两瓢冲） 小川连（八分） 小枳实（钱半） 鲜地汁（六瓢冲） 生锦纹（三钱） 真金汁（一两冲）【秀按】心与小肠相表里。热结在腑。上蒸心包。症必神昏谵语。甚则不语如尸。世俗所谓蒙闭证也。便通者宜芳香开窍。以通神明。若便秘而妄开之。势必将小肠结热。一齐而送入心窍。是开门揖盗也。此方君以大黄、黄连。极苦泄热。凉泻心小肠之火。臣以犀、地二汁。通心神而救心阴。佐以枳实。直达小肠幽门。俾心与小肠之火。
```

#### Top 2
- Book: `思考中医`
- Chapter: `思考中医`
```text
古籍：思考中医
篇名：思考中医
② 阳明病治法阳明病的治法历来都以清下二法概之，清法主要指白虎所赅之法，若细分起来，清法还应包括栀子豉汤法、猪苓汤法。下法前人今人都以三承气汤为代表，但若按仲景本人的说法，下法是有严格区分的。三承气汤中，只有大承气汤可称下法，是下法的代表方。而小承气汤仲景不言下只言和，如208条云：“阳明病，脉迟，虽汗出不恶寒者，其身必重，短气腹满而喘，有潮热者，此外欲解，可攻里也。手足濈然汗出者，此大便已鞭也，大承气汤主之；若汗多，微发热恶寒者，外未解也，其
```

#### Top 3
- Book: `重订广温热论`
- Chapter: `验方`
```text
古籍：重订广温热论
篇名：验方
\x加减小陷胸合半夏泻心汤\x 栝蒌仁（五钱） 仙露夏（二钱） 小川连（一钱） 条芩（二钱） 淡竹沥（一瓢） 生姜汁（四滴）\x昌阳泻心汤\x 鲜石菖蒲（钱半） 条芩（一钱） 仙露夏（一钱） 苏叶（四分） 小川连（六分） 真川朴（八分） 紫菀（三钱）先用鲜竹茹五钱，鲜枇杷叶一两去毛抽筋，活水芦根二两，煎汤代水。
\x按∶\x此方除痰泄热，宣气通津；专治暑秽夹痰，酿成霍乱，胸痞心烦，神昏谵语，或渴或呃，或呕酸吐苦，汤水碍下，小便秘涩等症。
\x太
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_6d98aea0c9f2_src

- Category: `formula_method`
- Task Family: `source_locate`
- Query: `古籍中关于养荣承气汤治法的记载出自哪本书哪一篇？`
- Acceptable Answers: `润燥兼下结热法, 润燥泄热以微下, 清下, 缓下, 镇润以缓下, 养血与通便并用`
- Acceptable Books: `475-重订通俗伤寒论, 重订通俗伤寒论, 549-重订广温热论, 重订广温热论`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `重订广温热论`
- Chapter: `论温热即是伏火（添加）`
```text
古籍：重订广温热论
篇名：论温热即是伏火（添加）
热结旁流，按之硬痛，必有燥矢；均宜调胃承气汤，咸苦下之。脘腹均按痛，痞满燥实坚悉具──痞满为湿热气结，燥实坚为燥矢，甚则上蒸心包，下烁肝肾，烦躁谵语，舌卷囊缩，宜大承气汤加犀、连急下之。阴伤者，加鲜生地、元参、知母、川柏之类足矣。盖速下其邪，即所以存津液也。
少腹按痛，大便色黑如漆，反觉易行，若其人喜笑若狂，
```

#### Top 2
- Book: `重订通俗伤寒论`
- Chapter: `第三节·攻下剂`
```text
古籍：重订通俗伤寒论
篇名：第三节·攻下剂
犀连承气汤 心与小肠并治法 俞氏经验方犀角汁（两瓢冲） 小川连（八分） 小枳实（钱半） 鲜地汁（六瓢冲） 生锦纹（三钱） 真金汁（一两冲）【秀按】心与小肠相表里。热结在腑。上蒸心包。症必神昏谵语。甚则不语如尸。世俗所谓蒙闭证也。便通者宜芳香开窍。以通神明。若便秘而妄开之。势必将小肠结热。一齐而送入心窍。是开门揖盗也
```

#### Top 3
- Book: `重订广温热论`
- Chapter: `验方`
```text
古籍：重订广温热论
篇名：验方
\x加减小陷胸合半夏泻心汤\x 栝蒌仁（五钱） 仙露夏（二钱） 小川连（一钱） 条芩（二钱） 淡竹沥（一瓢） 生姜汁（四滴）\x昌阳泻心汤\x 鲜石菖蒲（钱半） 条芩（一钱） 仙露夏（一钱） 苏叶（四分） 小川连（六分） 真川朴（八分） 紫菀（三钱）先用鲜竹茹五钱，鲜枇杷叶一两去毛抽筋，活水芦根二两，煎汤代水。
\x按∶\x此
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `重订通俗伤寒论`
- Chapter: `第三节·攻下剂`
```text
古籍：重订通俗伤寒论
篇名：第三节·攻下剂
犀连承气汤 心与小肠并治法 俞氏经验方犀角汁（两瓢冲） 小川连（八分） 小枳实（钱半） 鲜地汁（六瓢冲） 生锦纹（三钱） 真金汁（一两冲）【秀按】心与小肠相表里。热结在腑。上蒸心包。症必神昏谵语。甚则不语如尸。世俗所谓蒙闭证也。便通者宜芳香开窍。以通神明。若便秘而妄开之。势必将小肠结热。一齐而送入心窍。是开门揖盗也。此方君以大黄、黄连。极苦泄热。凉泻心小肠之火。臣以犀、地二汁。通心神而救心阴。佐以枳实。直达小肠幽门。俾心与小肠之火。
```

#### Top 2
- Book: `思考中医`
- Chapter: `思考中医`
```text
古籍：思考中医
篇名：思考中医
② 阳明病治法阳明病的治法历来都以清下二法概之，清法主要指白虎所赅之法，若细分起来，清法还应包括栀子豉汤法、猪苓汤法。下法前人今人都以三承气汤为代表，但若按仲景本人的说法，下法是有严格区分的。三承气汤中，只有大承气汤可称下法，是下法的代表方。而小承气汤仲景不言下只言和，如208条云：“阳明病，脉迟，虽汗出不恶寒者，其身必重，短气腹满而喘，有潮热者，此外欲解，可攻里也。手足濈然汗出者，此大便已鞭也，大承气汤主之；若汗多，微发热恶寒者，外未解也，其
```

#### Top 3
- Book: `重订广温热论`
- Chapter: `验方`
```text
古籍：重订广温热论
篇名：验方
\x加减小陷胸合半夏泻心汤\x 栝蒌仁（五钱） 仙露夏（二钱） 小川连（一钱） 条芩（二钱） 淡竹沥（一瓢） 生姜汁（四滴）\x昌阳泻心汤\x 鲜石菖蒲（钱半） 条芩（一钱） 仙露夏（一钱） 苏叶（四分） 小川连（六分） 真川朴（八分） 紫菀（三钱）先用鲜竹茹五钱，鲜枇杷叶一两去毛抽筋，活水芦根二两，煎汤代水。
\x按∶\x此方除痰泄热，宣气通津；专治暑秽夹痰，酿成霍乱，胸痞心烦，神昏谵语，或渴或呃，或呕酸吐苦，汤水碍下，小便秘涩等症。
\x太
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_1d14845d9935_src

- Category: `herb_effect`
- Task Family: `source_locate`
- Query: `古籍中关于鸡内金功效的记载出自哪本书哪一篇？`
- Acceptable Answers: `住崩带肠风, 健脾开胃, 助脾胃消化, 化滞和中, 可止痛, 尤止反胃, 杀虫磨积, 止泄痢遗精, 消水谷, 消磨水谷, 消酒积, 消食, 消食化滞, 祛瘀除积, 缩小便而除尿痛, 退烦热而息淋痛`
- Acceptable Books: `016-本草易读, 本草易读, 036-得配本草, 得配本草, 117-本草简要方, 本草简要方, 699-名老中医之路, 名老中医之路, 097-验方新编, 验方新编, 526-温病条辨, 温病条辨, 032-本草撮要, 本草撮要, 037-本草害利, 本草害利`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `True`

### Files-first Top Rows

#### Top 1
- Book: `本草纲目`
- Chapter: `菠`
```text
古籍：本草纲目
篇名：菠
内容：（宋《嘉 》）【释名】菠菜（《纲目》）、波斯草（《纲目》）、赤根菜。
慎微曰∶按∶刘禹锡《嘉话录》云∶菠 种出自西国。有僧将其子来，云本是颇陵国之种。语讹为波棱耳。
时珍曰∶按∶《唐会要》云∶太宗时尼波罗国献波棱菜，类红蓝，实如蒺藜，火熟之能益食味。即此也。方士隐名为波斯草云。
【集解】时珍曰∶波棱，八月、九月种者，可备冬食；
```

#### Top 2
- Book: `本草纲目`
- Chapter: `脾胃`
```text
古籍：本草纲目
篇名：脾胃
内容：（有劳倦内伤，有饮食内伤，有湿热，有虚寒）【劳倦】〔草部〕甘草（补脾胃，除邪热，益三焦元气，养阴血。） 人参（劳倦内伤，补中气，泻邪火。煎膏合姜、蜜服。） 黄 （益脾胃，实皮毛，去肌热，止自汗。） 黄精葳蕤（补中益气。） 白术（熬膏服良。） 苍术（安脾除湿，熬膏作丸散，有四制、八制、坎离、交感诸丸。） 柴胡芍药（泻肝，安脾肺
```

#### Top 3
- Book: `本草纲目`
- Chapter: `消渴`
```text
古籍：本草纲目
篇名：消渴
内容：（上消少食，中消多食，下消小便如膏油）【生津润燥】〔草部〕栝蒌根（为消渴要药，煎汤、作粉、熬膏皆良。） 黄栝蒌（酒洗熬膏，白矾丸服。） 王瓜子（同甘草煎服，日三。渴十年者亦愈。） 兰叶（生津止渴，除陈气。） 芭蕉根汁（日饮。）牛蒡子 葵根（消渴，小便不利，菜〕菇米（煮汁。） 青粱米 粟米 麻子仁（煮汁。） 沤麻汁 波 根（同
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `本草便读`
- Chapter: `乌骨鸡`
```text
古籍：本草便读
篇名：乌骨鸡
内容：\r乌骨鸡\pq132.bmp\r补肝家血液之亏。理产治劳。甘平无毒。治肺肾虚羸之疾。白毛黑骨。金水相生。
巽木属风。能动风而发毒。内金化食。可消食以宽中。 捕壳以调搽。磨翳敷疮。下疳尽愈。煎矢白而酒服。通肠治鼓。性味咸寒。鸡冠气禀纯阳。治中恶且除客忤。鸡子性平甘润。
安五脏尤养心神。（乌骨鸡。鸡之种类甚多。大抵以白毛黑骨。皮肉尽黑者良。鸡为巽木。
性味甘平。血肉有情之品。肝虚者宜食之。以其外白内黑。得金水相生之意。故肝肺肾三脏血液不足者最
```

#### Top 2
- Book: `本草纲目`
- Chapter: `鸡`
```text
古籍：本草纲目
篇名：鸡
【附方】旧三，新十七。小便遗失∶用鸡 一具，并肠烧存性，酒服。男用雌，女用雄。（《集验》）小便淋沥痛不可忍∶鸡肫内黄皮五钱，阴干烧存性，作一服，白汤下，立愈。（《医林集要》）膈消饮水∶鸡内金（洗，晒干）、栝蒌根（炒）各五两，为末，糊丸梧桐子大。每服三十丸，温水下，日三。（《总录》）反胃吐食∶鸡 一具，烧存性，酒调服。男用雌，女用雄。（《千金》）消导酒积∶鸡 、干葛为末，等分，面糊丸梧桐子大。每服五十丸，酒下。（《袖珍方》）噤口痢疾∶鸡内金焙研，乳汁服
```

#### Top 3
- Book: `绛囊撮要`
- Chapter: `鸡金散`
```text
古籍：绛囊撮要
篇名：鸡金散
属性：治臌胀如神。
鸡内金（一具） 沉香 砂仁（各三钱） 陈香橼（五钱去核）共为末。每服一钱五分。姜汤下。
<目录>内科
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_9b00e8ff191a_ans

- Category: `herb_effect`
- Task Family: `answer_trace`
- Query: `生麦芽在古籍中的主要功效是什么？请给出依据。`
- Acceptable Answers: `升发而助脾胃, 将顺肝木之性使不抑郁, 治肝气郁, 升肝, 调肝, 宣通, 疏达肝郁, 升达肝气, 舒肝气, 化瘀, 宣通肝气之郁结, 消食, 升达肝气之郁, 宣通诸药之滞腻, 善调和肝气, 引气火上散`
- Acceptable Books: `669-名师垂教, 名师垂教, 584-医学衷中参西录, 医学衷中参西录, 679-章次公医案, 章次公医案`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `得配本草`
- Chapter: `亚麻`
```text
古籍：得配本草
篇名：亚麻
内容：\x一名鳖虱胡麻\x甘，微温。入阳明经。散风热，解湿毒。
<目录>卷五\谷部
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `本草易读`
- Chapter: `麦芽二百十六`
```text
古籍：本草易读
篇名：麦芽二百十六
内容：\x炒用。\x咸，温，无毒。消食和中，宽肠下气，开胃除烦，催生下胎。破症结而消痰饮，退胀满而止产后回乳，因无子食胀膨，水煎三钱立消。（验方第一。）生胎欲去，蜜水煎二两服。（第二。）腹胀气急，为末酒下。因无子食乳。（第三。）进食，同陈皮、神曲丸服。（第四。）小儿肚大黄瘦，莲肉、山药、云苓、神曲、麦芽、白扁豆，每四两，入面一斤，或入糖水合，烙焦饼用。（第五。）<目录>本草易读卷六
```

#### Top 2
- Book: `本草备要`
- Chapter: `大麦芽`
```text
古籍：本草备要
篇名：大麦芽
内容：开胃健脾，行气消积咸温。能助胃气上行，而资健运，补脾宽肠，和中下气，消食除胀，散结祛痰（咸能软坚），化一切米、面、果、食积，通乳下胎（《外台方》∶麦芽一升、蜜一升服，下胎神验。
薛立斋治一妇人，丧子乳胀，几欲成痈，单用麦芽一二两炒，煎服立消，其破血散气如此。
《良方》云∶神曲亦下胎，皆不可轻用）。久服消肾气（王好古曰∶麦芽，神曲，胃虚人宜服之，以伐戊己，腐熟水谷。李时珍曰∶无积而服之，消人元气。与白术诸药，消补兼施，则无害也。胃为戊土，脾为
```

#### Top 3
- Book: `本草纲目`
- Chapter: `米`
```text
古籍：本草纲目
篇名：米
内容：（《别录》中品）【释名】弘景曰∶此是以米作 ，非别米名也。
恭曰∶ 犹孽也，生不以理之名也。皆当以可生之物生之，取其 中之米入药。按∶《食经》用稻 ，稻即 谷之总名。陶谓以米作 ，非矣。米【集解】宗 曰∶ 米，粟 也。
时珍曰∶《别录》止云 米，不云粟作也。苏恭言凡谷皆可生者，是矣。有粟、黍、谷、麦、豆诸 ，皆水浸胀，候生芽曝干去须，取其中米，炒研面用。其功皆主消导。今并集于左方。《日华子》谓 米为作醋黄子者，亦误矣。
\x粟 \x（一名粟芽）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_9b00e8ff191a_src

- Category: `herb_effect`
- Task Family: `source_locate`
- Query: `古籍中关于生麦芽功效的记载出自哪本书哪一篇？`
- Acceptable Answers: `升发而助脾胃, 将顺肝木之性使不抑郁, 治肝气郁, 升肝, 调肝, 宣通, 疏达肝郁, 升达肝气, 舒肝气, 化瘀, 宣通肝气之郁结, 消食, 升达肝气之郁, 宣通诸药之滞腻, 善调和肝气, 引气火上散`
- Acceptable Books: `669-名师垂教, 名师垂教, 584-医学衷中参西录, 医学衷中参西录, 679-章次公医案, 章次公医案`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `丹台玉案`
- Chapter: `附臀痈`
```text
古籍：丹台玉案
篇名：附臀痈
属性：\x活血散瘀汤\x 治臀痈初发。红赤肿痛。重坠如石。及大便秘涩。
川芎 当归 防风 赤芍（各一钱） 苏木 连翘...
```

#### Top 2
- Book: `丹台玉案`
- Chapter: `附脑痈`
```text
古籍：丹台玉案
篇名：附脑痈
属性：\x黄连救苦汤\x 治脑痈初起增寒发热头面耳项俱肿。服之立消。
黄连 赤芍 桔梗 金银花（各一钱五分） 升麻（八分） 柴胡 干葛...
```

#### Top 3
- Book: `丹台玉案`
- Chapter: `附肺痈`
```text
古籍：丹台玉案
篇名：附肺痈
属性：\x平肺饮\x 治肺痈初起。咳嗽气急。胸中隐隐作痛。呕吐脓痰。
人参 麦门冬 赤芍 槟榔 赤茯苓 陈皮 桔梗...
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `本草易读`
- Chapter: `麦芽二百十六`
```text
古籍：本草易读
篇名：麦芽二百十六
内容：\x炒用。\x咸，温，无毒。消食和中，宽肠下气，开胃除烦，催生下胎。破症结而消痰饮，退胀满而止产后回乳，因无子食胀膨，水煎三钱立消。（验方第一。）生胎欲去，蜜水煎二两服。（第二。）腹胀气急，为末酒下。因无子食乳。（第三。）进食，同陈皮、神曲丸服。（第四。）小儿肚大黄瘦，莲肉、山药、云苓、神曲、麦芽、白扁豆，每四两，入面一斤，或入糖水合，烙焦饼用。（第五。）<目录>本草易读卷六
```

#### Top 2
- Book: `本草备要`
- Chapter: `大麦芽`
```text
古籍：本草备要
篇名：大麦芽
内容：开胃健脾，行气消积咸温。能助胃气上行，而资健运，补脾宽肠，和中下气，消食除胀，散结祛痰（咸能软坚），化一切米、面、果、食积，通乳下胎（《外台方》∶麦芽一升、蜜一升服，下胎神验。
薛立斋治一妇人，丧子乳胀，几欲成痈，单用麦芽一二两炒，煎服立消，其破血散气如此。
《良方》云∶神曲亦下胎，皆不可轻用）。久服消肾气（王好古曰∶麦芽，神曲，胃虚人宜服之，以伐戊己，腐熟水谷。李时珍曰∶无积而服之，消人元气。与白术诸药，消补兼施，则无害也。胃为戊土，脾为
```

#### Top 3
- Book: `本草纲目`
- Chapter: `米`
```text
古籍：本草纲目
篇名：米
内容：（《别录》中品）【释名】弘景曰∶此是以米作 ，非别米名也。
恭曰∶ 犹孽也，生不以理之名也。皆当以可生之物生之，取其 中之米入药。按∶《食经》用稻 ，稻即 谷之总名。陶谓以米作 ，非矣。米【集解】宗 曰∶ 米，粟 也。
时珍曰∶《别录》止云 米，不云粟作也。苏恭言凡谷皆可生者，是矣。有粟、黍、谷、麦、豆诸 ，皆水浸胀，候生芽曝干去须，取其中米，炒研面用。其功皆主消导。今并集于左方。《日华子》谓 米为作醋黄子者，亦误矣。
\x粟 \x（一名粟芽）
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_556d7be9d41b_ans

- Category: `herb_channel`
- Task Family: `answer_trace`
- Query: `皂荚归入的一条经脉是什么？请给出古籍依据。`
- Acceptable Answers: `入厥阴经, 厥阴经, 厥阴经气分, 大肠经, 手太阴、阳明经气分, 手太阴手足阳明经气分, 手太阴经, 手少阴经, 手阳明经, 肝经, 肺、大肠, 肺大肠二经, 肺经, 胃经, 足厥阴, 足厥阴、手少阴、手太阴三经`
- Acceptable Books: `577-医学入门, 医学入门, 008-汤液本草, 汤液本草, 013-本草纲目, 本草纲目, 044-要药分剂, 要药分剂, 027-本草述钩元, 本草述钩元, 017-本草新编, 本草新编, 015-本草征要, 本草征要, 021-本草从新, 本草从新`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `千金翼方`
- Chapter: `皂荚`
```text
古籍：千金翼方
篇名：皂荚
内容：味辛咸，温，有小毒。主风痹，死肌，邪气，风头泪出，利九窍，杀精物。疗腹满，消谷，除咳嗽，囊结，妇人胞不落，明目益精。可为沐药，不入汤。生雍州川谷及鲁邹县。如猪牙者良。九月十月采荚，阴干。
<目录>卷第三·本草中\木部下品
```

#### Top 2
- Book: `名医别录`
- Chapter: `皂荚`
```text
古籍：名医别录
篇名：皂荚
内容：有小毒。主治腹胀满，消谷，破咳嗽囊结，妇人胞下落，明目，益精。可为沐药，不汤。生雍州及鲁邹县。如猪牙者良。九月、十月采荚，阴干。（青葙子为之使，恶麦门冬畏空青、人参、苦参。）《本经》原文∶皂荚，味辛、咸，温。主风痹死肌邪气，风头泪出，利九窍，杀精物。
生川谷。
<目录>下品·卷第三
```

#### Top 3
- Book: `增广和剂局方药性总论`
- Chapter: `皂荚`
```text
古籍：增广和剂局方药性总论
篇名：皂荚
属性：味辛咸，温，有小毒。主风痹死肌，邪气，风头泪出，利九窍，杀精物，疗腹胀满，谷，除咳嗽囊结，妇人胞不落，明目益精。《药性论》云∶使。主破坚症腹中痛，能堕胎日华子云∶通关节，除头风，消痰，杀劳虫，治骨蒸，开胃及中风口噤。一云∶核中白肉亦入治肺药。又炮复选中心黄嚼饵之，治膈痰吞酸。《梅师方》∶治霍乱转筋，又治卒外肾偏疼
```

### Vector Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `针灸问对`
- Chapter: `十二经纳支干歌`
```text
古籍：针灸问对
篇名：十二经纳支干歌
属性：肺寅大卯胃辰宫。脾巳心午小未中。申膀酉肾心包戌。亥三子胆丑肝通。此是经脉流注君当记取在心胸。甲胆乙肝丙小肠。丁心戊胃己脾乡。庚属大肠辛属肺。壬属膀胱癸肾藏。
三焦亦向壬中寄。包络同归入癸方。
<目录>卷之下
```

#### Top 2
- Book: `神农本草经`
- Chapter: `皂荚`
```text
古籍：神农本草经
篇名：皂荚
内容：味辛、咸，温。主风痹、死肌、邪气，风头、泪出，利九窍，杀精物。生川谷。
《名医》曰∶生壅州及鲁邹县。如猪牙者，良。九月、十月采，阴干。
案∶《说文》云∶荚，草实。《范子计然》云∶皂荚，出三辅。上价一枚一钱。《广志》曰∶鸡栖子，皂荚也（《御览》）。皂，即草省文。
<目录>卷三\下经
```

#### Top 3
- Book: `神农本草经`
- Chapter: `木药，下部`
```text
古籍：神农本草经
篇名：木药，下部
内容：黄环 鸢尾为使；恶茯苓、防己。
石南 五加皮为使。
巴豆 芫花为使；恶 草；畏大黄、黄连、藜芦；杀斑蝥毒。
栾花 决明为使。
蜀椒 杏仁为使，畏款冬。
溲疏 漏芦为使。
皂荚 柏实为使；恶麦门冬；畏空青、人参、苦参。
雷丸 荔实、浓朴为使；恶葛根。
<目录>卷三\下经
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_22e18a957ac2_src

- Category: `herb_channel`
- Task Family: `source_locate`
- Query: `古籍中关于络石藤归经的记载出自哪本书哪一篇？`
- Acceptable Answers: `手少阴经, 足厥阴经, 足少阳经, 足少阴经, 足阳明手足少阴足厥阴少阳经, 足阳明经`
- Acceptable Books: `027-本草述钩元, 本草述钩元`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `本草纲目`
- Chapter: `进《本草纲目》疏`
```text
古籍：本草纲目
篇名：进《本草纲目》疏
内容：湖广黄州府儒学增广生员李建元谨奏，为遵奉明例访书，进献《本草》以备采择事。臣伏读礼部仪制司勘合一款，恭请圣明敕儒臣开书局纂修正史，移文中外。凡名家着述，有关国家典章，及纪君臣事迹，他如天文、乐律、医术、方技诸书，但成一家名言，可以垂于方来者，即访求解送，以备采入《艺文志》。如已刻行者，即刷印一部送部。或其家自欲进
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `True`

### Vector Top Rows

#### Top 1
- Book: `本草便读`
- Chapter: `络石藤`
```text
古籍：本草便读
篇名：络石藤
内容：味苦性平。宣风通络。（络石藤凡藤蔓之属。皆可通络宣风。以风在络中。则络道闭塞。况苦平之性。又能宣发者乎。）<目录>草部\毒草类
```

#### Top 2
- Book: `本草述钩元`
- Chapter: `络石藤`
```text
古籍：本草述钩元
篇名：络石藤
内容：生阴湿处。冬夏常青。实黑而圆。其茎蔓延贴石。折之有白汁。其叶小于指头。浓强。面青背淡。涩而不光。有尖圆二种。功用相同。六七月采茎叶用。其绕树生者。叶薄也。气味苦温。微寒。入足阳明手足少阴足厥阴少阳经。治喉舌肿闭。背痈 肿。口干舌焦。养地之阴气毒也。喉即通。神叶相对栝蒌一小便白浊。
史载之言用络石人参茯苓各二两。龙骨 一两。为末。每服二钱。空心米饮下。日〔论〕凡味苦寒则就水。苦热则就火。络石味苦。凌冬不凋。得于阴气最浓。六七月采之。
达清浊
```

#### Top 3
- Book: `医学衷中参西录`
- Chapter: `31．答宗弟××问右臂疼治法`
```text
古籍：医学衷中参西录
篇名：31．答宗弟××问右臂疼治法
属性：据来案云云，臂疼当系因热。而愚再三思之，其原因断乎非热。或经络间因瘀生热，故乍服辛凉之品似觉轻也。盖此证纯为经络之病，治之者宜以经络为重，而兼顾其脏腑，盖欲药力由脏腑而达经络也。西人治急性关节疼痛，恒用阿斯匹林。然用其药宜用中药健运脾胃通行经络之品辅之。又细阅素服之方皆佳，所以不见效者，大抵因少开痹通窃之药耳。今拟一方于下∶于白术（此药药局中多用麸炒殊非所宜，当购生者自炒熟，其大小片分两次炒之轧细）取净末一两，乳
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_89d570c7a54e_ans

- Category: `entity_alias`
- Task Family: `answer_trace`
- Query: `苍耳在古籍中的一个别名是什么？请给出出处。`
- Acceptable Answers: `卷耳, 喝起草, 地葵, 常思, 爵耳, 猪耳, 缣丝草, 羊负来, 苓耳, 进贤菜, 道人头, 野茄, 鼠粘子, 羊负菜`
- Acceptable Books: `013-本草纲目, 本草纲目, 645-证类本草, 证类本草, 003-新修本草, 新修本草, 056-苏沈良方, 苏沈良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `True`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `本经逢原`
- Chapter: `苍耳`
```text
古籍：本经逢原
篇名：苍耳
内容：\x古名 耳\x实甘温，叶苦辛，小毒。酒浸炒用，忌猪肉。
\x发明\x 苍耳治头风脑痛，风湿周痹，四肢拘挛，恶肉死肌，皮肤瘙痒，脚膝寒痛，久服亦能益气。其叶久服去风湿有效。服苍耳人最忌猪肉及风邪，触犯则遍身发出赤丹也。妇人血风攻脑，头旋闷绝，忽倒不知人事者，用苍耳草嫩心阴干为末，酒服甚效。此味善通顶门连脑，能走督脉也。
<目
```

#### Top 2
- Book: `本草简要方`
- Chapter: `苍耳`
```text
古籍：本草简要方
篇名：苍耳
属性：主治散风。发汗。除湿。暖腰脚。风湿周痹。四肢挛痛。万应膏。五七九等月。采苍根火煎滚。文火煎稠。搅成膏。新罐贮封。治一切痈疽发背。无头恶疮疔毒风痒。杖疮。牙痛喉痹。内服一匙。酒调下。外用敷贴。苍耳丸。苍耳叶不拘多少。阴干研末。每用五两。取粟米二合煮粥研如膏。复以莨菪子（淘净炒微黄）捣末。用一两和丸绿豆大。每服二十丸。
空腹温
```

#### Top 3
- Book: `滇南本草`
- Chapter: `苍耳`
```text
古籍：滇南本草
篇名：苍耳
内容：\r苍耳\pb97.bmp\r，气味甘、苦，性温。主治上通脑顶，下行足膝。发汗，散风湿，外达皮肤。治头痛、目暗、齿痛、鼻渊、肢痛、痹痛。疮科仙草，慎勿轻视。
<目录>第二卷
```

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `神农本草经`
- Chapter: `耳实`
```text
古籍：神农本草经
篇名：耳实
内容：味甘，温。主风头寒痛，风湿周痹，四肢拘挛痛，恶肉死肌。久服益气，耳目聪明，强志轻身。一名胡 ，一名地葵。生《名医》曰∶一名 ，一名常思，生安陆及六安田野，实熟时采。
案∶《说文》云∶ ，卷耳也；苓，卷耳也。《广雅》云∶苓耳， ，常 ，胡 ，耳也。《尔雅》云∶苍耳，苓耳。郭璞云∶江东呼为常 ，形似鼠耳，丛生如盘。《毛诗》云∶采采卷耳。《传》云∶卷耳，苓耳也。陆玑云∶叶青，白色，似胡荽，白花，细茎蔓生。可煮为茹，滑而少味；四月中生子，正如妇人耳
```

#### Top 2
- Book: `食疗本草`
- Chapter: `苍耳〈温〉`
```text
古籍：食疗本草
篇名：苍耳〈温〉
内容：（一）主中风、伤寒头痛。〔嘉〕（二）又，疔肿困重，生捣苍耳根、叶，和小儿尿绞取汁，冷服一升，日三度，甚验。
〔嘉〕（三）拔疔肿根脚。〔证〕（四）又，治一切风∶取嫩叶一石，切，捣和五升麦 ，团作块。于蒿、艾中盛二十日，状成曲。取米一斗，炊作饭。看冷暖，入苍耳麦 曲，作三大升酿之。封一十四日成熟。取此酒，空心暖服之，神验。封此酒可两重布，不得全密，密则溢出。〔证〕（五）又，不可和马肉食。〔证〕<目录>卷上
```

#### Top 3
- Book: `神农本草经`
- Chapter: `苦瓠`
```text
古籍：神农本草经
篇名：苦瓠
内容：味苦，寒。主大水，面目四肢浮肿，下水，令人叶。生川泽。
《名医》曰∶生晋地。
案∶《说文》云∶瓠匏，匏瓠也。《广雅》云∶匏，瓠也。《尔雅》云∶瓠，栖瓣。《毛诗》云∶瓠有苦叶。《传》云∶匏，谓之瓠。又九月断壶。《传》云∶壶，瓠也。《古今注》云∶瓠，壶芦也。壶芦，瓠之无柄者。瓠，有柄者。又云∶瓢，瓠也。其 ，曰匏。
瓠则别名。
<目录>卷三\下经
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?

## tcb_89d570c7a54e_src

- Category: `entity_alias`
- Task Family: `source_locate`
- Query: `古籍中关于苍耳别名的记载出自哪本书哪一篇？`
- Acceptable Answers: `卷耳, 喝起草, 地葵, 常思, 爵耳, 猪耳, 缣丝草, 羊负来, 苓耳, 进贤菜, 道人头, 野茄, 鼠粘子, 羊负菜`
- Acceptable Books: `013-本草纲目, 本草纲目, 645-证类本草, 证类本草, 003-新修本草, 新修本草, 056-苏沈良方, 苏沈良方`

### Files-first Regraded Metrics
- top1 success: `False`
- topk success: `False`
- topk subject hit: `False`
- topk answer asset hit: `False`
- topk book asset hit: `False`

### Files-first Top Rows

No rows returned.

### Vector Regraded Metrics
- top1 success: `True`
- topk success: `True`
- topk subject hit: `True`
- topk answer asset hit: `True`
- topk book asset hit: `False`

### Vector Top Rows

#### Top 1
- Book: `神农本草经`
- Chapter: `耳实`
```text
古籍：神农本草经
篇名：耳实
内容：味甘，温。主风头寒痛，风湿周痹，四肢拘挛痛，恶肉死肌。久服益气，耳目聪明，强志轻身。一名胡 ，一名地葵。生《名医》曰∶一名 ，一名常思，生安陆及六安田野，实熟时采。
案∶《说文》云∶ ，卷耳也；苓，卷耳也。《广雅》云∶苓耳， ，常 ，胡 ，耳也。《尔雅》云∶苍耳，苓耳。郭璞云∶江东呼为常 ，形似鼠耳，丛生如盘。《毛诗》云∶采采卷耳。《传》云∶卷耳，苓耳也。陆玑云∶叶青，白色，似胡荽，白花，细茎蔓生。可煮为茹，滑而少味；四月中生子，正如妇人耳
```

#### Top 2
- Book: `食疗本草`
- Chapter: `苍耳〈温〉`
```text
古籍：食疗本草
篇名：苍耳〈温〉
内容：（一）主中风、伤寒头痛。〔嘉〕（二）又，疔肿困重，生捣苍耳根、叶，和小儿尿绞取汁，冷服一升，日三度，甚验。
〔嘉〕（三）拔疔肿根脚。〔证〕（四）又，治一切风∶取嫩叶一石，切，捣和五升麦 ，团作块。于蒿、艾中盛二十日，状成曲。取米一斗，炊作饭。看冷暖，入苍耳麦 曲，作三大升酿之。封一十四日成熟。取此酒，空心暖服之，神验。封此酒可两重布，不得全密，密则溢出。〔证〕（五）又，不可和马肉食。〔证〕<目录>卷上
```

#### Top 3
- Book: `神农本草经`
- Chapter: `苦瓠`
```text
古籍：神农本草经
篇名：苦瓠
内容：味苦，寒。主大水，面目四肢浮肿，下水，令人叶。生川泽。
《名医》曰∶生晋地。
案∶《说文》云∶瓠匏，匏瓠也。《广雅》云∶匏，瓠也。《尔雅》云∶瓠，栖瓣。《毛诗》云∶瓠有苦叶。《传》云∶匏，谓之瓠。又九月断壶。《传》云∶壶，瓠也。《古今注》云∶瓠，壶芦也。壶芦，瓠之无柄者。瓠，有柄者。又云∶瓢，瓠也。其 ，曰匏。
瓠则别名。
<目录>卷三\下经
```

### Human Review

- Files-first should be counted as correct? `Yes / No / Partial`
- Vector should be counted as correct? `Yes / No / Partial`
- If either should count, what is the supporting rationale?
