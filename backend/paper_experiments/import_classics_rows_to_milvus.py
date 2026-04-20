from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_ROWS_PATH = BACKEND_ROOT / "storage" / "retrieval_embed_sessions" / "classics-vector.rows.jsonl"
SESSION_DIR = BACKEND_ROOT / "storage" / "paper_milvus_import_sessions"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def _iter_jsonl(path: Path):
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
                yield payload


def _count_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _load_first_valid_row(path: Path) -> dict[str, Any]:
    for row in _iter_jsonl(path):
        return row
    raise RuntimeError("rows_jsonl_empty")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("text", "") or "")
    return {
        "dense_embedding": row.get("dense_embedding", []),
        "sparse_embedding": row.get("sparse_embedding", {}),
        "text": text[:24000],
        "filename": row.get("filename", ""),
        "file_type": row.get("file_type", "TXT"),
        "file_path": row.get("file_path", ""),
        "page_number": int(row.get("page_number", 0) or 0),
        "chunk_idx": int(row.get("chunk_idx", 0) or 0),
        "chunk_id": row.get("chunk_id", ""),
        "parent_chunk_id": row.get("parent_chunk_id", ""),
        "root_chunk_id": row.get("root_chunk_id", ""),
        "chunk_level": int(row.get("chunk_level", 3) or 3),
    }


def _progress_bar(done: int, total: int, *, width: int = 28) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _format_seconds(value: float) -> str:
    seconds = max(0, int(value))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _build_state_path(session_name: str) -> Path:
    return SESSION_DIR / f"{session_name}.state.json"


def _init_state(
    *,
    session_name: str,
    rows_path: Path,
    total_rows: int,
    dense_dim: int,
    batch_size: int,
    batch_retries: int,
    milvus_host: str,
    milvus_port: int,
    milvus_collection: str,
) -> dict[str, Any]:
    return {
        "session_name": session_name,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "idle",
        "rows_path": str(rows_path),
        "total_rows": total_rows,
        "inserted_rows": 0,
        "byte_offset": 0,
        "dense_dim": dense_dim,
        "batch_size": batch_size,
        "batch_retries": batch_retries,
        "milvus_host": milvus_host,
        "milvus_port": milvus_port,
        "milvus_collection": milvus_collection,
        "last_error": "",
    }


def _load_or_init_state(
    *,
    session_name: str,
    rows_path: Path,
    total_rows: int,
    dense_dim: int,
    batch_size: int,
    batch_retries: int,
    milvus_host: str,
    milvus_port: int,
    milvus_collection: str,
    reset: bool,
) -> tuple[Path, dict[str, Any]]:
    state_path = _build_state_path(session_name)
    if reset and state_path.exists():
        state_path.unlink()
    state = _read_json(state_path, {})
    if isinstance(state, dict) and state.get("session_name") == session_name:
        state["batch_size"] = batch_size
        state["batch_retries"] = batch_retries
        state["milvus_host"] = milvus_host
        state["milvus_port"] = milvus_port
        state["milvus_collection"] = milvus_collection
        state["dense_dim"] = dense_dim
        state["total_rows"] = total_rows
        state["rows_path"] = str(rows_path)
        return state_path, state
    state = _init_state(
        session_name=session_name,
        rows_path=rows_path,
        total_rows=total_rows,
        dense_dim=dense_dim,
        batch_size=batch_size,
        batch_retries=batch_retries,
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        milvus_collection=milvus_collection,
    )
    _write_json(state_path, state)
    return state_path, state


def _print_status(state: dict[str, Any]) -> None:
    done = int(state.get("inserted_rows", 0) or 0)
    total = int(state.get("total_rows", 0) or 0)
    print(json.dumps(
        {
            "session_name": state.get("session_name"),
            "status": state.get("status"),
            "rows_path": state.get("rows_path"),
            "milvus_host": state.get("milvus_host"),
            "milvus_port": state.get("milvus_port"),
            "milvus_collection": state.get("milvus_collection"),
            "inserted_rows": done,
            "total_rows": total,
            "progress_pct": round(done * 100.0 / max(1, total), 2),
            "byte_offset": state.get("byte_offset", 0),
            "last_error": state.get("last_error", ""),
        },
        ensure_ascii=False,
        indent=2,
    ))


def _insert_with_retry(engine, batch: list[dict[str, Any]], *, retries: int) -> None:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            engine.milvus.insert(batch)
            return
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                raise
            delay = min(12.0, 1.0 * (2**attempt))
            print(f"[rows->milvus] retry {attempt + 1}/{retries} in {delay:.1f}s: {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"milvus_insert_retry_exhausted:{last_error}")


def run_import(
    *,
    rows_path: Path,
    session_name: str,
    batch_size: int,
    batch_retries: int,
    reset: bool,
    milvus_host: str,
    milvus_port: int,
    milvus_collection: str,
) -> dict[str, Any]:
    if not rows_path.exists():
        raise FileNotFoundError(f"rows_jsonl_not_found: {rows_path}")

    os.environ["RETRIEVAL_VECTOR_COMPATIBILITY_ENABLED"] = "true"
    os.environ["MILVUS_URI"] = ""
    os.environ["MILVUS_HOST"] = str(milvus_host)
    os.environ["MILVUS_PORT"] = str(milvus_port)
    os.environ["MILVUS_COLLECTION"] = str(milvus_collection)

    from services.retrieval_service.engine import RetrievalEngine
    from services.retrieval_service.settings import load_settings

    total_rows = _count_rows(rows_path)
    first_row = _load_first_valid_row(rows_path)
    dense_dim = len(first_row.get("dense_embedding", []) or [])
    if dense_dim <= 0:
        raise RuntimeError("dense_dimension_missing")

    state_path, state = _load_or_init_state(
        session_name=session_name,
        rows_path=rows_path,
        total_rows=total_rows,
        dense_dim=dense_dim,
        batch_size=batch_size,
        batch_retries=batch_retries,
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        milvus_collection=milvus_collection,
        reset=reset,
    )

    settings = load_settings()
    engine = RetrievalEngine(settings)

    if reset:
        try:
            engine.milvus.reset_collection()
        except Exception:
            pass
        state["inserted_rows"] = 0
        state["byte_offset"] = 0
        state["last_error"] = ""
        state["status"] = "idle"
        _write_json(state_path, state)

    engine.milvus.ensure_collection(dense_dim=dense_dim)

    inserted = int(state.get("inserted_rows", 0) or 0)
    byte_offset = int(state.get("byte_offset", 0) or 0)
    started = time.perf_counter()
    state["status"] = "running"
    state["last_error"] = ""
    _write_json(state_path, state)

    batch: list[dict[str, Any]] = []
    batch_end_offset = byte_offset

    try:
        with rows_path.open("rb") as f:
            if byte_offset > 0:
                f.seek(byte_offset)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                batch_end_offset = f.tell()
                try:
                    payload = json.loads(raw_line.decode("utf-8").strip())
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                batch.append(_normalize_row(payload))
                if len(batch) >= batch_size:
                    _insert_with_retry(engine, batch, retries=batch_retries)
                    inserted += len(batch)
                    state["inserted_rows"] = inserted
                    state["byte_offset"] = batch_end_offset
                    state["updated_at"] = _now()
                    _write_json(state_path, state)
                    elapsed = max(0.1, time.perf_counter() - started)
                    rate = inserted / elapsed
                    eta = (total_rows - inserted) / rate if rate > 0 else 0
                    print(
                        f"[rows->milvus] {_progress_bar(inserted, total_rows)} "
                        f"{inserted}/{total_rows} ({inserted * 100.0 / max(1, total_rows):.1f}%) "
                        f"rate={rate:.1f} rows/s eta={_format_seconds(eta)}",
                        flush=True,
                    )
                    batch = []

            if batch:
                _insert_with_retry(engine, batch, retries=batch_retries)
                inserted += len(batch)
                state["inserted_rows"] = inserted
                state["byte_offset"] = batch_end_offset
                state["updated_at"] = _now()
                _write_json(state_path, state)
                elapsed = max(0.1, time.perf_counter() - started)
                rate = inserted / elapsed
                eta = (total_rows - inserted) / rate if rate > 0 else 0
                print(
                    f"[rows->milvus] {_progress_bar(inserted, total_rows)} "
                    f"{inserted}/{total_rows} ({inserted * 100.0 / max(1, total_rows):.1f}%) "
                    f"rate={rate:.1f} rows/s eta={_format_seconds(eta)}",
                    flush=True,
                )

    except KeyboardInterrupt:
        state["status"] = "interrupted"
        state["updated_at"] = _now()
        _write_json(state_path, state)
        raise
    except Exception as exc:
        state["status"] = "failed"
        state["last_error"] = str(exc)
        state["updated_at"] = _now()
        _write_json(state_path, state)
        raise

    state["status"] = "completed"
    state["updated_at"] = _now()
    _write_json(state_path, state)

    health = engine.milvus.health()
    return {
        "state_path": str(state_path),
        "rows_path": str(rows_path),
        "total_rows": total_rows,
        "inserted_rows": inserted,
        "dense_dim": dense_dim,
        "batch_size": batch_size,
        "batch_retries": batch_retries,
        "milvus_host": settings.milvus_host,
        "milvus_port": settings.milvus_port,
        "milvus_collection": settings.milvus_collection,
        "milvus_health": health,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import classics-vector rows.jsonl into Milvus with progress and resume.")
    parser.add_argument("--rows-path", type=Path, default=DEFAULT_ROWS_PATH)
    parser.add_argument("--session", default="classics-global-milvus")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--batch-retries", type=int, default=3)
    parser.add_argument("--reset", action="store_true", help="Drop existing collection and reset import progress.")
    parser.add_argument("--status", action="store_true", help="Show current import session status and exit.")
    parser.add_argument("--milvus-host", default="127.0.0.1")
    parser.add_argument("--milvus-port", type=int, default=19530)
    parser.add_argument("--milvus-collection", default="classics_embeddings_collection")
    args = parser.parse_args()

    total_rows = _count_rows(args.rows_path) if args.rows_path.exists() else 0
    dense_dim = 0
    if args.rows_path.exists():
        try:
            dense_dim = len((_load_first_valid_row(args.rows_path).get("dense_embedding", []) or []))
        except Exception:
            dense_dim = 0
    state_path, state = _load_or_init_state(
        session_name=str(args.session).strip(),
        rows_path=args.rows_path,
        total_rows=total_rows,
        dense_dim=dense_dim,
        batch_size=max(1, int(args.batch_size)),
        batch_retries=max(0, int(args.batch_retries)),
        milvus_host=str(args.milvus_host),
        milvus_port=int(args.milvus_port),
        milvus_collection=str(args.milvus_collection).strip(),
        reset=False,
    )
    if args.status:
        _print_status(state)
        return

    report = run_import(
        rows_path=args.rows_path,
        session_name=str(args.session).strip(),
        batch_size=max(1, int(args.batch_size)),
        batch_retries=max(0, int(args.batch_retries)),
        reset=bool(args.reset),
        milvus_host=str(args.milvus_host),
        milvus_port=int(args.milvus_port),
        milvus_collection=str(args.milvus_collection).strip(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

