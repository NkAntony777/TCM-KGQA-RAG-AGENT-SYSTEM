from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import textwrap
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import get_settings
from scripts.tcm_triple_console import PipelineConfig, TCMTriplePipeline, _extract_json_block
from services.common.evidence_payloads import normalize_source_chapter_label


DEFAULT_DB_PATH = BACKEND_DIR / "services" / "graph_service" / "data" / "graph_runtime.db"
DEFAULT_OUTPUT_JSON = BACKEND_DIR / "eval" / "batch2_llm_adjudication_latest.json"
DEFAULT_OUTPUT_MD = BACKEND_DIR / "eval" / "batch2_llm_adjudication_latest.md"

BATCH2_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "predicate": "使用药材",
        "subject_type": "herb",
        "object_type": "herb",
        "label": "composition_herb_to_herb",
        "allowed_actions": ["delete", "retype", "keep"],
        "allowed_target_predicates": ["配伍禁忌", "关联术语", "属于范畴", "使用药材"],
        "rule_hint": "药到药通常不应继续挂在使用药材；若明显是配方列举、炮制原料、组成列举，应优先 delete 或 retype。",
    },
    {
        "predicate": "使用药材",
        "subject_type": "category",
        "object_type": "herb",
        "label": "composition_category_to_herb",
        "allowed_actions": ["delete", "retype", "keep"],
        "allowed_target_predicates": ["属于范畴", "关联术语", "使用药材"],
        "rule_hint": "分类条目列举药物通常不应继续挂在使用药材；若仍有知识价值，优先 retype 为属于范畴或关联术语。",
    },
)


@dataclass(frozen=True)
class CandidateRow:
    signature: str
    fact_id: str
    predicate: str
    subject: str
    object: str
    subject_type: str
    object_type: str
    source_book: str
    source_chapter: str
    source_text_preview: str
    confidence: float
    target_label: str


T = TypeVar("T")


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _make_pipeline() -> TCMTriplePipeline:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("llm_api_key_missing")
    return TCMTriplePipeline(
        PipelineConfig(
            books_dir=BACKEND_DIR,
            output_dir=BACKEND_DIR / "storage" / "triple_benchmark_lab",
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            request_delay=0.0,
            max_retries=1,
            parallel_workers=1,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use the existing triple-extraction LLM providers to adjudicate batch-2 likely-dirty candidates.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--sample-per-target", type=int, default=8)
    parser.add_argument("--max-batches", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--sampling-mode", choices=["top_confidence", "diverse_books"], default="diverse_books")
    parser.add_argument("--target-label", action="append", default=None, help="Limit adjudication to one or more target labels.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _fetch_candidates(
    conn: sqlite3.Connection,
    *,
    sample_per_target: int,
    sampling_mode: str,
    target_labels: set[str] | None,
) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for target in BATCH2_TARGETS:
        if target_labels and target["label"] not in target_labels:
            continue
        if sampling_mode == "diverse_books":
            query_rows = conn.execute(
                """
                WITH ranked AS (
                    SELECT
                        signature,
                        fact_id,
                        predicate,
                        subject,
                        object,
                        subject_type,
                        object_type,
                        source_book,
                        source_chapter,
                        best_source_text,
                        best_confidence,
                        ROW_NUMBER() OVER (
                            PARTITION BY source_book
                            ORDER BY best_confidence DESC, signature ASC
                        ) AS rn
                    FROM facts
                    WHERE predicate = ? AND subject_type = ? AND object_type = ?
                )
                SELECT
                    signature,
                    fact_id,
                    predicate,
                    subject,
                    object,
                    subject_type,
                    object_type,
                    source_book,
                    source_chapter,
                    best_source_text,
                    best_confidence
                FROM ranked
                WHERE rn = 1
                ORDER BY best_confidence DESC, source_book ASC, signature ASC
                LIMIT ?
                """,
                (
                    target["predicate"],
                    target["subject_type"],
                    target["object_type"],
                    max(1, int(sample_per_target)),
                ),
            ).fetchall()
        else:
            query_rows = conn.execute(
                """
                SELECT
                    signature,
                    fact_id,
                    predicate,
                    subject,
                    object,
                    subject_type,
                    object_type,
                    source_book,
                    source_chapter,
                    best_source_text,
                    best_confidence
                FROM facts
                WHERE predicate = ? AND subject_type = ? AND object_type = ?
                ORDER BY best_confidence DESC, source_book ASC, signature ASC
                LIMIT ?
                """,
                (
                    target["predicate"],
                    target["subject_type"],
                    target["object_type"],
                    max(1, int(sample_per_target)),
                ),
            ).fetchall()
        for row in query_rows:
            source_book = str(row["source_book"] or "").strip()
            rows.append(
                CandidateRow(
                    signature=str(row["signature"] or "").strip(),
                    fact_id=str(row["fact_id"] or "").strip(),
                    predicate=str(row["predicate"] or "").strip(),
                    subject=str(row["subject"] or "").strip(),
                    object=str(row["object"] or "").strip(),
                    subject_type=str(row["subject_type"] or "").strip(),
                    object_type=str(row["object_type"] or "").strip(),
                    source_book=source_book,
                    source_chapter=normalize_source_chapter_label(
                        source_book=source_book,
                        source_chapter=str(row["source_chapter"] or "").strip(),
                    ),
                    source_text_preview=str(row["best_source_text"] or "").strip()[:240],
                    confidence=float(row["best_confidence"] or 0.0),
                    target_label=str(target["label"]),
                )
            )
    return rows


def _chunked(items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _target_meta(label: str) -> dict[str, Any]:
    for target in BATCH2_TARGETS:
        if target["label"] == label:
            return target
    raise KeyError(label)


def _build_prompt(batch: list[CandidateRow]) -> str:
    grouped_labels = sorted({item.target_label for item in batch})
    target_specs = []
    for label in grouped_labels:
        meta = _target_meta(label)
        target_specs.append(
            {
                "label": label,
                "predicate": meta["predicate"],
                "subject_type": meta["subject_type"],
                "object_type": meta["object_type"],
                "allowed_actions": meta["allowed_actions"],
                "allowed_target_predicates": meta["allowed_target_predicates"],
                "rule_hint": meta["rule_hint"],
            }
        )
    payload = {
        "task": "adjudicate_ontology_cleanup_candidates",
        "target_specs": target_specs,
        "rows": [asdict(item) for item in batch],
    }
    return textwrap.dedent(
        f"""
        你是中医知识图谱治理审查器。
        你的任务是审查候选三元组，判断它们在当前图谱主链里应该：
        1. delete
        2. retype
        3. keep

        规则：
        - 必须逐条判断
        - 如果 action=delete，则 target_predicate 必须为空字符串
        - 如果 action=retype，则 target_predicate 必须从对应 target_specs.allowed_target_predicates 中选择
        - 如果 action=keep，则 target_predicate 必须等于原 predicate
        - 不要发明新的关系名
        - 优先依据 source_text_preview 和 subject/object 语义判断
        - 只输出 JSON，对象字段固定为 decisions

        输入：
        {json.dumps(payload, ensure_ascii=False)}

        输出 JSON 结构：
        {{
          "decisions": [
            {{
              "signature": "...",
              "fact_id": "...",
              "action": "delete|retype|keep",
              "target_predicate": "",
              "reason": "一句话理由",
              "confidence": 0.0
            }}
          ]
        }}
        """
    ).strip()


def _normalize_decision(raw: dict[str, Any], batch: list[CandidateRow]) -> dict[str, Any]:
    signature = str(raw.get("signature", "")).strip()
    row = next((item for item in batch if item.signature == signature), None)
    if row is None:
        raise RuntimeError(f"llm_unknown_signature:{signature}")
    meta = _target_meta(row.target_label)
    action = str(raw.get("action", "")).strip().lower()
    if action not in {"delete", "retype", "keep"}:
        raise RuntimeError(f"llm_invalid_action:{action}")
    target_predicate = str(raw.get("target_predicate", "")).strip()
    if action == "delete":
        target_predicate = ""
    elif action == "keep":
        target_predicate = row.predicate
    elif target_predicate not in set(meta["allowed_target_predicates"]):
        raise RuntimeError(f"llm_invalid_target_predicate:{target_predicate}")
    confidence = raw.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except Exception as exc:
        raise RuntimeError(f"llm_invalid_confidence:{confidence}") from exc
    return {
        "signature": row.signature,
        "fact_id": row.fact_id,
        "predicate": row.predicate,
        "subject": row.subject,
        "object": row.object,
        "subject_type": row.subject_type,
        "object_type": row.object_type,
        "target_label": row.target_label,
        "action": action,
        "target_predicate": target_predicate,
        "reason": str(raw.get("reason", "")).strip(),
        "confidence": round(confidence_value, 4),
        "source_book": row.source_book,
        "source_chapter": row.source_chapter or None,
        "source_text_preview": row.source_text_preview,
    }


def _call_llm_decisions(pipeline: TCMTriplePipeline, batch: list[CandidateRow]) -> list[dict[str, Any]]:
    prompt = _build_prompt(batch)
    last_error: Exception | None = None
    raw_text: str = ""
    for response_format_mode in ("json_object", "text"):
        try:
            meta = pipeline.call_llm_raw(prompt, response_format_mode=response_format_mode)
            raw_text = str(meta.get("raw_text", ""))
            try:
                parsed = json.loads(raw_text)
            except Exception:
                parsed = _extract_json_block(raw_text)
            decisions: list[Any]
            if isinstance(parsed, list):
                decisions = parsed
            elif isinstance(parsed, dict):
                for key in ("decisions", "results", "rows", "items"):
                    value = parsed.get(key, [])
                    if isinstance(value, list) and value:
                        decisions = value
                        break
                else:
                    raise RuntimeError("llm_missing_decisions")
            else:
                raise RuntimeError("llm_response_not_object")
            normalized = [_normalize_decision(item, batch) for item in decisions if isinstance(item, dict)]
            if len(normalized) != len(batch):
                raise RuntimeError(f"llm_decision_count_mismatch:{len(normalized)}!={len(batch)}")
            by_signature = {item["signature"]: item for item in normalized}
            return [by_signature[item.signature] for item in batch]
        except Exception as exc:
            last_error = exc
            continue
    preview = raw_text[:400].replace("\n", " ")
    raise RuntimeError(f"llm_decision_parse_failed:{last_error}; raw_preview={preview}")


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Batch2 LLM Adjudication")
    lines.append("")
    lines.append(f"- 生成时间：`{payload.get('generated_at', '')}`")
    lines.append(f"- 数据库：`{payload.get('db_path', '')}`")
    summary = payload.get("summary", {})
    lines.append(f"- 候选总数：`{summary.get('candidate_count', 0)}`")
    lines.append(f"- 已审样本：`{summary.get('adjudicated_count', 0)}`")
    lines.append("")
    lines.append("## 动作统计")
    for action, count in summary.get("action_counts", {}).items():
        lines.append(f"- `{action}`: `{count}`")
    for label, item in payload.get("targets", {}).items():
        lines.append("")
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- action_counts: `{json.dumps(item.get('action_counts', {}), ensure_ascii=False)}`")
        for decision in item.get("decisions", [])[:12]:
            lines.append(
                f"- `{decision['action']}` `{decision['subject']} -> {decision['object']}` "
                f"=> `{decision['target_predicate'] or '-'}' @ `{decision['source_book']}`"
            )
            if decision.get("reason"):
                lines.append(f"  理由：`{decision['reason']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    target_labels = {str(item).strip() for item in (args.target_label or []) if str(item).strip()}
    with _connect(args.db_path) as conn:
        candidates = _fetch_candidates(
            conn,
            sample_per_target=max(1, int(args.sample_per_target)),
            sampling_mode=str(args.sampling_mode),
            target_labels=target_labels or None,
        )

    pipeline = _make_pipeline()
    batches = _chunked(candidates[: max(1, int(args.max_batches)) * max(1, int(args.batch_size))], max(1, int(args.batch_size)))

    decisions: list[dict[str, Any]] = []
    for batch in batches[: max(1, int(args.max_batches))]:
        decisions.extend(_call_llm_decisions(pipeline, batch))

    action_counter: dict[str, int] = {}
    by_target: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        action_counter[decision["action"]] = action_counter.get(decision["action"], 0) + 1
        target_bucket = by_target.setdefault(
            decision["target_label"],
            {
                "action_counts": {},
                "decisions": [],
            },
        )
        target_bucket["action_counts"][decision["action"]] = target_bucket["action_counts"].get(decision["action"], 0) + 1
        target_bucket["decisions"].append(decision)

    payload = {
        "generated_at": _utc_now_text(),
        "db_path": str(args.db_path),
        "provider_summary": pipeline.format_provider_metrics_summary(),
        "summary": {
            "candidate_count": len(candidates),
            "adjudicated_count": len(decisions),
            "action_counts": action_counter,
            "sampling_mode": args.sampling_mode,
            "target_labels": sorted(target_labels),
        },
        "targets": by_target,
        "decisions": decisions,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"json={args.output_json}")
        print(f"md={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
