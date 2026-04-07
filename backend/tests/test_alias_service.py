from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from services.qa_service.alias_service import RuntimeAliasService


def _init_alias_db(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            """
            CREATE TABLE facts (
                subject TEXT,
                predicate TEXT,
                object TEXT,
                source_book TEXT,
                source_chapter TEXT,
                best_source_text TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO facts (subject, predicate, object, source_book, source_chapter, best_source_text)
            VALUES (?, '别名', ?, ?, ?, ?)
            """,
            [
                ("六味地黄丸", "地黄丸", "小儿药证直诀", "卷下", "六味地黄丸，一名地黄丸。"),
                ("六味地黄丸", "六味丸", "医方考", "卷三", "六味地黄丸，又名六味丸。"),
                ("金匮肾气丸", "肾气丸", "金匮要略", "卷中", "肾气丸即金匮肾气丸。"),
                ("肾气丸", "八味丸", "金匮要略", "卷中", "八味丸即肾气丸。"),
            ],
        )
        conn.commit()


class AliasServiceTests(unittest.TestCase):
    def test_alias_service_expands_connected_alias_cluster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "graph_runtime.db"
            _init_alias_db(db_path)
            service = RuntimeAliasService(db_path)

            aliases = service.aliases_for_entity("金匮肾气丸", max_aliases=4)

        self.assertIn("肾气丸", aliases)
        self.assertIn("八味丸", aliases)

    def test_alias_service_can_expand_query_with_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "graph_runtime.db"
            _init_alias_db(db_path)
            service = RuntimeAliasService(db_path)

            expanded = service.expand_query_with_aliases("六味地黄丸 出处 原文")

        self.assertIn("地黄丸", expanded)
        self.assertIn("六味丸", expanded)

    def test_alias_relations_include_source_book(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "graph_runtime.db"
            _init_alias_db(db_path)
            service = RuntimeAliasService(db_path)

            items = service.alias_relations("六味地黄丸", max_items=4)

        aliases = {item.alias: item for item in items}
        self.assertIn("地黄丸", aliases)
        self.assertEqual(aliases["地黄丸"].source_book, "小儿药证直诀")


if __name__ == "__main__":
    unittest.main()
