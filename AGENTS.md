## langchain-miniopenclaw Notes

- Active subproject in this workspace: `langchain-miniopenclaw/`
- Triple pipeline backend entry: `backend/scripts/pipeline_server.py`
- Triple pipeline console page: `backend/scripts/pipeline_console.html`

## QA / Agent Status

- Current architecture direction is no longer vector-first.
- Preferred retrieval direction for this subproject is:
  - `graph + files-first + structured indexes + skills + planner`
- Treat dense/vector retrieval as a transitional compatibility layer, not the target main path.
- When documenting or modifying the QA chain, distinguish clearly between:
  - `already implemented`
  - `default main path`
  - `still retained as fallback`

## Current Retrieval Reality

- Files-first retrieval is already built and usable:
  - classics
  - HERB2 converted evidence
  - `book://`, `chapter://`, `entity://`, `alias://`
- Runtime alias expansion is already part of the retrieval stack.
- Structured non-vector QA index already exists and is now the default main path for case-QA.
- Dense retrieval still exists inside the legacy retrieval engine and case-QA path.
- Do not describe the system as “fully de-vectorized” yet.
- The accurate current wording is:
  - the project has basically implemented the non-vector retrieval method, but the old dense-compatible path has not been fully removed.

## Current Engineering Priority

- Do not spend the next iteration mainly on planner cleverness.
- The critical path is evidence-layer reliability:
  - graph hit -> stable evidence paths
  - evidence paths -> readable local evidence
  - files-first -> scoped source follow-up
- If deep mode quality regresses, first inspect:
  - `final_route`
  - `entity://` path readability
  - alias/source-scope drift
  - whether fallback secretly returned mock data

## Fallback Rule

- Service unavailability must fall back to local real engines, not mock demo data.
- If graph or retrieval sidecar services are down:
  - graph calls should fall back to local runtime graph
  - retrieval calls should fall back to local retrieval engine
- If local dense embedding is unavailable during retrieval fallback:
  - prefer degrading to `files_first`
  - do not silently make dense the only usable path again

## Triple Pipeline Behavior

- Empty book selection on `start` means automatic batch mode.
- Automatic batch mode now prioritizes recommended books, excludes historically completed books, and starts with 7 books per batch.
- Each automatic batch creates its own independent run directory. It does not append later batches into the same run directory.
- Automatic next-batch chaining applies to empty-selection `start` requests and also to `resume` requests by default.
- `resume` first continues the specified existing run, then continues with new batch runs if unprocessed books remain.
- Retry worker count is `max(1, parallel_workers // 2)`. With the current default `parallel_workers=11`, retry workers are `5`.

## Current Default Extraction Parameters

- `request_timeout = 314`
- `request_delay = 1.1`
- `parallel_workers = 11`

## Data Safety

- Do not commit `.env`, runtime extraction outputs, Nebula local data, or graph runtime data files.
- Do not change relation types to work around mojibake or parsing issues. Prefer decoding, normalization, or compatibility parsing.
- Preserve per-run isolation so checkpointing, resume, publish, and audit remain traceable.

## Dependency Management

- For this subproject, install or sync Python dependencies with `uv` only.
- Prefer `uv sync`, `uv add`, or `uv pip install --python <venv-python>` over direct `pip install`.
- If a runtime dependency is missing in `backend/.venv`, default to fixing it with `uv` first.
- If `uv` or pytest fails inside the sandbox because it cannot write to the default cache, temp, or managed interpreter directories:
  - first try project-local cache overrides
  - if that still fails, prefer rerunning `uv` / `pytest` outside the sandbox instead of switching to `pip`
- When rerunning tests outside the sandbox for this repo, prefer the project interpreter directly:
  - `backend/.venv/Scripts/python.exe -m pytest ...`
- When using `uv` outside the sandbox, state briefly that the reason is Windows cache/temp permission limits rather than a code failure.
