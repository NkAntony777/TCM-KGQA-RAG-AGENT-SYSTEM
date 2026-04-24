"""Prompt construction for triple extraction."""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterable


FORMULA_TITLE_SUFFIXES = ("汤", "丸", "散", "饮", "丹", "方", "膏", "煎")


def detect_formula_titles(text: str, limit: int = 12) -> list[str]:
    titles: list[str] = []
    lines = [line.strip() for line in (text or "").splitlines()]
    for index, line in enumerate(lines):
        if not line:
            continue
        if line.startswith("卷") or line.startswith("属性：") or len(line) > 24:
            continue
        if not any(line.endswith(suffix) for suffix in FORMULA_TITLE_SUFFIXES):
            continue
        lookahead = lines[index + 1 : index + 5]
        if not any(item.startswith("属性：") for item in lookahead):
            continue
        if line in titles:
            continue
        titles.append(line)
        if len(titles) >= limit:
            break
    return titles


def _triple_schema(
    subject_label: str,
    object_label: str,
    source_label: str,
) -> dict[str, list[dict[str, object]]]:
    entity_types = (
        "formula|herb|syndrome|symptom|disease|therapy|channel|category|book|chapter|"
        "food|medicine|processing_method|property|other"
    )
    return {
        "triples": [
            {
                "subject": subject_label,
                "predicate": "关系词",
                "object": object_label,
                "subject_type": entity_types,
                "object_type": entity_types,
                "source_text": source_label,
                "confidence": 0.0,
            }
        ]
    }


def build_prompt(
    *,
    book_name: str,
    chapter_name: str,
    text_chunk: str,
    allowed_relations: Iterable[str],
) -> str:
    schema = _triple_schema("实体名称", "实体名称或概念", "对应原文短句")
    formula_titles = detect_formula_titles(text_chunk)
    formula_hint_block = ""
    if formula_titles:
        title_lines = "\n".join(f"- {title}" for title in formula_titles)
        formula_hint_block = (
            "本 chunk 中按文本结构检测到的候选方剂标题（请逐个检查，不要遗漏）：\n"
            f"{title_lines}\n"
        )
    format_example_block = textwrap.dedent(
        """
        格式约束：
        1. 只输出一个 JSON 对象，顶层必须是 {"triples":[...]}。
        2. 不要输出多个 JSON 对象，不要把每条三元组拆成多个独立 JSON 反复输出。
        3. 不要输出 Markdown 代码块，不要输出解释、分析、说明。

        正确示例：
        {
          "triples": [
            {
              "subject": "桂枝汤",
              "predicate": "治疗证候",
              "object": "太阳中风证",
              "subject_type": "formula",
              "object_type": "syndrome",
              "source_text": "桂枝汤主太阳中风证",
              "confidence": 0.95
            },
            {
              "subject": "桂枝汤",
              "predicate": "使用药材",
              "object": "桂枝",
              "subject_type": "formula",
              "object_type": "herb",
              "source_text": "桂枝汤用桂枝三两",
              "confidence": 0.93
            },
            {
              "subject": "附子",
              "predicate": "药性",
              "object": "大热",
              "subject_type": "medicine",
              "object_type": "property",
              "source_text": "附子大热，纯阳有毒",
              "confidence": 0.91
            }
          ]
        }

        错误示例：
        {"subject":"桂枝汤","predicate":"治疗证候","object":"太阳中风证"}
        {"triples":[...]}
        {"triples":[...]}

        另一个错误示例：
        {
          "triples": [
            {
              "subject": "本方",
              "predicate": "使用药材",
              "object": "甘草",
              "source_text": "甘草"
            }
          ]
        }
        上例中的“本方”属于泛指主语。若上下文能确定具体方名，必须改写为具体方名；若无法唯一确定，则不要输出该条。

        source_text 错误示例：
        {
          "triples": [
            {
              "subject": "桂枝汤",
              "predicate": "使用药材",
              "object": "桂枝",
              "source_text": "桂枝"
            }
          ]
        }
        上例中的 source_text 只保留了孤立词语，证据过短。应至少保留能体现主语或关系成立的原文片段，例如“桂枝汤用桂枝三两”。
        """
    ).strip()
    return textwrap.dedent(
        f"""
        你是中医古籍三元组抽取器。请从给定文本中抽取可入图谱的事实。

        书名：{book_name}
        章节：{chapter_name}

        关系标准优先使用以下集合：
        {sorted(allowed_relations)}

        {formula_hint_block}
        {format_example_block}

        允许你先按原文抽取，再做轻度归一化，但最终输出的 predicate 应尽量落在上述集合。
        如果无法判断，请不要编造。

        输出必须是 JSON 对象，格式如下：
        {json.dumps(schema, ensure_ascii=False, indent=2)}

        规则：
        1. 只抽取文本里明确出现或强明示的事实。
        2. source_text 必须是原文短句或原文片段，不要改写成长解释。
        3. confidence 取 0 到 1 之间的小数。
        4. 不要输出任何 JSON 之外的说明文字。
        5. 若没有合适三元组，返回 {{"triples":[]}}。
        6. 同一个 chunk 中如果出现多个方名/药名/证候块，必须继续向后抽取，不要只返回第一条或最显眼的一条。
        7. 若出现“方名 + 属性/组成/评语”结构，优先覆盖每个方名块；每个方名块至少尝试抽取“属于范畴 / 使用药材 / 功效 / 治疗证候 / 治疗症状 / 别名”中原文明确出现的事实。
        8. 不要只抽取“出处”这类书目信息；只有在缺乏更有价值的领域事实时，才保留出处。
        9. 如果同一 chunk 里有多个连续方剂条目，输出应覆盖所有能识别出的条目，而不是只挑一个示例。
        10. 先在脑中完整扫描全文，再一次性输出结果；禁止因为看到了第一个方名就停止抽取后文。
        11. 如果 chunk 中出现多个方剂标题，例如“某某丸 / 某某汤 / 某某散 / 某某饮 / 某某丹”，通常应为每个标题至少抽取 1 到 3 条事实；若只输出 1 条，通常说明漏抽。
        12. 遇到“卷X\\某某之剂 + 方名 + 属性：...”的结构时：
            卷名/某某之剂通常对应“属于范畴”
            属性中的药物列表通常对应“使用药材”
            紧随其后的评语通常对应“功效 / 治疗证候 / 治疗症状 / 治法”
        13. 只要原文中出现了明确药物名，不要省略“使用药材”关系；这类关系是优先级最高的抽取目标之一。
        14. 优先输出高信息量的领域事实，少输出低价值的“出处”；如果一个方名块里已经能抽到药材、功效、证候，就不要只给出处。
        15. 输出前自检：确认是否已经覆盖 chunk 内每个可识别的方名块；若没有，继续补充后再输出。
        16. 若文本是本草、药性、食疗、炮制或禁忌类内容，不要强行套用“方剂-证候”模板；应优先抽取“食忌 / 配伍禁忌 / 用法 / 药性 / 五味 / 升降浮沉”等关系。
        17. 当对象是寒热温凉、甘辛酸苦咸、升降浮沉、有毒无毒等性质词时，object_type 优先标为 property。
        18. 当对象是炒、炙、煅、煨、蒸、煮、焙、酒浸、水煎、丸服、散服、外敷等加工或服用方式时，object_type 优先标为 processing_method。
        19. 当主语或宾语是食物禁忌对象时可使用 food；当是一般药物名但不必细分时可使用 medicine。
        20. subject 和 object 必须尽量使用具体实体名，如具体方名、药名、食物名、证候名、症状名；不要偷懒写成“本方 / 此方 / 治方 / 其方 / 该方 / 本药 / 此药 / 其药 / 药 / 诸药”等泛指词。
        21. 如果原文出现“本方 / 此方 / 其方 / 其药 / 该药”等指代，必须结合上下文回指到唯一的具体方名或药名后再输出；若不能唯一回指，则宁可不抽，也不要输出泛主语三元组。
        22. 对“使用药材 / 用法 / 药性 / 五味 / 升降浮沉 / 配伍禁忌 / 食忌”这类关系，若原文能定位到具体药物或具体方剂，subject 不得写成“药 / 本方 / 治方”等笼统名称。
        23. source_text 不能只截取一个孤立词语；至少保留能支撑该关系成立的最短原文片段。若只写“甘草”“人参”这类单词，通常说明证据片段过短。
        24. 若一个 chunk 中包含多个具体方名或药名，不要把它们合并概括为一个笼统主语；应分别挂到各自的具体实体上。
        25. 对“使用药材 / 药性 / 五味 / 用法 / 食忌 / 配伍禁忌”这类关系，source_text 优先包含主语名 + 关系触发词或性质词，不要只截对象本身。

        原文：
        {text_chunk}
        """
    ).strip()


def build_compact_prompt(
    *,
    book_name: str,
    chapter_name: str,
    text_chunk: str,
    allowed_relations: Iterable[str],
) -> str:
    schema = _triple_schema("实体名", "实体名或概念", "原文短句")
    formula_titles = detect_formula_titles(text_chunk)
    title_hint = ""
    if formula_titles:
        title_hint = "候选方剂标题：" + "、".join(formula_titles[:12])
    format_hint = textwrap.dedent(
        """
        输出时只允许返回一个 JSON 对象，格式固定为 {"triples":[...]}。
        不要输出多个 JSON 对象，不要追加解释，不要使用 Markdown 代码块。
        如果有多条三元组，必须全部放在同一个 triples 数组里。

        source_text 正确示例：
        "source_text": "桂枝汤用桂枝三两"
        source_text 错误示例：
        "source_text": "桂枝"
        """
    ).strip()
    return textwrap.dedent(
        f"""
        任务：从中医古籍片段中尽可能完整抽取三元组，返回且仅返回 JSON 对象。
        书名：{book_name}
        章节：{chapter_name}
        {title_hint}
        {format_hint}

        关系优先使用：{sorted(allowed_relations)}
        重点：如果一个 chunk 内出现多个方剂标题或多个条目，必须覆盖所有可识别条目，不要只返回第一条。
        如果原文出现明确药物名，优先抽取“使用药材”。
        如果文本更像本草/禁忌/药性/炮制说明，优先抽取“食忌 / 配伍禁忌 / 用法 / 药性 / 五味 / 升降浮沉”。
        主语和宾语优先写具体方名、药名、食物名，不要写“本方 / 此方 / 治方 / 药 / 其药”等泛指词；能回指就回指，不能唯一回指就不要输出。
        source_text 不要只保留单个词，至少保留能支撑关系判断的原文短片段。
        对“使用药材 / 药性 / 五味 / 用法 / 食忌 / 配伍禁忌”，source_text 最好同时带上主语名或关系判断依据，不要只写对象词。
        如果没有可抽取事实，返回 {{"triples":[]}}。

        输出格式：
        {json.dumps(schema, ensure_ascii=False, indent=2)}

        原文：
        {text_chunk}
        """
    ).strip()


def build_prompt_variant(
    *,
    book_name: str,
    chapter_name: str,
    text_chunk: str,
    allowed_relations: Iterable[str],
    variant: str = "current",
) -> str:
    normalized_variant = (variant or "current").strip().lower()
    if normalized_variant == "compact":
        return build_compact_prompt(
            book_name=book_name,
            chapter_name=chapter_name,
            text_chunk=text_chunk,
            allowed_relations=allowed_relations,
        )
    return build_prompt(
        book_name=book_name,
        chapter_name=chapter_name,
        text_chunk=text_chunk,
        allowed_relations=allowed_relations,
    )
