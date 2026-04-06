from __future__ import annotations

from typing import Any


ENTITY_RELATIONS: dict[str, dict[str, Any]] = {
    "逍遥散": {
        "canonical_name": "逍遥散",
        "entity_type": "formula",
        "relations": [
            {"predicate": "使用药材", "target": "柴胡", "source_book": "医方集解", "source_chapter": "卷一"},
            {"predicate": "使用药材", "target": "当归", "source_book": "医方集解", "source_chapter": "卷一"},
            {"predicate": "治疗证候", "target": "肝郁脾虚", "source_book": "和剂局方", "source_chapter": "方剂门"},
        ],
    },
    "柴胡": {
        "canonical_name": "柴胡",
        "entity_type": "herb",
        "relations": [
            {"predicate": "功效", "target": "疏肝解郁", "source_book": "本草纲目", "source_chapter": "草部"},
            {"predicate": "归经", "target": "肝经", "source_book": "本草纲目", "source_chapter": "草部"},
        ],
    },
    "肝郁脾虚": {
        "canonical_name": "肝郁脾虚",
        "entity_type": "syndrome",
        "relations": [
            {"predicate": "推荐方剂", "target": "逍遥散", "source_book": "医宗金鉴", "source_chapter": "杂病心法"},
            {"predicate": "常见症状", "target": "胁肋胀痛", "source_book": "医宗金鉴", "source_chapter": "杂病心法"},
        ],
    },
}

SYMPTOM_TO_SYNDROMES: dict[str, list[dict[str, Any]]] = {
    "胁肋胀痛": [{"name": "肝郁脾虚", "score": 0.82, "recommended_formulas": ["逍遥散"]}],
    "头痛": [{"name": "肝阳上亢", "score": 0.76, "recommended_formulas": ["天麻钩藤饮"]}],
    "烦躁": [{"name": "肝郁化火", "score": 0.74, "recommended_formulas": ["丹栀逍遥散"]}],
}

MOCK_DOCS: list[dict[str, Any]] = [
    {
        "chunk_id": "doc_001",
        "text": "逍遥散用于肝郁血虚、脾失健运之证，见胁肋作痛、神疲食少等。",
        "source_file": "医方集解.txt",
        "source_page": 12,
        "score": 0.91,
    },
    {
        "chunk_id": "doc_002",
        "text": "柴胡苦辛微寒，归肝胆经，善疏肝解郁并和解少阳。",
        "source_file": "本草纲目.txt",
        "source_page": 87,
        "score": 0.85,
    },
    {
        "chunk_id": "doc_003",
        "text": "肝郁脾虚调治宜疏肝理气、健脾和中，可配合逍遥散加减。",
        "source_file": "中医内科学.txt",
        "source_page": 33,
        "score": 0.83,
    },
]

MOCK_CASE_QA: list[dict[str, Any]] = [
    {
        "embedding_id": "case_001",
        "collection": "tcm_shard_0",
        "document": "基于输入的患者医案记录，直接给出你认为的【治疗方案】：中药、方剂，和【诊断】：证型。\n基本信息: 年龄: 47 性别: 女 主诉: 胁肋胀痛 失眠 口苦 现病史: 情绪波动后加重 纳差 体格检查: 舌苔薄白 脉弦。",
        "answer": "诊断: 证型: 肝郁脾虚证 治疗方案: 方剂: 逍遥散 中药: 柴胡 当归 白芍 茯苓 白术 甘草。",
        "score": 0.86,
    },
    {
        "embedding_id": "case_002",
        "collection": "tcm_shard_4",
        "document": "基于输入的患者医案记录，直接给出你认为的【治疗方案】：中药、方剂，和【诊断】：证型。\n基本信息: 年龄: 61 性别: 男 主诉: 腰酸 头晕 耳鸣 现病史: 夜尿频多 体格检查: 舌红少苔 脉细数。",
        "answer": "诊断: 证型: 肝肾阴虚证 治疗方案: 方剂: 六味地黄丸 中药: 熟地黄 山茱萸 山药 泽泻 牡丹皮 茯苓。",
        "score": 0.83,
    },
]


def lookup_entity(
    name: str,
    top_k: int = 12,
    predicate_allowlist: list[str] | None = None,
    predicate_blocklist: list[str] | None = None,
) -> dict[str, Any]:
    normalized = name.strip()
    if not normalized:
        return {}

    allow = {str(item).strip() for item in (predicate_allowlist or []) if str(item).strip()}
    block = {str(item).strip() for item in (predicate_blocklist or []) if str(item).strip()}

    for key, payload in ENTITY_RELATIONS.items():
        if normalized == key or normalized in key or key in normalized:
            relations = []
            for row in payload["relations"]:
                predicate = str(row.get("predicate", "")).strip()
                if allow and predicate not in allow:
                    continue
                if block and predicate in block:
                    continue
                relations.append(row)
            relations = relations[: max(1, top_k)]
            return {
                "entity": {
                    "name": normalized,
                    "canonical_name": payload["canonical_name"],
                    "entity_type": payload["entity_type"],
                },
                "relations": relations,
                "total": len(relations),
            }
    return {}


def query_path(start: str, end: str, max_hops: int = 3, path_limit: int = 5) -> dict[str, Any]:
    s = start.strip()
    e = end.strip()
    if not s or not e:
        return {"paths": [], "total": 0}

    if ("头痛" in s and "逍遥散" in e) or ("肝郁" in s and "逍遥散" in e):
        path = {
            "nodes": ["头痛", "肝郁", "疏肝解郁", "逍遥散"],
            "edges": ["表现症状", "定义治疗方案", "定义治疗方案"],
            "score": 0.87,
            "sources": [{"source_book": "金匮要略", "source_chapter": "杂病篇"}],
        }
        return {"paths": [path][: max(1, path_limit)], "total": 1}

    if "胁肋" in s and "逍遥散" in e:
        path = {
            "nodes": ["胁肋胀痛", "肝郁脾虚", "逍遥散"],
            "edges": ["表现症状", "推荐方剂"],
            "score": 0.84,
            "sources": [{"source_book": "医宗金鉴", "source_chapter": "杂病心法"}],
        }
        return {"paths": [path][: max(1, path_limit)], "total": 1}

    return {"paths": [], "total": 0}


def syndrome_chain(symptom: str, top_k: int = 5) -> dict[str, Any]:
    key = symptom.strip()
    if not key:
        return {"symptom": key, "syndromes": []}

    matched = []
    for source_key, syndromes in SYMPTOM_TO_SYNDROMES.items():
        if key == source_key or key in source_key or source_key in key:
            matched = syndromes
            break
    return {"symptom": key, "syndromes": matched[: max(1, top_k)]}


def hybrid_search(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    enable_rerank: bool = True,
) -> dict[str, Any]:
    q = query.strip()
    if not q:
        return {"retrieval_mode": "hybrid", "rerank_applied": False, "chunks": [], "total": 0}

    scored: list[dict[str, Any]] = []
    for item in MOCK_DOCS:
        score = float(item.get("score", 0.0))
        if any(token in item["text"] for token in [q, "逍遥散", "肝郁", "柴胡"] if token):
            score += 0.03
        scored.append({**item, "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    limited = scored[: max(1, top_k)]
    return {
        "retrieval_mode": "hybrid",
        "rerank_applied": bool(enable_rerank),
        "candidate_k": max(candidate_k, top_k),
        "chunks": limited,
        "total": len(limited),
    }


def rewrite_query(query: str, strategy: str = "complex") -> dict[str, Any]:
    q = query.strip()
    if not q:
        return {"strategy": strategy, "expanded_query": "", "step_back_question": "", "step_back_answer": "", "hypothetical_doc": ""}
    return {
        "strategy": strategy,
        "expanded_query": f"{q}。请结合证候、治法和方剂进行检索与解释。",
        "step_back_question": "中医辨证调理的通用原则是什么？",
        "step_back_answer": "先辨证后论治，兼顾疏肝健脾与调和气血。",
        "hypothetical_doc": f"{q} 可从证候识别、治法匹配、方剂出处三方面组织答案。",
    }


def case_qa_search(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
) -> dict[str, Any]:
    q = query.strip()
    if not q:
        return {"retrieval_mode": "case_qa_mock", "chunks": [], "total": 0}

    scored: list[dict[str, Any]] = []
    for item in MOCK_CASE_QA:
        score = float(item.get("score", 0.0))
        if any(token in item["document"] or token in item["answer"] for token in [q, "胁肋胀痛", "失眠", "口苦", "腰酸", "头晕", "耳鸣"] if token):
            score += 0.03
        scored.append(
            {
                "chunk_id": item["embedding_id"],
                "embedding_id": item["embedding_id"],
                "collection": item["collection"],
                "document": item["document"],
                "answer": item["answer"],
                "text": item["answer"],
                "source_file": f"caseqa:{item['collection']}",
                "source_page": None,
                "score": round(score, 4),
                "distance": round(max(0.0, 1.0 - score), 4),
                "rerank_score": round(score + 0.08, 4),
                "metadata": {"answer": item["answer"]},
            }
        )
    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    limited = scored[: max(1, top_k)]
    return {
        "retrieval_mode": "case_qa_mock",
        "candidate_k": max(candidate_k, top_k),
        "collection_count": len({item["collection"] for item in MOCK_CASE_QA}),
        "per_collection_k": max(1, top_k // 2),
        "chunks": limited,
        "total": len(limited),
    }
