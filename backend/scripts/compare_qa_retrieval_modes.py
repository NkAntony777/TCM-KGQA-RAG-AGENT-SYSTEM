from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.retrieval_service.engine import get_retrieval_engine
from services.retrieval_service.qa_structured_store import StructuredQAIndex, StructuredQAIndexSettings


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    mode: str
    query: str
    expected_keywords: tuple[str, ...]


DEFAULT_INDEX_PATH = BACKEND_ROOT / "storage" / "qa_structured_index.sqlite"
DEFAULT_QA_INPUT = BACKEND_ROOT / "services" / "retrieval_service" / "data" / "case_qa_clean" / "qa_fts_ready.jsonl"
DEFAULT_CASE_INPUT = BACKEND_ROOT / "services" / "retrieval_service" / "data" / "case_qa_clean" / "case_fts_ready.jsonl"
DEFAULT_OUTPUT_PATH = BACKEND_ROOT / "storage" / "qa_retrieval_compare_report.json"


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        case_id="origin_alias",
        category="baseline",
        mode="qa",
        query="六味地黄丸 出处 原文",
        expected_keywords=("地黄丸", "小儿药证直诀"),
    ),
    EvalCase(
        case_id="formula_role",
        category="baseline",
        mode="qa",
        query="托里消毒饮中的金银花在方剂中起什么作用",
        expected_keywords=("托里消毒饮", "金银花"),
    ),
    EvalCase(
        case_id="generic_reason",
        category="baseline",
        mode="qa",
        query="为什么远行奔走时脚上会起泡",
        expected_keywords=("起泡", "摩擦"),
    ),
    EvalCase(
        case_id="case_liver",
        category="baseline",
        mode="case",
        query="女 45岁 口苦 胁痛 舌红 脉弦",
        expected_keywords=("口苦", "胁痛", "舌红", "脉弦"),
    ),
    EvalCase(
        case_id="case_digestive",
        category="baseline",
        mode="case",
        query="女 45岁 慢性胃炎 吞咽障碍 怕冷 舌苔黄 脉沉",
        expected_keywords=("慢性胃炎", "吞咽障碍", "怕冷", "脉沉"),
    ),
    EvalCase(
        case_id="case_pneumonia",
        category="baseline",
        mode="case",
        query="发热 咳喘 腺病毒肺炎 心力衰竭 舌红无苔 脉滑微数",
        expected_keywords=("腺病毒肺炎", "心力衰竭", "咳喘"),
    ),
]


def _structured_search(index: StructuredQAIndex, case: EvalCase, top_k: int) -> list[dict[str, Any]]:
    if case.mode == "case":
        return index.search_case(case.query, top_k=top_k)
    return index.search_qa(case.query, top_k=top_k)


def _vector_search(case: EvalCase, top_k: int, candidate_k: int) -> dict[str, Any]:
    engine = get_retrieval_engine()
    return engine.search_case_qa(case.query, top_k=top_k, candidate_k=candidate_k)


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(row.get("question", "") or ""),
            str(row.get("answer", "") or ""),
            str(row.get("document", "") or ""),
            str(row.get("text", "") or ""),
            str(row.get("formula_text", "") or ""),
            str(row.get("symptom_text", "") or ""),
            str(row.get("syndrome_text", "") or ""),
        ]
    )


def _hit_score(rows: list[dict[str, Any]], expected_keywords: tuple[str, ...], *, top_k: int) -> dict[str, Any]:
    joined_rows = rows[:top_k]
    hits: list[dict[str, Any]] = []
    matched_count = 0
    for idx, row in enumerate(joined_rows, start=1):
        haystack = _row_text(row)
        matched = [keyword for keyword in expected_keywords if keyword and keyword in haystack]
        if matched:
            matched_count += len(matched)
        hits.append(
            {
                "rank": idx,
                "matched_keywords": matched,
                "coverage": round(len(matched) / max(1, len(expected_keywords)), 4),
            }
        )
    all_text = "\n".join(_row_text(row) for row in joined_rows)
    union_hits = [keyword for keyword in expected_keywords if keyword and keyword in all_text]
    return {
        "top_k": top_k,
        "matched_keywords_any": union_hits,
        "coverage_any": round(len(union_hits) / max(1, len(expected_keywords)), 4),
        "row_hits": hits,
        "matched_count_total": matched_count,
    }


def _trim_rows(rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for row in rows[:top_k]:
        trimmed.append(
            {
                "record_id": row.get("record_id") or row.get("embedding_id") or row.get("chunk_id"),
                "bucket": row.get("bucket"),
                "question_type": row.get("question_type"),
                "collection": row.get("collection"),
                "question": row.get("question") or row.get("document"),
                "answer": row.get("answer") or row.get("text"),
                "formula_text": row.get("formula_text"),
                "symptom_text": row.get("symptom_text"),
                "syndrome_text": row.get("syndrome_text"),
                "score": row.get("score"),
                "rerank_score": row.get("rerank_score"),
                "rank_score": row.get("rank_score"),
            }
        )
    return trimmed


def _load_eval_cases(cases_path: Path | None) -> list[EvalCase]:
    if cases_path is None:
        return list(EVAL_CASES)
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cases.append(
            EvalCase(
                case_id=str(item.get("case_id", "")).strip(),
                category=str(item.get("category", "custom")).strip() or "custom",
                mode=str(item.get("mode", "qa")).strip() or "qa",
                query=str(item.get("query", "")).strip(),
                expected_keywords=tuple(str(part).strip() for part in item.get("expected_keywords", []) if str(part).strip()),
            )
        )
    return [case for case in cases if case.case_id and case.query and case.expected_keywords]


def run_compare(
    *,
    index_path: Path,
    qa_input_path: Path,
    case_input_path: Path,
    top_k: int,
    candidate_k: int,
    eval_cases: list[EvalCase] | None = None,
) -> dict[str, Any]:
    index = StructuredQAIndex(
        StructuredQAIndexSettings(
            index_path=index_path,
            qa_input_path=qa_input_path,
            case_input_path=case_input_path,
        )
    )
    eval_cases = list(eval_cases or EVAL_CASES)
    engine = get_retrieval_engine()
    vector_health = engine.health()
    vector_available = bool(vector_health.get("embedding_configured")) and bool(vector_health.get("case_qa_configured"))

    cases_report: list[dict[str, Any]] = []
    summary = {
        "structured_cases": 0,
        "structured_hit_cases": 0,
        "vector_cases": 0,
        "vector_hit_cases": 0,
    }
    category_summary: dict[str, dict[str, Any]] = {}

    for case in eval_cases:
        structured_rows = _structured_search(index, case, top_k=top_k)
        structured_score = _hit_score(structured_rows, case.expected_keywords, top_k=top_k)
        summary["structured_cases"] += 1
        if structured_score["matched_keywords_any"]:
            summary["structured_hit_cases"] += 1
        category_block = category_summary.setdefault(
            case.category,
            {
                "cases": 0,
                "structured_hit_cases": 0,
                "vector_hit_cases": 0,
            },
        )
        category_block["cases"] += 1
        if structured_score["matched_keywords_any"]:
            category_block["structured_hit_cases"] += 1

        vector_block: dict[str, Any]
        if vector_available:
            vector_data = _vector_search(case, top_k=top_k, candidate_k=candidate_k)
            vector_rows = [item for item in vector_data.get("chunks", []) if isinstance(item, dict)]
            vector_score = _hit_score(vector_rows, case.expected_keywords, top_k=top_k)
            summary["vector_cases"] += 1
            if vector_score["matched_keywords_any"]:
                summary["vector_hit_cases"] += 1
                category_block["vector_hit_cases"] += 1
            vector_block = {
                "available": True,
                "warnings": vector_data.get("warnings", []),
                "retrieval_mode": vector_data.get("retrieval_mode"),
                "score": vector_score,
                "rows": _trim_rows(vector_rows, top_k=top_k),
            }
        else:
            vector_block = {
                "available": False,
                "reason": {
                    "embedding_configured": vector_health.get("embedding_configured"),
                    "case_qa_configured": vector_health.get("case_qa_configured"),
                },
            }

        cases_report.append(
            {
                "case": asdict(case),
                "structured": {
                    "score": structured_score,
                    "rows": _trim_rows(structured_rows, top_k=top_k),
                },
                "vector": vector_block,
            }
        )

    return {
        "settings": {
            "index_path": str(index_path),
            "qa_input_path": str(qa_input_path),
            "case_input_path": str(case_input_path),
            "top_k": top_k,
            "candidate_k": candidate_k,
        },
        "health": {
            "structured": index.health(),
            "vector": vector_health,
        },
        "summary": {
            **summary,
            "structured_hit_rate": round(summary["structured_hit_cases"] / max(1, summary["structured_cases"]), 4),
            "vector_hit_rate": round(summary["vector_hit_cases"] / max(1, summary["vector_cases"]), 4)
            if summary["vector_cases"]
            else None,
        },
        "category_summary": {
            key: {
                **value,
                "structured_hit_rate": round(value["structured_hit_cases"] / max(1, value["cases"]), 4),
                "vector_hit_rate": round(value["vector_hit_cases"] / max(1, value["cases"]), 4) if vector_available else None,
            }
            for key, value in category_summary.items()
        },
        "cases": cases_report,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare vector QA retrieval and structured non-vector QA retrieval.")
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--qa-input", type=Path, default=DEFAULT_QA_INPUT)
    parser.add_argument("--case-input", type=Path, default=DEFAULT_CASE_INPUT)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--cases-file", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_compare(
        index_path=args.index_path,
        qa_input_path=args.qa_input,
        case_input_path=args.case_input,
        top_k=max(1, int(args.top_k)),
        candidate_k=max(1, int(args.candidate_k)),
        eval_cases=_load_eval_cases(args.cases_file),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
