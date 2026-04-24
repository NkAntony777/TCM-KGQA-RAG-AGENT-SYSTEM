from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineConfig:
    books_dir: Path
    output_dir: Path
    model: str
    api_key: str
    base_url: str
    providers: tuple["LLMProviderConfig", ...] = field(default_factory=tuple)
    request_timeout: float = 90.0
    max_chunk_chars: int = 800
    chunk_overlap: int = 200
    max_retries: int = 2
    request_delay: float = 0.8
    parallel_workers: int = 8
    retry_backoff_base: float = 2.0
    chunk_strategy: str = "body_first"


@dataclass(frozen=True)
class LLMProviderConfig:
    name: str
    model: str
    api_key: str
    base_url: str
    weight: int = 1
    enabled: bool = True


@dataclass
class TripleRecord:
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    source_book: str
    source_chapter: str
    source_text: str
    confidence: float
    raw_predicate: str
    raw_subject_type: str
    raw_object_type: str


@dataclass(frozen=True)
class ChunkTask:
    sequence: int
    book_path: Path
    book_name: str
    chapter_name: str
    chunk_index: int
    text_chunk: str


@dataclass(frozen=True)
class CleanDecision:
    keep: bool
    reason: str
