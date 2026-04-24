"""Provider configuration normalization for triple extraction."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from services.triple_pipeline_models import LLMProviderConfig


def first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def sanitize_provider_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(name or "").strip())
    return cleaned.strip("_") or f"provider_{index}"


def provider_to_dict(provider: LLMProviderConfig) -> dict[str, Any]:
    return {
        "name": provider.name,
        "model": provider.model,
        "base_url": provider.base_url,
        "weight": int(provider.weight),
        "enabled": bool(provider.enabled),
        "api_key_set": bool(provider.api_key),
    }


def is_response_format_compatibility_error(exc: httpx.HTTPStatusError, *, response_format_mode: str) -> bool:
    normalized_mode = (response_format_mode or "").strip().lower()
    if normalized_mode != "json_object":
        return False
    response = exc.response
    if response is None or response.status_code not in {400, 415, 422}:
        return False
    try:
        response_text = response.text.lower()
    except Exception:
        response_text = ""
    return any(token in response_text for token in ("response_format", "json_object", "json_schema"))


def load_env_provider_dicts() -> list[dict[str, Any]]:
    raw_env_providers = first_env("TRIPLE_LLM_PROVIDERS")
    if not raw_env_providers:
        return []
    try:
        decoded = json.loads(raw_env_providers)
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []


def env_flag(*names: str, default: bool | None = None) -> bool | None:
    raw = first_env(*names)
    if not raw:
        return default
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def build_env_provider(
    *,
    index: int,
    name_envs: tuple[str, ...],
    default_name: str,
    model_envs: tuple[str, ...],
    api_key_envs: tuple[str, ...],
    base_url_envs: tuple[str, ...],
    weight_envs: tuple[str, ...] = (),
    enabled_envs: tuple[str, ...] = (),
) -> LLMProviderConfig | None:
    enabled = env_flag(*enabled_envs, default=True) if enabled_envs else True
    if enabled is False:
        return None
    model = first_env(*model_envs)
    api_key = first_env(*api_key_envs)
    base_url = first_env(*base_url_envs)
    if not model or not api_key or not base_url:
        return None
    return LLMProviderConfig(
        name=sanitize_provider_name(first_env(*name_envs, default=default_name), index),
        model=model,
        api_key=api_key,
        base_url=base_url,
        weight=max(1, int(first_env(*weight_envs, default="1") or 1)),
        enabled=True,
    )


def normalize_provider_configs(
    raw_providers: Any,
    *,
    fallback_model: str,
    fallback_api_key: str,
    fallback_base_url: str,
) -> tuple[LLMProviderConfig, ...]:
    providers: list[LLMProviderConfig] = []
    raw_env_providers = load_env_provider_dicts()
    env_providers_by_name: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw_env_providers, start=1):
        if not isinstance(item, dict):
            continue
        name = sanitize_provider_name(str(item.get("name") or ""), index)
        env_providers_by_name[name] = item

    if not raw_providers and raw_env_providers:
        raw_providers = raw_env_providers

    if isinstance(raw_providers, list):
        for index, item in enumerate(raw_providers, start=1):
            if isinstance(item, LLMProviderConfig):
                if item.enabled and item.api_key and item.base_url and item.model:
                    providers.append(item)
                continue
            if not isinstance(item, dict):
                continue
            provider_name = sanitize_provider_name(str(item.get("name") or ""), index)
            env_match = env_providers_by_name.get(provider_name, {})
            enabled = bool(item.get("enabled", env_match.get("enabled", True)))
            model = str(item.get("model") or env_match.get("model") or fallback_model).strip()
            api_key = str(item.get("api_key") or env_match.get("api_key") or "").strip()
            base_url = str(item.get("base_url") or env_match.get("base_url") or "").strip()
            if provider_name == "primary":
                api_key = api_key or str(fallback_api_key or "").strip()
                base_url = base_url or str(fallback_base_url or "").strip()
            weight = max(1, int(item.get("weight", env_match.get("weight", 1)) or 1))
            if not enabled or not model or not api_key or not base_url:
                continue
            providers.append(
                LLMProviderConfig(
                    name=provider_name,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    weight=weight,
                    enabled=True,
                )
            )

    if providers:
        return tuple(providers)

    primary = LLMProviderConfig(
        name="primary",
        model=fallback_model,
        api_key=fallback_api_key,
        base_url=fallback_base_url,
        weight=1,
        enabled=True,
    )
    providers = [primary]

    extra_providers = [
        build_env_provider(
            index=2,
            name_envs=("TRIPLE_LLM_PROVIDER2_NAME",),
            default_name="secondary",
            model_envs=("TRIPLE_LLM_PROVIDER2_MODEL", "TRIPLE_LLM_MODEL_2", "TRIPLE_LLM_MODEL"),
            api_key_envs=("TRIPLE_LLM_PROVIDER2_API_KEY", "TRIPLE_LLM_API_KEY_2"),
            base_url_envs=("TRIPLE_LLM_PROVIDER2_BASE_URL", "TRIPLE_LLM_BASE_URL_2"),
            weight_envs=("TRIPLE_LLM_PROVIDER2_WEIGHT",),
            enabled_envs=("TRIPLE_LLM_PROVIDER2_ENABLED",),
        ),
        build_env_provider(
            index=3,
            name_envs=("TRIPLE_LLM_JMRAI_NAME",),
            default_name="jmrai",
            model_envs=("TRIPLE_LLM_JMRAI_MODEL", "LLM_MODEL"),
            api_key_envs=("TRIPLE_LLM_JMRAI_API_KEY", "LLM_API_KEY"),
            base_url_envs=("TRIPLE_LLM_JMRAI_BASE_URL", "LLM_BASE_URL"),
            weight_envs=("TRIPLE_LLM_JMRAI_WEIGHT",),
            enabled_envs=("TRIPLE_LLM_JMRAI_ENABLED",),
        ),
    ]

    existing_names = {provider.name for provider in providers}
    existing_signatures = {
        (provider.model, provider.base_url, provider.api_key)
        for provider in providers
    }
    for provider in extra_providers:
        if provider is None:
            continue
        signature = (provider.model, provider.base_url, provider.api_key)
        if provider.name in existing_names or signature in existing_signatures:
            continue
        providers.append(provider)
        existing_names.add(provider.name)
        existing_signatures.add(signature)
    return tuple(providers)
