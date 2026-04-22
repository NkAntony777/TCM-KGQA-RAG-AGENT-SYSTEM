from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from config import get_settings, runtime_config
from graph.grounding_support import build_mock_answer as _build_mock_answer
from graph.grounding_support import collect_graph_evidence as _collect_graph_evidence
from graph.grounding_support import collect_retrieval_evidence as _collect_retrieval_evidence
from graph.grounding_support import extract_route_and_evidence as _extract_route_and_evidence
from graph.grounding_support import extract_tool_meta as _extract_tool_meta
from graph.grounding_support import safe_json_loads as _safe_json_loads
from graph.grounding_support import stringify_content as _stringify_content
from graph.grounding_support import summarize_graph_result as _summarize_graph_result
from graph.grounding_support import summarize_retrieval_result as _summarize_retrieval_result
from graph.memory_indexer import memory_indexer
from graph.prompt_builder import build_system_prompt
from graph.session_manager import SessionManager
from services.common.medical_guard import RiskLevel, append_disclaimer, assess_query
from tools import get_all_tools

class AgentManager:
    def __init__(self) -> None:
        self.base_dir: Path | None = None
        self.session_manager: SessionManager | None = None
        self.tools = []

    def initialize(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.session_manager = SessionManager(base_dir)
        self.tools = get_all_tools(base_dir)

    def _build_chat_model(self):
        settings = get_settings()

        if settings.llm_provider == "deepseek":
            try:
                from langchain_deepseek import ChatDeepSeek
            except ImportError as exc:  # pragma: no cover - optional dependency at runtime
                raise RuntimeError("langchain-deepseek is not installed") from exc

            if ChatDeepSeek is None:
                raise RuntimeError("langchain-deepseek is not installed")
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

    def _build_agent(self):
        if self.base_dir is None:
            raise RuntimeError("AgentManager is not initialized")

        from langchain.agents import create_agent

        system_prompt = build_system_prompt(self.base_dir, runtime_config.get_rag_mode())
        return create_agent(
            model=self._build_chat_model(),
            tools=self.tools,
            system_prompt=system_prompt,
        )

    def _get_tool(self, name: str):
        for tool in self.tools:
            if getattr(tool, "name", "") == name:
                return tool
        return None

    def _build_messages(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for item in history:
            role = item.get("role")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": str(item.get("content", ""))})
        return messages

    def _format_retrieval_context(self, results: list[dict[str, Any]]) -> str:
        lines = ["[RAG retrieved memory context]"]
        for idx, item in enumerate(results, start=1):
            text = str(item.get("text", "")).strip()
            source = str(item.get("source", "memory/MEMORY.md"))
            lines.append(f"{idx}. Source: {source}\n{text}")
        return "\n\n".join(lines)

    def _should_use_siliconflow_direct(self) -> bool:
        settings = get_settings()
        base_url = (settings.llm_base_url or "").lower()
        return "siliconflow.cn" in base_url

    def _get_recent_history_messages(self, history: list[dict[str, Any]], max_messages: int = 6) -> list[dict[str, str]]:
        messages = self._build_messages(history)
        if max_messages <= 0:
            return []
        return messages[-max_messages:]

    def _build_grounded_user_prompt(self, query: str, route_output: str) -> str:
        payload = _safe_json_loads(route_output)
        if not isinstance(payload, dict):
            return (
                f"用户问题：{query}\n"
                "请直接用中文回答，若证据不足请明确说明。不要输出 JSON、代码块或工具调用过程。"
            )

        lines = [
            "你将基于后端已经完成的中医路由与证据结果回答用户问题。",
            f"用户问题：{query}",
            f"最终路由：{payload.get('final_route', payload.get('route', 'unknown'))}",
        ]

        if payload.get("status") and payload.get("status") != "ok":
            lines.append(f"当前状态：{payload['status']}")

        graph_result = payload.get("graph_result")
        retrieval_result = payload.get("retrieval_result")

        graph_lines = _summarize_graph_result(graph_result) if isinstance(graph_result, dict) else []
        retrieval_lines = _summarize_retrieval_result(retrieval_result) if isinstance(retrieval_result, dict) else []

        if graph_lines:
            lines.append("图谱证据：")
            lines.extend(f"- {item}" for item in graph_lines)

        if retrieval_lines:
            lines.append("文献证据：")
            lines.extend(f"- {item}" for item in retrieval_lines)

        evidence: list[dict[str, Any]] = []
        if isinstance(graph_result, dict):
            _collect_graph_evidence(graph_result, evidence)
        if isinstance(retrieval_result, dict):
            _collect_retrieval_evidence(retrieval_result, evidence)
        if evidence:
            lines.append("可引用来源：")
            for item in evidence[:6]:
                source = str(item.get("source", "unknown"))
                snippet = str(item.get("snippet", "")).strip()
                if snippet:
                    lines.append(f"- {source}：{snippet[:120]}")

        lines.extend(
            [
                "输出要求：",
                "- 直接回答用户问题，不要复述检索过程。",
                "- 不要输出 JSON、trace_id、code、message、tool 名称或原始 payload。",
                "- 优先给出核心结论，再补充主治/证候/治法/出处。",
                "- 回答末尾可用“依据：...”简要列出 1-3 条来源。",
                "- 若证据有限，请明确说明“依据有限”。",
            ]
        )

        return "\n".join(lines)

    async def _siliconflow_stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str,
    ):
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "stream": True,
        }

        timeout = httpx.Timeout(connect=20.0, read=None, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {})
                        text = _stringify_content(delta.get("content", ""))
                        if text:
                            yield text

    async def _siliconflow_complete_chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str,
    ) -> str:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        choices = body.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return _stringify_content(message.get("content", "")).strip()

    async def _stream_siliconflow_grounded_answer(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        route_output: str,
    ):
        settings = get_settings()
        if not settings.llm_api_key:
            async for fallback_event in self._stream_route_fallback(message, "Missing API key for SiliconFlow direct mode"):
                yield fallback_event
            return

        system_prompt = build_system_prompt(self.base_dir, runtime_config.get_rag_mode()) if self.base_dir else ""
        grounded_prompt = self._build_grounded_user_prompt(message, route_output)
        request_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        request_messages.extend(self._get_recent_history_messages(history, max_messages=6))
        request_messages.append({"role": "user", "content": grounded_prompt})

        final_content_parts: list[str] = []
        try:
            async for token in self._siliconflow_stream_chat(
                messages=request_messages,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            ):
                final_content_parts.append(token)
                yield {"type": "token", "content": token}
        except Exception:
            try:
                content = await self._siliconflow_complete_chat(
                    messages=request_messages,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
                if content:
                    final_content_parts.append(content)
                    yield {"type": "token", "content": content}
            except Exception as exc:
                async for fallback_event in self._stream_answer_from_route_output(message, route_output, str(exc)):
                    yield fallback_event
                return

        final_content = "".join(final_content_parts).strip()
        if not final_content:
            async for fallback_event in self._stream_answer_from_route_output(message, route_output, "siliconflow_empty_response"):
                yield fallback_event
            return
        yield {"type": "done", "content": final_content}

    async def _stream_route_fallback(self, message: str, llm_error: str):
        route_tool = self._get_tool("tcm_route_search")
        if route_tool is None:
            yield {"type": "error", "error": f"LLM unavailable and route tool missing: {llm_error}"}
            yield {"type": "done", "content": ""}
            return

        tool_input = json.dumps({"query": message, "top_k": 12}, ensure_ascii=False)
        yield {"type": "tool_start", "tool": "tcm_route_search", "input": tool_input}
        output = route_tool._run(query=message, top_k=12)
        yield {
            "type": "tool_end",
            "tool": "tcm_route_search",
            "output": output,
            "meta": _extract_tool_meta("tcm_route_search", output),
        }
        route_event, evidence_items = _extract_route_and_evidence("tcm_route_search", output)
        if route_event:
            yield {"type": "route", **route_event}
        if evidence_items:
            yield {"type": "evidence", "tool": "tcm_route_search", "items": evidence_items}
        yield {"type": "new_response"}
        answer = _build_mock_answer(message, output, llm_error)
        yield {"type": "token", "content": answer}
        yield {"type": "done", "content": answer}

    async def _stream_answer_from_route_output(self, message: str, route_output: str, llm_error: str):
        answer = _build_mock_answer(message, route_output, llm_error)
        yield {"type": "token", "content": answer}
        yield {"type": "done", "content": answer}

    async def astream(
        self,
        message: str,
        history: list[dict[str, Any]],
    ):
        if self.base_dir is None:
            raise RuntimeError("AgentManager is not initialized")

        # ── S4 医疗边界前置检查 ────────────────────────────────────────────
        guard = assess_query(message)
        if guard.should_refuse:
            # 高风险拒答：直接返回拒答文本，不进入路由/LLM
            yield {"type": "guard", "risk_level": guard.risk_level.value,
                   "matched_patterns": guard.matched_patterns}
            refuse_text = guard.refuse_response
            yield {"type": "token", "content": refuse_text}
            yield {"type": "done", "content": refuse_text}
            return
        # ─────────────────────────────────────────────────────────────────

        rag_mode = runtime_config.get_rag_mode()
        augmented_history = list(history)
        if rag_mode:
            retrievals = memory_indexer.retrieve(message, top_k=3)
            yield {"type": "retrieval", "query": message, "results": retrievals}
            if retrievals:
                augmented_history.append(
                    {
                        "role": "assistant",
                        "content": self._format_retrieval_context(retrievals),
                    }
                )

        if self._should_use_siliconflow_direct():
            route_tool = self._get_tool("tcm_route_search")
            if route_tool is None:
                yield {"type": "error", "error": "SiliconFlow direct mode requires tcm_route_search"}
                yield {"type": "done", "content": ""}
                return

            tool_input = json.dumps({"query": message, "top_k": 12}, ensure_ascii=False)
            yield {"type": "tool_start", "tool": "tcm_route_search", "input": tool_input}
            route_output = route_tool._run(query=message, top_k=12)
            yield {
                "type": "tool_end",
                "tool": "tcm_route_search",
                "output": route_output,
                "meta": _extract_tool_meta("tcm_route_search", route_output),
            }
            route_event, evidence_items = _extract_route_and_evidence("tcm_route_search", route_output)
            if route_event:
                yield {"type": "route", **route_event}
            if evidence_items:
                yield {"type": "evidence", "tool": "tcm_route_search", "items": evidence_items}
            yield {"type": "new_response"}
            final_sf_parts: list[str] = []
            async for event in self._stream_siliconflow_grounded_answer(
                message=message,
                history=augmented_history,
                route_output=route_output,
            ):
                # intercept the done event to attach disclaimer
                if event.get("type") == "done":
                    content = str(event.get("content", ""))
                    if guard.disclaimer:
                        content = append_disclaimer(content, guard.disclaimer)
                    yield {"type": "done", "content": content}
                else:
                    final_sf_parts.append(str(event.get("content", "")))
                    yield event
            return

        try:
            agent = self._build_agent()
        except Exception as exc:
            async for fallback_event in self._stream_route_fallback(message, str(exc)):
                yield fallback_event
            return

        messages = self._build_messages(augmented_history)
        messages.append({"role": "user", "content": message})

        final_content_parts: list[str] = []
        last_ai_message = ""
        pending_tools: dict[str, dict[str, str]] = {}

        try:
            async for mode, payload in agent.astream(
                {"messages": messages},
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    chunk, _metadata = payload
                    text = _stringify_content(getattr(chunk, "content", ""))
                    if text:
                        final_content_parts.append(text)
                        yield {"type": "token", "content": text}
                    continue

                if mode != "updates":
                    continue

                for update in payload.values():
                    for agent_message in update.get("messages", []):
                        message_type = getattr(agent_message, "type", "")
                        tool_calls = getattr(agent_message, "tool_calls", []) or []

                        if message_type == "ai" and not tool_calls:
                            candidate = _stringify_content(getattr(agent_message, "content", ""))
                            if candidate:
                                last_ai_message = candidate

                        if tool_calls:
                            for tool_call in tool_calls:
                                call_id = str(tool_call.get("id") or tool_call.get("name"))
                                tool_name = str(tool_call.get("name", "tool"))
                                tool_args = tool_call.get("args", "")
                                if not isinstance(tool_args, str):
                                    tool_args = json.dumps(tool_args, ensure_ascii=False)
                                pending_tools[call_id] = {
                                    "tool": tool_name,
                                    "input": str(tool_args),
                                }
                                yield {
                                    "type": "tool_start",
                                    "tool": tool_name,
                                    "input": str(tool_args),
                                }

                        if message_type == "tool":
                            tool_call_id = str(getattr(agent_message, "tool_call_id", ""))
                            pending = pending_tools.pop(
                                tool_call_id,
                                {"tool": getattr(agent_message, "name", "tool"), "input": ""},
                            )
                            output = _stringify_content(getattr(agent_message, "content", ""))
                            tool_meta = _extract_tool_meta(pending["tool"], output)
                            yield {
                                "type": "tool_end",
                                "tool": pending["tool"],
                                "output": output,
                                "meta": tool_meta,
                            }
                            route_event, evidence_items = _extract_route_and_evidence(
                                pending["tool"],
                                output,
                            )
                            if route_event:
                                yield {"type": "route", **route_event}
                            if evidence_items:
                                yield {
                                    "type": "evidence",
                                    "tool": pending["tool"],
                                    "items": evidence_items,
                                }
                            yield {"type": "new_response"}
        except Exception as exc:
            async for fallback_event in self._stream_route_fallback(message, str(exc)):
                yield fallback_event
            return

        final_content = "".join(final_content_parts).strip() or last_ai_message.strip()
        # ── S4 免责声明追加 ───────────────────────────────────────────────
        if guard.disclaimer:
            final_content = append_disclaimer(final_content, guard.disclaimer)
        # ─────────────────────────────────────────────────────────────────
        yield {"type": "done", "content": final_content}

    async def generate_title(self, first_user_message: str) -> str:
        prompt = (
            "请根据用户的第一条消息生成一个中文会话标题。"
            "要求不超过 10 个汉字，不要带引号，不要解释。"
        )
        try:
            response = await self._build_chat_model().ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": first_user_message},
                ]
            )
            title = _stringify_content(getattr(response, "content", "")).strip()
            return title[:10] or "新会话"
        except Exception:
            return (first_user_message.strip() or "新会话")[:10]

    async def summarize_history(self, messages: list[dict[str, Any]]) -> str:
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
            response = await self._build_chat_model().ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": transcript},
                ]
            )
            summary = _stringify_content(getattr(response, "content", "")).strip()
            return summary[:500]
        except Exception:
            return transcript[:500]


agent_manager = AgentManager()
