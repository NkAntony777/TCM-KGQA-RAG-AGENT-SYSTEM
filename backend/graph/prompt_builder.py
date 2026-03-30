from __future__ import annotations

from pathlib import Path

from config import get_settings

SYSTEM_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("Skills Snapshot", "SKILLS_SNAPSHOT.md"),
    ("Soul", "workspace/SOUL.md"),
    ("Identity", "workspace/IDENTITY.md"),
    ("User Profile", "workspace/USER.md"),
    ("Agents Guide", "workspace/AGENTS.md"),
    ("Long-term Memory", "memory/MEMORY.md"),
)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _read_component(base_dir: Path, relative_path: str, limit: int) -> str:
    path = base_dir / relative_path
    if not path.exists():
        return f"[missing component: {relative_path}]"
    return _truncate(path.read_text(encoding="utf-8"), limit)


def build_system_prompt(base_dir: Path, rag_mode: bool) -> str:
    settings = get_settings()
    parts: list[str] = []

    for label, relative_path in SYSTEM_COMPONENTS:
        if rag_mode and relative_path == "memory/MEMORY.md":
            parts.append(
                "<!-- Long-term Memory -->\n"
                "长期记忆将通过检索动态注入。你应优先使用当次检索到的 MEMORY 片段，"
                "不要假设未检索到的记忆仍然有效。"
            )
            continue

        content = _read_component(base_dir, relative_path, settings.component_char_limit)
        parts.append(f"<!-- {label} -->\n{content}")

    parts.append(
        “<!-- Runtime Answering Rules -->\n”
        “你是面向用户的中医知识问答助手。\n”
        “1. 工具返回的 JSON、字典、trace_id、code、message、raw payload 仅供你内部使用，绝不能原样输出给用户。\n”
        “2. 你必须把工具结果整理成自然中文答案；优先直接回答问题，再补充证据来源。\n”
        “3. 回答结构尽量简洁，可使用短段落或一级列表；不要复述工具调用过程，不要说”让我再查询”。\n”
        “4. 引用证据时仅保留必要来源信息，例如”《医方集解》12页”或”《本草纲目》87页”。\n”
        “5. 若证据不足或发生降级，明确说明依据有限，但仍不要输出原始 JSON。\n”
        “6. 【医疗边界】本系统仅提供中医历史文献检索，不得提供个体化诊断、具体用药剂量或替代正规医疗的建议。”
        “当用户问题涉及急症、具体服药量、停药、替代西医治疗等场景时，”
        “必须明确说明超出服务范围，并建议就医。”
    )

    return "\n\n".join(parts)
