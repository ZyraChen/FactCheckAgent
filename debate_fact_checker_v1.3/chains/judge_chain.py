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
请判断这个证据是支持(support)还是反对(refute)这个claim。
support:这个证据与这个claim不存在冲突
refute:这个证据与claim存在内容冲突
只回答: support 或 refute
判断:"""
        )

        # 生成判决的 Prompt
        self.verdict_template = PromptTemplate(
            input_variables=["claim", "support_evidences", "refute_evidences",
                           "support_strength", "refute_strength"],
            template="""You are an impartial fact-checking judge.
Claim: {claim}
Supporting Evidence (strength: {support_strength:.2f}):
{support_evidences}
Refuting Evidence (strength: {refute_strength:.2f}):
{refute_evidences}

Please make a final verdict:
- Supported: There is sufficient evidence to support the claim
- Refuted: There is sufficient evidence to refute the claim
- Not Enough Evidence: Issues where evidence is insufficient or contentious, or where no consensus has been reached.

Verdict Guidelines:
1. Identify decisive evidence:
   Some evidence may directly prove/disprove the core part of a claim, even if other evidence is more numerous.
   For example:
   - Claim: "A plays B in the American TV series 《X》"
   - If there is evidence proving "《X》 is not an American TV series", this is decisive refuting evidence
   - Even if there are 10 pieces of evidence supporting "A plays B", this 1 piece of evidence already makes the entire claim false

2. Decompose the verifiable parts of the claim:
   - Identify all independently verifiable facts contained in the claim
   - Determine which are necessary conditions (if false, the entire claim must be false)
   
3. Evidence weight:
   - Evidence attacking necessary conditions > Evidence attacking secondary conditions
   - Direct evidence > Indirect evidence
   - High credibility evidence > Low credibility evidence

4. Logical reasoning:
   - If any necessary condition is disproven by high credibility evidence, or the claim itself has semantic or logical errors → Refuted (even if supporting evidence is more numerous)
   - If all parts are supported → Supported
   - If key parts cannot be verified, or the claim has not reached widely recognized consensus and has academic controversy → Not Enough Evidence

5. Avoid simple counting:
   Do not simply count the number of supporting/opposing evidence, but analyze which part of the claim each piece of evidence attacks/supports.

Please provide a detailed reasoning process (around 200 words), explaining the reasoning chain from evidence and evidence-based argumentation to reach the verdict, what the key evidence is, and why this verdict was made
Output format:
{{
  "verdict": "Supported/Refuted/Not Enough Evidence",//English
  "confidence": 0.0-1.0,
  "justification": "Please provide the reasoning process for the determination in Chinese. Detailed reasoning process (around 200 words), explaining the reasoning chain from evidence and evidence-based argumentation to reach the verdict, including:
              1. The key verifiable parts of the claim
              2. What the key evidence is
              3. Why this verdict was made",//Chinese
  "key_evidence": ["List of most critical evidence IDs"],//Preserve Source Language
  "decisive_evidence": {{
    "exists": true/false,//English
    "evidence_ids": ["Decisive evidence IDs"],
    "reason": "Why it is decisive"//Chinese
  }}
}}

Now make the verdict:"""
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
                decision="Not Enough Evidence",
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
            decision = "Not Enough Evidence"
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
                        elif "Not Enough Evidence" in decision_text:
                            decision = "Not Enough Evidence"
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
                decision="Not Enough Evidence",
                confidence=0.5,
                reasoning=f"判决生成失败: {e}",
                key_evidence_ids=[],
                accepted_evidence_ids=[ev.id for ev in accepted_evidences],
                pro_strength=support_strength,
                con_strength=refute_strength,
                total_evidences=all_evidences_count,
                accepted_evidences=len(accepted_evidences)
            )
