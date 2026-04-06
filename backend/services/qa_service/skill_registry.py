from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml

from config import get_settings

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
HEADING_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$")
CODE_PATTERN = re.compile(r"`([^`]+)`")

DEFAULT_SKILL_TOOL_MAP: dict[str, str] = {
    "route-tcm-query": "tcm_route_search",
    "read-formula-composition": "read_evidence_path",
    "read-formula-origin": "read_evidence_path",
    "read-syndrome-treatment": "read_evidence_path",
    "trace-graph-path": "read_evidence_path",
    "compare-formulas": "read_evidence_path",
    "find-case-reference": "search_evidence_text",
    "search-source-text": "search_evidence_text",
    "trace-source-passage": "search_evidence_text",
    "external-source-verification": "web_search",
}


@dataclass(frozen=True)
class RuntimeSkill:
    name: str
    description: str
    path: str
    preferred_tools: tuple[str, ...]
    workflow_steps: tuple[str, ...]
    output_focus: tuple[str, ...]
    stop_rules: tuple[str, ...]
    trigger_phrases: tuple[str, ...] = ()
    preferred_path_patterns: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()

    @property
    def primary_tool(self) -> str:
        if self.preferred_tools:
            return self.preferred_tools[0]
        return DEFAULT_SKILL_TOOL_MAP.get(self.name, "")


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1)) or {}
    return {str(key): value for key, value in data.items()}


def _split_body(text: str) -> str:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return text
    return text[match.end() :]


def _collect_section_lines(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in body.splitlines():
        heading = HEADING_PATTERN.match(raw_line.strip())
        if heading:
            current = heading.group("title").strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(raw_line.rstrip())
    return sections


def _clean_items(lines: list[str]) -> tuple[str, ...]:
    items: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line[:2] in {"- ", "* "}:
            line = line[2:].strip()
        if re.match(r"^\d+\.\s+", line):
            line = re.sub(r"^\d+\.\s+", "", line).strip()
        if line:
            items.append(line)
    return tuple(items)


def _clean_values(values: Iterable[Any]) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            items.append(text)
    return tuple(items)


def _extract_tools(lines: list[str]) -> tuple[str, ...]:
    tools: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        matches = CODE_PATTERN.findall(line)
        if matches:
            tools.extend(match.strip() for match in matches if match.strip())
            continue
        if line[:2] in {"- ", "* "}:
            tools.append(line[2:].strip())
    deduped: list[str] = []
    seen = set()
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            deduped.append(tool)
    return tuple(deduped)


def _parse_skill_file(base_dir: Path, skill_file: Path) -> RuntimeSkill:
    text = skill_file.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    body = _split_body(text)
    sections = _collect_section_lines(body)
    name = meta.get("name", skill_file.parent.name)
    description = str(meta.get("description", ""))
    preferred_tools = _extract_tools(sections.get("preferred tools", []))
    workflow_steps = _clean_items(sections.get("workflow", []))
    output_focus = _clean_items(sections.get("output focus", []))
    stop_rules = _clean_items(sections.get("stop rule", []))
    trigger_phrases = _clean_items(sections.get("trigger phrases", [])) or _clean_values(meta.get("trigger_phrases", []))
    preferred_path_patterns = _clean_items(sections.get("preferred paths", [])) or _clean_values(meta.get("preferred_paths", []))
    examples = _clean_items(sections.get("examples", [])) or _clean_values(meta.get("examples", []))
    if not preferred_tools and name in DEFAULT_SKILL_TOOL_MAP:
        preferred_tools = (DEFAULT_SKILL_TOOL_MAP[name],)
    return RuntimeSkill(
        name=name,
        description=description,
        path=str(skill_file.relative_to(base_dir)).replace("\\", "/"),
        preferred_tools=preferred_tools,
        workflow_steps=workflow_steps,
        output_focus=output_focus,
        stop_rules=stop_rules,
        trigger_phrases=trigger_phrases,
        preferred_path_patterns=preferred_path_patterns,
        examples=examples,
    )


@lru_cache(maxsize=1)
def _get_all_runtime_skills() -> dict[str, RuntimeSkill]:
    base_dir = get_settings().backend_dir
    skills_dir = base_dir / "skills"
    skills: dict[str, RuntimeSkill] = {}
    if not skills_dir.exists():
        return skills
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        skill = _parse_skill_file(base_dir, skill_file)
        skills[skill.name] = skill
    return skills


def get_runtime_skills(*, executable_only: bool = False, allowed_tools: set[str] | None = None) -> dict[str, RuntimeSkill]:
    skills = dict(_get_all_runtime_skills())
    if not executable_only:
        return skills
    tool_allowlist = allowed_tools or {"read_evidence_path", "search_evidence_text", "tcm_route_search", "list_evidence_paths"}
    return {
        name: skill
        for name, skill in skills.items()
        if skill.primary_tool in tool_allowlist
    }


def clear_runtime_skills_cache() -> None:
    _get_all_runtime_skills.cache_clear()
