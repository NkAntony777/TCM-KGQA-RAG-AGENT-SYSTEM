# Classics Six-Baseline Summary

## Overview

本文档汇总古籍来源敏感检索实验中的六个对照方法，便于论文表格统一引用。前四个方法来自 2026-04-19 official rerun 的 `Classics_Baseline_Matrix_Latest.md` 与 `Classics_Baseline_Matrix_External_Validation_Latest.md`；后两个开源工程基线来自 2026-04-24 补跑的 `run_classics_framework_baselines.py`。

| Field | Value |
| --- | --- |
| main_dataset | `backend/eval/datasets/paper/classics_vector_vs_filesfirst_seed_20.json` |
| external_validation_dataset | `backend/eval/datasets/paper/classics_vector_vs_filesfirst_external_validation_12.json` |
| sqlite_asset | `backend/storage/classics_vector_store.sqlite` |
| main_cases | 72 |
| external_validation_cases | 24 |
| top_k | 3 |
| candidate_k | 20 |

## Six-Baseline Aggregate

| Method | Type | Main topk_book | External topk_book | External avg_source_mrr | Main topk_keyword | External topk_keyword | Main avg_latency_ms | External avg_latency_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `files_first_internal` | FFSR structured main chain | 0.3750 | 0.6667 | 0.5417 | 0.9861 | 0.8750 | 10241.0 | 11190.1 |
| `external_bm25_docs` | Simple SQLite FTS/BM25 lexical baseline | 0.2222 | 0.5833 | 0.4722 | 0.9444 | 0.9583 | 4052.6 | 3560.1 |
| `vector_sqlite_internal` | Internal hybrid vector baseline | 0.1944 | 0.2083 | 0.1389 | 0.9722 | 0.8750 | 3301.8 | 6167.2 |
| `external_dense_candidates` | Simple dense candidate baseline | 0.0833 | 0.1667 | 0.0972 | 0.8194 | 0.5000 | 1809.0 | 2960.7 |
| `llamaindex_sqlite_dense` | LlamaIndex dense framework baseline | 0.3611 | 0.4583 | 0.3750 | 0.9861 | 0.9167 | 2225.7 | 1557.9 |
| `haystack_inmemory_bm25` | Haystack default BM25 framework baseline | 0.0833 | 0.1667 | 0.1667 | 0.7639 | 0.6250 | 1239.9 | 1397.8 |

## Baseline Setup

`files_first_internal` is the FFSR structured retrieval chain. It uses book-level outlines, navigation groups, section positioning, and source-aware ranking. It is the main structured retrieval path in the paper, not an external framework baseline.

`external_bm25_docs` is a simple lexical baseline implemented directly on the existing SQLite FTS table. It does not use navigation groups, source-aware reranking, alias expansion, or evidence-path supplementation.

`vector_sqlite_internal` uses the existing SQLite vector store with candidate recall, dense scores, sparse scores, and RRF-style fusion. It is stronger than a plain dense nearest-neighbor baseline and serves as the internal hybrid vector baseline.

`external_dense_candidates` uses the existing `dense_blob` vectors from the SQLite vector store and ranks lightweight candidates by dense similarity only. It is intended as a lower-bound dense retrieval baseline without structural constraints.

`llamaindex_sqlite_dense` reuses `vector_rows.dense_blob` from `classics_vector_store.sqlite`; it does not re-embed the ancient-text corpus. The embeddings are converted into a local float32 matrix cache, and the LlamaIndex retriever interface returns top-k chunks by cosine similarity between the query embedding and existing document embeddings. It does not use FFSR navigation groups or source-aware reranking.

`haystack_inmemory_bm25` reads the same SQLite ancient-text rows into Haystack `InMemoryDocumentStore` and uses `InMemoryBM25Retriever` default ranking. It is a framework-level BM25 baseline and does not use FFSR navigation groups, alias expansion, or evidence-path supplementation.

## Interpretation

The six-baseline comparison supports three points. First, FFSR has the strongest external-validation source control: `topk_book = 0.6667` and `avg_source_mrr = 0.5417`. Second, LlamaIndex dense retrieval is competitive on the main set (`topk_book = 0.3611`) but drops on external validation (`0.4583`), indicating that plain dense framework retrieval does not provide the same new-question robustness as the structured source-aware chain. Third, Haystack default BM25 is weaker than both FFSR and the simple SQLite FTS/BM25 baseline under this asset and scoring protocol, suggesting that the advantage is not simply caused by replacing vector retrieval with a generic BM25 framework.

## Source Files

| Result | File |
| --- | --- |
| Four-way baseline matrix, main set | `docs/official_rerun_20260419/Classics_Baseline_Matrix_Latest.md` |
| Four-way baseline matrix, external validation | `docs/official_rerun_20260419/Classics_Baseline_Matrix_External_Validation_Latest.md` |
| Framework baselines, main set | `docs/Classics_Framework_Baselines_Latest.md` |
| Framework baselines, external validation | `docs/Classics_Framework_Baselines_External_Validation_Latest.md` |
| Framework baseline script | `backend/paper_experiments/run_classics_framework_baselines.py` |
