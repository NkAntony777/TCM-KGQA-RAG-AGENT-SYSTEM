from __future__ import annotations

import unittest

from services.common.evidence_payloads import graph_relation_items
from services.common.evidence_payloads import normalize_source_chapter_label


class EvidencePayloadNormalizationTests(unittest.TestCase):
    def test_normalize_source_chapter_strips_book_prefixed_body_slug(self) -> None:
        self.assertEqual(
            normalize_source_chapter_label(source_book="089-医方论", source_chapter="089-医方论_正文"),
            "",
        )

    def test_normalize_source_chapter_keeps_readable_tail_after_book_prefix(self) -> None:
        self.assertEqual(
            normalize_source_chapter_label(source_book="089-医方论", source_chapter="089-医方论_卷上"),
            "卷上",
        )

    def test_graph_relation_items_emit_book_scope_when_chapter_is_only_body_slug(self) -> None:
        payload = {
            "data": {
                "relations": [
                    {
                        "predicate": "出处",
                        "target": "六味地黄丸",
                        "source_book": "089-医方论",
                        "source_chapter": "089-医方论_正文",
                        "source_text": "地黄（砂仁酒拌、九蒸九晒）八两",
                    }
                ]
            }
        }

        items = graph_relation_items(payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_book"], "089-医方论")
        self.assertIsNone(items[0]["source_chapter"])
        self.assertEqual(items[0]["evidence_path"], "book://医方论/*")
        self.assertEqual(items[0]["source_scope_path"], "book://医方论/*")


if __name__ == "__main__":
    unittest.main()
