from __future__ import annotations

from pathlib import Path
from typing import Any

from config import get_settings
from graph.grounding_support import stringify_content
from graph.session_manager import SessionManager


class AppContext:
    def __init__(self) -> None:
        self.base_dir: Path | None = None
        self.session_manager: SessionManager | None = None

    def initialize(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.session_manager = SessionManager(base_dir)


app_context = AppContext()


def initialize_app_context(base_dir: Path) -> None:
    app_context.initialize(base_dir)


def get_backend_dir() -> Path | None:
    return app_context.base_dir


def require_backend_dir() -> Path:
    if app_context.base_dir is None:
        raise RuntimeError("application context is not initialized")
    return app_context.base_dir


def get_session_manager() -> SessionManager | None:
    return app_context.session_manager


def require_session_manager() -> SessionManager:
    if app_context.session_manager is None:
        raise RuntimeError("application context is not initialized")
    return app_context.session_manager


def _build_chat_model():
    settings = get_settings()

    if settings.llm_provider == "deepseek":
        try:
            from langchain_deepseek import ChatDeepSeek
        except ImportError as exc:  # pragma: no cover - optional dependency at runtime
            raise RuntimeError("langchain-deepseek is not installed") from exc

        if not settings.llm_api_key:
            raise RuntimeError("Missing API key for provider deepseek")
        return ChatDeepSeek(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )

    if not settings.llm_api_key:
        raise RuntimeError(f"Missing API key for provider {settings.llm_provider}")

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
        disable_streaming=True,
        max_retries=2,
    )


async def generate_title(first_user_message: str) -> str:
    prompt = (
        "请根据用户的第一条消息生成一个中文会话标题。"
        "要求不超过 10 个汉字，不要带引号，不要解释。"
    )
    try:
        response = await _build_chat_model().ainvoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": first_user_message},
            ]
        )
        title = stringify_content(getattr(response, "content", "")).strip()
        return title[:10] or "新会话"
    except Exception:
        return (first_user_message.strip() or "新会话")[:10]


async def summarize_history(messages: list[dict[str, Any]]) -> str:
    prompt = (
        "请将以下对话压缩成中文摘要，控制在 500 字以内。"
        "重点保留用户目标、已完成步骤、重要结论和未解决事项。"
    )
    lines: list[str] = []
    for item in messages:
        role = item.get("role", "assistant")
        content = str(item.get("content", "") or "")
        if content:
            lines.append(f"{role}: {content}")
    transcript = "\n".join(lines)

    try:
        response = await _build_chat_model().ainvoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript},
            ]
        )
        summary = stringify_content(getattr(response, "content", "")).strip()
        return summary[:500]
    except Exception:
        return transcript[:500]
