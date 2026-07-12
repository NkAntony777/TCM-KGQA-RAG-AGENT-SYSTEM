from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from .. import section_response
from .build import pipeline as build_pipeline
from .build import schema as build_schema
from .build import state as build_state
from .search import reader as search_reader
from .search import pipeline as search_pipeline
from .utils import lifecycle as build_lifecycle
from .utils import metadata as build_metadata


def _compose_section_preview(*, section_summary: str, representative_passages: list[str]) -> str:
    parts = [str(section_summary or "").strip()]
    parts.extend(str(item or "").strip() for item in representative_passages if str(item or "").strip())
    return "\n".join(part for part in parts if part).strip()


def _build_section_search_basis(
    *,
    book_name: str,
    chapter_title: str,
    section_summary: str,
    topic_tags_text: str,
    entity_tags_text: str,
    representative_text: str,
) -> str:
    return " ".join(
        [
            str(book_name or ""),
            str(chapter_title or ""),
            str(section_summary or ""),
            str(topic_tags_text or ""),
            str(entity_tags_text or ""),
            str(representative_text or ""),
        ]
    ).strip()


def normalize_chunk(item: dict[str, Any]) -> dict[str, Any]:
    return section_response.normalize_chunk(
        item,
        extract_book_name=build_metadata.extract_book_name,
        extract_chapter_title=build_metadata.extract_chapter_title,
    )


def build_section_response(
    *,
    path: str,
    payload: dict[str, Any],
    parent_store: "ParentChunkStore",  # noqa: F821  (forward ref to parent_chunk_store.ParentChunkStore)
) -> dict[str, Any]:
    return section_response.build_section_response(
        path=path,
        payload=payload,
        parent_store=parent_store,
        normalize_chunk_fn=normalize_chunk,
        strip_classic_headers=build_metadata.strip_classic_headers,
        merge_section_bodies=build_metadata.merge_section_bodies,
        build_section_metadata=build_metadata.build_section_metadata,
    )


class LocalFilesFirstStore:
    def __init__(self, store_path: Path, *, tokenizer, summary_cache_path: Path | None = None, llm_summary_fn: Callable[[str, str, str], dict[str, Any]] | None = None):
        from services.retrieval_service.parent_chunk_store import ParentChunkStore  # noqa: F401  (only used for type)
        from services.retrieval_service.section_summary_cache import SectionSummaryCache

        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.summary_cache = SectionSummaryCache(summary_cache_path)
        self.llm_summary_fn = llm_summary_fn
        self.strip_classic_headers = build_metadata.strip_classic_headers
        self.merge_section_bodies = build_metadata.merge_section_bodies

    def _schema_status(self) -> dict[str, Any]:
        return build_schema.schema_status(self.store_path)

    def ensure_schema(self) -> dict[str, Any]:
        status = self._schema_status()
        if not status["exists"] or status["compatible"]:
            return status
        try:
            base_rows = build_schema.load_legacy_doc_rows(self.store_path)
        except Exception:
            return status
        if not base_rows:
            self.reset()
            return {"exists": False, "compatible": False, "version": 0, "migrated": True}
        time.sleep(0.2)
        try:
            self.rebuild(base_rows, reset=True)
        except PermissionError:
            self._migrate_legacy_schema_in_place(base_rows)
        migrated = self._schema_status()
        migrated["migrated"] = True
        return migrated

    def _migrate_legacy_schema_in_place(self, rows: list[dict[str, Any]]) -> None:
        build_schema.migrate_legacy_schema_in_place(
            self.store_path,
            rows,
            tokenizer=self.tokenizer,
            resolve_section_metadata=self._resolve_section_metadata,
            rebuild_nav_groups=lambda conn: self._rebuild_nav_groups(conn, show_progress=False),
        )

    def _resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        cached = self.summary_cache.get(section_key)
        if cached:
            return {
                "section_summary": str(cached.get("section_summary", "")),
                "topic_tags": list(cached.get("topic_tags", []))[:12],
                "entity_tags": list(cached.get("entity_tags", []))[:12],
                "representative_passages": list(cached.get("representative_passages", []))[:2],
            }
        metadata = build_metadata.build_section_metadata(book_name=book_name, chapter_title=chapter_title, section_text=section_text)
        if self.llm_summary_fn is not None:
            try:
                llm_metadata = self.llm_summary_fn(book_name, chapter_title, section_text)
            except Exception:
                llm_metadata = None
            if isinstance(llm_metadata, dict):
                metadata = {
                    "section_summary": str(llm_metadata.get("section_summary", metadata["section_summary"])),
                    "topic_tags": list(llm_metadata.get("topic_tags", metadata["topic_tags"]))[:12],
                    "entity_tags": list(llm_metadata.get("entity_tags", metadata["entity_tags"]))[:12],
                    "representative_passages": list(llm_metadata.get("representative_passages", metadata["representative_passages"]))[:2],
                }
                self.summary_cache.set(section_key, metadata)
        return metadata

    def resolve_section_metadata(self, *, section_key: str, book_name: str, chapter_title: str, section_text: str) -> dict[str, Any]:
        return self._resolve_section_metadata(
            section_key=section_key,
            book_name=book_name,
            chapter_title=chapter_title,
            section_text=section_text,
        )

    def health(self) -> dict[str, Any]:
        available = False
        docs = 0
        schema_status = self.ensure_schema()
        if self.store_path.exists():
            try:
                with closing(sqlite3.connect(self.store_path)) as conn:
                    docs = int(conn.execute("SELECT COUNT(1) FROM docs").fetchone()[0])
                    available = docs > 0
            except Exception:
                available = False
                docs = 0
        return {
            "files_first_index_available": available,
            "files_first_index_path": str(self.store_path),
            "files_first_index_docs": docs,
            "files_first_schema_version": schema_status.get("version", 0),
            "files_first_schema_compatible": bool(schema_status.get("compatible")),
            "files_first_schema_migrated": bool(schema_status.get("migrated")),
        }

    def reset(self) -> None:
        if self.store_path.exists():
            self._unlink_with_retry(self.store_path)

    @staticmethod
    def _unlink_with_retry(path: Path) -> None:
        build_lifecycle.unlink_with_retry(path)

    @staticmethod
    def _replace_file(target_path: Path, replacement_path: Path) -> None:
        build_lifecycle.replace_file(target_path, replacement_path)

    def _default_state_path(self) -> Path:
        return build_state.default_state_path(self.store_path)

    @staticmethod
    def _initialize_build_db(conn: sqlite3.Connection) -> None:
        build_schema.initialize_build_db(conn)

    @staticmethod
    def _ensure_post_docs_indexes(conn: sqlite3.Connection) -> None:
        build_schema.ensure_post_docs_indexes(conn)

    @staticmethod
    def _print_build_progress(*, stage: str, done: int, total: int, started_at: float) -> None:
        build_lifecycle.print_build_progress(stage=stage, done=done, total=total, started_at=started_at)

    @staticmethod
    def _print_stage_banner(*, stage: str, detail: str) -> None:
        build_lifecycle.print_stage_banner(stage=stage, detail=detail)

    @staticmethod
    def _count_rows_in_db(path: Path) -> dict[str, int]:
        return build_schema.count_rows_in_db(path)

    @staticmethod
    def _load_nav_group_seed_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        from .build import nav_groups as build_nav_groups
        return build_nav_groups.load_nav_group_seed_rows(conn)

    def _rebuild_nav_groups(self, conn: sqlite3.Connection, *, show_progress: bool) -> dict[str, Any]:
        from .build import nav_groups as build_nav_groups
        if show_progress:
            self._print_stage_banner(stage="nav-groups", detail="building adaptive nav groups from section summaries")
        seed_rows = self._load_nav_group_seed_rows(conn)
        if show_progress:
            seed_manifest = build_nav_groups.seed_manifest(seed_rows)
            self._print_stage_banner(stage="nav-groups", detail=f"seed_rows={seed_manifest['seed_rows']} books={seed_manifest['books']} sections={seed_manifest['sections']}")
        last_reported = 0

        def _progress(current: int, total: int, _book_name: str) -> None:
            nonlocal last_reported
            if not show_progress or total <= 0:
                return
            if current != total and (current - last_reported) < 25:
                return
            last_reported = current
            self._print_build_progress(stage="nav-groups", done=current, total=total, started_at=docs_started_at)

        docs_started_at = time.perf_counter()
        payload = build_nav_groups.build_nav_group_payload(
            seed_rows=seed_rows,
            summary_cache_path=self.summary_cache.cache_path if self.summary_cache.cache_path is not None else Path(""),
            progress_callback=_progress if show_progress else None,
        )
        manifest = build_nav_groups.replace_nav_group_payload(conn, payload)
        if show_progress:
            self._print_stage_banner(
                stage="nav-groups",
                detail=f"books={payload['manifest']['books']} nav_groups={payload['manifest']['nav_groups']} outlines={payload['manifest']['book_outlines']}",
            )
        return manifest

    def rebuild(
        self,
        rows: list[dict[str, Any]],
        *,
        state_path: Path | None = None,
        reset: bool = False,
        show_progress: bool = False,
        batch_size: int = 512,
    ) -> dict[str, Any]:
        return build_pipeline.rebuild(
            self,
            rows,
            state_path=state_path,
            reset=reset,
            show_progress=show_progress,
            batch_size=batch_size,
        )

    def search(self, *, query: str, query_context: dict[str, Any] | None = None, top_k: int, candidate_k: int, leaf_level: int) -> tuple[list[dict[str, Any]], str]:
        return search_pipeline.search(
            self,
            query=query,
            query_context=query_context,
            top_k=top_k,
            candidate_k=candidate_k,
            leaf_level=leaf_level,
        )

    def get_docs_by_chunk_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        return search_reader.get_docs_by_chunk_ids(self, chunk_ids)

    def read_section(self, *, path: str, top_k: int = 12) -> dict[str, Any]:
        return search_reader.read_section(self, path=path, top_k=top_k)


__all__ = [
    "LocalFilesFirstStore",
    "normalize_chunk",
    "build_section_response",
    "_compose_section_preview",
    "_build_section_search_basis",
]