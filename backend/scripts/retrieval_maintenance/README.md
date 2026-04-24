# Retrieval Maintenance Scripts

These scripts are offline maintenance entry points for rebuilding retrieval indexes and caches. They are intentionally kept outside `services/retrieval_service/` so the service package stays focused on runtime code.

Run them from `backend/` with the project environment, for example:

```powershell
uv run python scripts/retrieval_maintenance/index_configured_corpora.py --files-first --status
uv run python scripts/retrieval_maintenance/generate_nav_group_cache.py
```

Do not import these scripts from production services. Runtime retrieval should go through `services.retrieval_service.engine`.
