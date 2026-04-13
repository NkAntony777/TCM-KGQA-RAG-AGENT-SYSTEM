from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

IN_SCHEMA = "in_schema"
ACCEPTABLE_POLYSEMY = "acceptable_polysemy"
REVIEW_NEEDED = "review_needed"
LIKELY_DIRTY = "likely_dirty"


@dataclass(frozen=True)
class RelationGovernanceRule:
    predicate: str
    family: str | None = None
    normalized_predicate: str | None = None
    governance_parent: str | None = None
    expected_subject_types: frozenset[str] | None = None
    expected_object_types: frozenset[str] | None = None
    lock: bool = False
    path_expand: bool = True
    bridge_allowed: bool = True
    display_only: bool = False
    priority_boost: float = 0.0


RELATION_GOVERNANCE_RULES: dict[str, RelationGovernanceRule] = {
    "治疗证候": RelationGovernanceRule(
        "治疗证候",
        family="主治族",
        expected_subject_types=frozenset({"formula", "herb", "medicine"}),
        expected_object_types=frozenset({"syndrome"}),
        priority_boost=0.06,
    ),
    "治疗疾病": RelationGovernanceRule("治疗疾病", family="主治族", priority_boost=0.05),
    "治疗症状": RelationGovernanceRule(
        "治疗症状",
        family="主治族",
        expected_subject_types=frozenset({"formula", "herb", "medicine"}),
        expected_object_types=frozenset({"symptom"}),
        priority_boost=0.04,
    ),
    "常见症状": RelationGovernanceRule("常见症状", family="临床表现族", priority_boost=0.03),
    "表现症状": RelationGovernanceRule("表现症状", family="临床表现族", priority_boost=0.03),
    "相关症状": RelationGovernanceRule("相关症状", family="临床表现族", priority_boost=0.03),
    "药性": RelationGovernanceRule("药性", family="药性理论族", priority_boost=0.02),
    "归经": RelationGovernanceRule(
        "归经",
        family="药性理论族",
        expected_subject_types=frozenset({"herb", "medicine"}),
        expected_object_types=frozenset({"channel", "property", "other"}),
        priority_boost=0.02,
    ),
    "五味": RelationGovernanceRule("五味", family="药性理论族", priority_boost=0.02),
    "药性特征": RelationGovernanceRule("药性特征", governance_parent="归经", priority_boost=0.02),
    "药材基源": RelationGovernanceRule("药材基源", normalized_predicate="拉丁学名", priority_boost=0.01),
    "使用药材": RelationGovernanceRule(
        "使用药材",
        expected_subject_types=frozenset({"formula", "medicine"}),
        expected_object_types=frozenset({"herb"}),
        priority_boost=0.06,
    ),
    "推荐方剂": RelationGovernanceRule(
        "推荐方剂",
        expected_subject_types=frozenset({"syndrome", "disease"}),
        expected_object_types=frozenset({"formula"}),
        priority_boost=0.05,
    ),
    "功效": RelationGovernanceRule("功效", path_expand=False, bridge_allowed=False, priority_boost=0.06),
    "配伍禁忌": RelationGovernanceRule("配伍禁忌", path_expand=False, bridge_allowed=False),
    "食忌": RelationGovernanceRule("食忌", path_expand=False, bridge_allowed=False, display_only=True),
    "出处": RelationGovernanceRule("出处", path_expand=False, bridge_allowed=False, display_only=True),
    "作用靶点": RelationGovernanceRule("作用靶点", lock=True),
    "含有成分": RelationGovernanceRule("含有成分", lock=True),
    "关联靶点": RelationGovernanceRule("关联靶点", lock=True),
    "现代适应证": RelationGovernanceRule("现代适应证", lock=True),
}

RELATION_FAMILIES: dict[str, set[str]] = {
    "主治族": {"治疗证候", "治疗疾病", "治疗症状"},
    "临床表现族": {"常见症状", "表现症状", "相关症状"},
    "药性理论族": {"药性", "归经", "五味"},
}

NORMALIZED_PREDICATE_TARGETS: dict[str, set[str]] = {
    "拉丁学名": {"药材基源"},
}

QUERY_HINT_TOKENS: dict[str, tuple[str, ...]] = {
    "功效": ("功效",),
    "归经": ("归经",),
    "基源": ("拉丁学名",),
    "拉丁学名": ("拉丁学名",),
    "药材": ("使用药材",),
    "配伍": ("使用药材",),
    "组成": ("使用药材",),
    "主治": ("@主治族",),
    "主证": ("@主治族",),
    "适用": ("@主治族",),
    "证候": ("@主治族", "推荐方剂"),
    "辨证": ("@主治族", "推荐方剂"),
    "症状": ("@临床表现族", "治疗症状"),
    "临床表现": ("@临床表现族",),
    "治法": ("治法",),
    "疾病": ("治疗疾病",),
    "范畴": ("属于范畴",),
    "类别": ("属于范畴",),
    "别名": ("别名",),
    "药性理论": ("@药性理论族",),
}


def _normalize_filter_token(value: str) -> str:
    token = str(value or "").strip()
    if token.startswith("@"):
        token = token[1:]
    return token


def relation_rule(predicate: str) -> RelationGovernanceRule:
    normalized = str(predicate or "").strip()
    return RELATION_GOVERNANCE_RULES.get(normalized, RelationGovernanceRule(predicate=normalized))


def governance_parent(predicate: str) -> str | None:
    return relation_rule(predicate).governance_parent


def normalized_predicate(predicate: str) -> str | None:
    return relation_rule(predicate).normalized_predicate


def relation_family(predicate: str) -> str | None:
    rule = relation_rule(predicate)
    if rule.family:
        return rule.family
    parent = rule.governance_parent
    if not parent:
        return None
    for family_name, members in RELATION_FAMILIES.items():
        if parent in members:
            return family_name
    return None


def lock_enabled(predicate: str) -> bool:
    return relation_rule(predicate).lock


def display_only(predicate: str) -> bool:
    return relation_rule(predicate).display_only


def path_expand_allowed(predicate: str) -> bool:
    return relation_rule(predicate).path_expand


def bridge_allowed(predicate: str) -> bool:
    return relation_rule(predicate).bridge_allowed


def priority_boost(predicate: str) -> float:
    return float(relation_rule(predicate).priority_boost)


def family_members(family_name: str) -> set[str]:
    return set(RELATION_FAMILIES.get(_normalize_filter_token(family_name), set()))


def expand_filter_predicates(values: Iterable[str] | None) -> set[str]:
    expanded: set[str] = set()
    pending = [_normalize_filter_token(item) for item in (values or []) if _normalize_filter_token(item)]
    seen: set[str] = set()

    while pending:
        token = pending.pop()
        if token in seen:
            continue
        seen.add(token)
        if token in RELATION_FAMILIES:
            pending.extend(sorted(RELATION_FAMILIES[token]))
            continue
        if token in NORMALIZED_PREDICATE_TARGETS:
            pending.extend(sorted(NORMALIZED_PREDICATE_TARGETS[token]))
            continue
        expanded.add(token)
        for predicate, rule in RELATION_GOVERNANCE_RULES.items():
            if rule.governance_parent == token:
                pending.append(predicate)
    return expanded


def hinted_predicates(query_text: str) -> set[str]:
    normalized_query = str(query_text or "").strip()
    hinted_tokens: list[str] = []
    for token, targets in QUERY_HINT_TOKENS.items():
        if token and token in normalized_query:
            hinted_tokens.extend(targets)
    return expand_filter_predicates(hinted_tokens)


def relation_metadata(predicate: str) -> dict[str, object]:
    rule = relation_rule(predicate)
    return {
        "predicate_family": relation_family(predicate),
        "normalized_predicate": rule.normalized_predicate,
        "governance_parent": rule.governance_parent,
        "lock": rule.lock,
        "display_only": rule.display_only,
        "path_expand_allowed": rule.path_expand,
        "bridge_allowed": rule.bridge_allowed,
    }


def _rule_matches(predicate: str, subject_type: str, object_type: str) -> bool:
    rule = relation_rule(predicate)
    if not rule.expected_subject_types or not rule.expected_object_types:
        return True
    return subject_type in rule.expected_subject_types and object_type in rule.expected_object_types


def ontology_boundary_tier(
    *,
    predicate: str,
    direction: str,
    anchor_entity_type: str,
    target_type: str,
) -> str | None:
    rule = relation_rule(predicate)
    if not rule.expected_subject_types or not rule.expected_object_types:
        return None
    anchor_type = str(anchor_entity_type or "").strip()
    other_type = str(target_type or "").strip()
    if not anchor_type or not other_type:
        return None
    normalized_direction = str(direction or "").strip().lower() or "out"
    if normalized_direction == "in":
        subject_type = other_type
        object_type = anchor_type
    else:
        subject_type = anchor_type
        object_type = other_type

    if _rule_matches(predicate, subject_type, object_type):
        return IN_SCHEMA

    if predicate == "使用药材":
        if subject_type in {"disease", "syndrome", "symptom", "therapy"} and object_type == "herb":
            return ACCEPTABLE_POLYSEMY
        if subject_type == "formula" and object_type in {"formula", "medicine"}:
            return REVIEW_NEEDED
        if subject_type in {"category", "other", "channel"} and object_type == "herb":
            return LIKELY_DIRTY
        if subject_type == "herb" and object_type in {"herb", "formula"}:
            return LIKELY_DIRTY
        return REVIEW_NEEDED

    if predicate == "归经":
        if subject_type in {"medicine", "formula", "food"} and object_type == "channel":
            return ACCEPTABLE_POLYSEMY
        if subject_type in {"disease", "syndrome", "symptom", "therapy", "other", "category", "property"} and object_type == "channel":
            return REVIEW_NEEDED
        if subject_type == "channel":
            return LIKELY_DIRTY
        return REVIEW_NEEDED

    if predicate == "推荐方剂":
        if subject_type in {"symptom", "therapy"} and object_type == "formula":
            return ACCEPTABLE_POLYSEMY
        if subject_type in {"disease", "symptom"} and object_type == "therapy":
            return REVIEW_NEEDED
        if subject_type == "formula" and object_type == "formula":
            return REVIEW_NEEDED
        if object_type in {"food", "herb"}:
            return LIKELY_DIRTY
        return REVIEW_NEEDED

    if predicate == "治疗证候":
        if subject_type in {"herb", "medicine", "therapy", "disease", "symptom"} and object_type == "syndrome":
            return ACCEPTABLE_POLYSEMY
        if subject_type == "disease" and object_type in {"formula", "therapy", "herb"}:
            return REVIEW_NEEDED
        if subject_type in {"formula", "syndrome"} and object_type in {"symptom", "syndrome", "herb"}:
            return REVIEW_NEEDED
        return LIKELY_DIRTY

    if predicate == "治疗症状":
        if subject_type in {"herb", "medicine", "therapy", "disease", "food"} and object_type == "symptom":
            return ACCEPTABLE_POLYSEMY
        if subject_type in {"channel", "syndrome", "other"} and object_type == "symptom":
            return REVIEW_NEEDED
        if subject_type == "symptom" and object_type in {"therapy", "herb", "symptom"}:
            return REVIEW_NEEDED
        return LIKELY_DIRTY

    return REVIEW_NEEDED


def ontology_boundary_ok(
    *,
    predicate: str,
    direction: str,
    anchor_entity_type: str,
    target_type: str,
) -> bool | None:
    tier = ontology_boundary_tier(
        predicate=predicate,
        direction=direction,
        anchor_entity_type=anchor_entity_type,
        target_type=target_type,
    )
    if tier is None:
        return None
    return tier == IN_SCHEMA
