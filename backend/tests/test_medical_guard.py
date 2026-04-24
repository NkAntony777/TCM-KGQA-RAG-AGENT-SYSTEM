"""
test_medical_guard.py  —  S4 医疗边界策略单元测试
"""
from __future__ import annotations

import unittest

from services.common.medical_guard import (
    DISCLAIMER_HIGH_RISK,
    DISCLAIMER_STANDARD,
    RiskLevel,
    append_disclaimer,
    assess_query,
)


class TestRefusePatterns(unittest.TestCase):
    """高风险拒答：涉及剂量、自行开方、停药等关键词应触发拒答。"""

    def test_dosage_query_refused(self) -> None:
        result = assess_query("六味地黄丸每次吃几克")
        self.assertTrue(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_self_prescription_refused(self) -> None:
        result = assess_query("我想自己配药，需要哪些药材")
        self.assertTrue(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_stop_medication_refused(self) -> None:
        result = assess_query("停药之后有什么反应")
        self.assertTrue(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_replace_western_medicine_refused(self) -> None:
        result = assess_query("中药可以替代西药吗")
        self.assertTrue(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_refuse_response_non_empty(self) -> None:
        result = assess_query("几毫克最合适")
        self.assertTrue(result.should_refuse)
        self.assertGreater(len(result.refuse_response), 20)

    def test_refuse_disclaimer_is_high_risk(self) -> None:
        result = assess_query("每次吃多少")
        self.assertIn("声明", result.disclaimer)


class TestHighRiskPatterns(unittest.TestCase):
    """高风险场景：不拒答但追加高风险免责声明。"""

    def test_emergency_is_high_risk(self) -> None:
        result = assess_query("急性心肌梗死可以用中药吗")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)
        self.assertIn(DISCLAIMER_HIGH_RISK.strip(), result.disclaimer)

    def test_pregnancy_is_high_risk(self) -> None:
        result = assess_query("孕妇可以服用六味地黄丸吗")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_cancer_is_high_risk(self) -> None:
        result = assess_query("癌症患者适合什么中药")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_infant_medication_is_high_risk(self) -> None:
        result = assess_query("新生儿能不能用甘草")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.HIGH_RISK)

    def test_high_risk_disclaimer_present(self) -> None:
        result = assess_query("高血压能用中药调理吗")
        self.assertGreater(len(result.disclaimer), 0)
        self.assertIn("就医", result.disclaimer)


class TestCautionPatterns(unittest.TestCase):
    """谨慎场景：附加标准免责声明，不拒答。"""

    def test_formula_query_is_caution(self) -> None:
        result = assess_query("六味地黄丸的服法是什么")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.CAUTION)
        self.assertIn(DISCLAIMER_STANDARD.strip(), result.disclaimer)

    def test_side_effect_is_caution(self) -> None:
        result = assess_query("这个药有副作用吗")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.CAUTION)

    def test_contraindication_is_caution(self) -> None:
        result = assess_query("配伍禁忌有哪些")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.CAUTION)


class TestSafePatterns(unittest.TestCase):
    """安全场景：无免责声明，无拒答。"""

    def test_history_query_is_safe(self) -> None:
        result = assess_query("六味地黄丸出自哪部古籍")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)
        self.assertEqual(result.disclaimer, "")

    def test_formula_composition_is_safe(self) -> None:
        result = assess_query("六味地黄丸由哪些药材组成")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)

    def test_concept_query_is_safe(self) -> None:
        result = assess_query("中医的辨证论治是什么意思")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)

    def test_empty_query_is_safe(self) -> None:
        result = assess_query("")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)

    def test_academic_dosage_threshold_query_is_not_refused(self) -> None:
        result = assess_query("请从AQP分布差异分析五苓散发汗与利小便是否存在剂量或煎煮法阈值效应")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)

    def test_academic_dosage_context_is_case_insensitive_for_ascii_terms(self) -> None:
        result = assess_query("请从AQP机制分析五苓散剂量阈值效应")
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.risk_level, RiskLevel.SAFE)

    def test_multiple_choice_exam_query_with_dosage_terms_is_not_refused(self) -> None:
        result = assess_query(
            "请回答下面的中医处方审核选择题。\n"
            "题目：下列不属于调配制度的是\n"
            "选项：\n"
            "A. 调配人员接到计价收款后的处方，应再次审方\n"
            "B. 应注意处方中有无配伍禁忌\n"
            "C. 特殊管理的药品剂量是否正确\n"
            "D. 向患者说明用法用量，煎煮方法，有无禁忌\n"
            "E. 按处方药味顺序调配，间隔摆放"
        )
        self.assertFalse(result.should_refuse)
        self.assertNotEqual(result.risk_level, RiskLevel.HIGH_RISK)


class TestAppendDisclaimer(unittest.TestCase):
    """append_disclaimer 工具函数行为验证。"""

    def test_appends_to_answer(self) -> None:
        answer = "六味地黄丸有滋阴补肾之效。"
        result = append_disclaimer(answer, DISCLAIMER_STANDARD)
        self.assertIn(answer, result)
        self.assertIn(DISCLAIMER_STANDARD.strip(), result)

    def test_no_duplicate_append(self) -> None:
        answer = "六味地黄丸有滋阴补肾之效。" + DISCLAIMER_STANDARD
        result = append_disclaimer(answer, DISCLAIMER_STANDARD)
        self.assertEqual(result.count(DISCLAIMER_STANDARD.strip()), 1)

    def test_empty_disclaimer_unchanged(self) -> None:
        answer = "原始回答"
        result = append_disclaimer(answer, "")
        self.assertEqual(result, answer)


if __name__ == "__main__":
    unittest.main()
