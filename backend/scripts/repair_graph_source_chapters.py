from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.import_classic_books import (
    _collapse_wrapped_lines,
    _normalize_book_name,
    _read_source_text,
    _split_sections,
)
from services.graph_service.runtime_store import (
    RuntimeGraphStore,
    RuntimeGraphStoreSettings,
    _iter_json_array_rows,
    _iter_jsonl_rows,
)
PROJECT_ROOT = BACKEND_DIR.parent.parent
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "TCM-Ancient-Books-master" / "TCM-Ancient-Books-master"
DEFAULT_GRAPH_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.json"
DEFAULT_EVIDENCE_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.evidence.jsonl"
DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_SAMPLE_GRAPH_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "sample_graph.json"
DEFAULT_MODERN_GRAPH_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "modern_graph_runtime.jsonl"
DEFAULT_MODERN_EVIDENCE_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "modern_graph_runtime.evidence.jsonl"
DEFAULT_MANIFEST_DIR = BACKEND_DIR / "services" / "graph_service" / "data"

BODY_HINTS = (
    "学生：",
    "老师：",
    "医师甲",
    "医师乙",
    "患者",
    "病例",
    "辨证",
    "治法",
)
SENTENCE_MARKS = "。！？；：!?："
SAFE_BODY_SLUG = re.compile(r"^[^\r\n]{1,80}[_-]正文$")
NON_WORD_PATTERN = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair polluted source_chapter values in runtime graph files.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--graph-path", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--sample-graph-path", type=Path, default=DEFAULT_SAMPLE_GRAPH_PATH)
    parser.add_argument("--modern-graph-path", type=Path, default=DEFAULT_MODERN_GRAPH_PATH)
    parser.add_argument("--modern-evidence-path", type=Path, default=DEFAULT_MODERN_EVIDENCE_PATH)
    parser.add_argument("--apply", action="store_true", help="Write repaired files and rebuild runtime DB.")
    return parser.parse_args()


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split()).strip()


def _search_text(value: Any) -> str:
    return "".join(_compact_text(value).split())


def _loose_search_text(value: Any) -> str:
    return NON_WORD_PATTERN.sub("", _search_text(value))


def _is_polluted_source_chapter(source_chapter: Any, *, source_book: Any = "") -> bool:
    chapter = str(source_chapter or "").strip()
    if not chapter:
        return False
    if SAFE_BODY_SLUG.match(chapter):
        return False
    book = str(source_book or "").strip()
    if chapter in {book, _normalize_book_name(book)}:
        return False
    if "\n" in chapter or "\r" in chapter:
        return True
    if len(chapter) >= 120:
        return True
    punctuation_count = sum(chapter.count(mark) for mark in SENTENCE_MARKS)
    if punctuation_count >= 2:
        return True
    return any(hint in chapter for hint in BODY_HINTS)


@dataclass(frozen=True)
class SectionEntry:
    title: str
    search_text: str
    loose_search_text: str


class SectionResolver:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self._section_cache: dict[str, list[SectionEntry]] = {}
        self._path_cache: dict[str, Path | None] = {}

    def _resolve_book_path(self, source_book: str) -> Path | None:
        if source_book in self._path_cache:
            return self._path_cache[source_book]
        candidates = [
            self.source_root / f"{source_book}.txt",
            self.source_root / f"{_normalize_book_name(source_book)}.txt",
        ]
        book_basename = _normalize_book_name(source_book)
        if book_basename:
            for path in self.source_root.glob("*.txt"):
                if _normalize_book_name(path.stem) == book_basename:
                    candidates.append(path)
        resolved = next((path for path in candidates if path.exists()), None)
        self._path_cache[source_book] = resolved
        return resolved

    def _load_sections(self, source_book: str) -> list[SectionEntry]:
        if source_book in self._section_cache:
            return self._section_cache[source_book]
        path = self._resolve_book_path(source_book)
        if path is None:
            self._section_cache[source_book] = []
            return []
        book_name = _normalize_book_name(path.stem)
        text = _read_source_text(path)
        sections: list[SectionEntry] = []
        for title, lines in _split_sections(text, fallback_title=book_name):
            paragraphs = _collapse_wrapped_lines(lines)
            body = "\n".join(paragraphs or lines)
            search_text = _search_text(body)
            if search_text:
                sections.append(
                    SectionEntry(
                        title=title or book_name,
                        search_text=search_text,
                        loose_search_text=_loose_search_text(body),
                    )
                )
        self._section_cache[source_book] = sections
        return sections

    def _unique_match(self, sections: list[SectionEntry], term: str, *, loose: bool = False) -> str | None:
        normalized_term = _loose_search_text(term) if loose else _search_text(term)
        if len(normalized_term) < 18:
            return None
        for probe_len in (220, 180, 140, 100, 80, 60, 40):
            probe = normalized_term[:probe_len]
            if len(probe) < 18:
                continue
            haystack_attr = "loose_search_text" if loose else "search_text"
            matches = [section.title for section in sections if probe in getattr(section, haystack_attr)]
            unique = list(dict.fromkeys(title for title in matches if title))
            if len(unique) == 1:
                return unique[0]
        return None

    def resolve(self, *, source_book: str, polluted_chapter: str, source_text: str) -> tuple[str | None, str]:
        sections = self._load_sections(source_book)
        if not sections:
            return None, "book_missing"
        source_term = _search_text(source_text)
        if source_term:
            title = self._unique_match(sections, source_term)
            if title:
                return title, "source_text_match"
            title = self._unique_match(sections, source_term, loose=True)
            if title:
                return title, "source_text_loose_match"
        chapter_term = _search_text(polluted_chapter)
        if chapter_term:
            title = self._unique_match(sections, chapter_term)
            if title:
                return title, "chapter_text_match"
            title = self._unique_match(sections, chapter_term, loose=True)
            if title:
                return title, "chapter_text_loose_match"
        return None, "unresolved"


def _iter_repair_candidates(evidence_path: Path) -> Iterable[dict[str, Any]]:
    for row in _iter_jsonl_rows(evidence_path):
        source_book = str(row.get("source_book", "")).strip()
        source_chapter = str(row.get("source_chapter", "")).strip()
        if not _is_polluted_source_chapter(source_chapter, source_book=source_book):
            continue
        yield row


def _derive_repairs(evidence_path: Path, *, source_root: Path) -> tuple[dict[str, str], dict[str, Any]]:
    resolver = SectionResolver(source_root)
    repairs_by_fact_id: dict[str, str] = {}
    books: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    unresolved_examples: list[dict[str, Any]] = []
    polluted_rows = 0

    for row in _iter_repair_candidates(evidence_path):
        polluted_rows += 1
        fact_id = str(row.get("fact_id", "")).strip()
        source_book = str(row.get("source_book", "")).strip()
        polluted_chapter = str(row.get("source_chapter", "")).strip()
        source_text = str(row.get("source_text", "")).strip()
        books[source_book] += 1
        repaired_chapter, reason = resolver.resolve(
            source_book=source_book,
            polluted_chapter=polluted_chapter,
            source_text=source_text,
        )
        reasons[reason] += 1
        if repaired_chapter:
            repairs_by_fact_id[fact_id] = repaired_chapter
            continue
        if polluted_chapter and len(_loose_search_text(polluted_chapter)) <= 1:
            repairs_by_fact_id[fact_id] = ""
            reasons["fallback_empty"] += 1
            continue
        unresolved_examples.append(
            {
                "fact_id": fact_id,
                "source_book": source_book,
                "source_chapter_preview": _compact_text(polluted_chapter)[:160],
                "source_text_preview": _compact_text(source_text)[:160],
            }
        )

    summary = {
        "polluted_rows": polluted_rows,
        "repaired_rows": len(repairs_by_fact_id),
        "affected_books": books.most_common(),
        "repair_reasons": reasons,
        "unresolved_examples": unresolved_examples[:20],
    }
    return repairs_by_fact_id, summary


def _write_jsonl_with_repairs(path: Path, output_path: Path, repairs_by_fact_id: dict[str, str]) -> int:
    repaired = 0
    with output_path.open("w", encoding="utf-8") as fout:
        for row in _iter_jsonl_rows(path):
            fact_id = str(row.get("fact_id", "")).strip()
            if fact_id in repairs_by_fact_id:
                replacement = repairs_by_fact_id[fact_id]
                row["source_chapter"] = replacement
                repaired += 1
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
    return repaired


def _row_fact_ids(row: dict[str, Any]) -> list[str]:
    fact_ids: list[str] = []
    raw_fact_ids = row.get("fact_ids")
    if isinstance(raw_fact_ids, list):
        for item in raw_fact_ids:
            text = str(item or "").strip()
            if text and text not in fact_ids:
                fact_ids.append(text)
    fact_id = str(row.get("fact_id", "")).strip()
    if fact_id and fact_id not in fact_ids:
        fact_ids.append(fact_id)
    return fact_ids


def _write_graph_with_repairs(path: Path, output_path: Path, repairs_by_fact_id: dict[str, str]) -> int:
    repaired = 0
    with output_path.open("w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        for row in _iter_json_array_rows(path):
            replacements = [repairs_by_fact_id[fact_id] for fact_id in _row_fact_ids(row) if fact_id in repairs_by_fact_id]
            if replacements:
                row["source_chapter"] = Counter(replacements).most_common(1)[0][0]
                repaired += 1
            if not first:
                fout.write(",\n")
            fout.write("  ")
            json.dump(row, fout, ensure_ascii=False)
            first = False
        fout.write("\n]\n")
    return repaired


def _rebuild_runtime_db(
    *,
    graph_path: Path,
    evidence_path: Path,
    db_path: Path,
    sample_graph_path: Path,
    modern_graph_path: Path,
    modern_evidence_path: Path,
) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="graph-runtime-repair-", dir=str(db_path.parent)))
    rebuilt_db_path = temp_dir / db_path.name
    store = RuntimeGraphStore(
        RuntimeGraphStoreSettings(
            graph_path=graph_path,
            evidence_path=evidence_path,
            db_path=rebuilt_db_path,
            sample_graph_path=sample_graph_path if sample_graph_path.exists() else None,
            sample_evidence_path=sample_graph_path.with_name("sample_graph.evidence.jsonl")
            if sample_graph_path.with_name("sample_graph.evidence.jsonl").exists()
            else None,
            modern_graph_path=modern_graph_path if modern_graph_path.exists() else None,
            modern_evidence_path=modern_evidence_path if modern_evidence_path.exists() else None,
        )
    )
    store.ensure_ready()
    return rebuilt_db_path, temp_dir


def _cleanup_temp_dir(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    shutil.rmtree(path, ignore_errors=True)


def _replace_with_backup(current_path: Path, replacement_path: Path, *, stamp: str) -> str:
    backup_path = current_path.with_name(f"{current_path.stem}.{stamp}.bak{current_path.suffix}")
    if current_path.exists():
        shutil.move(str(current_path), str(backup_path))
    shutil.move(str(replacement_path), str(current_path))
    return str(backup_path) if backup_path.exists() else ""


def main() -> int:
    args = _parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repairs_by_fact_id, summary = _derive_repairs(args.evidence_path, source_root=args.source_root)
    manifest: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "graph_path": str(args.graph_path),
        "evidence_path": str(args.evidence_path),
        "db_path": str(args.db_path),
        "source_root": str(args.source_root),
        "apply": bool(args.apply),
        "summary": summary,
        "backups": {},
    }

    if not args.apply:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    temp_graph_path = args.graph_path.with_name(f"{args.graph_path.stem}.{stamp}.repairing.json")
    temp_evidence_path = args.evidence_path.with_name(f"{args.evidence_path.stem}.{stamp}.repairing{args.evidence_path.suffix}")

    manifest["summary"]["repaired_evidence_rows"] = _write_jsonl_with_repairs(args.evidence_path, temp_evidence_path, repairs_by_fact_id)
    manifest["summary"]["repaired_graph_rows"] = _write_graph_with_repairs(args.graph_path, temp_graph_path, repairs_by_fact_id)

    rebuilt_db_temp_dir: Path | None = None
    try:
        rebuilt_db_path, rebuilt_db_temp_dir = _rebuild_runtime_db(
            graph_path=temp_graph_path,
            evidence_path=temp_evidence_path,
            db_path=args.db_path,
            sample_graph_path=args.sample_graph_path,
            modern_graph_path=args.modern_graph_path,
            modern_evidence_path=args.modern_evidence_path,
        )

        manifest["backups"]["graph_path"] = _replace_with_backup(args.graph_path, temp_graph_path, stamp=stamp)
        manifest["backups"]["evidence_path"] = _replace_with_backup(args.evidence_path, temp_evidence_path, stamp=stamp)
        manifest["backups"]["db_path"] = _replace_with_backup(args.db_path, rebuilt_db_path, stamp=stamp)
    finally:
        _cleanup_temp_dir(rebuilt_db_temp_dir)

    manifest_path = DEFAULT_MANIFEST_DIR / f"graph_runtime.source_chapter_repair.{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
