## Modern Retrieval Corpus

Optional modern evidence corpus generated from `HERB 2.0`:

- `herb2_modern_corpus.json`

Generate it with:

```powershell
cd backend
python scripts/import_herb2.py --source-root D:\herb2.0
```

Index bundled corpora together with:

```powershell
cd backend
python services/retrieval_service/index_configured_corpora.py --reset
```
