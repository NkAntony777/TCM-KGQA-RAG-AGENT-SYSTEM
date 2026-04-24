# External Benchmark Integration Plan

## Goal

Integrate the first batch of external TCM benchmarks into the existing paper-evaluation pipeline with minimal disruption to current scripts.

The current project already has three mature evaluation routes:

1. `paper_experiments/run_classics_vector_vs_filesfirst.py`
   - retrieval-level
   - requires gold provenance / source constraints
2. `paper_experiments/run_caseqa_vector_vs_structured.py`
   - structured case / QA retrieval-level
   - requires keyword or outline-level gold targets
3. `paper_experiments/run_end_to_end_qa_paper_eval.py`
   - HTTP end-to-end answer evaluation
   - best fit for external benchmarks that do not expose provenance gold

For the first batch of external benchmarks, the recommended default route is the third one.

## Recommended Mapping

### 1. TCMEval-SDT

Recommended route:
- `run_end_to_end_qa_paper_eval.py`

Reason:
- multi-step syndrome differentiation benchmark
- external cases do not naturally provide the same provenance schema as the internal classics retrieval benchmark
- closer to final-answer capability than to strict source-trace retrieval

Suggested local storage:
- raw files:
  - `backend/eval/datasets/external/raw/tcmeval_sdt/`
- converted draft dataset:
  - `backend/eval/datasets/external/tcmeval_sdt_draft.json`

Suggested evaluation focus:
- answer correctness
- reasoning adequacy
- conservative behavior on unsupported items

### 2. TCMEval-PA

Recommended route:
- `run_end_to_end_qa_paper_eval.py`

Reason:
- prescription-audit benchmark is primarily rule/safety QA
- existing retrieval-level scripts are not a good fit because they assume provenance-centric gold labels

Suggested local storage:
- raw files:
  - `backend/eval/datasets/external/raw/tcmeval_pa/`
- converted draft dataset:
  - `backend/eval/datasets/external/tcmeval_pa_draft.json`

Important note:
- the public data is `xlsx`
- current environment has `pandas` but may still require `openpyxl` to read `.xlsx`

### 3. TCMBench

Recommended route:
- phase 1: `run_end_to_end_qa_paper_eval.py`
- phase 2: build smaller subsets for retrieval-level or case-style evaluation if the data structure matches

Reason:
- this benchmark is broad and heterogeneous
- forcing all tasks into a single retrieval metric too early will distort conclusions

Suggested local storage:
- raw files:
  - `backend/eval/datasets/external/raw/tcmbench/`
- converted draft dataset:
  - `backend/eval/datasets/external/tcmbench_draft.json`

## Practical Integration Strategy

### Step 1: Download raw benchmark files

Keep raw data untouched under:

```text
backend/eval/datasets/external/raw/
  tcmeval_sdt/
  tcmeval_pa/
  tcmbench/
```

### Step 2: Convert raw files into the existing end-to-end dataset shape

Use:

```text
paper_experiments/build_external_end_to_end_dataset.py
```

This script creates a **draft** dataset compatible with the existing end-to-end evaluator.

Output shape:

```json
{
  "meta": { "...": "..." },
  "cases": [
    {
      "id": "external_0001",
      "category": "external_benchmark",
      "query": "question text",
      "answer_contains_any": ["gold answer token 1", "gold answer token 2"],
      "meta": {
        "raw_question": "...",
        "raw_answer": "...",
        "raw_analysis": "...",
        "raw_options": [],
        "draft_source": "external_benchmark_import",
        "needs_manual_review": true
      }
    }
  ]
}
```

### Step 3: Manual review before formal evaluation

The generated dataset is intentionally marked as `needs_manual_review`.

You should manually review:
- answer token quality
- option rendering
- whether question wording should be kept verbatim
- whether any items need `answer_forbid`
- whether route expectations should be added for some subsets

### Step 4: Flatten `cases` into the evaluator input

`run_end_to_end_qa_paper_eval.py` expects a list of cases, while the draft builder outputs:

```json
{
  "meta": ...,
  "cases": [...]
}
```

Before running formal evaluation, create a cleaned list-only file, for example:

```text
backend/eval/datasets/external/tcmeval_sdt_eval_50.json
```

with contents:

```json
[
  {
    "id": "...",
    "category": "...",
    "query": "...",
    "answer_contains_any": ["..."]
  }
]
```

### Step 5: Run the existing evaluator

Example:

```powershell
& '.\.venv\Scripts\python.exe' paper_experiments\run_end_to_end_qa_paper_eval.py `
  --datasets eval\datasets\external\tcmeval_sdt_eval_50.json `
  --base-url http://127.0.0.1:8002 `
  --modes quick deep `
  --top-k 12 `
  --timeout 120 `
  --workers 0 `
  --auto-workers 8
```

## Ready-to-Use Examples

### TCMEval-PA

```powershell
& '.\.venv\Scripts\python.exe' paper_experiments\build_external_end_to_end_dataset.py `
  --input eval\datasets\external\raw\tcmeval_pa\TCMEval-PA.xlsx `
  --input-format xlsx `
  --profile tcmeval_pa `
  --output eval\datasets\external\tcmeval_pa_draft.json
```

### Generic JSON benchmark

```powershell
& '.\.venv\Scripts\python.exe' paper_experiments\build_external_end_to_end_dataset.py `
  --input eval\datasets\external\raw\tcmeval_sdt\test.json `
  --input-format json `
  --question-field question `
  --answer-field answer `
  --analysis-field explanation `
  --id-field id `
  --category-field task `
  --output eval\datasets\external\tcmeval_sdt_draft.json
```

### Generic JSONL benchmark

```powershell
& '.\.venv\Scripts\python.exe' paper_experiments\build_external_end_to_end_dataset.py `
  --input eval\datasets\external\raw\tcmbench\subset.jsonl `
  --input-format jsonl `
  --question-field question `
  --answer-field answer `
  --analysis-field analysis `
  --id-field id `
  --category-field category `
  --output eval\datasets\external\tcmbench_draft.json
```

## What Not to Do

- Do not force TCMEval-SDT or TCMEval-PA into `run_classics_vector_vs_filesfirst.py` directly.
  - Those scripts assume provenance-aware gold fields such as `expected_books_any`.
- Do not report automatically generated token-matching results as final paper results without manual review.
- Do not mix raw downloaded benchmark files with cleaned paper-facing evaluation datasets in the same folder.

## Recommended First Execution Order

1. `TCMEval-SDT`
2. `TCMEval-PA`
3. `TCMBench`

This order matches:
- reasoning transfer
- safety/rule transfer
- broad external knowledge transfer
