from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.graph_service.nebulagraph_store import (
    NebulaGraphStore,
    NebulaGraphSettings,
    _escape_ngql,
    edge_rank,
    entity_vid,
    load_graph_rows,
    load_nebula_settings,
)


class TestNebulaGraphStore(unittest.TestCase):
    def test_default_password_is_not_hardcoded(self) -> None:
        self.assertEqual(NebulaGraphSettings().password, "")

    def test_load_settings_does_not_default_to_nebula_password(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_nebula_settings().password, "")

    def test_escape_ngql_escapes_backtick_and_quotes(self) -> None:
        self.assertEqual(_escape_ngql('a`b"c'), 'a\\`b\\"c')

    def test_entity_vid_is_stable(self) -> None:
        self.assertEqual(entity_vid("六味地黄丸"), entity_vid("六味地黄丸"))
        self.assertNotEqual(entity_vid("六味地黄丸"), entity_vid("四君子汤"))

    def test_load_graph_rows_merges_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            graph_path = root / "graph.json"
            evidence_path = root / "graph.evidence.jsonl"

            graph_path.write_text(
                json.dumps(
                    [
                        {
                            "subject": "测试方",
                            "predicate": "使用药材",
                            "object": "甘草",
                            "subject_type": "formula",
                            "object_type": "herb",
                            "fact_id": "fact-1",
                            "fact_ids": ["fact-1"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence_path.write_text(
                json.dumps(
                    {
                        "fact_id": "fact-1",
                        "source_text": "测试方以甘草为君。",
                        "confidence": 0.95,
                    },
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )

            rows = load_graph_rows(graph_path, evidence_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_text"], "测试方以甘草为君。")
            self.assertAlmostEqual(float(rows[0]["confidence"]), 0.95, places=2)

    def test_load_graph_rows_supports_jsonl_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            graph_path = root / "graph.jsonl"
            evidence_path = root / "graph.evidence.jsonl"

            graph_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "subject": "测试方",
                                "predicate": "使用药材",
                                "object": "甘草",
                                "subject_type": "formula",
                                "object_type": "herb",
                                "fact_id": "fact-1",
                                "fact_ids": ["fact-1"],
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "subject": "测试方",
                                "predicate": "治疗证候",
                                "object": "气虚证",
                                "subject_type": "formula",
                                "object_type": "syndrome",
                                "fact_id": "fact-2",
                                "fact_ids": ["fact-2"],
                            },
                            ensure_ascii=False,
                        ),
                    ]
                ) + "\n",
                encoding="utf-8",
            )
            evidence_path.write_text(
                json.dumps(
                    {
                        "fact_id": "fact-1",
                        "source_text": "测试方以甘草为君。",
                        "confidence": 0.95,
                    },
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )

            rows = load_graph_rows(graph_path, evidence_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["source_text"], "测试方以甘草为君。")
            self.assertAlmostEqual(float(rows[0]["confidence"]), 0.95, places=2)

    def test_export_ngql_contains_schema_and_insert_statements(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            graph_path = root / "graph.json"
            output_path = root / "graph.ngql"

            graph_path.write_text(
                json.dumps(
                    [
                        {
                            "subject": "测试方",
                            "predicate": "使用药材",
                            "object": "甘草",
                            "subject_type": "formula",
                            "object_type": "herb",
                            "fact_id": "fact-1",
                            "fact_ids": ["fact-1"],
                            "source_book": "测试书",
                            "source_chapter": "正文",
                            "source_text": "测试方以甘草为君。",
                            "confidence": 0.95,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = NebulaGraphStore().export_ngql(graph_path, None, output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertEqual(summary["triples"], 1)
            self.assertIn("CREATE SPACE IF NOT EXISTS", content)
            self.assertIn("CREATE TAG IF NOT EXISTS `entity`", content)
            self.assertIn("CREATE EDGE IF NOT EXISTS `relation`", content)
            self.assertIn("INSERT VERTEX `entity`", content)
            self.assertIn("INSERT EDGE `relation`", content)
            self.assertIn("测试方", content)
            self.assertIn("甘草", content)

    def test_build_import_statements_use_distinct_edge_ranks_for_same_entity_pair(self) -> None:
        store = NebulaGraphStore()
        rows = [
            {
                "subject": "桂枝汤",
                "predicate": "治疗证候",
                "object": "太阳中风",
                "subject_type": "formula",
                "object_type": "syndrome",
                "fact_id": "fact-a",
                "source_book": "伤寒论",
                "source_chapter": "辨太阳病脉证并治上",
            },
            {
                "subject": "桂枝汤",
                "predicate": "组成",
                "object": "太阳中风",
                "subject_type": "formula",
                "object_type": "syndrome",
                "fact_id": "fact-b",
                "source_book": "伤寒论",
                "source_chapter": "辨太阳病脉证并治上",
            },
        ]

        statements = store.build_import_statements(rows)
        edge_statements = [stmt for stmt in statements if stmt.startswith("INSERT EDGE `relation`")]

        self.assertEqual(len(edge_statements), 2)
        self.assertIn(f'@{edge_rank(rows[0])}:', edge_statements[0])
        self.assertIn(f'@{edge_rank(rows[1])}:', edge_statements[1])
        self.assertNotEqual(edge_rank(rows[0]), edge_rank(rows[1]))

    def test_build_import_statements_escape_multiline_source_text(self) -> None:
        store = NebulaGraphStore()
        rows = [
            {
                "subject": "孔圣枕中丹",
                "predicate": "属于范畴",
                "object": "补养之剂",
                "subject_type": "formula",
                "object_type": "category",
                "fact_id": "fact-multiline",
                "source_book": "089-医方论",
                "source_chapter": "089-医方论_正文",
                "source_text": "卷一\\n补养之剂\\n\\n孔圣枕中丹",
                "confidence": 1.0,
            }
        ]

        statements = store.build_import_statements(rows)
        edge_statement = next(stmt for stmt in statements if stmt.startswith("INSERT EDGE `relation`"))

        self.assertIn("\\n", edge_statement)
        self.assertNotIn("卷一\n补养之剂", edge_statement)


if __name__ == "__main__":
    unittest.main()
