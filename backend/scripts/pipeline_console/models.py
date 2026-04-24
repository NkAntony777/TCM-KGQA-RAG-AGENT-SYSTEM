from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    model: str = Field(default="", description="LLM 模型名")
    api_key: str = Field(default="", description="API Key")
    base_url: str = Field(default="", description="API Base URL")
    providers: list[dict[str, Any]] = Field(default_factory=list, description="多 API 源配置列表")
    request_timeout: float = Field(default=314.0)
    max_retries: int = Field(default=2)
    request_delay: float = Field(default=1.1)
    retry_backoff_base: float = Field(default=2.0)
    parallel_workers: int = Field(default=11)
    max_chunk_chars: int = Field(default=800)
    chunk_overlap: int = Field(default=200)
    chunk_strategy: str = Field(default="body_first")
    max_chunk_retries: int = Field(default=2, description="Chunk 失败后最大重试次数")


class StartJobRequest(BaseModel):
    selected_books: list[str] = Field(default=[], description="书名关键词或序号列表")
    label: str = Field(default="", description="任务标签")
    dry_run: bool = Field(default=False)
    chapter_excludes: list[str] = Field(default=[])
    max_chunks_per_book: int | None = Field(default=None)
    skip_initial_chunks: int = Field(default=0)
    chunk_strategy: str = Field(default="body_first")
    auto_clean: bool = Field(default=True)
    auto_publish: bool = Field(default=False)
    api_config: APIConfig = Field(default_factory=APIConfig)


class ResumeRunRequest(BaseModel):
    auto_clean: bool = Field(default=False)
    auto_publish: bool = Field(default=False)
    continue_next_batches: bool = Field(default=True)
    api_config: APIConfig = Field(default_factory=APIConfig)


class GraphBookDeleteRequest(BaseModel):
    books: list[str] = Field(default=[], description="要删除的 source_book 列表")
    sync_nebula: bool = Field(default=True)
    mark_unprocessed: bool = Field(default=True)
