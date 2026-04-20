# QA Section Summary Ablation

## Aggregate

| Condition | avg_latency_ms | avg_score | book_hit_rate | fallback_rate |
| --- | --- | --- | --- | --- |
| baseline_no_summary_cache | 34436.4 | 4.12 | 12.50% | 0.00% |
| enhanced_with_summary_cache | 34586.8 | 4.17 | 12.50% | 0.00% |

## Per Case

| ID | Mode | baseline_latency | baseline_score | enhanced_latency | enhanced_score | delta_score |
| --- | --- | --- | --- | --- | --- | --- |
| qa_sum_001 | quick | 37614.8 | 4.25 | 23770.2 | 4.25 | 0.0 |
| qa_sum_001 | deep | 24442.5 | 4.25 | 23665.1 | 3.5 | -0.75 |
| qa_sum_002 | quick | 25011.8 | 2.75 | 26814.1 | 2.75 | 0.0 |
| qa_sum_002 | deep | 27113.6 | 2.75 | 32499.2 | 2.75 | 0.0 |
| qa_sum_003 | quick | 42449.0 | 4.25 | 39679.6 | 4.25 | 0.0 |
| qa_sum_003 | deep | 62896.3 | 4.25 | 81808.8 | 4.25 | 0.0 |
| qa_sum_004 | quick | 63467.0 | 4.25 | 50055.1 | 4.25 | 0.0 |
| qa_sum_004 | deep | 87741.8 | 4.25 | 90803.2 | 4.25 | 0.0 |
| qa_sum_005 | quick | 20118.8 | 3.25 | 22603.0 | 3.25 | 0.0 |
| qa_sum_005 | deep | 23847.3 | 4.25 | 19452.3 | 4.25 | 0.0 |
| qa_sum_006 | quick | 22536.5 | 5.75 | 23940.0 | 5.75 | 0.0 |
| qa_sum_006 | deep | 25087.2 | 5.75 | 20906.5 | 5.75 | 0.0 |
| qa_sum_007 | quick | 17731.3 | 3.25 | 22898.0 | 4.25 | 1.0 |
| qa_sum_007 | deep | 21653.1 | 4.25 | 17683.2 | 3.25 | -1.0 |
| qa_sum_008 | quick | 26304.5 | 4.25 | 21929.5 | 5.0 | 0.75 |
| qa_sum_008 | deep | 22967.6 | 4.25 | 34881.6 | 5.0 | 0.75 |
