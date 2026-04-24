from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.pipeline_server import _build_pipeline
from services.triple_pipeline_service import PipelineConfig, TCMTriplePipeline


BOOK_NAME = "072-医方考"
CHUNK_IDS = [20, 30, 50, 100]
MODELS = [
    "doubao-seed-2.0-pro",
    "doubao-seed-2.0-lite",
    "deepseek-v3.2",
    "mimo-v2-pro",
    "mimo-v2-omni",
    "mimo-v2-flash",
    "kimi-k2.5",
]


def normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    for token in [" ", "\n", "\t", "\r", "（", "）", "(", ")", "：", ":", "，", ",", "。", ".", "；", ";", "、"]:
        text = text.replace(token, "")
    return text


def triple_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_text(row.get("subject", "")),
        normalize_text(row.get("predicate", "")),
        normalize_text(row.get("object", "")),
    )


def choose_chunk_tasks() -> list[Any]:
    backend_root = Path(__file__).resolve().parents[1]
    books_dir = (backend_root.parent.parent / "TCM-Ancient-Books-master" / "TCM-Ancient-Books-master").resolve()
    output_dir = (backend_root / "storage" / "triple_pipeline").resolve()
    pipeline = TCMTriplePipeline(
        PipelineConfig(
            books_dir=books_dir,
            output_dir=output_dir,
            model="benchmark-dummy",
            api_key="dummy",
            base_url="https://example.invalid",
            request_timeout=314.0,
            request_delay=0.0,
            parallel_workers=1,
            max_chunk_chars=800,
            chunk_overlap=200,
            chunk_strategy="body_first",
        )
    )
    book = next(path for path in books_dir.glob(f"{BOOK_NAME}.txt"))
    tasks = pipeline.schedule_book_chunks(book_path=book, chunk_strategy="body_first")
    mapping = {task.chunk_index: task for task in tasks}
    return [mapping[idx] for idx in CHUNK_IDS]


GOLD: dict[int, list[dict[str, str]]] = {
    20: [
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "大黄"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "附子泻心汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "附子泻心汤", "predicate": "治疗证候", "object": "伤寒心下痞"},
        {"subject": "附子泻心汤", "predicate": "治疗症状", "object": "汗出恶寒"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "生姜"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "甘草"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "半夏"},
        {"subject": "生姜泻心汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "生姜泻心汤", "predicate": "治疗疾病", "object": "伤寒中风"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "下利"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "谷不化"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "腹中雷鸣"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "心下痞硬而满"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "干呕"},
        {"subject": "生姜泻心汤", "predicate": "治疗症状", "object": "心烦不得安"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "芫花"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "甘遂"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "大戟"},
        {"subject": "十枣汤", "predicate": "使用药材", "object": "大枣"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "汗出"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "心下痞硬"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "胁痛"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "干呕"},
        {"subject": "十枣汤", "predicate": "治疗症状", "object": "短气"},
    ],
    30: [
        {"subject": "附子汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "茯苓"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "芍药"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "附子汤", "predicate": "使用药材", "object": "白术"},
        {"subject": "附子汤", "predicate": "治疗证候", "object": "少阴病"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "背恶寒"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "身体痛"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "手足寒"},
        {"subject": "附子汤", "predicate": "治疗症状", "object": "骨节痛"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "甘草"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "干姜"},
        {"subject": "四逆汤", "predicate": "使用药材", "object": "附子"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "自利不渴"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "身痛"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "厥逆下利"},
        {"subject": "四逆汤", "predicate": "治疗症状", "object": "脉不至"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "干姜"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "黄连"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "黄芩"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "使用药材", "object": "人参"},
        {"subject": "干姜黄连黄芩人参汤", "predicate": "治疗症状", "object": "食入口即吐"},
    ],
    50: [
        {"subject": "二妙散", "predicate": "使用药材", "object": "黄柏"},
        {"subject": "二妙散", "predicate": "使用药材", "object": "苍术"},
        {"subject": "二妙散", "predicate": "治疗症状", "object": "腰膝疼痛"},
        {"subject": "二妙散", "predicate": "治疗证候", "object": "湿热"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "白术"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "茯苓"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "猪苓"},
        {"subject": "四苓散", "predicate": "使用药材", "object": "泽泻"},
        {"subject": "四苓散", "predicate": "治疗症状", "object": "水泻"},
        {"subject": "四苓散", "predicate": "治疗症状", "object": "小便不利"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "浓朴"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "陈皮"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "半夏"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "藿香"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "苍术"},
        {"subject": "不换金正气散", "predicate": "使用药材", "object": "甘草"},
        {"subject": "不换金正气散", "predicate": "治疗症状", "object": "吐泻下利"},
        {"subject": "不换金正气散", "predicate": "治疗证候", "object": "山岚瘴气"},
        {"subject": "不换金正气散", "predicate": "治疗证候", "object": "不服水土"},
    ],
    100: [
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "半夏"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "胆南星"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "陈皮"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "香附"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "苏子"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "青皮"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "神曲"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "萝卜子"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "棠球肉"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "麦芽"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "杏仁"},
        {"subject": "顺气消食化痰丸", "predicate": "使用药材", "object": "葛根"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗证候", "object": "酒食生痰"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗症状", "object": "五更咳嗽"},
        {"subject": "顺气消食化痰丸", "predicate": "治疗症状", "object": "胸膈膨闷"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "生地黄"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "白茯苓"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "人参"},
        {"subject": "琼玉膏", "predicate": "使用药材", "object": "白蜜"},
        {"subject": "琼玉膏", "predicate": "治疗症状", "object": "干咳嗽"},
    ],
}


def run_single_model(model_name: str, tasks: list[Any]) -> dict[str, Any]:
    pipeline = _build_pipeline(
        {
            "model": model_name,
            "request_timeout": 314.0,
            "request_delay": 1.1,
            "parallel_workers": 11,
            "max_retries": 2,
            "retry_backoff_base": 2.0,
            "max_chunk_chars": 800,
            "chunk_overlap": 200,
            "chunk_strategy": "body_first",
        }
    )

    outputs: list[dict[str, Any]] = []
    all_predicted_keys: list[tuple[str, str, str]] = []
    all_gold_keys: list[tuple[str, str, str]] = []
    per_chunk_scores: list[dict[str, Any]] = []
    relation_counter: Counter[str] = Counter()
    error_types: Counter[str] = Counter()
    parse_success = 0

    for task in tasks:
        gold_rows = GOLD[task.chunk_index]
        gold_keys = {triple_key(item) for item in gold_rows}
        all_gold_keys.extend(gold_keys)
        start = time.perf_counter()
        raw_meta: dict[str, Any] | None = None
        normalized_rows: list[dict[str, Any]] = []
        error = ""
        try:
            payload = pipeline.extract_chunk_payload(task, dry_run=False)
            raw_meta = payload.get("__meta__", {}) if isinstance(payload, dict) else {}
            normalized = pipeline.normalize_triples(
                payload=payload,
                book_name=task.book_name,
                chapter_name=task.chapter_name,
            )
            normalized_rows = [asdict(row) for row in normalized]
            parse_success += 1
        except Exception as exc:
            error = str(exc)
            error_types[type(exc).__name__] += 1
        elapsed = time.perf_counter() - start

        predicted_keys = {triple_key(item) for item in normalized_rows}
        all_predicted_keys.extend(predicted_keys)
        tp = len(predicted_keys & gold_keys)
        fp = len(predicted_keys - gold_keys)
        fn = len(gold_keys - predicted_keys)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        for row in normalized_rows:
            relation_counter[str(row.get("predicate", "")).strip()] += 1

        usage = raw_meta.get("usage", {}) if isinstance(raw_meta, dict) else {}
        outputs.append(
            {
                "chunk_index": task.chunk_index,
                "elapsed_sec": elapsed,
                "triples_count": len(normalized_rows),
                "gold_count": len(gold_keys),
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "error": error,
                "usage": usage,
                "predicted_rows": normalized_rows,
            }
        )
        per_chunk_scores.append(
            {
                "chunk_index": task.chunk_index,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    predicted_set = set(all_predicted_keys)
    gold_set = set(all_gold_keys)
    tp_total = len(predicted_set & gold_set)
    fp_total = len(predicted_set - gold_set)
    fn_total = len(gold_set - predicted_set)
    precision_total = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    recall_total = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    f1_total = (2 * precision_total * recall_total / (precision_total + recall_total)) if (precision_total + recall_total) else 0.0

    latencies = [item["elapsed_sec"] for item in outputs]
    prompt_tokens = [int(item["usage"].get("prompt_tokens", 0) or 0) for item in outputs]
    completion_tokens = [int(item["usage"].get("completion_tokens", 0) or 0) for item in outputs]
    total_triples = sum(item["triples_count"] for item in outputs)
    total_completion_tokens = sum(completion_tokens)

    return {
        "model": model_name,
        "outputs": outputs,
        "per_chunk_scores": per_chunk_scores,
        "parse_success_rate": parse_success / len(tasks),
        "total_triples": total_triples,
        "mean_triples_per_chunk": total_triples / len(tasks),
        "latency_mean_sec": statistics.mean(latencies),
        "latency_median_sec": statistics.median(latencies),
        "latency_max_sec": max(latencies),
        "prompt_tokens_total": sum(prompt_tokens),
        "completion_tokens_total": total_completion_tokens,
        "completion_tokens_per_triple": (total_completion_tokens / total_triples) if total_triples else 0.0,
        "precision": precision_total,
        "recall": recall_total,
        "f1": f1_total,
        "tp": tp_total,
        "fp": fp_total,
        "fn": fn_total,
        "relation_dist": relation_counter.most_common(),
        "errors": dict(error_types),
    }


def rank_models(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    latency_values = [item["latency_mean_sec"] for item in results]
    min_latency = min(latency_values) if latency_values else 1.0
    for item in results:
        speed_score = min_latency / item["latency_mean_sec"] if item["latency_mean_sec"] else 0.0
        score = (
            item["f1"] * 0.5
            + item["precision"] * 0.15
            + item["recall"] * 0.15
            + item["parse_success_rate"] * 0.1
            + speed_score * 0.1
        )
        ranked.append({**item, "composite_score": score, "speed_score": speed_score})
    ranked.sort(key=lambda item: item["composite_score"], reverse=True)
    return ranked


def render_report(tasks: list[Any], ranked: list[dict[str, Any]], output_path: Path) -> None:
    best = ranked[0] if ranked else None
    lines: list[str] = []
    lines.append("# 三元组提取模型横评报告")
    lines.append("")
    lines.append(f"- 评测时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 评测书目：`{BOOK_NAME}`")
    lines.append(f"- 评测 chunk：{', '.join(str(task.chunk_index) for task in tasks)}")
    lines.append("- 统一参数：`request_timeout=314`，`request_delay=1.1`，`parallel_workers=11`，`temperature=0`，`chunk_strategy=body_first`")
    lines.append("- 统一 prompt：当前主链路 `build_prompt()`")
    lines.append("- 统一解析：当前主链路 `call_llm() -> _extract_json_block() -> normalize_triples()`")
    lines.append("- 排名原则：本次以性能为主，不把价格纳入综合分；token 指标只作为辅助观察项。")
    lines.append("")
    lines.append("## 样本说明")
    lines.append("")
    for task in tasks:
        preview = task.text_chunk[:140].replace("\n", " ")
        lines.append(f"- chunk {task.chunk_index}：`{task.chapter_name}`，长度 {len(task.text_chunk)} 字，预览：{preview}...")
    lines.append("")
    lines.append("## 金标设计")
    lines.append("")
    gold_total = sum(len(GOLD[idx]) for idx in CHUNK_IDS)
    lines.append(f"- 本次人工金标共 {gold_total} 条，只纳入原文中明确可抽取、且适合进入图谱的高置信事实。")
    lines.append("- 重点考察三类事实：`使用药材`、`治疗证候/治疗症状/治疗疾病`。")
    lines.append("- 不将长段注释中的推理性解释全部纳入金标，以避免把主观扩展当成漏抽。")
    lines.append("")
    lines.append("## 总榜")
    lines.append("")
    lines.append("| 排名 | 模型 | F1 | Precision | Recall | 平均延迟(s) | 平均每 chunk 三元组数 | 解析成功率 | completion_tokens/三元组 | 综合分 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for index, item in enumerate(ranked, start=1):
        lines.append(
            f"| {index} | `{item['model']}` | {item['f1']:.3f} | {item['precision']:.3f} | {item['recall']:.3f} | "
            f"{item['latency_mean_sec']:.2f} | {item['mean_triples_per_chunk']:.2f} | {item['parse_success_rate']:.2%} | "
            f"{item['completion_tokens_per_triple']:.1f} | {item['composite_score']:.3f} |"
        )
    lines.append("")
    lines.append("## 分模型详情")
    lines.append("")
    for item in ranked:
        lines.append(f"### {item['model']}")
        lines.append("")
        lines.append(
            f"- 总体：F1={item['f1']:.3f}，Precision={item['precision']:.3f}，Recall={item['recall']:.3f}，"
            f"TP={item['tp']}，FP={item['fp']}，FN={item['fn']}。"
        )
        lines.append(
            f"- 速度：平均 {item['latency_mean_sec']:.2f}s，中位数 {item['latency_median_sec']:.2f}s，最大 {item['latency_max_sec']:.2f}s。"
        )
        lines.append(
            f"- 产出：总三元组 {item['total_triples']}，平均每 chunk {item['mean_triples_per_chunk']:.2f} 条，解析成功率 {item['parse_success_rate']:.2%}。"
        )
        lines.append(
            f"- token：prompt 总计 {item['prompt_tokens_total']}，completion 总计 {item['completion_tokens_total']}，completion/三元组 {item['completion_tokens_per_triple']:.1f}。"
        )
        if item["relation_dist"]:
            top_relations = "，".join(f"{name}:{count}" for name, count in item["relation_dist"][:6])
            lines.append(f"- 关系分布：{top_relations}")
        if item["errors"]:
            lines.append(f"- 异常：`{json.dumps(item['errors'], ensure_ascii=False)}`")
        lines.append("")
        lines.append("| chunk | triples | precision | recall | f1 | latency(s) |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        score_map = {row["chunk_index"]: row for row in item["per_chunk_scores"]}
        output_map = {row["chunk_index"]: row for row in item["outputs"]}
        for chunk_id in CHUNK_IDS:
            score = score_map[chunk_id]
            output = output_map[chunk_id]
            lines.append(
                f"| {chunk_id} | {output['triples_count']} | {score['precision']:.3f} | {score['recall']:.3f} | {score['f1']:.3f} | {output['elapsed_sec']:.2f} |"
            )
        lines.append("")
    lines.append("## 结论")
    lines.append("")
    if best:
        lines.append(f"- 综合最优模型是 `{best['model']}`。它在当前 prompt 和参数下取得了最高综合分。")
    fastest = min(ranked, key=lambda item: item["latency_mean_sec"]) if ranked else None
    highest_recall = max(ranked, key=lambda item: item["recall"]) if ranked else None
    highest_precision = max(ranked, key=lambda item: item["precision"]) if ranked else None
    if fastest:
        lines.append(f"- 速度最快的是 `{fastest['model']}`，平均延迟 {fastest['latency_mean_sec']:.2f}s。")
    if highest_recall:
        lines.append(f"- 召回最高的是 `{highest_recall['model']}`，Recall={highest_recall['recall']:.3f}。")
    if highest_precision:
        lines.append(f"- 精度最高的是 `{highest_precision['model']}`，Precision={highest_precision['precision']:.3f}。")
    lines.append("- 如果你后续更看重“大任务稳定产量”，优先看 Recall、解析成功率和低产出 chunk 比例。")
    lines.append("- 如果你更看重“成本与吞吐”，优先看平均延迟和 completion_tokens/三元组。")
    lines.append("- 本报告基于单书 4 个 chunk 的小样本人工金标，适合做当前链路上的模型筛选，不适合外推成全量语料的绝对结论。")
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    tasks = choose_chunk_tasks()
    raw_results = [run_single_model(model_name, tasks) for model_name in MODELS]
    ranked = rank_models(raw_results)
    output_path = Path(__file__).resolve().parents[2] / "docs" / "triple_model_benchmark_report.md"
    render_report(tasks, ranked, output_path)
    print(json.dumps({"output_path": str(output_path), "models": [item["model"] for item in ranked]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
