from __future__ import annotations

import gc
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.retrieval_service.files_first_support import LocalFilesFirstStore
from services.retrieval_service.files_first_support import _prepare_match_terms


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[。，“”、；：:（）()\[\]《》]", " ", str(text or ""))
        return [token for token in normalized.split() if token]


class FilesFirstSupportTests(unittest.TestCase):
    def test_rebuild_generates_section_metadata_and_section_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesFirstStore(Path(tmp) / "retrieval_local_index.fts.db", tokenizer=FakeTokenizer())
            rows = [
                {
                    "chunk_id": "leaf-1",
                    "text": "古籍：伤寒论\n篇名：辨太阳病脉证并治\n小柴胡汤功效在和解少阳，主治往来寒热。",
                    "filename": "伤寒论.txt",
                    "file_path": "classic://伤寒论/0001",
                    "page_number": 1,
                    "chunk_idx": 1,
                    "chunk_level": 3,
                    "parent_chunk_id": "parent-1",
                    "root_chunk_id": "root-1",
                },
                {
                    "chunk_id": "leaf-2",
                    "text": "古籍：伤寒论\n篇名：辨太阳病脉证并治\n方后注可见咳者去人参加干姜五味子。",
                    "filename": "伤寒论.txt",
                    "file_path": "classic://伤寒论/0001",
                    "page_number": 1,
                    "chunk_idx": 2,
                    "chunk_level": 3,
                    "parent_chunk_id": "parent-1",
                    "root_chunk_id": "root-1",
                },
            ]
            rebuild = store.rebuild(rows)
            self.assertEqual(rebuild["indexed_sections"], 1)

            results, mode = store.search(
                query="小柴胡汤 功效 和解少阳",
                top_k=3,
                candidate_k=6,
                leaf_level=3,
            )
            self.assertTrue(results)
            self.assertEqual(mode, "fts_local")
            self.assertEqual(results[0]["file_type"], "SECTION")
            self.assertEqual(results[0]["chunk_level"], 2)
            self.assertIn("section_summary", results[0])
            self.assertIn("topic_tags", results[0])

            section = store.read_section(path="chapter://伤寒论/辨太阳病脉证并治", top_k=8)
            self.assertEqual(section["status"], "ok")
            self.assertIn("section", section)
            self.assertTrue(section["section"]["section_summary"])
            self.assertIn("功效", section["section"]["topic_tags"])

    def test_health_auto_migrates_legacy_schema(self) -> None:
        tmp = tempfile.mkdtemp()
        try:
            db_path = Path(tmp) / "retrieval_local_index.fts.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE docs (chunk_id TEXT PRIMARY KEY, text TEXT, filename TEXT, file_type TEXT, file_path TEXT, page_number INTEGER, chunk_idx INTEGER, parent_chunk_id TEXT, root_chunk_id TEXT, chunk_level INTEGER, book_name TEXT, chapter_title TEXT, section_key TEXT)"
                )
                conn.execute(
                    "INSERT INTO docs (chunk_id, text, filename, file_type, file_path, page_number, chunk_idx, parent_chunk_id, root_chunk_id, chunk_level, book_name, chapter_title, section_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("leaf-1", "古籍：伤寒论\n篇名：卷上\n小柴胡汤。", "伤寒论.txt", "TXT", "classic://伤寒论/0001", 1, 0, "", "", 3, "伤寒论", "卷上", "伤寒论::卷上"),
                )
                conn.commit()
            store = LocalFilesFirstStore(db_path, tokenizer=FakeTokenizer())
            health = store.health()
            self.assertTrue(health["files_first_schema_migrated"])
            self.assertTrue(health["files_first_index_available"])
            self.assertTrue(health["files_first_schema_compatible"])
            del store
            gc.collect()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_prepare_match_terms_strips_prompt_scaffolding(self) -> None:
        terms = _prepare_match_terms("逍遥散一个比较适合直接引用的古籍出处片段是什么", FakeTokenizer())
        self.assertIn("逍遥散", terms)
        self.assertIn("出处", terms)
        self.assertIn("原文", terms)
        self.assertFalse(any("一个比较" in item for item in terms))
        self.assertFalse(any("逍遥散一个比较" in item for item in terms))

    def test_search_prefers_rows_covering_multiple_focus_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesFirstStore(Path(tmp) / "retrieval_local_index.fts.db", tokenizer=FakeTokenizer())
            rows = [
                {
                    "chunk_id": "leaf-1",
                    "text": "古籍：医宗金鉴\n篇名：托里消毒饮\n托里消毒饮 组成 黄芪 当归 甘草。",
                    "filename": "医宗金鉴.txt",
                    "file_path": "classic://医宗金鉴/0001",
                    "page_number": 1,
                    "chunk_idx": 1,
                    "chunk_level": 3,
                    "parent_chunk_id": "parent-1",
                    "root_chunk_id": "root-1",
                },
                {
                    "chunk_id": "leaf-2",
                    "text": "古籍：外科证治全书\n篇名：托里消毒饮加减\n托里消毒饮 金银花 配伍 清热解毒 散结。",
                    "filename": "外科证治全书.txt",
                    "file_path": "classic://外科证治全书/0002",
                    "page_number": 2,
                    "chunk_idx": 1,
                    "chunk_level": 3,
                    "parent_chunk_id": "parent-2",
                    "root_chunk_id": "root-2",
                },
            ]
            store.rebuild(rows)

            results, mode = store.search(
                query="托里消毒饮中的金银花在方剂中起什么作用",
                top_k=3,
                candidate_k=6,
                leaf_level=3,
            )

            self.assertEqual(mode, "fts_local")
            self.assertTrue(results)
            self.assertEqual(results[0]["book_name"], "外科证治全书")
            self.assertIn("金银花", results[0]["text"])


if __name__ == "__main__":
    unittest.main()
