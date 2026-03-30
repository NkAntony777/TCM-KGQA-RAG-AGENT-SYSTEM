"""
medical_guard.py  —  S4 医疗边界策略
功能：
  1. 高风险关键词检测：检测查询是否涉及急症、替代治疗、投药剂量等高风险场景。
  2. 免责声明生成：在回答末尾附加可追踪的免责声明块。
  3. 拒答模板：对极高风险问题直接返回拒答文本，不再继续路由。

设计原则：
  - 规则驱动，不依赖 LLM 判断，延迟 < 1ms。
  - 免责声明仅附加，不修改工具调用流程；拒答在 Agent 入口前拦截。
  - 所有关键词组和规则在本文件集中维护，便于审计。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"       # 附加免责声明，继续回答
    HIGH_RISK = "high_risk"   # 附加免责声明 + 强烈建议就医


# ---------------------------------------------------------------------------
# 关键词规则表
# ---------------------------------------------------------------------------

# 极高风险：直接拒答，不继续路由
_REFUSE_PATTERNS: tuple[str, ...] = (
    "剂量",
    "每次吃几",
    "吃几克",
    "吃多少",
    "用量",
    "几毫克",
    "几片",
    "自己配药",
    "自己开方",
    "替代西药",
    "替代胰岛素",
    "停止服药",
    "停药",
    "不用看医生",
    "不需要看医生",
    "自行诊断",
)

# 高风险：附加免责声明 + 强烈建议就医
_HIGH_RISK_PATTERNS: tuple[str, ...] = (
    "急性",
    "急救",
    "中毒",
    "抢救",
    "休克",
    "昏迷",
    "大出血",
    "骨折",
    "心肌梗死",
    "脑梗",
    "脑出血",
    "癌症",
    "恶性肿瘤",
    "化疗",
    "手术前",
    "手术后",
    "孕妇",
    "哺乳期",
    "新生儿",
    "婴儿",
    "儿童用药",
    "糖尿病",
    "高血压",
    "心脏病",
    "肾衰",
    "肝衰",
    "传染病",
    "新冠",
)

# 谨慎：附加标准免责声明
_CAUTION_PATTERNS: tuple[str, ...] = (
    "治疗",
    "用药",
    "服药",
    "药方",
    "方剂",
    "处方",
    "煎服",
    "服法",
    "副作用",
    "禁忌",
    "不良反应",
    "配伍禁忌",
    "毒性",
)

# ---------------------------------------------------------------------------
# 免责声明文本
# ---------------------------------------------------------------------------

DISCLAIMER_STANDARD = (
    "\n\n---\n"
    "⚠️ **中医知识声明**：本回答仅供学习参考，不构成医疗建议。"
    "中医诊疗应在有执照的医师指导下进行，请勿自行用药。"
)

DISCLAIMER_HIGH_RISK = (
    "\n\n---\n"
    "🚨 **重要医疗声明**：您提及的情况涉及需要专业医疗判断的高风险场景。"
    "本系统仅提供中医历史文献知识，无法替代执业医师的诊断与治疗方案。"
    "请立即就医或拨打急救电话，不要仅依靠本工具的信息做出医疗决策。"
)

REFUSE_RESPONSE = (
    "非常抱歉，您的问题涉及具体用药剂量、替代处方或自行停药等高风险医疗决策，"
    "超出本系统的服务范围。\n\n"
    "本系统仅提供中医古籍文献中的知识检索与图谱查询，不能提供个体化用药方案。\n\n"
    "请向有执照的中医师或医疗机构咨询，以保障您的健康与安全。"
)


# ---------------------------------------------------------------------------
# 评估结果
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    risk_level: RiskLevel
    matched_patterns: list[str] = field(default_factory=list)
    should_refuse: bool = False
    disclaimer: str = ""
    refuse_response: str = ""


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def assess_query(query: str) -> GuardResult:
    """
    评估一条用户查询的医疗风险等级。

    Returns:
        GuardResult with:
          - risk_level: SAFE / CAUTION / HIGH_RISK
          - should_refuse: True 时直接返回 refuse_response 给用户
          - disclaimer: 追加到回答末尾的免责声明（空字符串表示无需追加）
          - refuse_response: should_refuse=True 时的完整拒答文本
    """
    text = (query or "").strip()
    matched: list[str] = []

    # 拒答检查（优先级最高）
    for pattern in _REFUSE_PATTERNS:
        if pattern in text:
            matched.append(pattern)
    if matched:
        return GuardResult(
            risk_level=RiskLevel.HIGH_RISK,
            matched_patterns=matched,
            should_refuse=True,
            disclaimer=DISCLAIMER_HIGH_RISK,
            refuse_response=REFUSE_RESPONSE,
        )

    # 高风险检查
    for pattern in _HIGH_RISK_PATTERNS:
        if pattern in text:
            matched.append(pattern)
    if matched:
        return GuardResult(
            risk_level=RiskLevel.HIGH_RISK,
            matched_patterns=matched,
            should_refuse=False,
            disclaimer=DISCLAIMER_HIGH_RISK,
        )

    # 谨慎检查
    for pattern in _CAUTION_PATTERNS:
        if pattern in text:
            matched.append(pattern)
    if matched:
        return GuardResult(
            risk_level=RiskLevel.CAUTION,
            matched_patterns=matched,
            should_refuse=False,
            disclaimer=DISCLAIMER_STANDARD,
        )

    return GuardResult(risk_level=RiskLevel.SAFE)


def append_disclaimer(answer: str, disclaimer: str) -> str:
    """将免责声明追加到回答末尾（已有声明时不重复追加）。"""
    if not disclaimer:
        return answer
    disclaimer_stripped = disclaimer.strip()
    if disclaimer_stripped in answer:
        return answer
    return answer + disclaimer
