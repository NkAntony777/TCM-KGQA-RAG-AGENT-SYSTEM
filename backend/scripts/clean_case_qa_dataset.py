from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import TextIO


DEFAULT_INPUT = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "retrieval_service"
    / "data"
    / "case_qa_export"
    / "case_qa_records.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "retrieval_service"
    / "data"
    / "case_qa_clean"
)

CASE_STYLE_MARKERS = ("基本信息", "主诉", "现病史", "体格检查", "年龄", "性别", "舌", "脉")
SLOT_PATTERNS = {
    "age": [r"年龄[:：]\s*([0-9]{1,3})", r"(\d{1,3})岁"],
    "sex": [r"性别[:：]\s*(男|女)"],
    "chief_complaint": [r"主诉[:：]\s*([^。；;\n]+)"],
    "history": [r"现病史[:：]\s*([^。；;\n]+)"],
    "tongue": [r"舌(?:象)?[:：]?\s*([^。；;\n]+)"],
    "pulse": [r"脉(?:象)?[:：]?\s*([^。；;\n]+)"],
}
QUESTION_SPLIT_PATTERN = re.compile(r"[，,。；;：:\s]+")
FORMULA_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,16}(?:丸|散|汤|饮|膏|丹|方|颗粒|胶囊)")
SYNDROME_HINTS = ("证", "证候", "证型", "肝郁", "脾虚", "肾虚", "阴虚", "阳虚", "气滞", "血瘀", "痰湿")
SYMPTOM_HINTS = ("痛", "热", "寒", "汗", "咳", "喘", "胀", "满", "吐", "泻", "烦", "渴", "痒", "麻", "酸")


def _clean(value: object) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def _normalize_text(text: str) -> str:
    value = _clean(text)
    value = re.sub(r"\s+", " ", value)
    return value


def _hash_pair(question: str, answer: str) -> str:
    payload = f"{_normalize_text(question)}\n{_normalize_text(answer)}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _extract_slot(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean(match.group(1))
    return ""


def _extract_slots(question: str, answer: str) -> dict[str, str]:
    joined = f"{question}\n{answer}"
    return {name: _extract_slot(joined, patterns) for name, patterns in SLOT_PATTERNS.items()}


def _extract_keywords(text: str, *, limit: int = 20) -> list[str]:
    results: list[str] = []
    for piece in QUESTION_SPLIT_PATTERN.split(_normalize_text(text)):
        token = _clean(piece)
        if len(token) < 2 or token in results:
            continue
        results.append(token)
        if len(results) >= limit:
            break
    return results


def _extract_formula_candidates(text: str, *, limit: int = 8) -> list[str]:
    results: list[str] = []
    for token in FORMULA_PATTERN.findall(text or ""):
        if token not in results:
            results.append(token)
        if len(results) >= limit:
            break
    return results


def _extract_symptom_terms(text: str, *, limit: int = 10) -> list[str]:
    results: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,10}", text or ""):
        if not any(marker in token for marker in SYMPTOM_HINTS):
            continue
        if token not in results:
            results.append(token)
        if len(results) >= limit:
            break
    return results


def _extract_syndrome_terms(text: str, *, limit: int = 10) -> list[str]:
    results: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,12}", text or ""):
        if not any(marker in token for marker in SYNDROME_HINTS):
            continue
        if token not in results:
            results.append(token)
        if len(results) >= limit:
            break
    return results


def _is_case_style(question: str, answer: str, raw_flag: object) -> bool:
    if bool(raw_flag):
        return True
    joined = f"{question}\n{answer}"
    return sum(1 for marker in CASE_STYLE_MARKERS if marker in joined) >= 2


def _target_bucket(question_type: str, *, is_case_style: bool) -> str:
    if is_case_style:
        return "case_structured"
    if question_type == "origin":
        return "origin_qa"
    if question_type in {"composition", "efficacy", "indication"}:
        return "formula_qa"
    return "generic_qa"


def _build_case_search_text(record: dict[str, object]) -> str:
    lines = [
        f"类型：{record['bucket']}",
        f"问题：{record['question']}",
        f"答案：{record['answer']}",
    ]
    slots = record.get("slots", {})
    if isinstance(slots, dict):
        for key in ("age", "sex", "chief_complaint", "history", "tongue", "pulse"):
            value = _clean(slots.get(key))
            if value:
                lines.append(f"{key}：{value}")
    symptom_terms = record.get("symptom_terms", [])
    syndrome_terms = record.get("syndrome_terms", [])
    formula_candidates = record.get("formula_candidates", [])
    if symptom_terms:
        lines.append(f"症状词：{'；'.join(str(item) for item in symptom_terms)}")
    if syndrome_terms:
        lines.append(f"证候词：{'；'.join(str(item) for item in syndrome_terms)}")
    if formula_candidates:
        lines.append(f"方剂词：{'；'.join(str(item) for item in formula_candidates)}")
    return "\n".join(lines)


def _build_fts_search_text(record: dict[str, object]) -> str:
    lines = [
        f"类型：{record['bucket']}",
        f"子类：{record['question_type']}",
        f"问题：{record['question']}",
        f"答案：{record['answer']}",
    ]
    if record.get("formula_candidates"):
        lines.append(f"方剂候选：{'；'.join(str(item) for item in record['formula_candidates'])}")
    if record.get("keywords"):
        lines.append(f"关键词：{'；'.join(str(item) for item in record['keywords'])}")
    return "\n".join(lines)


def _open_writer(output_dir: Path, name: str) -> TextIO:
    return (output_dir / name).open("w", encoding="utf-8")


class DiskBackedDeduper:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA temp_store=FILE")
        self.conn.execute("CREATE TABLE IF NOT EXISTS seen_hashes (pair_hash TEXT PRIMARY KEY)")
        self.conn.commit()

    def add_if_new(self, pair_hash: str) -> bool:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO seen_hashes(pair_hash) VALUES (?)",
            (pair_hash,),
        )
        return int(cursor.rowcount or 0) > 0

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()


def clean_case_qa_dataset(input_path: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dedup_db_path = output_dir / "clean_case_qa_dedup.sqlite"
    writers = {
        "case_structured": _open_writer(output_dir, "case_structured.jsonl"),
        "origin_qa": _open_writer(output_dir, "origin_qa.jsonl"),
        "formula_qa": _open_writer(output_dir, "formula_qa.jsonl"),
        "generic_qa": _open_writer(output_dir, "generic_qa.jsonl"),
        "case_fts": _open_writer(output_dir, "case_fts_ready.jsonl"),
        "qa_fts": _open_writer(output_dir, "qa_fts_ready.jsonl"),
    }

    deduper = DiskBackedDeduper(dedup_db_path)
    bucket_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    duplicate_counter = 0
    total = 0

    try:
        with input_path.open("r", encoding="utf-8") as f:
            for line in f:
                payload = json.loads(line)
                question = _clean(payload.get("question"))
                answer = _clean(payload.get("answer"))
                if not question or not answer:
                    continue
                total += 1
                pair_hash = _hash_pair(question, answer)
                if not deduper.add_if_new(pair_hash):
                    duplicate_counter += 1
                    continue

                question_type = _clean(payload.get("question_type")) or "generic_qa"
                is_case_style = _is_case_style(question, answer, payload.get("is_case_style"))
                bucket = _target_bucket(question_type, is_case_style=is_case_style)
                formula_candidates = _extract_formula_candidates(f"{question}\n{answer}")
                symptom_terms = _extract_symptom_terms(f"{question}\n{answer}")
                syndrome_terms = _extract_syndrome_terms(f"{question}\n{answer}")
                keywords = _extract_keywords(question)
                slots = _extract_slots(question, answer) if is_case_style else {}

                record = {
                    "record_id": _clean(payload.get("record_id")),
                    "collection": _clean(payload.get("collection")),
                    "embedding_id": _clean(payload.get("embedding_id")),
                    "qa_pair_hash": pair_hash,
                    "bucket": bucket,
                    "question_type": question_type,
                    "is_case_style": is_case_style,
                    "question": question,
                    "answer": answer,
                    "formula_candidates": formula_candidates,
                    "symptom_terms": symptom_terms,
                    "syndrome_terms": syndrome_terms,
                    "keywords": keywords,
                    "slots": slots,
                }

                writers[bucket].write(json.dumps(record, ensure_ascii=False) + "\n")

                if bucket == "case_structured":
                    fts_ready = {
                        **record,
                        "search_text": _build_case_search_text(record),
                    }
                    writers["case_fts"].write(json.dumps(fts_ready, ensure_ascii=False) + "\n")
                else:
                    fts_ready = {
                        **record,
                        "search_text": _build_fts_search_text(record),
                    }
                    writers["qa_fts"].write(json.dumps(fts_ready, ensure_ascii=False) + "\n")

                bucket_counter[bucket] += 1
                type_counter[question_type] += 1
    finally:
        deduper.close()
        for writer in writers.values():
            writer.close()

    manifest = {
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "dedup_db_path": str(dedup_db_path),
        "total_input_records": total,
        "deduplicated_records": sum(bucket_counter.values()),
        "duplicate_records_skipped": duplicate_counter,
        "bucket_counts": dict(bucket_counter),
        "question_type_counts": dict(type_counter),
        "outputs": {
            "case_structured": str(output_dir / "case_structured.jsonl"),
            "origin_qa": str(output_dir / "origin_qa.jsonl"),
            "formula_qa": str(output_dir / "formula_qa.jsonl"),
            "generic_qa": str(output_dir / "generic_qa.jsonl"),
            "case_fts": str(output_dir / "case_fts_ready.jsonl"),
            "qa_fts": str(output_dir / "qa_fts_ready.jsonl"),
        },
    }
    (output_dir / "clean_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean and split exported case QA data for non-vector retrieval.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = clean_case_qa_dataset(args.input, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
