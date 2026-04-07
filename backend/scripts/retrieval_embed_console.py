from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import RetrievalEngine, load_settings


SESSION_DIR = BACKEND_ROOT / "storage" / "retrieval_embed_sessions"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_session_name(value: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in str(value or "").strip())
    return name or "configured-corpora"


def _format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _estimate_local_index_size_mb(doc_count: int, *, approx_per_doc_kb: int = 120) -> float:
    return round(doc_count * approx_per_doc_kb / 1024, 1)


@dataclass
class SessionConfig:
    session_name: str
    include_sample: bool
    include_modern: bool
    workers: int
    batch_size: int
    target_store: str


class EmbedConsoleSession:
    def __init__(self, config: SessionConfig):
        self.config = config
        self.settings = load_settings()
        self.engine = RetrievalEngine(self.settings)
        self.engine.settings.project_backend_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir = SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.session_dir / f"{self.config.session_name}.state.json"
        self.rows_path = self.session_dir / f"{self.config.session_name}.rows.jsonl"
        self.log_path = self.session_dir / f"{self.config.session_name}.log"
        self.meta_path = self.session_dir / f"{self.config.session_name}.meta.json"
        self._write_lock = threading.Lock()
        self._docs: list[dict[str, Any]] | None = None
        self._parent_docs: list[dict[str, Any]] | None = None
        self._leaf_docs: list[dict[str, Any]] | None = None
        self._state = self._load_or_init_state()

    def _log(self, message: str) -> None:
        line = f"[{_now()}] {message}"
        print(line)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _load_or_init_state(self) -> dict[str, Any]:
        state = _read_json(self.state_path, {})
        if isinstance(state, dict) and state.get("session_name") == self.config.session_name:
            state.setdefault("workers", self.config.workers)
            state.setdefault("batch_size", self.config.batch_size)
            state.setdefault("status", "idle")
            return state
        state = {
            "session_name": self.config.session_name,
            "created_at": _now(),
            "updated_at": _now(),
            "status": "idle",
            "workers": self.config.workers,
            "batch_size": self.config.batch_size,
            "target_store": self.config.target_store,
            "include_sample": self.config.include_sample,
            "include_modern": self.config.include_modern,
            "completed_docs": 0,
            "completed_batches": 0,
            "total_docs": 0,
            "total_batches": 0,
            "last_error": "",
            "rows_path": str(self.rows_path),
            "log_path": str(self.log_path),
        }
        _write_json(self.state_path, state)
        return state

    def _save_state(self) -> None:
        self._state["updated_at"] = _now()
        _write_json(self.state_path, self._state)

    def _corpus_paths(self) -> list[Path]:
        paths: list[Path] = []
        if self.config.include_sample and self.settings.sample_corpus_path.exists():
            paths.append(self.settings.sample_corpus_path)
        if self.config.include_modern and self.settings.modern_corpus_path.exists():
            paths.append(self.settings.modern_corpus_path)
        return paths

    def _load_docs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self._parent_docs is not None and self._leaf_docs is not None:
            return self._parent_docs, self._leaf_docs
        docs: list[dict[str, Any]] = []
        for path in self._corpus_paths():
            docs.extend(self.engine._load_corpus_file(path))
        docs = self.engine._dedupe_docs(docs)
        parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) < self.settings.leaf_retrieve_level]
        leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == self.settings.leaf_retrieve_level]
        self._docs = docs
        self._parent_docs = parent_docs
        self._leaf_docs = leaf_docs
        meta = {
            "corpus_paths": [str(path) for path in self._corpus_paths()],
            "leaf_docs": len(leaf_docs),
            "parent_docs": len(parent_docs),
            "estimated_local_index_mb": _estimate_local_index_size_mb(len(leaf_docs)),
        }
        _write_json(self.meta_path, meta)
        self._state["total_docs"] = len(leaf_docs)
        self._state["total_batches"] = math.ceil(len(leaf_docs) / max(1, self._state["batch_size"]))
        self._save_state()
        return parent_docs, leaf_docs

    def _completed_chunk_ids(self) -> set[str]:
        completed: set[str] = set()
        for row in _iter_jsonl(self.rows_path):
            chunk_id = str(row.get("chunk_id", "")).strip()
            if chunk_id:
                completed.add(chunk_id)
        return completed

    def status(self) -> dict[str, Any]:
        parent_docs, leaf_docs = self._load_docs()
        completed = self._completed_chunk_ids()
        remaining = max(0, len(leaf_docs) - len(completed))
        self._state["completed_docs"] = len(completed)
        self._state["total_docs"] = len(leaf_docs)
        self._state["total_batches"] = math.ceil(len(leaf_docs) / max(1, self._state["batch_size"]))
        self._save_state()
        return {
            "session_name": self.config.session_name,
            "status": self._state.get("status", "idle"),
            "include_sample": self.config.include_sample,
            "include_modern": self.config.include_modern,
            "corpus_paths": [str(path) for path in self._corpus_paths()],
            "workers": int(self._state.get("workers", self.config.workers)),
            "batch_size": int(self._state.get("batch_size", self.config.batch_size)),
            "embedding_model": self.settings.embedding_model,
            "dense_dim": int(self.settings.dense_dim),
            "target_store": self.config.target_store,
            "completed_docs": len(completed),
            "remaining_docs": remaining,
            "total_docs": len(leaf_docs),
            "parent_docs": len(parent_docs),
            "estimated_local_index_mb": _estimate_local_index_size_mb(len(leaf_docs)),
            "rows_path": str(self.rows_path),
            "log_path": str(self.log_path),
        }

    def print_status(self) -> None:
        payload = self.status()
        done = int(payload["completed_docs"])
        total = int(payload["total_docs"])
        remaining = int(payload["remaining_docs"])
        workers = int(payload["workers"])
        batch_size = int(payload["batch_size"])
        print("")
        print("=" * 72)
        print(f"Session      : {payload['session_name']}")
        print(f"Status       : {payload['status']}")
        print(f"Corpus       : sample={payload['include_sample']} modern={payload['include_modern']}")
        print(f"Corpus Paths : {', '.join(payload['corpus_paths']) if payload['corpus_paths'] else '(none)'}")
        print(f"Embed Model  : {payload['embedding_model']}")
        print(f"Dense Dim    : {payload['dense_dim']}")
        print(f"Workers      : {workers}")
        print(f"Batch size   : {batch_size}")
        print(f"Target Store : {payload['target_store']}")
        print(f"Progress     : {_progress_bar(done, total)} {done}/{total} remaining={remaining}")
        print(f"Rows file    : {payload['rows_path']}")
        print(f"Log file     : {payload['log_path']}")
        print(f"Est. local   : ~{payload['estimated_local_index_mb']} MB if finalized to JSON")
        print("=" * 72)
        print("")

    def set_workers(self, workers: int) -> None:
        self._state["workers"] = max(1, int(workers))
        self._save_state()
        self._log(f"workers updated to {self._state['workers']}")

    def set_batch_size(self, batch_size: int) -> None:
        self._state["batch_size"] = max(1, int(batch_size))
        parent_docs, leaf_docs = self._load_docs()
        self._state["total_batches"] = math.ceil(len(leaf_docs) / self._state["batch_size"])
        self._save_state()
        self._log(f"batch_size updated to {self._state['batch_size']}")

    def reset(self) -> None:
        for path in [self.state_path, self.rows_path, self.log_path, self.meta_path]:
            if path.exists():
                path.unlink()
        self._state = self._load_or_init_state()
        self._log("session reset")

    def _prepare_sparse_index(self, leaf_docs: list[dict[str, Any]], parent_docs: list[dict[str, Any]]) -> None:
        leaf_texts = [str(doc.get("text", "")) for doc in leaf_docs]
        self.engine.lexicon.fit(leaf_texts)
        self.engine.lexicon.save()
        self.engine.parent_store.upsert_documents(parent_docs)
        self._log(
            f"sparse lexicon prepared for {len(leaf_docs)} leaf docs; parent docs upserted={len(parent_docs)}"
        )

    def _pending_batches(self) -> list[list[dict[str, Any]]]:
        _, leaf_docs = self._load_docs()
        completed = self._completed_chunk_ids()
        pending = [doc for doc in leaf_docs if str(doc.get("chunk_id", "")).strip() not in completed]
        batch_size = max(1, int(self._state.get("batch_size", self.config.batch_size)))
        return [pending[index : index + batch_size] for index in range(0, len(pending), batch_size)]

    def _embed_batch(self, batch_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        texts = [str(doc.get("text", "")) for doc in batch_docs]
        dense_vectors = self.engine.embedding_client.embed(texts, self.settings.embedding_model)
        rows: list[dict[str, Any]] = []
        for doc, dense_embedding in zip(batch_docs, dense_vectors):
            rows.append(
                {
                    "dense_embedding": dense_embedding,
                    "sparse_embedding": self.engine.lexicon.encode_document(str(doc.get("text", ""))),
                    "text": doc.get("text", ""),
                    "filename": doc.get("filename", ""),
                    "file_type": doc.get("file_type", "TXT"),
                    "file_path": doc.get("file_path", ""),
                    "page_number": int(doc.get("page_number", 0) or 0),
                    "chunk_idx": int(doc.get("chunk_idx", 0) or 0),
                    "chunk_id": doc.get("chunk_id", ""),
                    "parent_chunk_id": doc.get("parent_chunk_id", ""),
                    "root_chunk_id": doc.get("root_chunk_id", ""),
                    "chunk_level": int(doc.get("chunk_level", self.settings.leaf_retrieve_level) or self.settings.leaf_retrieve_level),
                }
            )
        return rows

    def run(self, *, resume: bool = True) -> None:
        if not self.engine.embedding_client.is_ready():
            raise RuntimeError("embedding_client_not_configured")
        parent_docs, leaf_docs = self._load_docs()
        if not leaf_docs:
            raise RuntimeError("no_leaf_docs_to_embed")
        if not resume and self.rows_path.exists():
            raise RuntimeError("session_rows_exist_use_reset_or_resume")
        self._prepare_sparse_index(leaf_docs, parent_docs)

        pending_batches = self._pending_batches()
        total_docs = len(leaf_docs)
        completed_docs = len(self._completed_chunk_ids())
        if not pending_batches:
            self._state["status"] = "completed"
            self._save_state()
            self._log("no pending batches; session already completed")
            return

        workers = max(1, int(self._state.get("workers", self.config.workers)))
        start_time = time.time()
        self._state["status"] = "running"
        self._state["last_error"] = ""
        self._save_state()
        self._log(
            f"embedding run started: pending_batches={len(pending_batches)} workers={workers} batch_size={self._state['batch_size']}"
        )
        futures: dict[Future[list[dict[str, Any]]], int] = {}
        next_batch_idx = 0
        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="embed-worker") as executor:
                while next_batch_idx < len(pending_batches) and len(futures) < workers:
                    batch_docs = pending_batches[next_batch_idx]
                    futures[executor.submit(self._embed_batch, batch_docs)] = len(batch_docs)
                    next_batch_idx += 1

                while futures:
                    done_set, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED)
                    for future in done_set:
                        batch_size = futures.pop(future)
                        rows = future.result()
                        with self._write_lock:
                            _append_jsonl(self.rows_path, rows)
                        completed_docs += batch_size
                        self._state["completed_docs"] = completed_docs
                        self._state["completed_batches"] = int(self._state.get("completed_batches", 0)) + 1
                        self._save_state()
                        elapsed = max(0.1, time.time() - start_time)
                        rate = completed_docs / elapsed
                        eta = (total_docs - completed_docs) / rate if rate > 0 else 0
                        line = (
                            f"{_progress_bar(completed_docs, total_docs)} "
                            f"{completed_docs}/{total_docs} "
                            f"batches={self._state['completed_batches']}/{self._state['total_batches']} "
                            f"rate={rate:.1f} docs/s eta={_format_seconds(eta)}"
                        )
                        self._log(line)
                        if next_batch_idx < len(pending_batches):
                            batch_docs = pending_batches[next_batch_idx]
                            futures[executor.submit(self._embed_batch, batch_docs)] = len(batch_docs)
                            next_batch_idx += 1
        except KeyboardInterrupt:
            self._state["status"] = "interrupted"
            self._save_state()
            self._log("run interrupted by user; resume is available")
            return
        except Exception as exc:
            self._state["status"] = "failed"
            self._state["last_error"] = str(exc)
            self._save_state()
            self._log(f"run failed: {exc}")
            raise

        self._state["status"] = "completed"
        self._state["completed_docs"] = total_docs
        self._save_state()
        self._log("embedding run completed")

    def finalize_local_json(self) -> None:
        status = self.status()
        if int(status["completed_docs"]) < int(status["total_docs"]):
            raise RuntimeError("session_not_complete")
        rows = _iter_jsonl(self.rows_path)
        if not rows:
            raise RuntimeError("no_rows_to_finalize")
        self.engine.local_store.save(rows)
        self._log(
            f"local index finalized: rows={len(rows)} path={self.engine.settings.local_index_path}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive embedding/index console for retrieval corpora.")
    parser.add_argument("--session", default="configured-corpora")
    parser.add_argument("--exclude-sample", action="store_true")
    parser.add_argument("--exclude-modern", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--target-store", choices=["session_only", "local_json"], default="session_only")
    parser.add_argument("--run-now", action="store_true", help="Start embedding immediately, then enter console.")
    parser.add_argument("--non-interactive", action="store_true", help="Run once and exit.")
    return parser


def _print_help() -> None:
    print("Commands:")
    print("  status                 show current session status")
    print("  resume                 continue embedding from checkpoint")
    print("  run                    alias of resume")
    print("  set workers <n>        update worker count for next run")
    print("  set batch <n>          update batch size for next run")
    print("  finalize               write completed rows into retrieval_local_index.json")
    print("  reset                  delete current session state and rows")
    print("  help                   show this help")
    print("  quit                   exit console")


def _interactive_loop(session: EmbedConsoleSession) -> None:
    session.print_status()
    _print_help()
    while True:
        try:
            raw = input("embed-console> ").strip()
        except EOFError:
            print("")
            return
        if not raw:
            continue
        if raw in {"quit", "exit"}:
            return
        if raw in {"help", "?"}:
            _print_help()
            continue
        if raw == "status":
            session.print_status()
            continue
        if raw in {"resume", "run"}:
            session.run(resume=True)
            continue
        if raw == "finalize":
            session.finalize_local_json()
            continue
        if raw == "reset":
            session.reset()
            continue
        if raw.startswith("set workers "):
            try:
                session.set_workers(int(raw.split()[-1]))
            except Exception as exc:
                print(f"invalid workers: {exc}")
            continue
        if raw.startswith("set batch "):
            try:
                session.set_batch_size(int(raw.split()[-1]))
            except Exception as exc:
                print(f"invalid batch size: {exc}")
            continue
        print("unknown command; type 'help'")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    config = SessionConfig(
        session_name=_clean_session_name(args.session),
        include_sample=not args.exclude_sample,
        include_modern=not args.exclude_modern,
        workers=max(1, args.workers),
        batch_size=max(1, args.batch_size),
        target_store=args.target_store,
    )
    session = EmbedConsoleSession(config)
    session.set_workers(config.workers)
    session.set_batch_size(config.batch_size)
    if args.run_now or args.non_interactive:
        session.run(resume=True)
        if args.target_store == "local_json":
            session.finalize_local_json()
    if not args.non_interactive:
        _interactive_loop(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
