from __future__ import annotations

from dataclasses import dataclass

import httpx

from config import Settings, get_settings


@dataclass
class GroundedAnswerLLMClient:
    settings: Settings | None = None
    timeout_seconds: float = 60.0

    async def acomplete(self, *, system_prompt: str, user_prompt: str) -> str:
        settings = self.settings or get_settings()
        if not settings.llm_api_key:
            raise RuntimeError("llm_api_key_missing")

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("llm_empty_choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            return "".join(parts).strip()
        return str(content or "").strip()
