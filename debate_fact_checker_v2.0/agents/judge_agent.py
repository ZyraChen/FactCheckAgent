"""
Judge Agent - 法官代理
基于论辩图做出最终判决
"""

from typing import List, Set
from utils.models import Evidence, Verdict
from core.evidence_pool import EvidencePool
from core.argumentation_graph import ArgumentationGraph
from llm.qwen_client import QwenClient


class JudgeAgent:
    """
    法官Agent
    职责:
    1. 计算Grounded Extension(可接受的证据集合)
    2. 分析双方强度
    3. 做出最终判决并生成解释
    """

    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client

    def make_verdict(
        self,
        claim: str,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> Verdict:
        """
        生成最终判决 - 修复版

        关键修复: 基于证据的**内容立场**而不是**谁搜索的**

        流程:
        1. 计算Grounded Extension(可接受的证据集合)
        2. 使用LLM判断每个证据的立场(支持/反对claim)
        3. 计算支持vs反对的强度
        4. 做出判决(Supported/Refuted/NEI)
        5. 生成详细解释
        """
        print("\n" + "=" * 80)
        print("Judge 开始判决")
        print("=" * 80)

        # 1. 计算Grounded Extension
        accepted_ids = arg_graph.compute_grounded_extension()
        print(f"可接受的证据节点: {len(accepted_ids)} 个")

        # 2. 获取被接受的证据对象
        accepted_evidences = [
            arg_graph.get_node_by_id(eid) for eid in accepted_ids
            if arg_graph.get_node_by_id(eid)
        ]

        if not accepted_evidences:
            return Verdict(
                decision="NEI",
                confidence=0.3,
                reasoning="没有被接受的证据，无法判断。",
                key_evidence_ids=[],
                accepted_evidence_ids=[],
                pro_strength=0.0,
                con_strength=0.0,
                total_evidences=len(arg_graph.evidence_nodes),
                accepted_evidences=0
            )

        # 3. 判断每个证据的立场（支持/反对claim）
        print("\n[立场分析] 判断证据立场...")
        supporting_evidences = []
        refuting_evidences = []

        for evidence in accepted_evidences:
            stance = self._determine_evidence_stance(claim, evidence)
            if stance == "support":
                supporting_evidences.append(evidence)
                print(f"  ✓ {evidence.id}: 支持claim")
            elif stance == "refute":
                refuting_evidences.append(evidence)
                print(f"  ✗ {evidence.id}: 反对claim")
            else:
                print(f"  ? {evidence.id}: 中立/不确定")

        print(f"\n[立场统计] 支持: {len(supporting_evidences)}个, 反对: {len(refuting_evidences)}个")

        # 4. 计算双方强度
        support_strength = self._calculate_strength(supporting_evidences)
        refute_strength = self._calculate_strength(refuting_evidences)

        print(f"支持强度: {support_strength:.3f}, 反对强度: {refute_strength:.3f}")

        # 5. 做出判决
        decision, confidence = self._make_decision(
            supporting_evidences, refuting_evidences, support_strength, refute_strength
        )

        print(f"判决: {decision}, 置信度: {confidence:.2f}")

        # 6. 生成推理解释
        reasoning = self._generate_reasoning(
            claim, arg_graph, accepted_ids, decision, supporting_evidences, refuting_evidences
        )

        # 7. 提取关键证据
        key_evidence_ids = self._extract_key_evidence(supporting_evidences, refuting_evidences, decision)

        return Verdict(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_evidence_ids=key_evidence_ids,
            accepted_evidence_ids=list(accepted_ids),
            pro_strength=support_strength,
            con_strength=refute_strength,
            total_evidences=len(arg_graph.evidence_nodes),
            accepted_evidences=len(accepted_ids)
        )

    def _determine_evidence_stance(self, claim: str, evidence: Evidence) -> str:
        """
        判断证据的立场 (支持/反对claim)

        返回: "support", "refute", "neutral"
        """
        system = """你是事实核查专家，判断证据是支持还是反对给定的claim。

只回答: support / refute / neutral"""

        prompt = f"""Claim: {claim}

证据来源: {evidence.source}
证据内容: {evidence.content[:500]}

这条证据是支持(support)、反对(refute)还是中立(neutral)于该claim？

只回答一个词: support / refute / neutral"""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.llm.chat(messages, system=system, temperature=0.3)
            response_lower = response.strip().lower()

            if "support" in response_lower:
                return "support"
            elif "refute" in response_lower:
                return "refute"
            else:
                return "neutral"

        except Exception as e:
            print(f"⚠ 立场判断失败: {e}")
            # 降级策略: 基于retrieved_by字段
            return "support" if evidence.retrieved_by == "pro" else "refute"

    def _calculate_strength(self, accepted_evidences: List[Evidence]) -> float:
        """计算一方的强度"""
        if not accepted_evidences:
            return 0.0

        # 考虑优先级和数量
        avg_priority = sum(e.get_priority() for e in accepted_evidences) / len(accepted_evidences)
        count_factor = min(1.0, len(accepted_evidences) / 3)  # 3个证据达到满分

        return avg_priority * 0.7 + count_factor * 0.3

    def _make_decision(
        self,
        supporting: List[Evidence],
        refuting: List[Evidence],
        support_strength: float,
        refute_strength: float
    ) -> tuple[str, float]:
        """
        做出判决 (基于证据立场，不是Pro/Con)

        判决逻辑:
        1. 如果一方没有被接受的证据 → 另一方胜出
        2. 如果双方强度差距明显(>0.15) → 强者胜出
        3. 如果势均力敌 → 比较最高质量证据
        4. 最后手段 → NEI
        """
        # 情况1: 一方没有被接受的证据
        if not supporting and not refuting:
            return "NEI", 0.3

        if not supporting:
            return "Refuted", min(0.90, 0.6 + refute_strength * 0.4)

        if not refuting:
            return "Supported", min(0.90, 0.6 + support_strength * 0.4)

        # 情况2: 双方都有证据 - 比较强度
        strength_diff = abs(support_strength - refute_strength)

        if strength_diff > 0.15:  # 差距明显
            if support_strength > refute_strength:
                confidence = 0.6 + (strength_diff * 0.4)
                return "Supported", min(0.90, confidence)
            else:
                confidence = 0.6 + (strength_diff * 0.4)
                return "Refuted", min(0.90, confidence)

        # 情况3: 势均力敌 - 比较最高优先级证据
        max_support_priority = max((e.get_priority() for e in supporting), default=0)
        max_refute_priority = max((e.get_priority() for e in refuting), default=0)

        if max_support_priority > max_refute_priority + 0.1:
            return "Supported", 0.6
        elif max_refute_priority > max_support_priority + 0.1:
            return "Refuted", 0.6

        # 情况4: 真正无法判断
        # 比较数量
        if len(supporting) > len(refuting) + 1:
            return "Supported", 0.55
        elif len(refuting) > len(supporting) + 1:
            return "Refuted", 0.55
        else:
            return "NEI", 0.5

    def _generate_reasoning(
        self,
        claim: str,
        arg_graph: ArgumentationGraph,
        accepted_ids: Set[str],
        decision: str,
        supporting: List[Evidence],
        refuting: List[Evidence]
    ) -> str:
        """生成推理解释 (参数为支持/反对证据，而非Pro/Con)"""

        # 准备证据描述
        support_desc = ""
        if supporting:
            support_lines = []
            for i, ev in enumerate(supporting[:2], 1):
                support_lines.append(f"{i}. [{ev.source}] {ev.content[:150]}... (可信度:{ev.credibility}, 优先级:{ev.get_priority():.2f})")
            support_desc = "\n".join(support_lines)
        else:
            support_desc = "无支持claim的证据"

        refute_desc = ""
        if refuting:
            refute_lines = []
            for i, ev in enumerate(refuting[:2], 1):
                refute_lines.append(f"{i}. [{ev.source}] {ev.content[:150]}... (可信度:{ev.credibility}, 优先级:{ev.get_priority():.2f})")
            refute_desc = "\n".join(refute_lines)
        else:
            refute_desc = "无反对claim的证据"

        system = """你是事实核查专家,需要生成清晰的判决解释。

要求:
1. 说明考虑了哪些证据来源
2. 解释为什么某些证据更权威(可信度、来源)
3. 说明攻击关系如何影响判决
4. 给出最终结论的依据
5. 200-300字,自然流畅,不要使用列表格式"""

        prompt = f"""待核查主张: {claim}

判决结果: {decision}

支持claim的证据({len(supporting)}条):
{support_desc}

反对claim的证据({len(refuting)}条):
{refute_desc}

论辩图统计:
- 总证据节点: {len(arg_graph.evidence_nodes)}
- 攻击边: {len(arg_graph.attack_edges)}条
- 被接受节点: {len(accepted_ids)}个

请生成判决推理过程(200-300字):"""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.llm.chat(messages, system=system, temperature=0.5)
            return response if response else f"基于论辩分析,判决为{decision}。"
        except Exception as e:
            print(f"⚠ 推理生成失败: {e}")
            return f"基于{len(accepted_ids)}个被接受的证据,判决为{decision}。支持{len(supporting)}条,反对{len(refuting)}条。"

    def _extract_key_evidence(
        self,
        supporting: List[Evidence],
        refuting: List[Evidence],
        decision: str
    ) -> List[str]:
        """提取关键证据ID (基于立场，不是Pro/Con)"""
        if decision == "Supported":
            # 返回支持claim的最强证据
            sorted_support = sorted(supporting, key=lambda e: e.get_priority(), reverse=True)
            return [e.id for e in sorted_support[:3]]
        elif decision == "Refuted":
            # 返回反对claim的最强证据
            sorted_refute = sorted(refuting, key=lambda e: e.get_priority(), reverse=True)
            return [e.id for e in sorted_refute[:3]]
        else:
            # NEI: 返回双方最强的证据
            all_evidences = sorted(
                supporting + refuting,
                key=lambda e: e.get_priority(),
                reverse=True
            )
            return [e.id for e in all_evidences[:3]]