# Origin/source regression probe — 2026-04-09

- Dataset: `backend/eval/datasets/qa_origin_source_probe_4.json`
- Command: inline Python call to `eval.runners.run_qa_weakness_probe.run_probe(...)` against `http://127.0.0.1:8002` with modes `quick` + `deep`, `top_k=12`, `timeout=180s`
- Total: 8
- Passed: 4
- Failed: 4

## Category summary
- origin_source: failed=0/2, avg_latency_ms=30187.5
- origin_clause: failed=4/6, avg_latency_ms=53517.9

## Top issues
- book_missing_any:伤寒论: 4
- route_mismatch:graph!=hybrid: 2

## Failing cases
### origin_003 [quick]
- Query: 《伤寒论》第96条小柴胡汤方后注“若咳者，去人参、大枣、生姜，加五味子半升、干姜二两”是什么意思？
- Route: hybrid
- Issues: book_missing_any:伤寒论
- Books: 伤寒论辩证广注; 医学纲目; 圣济总录; 长沙方歌括
- Answer preview: 这是针对小柴胡汤证兼有咳嗽症状时的药物加减法。

原方中的人参、大枣、生姜性偏甘壅或辛散，可能助湿生痰，不利于止咳平喘，故去除。加入五味子以收敛肺气、止咳平喘，加入干姜以温肺化饮、散寒止咳。这一加一减，旨在针对咳嗽的病机（常为寒饮犯肺）进行精准调整，使全方在和解少阳的基础上，兼能温肺止咳。

依据：
1. 《圣济总录》记载小柴胡汤方使用药材含人参。
2. 《伤寒论辩证广注》指出小柴胡汤主治少阳证，症见往来寒热而呕。

### origin_003 [deep]
- Query: 《伤寒论》第96条小柴胡汤方后注“若咳者，去人参、大枣、生姜，加五味子半升、干姜二两”是什么意思？
- Route: hybrid
- Issues: book_missing_any:伤寒论
- Books: 伤寒论注; 伤寒论辩证广注; 医方论; 圣济总录; 本草经解; 长沙方歌括
- Answer preview: 这是针对小柴胡汤证兼有咳嗽症状时的药物加减法，其核心在于调整方剂以温化寒饮、敛肺止咳。

**具体含义是：**
当患者具备小柴胡汤主治的少阳证（如往来寒热、胸胁苦满等），同时又出现咳嗽症状时，需要对原方进行加减。需要去掉人参、大枣、生姜这三味药，再加入五味子半升和干姜二两。

**方义解析：**
1.  **去掉人参、大枣**：因二药味甘，甘能壅气助湿，可能妨碍气机宣降，不利于咳嗽的消除。
2.  **去掉生姜**：原方中的生姜主要针对…

### origin_004 [quick]
- Query: 《伤寒论》四逆散原条文主治是什么？请给接近原文的片段。
- Route: graph
- Issues: route_mismatch:graph!=hybrid; book_missing_any:伤寒论
- Books: 临证指南医案; 伤寒恒论; 伤寒论纲目; 医宗金鉴; 医方论; 景岳全书
- Answer preview: **主治**
《伤寒论》中四逆散主治少阴病，症见四肢逆冷（四逆），并可能伴有咳嗽、心悸、小便不利、腹中疼痛或腹泻、里急后重（泄利下重）等或然症。

**出处**
该条文出自《伤寒论·辨少阴病脉证并治》。其原文或最接近的经典表述为：“少阴病，四逆，其人或咳、或悸、或小便不利，或腹中痛，或泄利下重者，四逆散主之。”

依据：
1. 《伤寒恒论》记载了“少陰病，四逆，其人或咳、或悸、或小便不利，或腹中痛，或泄利下重者，四逆散主之”的条文。
2…

### origin_004 [deep]
- Query: 《伤寒论》四逆散原条文主治是什么？请给接近原文的片段。
- Route: graph
- Issues: route_mismatch:graph!=hybrid; book_missing_any:伤寒论
- Books: 临证指南医案; 伤寒恒论; 伤寒论纲目; 医宗金鉴; 医方论; 景岳全书
- Answer preview: **主治**
《伤寒论》中四逆散主治的证候是少阴病，具体表现为手足厥冷（四逆），并可能伴有咳嗽、心悸、小便不利、腹中疼痛或腹泻下重（里急后重）等或然症状。

**出处**
其原始条文出自《伤寒论》。根据后世医籍《伤寒恒论》及《伤寒论纲目》的引述，最接近原文的片段为：“少阴病，四逆，其人或咳、或悸、或小便不利，或腹中痛，或泄利下重者，四逆散主之。”

依据：
1. 《伤寒恒论》记载了四逆散主治“少阴病，四逆，其人或咳、或悸、或小便不利，或…

## Readout
- `origin_source` passed in both quick/deep on the current live backend.
- Clause-focused probes still show two remaining regression surfaces: source-book normalization for 《伤寒论》-family citations and one route expectation mismatch where the live backend stayed on `graph` despite original-text phrasing.
- This export is intended as a follow-up regression artifact for Batch 2 Lane D, not as a release gate.
