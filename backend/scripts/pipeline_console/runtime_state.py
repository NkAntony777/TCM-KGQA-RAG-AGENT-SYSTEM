from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineConsoleRuntimeState:
    run_lock: threading.Lock = field(default_factory=threading.Lock)
    current_job: dict[str, Any] = field(default_factory=dict)
    job_log: list[dict[str, Any]] = field(default_factory=list)
    job_log_file: Path | None = None
    job_log_file_path: Path | None = None
    job_thread: threading.Thread | None = None
    job_cancelled: threading.Event = field(default_factory=threading.Event)
    book_status_lock: threading.RLock = field(default_factory=threading.RLock)
    runtime_graph_mutation_lock: threading.RLock = field(default_factory=threading.RLock)

    def set_job_log_files(self, log_file: Path | None, log_file_path: Path | None) -> tuple[Path | None, Path | None]:
        self.job_log_file = log_file
        self.job_log_file_path = log_file_path
        return self.job_log_file, self.job_log_file_path

    def set_job_thread(self, thread: threading.Thread | None) -> threading.Thread | None:
        self.job_thread = thread
        return self.job_thread

    def bind_legacy_job_state(
        self,
        *,
        current_job: dict[str, Any],
        job_log: list[dict[str, Any]],
        job_log_file: Path | None,
        job_log_file_path: Path | None,
        job_thread: threading.Thread | None,
        job_cancelled: threading.Event,
    ) -> "PipelineConsoleRuntimeState":
        self.current_job = current_job
        self.job_log = job_log
        self.job_log_file = job_log_file
        self.job_log_file_path = job_log_file_path
        self.job_thread = job_thread
        self.job_cancelled = job_cancelled
        return self


@dataclass
class PublishCompatibilityState:
    lock: threading.RLock = field(default_factory=threading.RLock)
    nebula_publish_threads: dict[str, threading.Thread] = field(default_factory=dict)
    queue: deque[dict[str, Any]] = field(default_factory=deque)
    worker_wakeup: threading.Event = field(default_factory=threading.Event)
    active_task: dict[str, Any] | None = None
