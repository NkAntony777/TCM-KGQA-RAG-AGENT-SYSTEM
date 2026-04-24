# Paired Significance Analysis

## Overview

| Field | Value |
| --- | --- |
| input_json | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\official_rerun_20260419\caseqa_vector_vs_structured_latest.json |
| format | caseqa_pair |
| left | structured |
| right | vector |
| bootstrap_iterations | 5000 |

## Metrics

| Metric | Paired Cases | Left Mean | Right Mean | Delta Mean | 95% CI | Wins | Losses | Ties | Sign Test p | Better Direction |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| top1_hit | 48 | 0.875 | 0.854167 | 0.020833 | [-0.104167, 0.166667] | 6 | 5 | 37 | 1.0 | higher |
| topk_hit | 48 | 0.9375 | 0.9375 | 0.0 | [-0.104167, 0.104167] | 3 | 3 | 42 | 1.0 | higher |
| coverage_any | 48 | 0.762502 | 0.684377 | 0.078125 | [-0.020485, 0.175694] | 17 | 9 | 22 | 0.168638 | higher |
| keypoint_recall | 48 | 0.59595 | 0.529244 | 0.066706 | [-0.018956, 0.152429] | 19 | 13 | 16 | 0.377086 | higher |
| keypoint_f1 | 48 | 0.337235 | 0.336615 | 0.000621 | [-0.059594, 0.059985] | 25 | 21 | 2 | 0.658738 | higher |
| preferred_hit | 48 | 0.6875 | 0.75 | -0.0625 | [-0.229167, 0.083333] | 6 | 9 | 33 | 0.607239 | higher |
| latency_ms | 48 | 4174.20625 | 20152.25 | -15978.04375 | [-20685.739583, -11724.422917] | 4 | 44 | 0 | 0.0 | lower |
