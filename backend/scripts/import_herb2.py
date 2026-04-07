from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = Path(r"D:\herb2.0")
DEFAULT_OUTPUT = BACKEND_DIR / "services" / "retrieval_service" / "data" / "herb2_modern_corpus.json"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [{str(key or "").strip(): _clean(value) for key, value in row.items()} for row in reader]


def _chunk(
    *,
    chunk_id: str,
    filename: str,
    file_path: str,
    title: str,
    body_lines: list[str],
    page_number: int = 0,
) -> dict[str, object]:
    text = "\n".join([title, *[line for line in body_lines if line]])[:4000]
    return {
        "chunk_id": chunk_id,
        "chunk_idx": 0,
        "parent_chunk_id": "",
        "root_chunk_id": chunk_id,
        "chunk_level": 3,
        "filename": filename,
        "file_type": "TXT",
        "file_path": file_path,
        "page_number": page_number,
        "text": text,
    }


def build_herb2_corpus(source_root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    docs: list[dict[str, object]] = []
    stats: dict[str, int] = {}

    for row in _tsv_rows(source_root / "HERB_formula_info_v2.txt"):
        formula_id = _clean(row.get("Formula_id"))
        formula_name = _clean(row.get("Formula_cn_name")) or _clean(row.get("Formula_pinyin_name"))
        if not formula_id or not formula_name:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-formula-{formula_id}",
                filename="HERB2_formula.txt",
                file_path=f"herb2://formula/{formula_id}",
                title=f"HERB2 方剂资料: {formula_name}",
                body_lines=[
                    f"方剂ID: {formula_id}",
                    f"拼音名: {_clean(row.get('Formula_pinyin_name'))}",
                    f"英文名: {_clean(row.get('Formula_en_name'))}",
                    f"剂型: {_clean(row.get('Dosage_form'))}",
                    f"给药方式: {_clean(row.get('Administration'))}",
                    f"分类: {_clean(row.get('Type'))}",
                    f"类别: {_clean(row.get('Category'))}",
                    f"组成: {_clean(row.get('Herbs_in_Chinese'))}",
                    f"证候: {_clean(row.get('Syndromes_in_Chinese'))}",
                    f"适应证: {_clean(row.get('Indications_in_Chinese'))}",
                    f"来源数据库: {_clean(row.get('Source'))}",
                ],
            )
        )
    stats["formula_docs"] = len(docs)

    herb_docs = 0
    for row in _tsv_rows(source_root / "HERB_herb_info_v2.txt"):
        herb_id = _clean(row.get("Herb_id"))
        herb_name = _clean(row.get("Herb_cn_name")) or _clean(row.get("Herb_pinyin_name"))
        if not herb_id or not herb_name:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-herb-{herb_id}",
                filename="HERB2_herb.txt",
                file_path=f"herb2://herb/{herb_id}",
                title=f"HERB2 药材资料: {herb_name}",
                body_lines=[
                    f"药材ID: {herb_id}",
                    f"拼音名: {_clean(row.get('Herb_pinyin_name'))}",
                    f"英文名: {_clean(row.get('Herb_en_name'))}",
                    f"别名: {_clean(row.get('Herb_alias_name'))}",
                    f"来源: {_clean(row.get('Source'))}",
                ],
            )
        )
        herb_docs += 1
    stats["herb_docs"] = herb_docs

    reference_docs = 0
    for row in _tsv_rows(source_root / "HERB_reference_info_v2.txt"):
        ref_id = _clean(row.get("Reference_id"))
        title = _clean(row.get("Paper_title"))
        subject_name = _clean(row.get("Subject_name"))
        if not ref_id or not title:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-reference-{ref_id}",
                filename="HERB2_reference.txt",
                file_path=f"herb2://reference/{ref_id}",
                title=f"HERB2 文献证据: {subject_name or _clean(row.get('Subject_id'))}",
                body_lines=[
                    f"证据ID: {ref_id}",
                    f"主题: {subject_name}",
                    f"主题类型: {_clean(row.get('Subject_type'))}",
                    f"论文标题: {title}",
                    f"摘要: {_clean(row.get('Paper_abstract'))}",
                    f"实验类型: {_clean(row.get('Experiment_type'))}",
                    f"表型相关: {_clean(row.get('Phenotype_related'))}",
                    f"期刊: {_clean(row.get('Journal'))}",
                    f"DOI: {_clean(row.get('DOI'))}",
                    f"PubMed: {_clean(row.get('PubMed_id'))}",
                    f"发表时间: {_clean(row.get('Publish_date'))}",
                ],
            )
        )
        reference_docs += 1
    stats["reference_docs"] = reference_docs

    trial_docs = 0
    for row in _tsv_rows(source_root / "HERB_clinical_trials_v2.txt"):
        trial_id = _clean(row.get("Clinical_trial_id"))
        subject_name = _clean(row.get("Subject_name"))
        nct_id = _clean(row.get("NCT_id"))
        if not trial_id or not subject_name:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-trial-{trial_id}",
                filename="HERB2_trial.txt",
                file_path=f"herb2://trial/{trial_id}",
                title=f"HERB2 临床试验证据: {subject_name}",
                body_lines=[
                    f"试验ID: {trial_id}",
                    f"NCT: {nct_id}",
                    f"标题: {_clean(row.get('NCT_title'))}",
                    f"主题类型: {_clean(row.get('Subject_type'))}",
                    f"研究状态: {_clean(row.get('Status'))}",
                    f"阶段: {_clean(row.get('Phase ')) or _clean(row.get('Phase'))}",
                    f"疾病/状态: {_clean(row.get('Study_condition'))}",
                    f"研究类型: {_clean(row.get('Study_type'))}",
                    f"干预: {_clean(row.get('Intervention'))}",
                    f"主要结局: {_clean(row.get('Outcome_measure'))}",
                    f"地点: {_clean(row.get('Location'))}",
                    f"链接: {_clean(row.get('URL'))}",
                ],
            )
        )
        trial_docs += 1
    stats["trial_docs"] = trial_docs

    meta_docs = 0
    for row in _tsv_rows(source_root / "HERB_meta_info_v2.txt"):
        meta_id = _clean(row.get("Meta_id")) or _clean(row.get("CRD_id")) or _clean(row.get("Subject_id"))
        title = _clean(row.get("CRD_title")) or _clean(row.get("Title"))
        subject_name = _clean(row.get("Subject_name"))
        if not meta_id or not title:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-meta-{meta_id}",
                filename="HERB2_meta.txt",
                file_path=f"herb2://meta/{meta_id}",
                title=f"HERB2 Meta 证据: {subject_name or meta_id}",
                body_lines=[
                    f"Meta ID: {meta_id}",
                    f"主题: {subject_name}",
                    f"标题: {title}",
                    f"研究病种: {_clean(row.get('Condition_being_studied'))}",
                    f"干预: {_clean(row.get('Intervention'))}",
                    f"结局指标: {_clean(row.get('Outcome_measure'))}",
                    f"来源链接: {_clean(row.get('URL'))}",
                ],
            )
        )
        meta_docs += 1
    stats["meta_docs"] = meta_docs

    experiment_docs = 0
    for row in _tsv_rows(source_root / "HERB_experiment_info_v2.txt"):
        exp_id = _clean(row.get("Experiment_id")) or _clean(row.get("GSE_id")) or _clean(row.get("Subject_disease_key"))
        subject_name = _clean(row.get("Subject_name")) or _clean(row.get("Subject_disease_key"))
        if not exp_id or not subject_name:
            continue
        docs.append(
            _chunk(
                chunk_id=f"herb2-experiment-{exp_id}",
                filename="HERB2_experiment.txt",
                file_path=f"herb2://experiment/{exp_id}",
                title=f"HERB2 实验证据: {subject_name}",
                body_lines=[
                    f"实验ID: {exp_id}",
                    f"GSE: {_clean(row.get('GSE_id'))}",
                    f"实验类型: {_clean(row.get('Experiment_type'))}",
                    f"组织: {_clean(row.get('Tissue'))}",
                    f"细胞类型: {_clean(row.get('Cell_type'))}",
                    f"细胞系: {_clean(row.get('Cell_line'))}",
                    f"疾病键: {_clean(row.get('Subject_disease_key'))}",
                ],
            )
        )
        experiment_docs += 1
    stats["experiment_docs"] = experiment_docs

    stats["total_docs"] = len(docs)
    return docs, {"source_root": str(source_root), **stats}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert HERB 2.0 tables into retrieval corpus JSON.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    docs, manifest = build_herb2_corpus(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    args.manifest_output.write_text(
        json.dumps(
            {
                **manifest,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(args.manifest_output.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
