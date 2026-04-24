from __future__ import annotations

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

from services.common.models import error, success
from services.graph_service.engine import get_graph_engine


class EntityLookupRequest(BaseModel):
    name: str = Field(..., min_length=1)
    top_k: int = Field(default=12, ge=1, le=100)
    predicate_allowlist: list[str] | None = None
    predicate_blocklist: list[str] | None = None


class PathQueryRequest(BaseModel):
    start: str = Field(..., min_length=1)
    end: str = Field(..., min_length=1)
    max_hops: int = Field(default=3, ge=1, le=5)
    path_limit: int = Field(default=5, ge=1, le=20)


class SyndromeChainRequest(BaseModel):
    symptom: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


app = FastAPI(title="TCM Graph Service", version="0.1.0")


@app.get("/health")
@app.get("/api/v1/graph/health")
def health(x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    return success(get_graph_engine().health(), trace_id=x_trace_id)


@app.post("/api/v1/graph/entity/lookup")
def entity_lookup(payload: EntityLookupRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_graph_engine().entity_lookup(
        payload.name,
        top_k=payload.top_k,
        predicate_allowlist=payload.predicate_allowlist,
        predicate_blocklist=payload.predicate_blocklist,
    )
    if not data:
        return error(20001, "KG_ENTITY_NOT_FOUND", trace_id=x_trace_id)
    return success(data, trace_id=x_trace_id)


@app.post("/api/v1/graph/path/query")
def path_query(payload: PathQueryRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_graph_engine().path_query(
        payload.start,
        payload.end,
        max_hops=payload.max_hops,
        path_limit=payload.path_limit,
    )
    if not data.get("paths"):
        return error(20002, "KG_PATH_NOT_FOUND", trace_id=x_trace_id, data=data)
    return success(data, trace_id=x_trace_id)


@app.post("/api/v1/graph/syndrome/chain")
def syndrome(payload: SyndromeChainRequest, x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")):
    data = get_graph_engine().syndrome_chain(payload.symptom, top_k=payload.top_k)
    if not data.get("syndromes"):
        return error(20001, "KG_ENTITY_NOT_FOUND", trace_id=x_trace_id, data=data)
    return success(data, trace_id=x_trace_id)
