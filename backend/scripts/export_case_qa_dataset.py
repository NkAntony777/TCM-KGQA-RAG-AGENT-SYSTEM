from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path


DEFAULT_DB_PATH = Path(r"E:\tcm_vector_db")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "services" / "retrieval_service" / "data" / "case_qa_export"
CASE_COLLECTION_PREFIX = "tcm_shard_"

CASE_STYLE_MARKERS = ("基本信息", "主诉", "现病史", "体格检查", "年龄", "性别", "舌", "脉")
SYMPTOM_MARKERS = ("疼", "痛", "热", "寒", "汗", "咳", "喘", "胀", "满", "痒", "吐", "泻", "烦", "渴", "眩")
FORMULA_SUFFIXES = ("丸", "散", "汤", "饮", "膏", "丹", "方", "颗粒", "胶囊")
QUESTION_SPLIT_PATTERN = re.compile(r"[，,。；;：:\s]+")


def _clean(text: object) -> str:
    return str(text or "").replace("\ufeff", "").strip()


def _open_sqlite_readonly(sqlite_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)


def _is_case_style_text(text: str) -> bool:
    hits = sum(1 for marker in CASE_STYLE_MARKERS if marker in text)
    return hits >= 2


def _classify_question(question: str, answer: str) -> str:
    q = _clean(question)
    a = _clean(answer)
    if _is_case_style_text(q) or _is_case_style_text(a):
        return "case_style"
    if any(keyword in q for keyword in ("出处", "出自", "原文", "哪本书", "古籍")):
        return "origin"
    if any(keyword in q for keyword in ("组成", "配伍", "由什么组成", "哪些药")):
        return "composition"
    if any(keyword in q for keyword in ("功效", "作用", "治法", "归经", "性味")):
        return "efficacy"
    if any(keyword in q for keyword in ("主治", "适应", "治什么", "证候", "症状")):
        return "indication"
    if any(keyword in q for keyword in ("是什么", "为什么", "如何", "怎样", "怎么")):
        return "definition_or_explanation"
    return "generic_qa"


def _extract_formula_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,16}", text or ""):
        if token.endswith(FORMULA_SUFFIXES):
            if token not in candidates:
                candidates.append(token)
    return candidates[:8]


def _extract_keywords(text: str) -> list[str]:
    keywords: list[str] = []
    for part in QUESTION_SPLIT_PATTERN.split(_clean(text)):
        token = _clean(part)
        if len(token) < 2:
            continue
        if token in keywords:
            continue
        keywords.append(token)
    return keywords[:24]


def _extract_symptom_like_terms(text: str) -> list[str]:
    results: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,8}", text or ""):
        if any(marker in token for marker in SYMPTOM_MARKERS):
            if token not in results:
                results.append(token)
    return results[:12]


def _build_search_text(*, question: str, answer: str, question_type: str, formulas: list[str], keywords: list[str], symptom_terms: list[str]) -> str:
    lines = [
        f"问题类型：{question_type}",
        f"问题：{question}",
        f"答案：{answer}",
    ]
    if formulas:
        lines.append(f"方剂候选：{'；'.join(formulas)}")
    if symptom_terms:
        lines.append(f"症状词：{'；'.join(symptom_terms)}")
    if keywords:
        lines.append(f"关键词：{'；'.join(keywords[:12])}")
    return "\n".join(lines)


def export_case_qa_dataset(db_root: Path, output_dir: Path) -> dict[str, object]:
    sqlite_path = db_root / "chroma.sqlite3"
    if not sqlite_path.exists():
        raise FileNotFoundError(f"case_qa_sqlite_not_found: {sqlite_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "case_qa_records.jsonl"
    csv_path = output_dir / "case_qa_records.csv"
    manifest_path = output_dir / "case_qa_manifest.json"

    conn = _open_sqlite_readonly(sqlite_path)
    try:
        sql = """
        SELECT
            c.name AS collection_name,
            e.embedding_id,
            MAX(CASE WHEN em.key = 'chroma:document' THEN em.string_value END) AS question,
            MAX(CASE WHEN em.key = 'answer' THEN em.string_value END) AS answer
        FROM collections c
        JOIN segments s ON s.collection = c.id AND s.scope = 'METADATA'
        JOIN embeddings e ON e.segment_id = s.id
        LEFT JOIN embedding_metadata em ON em.id = e.id
        WHERE c.name LIKE ?
        GROUP BY c.name, e.embedding_id
        ORDER BY c.name, e.embedding_id
        """
        rows = conn.execute(sql, (f"{CASE_COLLECTION_PREFIX}%",)).fetchall()
    finally:
        conn.close()

    type_counter: Counter[str] = Counter()
    collection_counter: Counter[str] = Counter()
    exported = 0

    with (
        jsonl_path.open("w", encoding="utf-8") as jsonl_file,
        csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file,
    ):
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "record_id",
                "collection",
                "embedding_id",
                "question_type",
                "is_case_style",
                "question",
                "answer",
                "formula_candidates",
                "symptom_terms",
                "keywords",
                "search_text",
            ],
        )
        writer.writeheader()

        for collection_name, embedding_id, question, answer in rows:
            question_text = _clean(question)
            answer_text = _clean(answer)
            if not question_text or not answer_text:
                continue

            formulas = _extract_formula_candidates(" ".join([question_text, answer_text]))
            symptom_terms = _extract_symptom_like_terms(" ".join([question_text, answer_text]))
            keywords = _extract_keywords(question_text)
            question_type = _classify_question(question_text, answer_text)
            is_case_style = _is_case_style_text(question_text) or _is_case_style_text(answer_text)
            record = {
                "record_id": f"{collection_name}::{embedding_id}",
                "collection": _clean(collection_name),
                "embedding_id": _clean(embedding_id),
                "question_type": question_type,
                "is_case_style": is_case_style,
                "question": question_text,
                "answer": answer_text,
                "formula_candidates": formulas,
                "symptom_terms": symptom_terms,
                "keywords": keywords,
                "search_text": _build_search_text(
                    question=question_text,
                    answer=answer_text,
                    question_type=question_type,
                    formulas=formulas,
                    keywords=keywords,
                    symptom_terms=symptom_terms,
                ),
            }
            jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            writer.writerow(
                {
                    **record,
                    "formula_candidates": " | ".join(formulas),
                    "symptom_terms": " | ".join(symptom_terms),
                    "keywords": " | ".join(keywords),
                }
            )
            exported += 1
            type_counter[question_type] += 1
            collection_counter[_clean(collection_name)] += 1

    manifest = {
        "db_root": str(db_root),
        "sqlite_path": str(sqlite_path),
        "output_dir": str(output_dir),
        "jsonl": str(jsonl_path),
        "csv": str(csv_path),
        "total_records": exported,
        "collections": dict(collection_counter),
        "question_types": dict(type_counter),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export local case QA Chroma store into structured files for vector-free retrieval.")
    parser.add_argument("--db-root", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_case_qa_dataset(args.db_root, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
