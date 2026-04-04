from __future__ import annotations

import asyncio
import json
from typing import Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.tcm_service_client import call_graph_entity_lookup, call_graph_path_query, call_graph_syndrome_chain


class TCMEntityLookupInput(BaseModel):
    name: str = Field(..., description="TCM entity name, e.g. 逍遥散、柴胡、肝郁脾虚")
    top_k: int = Field(default=12, ge=1, le=100, description="Max relations to return")
    predicate_allowlist: list[str] | None = Field(default=None, description="Optional predicate allowlist")
    predicate_blocklist: list[str] | None = Field(default=None, description="Optional predicate blocklist")


class TCMPathQueryInput(BaseModel):
    start: str = Field(..., description="Path start entity")
    end: str = Field(..., description="Path end entity")
    max_hops: int = Field(default=3, ge=1, le=5)
    path_limit: int = Field(default=5, ge=1, le=20)


class TCMSyndromeChainInput(BaseModel):
    symptom: str = Field(..., description="Symptom text such as 头痛, 胁肋胀痛")
    top_k: int = Field(default=5, ge=1, le=20, description="Max syndrome candidates")


class TCMEntityLookupTool(BaseTool):
    name: str = "tcm_entity_lookup"
    description: str = (
        "Lookup a TCM entity in graph-service and return direct graph relations with source info. "
        "Use when user asks formula/herb/syndrome relation details."
    )
    args_schema: Type[BaseModel] = TCMEntityLookupInput

    def _run(
        self,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_graph_entity_lookup(
            name=name,
            top_k=top_k,
            predicate_allowlist=predicate_allowlist,
            predicate_blocklist=predicate_blocklist,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        name: str,
        top_k: int = 12,
        predicate_allowlist: list[str] | None = None,
        predicate_blocklist: list[str] | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, name, top_k, predicate_allowlist, predicate_blocklist, None)


class TCMPathQueryTool(BaseTool):
    name: str = "tcm_path_query"
    description: str = (
        "Query graph semantic paths between two entities. Use for multi-hop reasoning "
        "like symptom -> syndrome -> formula."
    )
    args_schema: Type[BaseModel] = TCMPathQueryInput

    def _run(
        self,
        start: str,
        end: str,
        max_hops: int = 3,
        path_limit: int = 5,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_graph_path_query(
            start=start,
            end=end,
            max_hops=max_hops,
            path_limit=path_limit,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        start: str,
        end: str,
        max_hops: int = 3,
        path_limit: int = 5,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, start, end, max_hops, path_limit, None)


class TCMSyndromeChainTool(BaseTool):
    name: str = "tcm_syndrome_chain"
    description: str = (
        "Infer syndrome candidates from symptom text and return recommended formulas. "
        "Use for TCM syndrome differentiation style questions."
    )
    args_schema: Type[BaseModel] = TCMSyndromeChainInput

    def _run(
        self,
        symptom: str,
        top_k: int = 5,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_graph_syndrome_chain(symptom=symptom, top_k=top_k)
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        symptom: str,
        top_k: int = 5,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, symptom, top_k, None)
