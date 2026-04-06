from __future__ import annotations

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

from services.common.models import error, success
from services.retrieval_service.engine import get_retrieval_engine


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int = Field(default=20, ge=1, le=100)
    enable_rerank: bool = True


class RewriteRequest(BaseModel):
    query: str = Field(..., min_length=1)
    strategy: str = Field(default="complex")


class CaseQASearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int = Field(default=30, ge=1, le=200)


app = FastAPI(title="TCM Retrieval Service", version="0.1.0")


@app.get("/api/v1/retrieval/health")
def health(x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    return success(get_retrieval_engine().health(), trace_id=x_trace_id)


@app.post("/api/v1/retrieval/search/hybrid")
def search_hybrid(payload: HybridSearchRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_retrieval_engine().search_hybrid(
        payload.query,
        top_k=payload.top_k,
        candidate_k=payload.candidate_k,
        enable_rerank=payload.enable_rerank,
    )
    if not data.get("chunks"):
        return error(30001, "RETRIEVE_EMPTY", trace_id=x_trace_id, data=data)
    return success(data, trace_id=x_trace_id)


@app.post("/api/v1/retrieval/search/rewrite")
def search_rewrite(payload: RewriteRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_retrieval_engine().rewrite_query(payload.query, strategy=payload.strategy)
    return success(data, trace_id=x_trace_id)


@app.post("/api/v1/retrieval/search/case-qa")
def search_case_qa(payload: CaseQASearchRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_retrieval_engine().search_case_qa(
        payload.query,
        top_k=payload.top_k,
        candidate_k=payload.candidate_k,
    )
    if not data.get("chunks"):
        return error(30002, "CASE_QA_EMPTY", trace_id=x_trace_id, data=data)
    return success(data, trace_id=x_trace_id)
