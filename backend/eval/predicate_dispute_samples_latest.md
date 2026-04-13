# Predicate Dispute Samples

- db_path: `D:\毕业设计数据处理\langchain-miniopenclaw\backend\services\graph_service\data\graph_runtime.db`
- predicates: `药材基源, 药性特征, 利水化饮, 理气活血, 配伍禁忌, 食忌, 适应证, 功效`

## 审阅重点

- 先看 `type_distribution` 是否支持你的归一化假设。
- 再看 `top_objects` 是否暴露出“谓词=宾语”或对象值域漂移。
- 再看 `top_books`，判断该谓词是否其实只在某个来源体系中成立。
- 如果同一谓词跨多个 `subject_type/object_type` 语义空间，就不应直接物理归一。

## `药材基源`

- total: `1789`

**类型分布**

- subject_type=herb | object_type=origin | count=1789

**高频对象值**

- object=Cervus elaphus | count=8
- object=Cervus nippon | count=8
- object=Gallus gallus | count=8
- object=Citrus reticulata | count=7
- object=Nelumbo nucifera | count=7
- object=Cinnamomum camphora | count=6
- object=Pinus massoniana | count=6
- object=Zingiber officinale | count=6
- object=Bubalus bubalis | count=5
- object=Glycine max | count=5
- object=Morus alba | count=5
- object=Panax ginseng | count=5
- object=Styphnolobium japonicum | count=5
- object=Bombyx mori | count=4
- object=Bos taurus | count=4

**主要来源书**

- source_book=TCM-MKG | count=1789

**object = predicate 样本**

- -

**常规样本**

- subject=一支箭 | predicate=药材基源 | object=Ophioglossum pedunculosum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝蒿 | predicate=药材基源 | object=Artemisia rupestris | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝黄花 | predicate=药材基源 | object=Solidago altissima | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝黄花 | predicate=药材基源 | object=Solidago decurrens | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁公藤 | predicate=药材基源 | object=Erycibe obtusifolia | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁公藤 | predicate=药材基源 | object=Erycibe schmidtii | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁茄 | predicate=药材基源 | object=Solanum virginianum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香 | predicate=药材基源 | object=Syzygium aromaticum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香叶 | predicate=药材基源 | object=Leptodermis pilosa | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香油 | predicate=药材基源 | object=Syzygium aromaticum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香罗勒 | predicate=药材基源 | object=Ocimum gratissimum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香蓼 | predicate=药材基源 | object=Ludwigia prostrata | subject_type=herb | object_type=origin | source_book=TCM-MKG

**跨类型样本**

- subject=一支箭 | predicate=药材基源 | object=Ophioglossum pedunculosum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝蒿 | predicate=药材基源 | object=Artemisia rupestris | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝黄花 | predicate=药材基源 | object=Solidago decurrens | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=一枝黄花 | predicate=药材基源 | object=Solidago altissima | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁公藤 | predicate=药材基源 | object=Erycibe obtusifolia | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁公藤 | predicate=药材基源 | object=Erycibe schmidtii | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁茄 | predicate=药材基源 | object=Solanum virginianum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香 | predicate=药材基源 | object=Syzygium aromaticum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香叶 | predicate=药材基源 | object=Leptodermis pilosa | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香油 | predicate=药材基源 | object=Syzygium aromaticum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香罗勒 | predicate=药材基源 | object=Ocimum gratissimum | subject_type=herb | object_type=origin | source_book=TCM-MKG
- subject=丁香蓼 | predicate=药材基源 | object=Ludwigia prostrata | subject_type=herb | object_type=origin | source_book=TCM-MKG

## `药性特征`

- total: `2383`

**类型分布**

- subject_type=herb | object_type=property | count=2383

**高频对象值**

- object=Liver meridian | count=547
- object=Lung meridian | count=397
- object=Stomach meridian | count=321
- object=Spleen meridian | count=319
- object=Kidney meridian | count=256
- object=Heart meridian | count=206
- object=Large intestine meridian | count=165
- object=Bladder meridian | count=88
- object=Gallbladder meridian | count=41
- object=Small intestine meridian | count=30
- object=Pericardium meridian | count=10
- object=Triple burner meridian | count=3

**主要来源书**

- source_book=TCM-MKG | count=2383

**object = predicate 样本**

- -

**常规样本**

- subject=一支箭 | predicate=药性特征 | object=Liver meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁茄 | predicate=药性特征 | object=Lung meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁茄 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Kidney meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Kidney meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Lung meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香油 | predicate=药性特征 | object=Kidney meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香油 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG

**跨类型样本**

- subject=一支箭 | predicate=药性特征 | object=Liver meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁茄 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁茄 | predicate=药性特征 | object=Lung meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香 | predicate=药性特征 | object=Kidney meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Lung meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香叶 | predicate=药性特征 | object=Kidney meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香油 | predicate=药性特征 | object=Stomach meridian | subject_type=herb | object_type=property | source_book=TCM-MKG
- subject=丁香油 | predicate=药性特征 | object=Spleen meridian | subject_type=herb | object_type=property | source_book=TCM-MKG

## `利水化饮`

- total: `7`

**类型分布**

- subject_type=herb | object_type=therapy | count=7

**高频对象值**

- object=利水化饮 | count=7

**主要来源书**

- source_book=686-中医临证经验与方法 | count=7

**object = predicate 样本**

- subject=大腹皮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=白术 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=砂仁 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=苍术 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=莱菔子 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=防己 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=陈皮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文

**常规样本**

- subject=大腹皮 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=白术 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=砂仁 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=苍术 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=莱菔子 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=防己 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=陈皮 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法

**跨类型样本**

- subject=大腹皮 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=白术 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=砂仁 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=苍术 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=莱菔子 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=防己 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=陈皮 | predicate=利水化饮 | object=利水化饮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法

## `理气活血`

- total: `4`

**类型分布**

- subject_type=herb | object_type=therapy | count=4

**高频对象值**

- object=理气活血 | count=4

**主要来源书**

- source_book=686-中医临证经验与方法 | count=4

**object = predicate 样本**

- subject=丹参 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=薄荷 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=陈皮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文
- subject=青皮 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法 | source_chapter=686-中医临证经验与方法_正文

**常规样本**

- subject=丹参 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=薄荷 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=陈皮 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=青皮 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法

**跨类型样本**

- subject=丹参 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=薄荷 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=陈皮 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法
- subject=青皮 | predicate=理气活血 | object=理气活血 | subject_type=herb | object_type=therapy | source_book=686-中医临证经验与方法

## `配伍禁忌`

- total: `22241`

**类型分布**

- subject_type=herb | object_type=herb | count=6423
- subject_type=medicine | object_type=herb | count=2445
- subject_type=herb | object_type=other | count=1850
- subject_type=medicine | object_type=medicine | count=1588
- subject_type=medicine | object_type=other | count=1577
- subject_type=herb | object_type=property | count=1026
- subject_type=formula | object_type=other | count=663
- subject_type=formula | object_type=herb | count=499
- subject_type=medicine | object_type=property | count=485
- subject_type=herb | object_type=symptom | count=417
- subject_type=herb | object_type=syndrome | count=405
- subject_type=herb | object_type=disease | count=404

**高频对象值**

- object=甘草 | count=336
- object=藜芦 | count=336
- object=孕妇 | count=291
- object=乌头 | count=204
- object=大黄 | count=188
- object=芫花 | count=159
- object=干姜 | count=144
- object=附子 | count=141
- object=贝母 | count=139
- object=黄连 | count=139
- object=黄芩 | count=138
- object=妊娠 | count=126
- object=半夏 | count=125
- object=人参 | count=124
- object=麻黄 | count=120

**主要来源书**

- source_book=011-本草品汇精要 | count=1078
- source_book=645-证类本草 | count=906
- source_book=036-得配本草 | count=762
- source_book=027-本草述钩元 | count=737
- source_book=003-新修本草 | count=571
- source_book=021-本草从新 | count=562
- source_book=577-医学入门 | count=554
- source_book=002-本草经集注 | count=543
- source_book=073-增广和剂局方药性总论 | count=532
- source_book=597-冯氏锦囊秘录 | count=531
- source_book=032-本草撮要 | count=497
- source_book=041-炮炙大法 | count=494

**object = predicate 样本**

- -

**常规样本**

- subject=丹参 | predicate=配伍禁忌 | object=藜芦 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=丹砂 | predicate=配伍禁忌 | object=咸水 | subject_type=herb | object_type=other | source_book=000-神农本草经
- subject=丹砂 | predicate=配伍禁忌 | object=磁石 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=半夏 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=栝蒌 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=白芨 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=白蔹 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=莽草 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=藜芦 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌喙 | predicate=配伍禁忌 | object=贝母 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌头 | predicate=配伍禁忌 | object=半夏 | subject_type=herb | object_type=herb | source_book=000-神农本草经
- subject=乌头 | predicate=配伍禁忌 | object=大豆 | subject_type=medicine | object_type=herb | source_book=000-神农本草经

**跨类型样本**

- subject=痰疠法门 | predicate=配伍禁忌 | object=乌头 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=南星 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=大戟 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=桂枝 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=细辛 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=附子 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=麻黄 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=痰疠法门 | predicate=配伍禁忌 | object=黑丑 | subject_type=book | object_type=herb | source_book=288-痰疠法门
- subject=《本草性事类》 | predicate=配伍禁忌 | object=畏恶 | subject_type=book | object_type=property | source_book=645-证类本草
- subject=《本草性事类》 | predicate=配伍禁忌 | object=相反 | subject_type=book | object_type=property | source_book=645-证类本草
- subject=十八反 | predicate=配伍禁忌 | object=乌头反诸药类 | subject_type=category | object_type=category | source_book=623-医旨绪余
- subject=十八反 | predicate=配伍禁忌 | object=甘草反诸药类 | subject_type=category | object_type=category | source_book=623-医旨绪余

## `食忌`

- total: `30188`

**类型分布**

- subject_type=formula | object_type=food | count=13818
- subject_type=herb | object_type=food | count=2138
- subject_type=disease | object_type=food | count=2106
- subject_type=food | object_type=food | count=1784
- subject_type=medicine | object_type=food | count=1644
- subject_type=food | object_type=other | count=1032
- subject_type=food | object_type=symptom | count=808
- subject_type=therapy | object_type=food | count=727
- subject_type=medicine | object_type=other | count=581
- subject_type=food | object_type=property | count=579
- subject_type=herb | object_type=other | count=492
- subject_type=other | object_type=food | count=475

**高频对象值**

- object=猪肉 | count=998
- object=菘菜 | count=699
- object=生葱 | count=686
- object=海藻 | count=670
- object=生冷 | count=452
- object=羊肉 | count=406
- object=冷水 | count=377
- object=生菜 | count=363
- object=蒜 | count=345
- object=酒 | count=341
- object=鱼 | count=337
- object=雀肉 | count=283
- object=李 | count=268
- object=鸡 | count=256
- object=桃 | count=255

**主要来源书**

- source_book=053-外台秘要 | count=4235
- source_book=074-普济方 | count=2094
- source_book=054-医心方 | count=1025
- source_book=645-证类本草 | count=714
- source_book=617-古今医统大全 | count=684
- source_book=011-本草品汇精要 | count=669
- source_book=555-饮食须知 | count=628
- source_book=577-医学入门 | count=508
- source_book=097-验方新编 | count=467
- source_book=156-幼幼新书 | count=432
- source_book=055-太平圣惠方 | count=420
- source_book=223-疡医大全 | count=401

**object = predicate 样本**

- -

**常规样本**

- subject=黍 | predicate=食忌 | object=丑 | subject_type=food | object_type=other | source_book=000-神农本草经
- subject=梨 | predicate=食忌 | object=产妇蓐中及疾病未愈，食梨多者，无 不致病 | subject_type=food | object_type=other | source_book=001-吴普本草
- subject=梨 | predicate=食忌 | object=咳逆上气者，尤宜慎之 | subject_type=food | object_type=other | source_book=001-吴普本草
- subject=梨 | predicate=食忌 | object=金创、乳妇不可食梨 | subject_type=food | object_type=other | source_book=001-吴普本草
- subject=麻蓝 | predicate=食忌 | object=叶上有毒，食之杀人 | subject_type=herb | object_type=food | source_book=001-吴普本草
- subject=丹砂 | predicate=食忌 | object=咸水 | subject_type=medicine | object_type=food | source_book=002-本草经集注
- subject=乌鸡肉 | predicate=食忌 | object=犬肝、肾 | subject_type=food | object_type=food | source_book=002-本草经集注
- subject=兔肉 | predicate=食忌 | object=妊身不可食 | subject_type=medicine | object_type=food | source_book=002-本草经集注
- subject=其实 | predicate=食忌 | object=多食令人有热 | subject_type=herb | object_type=food | source_book=002-本草经集注
- subject=冬葵 | predicate=食忌 | object=不可多食 | subject_type=herb | object_type=food | source_book=002-本草经集注
- subject=凡猪肉 | predicate=食忌 | object=不可久食 | subject_type=food | object_type=therapy | source_book=002-本草经集注
- subject=凡猪肉 | predicate=食忌 | object=病患金创者尤甚 | subject_type=food | object_type=therapy | source_book=002-本草经集注

**跨类型样本**

- subject=《病源论》 | predicate=食忌 | object=落葵 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=仓米 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=尘臭烂败之物 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=热食热羹 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=白酒 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=羊血羹 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=鲤鱼 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=麦 | subject_type=book | object_type=food | source_book=054-医心方
- subject=大清经 | predicate=食忌 | object=黄牛肉 | subject_type=book | object_type=food | source_book=054-医心方
- subject=苏敬本草注 | predicate=食忌 | object=软熟柿 | subject_type=book | object_type=food | source_book=054-医心方
- subject=养生禁忌 | predicate=食忌 | object=鱼无腮者 | subject_type=book | object_type=food | source_book=274-解围元薮
- subject=痰疠法门 | predicate=食忌 | object=大椒 | subject_type=book | object_type=food | source_book=288-痰疠法门

## `适应证`

- total: `3`

**类型分布**

- subject_type=therapy | object_type=syndrome | count=3

**高频对象值**

- object=气血俱虚，寒湿内蕴，外受风寒，偏瘫身重，心中寒，气短乏力，手足厥冷，舌苔薄白，脉沉细弦 | count=1
- object=真阴亏损，虚风内动，瘛疭瘫痪，神疲乏力，或自汗盗汗，手足心热，舌绛少苔或光剥无苔，脉虚大无根或虚而无力 | count=1
- object=肝胆实火，筋脉失养，头晕头痛，烦躁易怒，轻度偏瘫，恶热，尿黄赤，舌质红苔黄或黄白，脉弦数者 | count=1

**主要来源书**

- source_book=686-中医临证经验与方法 | count=3

**object = predicate 样本**

- -

**常规样本**

- subject=柔肝熄风法 | predicate=适应证 | object=真阴亏损，虚风内动，瘛疭瘫痪，神疲乏力，或自汗盗汗，手足心热，舌绛少苔或光剥无苔，脉虚大无根或虚而无力 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法
- subject=益气散风法 | predicate=适应证 | object=气血俱虚，寒湿内蕴，外受风寒，偏瘫身重，心中寒，气短乏力，手足厥冷，舌苔薄白，脉沉细弦 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法
- subject=苦寒泻火法 | predicate=适应证 | object=肝胆实火，筋脉失养，头晕头痛，烦躁易怒，轻度偏瘫，恶热，尿黄赤，舌质红苔黄或黄白，脉弦数者 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法

**跨类型样本**

- subject=柔肝熄风法 | predicate=适应证 | object=真阴亏损，虚风内动，瘛疭瘫痪，神疲乏力，或自汗盗汗，手足心热，舌绛少苔或光剥无苔，脉虚大无根或虚而无力 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法
- subject=益气散风法 | predicate=适应证 | object=气血俱虚，寒湿内蕴，外受风寒，偏瘫身重，心中寒，气短乏力，手足厥冷，舌苔薄白，脉沉细弦 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法
- subject=苦寒泻火法 | predicate=适应证 | object=肝胆实火，筋脉失养，头晕头痛，烦躁易怒，轻度偏瘫，恶热，尿黄赤，舌质红苔黄或黄白，脉弦数者 | subject_type=therapy | object_type=syndrome | source_book=686-中医临证经验与方法

## `功效`

- total: `167536`

**类型分布**

- subject_type=herb | object_type=therapy | count=40449
- subject_type=medicine | object_type=therapy | count=27081
- subject_type=formula | object_type=therapy | count=26833
- subject_type=herb | object_type=property | count=21051
- subject_type=formula | object_type=property | count=20834
- subject_type=herb | object_type=other | count=10590
- subject_type=formula | object_type=other | count=6397
- subject_type=medicine | object_type=property | count=5718
- subject_type=food | object_type=therapy | count=1756
- subject_type=medicine | object_type=other | count=1597
- subject_type=therapy | object_type=property | count=1292
- subject_type=food | object_type=property | count=1217

**高频对象值**

- object=明目 | count=1082
- object=利小便 | count=1008
- object=益气 | count=620
- object=下气 | count=505
- object=杀虫 | count=462
- object=止血 | count=456
- object=安胎 | count=437
- object=补中益气 | count=434
- object=解毒 | count=414
- object=安五脏 | count=366
- object=止渴 | count=363
- object=补中 | count=327
- object=破血 | count=308
- object=利水道 | count=304
- object=益气力 | count=302

**主要来源书**

- source_book=013-本草纲目 | count=10558
- source_book=074-普济方 | count=8046
- source_book=645-证类本草 | count=5354
- source_book=597-冯氏锦囊秘录 | count=4315
- source_book=011-本草品汇精要 | count=3818
- source_book=577-医学入门 | count=3557
- source_book=617-古今医统大全 | count=3020
- source_book=027-本草述钩元 | count=2969
- source_book=021-本草从新 | count=2849
- source_book=025-本草求真 | count=2433
- source_book=073-增广和剂局方药性总论 | count=2329
- source_book=637-景岳全书 | count=2216

**object = predicate 样本**

- -

**常规样本**

- subject=KT | predicate=功效 | object=主金创，创败，轻身、不饥、耐老 | subject_type=herb | object_type=therapy | source_book=000-神农本草经
- subject=上药 | predicate=功效 | object=令人身安命延，升天神仙，遨游上下，役使万灵，体生毛羽，行厨立至 | subject_type=medicine | object_type=property | source_book=000-神农本草经
- subject=下经 | predicate=功效 | object=欲除寒热邪气，破积聚，愈疾者 | subject_type=chapter | object_type=therapy | source_book=000-神农本草经
- subject=下药 | predicate=功效 | object=除病 | subject_type=medicine | object_type=property | source_book=000-神农本草经
- subject=中经 | predicate=功效 | object=主养性以应人 | subject_type=chapter | object_type=property | source_book=000-神农本草经
- subject=中药 | predicate=功效 | object=养性 | subject_type=medicine | object_type=property | source_book=000-神农本草经
- subject=丹沙 | predicate=功效 | object=养精神，安魂魄，益气，明目 | subject_type=medicine | object_type=therapy | source_book=000-神农本草经
- subject=丹砂 | predicate=功效 | object=不老 | subject_type=herb | object_type=therapy | source_book=000-神农本草经
- subject=丹砂 | predicate=功效 | object=令人飞行、长生 | subject_type=medicine | object_type=property | source_book=000-神农本草经
- subject=丹砂 | predicate=功效 | object=养精神 | subject_type=herb | object_type=therapy | source_book=000-神农本草经
- subject=丹砂 | predicate=功效 | object=安魂魄 | subject_type=herb | object_type=therapy | source_book=000-神农本草经
- subject=丹砂 | predicate=功效 | object=明目 | subject_type=herb | object_type=therapy | source_book=000-神农本草经

**跨类型样本**

- subject=《伤寒论》 | predicate=功效 | object=提出了较为完整的六经辨证论治理论体系 | subject_type=book | object_type=other | source_book=700.李培生老中医经验集
- subject=辛味 | predicate=功效 | object=发散 | subject_type=category | object_type=formula | source_book=013-本草纲目
- subject=辛味 | predicate=功效 | object=散 | subject_type=category | object_type=formula | source_book=013-本草纲目
- subject=《神农本经》上品药 | predicate=功效 | object=遣病，药性和缓，久服获大益 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=上品药 | predicate=功效 | object=轻身益气，不老延年 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=上品药 | predicate=功效 | object=遣疾，势力和浓，久服获大益 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=上药 | predicate=功效 | object=养命，轻身益气，不老延年，多服久服不伤人 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=下品药 | predicate=功效 | object=专主攻击，不可久服，疾愈即止 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=下品药 | predicate=功效 | object=主治病 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=下品药 | predicate=功效 | object=除寒热邪气，破积聚愈疾 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=下药 | predicate=功效 | object=治病，除寒热邪气，破积聚愈疾 | subject_type=category | object_type=other | source_book=013-本草纲目
- subject=中品药 | predicate=功效 | object=主养性 | subject_type=category | object_type=other | source_book=013-本草纲目
