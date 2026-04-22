from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "eval" / "datasets" / "external"
TOKEN_SPLIT_RE = re.compile(r"[；;，,、/\n|\t]+")


def _load_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "records", "examples", "dataset"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("unsupported_json_shape")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        item = json.loads(text)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _load_xlsx(path: Path, sheet_name: str | None) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover - env dependent
        raise RuntimeError("pandas_not_available") from exc
    try:
        frame = pd.read_excel(path, sheet_name=sheet_name or 0)
    except ImportError as exc:  # pragma: no cover - env dependent
        raise RuntimeError("openpyxl_required_for_xlsx") from exc
    return frame.fillna("").to_dict(orient="records")


def _load_rows(path: Path, input_format: str, sheet_name: str | None) -> list[dict[str, Any]]:
    if input_format == "json":
        return _load_json(path)
    if input_format == "jsonl":
        return _load_jsonl(path)
    if input_format == "xlsx":
        return _load_xlsx(path, sheet_name)
    raise ValueError(f"unsupported_input_format:{input_format}")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _listify_options(value: Any, separator: str) -> list[str]:
    if isinstance(value, list):
        return [_string(item) for item in value if _string(item)]
    text = _string(value)
    if not text:
        return []
    if separator:
        return [part.strip() for part in text.split(separator) if part.strip()]
    return [part.strip() for part in text.splitlines() if part.strip()]


def _normalize_token(value: str) -> str:
    return "".join(str(value or "").split()).strip()


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_token(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(value.strip())
    return output


def _candidate_tokens(answer: str, analysis: str) -> list[str]:
    tokens: list[str] = []
    answer_text = _string(answer)
    analysis_text = _string(analysis)

    if answer_text:
        tokens.append(answer_text)
        if len(answer_text) <= 24:
            tokens.extend(part.strip() for part in TOKEN_SPLIT_RE.split(answer_text) if len(_normalize_token(part)) >= 2)

    if analysis_text and len(answer_text) <= 8:
        for part in TOKEN_SPLIT_RE.split(analysis_text):
            normalized = _normalize_token(part)
            if 2 <= len(normalized) <= 24:
                tokens.append(part.strip())

    return _unique(tokens[:12])


def _resolve_profile_fields(profile: str, args: argparse.Namespace) -> dict[str, str]:
    if profile == "tcmeval_pa":
        return {
            "id_field": args.id_field or "ID",
            "category_field": args.category_field or "Category",
            "question_field": args.question_field or "Question",
            "answer_field": args.answer_field or "Answer",
            "analysis_field": args.analysis_field or "Explanation",
            "options_field": args.options_field or "Candidate Answers",
        }
    return {
        "id_field": args.id_field or "id",
        "category_field": args.category_field or "category",
        "question_field": args.question_field or "question",
        "answer_field": args.answer_field or "answer",
        "analysis_field": args.analysis_field or "",
        "options_field": args.options_field or "",
    }


def _compose_query(question: str, options: list[str]) -> str:
    if not options:
        return question
    return question.rstrip() + "\n选项：\n" + "\n".join(options)


def _build_case(
    row: dict[str, Any],
    *,
    index: int,
    fields: dict[str, str],
    options_separator: str,
) -> dict[str, Any] | None:
    question = _string(row.get(fields["question_field"]))
    answer = _string(row.get(fields["answer_field"]))
    analysis = _string(row.get(fields["analysis_field"])) if fields["analysis_field"] else ""
    options = _listify_options(row.get(fields["options_field"]), options_separator) if fields["options_field"] else []

    if not question or not answer:
        return None

    case_id = _string(row.get(fields["id_field"])) or f"external_{index:04d}"
    category = _string(row.get(fields["category_field"])) or "external_benchmark"
    answer_tokens = _candidate_tokens(answer, analysis)
    if not answer_tokens:
        answer_tokens = [answer]

    item: dict[str, Any] = {
        "id": case_id,
        "category": category,
        "query": _compose_query(question, options),
        "answer_contains_any": answer_tokens,
        "meta": {
            "raw_question": question,
            "raw_answer": answer,
            "raw_analysis": analysis,
            "raw_options": options,
            "draft_source": "external_benchmark_import",
            "needs_manual_review": True,
        },
    }
    return item


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a draft end-to-end QA evaluation dataset from an external TCM benchmark."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-format", choices=["json", "jsonl", "xlsx"], required=True)
    parser.add_argument("--profile", choices=["generic", "tcmeval_pa"], default="generic")
    parser.add_argument("--sheet-name", default=None)
    parser.add_argument("--id-field", default="")
    parser.add_argument("--category-field", default="")
    parser.add_argument("--question-field", default="")
    parser.add_argument("--answer-field", default="")
    parser.add_argument("--analysis-field", default="")
    parser.add_argument("--options-field", default="")
    parser.add_argument("--options-separator", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = _load_rows(args.input, args.input_format, args.sheet_name)
    if args.limit > 0:
        rows = rows[: max(1, int(args.limit))]

    fields = _resolve_profile_fields(args.profile, args)
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        item = _build_case(
            row,
            index=index,
            fields=fields,
            options_separator=str(args.options_separator or ""),
        )
        if item is not None:
            cases.append(item)

    payload = {
        "meta": {
            "source_file": str(args.input),
            "input_format": args.input_format,
            "profile": args.profile,
            "sheet_name": args.sheet_name,
            "field_mapping": fields,
            "count": len(cases),
            "note": "This is a draft dataset for run_end_to_end_qa_paper_eval.py and requires manual review before formal reporting.",
        },
        "cases": cases,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"draft_external_dataset_cases={len(cases)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
