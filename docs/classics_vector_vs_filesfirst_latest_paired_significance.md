# Paired Significance Analysis

## Overview

| Field | Value |
| --- | --- |
| input_json | D:\毕业设计数据处理\langchain-miniopenclaw\backend\eval\paper\official_rerun_20260419\classics_vector_vs_filesfirst_latest.json |
| format | classics_pair |
| left | files_first |
| right | vector |
| bootstrap_iterations | 5000 |

## Metrics

| Metric | Paired Cases | Left Mean | Right Mean | Delta Mean | 95% CI | Wins | Losses | Ties | Sign Test p | Better Direction |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| topk_book_hit | 72 | 0.375 | 0.194444 | 0.180556 | [0.041667, 0.319444] | 20 | 7 | 45 | 0.019157 | higher |
| topk_provenance_hit | 72 | 0.375 | 0.194444 | 0.180556 | [0.041667, 0.319444] | 20 | 7 | 45 | 0.019157 | higher |
| topk_answer_provenance_hit | 72 | 0.361111 | 0.194444 | 0.166667 | [0.027778, 0.305556] | 20 | 8 | 44 | 0.035698 | higher |
| answer_keypoint_recall | 72 | 0.722176 | 0.603618 | 0.118558 | [0.036456, 0.198249] | 33 | 13 | 26 | 0.004534 | higher |
| source_mrr | 72 | 0.379629 | 0.386572 | -0.006943 | [-0.062497, 0.048614] | 5 | 7 | 60 | 0.774414 | higher |
| latency_ms | 72 | 10112.820833 | 5151.430556 | 4961.390278 | [3368.422222, 6431.022222] | 63 | 9 | 0 | 0.0 | lower |
