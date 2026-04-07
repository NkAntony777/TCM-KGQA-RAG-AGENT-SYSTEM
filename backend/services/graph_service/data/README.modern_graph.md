## Modern Graph Artifacts

This directory can host optional runtime-compatible graph files generated from external datasets.

- `modern_graph_runtime.jsonl`
- `modern_graph_runtime.evidence.jsonl`

Generate them with:

```powershell
cd backend
python scripts/import_tcm_mkg.py --source-root D:\TCM-MKG
```

When these files exist, `GraphQueryEngine` will load them automatically with `dataset_scope=modern_graph`.
