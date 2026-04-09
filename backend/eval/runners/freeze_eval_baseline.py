from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from render_eval_markdown import render_markdown, summarize_mode_observability


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation payload must be a JSON object")
    return payload


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _freeze_payload(source_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("payload.questions must be a list")

    frozen_questions: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        quick = item.get("quick", {}) if isinstance(item.get("quick"), dict) else {}
        deep = item.get("deep", {}) if isinstance(item.get("deep"), dict) else {}
        frozen_questions.append(
            {
                "id": item.get("id"),
                "topic": item.get("topic"),
                "question": item.get("question"),
                "quick": summarize_mode_observability(quick),
                "deep": summarize_mode_observability(deep),
            }
        )

    return {
        "frozen_at": _utc_now_text(),
        "source_eval_json": str(source_path),
        "source_generated_at": payload.get("generated_at"),
        "backend_url": payload.get("backend_url"),
        "source": payload.get("source"),
        "top_k": payload.get("top_k"),
        "question_count": len(frozen_questions),
        "questions": frozen_questions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze current eval output into diffable JSON + Markdown baselines.")
    parser.add_argument("input", type=Path, help="Path to the source eval JSON file.")
    parser.add_argument("--output-json", type=Path, default=None, help="Output path for the compact frozen JSON baseline.")
    parser.add_argument("--output-md", type=Path, default=None, help="Output path for the rendered Markdown baseline.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    compact_output = args.output_json.resolve() if args.output_json else input_path.with_name(f"{input_path.stem}.baseline.json")
    markdown_output = args.output_md.resolve() if args.output_md else input_path.with_name(f"{input_path.stem}.baseline.md")

    payload = _load_payload(input_path)
    frozen_payload = _freeze_payload(input_path, payload)

    compact_output.write_text(json.dumps(frozen_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_json": str(compact_output),
                "output_md": str(markdown_output),
                "question_count": frozen_payload["question_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
