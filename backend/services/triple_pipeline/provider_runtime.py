from __future__ import annotations

import time
from typing import Any

import httpx

from services.triple_pipeline.llm_json import extract_json_block as _extract_json_block
from services.triple_pipeline_models import LLMProviderConfig


def _is_response_format_compatibility_error(exc: httpx.HTTPStatusError, *, response_format_mode: str) -> bool:
    if response_format_mode != "json_object" or exc.response is None:
        return False
    if exc.response.status_code not in {400, 415, 422}:
        return False
    response_text = exc.response.text.lower()
    return "response_format" in response_text or "json_object" in response_text or "json_schema" in response_text

def _select_provider_sequence(self) -> list[LLMProviderConfig]:
    enabled_names = [provider.name for provider in self.config.providers if provider.enabled]
    if not enabled_names:
        return []
    with self._provider_lock:
        if not self._provider_rotation:
            ordered_names = enabled_names
        else:
            start = self._provider_cursor % len(self._provider_rotation)
            self._provider_cursor = (self._provider_cursor + 1) % max(len(self._provider_rotation), 1)
            rotated = self._provider_rotation[start:] + self._provider_rotation[:start]
            ordered_names = []
            seen: set[str] = set()
            for name in rotated:
                if name in seen:
                    continue
                seen.add(name)
                ordered_names.append(name)
            for name in enabled_names:
                if name not in seen:
                    ordered_names.append(name)
    return [self._providers_by_name[name] for name in ordered_names if name in self._providers_by_name]

def _record_provider_result(
    self,
    provider_name: str,
    *,
    success: bool,
    latency_ms: float,
    error: str = "",
) -> None:
    with self._provider_lock:
        stats = self._provider_stats.setdefault(
            provider_name,
            {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_error": "",
                "last_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "latency_sample_count": 0,
            },
        )
        stats["last_latency_ms"] = round(float(latency_ms), 2)
        stats["total_latency_ms"] = round(float(stats.get("total_latency_ms", 0.0)) + float(latency_ms), 2)
        stats["latency_sample_count"] = int(stats.get("latency_sample_count", 0)) + 1
        if success:
            stats["success_count"] = int(stats.get("success_count", 0)) + 1
            stats["consecutive_failures"] = 0
            stats["last_error"] = ""
        else:
            stats["failure_count"] = int(stats.get("failure_count", 0)) + 1
            stats["consecutive_failures"] = int(stats.get("consecutive_failures", 0)) + 1
            stats["last_error"] = error[:300]

def _reclassify_provider_success_as_failure(
    self,
    provider_name: str,
    *,
    error: str,
    latency_ms: float | None = None,
) -> None:
    with self._provider_lock:
        stats = self._provider_stats.setdefault(
            provider_name,
            {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_error": "",
                "last_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "latency_sample_count": 0,
            },
        )
        current_success = int(stats.get("success_count", 0) or 0)
        if current_success > 0:
            stats["success_count"] = current_success - 1
        stats["failure_count"] = int(stats.get("failure_count", 0) or 0) + 1
        stats["consecutive_failures"] = int(stats.get("consecutive_failures", 0) or 0) + 1
        stats["last_error"] = error[:300]
        if latency_ms is not None:
            stats["last_latency_ms"] = round(float(latency_ms), 2)

def get_provider_metrics(self) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    with self._provider_lock:
        for provider in self.config.providers:
            stats = self._provider_stats.get(provider.name, {})
            success_count = int(stats.get("success_count", 0) or 0)
            failure_count = int(stats.get("failure_count", 0) or 0)
            attempt_count = success_count + failure_count
            latency_sample_count = int(stats.get("latency_sample_count", 0) or 0)
            total_latency_ms = float(stats.get("total_latency_ms", 0.0) or 0.0)
            metrics.append(
                {
                    "name": provider.name,
                    "model": provider.model,
                    "base_url": provider.base_url,
                    "weight": int(provider.weight),
                    "enabled": bool(provider.enabled),
                    "attempt_count": attempt_count,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_rate": round(success_count / attempt_count, 4) if attempt_count else 0.0,
                    "failure_rate": round(failure_count / attempt_count, 4) if attempt_count else 0.0,
                    "avg_latency_ms": round(total_latency_ms / latency_sample_count, 2) if latency_sample_count else 0.0,
                    "last_latency_ms": round(float(stats.get("last_latency_ms", 0.0) or 0.0), 2),
                    "consecutive_failures": int(stats.get("consecutive_failures", 0) or 0),
                    "last_error": str(stats.get("last_error", "") or ""),
                }
            )
    return metrics

def format_provider_metrics_summary(self) -> str:
    metrics = self.get_provider_metrics()
    if not metrics:
        return "provider-monitor: no providers configured"
    parts = []
    for item in metrics:
        parts.append(
            f"{item['name']} ok={item['success_count']} fail={item['failure_count']} "
            f"succ={item['success_rate']:.1%} failr={item['failure_rate']:.1%} "
            f"avg={item['avg_latency_ms']:.0f}ms last={item['last_latency_ms']:.0f}ms"
        )
    return " | ".join(parts)

def _call_llm_raw_once(
    self,
    provider: LLMProviderConfig,
    prompt: str,
    *,
    response_format_mode: str = "json_object",
) -> dict[str, Any]:
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": provider.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    normalized_mode = (response_format_mode or "json_object").strip().lower()
    if normalized_mode not in {"json_object", "text"}:
        raise ValueError(f"unsupported_response_format_mode: {response_format_mode}")

    request_payload = dict(payload)
    if normalized_mode == "json_object":
        request_payload["response_format"] = {"type": "json_object"}

    started_at = time.perf_counter()
    with httpx.Client(timeout=self.config.request_timeout, http2=False) as client:
        response = client.post(url, headers=headers, json=request_payload)
        response.raise_for_status()
        body = response.json()
    latency_ms = (time.perf_counter() - started_at) * 1000
    choices = body.get("choices", [])
    if not choices:
        raise ValueError("llm_empty_choices")
    content = choices[0].get("message", {}).get("content", "")
    return {
        "raw_text": str(content),
        "usage": body.get("usage", {}) if isinstance(body.get("usage"), dict) else {},
        "finish_reason": choices[0].get("finish_reason"),
        "response_format_mode": normalized_mode,
        "raw_body": body,
        "provider_name": provider.name,
        "provider_model": provider.model,
        "provider_base_url": provider.base_url,
        "provider_latency_ms": round(latency_ms, 2),
    }

def call_llm_raw(
    self,
    prompt: str,
    *,
    response_format_mode: str = "json_object",
    provider_sequence: list[LLMProviderConfig] | None = None,
) -> dict[str, Any]:
    providers = provider_sequence or self._select_provider_sequence()
    if not providers:
        raise RuntimeError("llm_provider_not_configured")
    last_error: Exception | None = None
    total_attempts = max(self.config.max_retries + 1, len(providers))
    for attempt in range(total_attempts):
        provider = providers[attempt % len(providers)]
        attempt_started_at = time.perf_counter()
        try:
            meta = self._call_llm_raw_once(
                provider,
                prompt,
                response_format_mode=response_format_mode,
            )
            self._record_provider_result(
                provider.name,
                success=True,
                latency_ms=float(meta.get("provider_latency_ms", 0.0) or 0.0),
            )
            return meta
        except httpx.HTTPStatusError as exc:
            last_error = exc
            latency_ms = (time.perf_counter() - attempt_started_at) * 1000
            if _is_response_format_compatibility_error(exc, response_format_mode=response_format_mode):
                if attempt < total_attempts - 1:
                    backoff = self.config.retry_backoff_base * (2 ** attempt)
                    time.sleep(min(backoff, 20.0))
                continue
            self._record_provider_result(
                provider.name,
                success=False,
                latency_ms=latency_ms,
                error=f"http_{exc.response.status_code if exc.response is not None else 'unknown'}: {str(exc)}",
            )
            if attempt < total_attempts - 1:
                backoff = self.config.retry_backoff_base * (2 ** attempt)
                time.sleep(min(backoff, 20.0))
        except Exception as exc:
            last_error = exc
            latency_ms = (time.perf_counter() - attempt_started_at) * 1000
            self._record_provider_result(
                provider.name,
                success=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
            if attempt < total_attempts - 1:
                backoff = self.config.retry_backoff_base * (2 ** attempt)
                time.sleep(min(backoff, 20.0))
    raise RuntimeError(f"llm_request_failed: {last_error}")

def call_llm(self, prompt: str) -> dict[str, Any]:
    provider_sequence = self._select_provider_sequence()
    last_error: Exception | None = None
    for response_format_mode in ("json_object", "text"):
        meta: dict[str, Any] | None = None
        try:
            meta = self.call_llm_raw(
                prompt,
                response_format_mode=response_format_mode,
                provider_sequence=provider_sequence,
            )
            parsed = _extract_json_block(str(meta.get("raw_text", "")))
            if isinstance(parsed, list):
                return {"triples": parsed, "__meta__": meta}
            if isinstance(parsed, dict):
                result = dict(parsed)
                result["__meta__"] = meta
                return result
            raise ValueError("llm_json_invalid_shape")
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if response_format_mode == "json_object" and exc.response is not None and exc.response.status_code in {400, 415, 422}:
                response_text = exc.response.text.lower()
                if "response_format" in response_text or "json_object" in response_text or "json_schema" in response_text:
                    continue
            break
        except Exception as exc:
            provider_name = str(meta.get("provider_name", "")).strip() if isinstance(meta, dict) else ""
            if provider_name:
                self._reclassify_provider_success_as_failure(
                    provider_name,
                    error=f"unprocessable_response: {str(exc)}",
                    latency_ms=float(meta.get("provider_latency_ms", 0.0) or 0.0),
                )
            last_error = exc
            if response_format_mode == "json_object":
                continue
            break
    raise RuntimeError(f"llm_request_failed: {last_error}")
