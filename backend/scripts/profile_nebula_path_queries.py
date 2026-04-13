from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT.parent / "docs"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_CASES = [
    {"id": "light_001", "start": "附子", "end": "少阴病", "max_hops": 2},
    {"id": "light_002", "start": "熟地黄", "end": "真阴亏损", "max_hops": 3},
    {"id": "heavy_001", "start": "黄芪", "end": "虚风内动", "max_hops": 5},
]


def _render_markdown(rows: list[dict], output_json: Path) -> str:
    lines = [
        "# Nebula Path Query Profile",
        "",
        f"- JSON artifact: `{output_json}`",
        "- Scope: collect PROFILE outputs and whole-latency for representative Nebula path-query cases.",
        "",
        "| Case | Start | End | Hops | whole_latency_us | rows | operators | top operator |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['start']} | {row['end']} | {row['max_hops']} | "
            f"{row.get('whole_latency_us', '')} | {row.get('row_size', '')} | "
            f"{row.get('operator_count', '')} | {row.get('top_operator', '')} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- `whole_latency_us` comes from Nebula ResultSet; it is suitable for relative tuning, not as an end-to-end application latency metric.")
    lines.append("- `plan_desc` is preserved in JSON for deeper inspection after config or query-shape changes.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default=str(BACKEND_DIR / "eval" / "nebula_path_profile_latest.json"))
    parser.add_argument("--output-md", default=str(DOCS_DIR / "Nebula_Path_Profile_20260413.md"))
    args = parser.parse_args()

    from services.graph_service.nebulagraph_store import NebulaGraphStore, entity_vid

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    store = NebulaGraphStore()
    rows: list[dict] = []
    with store._session() as session:  # noqa: SLF001
        session.execute(f"USE `{store.settings.space}`;")
        for case in DEFAULT_CASES:
            stmt = (
                "PROFILE FIND SHORTEST PATH "
                f'FROM "{entity_vid(case["start"])}" TO "{entity_vid(case["end"])}" '
                f'OVER `relation` BIDIRECT UPTO {int(case["max_hops"])} STEPS '
                "YIELD path as p | LIMIT 3;"
            )
            started = time.perf_counter()
            result = session.execute(stmt)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            plan_desc = result.plan_desc() if result.is_succeeded() else None
            plan_nodes = getattr(plan_desc, "plan_node_descs", []) or []
            item = {
                **case,
                "statement": stmt,
                "client_elapsed_ms": elapsed_ms,
                "succeeded": bool(result.is_succeeded()),
                "error_msg": "" if result.is_succeeded() else str(result.error_msg()),
                "whole_latency_us": int(result.whole_latency()) if result.is_succeeded() else None,
                "row_size": int(result.row_size()) if result.is_succeeded() else 0,
                "keys": list(result.keys()) if result.is_succeeded() else [],
                "plan_desc_repr": repr(plan_desc) if plan_desc is not None else "",
                "operator_count": len(plan_nodes),
                "top_operator": "",
            }
            if plan_nodes:
                name = getattr(plan_nodes[0], "name", "") or ""
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                item["top_operator"] = str(name).strip()
            rows.append(item)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rows": rows,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_render_markdown(rows, output_json), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "md": str(output_md), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
