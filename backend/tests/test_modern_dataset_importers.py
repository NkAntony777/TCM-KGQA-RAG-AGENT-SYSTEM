from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.import_classic_books import build_classic_books_corpus
from scripts.import_herb2 import build_herb2_corpus
from scripts.import_tcm_mkg import build_tcm_mkg_graph


def _write(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


class TcmMkgImporterTests(unittest.TestCase):
    def test_build_tcm_mkg_graph_maps_core_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "D2_Chinese_patent_medicine.tsv", "CPM_ID\tChinese_patent_medicine\nCPM1\t测试方")
            _write(root / "D3_CPM_TCMT.tsv", "CPM_ID\tChinese_group\tChinese_term\nCPM1\t治则\t扶正祛邪")
            _write(root / "D4_CPM_CHP.tsv", "CPM_ID\tCHP_ID\nCPM1\tCHP1")
            _write(root / "D5_CPM_ICD11.tsv", "CPM_ID\tICD11_code\nCPM1\tA00")
            _write(root / "D6_Chinese_herbal_pieces.tsv", "CHP_ID\tChinese_herbal_pieces\nCHP1\t测试药")
            _write(root / "D7_CHP_Medicinal_properties.tsv", "CHP_ID\tMedicinal_properties\tClass\nCHP1\tSweet medicinal\tMedicinal flavor")
            _write(root / "D8_CHP_PO.tsv", "CHP_ID\tspecies_name\nCHP1\tTest species")
            _write(root / "D9_CHP_InChIKey.tsv", "CHP_ID\tInChIKey\nCHP1\tINK1")
            _write(root / "D13_InChIKey_EntrezID.tsv", "InChIKey\tEntrezID\nINK1\t1")
            _write(root / "D17_Target_Symbol_Mapping.tsv", "EntrezID\tGeneSymbol\n1\tGENE1")
            _write(root / "D18_ICD11.tsv", "ICD11_code\tChinese_term\nA00\t测试病")
            _write(root / "D19_ICD11_CUI.tsv", "ICD11_code\tCUI\nA00\tC0001")
            _write(root / "D20_ICD11_MeSH.tsv", "ICD11_code\tMeSH\nA00\tM0001")
            _write(root / "D21_ICD11_DOID.tsv", "ICD11_code\tDOID\nA00\tDOID:1")
            _write(root / "D22_CUI_targets.tsv", "CUI\tEntrezID\nC0001\t1")
            _write(root / "D23_MeSH_targets.tsv", "MeSH\tEntrezID\nM0001\t1")
            _write(root / "D24_DOID_targets.tsv", "DOID\tEntrezID\nDOID:1\t1")

            facts, evidence, manifest = build_tcm_mkg_graph(root)

        self.assertTrue(facts)
        self.assertEqual(len(facts), len(evidence))
        predicates = {(item["subject"], item["predicate"], item["object"]) for item in facts}
        self.assertIn(("测试方", "使用药材", "测试药"), predicates)
        self.assertIn(("测试方", "现代适应证", "测试病"), predicates)
        self.assertIn(("测试方", "治法", "扶正祛邪"), predicates)
        self.assertIn(("测试药", "药味", "Sweet medicinal"), predicates)
        self.assertIn(("测试药", "药材基源", "Test species"), predicates)
        self.assertIn(("测试药", "含有成分", "INK1"), predicates)
        self.assertIn(("INK1", "作用靶点", "GENE1"), predicates)
        self.assertIn(("测试病", "关联靶点", "GENE1"), predicates)
        self.assertGreaterEqual(manifest["facts"], 8)


class Herb2ImporterTests(unittest.TestCase):
    def test_build_herb2_corpus_emits_modern_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "HERB_formula_info_v2.txt",
                "Formula_id\tFormula_cn_name\tFormula_pinyin_name\tFormula_en_name\tDosage_form\tAdministration\tType\tCategory\tHerbs_in_Chinese\tSyndromes_in_Chinese\tIndications_in_Chinese\tSource\nF1\t测试方\tCe Shi Fang\tTest Formula\t丸剂\tOral\t补益药\t中成药\t测试药\t测试证\t测试病\tETCM",
            )
            _write(
                root / "HERB_herb_info_v2.txt",
                "Herb_id\tHerb_cn_name\tHerb_pinyin_name\tHerb_en_name\tHerb_alias_name\tSource\nH1\t测试药\tCe Shi Yao\tTest Herb\t别名\tETCM",
            )
            _write(
                root / "HERB_reference_info_v2.txt",
                "Reference_id\tSubject_name\tSubject_type\tPaper_title\tPaper_abstract\tExperiment_type\tPhenotype_related\tJournal\tDOI\tPubMed_id\tPublish_date\nR1\t测试药\tHerb\t文献标题\t文献摘要\tAnimal\tPhenotype\tJournal\t10.1/test\t123\t2024",
            )
            _write(
                root / "HERB_clinical_trials_v2.txt",
                "Clinical_trial_id\tSubject_name\tSubject_type\tNCT_id\tNCT_title\tStatus\tPhase \tStudy_condition\tStudy_type\tIntervention\tOutcome_measure\tLocation\tURL\nC1\t测试药\tHerb\tNCT1\t试验标题\tCompleted\tII\t测试病\tInterventional\t测试干预\t测试结局\t中国\thttps://example.com",
            )
            _write(
                root / "HERB_meta_info_v2.txt",
                "Meta_id\tSubject_name\tCRD_title\tCondition_being_studied\tIntervention\tOutcome_measure\tURL\nM1\t测试药\tMeta标题\t测试病\t测试干预\t测试结局\thttps://example.com/meta",
            )
            _write(
                root / "HERB_experiment_info_v2.txt",
                "Experiment_id\tSubject_name\tGSE_id\tExperiment_type\tTissue\tCell_type\tCell_line\tSubject_disease_key\nE1\t测试药\tGSE1\tRNA-seq\tLiver\tCell\tLine\tKEY1",
            )

            docs, manifest = build_herb2_corpus(root)

        self.assertEqual(manifest["total_docs"], 6)
        file_paths = {doc["file_path"] for doc in docs}
        self.assertIn("herb2://formula/F1", file_paths)
        self.assertIn("herb2://reference/R1", file_paths)
        self.assertIn("herb2://trial/C1", file_paths)
        self.assertIn("herb2://meta/M1", file_paths)
        self.assertIn("herb2://experiment/E1", file_paths)


class ClassicBooksImporterTests(unittest.TestCase):
    def test_build_classic_books_corpus_emits_classic_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = (
                "<篇名>小儿药证直诀\n"
                "书名：小儿药证直诀\n"
                "作者：钱乙\n"
                "\n"
                "<目录>\n"
                "<篇名>卷上\n"
                "属性：六味地黄丸，治肾怯失音，囟开不合，神不足。\n"
                "熟地黄八两，山茱萸四两，山药四两。\n"
            )
            (root / "133-小儿药证直诀.txt").write_bytes(content.encode("gb18030"))

            docs, manifest = build_classic_books_corpus(root, chunk_size=80, overlap_chars=10)

        self.assertEqual(manifest["books_processed"], 1)
        self.assertGreaterEqual(manifest["sections_processed"], 1)
        self.assertTrue(any(str(doc["file_path"]).startswith("classic://小儿药证直诀/") for doc in docs))
        self.assertTrue(any("篇名：卷上" in str(doc["text"]) for doc in docs))
        self.assertTrue(any("六味地黄丸" in str(doc["text"]) for doc in docs))


if __name__ == "__main__":
    unittest.main()
