from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_INPUT = BACKEND_ROOT / "eval" / "TCM-SDT" / "Train_TCM_Data_v1.json"
DEFAULT_OUTPUT = BACKEND_ROOT / "eval" / "datasets" / "external" / "tcmeval_sdt_train_full.json"


def _split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").replace("；", ";").split(";") if part.strip()]


def _option_texts(option_field: str, answers: list[str]) -> list[str]:
    mapping: dict[str, str] = {}
    for piece in _split_semicolon(option_field):
        if ":" in piece:
            key, text = piece.split(":", 1)
            mapping[key.strip().upper()] = text.strip()
    output: list[str] = []
    for answer in answers:
        value = mapping.get(answer.strip().upper())
        if value:
            output.append(value)
    return output


def _compose_choice_query(clinical_data: str, stem: str, options: str) -> str:
    return (
        "请根据以下中医病例回答选择题。"
        "请先给出简短判断，再明确写出最终选项字母。\n"
        f"病例：{clinical_data}\n"
        f"题目：{stem}\n"
        f"选项：{options}"
    )


def _build_case(
    *,
    case_id: str,
    category: str,
    clinical_data: str,
    stem: str,
    option_field: str,
    answer_field: str,
    include_option_letters: bool,
) -> dict[str, object] | None:
    answer_letters = [part.strip().upper() for part in _split_semicolon(answer_field)]
    if not clinical_data or not option_field or not answer_letters:
        return None
    answer_texts = _option_texts(option_field, answer_letters)
    item: dict[str, object] = {
        "id": case_id,
        "category": category,
        "query": _compose_choice_query(clinical_data, stem, option_field),
        "answer_contains_any": answer_texts,
    }
    if include_option_letters:
        item["answer_option_letters_any"] = ["".join(answer_letters)]
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a paper-facing multiple-choice eval dataset from TCMEval-SDT.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--case-limit", type=int, default=200)
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=["pathogenesis", "syndrome"],
        default=["pathogenesis", "syndrome"],
    )
    parser.add_argument(
        "--include-option-letters",
        action="store_true",
        help="When enabled, require the final answer to explicitly contain the multiple-choice option letters.",
    )
    args = parser.parse_args()

    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("tcmeval_sdt_input_must_be_list")

    labeled_rows = [row for row in rows if isinstance(row, dict) and str(row.get("Clinical Data", "")).strip()]
    rng = random.Random(int(args.seed))
    selected = (
        rng.sample(labeled_rows, min(len(labeled_rows), max(1, int(args.case_limit))))
        if labeled_rows
        else []
    )

    cases: list[dict[str, object]] = []
    for index, row in enumerate(selected, start=1):
        base_case_id = str(row.get("Medical Record ID", "")).strip() or f"sdt_{index:03d}"
        clinical_data = str(row.get("Clinical Data", "")).strip()

        if "pathogenesis" in args.tasks:
            item = _build_case(
                case_id=f"{base_case_id}_pathogenesis",
                category="tcmeval_sdt_pathogenesis",
                clinical_data=clinical_data,
                stem="该病例的核心中医病机是下列哪项或哪几项？",
                option_field=str(row.get("Options of TCM Pathogenesis", "")).strip(),
                answer_field=str(row.get("Answers of TCM Pathogenesis", "")).strip(),
                include_option_letters=bool(args.include_option_letters),
            )
            if item is not None:
                cases.append(item)

        if "syndrome" in args.tasks:
            item = _build_case(
                case_id=f"{base_case_id}_syndrome",
                category="tcmeval_sdt_syndrome",
                clinical_data=clinical_data,
                stem="该病例的核心证候或辨证结论是下列哪项或哪几项？",
                option_field=str(row.get("Options of TCM Syndrome", "")).strip(),
                answer_field=str(row.get("Answers of TCM Syndrome", "")).strip(),
                include_option_letters=bool(args.include_option_letters),
            )
            if item is not None:
                cases.append(item)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"tcmeval_sdt_cases={len(cases)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
