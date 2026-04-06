from __future__ import annotations

import asyncio
import json
from typing import Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.tcm_service_client import call_retrieval_case_qa, call_retrieval_hybrid, call_retrieval_rewrite


class TCMHybridSearchInput(BaseModel):
    query: str = Field(..., description="User question or retrieval query")
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int = Field(default=20, ge=1, le=100)
    enable_rerank: bool = True


class TCMRewriteInput(BaseModel):
    query: str = Field(..., description="Original user query")
    strategy: str = Field(default="complex", description="step_back | hyde | complex")


class TCMCaseQASearchInput(BaseModel):
    query: str = Field(..., description="Case description or TCM question")
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int = Field(default=30, ge=1, le=200)


class TCMHybridSearchTool(BaseTool):
    name: str = "tcm_hybrid_search"
    description: str = (
        "Run hybrid retrieval over TCM documents and return evidence chunks with scores and sources. "
        "Use for concept explanation, source-based answers, and document-grounded responses."
    )
    args_schema: Type[BaseModel] = TCMHybridSearchInput

    def _run(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        enable_rerank: bool = True,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_retrieval_hybrid(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            enable_rerank=enable_rerank,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        enable_rerank: bool = True,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, candidate_k, enable_rerank, None)


class TCMRewriteTool(BaseTool):
    name: str = "tcm_query_rewrite"
    description: str = (
        "Rewrite a TCM question using step-back/hyde strategy. "
        "Use when the original query is ambiguous or too short for retrieval."
    )
    args_schema: Type[BaseModel] = TCMRewriteInput

    def _run(
        self,
        query: str,
        strategy: str = "complex",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_retrieval_rewrite(query=query, strategy=strategy)
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        query: str,
        strategy: str = "complex",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, strategy, None)


class TCMCaseQASearchTool(BaseTool):
    name: str = "tcm_case_qa_search"
    description: str = (
        "Search the local Chroma case QA database for similar TCM cases and return structured case-reference evidence. "
        "Use for long case descriptions, syndrome-to-formula reasoning, and similar-case lookup."
    )
    args_schema: Type[BaseModel] = TCMCaseQASearchInput

    def _run(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 30,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        result = call_retrieval_case_qa(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]

    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 30,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, candidate_k, None)
