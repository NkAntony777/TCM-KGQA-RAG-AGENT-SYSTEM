from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


FirstEnvFn = Callable[..., str]
NormalizeProvidersFn = Callable[..., list[Any]]


def build_pipeline(
    *,
    cfg_override: dict[str, Any] | None,
    pipeline_config_cls: type,
    pipeline_cls: type,
    default_books_dir: Path,
    default_output_dir: Path,
    first_env: FirstEnvFn,
    normalize_provider_configs: NormalizeProvidersFn,
) -> Any:
    cfg = cfg_override or {}
    model = cfg.get("model") or first_env("TRIPLE_LLM_MODEL", "LLM_MODEL", default="mimo-v2-pro")
    api_key_raw = cfg.get("api_key")
    if not api_key_raw:
        api_key_raw = first_env("TRIPLE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    api_key = api_key_raw
    base_url = cfg.get("base_url") or first_env(
        "TRIPLE_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL",
        default="https://api.siliconflow.cn/v1",
    )
    providers = normalize_provider_configs(
        cfg.get("providers", []),
        fallback_model=model,
        fallback_api_key=api_key or "",
        fallback_base_url=base_url,
    )
    config = pipeline_config_cls(
        books_dir=Path(cfg.get("books_dir") or default_books_dir),
        output_dir=Path(cfg.get("output_dir") or default_output_dir),
        model=model,
        api_key=api_key or "dummy_for_dry_run",
        base_url=base_url,
        providers=providers,
        request_timeout=float(cfg.get("request_timeout", 314.0)),
        max_chunk_chars=int(cfg.get("max_chunk_chars", 800)),
        chunk_overlap=int(cfg.get("chunk_overlap", 200)),
        max_retries=int(cfg.get("max_retries", 2)),
        request_delay=float(cfg.get("request_delay", 1.1)),
        parallel_workers=max(1, int(cfg.get("parallel_workers", 11))),
        retry_backoff_base=float(cfg.get("retry_backoff_base", 2.0)),
        chunk_strategy=str(cfg.get("chunk_strategy", "body_first")),
    )
    return pipeline_cls(config)
