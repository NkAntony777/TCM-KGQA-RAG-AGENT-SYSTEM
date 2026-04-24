from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import Any, Callable


JsonLoader = Callable[[Path, Any], Any]
TextWriter = Callable[[Path, str], None]
PathProvider = Callable[[], Path]
RuntimeGraphStoreFactory = Callable[[], Any]
RunPublishSourceResolver = Callable[[Path], tuple[Path, Path | None]]
NowProvider = Callable[[], str]
ExceptionDescriber = Callable[[Exception], str]
NebulaHealthFormatter = Callable[[dict[str, Any]], str]


class PublishQueueRuntime:
    def __init__(
        self,
        *,
        output_dir_provider: PathProvider,
        load_json_file: JsonLoader,
        write_json_text: TextWriter,
        runtime_graph_store: RuntimeGraphStoreFactory,
        runtime_graph_mutation_lock: threading.RLock,
        resolve_run_publish_source: RunPublishSourceResolver,
        now_iso: NowProvider,
        describe_exception: ExceptionDescriber,
        nebula_health_detail: NebulaHealthFormatter,
    ) -> None:
        self.output_dir_provider = output_dir_provider
        self.load_json_file = load_json_file
        self.write_json_text = write_json_text
        self.runtime_graph_store = runtime_graph_store
        self.runtime_graph_mutation_lock = runtime_graph_mutation_lock
        self.resolve_run_publish_source = resolve_run_publish_source
        self.now_iso = now_iso
        self.describe_exception = describe_exception
        self.nebula_health_detail = nebula_health_detail
        self.lock = threading.RLock()
        self.nebula_publish_threads: dict[str, threading.Thread] = {}
        self.queue: deque[dict[str, Any]] = deque()
        self.worker_thread: threading.Thread | None = None
        self.worker_wakeup = threading.Event()
        self.active_task: dict[str, Any] | None = None

    def publish_status_path(self, run_dir: Path) -> Path:
        return run_dir / "publish_status.json"

    def normalize_status(self, payload: Any) -> dict[str, Any]:
        base = payload if isinstance(payload, dict) else {}
        json_status = base.get("json")
        nebula_status = base.get("nebula")
        if not isinstance(json_status, dict):
            json_status = {}
        if not isinstance(nebula_status, dict):
            nebula_status = {}
        return {
            "json": {
                "status": str(json_status.get("status", "idle") or "idle"),
                "published": bool(json_status.get("published", False)),
                "published_at": str(json_status.get("published_at", "") or ""),
                "updated_at": str(json_status.get("updated_at", "") or ""),
                "started_at": str(json_status.get("started_at", "") or ""),
                "finished_at": str(json_status.get("finished_at", "") or ""),
                "target": str(json_status.get("target", "") or ""),
                "graph_triples": int(json_status.get("graph_triples", 0) or 0),
                "evidence_count": int(json_status.get("evidence_count", 0) or 0),
                "error": str(json_status.get("error", "") or ""),
            },
            "nebula": {
                "status": str(nebula_status.get("status", "idle") or "idle"),
                "published": bool(nebula_status.get("published", False)),
                "published_at": str(nebula_status.get("published_at", "") or ""),
                "updated_at": str(nebula_status.get("updated_at", "") or ""),
                "started_at": str(nebula_status.get("started_at", "") or ""),
                "finished_at": str(nebula_status.get("finished_at", "") or ""),
                "target": str(nebula_status.get("target", "") or ""),
                "source_path": str(nebula_status.get("source_path", "") or ""),
                "space": str(nebula_status.get("space", "") or ""),
                "graph_triples": int(nebula_status.get("graph_triples", 0) or 0),
                "progress_current": int(nebula_status.get("progress_current", 0) or 0),
                "progress_total": int(nebula_status.get("progress_total", 0) or 0),
                "progress_pct": float(nebula_status.get("progress_pct", 0.0) or 0.0),
                "ok_count": int(nebula_status.get("ok_count", 0) or 0),
                "fail_count": int(nebula_status.get("fail_count", 0) or 0),
                "error": str(nebula_status.get("error", "") or ""),
            },
        }

    def load_status(self, run_dir: Path) -> dict[str, Any]:
        with self.lock:
            path = self.publish_status_path(run_dir)
            payload = self.load_json_file(path, {}) if path.exists() else {}
            return self.normalize_status(payload)

    def write_status(self, run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self.normalize_status(payload)
        self.write_json_text(
            self.publish_status_path(run_dir),
            json.dumps(normalized, ensure_ascii=False, indent=2),
        )
        return normalized

    def update_status(self, run_dir: Path, section: str, patch: dict[str, Any]) -> dict[str, Any]:
        if section not in {"json", "nebula"}:
            raise ValueError(f"unsupported_publish_section: {section}")
        with self.lock:
            payload = self.load_status(run_dir)
            section_payload = payload.get(section, {})
            if not isinstance(section_payload, dict):
                section_payload = {}
            section_payload.update(patch)
            section_payload["updated_at"] = self.now_iso()
            payload[section] = section_payload
            return self.write_status(run_dir, payload)

    @staticmethod
    def task_covers(task_kind: str, requested_kind: str) -> bool:
        return task_kind == requested_kind or (task_kind == "nebula" and requested_kind == "json")

    def publish_queue_busy_marker(self) -> str | None:
        active = self.active_task or {}
        active_run = str(active.get("run_name", "") or "").strip()
        active_kind = str(active.get("kind", "") or "").strip()
        if active_run and active_kind:
            return f"{active_run}:{active_kind}"
        if self.queue:
            queued = self.queue[0]
            queued_run = str(queued.get("run_name", "") or "").strip()
            queued_kind = str(queued.get("kind", "") or "").strip()
            if queued_run and queued_kind:
                return f"{queued_run}:{queued_kind}"
        return None

    def enqueue(self, run_name: str, *, kind: str, replace: bool = False) -> tuple[bool, dict[str, Any]]:
        run_dir = self.output_dir_provider() / run_name
        if not run_dir.exists():
            raise FileNotFoundError("run_not_found")

        with self.lock:
            active = self.active_task or {}
            active_run = str(active.get("run_name", "") or "")
            active_kind = str(active.get("kind", "") or "")
            if active_run == run_name and self.task_covers(active_kind, kind):
                return False, self.load_status(run_dir)

            queued_task: dict[str, Any] | None = None
            for task in self.queue:
                if str(task.get("run_name", "") or "") == run_name:
                    queued_task = task
                    break

            if queued_task is not None:
                queued_kind = str(queued_task.get("kind", "") or "")
                if self.task_covers(queued_kind, kind):
                    return False, self.load_status(run_dir)
                if kind == "nebula" and queued_kind == "json":
                    queued_task["kind"] = "nebula"
                    queued_task["replace"] = False
                    self.reset_json_to_idle_if_unpublished(run_dir)
                    status = self.set_nebula_queued(run_dir)
                    self.ensure_worker_locked()
                    self.worker_wakeup.set()
                    return True, status
                return False, self.load_status(run_dir)

            self.queue.append(
                {
                    "run_name": run_name,
                    "kind": kind,
                    "replace": bool(replace),
                    "queued_at": self.now_iso(),
                }
            )
            status = self.set_nebula_queued(run_dir) if kind == "nebula" else self.set_json_queued(run_dir)
            self.ensure_worker_locked()
            self.worker_wakeup.set()
            return True, status

    def bulk_enqueue_unpublished(self, kind: str) -> dict[str, Any]:
        if kind not in {"json", "nebula"}:
            raise ValueError(f"unsupported_bulk_publish_kind: {kind}")
        scanned = 0
        eligible = 0
        enqueued_runs: list[str] = []
        skipped_runs: list[str] = []
        failed_runs: list[dict[str, str]] = []
        for run_dir in self.iter_run_dirs_desc():
            scanned += 1
            if not self.eligible_for_bulk_publish(run_dir, kind=kind):
                skipped_runs.append(run_dir.name)
                continue
            eligible += 1
            try:
                enqueued, _ = self.enqueue(run_dir.name, kind=kind, replace=False)
                if enqueued:
                    enqueued_runs.append(run_dir.name)
                else:
                    skipped_runs.append(run_dir.name)
            except Exception as exc:
                failed_runs.append({"run_dir": run_dir.name, "error": str(exc)})
        return {
            "kind": kind,
            "scanned": scanned,
            "eligible": eligible,
            "enqueued": enqueued_runs,
            "skipped": skipped_runs,
            "failed": failed_runs,
        }

    def stop_all(self) -> dict[str, Any]:
        stopped_runs: list[str] = []
        with self.lock:
            queued_tasks = list(self.queue)
            self.queue.clear()
            self.worker_wakeup.clear()
        for task in queued_tasks:
            run_name = str(task.get("run_name", "") or "").strip()
            kind = str(task.get("kind", "") or "json").strip()
            if not run_name:
                continue
            run_dir = self.output_dir_provider() / run_name
            if not run_dir.exists():
                continue
            self.update_status(
                run_dir,
                "nebula" if kind == "nebula" else "json",
                {
                    "status": "error",
                    "published": False,
                    "finished_at": self.now_iso(),
                    "error": "cancelled_from_queue",
                },
            )
            stopped_runs.append(f"{run_name}:{kind}")

        active_run = ""
        with self.lock:
            if isinstance(self.active_task, dict):
                active_run = str(self.active_task.get("run_name", "") or "").strip()

        if active_run:
            active_dir = self.output_dir_provider() / active_run
            if active_dir.exists():
                status = self.load_status(active_dir)
                for section in ("json", "nebula"):
                    current = status.get(section, {})
                    if current.get("status") == "running":
                        self.update_status(
                            active_dir,
                            section,
                            {
                                "status": "error",
                                "published": False,
                                "finished_at": self.now_iso(),
                                "error": "marked_stopped_manually; restart server if worker is still blocked",
                            },
                        )
                        stopped_runs.append(f"{active_run}:{section}")

        output_dir = self.output_dir_provider()
        if output_dir.exists():
            for run_dir in output_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                status = self.load_status(run_dir)
                for section in ("json", "nebula"):
                    current = status.get(section, {})
                    if current.get("status") not in {"queued", "running"}:
                        continue
                    marker = f"{run_dir.name}:{section}"
                    if marker in stopped_runs:
                        continue
                    self.update_status(
                        run_dir,
                        section,
                        {
                            "status": "error",
                            "published": False,
                            "finished_at": self.now_iso(),
                            "error": "stopped_manually_or_server_restarted",
                        },
                    )
                    stopped_runs.append(marker)
        return {"stopped": stopped_runs}

    def set_json_queued(self, run_dir: Path) -> dict[str, Any]:
        return self.update_status(
            run_dir,
            "json",
            {
                "status": "queued",
                "published": False,
                "published_at": "",
                "started_at": "",
                "finished_at": "",
                "error": "",
            },
        )

    def set_nebula_queued(self, run_dir: Path) -> dict[str, Any]:
        return self.update_status(
            run_dir,
            "nebula",
            {
                "status": "queued",
                "published": False,
                "published_at": "",
                "started_at": "",
                "finished_at": "",
                "progress_current": 0,
                "progress_total": 0,
                "progress_pct": 0.0,
                "ok_count": 0,
                "fail_count": 0,
                "error": "",
            },
        )

    def reset_json_to_idle_if_unpublished(self, run_dir: Path) -> dict[str, Any]:
        current = self.load_status(run_dir).get("json", {})
        if current.get("published"):
            return self.update_status(run_dir, "json", {"status": "completed", "error": ""})
        return self.update_status(
            run_dir,
            "json",
            {
                "status": "idle",
                "published": False,
                "published_at": "",
                "started_at": "",
                "finished_at": "",
                "error": "",
            },
        )

    def worker_loop(self) -> None:
        while True:
            self.worker_wakeup.wait()
            while True:
                with self.lock:
                    if not self.queue:
                        self.active_task = None
                        self.worker_wakeup.clear()
                        break
                    task = self.queue.popleft()
                    self.active_task = dict(task)
                try:
                    if task.get("kind") == "nebula":
                        self.run_nebula_publish_job(str(task.get("run_name") or ""))
                    else:
                        self.run_json_publish_job(
                            str(task.get("run_name") or ""),
                            replace=bool(task.get("replace", False)),
                        )
                except Exception:
                    pass
                finally:
                    with self.lock:
                        if self.active_task == task:
                            self.active_task = None

    def ensure_worker_locked(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(
            target=self.worker_loop,
            name="publish-queue-worker",
            daemon=True,
        )
        self.worker_thread.start()

    def iter_run_dirs_desc(self) -> list[Path]:
        output_dir = self.output_dir_provider()
        if not output_dir.exists():
            return []
        return sorted((path for path in output_dir.iterdir() if path.is_dir()), reverse=True)

    def eligible_for_bulk_publish(self, run_dir: Path, *, kind: str) -> bool:
        manifest = self.load_json_file(run_dir / "manifest.json", {})
        state = self.load_json_file(run_dir / "state.json", {})
        if bool(manifest.get("dry_run", False)):
            return False
        status = str(state.get("status", "")).strip().lower()
        if status not in {"completed", "partial"}:
            return False
        publish_status = self.load_status(run_dir)
        json_status = publish_status.get("json", {})
        nebula_status = publish_status.get("nebula", {})
        if kind == "json":
            return not bool(json_status.get("published")) and str(json_status.get("status", "")) not in {"queued", "running"}
        return not bool(nebula_status.get("published")) and str(nebula_status.get("status", "")) not in {"queued", "running"}

    def record_json_publish_status(
        self,
        run_dir: Path,
        *,
        target: Path,
        graph_triples: int,
        evidence_count: int,
    ) -> dict[str, Any]:
        return self.update_status(
            run_dir,
            "json",
            {
                "status": "completed",
                "published": True,
                "published_at": self.now_iso(),
                "finished_at": self.now_iso(),
                "target": str(target),
                "graph_triples": graph_triples,
                "evidence_count": evidence_count,
                "error": "",
            },
        )

    def publish_json_for_run(self, run_dir: Path, *, replace: bool = False) -> dict[str, Any]:
        graph_import_path, evidence_path = self.resolve_run_publish_source(run_dir)
        store = self.runtime_graph_store()
        with self.runtime_graph_mutation_lock:
            if replace:
                raise RuntimeError("sqlite_runtime_replace_not_supported")
            stats = store.import_run(graph_path=graph_import_path, evidence_path=evidence_path)
            target = store.settings.db_path
        self.record_json_publish_status(
            run_dir,
            target=target,
            graph_triples=int(stats["total_triples"]),
            evidence_count=int(stats["evidence_count"]),
        )
        return {
            "target": target,
            "graph_triples": int(stats["total_triples"]),
            "evidence_count": int(stats["evidence_count"]),
        }

    def run_json_publish_job(self, run_name: str, *, replace: bool = False) -> dict[str, Any]:
        run_dir = self.output_dir_provider() / run_name
        if not run_dir.exists():
            raise FileNotFoundError("run_not_found")
        try:
            self.update_status(
                run_dir,
                "json",
                {
                    "status": "running",
                    "published": False,
                    "published_at": "",
                    "started_at": self.now_iso(),
                    "finished_at": "",
                    "error": "",
                },
            )
            return self.publish_json_for_run(run_dir, replace=replace)
        except Exception as exc:
            self.update_status(
                run_dir,
                "json",
                {
                    "status": "error",
                    "published": False,
                    "published_at": "",
                    "finished_at": self.now_iso(),
                    "error": self.describe_exception(exc),
                },
            )
            raise

    def run_nebula_publish_job(self, run_name: str) -> None:
        run_dir = self.output_dir_provider() / run_name
        try:
            if not run_dir.exists():
                raise FileNotFoundError("run_not_found")

            self.update_status(
                run_dir,
                "nebula",
                {
                    "status": "running",
                    "published": False,
                    "started_at": self.now_iso(),
                    "finished_at": "",
                    "published_at": "",
                    "progress_current": 0,
                    "progress_total": 0,
                    "progress_pct": 0.0,
                    "ok_count": 0,
                    "fail_count": 0,
                    "error": "",
                },
            )
            json_result = self.run_json_publish_job(run_name, replace=False)
            target = Path(str(json_result["target"]))

            graph_import_path, evidence_path = self.resolve_run_publish_source(run_dir)
            from services.graph_service.nebulagraph_store import NebulaGraphStore, load_graph_rows

            rows_with_evidence = load_graph_rows(graph_import_path, evidence_path)
            store = NebulaGraphStore()
            health = store.health()
            if not store.client_available():
                raise RuntimeError(self.nebula_health_detail(health))

            stmts = store.build_schema_statements() + store.build_import_statements(rows_with_evidence)
            total = len(stmts)
            self.update_status(
                run_dir,
                "nebula",
                {
                    "status": "running",
                    "published": False,
                    "target": str(target),
                    "source_path": str(graph_import_path),
                    "space": store.settings.space,
                    "graph_triples": int(json_result["graph_triples"]),
                    "progress_current": 0,
                    "progress_total": total,
                    "progress_pct": 0.0,
                    "ok_count": 0,
                    "fail_count": 0,
                    "error": "",
                },
            )

            from nebula3.Config import Config as NebulaConfig
            from nebula3.gclient.net import ConnectionPool

            config = NebulaConfig()
            config.max_connection_pool_size = 2
            config.timeout = 30000
            pool = ConnectionPool()
            pool.init([(store.settings.host, store.settings.port)], config)
            session = pool.get_session(store.settings.user, store.settings.password)

            ok_count = 0
            fail_count = 0
            last_error = ""
            try:
                for idx, stmt in enumerate(stmts, start=1):
                    result = session.execute(f"USE `{store.settings.space}`; {stmt}")
                    if result.is_succeeded():
                        ok_count += 1
                    else:
                        fail_count += 1
                        last_error = str(result.error_msg() or "")

                    if idx == 1 or idx == total or idx % 10 == 0:
                        self.update_status(
                            run_dir,
                            "nebula",
                            {
                                "status": "running",
                                "progress_current": idx,
                                "progress_total": total,
                                "progress_pct": round((idx / total) * 100, 1) if total else 100.0,
                                "ok_count": ok_count,
                                "fail_count": fail_count,
                                "error": last_error if fail_count else "",
                            },
                        )
            finally:
                session.release()
                pool.close()

            final_status = "completed" if fail_count == 0 else "error"
            self.update_status(
                run_dir,
                "nebula",
                {
                    "status": final_status,
                    "published": fail_count == 0,
                    "published_at": self.now_iso() if fail_count == 0 else "",
                    "finished_at": self.now_iso(),
                    "progress_current": total,
                    "progress_total": total,
                    "progress_pct": 100.0,
                    "ok_count": ok_count,
                    "fail_count": fail_count,
                    "error": "" if fail_count == 0 else (last_error or f"nebula_fail_count={fail_count}"),
                },
            )
        except Exception as exc:
            if run_dir.exists():
                self.update_status(
                    run_dir,
                    "nebula",
                    {
                        "status": "error",
                        "published": False,
                        "finished_at": self.now_iso(),
                        "error": self.describe_exception(exc),
                    },
                )
        finally:
            with self.lock:
                self.nebula_publish_threads.pop(run_name, None)
