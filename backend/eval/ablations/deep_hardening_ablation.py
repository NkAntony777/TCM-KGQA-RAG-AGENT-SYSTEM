from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.ablations._common import BACKEND_ROOT, render_simple_table, write_outputs


DEFAULT_OLD = BACKEND_ROOT / "eval" / "doctoral_hard_probe_quick_deep_20260414_nebula_live_rerun.json"
DEFAULT_NEW = BACKEND_ROOT / "eval" / "doctoral_hard_probe_quick_deep_20260414_hardening_rerun.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize(payload: dict) -> dict[str, float | int]:
    questions = payload.get("questions", [])
    deep_rows = [row.get("deep", {}) for row in questions if isinstance(row, dict) and isinstance(row.get("deep"), dict)]
    total = len(deep_rows)
    fallback = sum(1 for item in deep_rows if "fallback" in str(item.get("generation_backend", "")).lower() or any("fallback" in str(note).lower() for note in (item.get("notes", []) or [])))
    short = sum(1 for item in deep_rows if len(str(item.get("answer", "") or "").strip()) < 400)
    avg_latency = round(sum(float(item.get("latency_ms", 0.0) or 0.0) for item in deep_rows) / max(total, 1), 1)
    return {"total": total, "fallback_count": fallback, "short_count": short, "avg_latency_ms": avg_latency}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare doctoral deep quality before and after hardening.")
    parser.add_argument("--old-json", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new-json", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--output-json", type=Path, default=BACKEND_ROOT / "eval" / "ablations" / "deep_hardening_ablation_latest.json")
    parser.add_argument("--output-md", type=Path, default=BACKEND_ROOT.parent.parent / "docs" / "Deep_Hardening_Ablation_Latest.md")
    args = parser.parse_args()

    old_payload = _load(args.old_json)
    new_payload = _load(args.new_json)
    old_summary = _summarize(old_payload)
    new_summary = _summarize(new_payload)
    payload = {"old": {"path": str(args.old_json), **old_summary}, "new": {"path": str(args.new_json), **new_summary}}
    markdown = render_simple_table(
        "Deep Hardening Ablation",
        [("old_json", args.old_json), ("new_json", args.new_json)],
        ["Condition", "deep_total", "fallback_count", "short_count", "avg_latency_ms"],
        [
            ["before_hardening", old_summary["total"], old_summary["fallback_count"], old_summary["short_count"], old_summary["avg_latency_ms"]],
            ["after_hardening", new_summary["total"], new_summary["fallback_count"], new_summary["short_count"], new_summary["avg_latency_ms"]],
        ],
    )
    write_outputs(output_json=args.output_json, output_md=args.output_md, payload=payload, markdown=markdown)


if __name__ == "__main__":
    main()
