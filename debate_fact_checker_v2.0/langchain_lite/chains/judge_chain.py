"""
Judge Chain - 生成最终判决
使用 LangChain 来组织 Prompt + LLM + Output Parsing
"""

from typing import List
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from utils.models import Verdict


class JudgeChain:
    """
    Judge 判决生成链

    职责：根据论辩图和被接受的证据生成最终判决
    """

    def __init__(self, llm):
        """
        初始化

        Args:
            llm: LangChain compatible LLM (QwenLLMWrapper)
        """
        self.llm = llm

        # 判断证据立场的 Prompt
        self.stance_template = PromptTemplate(
            input_variables=["claim", "evidence_content", "evidence_source"],
            template="""你是一个公正的事实核查专家。

Claim: {claim}

证据来源: {evidence_source}
证据内容: {evidence_content}

请判断这个证据是**支持(support)**还是**反对(refute)**这个claim。

只回答: support 或 refute

判断:"""
        )

        # 生成判决的 Prompt
        self.verdict_template = PromptTemplate(
            input_variables=["claim", "support_evidences", "refute_evidences",
                           "support_strength", "refute_strength"],
            template="""你是一个公正的事实核查法官。

Claim: {claim}

支持证据 ({support_strength:.2f} 强度):
{support_evidences}

反对证据 ({refute_strength:.2f} 强度):
{refute_evidences}

请做出最终判决:
- Supported: 有充分的高质量证据支持claim
- Refuted: 有充分的高质量证据反驳claim
- NEI: 证据不足或双方势均力敌

同时给出详细的推理过程（200字左右），说明：
1. 为什么做出这个判决
2. 关键证据是什么
3. 双方论证的强弱分析

输出格式:
判决: [Supported/Refuted/NEI]
推理: [详细推理过程]

现在判决:"""
        )

        self.stance_chain = LLMChain(llm=self.llm, prompt=self.stance_template)
        self.verdict_chain = LLMChain(llm=self.llm, prompt=self.verdict_template)

    def determine_stance(self, claim: str, evidence) -> str:
        """
        判断证据的立场

        Args:
            claim: Claim
            evidence: Evidence 对象

        Returns:
            "support" 或 "refute"
        """
        try:
            result = self.stance_chain.invoke({
                "claim": claim,
                "evidence_content": evidence.content[:500],
                "evidence_source": evidence.source
            })

            text = result.get('text', '').strip().lower()

            if 'support' in text:
                return 'support'
            elif 'refute' in text:
                return 'refute'
            else:
                return 'neutral'

        except Exception as e:
            print(f"⚠ 立场判断失败: {e}")
            return 'neutral'

    def make_verdict(
        self,
        claim: str,
        accepted_evidences: List,
        all_evidences_count: int
    ) -> Verdict:
        """
        生成最终判决

        Args:
            claim: Claim
            accepted_evidences: 被接受的证据列表
            all_evidences_count: 所有证据总数

        Returns:
            Verdict 对象
        """
        if not accepted_evidences:
            return Verdict(
                decision="NEI",
                confidence=0.3,
                reasoning="没有被接受的证据，无法判断。",
                key_evidence_ids=[],
                accepted_evidence_ids=[],
                pro_strength=0.0,
                con_strength=0.0,
                total_evidences=all_evidences_count,
                accepted_evidences=0
            )

        # 1. 判断每个证据的立场
        print("\n[立场分析] 判断证据立场...")
        supporting = []
        refuting = []

        for ev in accepted_evidences:
            stance = self.determine_stance(claim, ev)
            if stance == 'support':
                supporting.append(ev)
                print(f"  ✓ {ev.id}: 支持")
            elif stance == 'refute':
                refuting.append(ev)
                print(f"  ✗ {ev.id}: 反对")

        # 2. 计算强度
        support_strength = sum(ev.get_priority() for ev in supporting) / len(supporting) if supporting else 0.0
        refute_strength = sum(ev.get_priority() for ev in refuting) / len(refuting) if refuting else 0.0

        print(f"\n支持强度: {support_strength:.3f}, 反对强度: {refute_strength:.3f}")

        # 3. 构建证据摘要
        support_summary = "\n".join([f"- [{ev.source}] {ev.content[:100]}..." for ev in supporting[:3]]) if supporting else "无"
        refute_summary = "\n".join([f"- [{ev.source}] {ev.content[:100]}..." for ev in refuting[:3]]) if refuting else "无"

        # 4. 调用 LLM 生成判决
        try:
            result = self.verdict_chain.invoke({
                "claim": claim,
                "support_evidences": support_summary,
                "refute_evidences": refute_summary,
                "support_strength": support_strength,
                "refute_strength": refute_strength
            })

            text = result.get('text', '')

            # 解析输出
            decision = "NEI"
            reasoning = text

            if "判决:" in text:
                lines = text.split('\n')
                for line in lines:
                    if line.startswith("判决:"):
                        decision_text = line.replace("判决:", "").strip()
                        if "Supported" in decision_text:
                            decision = "Supported"
                        elif "Refuted" in decision_text:
                            decision = "Refuted"
                        elif "NEI" in decision_text:
                            decision = "NEI"
                    elif line.startswith("推理:"):
                        reasoning = line.replace("推理:", "").strip()

            # 计算置信度
            strength_diff = abs(support_strength - refute_strength)
            if strength_diff > 0.3:
                confidence = 0.9
            elif strength_diff > 0.15:
                confidence = 0.7
            else:
                confidence = 0.5

            # 关键证据
            key_evidences = []
            if decision == "Supported":
                key_evidences = [ev.id for ev in supporting[:3]]
            elif decision == "Refuted":
                key_evidences = [ev.id for ev in refuting[:3]]

            return Verdict(
                decision=decision,
                confidence=confidence,
                reasoning=reasoning,
                key_evidence_ids=key_evidences,
                accepted_evidence_ids=[ev.id for ev in accepted_evidences],
                pro_strength=support_strength,
                con_strength=refute_strength,
                total_evidences=all_evidences_count,
                accepted_evidences=len(accepted_evidences)
            )

        except Exception as e:
            print(f"⚠ 判决生成失败: {e}")
            return Verdict(
                decision="NEI",
                confidence=0.5,
                reasoning=f"判决生成失败: {e}",
                key_evidence_ids=[],
                accepted_evidence_ids=[ev.id for ev in accepted_evidences],
                pro_strength=support_strength,
                con_strength=refute_strength,
                total_evidences=all_evidences_count,
                accepted_evidences=len(accepted_evidences)
            )
