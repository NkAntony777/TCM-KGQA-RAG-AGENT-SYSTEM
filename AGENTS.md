## langchain-miniopenclaw Notes

- Active subproject in this workspace: `langchain-miniopenclaw/`
- Triple pipeline backend entry: `backend/scripts/pipeline_server.py`
- Triple pipeline console page: `backend/scripts/pipeline_console.html`

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
