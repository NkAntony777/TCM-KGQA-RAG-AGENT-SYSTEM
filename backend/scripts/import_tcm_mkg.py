from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = Path(r"D:\TCM-MKG")
DEFAULT_GRAPH_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "modern_graph_runtime.jsonl"
DEFAULT_EVIDENCE_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "modern_graph_runtime.evidence.jsonl"
SOURCE_BOOK = "TCM-MKG"


def _tsv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}


def _clean(value: str) -> str:
    return str(value or "").strip()


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


class ModernGraphEmitter:
    def __init__(self) -> None:
        self.fact_counter = 0
        self.edge_count = 0
        self.evidence_count = 0
        self.by_chapter: dict[str, int] = {}
        self._facts: list[dict[str, object]] = []
        self._evidence: list[dict[str, object]] = []

    def add(
        self,
        *,
        subject: str,
        predicate: str,
        obj: str,
        subject_type: str,
        object_type: str,
        source_chapter: str,
        source_text: str,
        confidence: float = 0.85,
    ) -> None:
        subject = _clean(subject)
        predicate = _clean(predicate)
        obj = _clean(obj)
        source_text = _clean(source_text)
        if not subject or not predicate or not obj:
            return
        self.fact_counter += 1
        fact_id = f"tcm_mkg:{source_chapter}:{self.fact_counter:07d}"
        self._facts.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "subject_type": subject_type,
                "object_type": object_type,
                "source_book": SOURCE_BOOK,
                "source_chapter": source_chapter,
                "fact_id": fact_id,
            }
        )
        self._evidence.append(
            {
                "fact_id": fact_id,
                "source_book": SOURCE_BOOK,
                "source_chapter": source_chapter,
                "source_text": source_text[:1600],
                "confidence": round(float(confidence), 4),
            }
        )
        self.edge_count += 1
        self.evidence_count += 1
        self.by_chapter[source_chapter] = self.by_chapter.get(source_chapter, 0) + 1

    @property
    def facts(self) -> list[dict[str, object]]:
        return self._facts

    @property
    def evidence(self) -> list[dict[str, object]]:
        return self._evidence


def _load_name_map(path: Path, *, key_field: str, value_field: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for row in _tsv_rows(path):
        key = _clean(row.get(key_field, ""))
        value = _clean(row.get(value_field, ""))
        if key and value:
            payload[key] = value
    return payload


def build_tcm_mkg_graph(
    source_root: Path,
    *,
    include_mesh_doid_bridges: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    cpm_names = _load_name_map(source_root / "D2_Chinese_patent_medicine.tsv", key_field="CPM_ID", value_field="Chinese_patent_medicine")
    chp_names = _load_name_map(source_root / "D6_Chinese_herbal_pieces.tsv", key_field="CHP_ID", value_field="Chinese_herbal_pieces")
    icd_names = _load_name_map(source_root / "D18_ICD11.tsv", key_field="ICD11_code", value_field="Chinese_term")
    gene_symbols = _load_name_map(source_root / "D17_Target_Symbol_Mapping.tsv", key_field="EntrezID", value_field="GeneSymbol")

    emitter = ModernGraphEmitter()
    referenced_chp_ids: set[str] = set()
    referenced_icd_codes: set[str] = set()
    reachable_inchikeys: set[str] = set()

    for row in _tsv_rows(source_root / "D4_CPM_CHP.tsv"):
        formula_name = cpm_names.get(_clean(row.get("CPM_ID", "")))
        herb_name = chp_names.get(_clean(row.get("CHP_ID", "")))
        chp_id = _clean(row.get("CHP_ID", ""))
        if not formula_name or not herb_name:
            continue
        referenced_chp_ids.add(chp_id)
        emitter.add(
            subject=formula_name,
            predicate="使用药材",
            obj=herb_name,
            subject_type="formula",
            object_type="herb",
            source_chapter="D4_CPM_CHP",
            source_text=f"{formula_name} 关联药材 {herb_name}（CHP_ID={chp_id}）。",
            confidence=0.98,
        )

    for row in _tsv_rows(source_root / "D5_CPM_ICD11.tsv"):
        formula_name = cpm_names.get(_clean(row.get("CPM_ID", "")))
        icd_code = _clean(row.get("ICD11_code", ""))
        disease_name = icd_names.get(icd_code) or _clean(row.get("English_term", "")) or icd_code
        if not formula_name or not disease_name or not icd_code:
            continue
        referenced_icd_codes.add(icd_code)
        emitter.add(
            subject=formula_name,
            predicate="现代适应证",
            obj=disease_name,
            subject_type="formula",
            object_type="disease",
            source_chapter="D5_CPM_ICD11",
            source_text=f"{formula_name} 在 TCM-MKG 中关联 ICD11 {icd_code}：{disease_name}。",
            confidence=0.92,
        )

    for row in _tsv_rows(source_root / "D3_CPM_TCMT.tsv"):
        formula_name = cpm_names.get(_clean(row.get("CPM_ID", "")))
        term = _clean(row.get("Chinese_term", ""))
        group_name = _clean(row.get("Chinese_group", ""))
        if not formula_name or not term:
            continue
        predicate = "治法" if group_name == "治则" else "关联术语"
        emitter.add(
            subject=formula_name,
            predicate=predicate,
            obj=term,
            subject_type="formula",
            object_type="therapy" if predicate == "治法" else "other",
            source_chapter="D3_CPM_TCMT",
            source_text=f"{formula_name} 在 {group_name or '术语'} 维度关联 {term}。",
            confidence=0.84,
        )

    for row in _tsv_rows(source_root / "D7_CHP_Medicinal_properties.tsv"):
        chp_id = _clean(row.get("CHP_ID", ""))
        herb_name = chp_names.get(chp_id)
        prop = _clean(row.get("Medicinal_properties", ""))
        prop_class = _clean(row.get("Class", ""))
        if chp_id not in referenced_chp_ids or not herb_name or not prop:
            continue
        predicate = "药性特征"
        if "flavor" in prop_class.lower():
            predicate = "药味"
        elif "nature" in prop_class.lower():
            predicate = "药性"
        elif "channel" in prop_class.lower():
            predicate = "归经"
        emitter.add(
            subject=herb_name,
            predicate=predicate,
            obj=prop,
            subject_type="herb",
            object_type="property",
            source_chapter="D7_CHP_Medicinal_properties",
            source_text=f"{herb_name} 的 {prop_class or '药性属性'} 为 {prop}。",
            confidence=0.9,
        )

    for row in _tsv_rows(source_root / "D8_CHP_PO.tsv"):
        chp_id = _clean(row.get("CHP_ID", ""))
        herb_name = chp_names.get(chp_id)
        species_name = _clean(row.get("species_name", ""))
        if chp_id not in referenced_chp_ids or not herb_name or not species_name:
            continue
        emitter.add(
            subject=herb_name,
            predicate="药材基源",
            obj=species_name,
            subject_type="herb",
            object_type="origin",
            source_chapter="D8_CHP_PO",
            source_text=f"{herb_name} 的基源物种为 {species_name}。",
            confidence=0.9,
        )

    for row in _tsv_rows(source_root / "D9_CHP_InChIKey.tsv"):
        chp_id = _clean(row.get("CHP_ID", ""))
        herb_name = chp_names.get(chp_id)
        inchikey = _clean(row.get("InChIKey", ""))
        if chp_id not in referenced_chp_ids or not herb_name or not inchikey:
            continue
        reachable_inchikeys.add(inchikey)
        emitter.add(
            subject=herb_name,
            predicate="含有成分",
            obj=inchikey,
            subject_type="herb",
            object_type="ingredient",
            source_chapter="D9_CHP_InChIKey",
            source_text=f"{herb_name} 关联成分 InChIKey={inchikey}。",
            confidence=0.82,
        )

    for row in _tsv_rows(source_root / "D13_InChIKey_EntrezID.tsv"):
        inchikey = _clean(row.get("InChIKey", ""))
        entrez_id = _clean(row.get("EntrezID", ""))
        gene_symbol = gene_symbols.get(entrez_id) or entrez_id
        if inchikey not in reachable_inchikeys or not gene_symbol:
            continue
        emitter.add(
            subject=inchikey,
            predicate="作用靶点",
            obj=gene_symbol,
            subject_type="ingredient",
            object_type="gene",
            source_chapter="D13_InChIKey_EntrezID",
            source_text=f"成分 {inchikey} 关联靶点 {gene_symbol}（EntrezID={entrez_id}）。",
            confidence=0.8,
        )

    icd_to_cui: dict[str, set[str]] = {}
    for row in _tsv_rows(source_root / "D19_ICD11_CUI.tsv"):
        icd_code = _clean(row.get("ICD11_code", ""))
        cui = _clean(row.get("CUI", ""))
        if icd_code in referenced_icd_codes and cui:
            icd_to_cui.setdefault(icd_code, set()).add(cui)

    cui_to_genes: dict[str, set[str]] = {}
    for row in _tsv_rows(source_root / "D22_CUI_targets.tsv"):
        cui = _clean(row.get("CUI", ""))
        gene_symbol = gene_symbols.get(_clean(row.get("EntrezID", "")))
        if cui and gene_symbol:
            cui_to_genes.setdefault(cui, set()).add(gene_symbol)

    icd_to_mesh: dict[str, set[str]] = {}
    icd_to_doid: dict[str, set[str]] = {}
    mesh_to_genes: dict[str, set[str]] = {}
    doid_to_genes: dict[str, set[str]] = {}
    if include_mesh_doid_bridges:
        for row in _tsv_rows(source_root / "D20_ICD11_MeSH.tsv"):
            icd_value = _clean(row.get("ICD11_code", ""))
            mesh = _clean(row.get("MeSH", ""))
            if icd_value in referenced_icd_codes and mesh:
                icd_to_mesh.setdefault(icd_value, set()).add(mesh)
        for row in _tsv_rows(source_root / "D21_ICD11_DOID.tsv"):
            icd_value = _clean(row.get("ICD11_code", ""))
            doid = _clean(row.get("DOID", ""))
            if icd_value in referenced_icd_codes and doid:
                icd_to_doid.setdefault(icd_value, set()).add(doid)
        for row in _tsv_rows(source_root / "D23_MeSH_targets.tsv"):
            mesh = _clean(row.get("MeSH", ""))
            gene_symbol = gene_symbols.get(_clean(row.get("EntrezID", "")))
            if mesh and gene_symbol:
                mesh_to_genes.setdefault(mesh, set()).add(gene_symbol)
        for row in _tsv_rows(source_root / "D24_DOID_targets.tsv"):
            doid = _clean(row.get("DOID", ""))
            gene_symbol = gene_symbols.get(_clean(row.get("EntrezID", "")))
            if doid and gene_symbol:
                doid_to_genes.setdefault(doid, set()).add(gene_symbol)

    for icd_code in sorted(referenced_icd_codes):
        disease_name = icd_names.get(icd_code) or icd_code
        for cui in sorted(icd_to_cui.get(icd_code, set())):
            for gene_symbol in sorted(cui_to_genes.get(cui, set())):
                emitter.add(
                    subject=disease_name,
                    predicate="关联靶点",
                    obj=gene_symbol,
                    subject_type="disease",
                    object_type="gene",
                    source_chapter="D19_D22_ICD11_target_bridge",
                    source_text=f"{disease_name} 通过 CUI={cui} 关联靶点 {gene_symbol}。",
                    confidence=0.74,
                )
        if include_mesh_doid_bridges:
            for mesh in sorted(icd_to_mesh.get(icd_code, set())):
                for gene_symbol in sorted(mesh_to_genes.get(mesh, set())):
                    emitter.add(
                        subject=disease_name,
                        predicate="关联靶点",
                        obj=gene_symbol,
                        subject_type="disease",
                        object_type="gene",
                        source_chapter="D20_D23_ICD11_target_bridge",
                        source_text=f"{disease_name} 通过 MeSH={mesh} 关联靶点 {gene_symbol}。",
                        confidence=0.74,
                    )
            for doid in sorted(icd_to_doid.get(icd_code, set())):
                for gene_symbol in sorted(doid_to_genes.get(doid, set())):
                    emitter.add(
                        subject=disease_name,
                        predicate="关联靶点",
                        obj=gene_symbol,
                        subject_type="disease",
                        object_type="gene",
                        source_chapter="D21_D24_ICD11_target_bridge",
                        source_text=f"{disease_name} 通过 DOID={doid} 关联靶点 {gene_symbol}。",
                        confidence=0.74,
                    )

    manifest = {
        "source_root": str(source_root),
        "source_book": SOURCE_BOOK,
        "include_mesh_doid_bridges": include_mesh_doid_bridges,
        "facts": emitter.edge_count,
        "evidence": emitter.evidence_count,
        "chapters": emitter.by_chapter,
        "referenced_herbs": len(referenced_chp_ids),
        "referenced_diseases": len(referenced_icd_codes),
        "reachable_ingredients": len(reachable_inchikeys),
    }
    return emitter.facts, emitter.evidence, manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert TCM-MKG TSV exports into runtime-compatible graph artifacts.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--graph-output", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_GRAPH_PATH.with_suffix(".manifest.json"))
    parser.add_argument("--include-mesh-doid-bridges", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    facts, evidence, manifest = build_tcm_mkg_graph(
        args.source_root,
        include_mesh_doid_bridges=args.include_mesh_doid_bridges,
    )
    graph_count = _write_jsonl(args.graph_output, facts)
    evidence_count = _write_jsonl(args.evidence_output, evidence)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(
            {
                **manifest,
                "graph_output": str(args.graph_output),
                "evidence_output": str(args.evidence_output),
                "written_graph_rows": graph_count,
                "written_evidence_rows": evidence_count,
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
