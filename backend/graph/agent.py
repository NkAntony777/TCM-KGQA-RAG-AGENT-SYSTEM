from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from config import get_settings, runtime_config
from graph.memory_indexer import memory_indexer
from graph.prompt_builder import build_system_prompt
from graph.session_manager import SessionManager
from services.common.medical_guard import RiskLevel, append_disclaimer, assess_query
from tools import get_all_tools


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _add_evidence(
    bucket: list[dict[str, Any]],
    *,
    source_type: str,
    source: str,
    snippet: str,
    score: float | None = None,
    fact_id: str | None = None,
    source_book: str | None = None,
    source_chapter: str | None = None,
    source_text: str | None = None,
    confidence: float | None = None,
    predicate: str | None = None,
    target: str | None = None,
    path_nodes: list[str] | None = None,
    path_edges: list[str] | None = None,
    path_sources: list[dict[str, Any]] | None = None,
) -> None:
    cleaned_source = (source or "unknown").strip()
    cleaned_snippet = (snippet or "").strip()
    if not cleaned_snippet:
        return
    item: dict[str, Any] = {
        "source_type": source_type,
        "source": cleaned_source,
        "snippet": cleaned_snippet[:300],
        "score": float(score) if score is not None else None,
    }
    if fact_id:
        item["fact_id"] = fact_id
    if source_book:
        item["source_book"] = source_book
    if source_chapter:
        item["source_chapter"] = source_chapter
    if source_text:
        item["source_text"] = source_text[:300]
    if confidence is not None:
        item["confidence"] = float(confidence)
    if predicate:
        item["predicate"] = predicate
    if target:
        item["target"] = target
    if path_nodes:
        item["path_nodes"] = path_nodes
    if path_edges:
        item["path_edges"] = path_edges
    if path_sources:
        item["path_sources"] = path_sources
    bucket.append(item)


def _collect_retrieval_evidence(payload: dict[str, Any], bucket: list[dict[str, Any]]) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    chunks = data.get("chunks", []) if isinstance(data, dict) else []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        source_file = str(chunk.get("source_file", "unknown"))
        source_page = chunk.get("source_page")
        source = f"{source_file}#{source_page}" if source_page is not None else source_file
        _add_evidence(
            bucket,
            source_type="doc",
            source=source,
            snippet=str(chunk.get("text", "")),
            score=float(chunk.get("score")) if chunk.get("score") is not None else None,
        )


def _collect_graph_evidence(payload: dict[str, Any], bucket: list[dict[str, Any]]) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return

    relations = data.get("relations", [])
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            source_book = str(relation.get("source_book", "unknown"))
            source_chapter = str(relation.get("source_chapter", ""))
            source = f"{source_book}/{source_chapter}".strip("/")
            source_text = str(relation.get("source_text", "")).strip()
            confidence = relation.get("confidence")
            snippet = source_text or f"{relation.get('predicate', '')}: {relation.get('target', '')}"
            _add_evidence(
                bucket,
                source_type="graph",
                source=source,
                snippet=snippet,
                score=float(confidence) if confidence is not None else None,
                fact_id=str(relation.get("fact_id", "")).strip() or None,
                source_book=source_book,
                source_chapter=source_chapter,
                source_text=source_text or None,
                confidence=float(confidence) if confidence is not None else None,
                predicate=str(relation.get("predicate", "")).strip() or None,
                target=str(relation.get("target", "")).strip() or None,
            )

    paths = data.get("paths", [])
    if isinstance(paths, list):
        for path in paths:
            if not isinstance(path, dict):
                continue
            nodes = path.get("nodes", [])
            snippet = " -> ".join(str(node) for node in nodes) if isinstance(nodes, list) else ""
            source = "graph/path"
            sources = path.get("sources", [])
            if isinstance(sources, list) and sources:
                first = sources[0]
                if isinstance(first, dict):
                    source = f"{first.get('source_book', 'unknown')}/{first.get('source_chapter', '')}".strip("/")
            _add_evidence(
                bucket,
                source_type="graph_path",
                source=source,
                snippet=snippet,
                score=float(path.get("score")) if path.get("score") is not None else None,
                path_nodes=[str(node) for node in nodes] if isinstance(nodes, list) else None,
                path_edges=[str(edge) for edge in path.get("edges", [])] if isinstance(path.get("edges"), list) else None,
                path_sources=sources if isinstance(sources, list) else None,
            )

    syndromes = data.get("syndromes", [])
    if isinstance(syndromes, list):
        for syndrome in syndromes:
            if not isinstance(syndrome, dict):
                continue
            formulas = syndrome.get("recommended_formulas", [])
            formulas_text = ",".join(str(item) for item in formulas) if isinstance(formulas, list) else ""
            source_book = str(syndrome.get("source_book", ""))
            source_chapter = str(syndrome.get("source_chapter", ""))
            source = f"{source_book}/{source_chapter}".strip("/") or "graph/syndrome_chain"
            source_text = str(syndrome.get("source_text", "")).strip()
            confidence = syndrome.get("confidence")
            snippet = source_text or f"{syndrome.get('name', '')} -> {formulas_text}".strip()
            _add_evidence(
                bucket,
                source_type="graph",
                source=source,
                snippet=snippet,
                score=float(confidence) if confidence is not None else float(syndrome.get("score")) if syndrome.get("score") is not None else None,
                fact_id=str(syndrome.get("fact_id", "")).strip() or None,
                source_book=source_book or None,
                source_chapter=source_chapter or None,
                source_text=source_text or None,
                confidence=float(confidence) if confidence is not None else None,
                predicate="辨证链",
                target=str(syndrome.get("name", "")).strip() or None,
            )


def _extract_route_and_evidence(tool_name: str, output: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    payload = _safe_json_loads(output)
    if not isinstance(payload, dict):
        return None, []

    route_event: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []

    if tool_name == "tcm_route_search":
        route_value = payload.get("route")
        route_reason = payload.get("route_reason")
        if route_value:
            route_event = {
                "route": str(route_value),
                "reason": str(route_reason or ""),
                "status": str(payload.get("status") or "ok"),
                "final_route": str(payload.get("final_route") or route_value),
                "executed_routes": payload.get("executed_routes", []),
                "degradation": payload.get("degradation", []),
                "service_health": payload.get("service_health", {}),
                "service_trace_ids": payload.get("service_trace_ids", {}),
                "service_backends": payload.get("service_backends", {}),
            }
        graph_result = payload.get("graph_result")
        retrieval_result = payload.get("retrieval_result")
        if isinstance(graph_result, dict):
            _collect_graph_evidence(graph_result, evidence)
        if isinstance(retrieval_result, dict):
            _collect_retrieval_evidence(retrieval_result, evidence)
        return route_event, evidence

    if tool_name in {"tcm_hybrid_search", "tcm_query_rewrite"}:
        if tool_name == "tcm_hybrid_search":
            _collect_retrieval_evidence(payload, evidence)
        return None, evidence

    if tool_name in {"tcm_entity_lookup", "tcm_path_query", "tcm_syndrome_chain"}:
        _collect_graph_evidence(payload, evidence)
        return None, evidence

    return None, []


def _extract_tool_meta(tool_name: str, output: str) -> dict[str, Any]:
    payload = _safe_json_loads(output)
    if not isinstance(payload, dict):
        return {}

    meta: dict[str, Any] = {}
    for key in ("code", "message", "trace_id", "backend", "warning"):
        value = payload.get(key)
        if value is not None:
            meta[key] = value

    if tool_name == "tcm_route_search":
        meta["status"] = payload.get("status", "ok")
        meta["final_route"] = payload.get("final_route", payload.get("route"))
        meta["service_trace_ids"] = payload.get("service_trace_ids", {})
        meta["service_backends"] = payload.get("service_backends", {})

    return meta


def _summarize_graph_result(result: dict[str, Any]) -> list[str]:
    if result.get("code") != 0:
        return []

    data = result.get("data", {})
    if not isinstance(data, dict):
        return []

    lines: list[str] = []
    entity = data.get("entity")
    relations = data.get("relations")
    if isinstance(entity, dict) and isinstance(relations, list) and relations:
        relation_text = "；".join(
            f"{item.get('predicate', '')}:{item.get('target', '')}"
            for item in relations[:4]
            if isinstance(item, dict)
        )
        lines.append(f"图谱关系：{entity.get('canonical_name') or entity.get('name')} -> {relation_text}")

    syndromes = data.get("syndromes")
    if isinstance(syndromes, list) and syndromes:
        parts = []
        for item in syndromes[:3]:
            if not isinstance(item, dict):
                continue
            formulas = item.get("recommended_formulas", [])
            formula_text = "、".join(str(x) for x in formulas[:3]) if isinstance(formulas, list) else ""
            parts.append(f"{item.get('name', '')}（推荐方剂：{formula_text}）")
        if parts:
            lines.append(f"辨证结果：{'；'.join(parts)}")

    paths = data.get("paths")
    if isinstance(paths, list) and paths:
        first = paths[0]
        if isinstance(first, dict) and isinstance(first.get("nodes"), list):
            lines.append(f"图谱路径：{' -> '.join(str(x) for x in first['nodes'])}")

    return lines


def _summarize_retrieval_result(result: dict[str, Any]) -> list[str]:
    if result.get("code") != 0:
        return []

    data = result.get("data", {})
    if not isinstance(data, dict):
        return []

    chunks = data.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        return []

    lines: list[str] = []
    for chunk in chunks[:2]:
        if not isinstance(chunk, dict):
            continue
        source_file = chunk.get("source_file", "unknown")
        source_page = chunk.get("source_page")
        source = f"{source_file}#{source_page}" if source_page is not None else str(source_file)
        lines.append(f"文献证据：{source} -> {str(chunk.get('text', '')).strip()[:120]}")
    return lines


def _build_mock_answer(query: str, tool_output: str, llm_error: str) -> str:
    payload = _safe_json_loads(tool_output)
    if not isinstance(payload, dict):
        return "当前处于本地降级模式，但结构化工具返回不可解析，暂时无法生成回答。"

    lines = [
        "当前处于本地演示降级模式，未调用外部大模型，以下回答直接基于路由与 mock 证据生成。",
        f"- 问题：{query}",
        f"- 路由：{payload.get('route', 'unknown')} -> {payload.get('final_route', payload.get('route', 'unknown'))}",
    ]

    for item in _summarize_graph_result(payload.get("graph_result", {})):
        lines.append(f"- {item}")
    for item in _summarize_retrieval_result(payload.get("retrieval_result", {})):
        lines.append(f"- {item}")

    if len(lines) <= 3:
        lines.append("- 当前证据不足，建议改问更具体的方剂、证候、出处或原文问题。")

    lines.append(f"- 降级原因：{llm_error.splitlines()[0][:120]}")
    return "\n".join(lines)


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


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
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
