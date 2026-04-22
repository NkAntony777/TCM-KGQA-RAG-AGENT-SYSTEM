from __future__ import annotations

import argparse
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_INPUT = BACKEND_ROOT / "eval" / "TCM-PA" / "TCMEval-PA.xlsx"
DEFAULT_OUTPUT = BACKEND_ROOT / "eval" / "datasets" / "external" / "tcmeval_pa_seed_80.json"
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OPTION_RE = re.compile(r"([A-Z])[\.\:]\s*(.+)")


def _read_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    shared: list[str] = []
    for si in root:
        text = "".join(node.text or "" for node in si.iter(f"{XML_NS}t"))
        shared.append(text)
    return shared


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    inline = cell.find(f"{XML_NS}is")
    if inline is not None:
        return "".join(node.text or "" for node in inline.iter(f"{XML_NS}t"))
    raw = cell.find(f"{XML_NS}v")
    if raw is None:
        return ""
    text = raw.text or ""
    if cell_type == "s":
        try:
            return shared[int(text)]
        except Exception:
            return text
    return text


def _xlsx_rows(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as zf:
        shared = _read_shared_strings(zf)
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    sheet_data = sheet.find(f"{XML_NS}sheetData")
    if sheet_data is None:
        return []

    rows = list(sheet_data)
    if not rows:
        return []
    headers = [_cell_value(cell, shared).strip() for cell in rows[0]]
    output: list[dict[str, str]] = []
    for row in rows[1:]:
        values = [_cell_value(cell, shared).strip() for cell in row]
        item = {headers[index]: values[index] if index < len(values) else "" for index in range(len(headers))}
        output.append(item)
    return output


def _option_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in str(value or "").splitlines():
        text = line.strip()
        if not text:
            continue
        match = OPTION_RE.match(text)
        if match:
            mapping[match.group(1)] = match.group(2).strip()
    return mapping


def _expand_answer_letters(value: str) -> list[str]:
    letters = [ch for ch in str(value or "").upper() if "A" <= ch <= "Z"]
    if not letters:
        return []
    return letters


def _build_query(question: str, options: str) -> str:
    return (
        "请回答下面的中医处方审核或中药学选择题。"
        "可以先简要解释，再明确给出最终选项。\n"
        f"题目：{question}\n"
        f"选项：\n{options}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a paper-facing end-to-end eval dataset from TCMEval-PA.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--per-category", type=int, default=12)
    args = parser.parse_args()

    rows = [row for row in _xlsx_rows(args.input) if isinstance(row, dict)]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("Category", "")).strip() or "uncategorized"].append(row)

    rng = random.Random(int(args.seed))
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()
    for category in sorted(grouped):
        bucket = grouped[category]
        picked = (
            bucket
            if len(bucket) <= max(1, int(args.per_category))
            else rng.sample(bucket, max(1, int(args.per_category)))
        )
        for row in picked:
            row_id = str(row.get("ID", "")).strip()
            if row_id and row_id not in selected_ids:
                selected_ids.add(row_id)
                selected.append(row)

    if len(selected) < max(1, int(args.limit)):
        remaining = [row for row in rows if str(row.get("ID", "")).strip() not in selected_ids]
        if remaining:
            need = min(len(remaining), max(0, int(args.limit) - len(selected)))
            for row in rng.sample(remaining, need):
                row_id = str(row.get("ID", "")).strip()
                if row_id and row_id not in selected_ids:
                    selected_ids.add(row_id)
                    selected.append(row)

    if len(selected) > max(1, int(args.limit)):
        selected = rng.sample(selected, max(1, int(args.limit)))

    cases: list[dict[str, object]] = []
    for row in selected:
        qid = str(row.get("ID", "")).strip()
        question = str(row.get("Question", "")).strip()
        options = str(row.get("Candidate Answers", "")).strip()
        answer = str(row.get("Answer", "")).strip().upper()
        category = str(row.get("Category", "")).strip() or "tcmeval_pa"
        if not qid or not question or not answer:
            continue
        option_mapping = _option_map(options)
        letters = _expand_answer_letters(answer)
        expected = [option_mapping[letter] for letter in letters if letter in option_mapping]
        answer_letters = ["".join(letters)] if letters else []
        cases.append(
            {
                "id": f"tcmpa_{qid}",
                "category": f"tcmeval_pa_{category}",
                "query": _build_query(question, options),
                "answer_contains_any": expected,
                "answer_option_letters_any": answer_letters,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"tcmeval_pa_cases={len(cases)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
