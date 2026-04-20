# Files-first Failed Case Comparison

本文件收录 `files-first` 在重判分后仍失败的题目，并并排给出 `files-first` 与 `vector` 的返回内容，供人工审核是否真的回答错误。

Total failed cases: `8`

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
- Book: `理瀹骈文`
- Chapter: `存济堂药局修合施送方并加药法`
```text
古籍：理瀹骈文
篇名：存济堂药局修合施送方并加药法
属性：余为理瀹骈文。既明经文内外治一贯之理。复详前贤外治用药之法。所以开外治之一门文人而喜医者读吾文可知其理。并有所取法。莫不能自为方矣。方出于矩篇中。所引古方。
即有未尽验者要皆矩也。余方何足道以局所用录存焉。古有百草膏。杂取山上鲜草。不问芳草毒草。并而熬膏。能治百病。乃知膏别有道。不必以汤头拘。膏包百病
```

#### Top 3
- Book: `理瀹骈文`
- Chapter: `清阳膏`
```text
古籍：理瀹骈文
篇名：清阳膏
属性：（此膏治上焦风热及表里俱热者凡三阳症并宜之亦治湿在上须表散者若湿温症宜金仙膏阴虚有火者宜滋阴膏外症拔毒提脓宜云台膏○此膏治头疼如神风火症并效）统治四时脑后第二椎下两旁风门穴风常从此入脑鼻塞贴鼻梁并可卷一张塞鼻咳嗽及内热者贴喉下即天突穴心口即膻中穴或兼贴背后第三骨节即肺俞也凡肺病俱如此贴○此邪在上焦宜以上清散嗅鼻取嚏上清散用
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
- topk book asset hit: `False`

### Files-first Top Rows

#### Top 1
- Book: `医方集宜`
- Chapter: `治法`
```text
古籍：医方集宜
篇名：治法
属性：方见痰门<目录>卷之三\嘈杂门
```

#### Top 2
- Book: `古今医统大全`
- Chapter: `治法`
```text
古籍：古今医统大全
篇名：治法
属性：小续命汤、仲景三黄汤是也。
<目录>卷之五十五\皮肤候
```

#### Top 3
- Book: `丹台玉案`
- Chapter: `治法`
```text
古籍：丹台玉案
篇名：治法
属性：以三角针刺其红点之首尾处出血。外用锈铁钉。磨水敷之。内服犀角地黄汤立愈。（方<目录>卷之二\伤寒门
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
- Book: `重订通俗伤寒论`
- Chapter: `第三节·攻下剂`
```text
古籍：重订通俗伤寒论
篇名：第三节·攻下剂
犀连承气汤 心与小肠并治法 俞氏经验方犀角汁（两瓢冲） 小川连（八分） 小枳实（钱半） 鲜地汁（六瓢冲） 生锦纹（三钱） 真金汁（一两冲）【秀按】心与小肠相表里。热结在腑。上蒸心包。症必神昏谵语。甚则不语如尸。世俗所谓蒙闭证也。便通者宜芳香开窍。以通神明。若便秘而妄开之。势必将小肠结热。一齐而送入心窍。是开门揖盗也
```

#### Top 2
- Book: `重订广温热论`
- Chapter: `论温热即是伏火（添加）`
```text
古籍：重订广温热论
篇名：论温热即是伏火（添加）
热结旁流，按之硬痛，必有燥矢；均宜调胃承气汤，咸苦下之。脘腹均按痛，痞满燥实坚悉具──痞满为湿热气结，燥实坚为燥矢，甚则上蒸心包，下烁肝肾，烦躁谵语，舌卷囊缩，宜大承气汤加犀、连急下之。阴伤者，加鲜生地、元参、知母、川柏之类足矣。盖速下其邪，即所以存津液也。
少腹按痛，大便色黑如漆，反觉易行，若其人喜笑若狂，
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
- Book: `得配本草`
- Chapter: `石部`
```text
古籍：得配本草
篇名：石部
内容：（玉石类三种）<目录>卷一\石部
```

#### Top 2
- Book: `得配本草`
- Chapter: `石部`
```text
古籍：得配本草
篇名：石部
内容：（卤石类十五种）<目录>卷一\石部
```

#### Top 3
- Book: `得配本草`
- Chapter: `草部`
```text
古籍：得配本草
篇名：草部
内容：（隰草类七十二种）<目录>卷三\草部
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
