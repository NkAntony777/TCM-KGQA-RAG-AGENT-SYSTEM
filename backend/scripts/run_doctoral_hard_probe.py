from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BACKEND_URL = "http://127.0.0.1:8002"
DEFAULT_TOP_K = 12


@dataclass(frozen=True)
class ProbeQuestion:
    id: str
    topic: str
    question: str


QUESTIONS: tuple[ProbeQuestion, ...] = (
    ProbeQuestion(
        id="q01",
        topic="小柴胡汤少阳咳加减",
        question="《伤寒论》第96条小柴胡汤方后注“若咳者，去人参、大枣、生姜，加五味子半升、干姜二两”。请从小柴胡汤“和解少阳”的基本结构出发，分析“去人参”与“加干姜、五味子”之间的药性矛盾与统一，并论述此加减法对后世治疗“少阳咳”的指导意义（如与柴胡桂枝干姜汤证的咳嗽如何鉴别）。",
    ),
    ProbeQuestion(
        id="q02",
        topic="小建中汤寒热并治",
        question="《金匮要略·血痹虚劳病脉证并治》云“虚劳里急，悸，衄，腹中痛，梦失精，四肢酸疼，手足烦热，咽干口燥，小建中汤主之”。小建中汤由桂枝汤倍芍药加饴糖组成，请从“酸甘化阴”与“辛甘化阳”两个相反的药性配伍角度，论证小建中汤何以同时治疗“里急腹痛”（寒象）与“手足烦热、咽干口燥”（热象），并辨析其与黄连阿胶汤在治疗“虚烦”上的病机界限。",
    ),
    ProbeQuestion(
        id="q03",
        topic="升阳益胃汤风药与黄连",
        question="李东垣《脾胃论》中“升阳益胃汤”由补中益气汤化裁而来，加入羌活、独活、防风、白芍、黄连、茯苓、泽泻等。请从“风药胜湿”与“升阳散火”两个学说，分析该方为何同时使用大量风药与苦寒之黄连，并论述其与“补中益气汤证”之间的虚实、燥湿转化关系。",
    ),
    ProbeQuestion(
        id="q04",
        topic="宣痹汤与白虎加桂枝汤",
        question="《温病条辨》中“宣痹汤”（苦辛宣痹法）治疗湿温痹阻，方中多用杏仁、薏苡仁、滑石、通草等淡渗之品，但又加入防己、蚕砂、半夏等辛温或苦辛之药。请从“湿闭气分”与“热蕴经络”的病机交织，论述宣痹汤与白虎加桂枝汤在治疗“热痹”证中的方证鉴别要点，并说明为何湿温所致痹证不宜早用石膏、知母。",
    ),
    ProbeQuestion(
        id="q05",
        topic="久病入络与虫类药阶梯",
        question="叶天士《临证指南医案》中提出“久病入络”理论，并善用虫类药（如水蛭、䗪虫、全蝎、地龙）治疗顽痹、积聚。请结合《素问·痹论》“病久入深，营卫之行涩，经络时疏，故不通”的经旨，论证虫类药“搜剔络邪”与草木活血化瘀药在作用层次上的本质差异，并举例说明在肿瘤、肝纤维化中如何根据“络瘀”程度选择用药阶梯。",
    ),
    ProbeQuestion(
        id="q06",
        topic="2024甲辰年五运六气",
        question="五运六气中“客主加临”出现“顺化”、“逆化”、“小逆”、“不和”等格局。请以某一年（如2024甲辰年）为例，推演其司天、在泉、主气、客气之间的加临关系，分析可能出现的气候与疫病倾向，并论述“治以咸寒，佐以甘苦”等运气治则在该年流感防治中的具体方药设计思路。",
    ),
    ProbeQuestion(
        id="q07",
        topic="黄芪托毒生肌与免疫",
        question="《神农本草经》载黄芪“主痈疽久败疮，排脓止痛，大风癞疾”，而补中益气汤、玉屏风散等方多取其补气固表。请从“托毒生肌”与“益气升阳”两个看似不同的功效指向，论证黄芪作用的统一性（即“阳气充足则邪气自散”），并结合现代免疫学（如T细胞亚群、巨噬细胞极化）解释黄芪在慢性感染、难愈性溃疡中的应用机制。",
    ),
    ProbeQuestion(
        id="q08",
        topic="半夏秫米汤与睡眠节律",
        question="《灵枢·卫气行》论述卫气昼行于阳、夜行于阴的节律。失眠（不寐）病机多责之“阳不入阴”。请从卫气循行与跷脉的关系，分析半夏秫米汤“通阴阳”的配伍原理，并论述该方与现代治疗失眠的褪黑素、GABA受体激动剂在调节“睡眠-觉醒节律”上的可能对应机制。",
    ),
    ProbeQuestion(
        id="q09",
        topic="胸痹三方与冠心病分层",
        question="张仲景《金匮要略·胸痹心痛短气病脉证治》中，栝楼薤白白酒汤、栝楼薤白半夏汤、枳实薤白桂枝汤三方均治胸痹，但用药有从“辛温通阳”到“理气化痰”再到“破气逐饮”的递进。请从“阳气不通—痰浊壅盛—饮邪结聚”的病机演变，论证三方证的阶梯性差异，并说明现代冠心病（稳定型心绞痛、不稳定型心绞痛、急性心肌梗死）可如何参照此辨证体系。",
    ),
    ProbeQuestion(
        id="q10",
        topic="四逆散与三类厥冷鉴别",
        question="《伤寒论》四逆散（甘草、枳实、柴胡、芍药）被后世视为“疏肝理气之祖”，但其原条文主治“少阴病，四逆，其人或咳，或悸，或小便不利，或腹中痛，或泄利下重”。请从“阳郁于里”而非“阳虚”的角度，解释四逆散证“四逆”的病理机制，并论述其与四逆汤证、当归四逆汤证在手足逆冷上的鉴别要点，以及为何方中不用附子、干姜而用柴胡、枳实。",
    ),
)


def _utc_now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _post_json(url: str, payload: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("qa_response_not_object")
    return parsed


def _get_json(url: str, *, timeout_s: int) -> dict[str, Any]:
    request = Request(url=url, method="GET")
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("health_response_not_object")
    return parsed


def _empty_result(question: str, mode: str, top_k: int, *, error: str) -> dict[str, Any]:
    return {
        "request": {"query": question, "mode": mode, "top_k": top_k},
        "topic_sent_to_system": False,
        "ok": False,
        "latency_ms": 0.0,
        "status": "request_error",
        "final_route": None,
        "route": None,
        "executed_routes": [],
        "generation_backend": None,
        "answer": None,
        "citations": [],
        "book_citations": [],
        "evidence_paths": [],
        "factual_evidence_count": 0,
        "case_reference_count": 0,
        "factual_evidence_preview": [],
        "case_reference_preview": [],
        "planner_steps": [],
        "tool_trace": [],
        "deep_trace": [],
        "notes": [],
        "trace_id": None,
        "error": error,
    }


def _run_mode(backend_url: str, question: str, mode: str, *, top_k: int, timeout_s: int) -> dict[str, Any]:
    started = time.perf_counter()
    request_payload = {"query": question, "mode": mode, "top_k": top_k}
    try:
        response = _post_json(f"{backend_url}/api/qa/answer", request_payload, timeout_s=timeout_s)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
        data = response.get("data", {}) if isinstance(response.get("data"), dict) else {}
        route = data.get("route", {}) if isinstance(data.get("route"), dict) else {}
        factual = data.get("factual_evidence", []) if isinstance(data.get("factual_evidence"), list) else []
        cases = data.get("case_references", []) if isinstance(data.get("case_references"), list) else []
        return {
            "request": request_payload,
            "topic_sent_to_system": False,
            "ok": True,
            "latency_ms": elapsed_ms,
            "status": data.get("status"),
            "final_route": route.get("final_route"),
            "route": route.get("route"),
            "executed_routes": route.get("executed_routes", []) if isinstance(route.get("executed_routes"), list) else [],
            "generation_backend": data.get("generation_backend"),
            "answer": data.get("answer"),
            "citations": data.get("citations", []) if isinstance(data.get("citations"), list) else [],
            "book_citations": data.get("book_citations", []) if isinstance(data.get("book_citations"), list) else [],
            "evidence_paths": data.get("evidence_paths", []) if isinstance(data.get("evidence_paths"), list) else [],
            "factual_evidence_count": len(factual),
            "case_reference_count": len(cases),
            "factual_evidence_preview": factual[:3],
            "case_reference_preview": cases[:2],
            "planner_steps": data.get("planner_steps", []) if isinstance(data.get("planner_steps"), list) else [],
            "tool_trace": data.get("tool_trace", []) if isinstance(data.get("tool_trace"), list) else [],
            "deep_trace": data.get("deep_trace", []) if isinstance(data.get("deep_trace"), list) else [],
            "notes": data.get("notes", []) if isinstance(data.get("notes"), list) else [],
            "trace_id": response.get("trace_id"),
            "error": None,
        }
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        result = _empty_result(question, mode, top_k, error=f"http_{exc.code}: {payload}")
    except URLError as exc:
        result = _empty_result(question, mode, top_k, error=f"url_error: {exc}")
    except Exception as exc:
        result = _empty_result(question, mode, top_k, error=str(exc))
    result["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
    return result


def _build_summary(questions: list[dict[str, Any]]) -> dict[str, Any]:
    quick_items = [item.get("quick", {}) for item in questions if isinstance(item.get("quick"), dict)]
    deep_items = [item.get("deep", {}) for item in questions if isinstance(item.get("deep"), dict)]

    def avg_latency(rows: list[dict[str, Any]]) -> float:
        values = [float(row.get("latency_ms", 0.0) or 0.0) for row in rows]
        return round(sum(values) / len(values), 1) if values else 0.0

    return {
        "total_questions": len(questions),
        "quick_ok": sum(1 for row in quick_items if row.get("ok") is True),
        "deep_ok": sum(1 for row in deep_items if row.get("ok") is True),
        "quick_avg_latency_ms": avg_latency(quick_items),
        "deep_avg_latency_ms": avg_latency(deep_items),
    }


def _initial_payload(backend_url: str, top_k: int) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_text(),
        "backend_url": backend_url,
        "source": "live_http_eval",
        "topic_kept_in_output_only": True,
        "top_k": top_k,
        "questions": [
            {
                "id": item.id,
                "topic": item.topic,
                "question": item.question,
                "quick": None,
                "deep": None,
            }
            for item in QUESTIONS
        ],
        "summary": {},
    }


def _load_or_init(path: Path, *, backend_url: str, top_k: int) -> dict[str, Any]:
    if not path.exists():
        return _initial_payload(backend_url, top_k)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _initial_payload(backend_url, top_k)
    if not isinstance(payload, dict):
        return _initial_payload(backend_url, top_k)
    if not isinstance(payload.get("questions"), list):
        payload = _initial_payload(backend_url, top_k)
    payload["backend_url"] = backend_url
    payload["topic_kept_in_output_only"] = True
    payload["top_k"] = top_k
    return payload


def _save_payload(path: Path, payload: dict[str, Any]) -> None:
    payload["generated_at"] = _utc_now_text()
    questions = payload.get("questions", [])
    payload["summary"] = _build_summary(questions if isinstance(questions, list) else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_done(slot: Any) -> bool:
    return isinstance(slot, dict) and slot.get("ok") is True and slot.get("answer")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run doctoral-level quick/deep QA probe with incremental JSON writes.")
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--output", default="eval/doctoral_hard_probe_quick_deep_20260408.json")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()

    backend_url = str(args.backend_url).rstrip("/")
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    health = _get_json(f"{backend_url}/health", timeout_s=30)
    if health.get("status") != "ok":
        print(json.dumps({"error": "backend_unhealthy", "health": health}, ensure_ascii=False))
        return 1

    payload = _load_or_init(output_path, backend_url=backend_url, top_k=args.top_k)
    questions = payload.get("questions", [])
    if not isinstance(questions, list):
        print(json.dumps({"error": "questions_payload_invalid"}, ensure_ascii=False))
        return 1

    total_modes = len(questions) * 2
    completed_modes = 0
    for row in questions:
        if isinstance(row, dict) and _is_done(row.get("quick")):
            completed_modes += 1
        if isinstance(row, dict) and _is_done(row.get("deep")):
            completed_modes += 1

    print(f"[probe] resume from {completed_modes}/{total_modes} finished modes", flush=True)

    for index, row in enumerate(questions, start=1):
        if not isinstance(row, dict):
            continue
        question = str(row.get("question", "")).strip()
        if not question:
            continue
        for mode in ("quick", "deep"):
            if _is_done(row.get(mode)):
                continue
            print(f"[probe] {index:02d}/{len(questions)} {row.get('id')} {mode} start", flush=True)
            row[mode] = _run_mode(
                backend_url,
                question,
                mode,
                top_k=max(1, int(args.top_k)),
                timeout_s=max(30, int(args.timeout_sec)),
            )
            _save_payload(output_path, payload)
            status = row[mode].get("status")
            latency = row[mode].get("latency_ms")
            print(f"[probe] {index:02d}/{len(questions)} {row.get('id')} {mode} done status={status} latency_ms={latency}", flush=True)

    _save_payload(output_path, payload)
    print(json.dumps({"out_path": str(output_path), "summary": payload.get("summary", {})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
