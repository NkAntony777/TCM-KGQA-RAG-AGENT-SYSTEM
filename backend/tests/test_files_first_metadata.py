from __future__ import annotations

from services.retrieval_service import files_first_metadata as metadata
from services.retrieval_service import files_first_support


def test_extract_book_and_chapter_from_classic_headers() -> None:
    text = "古籍：伤寒论\n篇名：辨太阳病脉证并治\n小柴胡汤功效在和解少阳。"

    assert metadata.extract_book_name(text=text, filename="001-ignored.txt", file_path="classic://伤寒论/0001") == "伤寒论"
    assert metadata.extract_chapter_title(text=text, page_number=1, file_path="classic://伤寒论/0001") == "辨太阳病脉证并治"
    assert metadata.build_section_key(
        book_name="伤寒论",
        chapter_title="辨太阳病脉证并治",
        page_number=1,
        file_path="classic://伤寒论/0001",
    ) == "伤寒论::0001"


def test_extract_book_name_falls_back_to_classic_path_then_filename() -> None:
    assert metadata.extract_book_name(text="", filename="001-ignored.txt", file_path="classic://金匮要略/0012-01") == "金匮要略"
    assert metadata.extract_book_name(text="", filename="012 - 温病条辨.txt", file_path="") == "温病条辨"


def test_strip_and_merge_section_bodies_remove_headers_and_overlap() -> None:
    repeated = "往来寒热，胸胁苦满，默默不欲饮食，心烦喜呕，口苦咽干目眩。"
    first = metadata.strip_classic_headers(f"古籍：伤寒论\n篇名：卷上\n小柴胡汤主治{repeated}")
    second = metadata.strip_classic_headers(f"古籍：伤寒论\n篇名：卷上\n{repeated}方后注可见加减。")

    merged = metadata.merge_section_bodies([first, second])

    assert "古籍：" not in merged
    assert "篇名：" not in merged
    assert merged.count(repeated) == 1
    assert merged.endswith("方后注可见加减。")


def test_build_section_metadata_tags_and_preview_passages() -> None:
    result = metadata.build_section_metadata(
        book_name="伤寒论",
        chapter_title="小柴胡汤证",
        section_text="古籍：伤寒论\n篇名：小柴胡汤证\n小柴胡汤功效在和解少阳，主治往来寒热。方后注可见加减禁忌。",
    )

    assert result["section_summary"].startswith("小柴胡汤功效在和解少阳")
    assert "功效" in result["topic_tags"]
    assert "主治" in result["topic_tags"]
    assert "小柴胡汤" in result["entity_tags"]
    assert result["representative_passages"]


def test_support_module_keeps_legacy_metadata_exports() -> None:
    assert files_first_support.extract_book_name is metadata.extract_book_name
    assert files_first_support.extract_chapter_title is metadata.extract_chapter_title
    assert files_first_support.build_section_key is metadata.build_section_key
    assert files_first_support.strip_classic_headers is metadata.strip_classic_headers
    assert files_first_support.merge_section_bodies is metadata.merge_section_bodies
    assert files_first_support._build_section_metadata is metadata.build_section_metadata
