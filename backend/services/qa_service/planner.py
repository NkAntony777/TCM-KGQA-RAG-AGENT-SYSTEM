from __future__ import annotations

from typing import Any

from services.qa_service.models import ALLOWED_PLANNER_GAPS
from services.qa_service.skill_registry import RuntimeSkill

def _normalize_gap_names(raw_gaps: list[Any]) -> list[str]:
    allowed = set(ALLOWED_PLANNER_GAPS)
    normalized: list[str] = []
    for item in raw_gaps:
        gap = str(item or "").strip()
        if gap and gap in allowed and gap not in normalized:
            normalized.append(gap)
    return normalized


def _normalize_planner_actions(*, planner_skills: dict[str, RuntimeSkill], raw_actions: list[Any], query: str, payload: dict[str, Any], evidence_paths: list[str], executed_actions: set[str], max_actions: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        action = dict(raw)
        skill = str(action.get("skill", "")).strip()
        skill_meta = planner_skills.get(skill) if skill else None
        if skill and skill_meta and not action.get("tool"):
            action["tool"] = skill_meta.primary_tool
        if skill and skill_meta is None:
            continue
        if not action.get("tool"):
            continue
        if skill_meta is not None:
            action.setdefault("skill_description", skill_meta.description)
            action.setdefault("output_focus", list(skill_meta.output_focus[:4]))
            action.setdefault("stop_rules", list(skill_meta.stop_rules[:2]))
            action.setdefault("preferred_paths", list(skill_meta.preferred_path_patterns[:2]))
        action.setdefault("query", query)
        action.setdefault("top_k", 6)
        if skill == "read-formula-composition":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "read-formula-origin":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
            action["query"] = str(action.get("query") or f"{query} 出处 原文")
        if skill == "compare-formulas":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "find-case-reference":
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith("caseqa://")])
        if skill == "search-source-text":
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith(("book://", "qa://"))])
            action["query"] = str(action.get("query") or f"{query} 出处 古籍 原文")
        if skill == "trace-source-passage":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith(("book://", "qa://"))])
            action["query"] = str(action.get("query") or f"{query} 古籍出处 原文 佐证")
        if skill == "read-syndrome-treatment":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "trace-graph-path":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
        if skill == "search-source-text":
            action.setdefault("path", _preferred_path_for_skill(skill=skill, payload=payload, evidence_paths=evidence_paths))
            action.setdefault("scope_paths", [path for path in evidence_paths if path.startswith(("book://", "qa://"))])
        if str(action.get("tool", "")) == "read_evidence_path" and not str(action.get("path", "")).strip():
            continue
        key = _action_key(action)
        if key in executed_actions:
            continue
        normalized.append(action)
        if len(normalized) >= max_actions:
            break
    return normalized


def _apply_origin_action_policy(*, planner_skills: dict[str, RuntimeSkill], query: str, payload: dict[str, Any], evidence_paths: list[str], gaps: list[str], actions: list[dict[str, Any]], max_actions: int, executed_actions: set[str]) -> list[dict[str, Any]]:
    if "origin" not in gaps:
        return actions[:max_actions]

    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    graph_source_books = _top_graph_source_books(factual_evidence=payload.get("_planner_factual_evidence", []))
    corrected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def append_action(candidate: dict[str, Any]) -> None:
        if len(corrected) >= max_actions:
            return
        key = _action_key(candidate)
        if key in executed_actions or key in seen_keys:
            return
        corrected.append(candidate)
        seen_keys.add(key)

    def is_origin_book_action(candidate: dict[str, Any]) -> bool:
        return (
            str(candidate.get("skill", "")).strip() == "read-formula-origin"
            and str(candidate.get("path", "")).strip().startswith("book://")
        )

    if entity_name and not graph_source_books:
        append_action(
            _build_skill_action(
                planner_skills=planner_skills,
                skill_name="read-formula-origin",
                path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") or f"entity://{entity_name}/*",
                query=f"{entity_name} 出处 原文",
                top_k=6,
                reason="先从实体级证据锁定来源书名与篇章",
            )
        )
        for action in actions:
            if is_origin_book_action(action):
                continue
            append_action(action)
        return corrected[:max_actions]

    if graph_source_books:
        for source_book in graph_source_books[:2]:
            append_action(
                _build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=f"book://{source_book}/*",
                    query=f"{entity_name or query} 出处 原文",
                    top_k=4,
                    reason=f"根据实体证据已定位来源书目，继续追 {source_book} 的原文片段",
                )
            )
        for action in actions:
            path = str(action.get("path", "")).strip()
            if is_origin_book_action(action) and not any(path == f"book://{book}/*" for book in graph_source_books):
                continue
            append_action(action)
        return corrected[:max_actions]

    return actions[:max_actions]


def _preferred_path_for_skill(*, skill: str, payload: dict[str, Any], evidence_paths: list[str]) -> str:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    symptom_name = str(strategy.get("symptom_name", "")).strip()
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    if skill == "read-formula-composition" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="使用药材") or f"entity://{entity_name}/使用药材"
    if skill == "read-formula-origin":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://")) or (f"book://{entity_name}/*" if entity_name else "")
    if skill == "compare-formulas" and compare_entities:
        entity = compare_entities[0]
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity}/", suffix="*") or f"entity://{entity}/*"
    if skill == "compare-formulas" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") or f"entity://{entity_name}/*"
    if skill == "read-syndrome-treatment" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="治法") or f"entity://{entity_name}/治法"
    if skill == "trace-graph-path" and symptom_name:
        return _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
    if skill == "trace-graph-path" and entity_name:
        return _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="推荐方剂") or f"entity://{entity_name}/推荐方剂"
    if skill == "find-case-reference":
        return _pick_first_matching_path(evidence_paths, prefixes=("caseqa://",))
    if skill == "search-source-text":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
    if skill == "trace-source-passage":
        return _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
    if skill == "read-formula-origin" and symptom_name:
        return _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
    return ""


def _build_skill_action(
    *,
    planner_skills: dict[str, RuntimeSkill],
    skill_name: str,
    query: str,
    reason: str,
    path: str = "",
    scope_paths: list[str] | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    skill_meta = planner_skills.get(skill_name)
    tool_name = skill_meta.primary_tool if skill_meta is not None else ""
    action: dict[str, Any] = {
        "skill": skill_name,
        "tool": tool_name,
        "query": query,
        "top_k": top_k,
        "reason": reason,
    }
    if path:
        action["path"] = path
    if scope_paths:
        action["scope_paths"] = scope_paths
    return action


def _plan_followup_actions(*, planner_skills: dict[str, RuntimeSkill], query: str, payload: dict[str, Any], evidence_paths: list[str], gaps: list[str], max_actions: int, executed_actions: set[str]) -> list[dict[str, Any]]:
    strategy = payload.get("retrieval_strategy", {}) if isinstance(payload.get("retrieval_strategy"), dict) else {}
    analysis = payload.get("query_analysis", {}) if isinstance(payload.get("query_analysis"), dict) else {}
    entity_name = str(strategy.get("entity_name", "")).strip()
    symptom_name = str(strategy.get("symptom_name", "")).strip()
    compare_entities = strategy.get("compare_entities", analysis.get("compare_entities", []))
    compare_entities = [str(item).strip() for item in compare_entities if str(item).strip()] if isinstance(compare_entities, list) else []
    actions: list[dict[str, Any]] = []

    def add_action(candidate: dict[str, Any]) -> None:
        if len(actions) >= max_actions:
            return
        if _action_key(candidate) in executed_actions:
            return
        actions.append(candidate)

    if "composition" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="read-formula-composition",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="使用药材") or f"entity://{entity_name}/使用药材",
            query=query,
            top_k=6,
            reason="补充方剂组成证据",
        ))
    if "efficacy" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="read-syndrome-treatment",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="功效") or f"entity://{entity_name}/功效",
            query=query,
            top_k=6,
            reason="补充功效证据",
        ))
    if "indication" in gaps and entity_name:
        add_action(_build_skill_action(
            planner_skills=planner_skills,
            skill_name="read-syndrome-treatment",
            path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="治疗证候") or f"entity://{entity_name}/治疗证候",
            query=query,
            top_k=6,
            reason="补充主治证候证据",
        ))
    if "syndrome_formula" in gaps:
        target_path = ""
        if symptom_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
        elif entity_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="推荐方剂") or f"entity://{entity_name}/推荐方剂"
        if target_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="trace-graph-path",
                path=target_path,
                query=query,
                top_k=6,
                reason="补充证候到方剂映射",
            ))
    if "comparison" in gaps and compare_entities:
        for entity in compare_entities[:2]:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="compare-formulas",
                path=_pick_existing_path(evidence_paths, prefix=f"entity://{entity}/", suffix="*") or f"entity://{entity}/*",
                query=query,
                top_k=6,
                reason=f"补充比较对象 {entity} 的证据",
            ))
        if len(actions) < max_actions:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="search-source-text",
                query=f"{query} 古籍 教材 出处",
                scope_paths=[path for path in evidence_paths if path.startswith(("qa://", "book://"))],
                top_k=4,
                reason="补充比较问题的文献出处",
            ))
    if "path_reasoning" in gaps:
        target_path = ""
        if symptom_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"symptom://{symptom_name}/", suffix="syndrome_chain") or f"symptom://{symptom_name}/syndrome_chain"
        elif entity_name:
            target_path = _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="推荐方剂") or f"entity://{entity_name}/推荐方剂"
        elif evidence_paths:
            target_path = evidence_paths[0]
        if target_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="trace-graph-path",
                path=target_path,
                query=query,
                top_k=6,
                reason="补充链路或辨证路径证据",
            ))
        if len(actions) < max_actions:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="trace-source-passage",
                path=_pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://")),
                query=f"{query} 古籍出处 佐证",
                top_k=4,
                reason="为链路结论补充可引用出处",
            ))
    if "origin" in gaps:
        graph_source_books = _top_graph_source_books(factual_evidence=payload.get("_planner_factual_evidence", []))
        entity_origin_path = _pick_existing_path(evidence_paths, prefix=f"entity://{entity_name}/", suffix="*") if entity_name else ""
        if entity_name and not graph_source_books:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="read-formula-origin",
                path=entity_origin_path or f"entity://{entity_name}/*",
                query=f"{entity_name} 出处 原文",
                top_k=6,
                reason="先从实体级证据锁定来源书名与篇章",
            ))
        elif graph_source_books:
            for source_book in graph_source_books[:2]:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=f"book://{source_book}/*",
                    query=f"{entity_name or query} 出处 原文",
                    top_k=4,
                    reason=f"根据实体证据已定位来源书目，继续追 {source_book} 的原文片段",
                ))
        else:
            origin_path = _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
            if origin_path:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="read-formula-origin",
                    path=origin_path,
                    query=f"{query} 出处 原文",
                    top_k=4,
                    reason="补充出处或原文证据",
                ))
            else:
                add_action(_build_skill_action(
                    planner_skills=planner_skills,
                    skill_name="search-source-text",
                    query=f"{query} 出处 古籍 原文 教材",
                    scope_paths=[path for path in evidence_paths if path.startswith(("qa://", "book://"))],
                    top_k=4,
                    reason="补充出处或原文证据",
                ))
        if len(actions) < max_actions and any(marker in query for marker in ("原文", "原句", "原话", "佐证")):
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="trace-source-passage",
                path=_pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://")),
                query=f"{query} 古籍出处 原文 佐证",
                top_k=4,
                reason="补充更适合展示给用户的出处片段",
            ))
    if "source_trace" in gaps:
        trace_path = _pick_first_matching_path(evidence_paths, prefixes=("book://", "qa://"))
        if trace_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="trace-source-passage",
                path=trace_path,
                query=f"{query} 古籍出处 原文 佐证",
                top_k=4,
                reason="补充书名、篇章和可引用片段",
            ))
        else:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="search-source-text",
                query=f"{query} 古籍出处 原文 佐证",
                scope_paths=[path for path in evidence_paths if path.startswith(("qa://", "book://"))],
                top_k=4,
                reason="补充书名、篇章和可引用片段",
            ))
    if "case_reference" in gaps:
        case_path = _pick_first_matching_path(evidence_paths, prefixes=("caseqa://",))
        if case_path:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="find-case-reference",
                path=case_path,
                query=query,
                top_k=3,
                reason="补充相似案例参考",
            ))
        else:
            add_action(_build_skill_action(
                planner_skills=planner_skills,
                skill_name="find-case-reference",
                query=query,
                scope_paths=["caseqa://query/similar"],
                top_k=3,
                reason="补充相似案例参考",
            ))
    return actions[:max_actions]


def _pick_existing_path(paths: list[str], *, prefix: str, suffix: str) -> str:
    for path in paths:
        if path.startswith(prefix) and (suffix == "*" or path.endswith(suffix) or path.endswith("/*")):
            return path
    return ""


def _pick_first_matching_path(paths: list[str], *, prefixes: tuple[str, ...]) -> str:
    for path in paths:
        if path.startswith(prefixes):
            return path
    return ""


def _action_key(action: dict[str, Any]) -> str:
    scope = action.get("scope_paths", [])
    scope_text = "|".join(str(item).strip() for item in scope) if isinstance(scope, list) else ""
    return "::".join([str(action.get("skill", "")).strip(), str(action.get("tool", "")).strip(), str(action.get("path", "")).strip(), str(action.get("query", "")).strip(), scope_text])


def _top_graph_source_books(*, factual_evidence: list[dict[str, Any]]) -> list[str]:
    books: list[str] = []
    seen = set()
    for item in factual_evidence:
        if str(item.get("source_type", "")).strip() != "graph":
            continue
        source_book = str(item.get("source_book", "")).strip()
        if not source_book or source_book in seen:
            continue
        seen.add(source_book)
        books.append(source_book)
    return books


