from __future__ import annotations

from tools.evidence_path_resolver import ordered_unique_paths, parse_evidence_path, source_scope_specs


def test_parse_evidence_path_decodes_scheme_head_and_tail() -> None:
    parsed = parse_evidence_path("chapter://小儿药证直诀/%E5%8D%B7%E4%B8%8A")

    assert parsed.normalized == "chapter://小儿药证直诀/卷上"
    assert parsed.scheme == "chapter"
    assert parsed.head == "小儿药证直诀"
    assert parsed.tail == "卷上"


def test_parse_path_query_keeps_arrow_body_available() -> None:
    parsed = parse_evidence_path("path://熟地黄->六味地黄丸")

    assert parsed.scheme == "path"
    assert parsed.body == "熟地黄->六味地黄丸"
    assert parsed.head == "熟地黄->六味地黄丸"
    assert parsed.tail == ""


def test_ordered_unique_paths_preserves_existing_priority_contract() -> None:
    assert ordered_unique_paths(
        [
            "qa://六味地黄丸/similar",
            "book://小儿药证直诀/*",
            "alias://六味地黄丸",
            "entity://六味地黄丸/*",
            "chapter://小儿药证直诀/%E5%8D%B7%E4%B8%8A",
            "caseqa://六味地黄丸/similar",
            "entity://六味地黄丸/*",
        ]
    ) == [
        "entity://六味地黄丸/*",
        "alias://六味地黄丸",
        "chapter://小儿药证直诀/卷上",
        "book://小儿药证直诀/*",
        "qa://六味地黄丸/similar",
        "caseqa://六味地黄丸/similar",
    ]


def test_source_scope_specs_normalize_book_labels_and_dedupe() -> None:
    assert source_scope_specs(["book://089-医方论/*", "book://医方论/正文"]) == [
        ("医方论", ""),
        ("医方论", "正文"),
    ]
