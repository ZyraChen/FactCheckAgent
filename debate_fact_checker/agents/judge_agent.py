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
        生成最终判决

        流程:
        1. 计算Grounded Extension(可接受的证据集合)
        2. 统计双方被接受的证据数量和强度
        3. 做出判决(Supported/Refuted/NEI)
        4. 生成详细解释
        """
        print("\n" + "=" * 80)
        print("Judge 开始判决")
        print("=" * 80)

        # 1. 计算Grounded Extension
        accepted_ids = arg_graph.compute_grounded_extension()
        print(f"可接受的证据节点: {len(accepted_ids)} 个")

        # 2. 分析双方
        pro_accepted = [
            arg_graph.get_node_by_id(eid) for eid in accepted_ids
            if arg_graph.get_node_by_id(eid) and arg_graph.get_node_by_id(eid).retrieved_by == "pro"
        ]
        con_accepted = [
            arg_graph.get_node_by_id(eid) for eid in accepted_ids
            if arg_graph.get_node_by_id(eid) and arg_graph.get_node_by_id(eid).retrieved_by == "con"
        ]

        print(f"Pro被接受: {len(pro_accepted)} 个, Con被接受: {len(con_accepted)} 个")

        # 3. 计算双方强度
        pro_strength = self._calculate_strength(pro_accepted)
        con_strength = self._calculate_strength(con_accepted)

        print(f"Pro强度: {pro_strength:.3f}, Con强度: {con_strength:.3f}")

        # 4. 做出判决
        decision, confidence = self._make_decision(
            pro_accepted, con_accepted, pro_strength, con_strength
        )

        print(f"判决: {decision}, 置信度: {confidence:.2f}")

        # 5. 生成推理解释
        reasoning = self._generate_reasoning(
            claim, arg_graph, accepted_ids, decision, pro_accepted, con_accepted
        )

        # 6. 提取关键证据
        key_evidence_ids = self._extract_key_evidence(pro_accepted, con_accepted, decision)

        return Verdict(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_evidence_ids=key_evidence_ids,
            accepted_evidence_ids=list(accepted_ids),
            pro_strength=pro_strength,
            con_strength=con_strength,
            total_evidences=len(arg_graph.evidence_nodes),
            accepted_evidences=len(accepted_ids)
        )

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
        pro_accepted: List[Evidence],
        con_accepted: List[Evidence],
        pro_strength: float,
        con_strength: float
    ) -> tuple[str, float]:
        """
        做出判决

        判决逻辑:
        1. 如果一方没有被接受的证据 → 另一方胜出
        2. 如果双方强度差距明显(>0.15) → 强者胜出
        3. 如果势均力敌 → 比较最高质量证据
        4. 最后手段 → NEI
        """
        # 情况1: 一方没有被接受的证据
        if not pro_accepted and not con_accepted:
            return "NEI", 0.3

        if not pro_accepted:
            return "Refuted", min(0.90, 0.6 + con_strength * 0.4)

        if not con_accepted:
            return "Supported", min(0.90, 0.6 + pro_strength * 0.4)

        # 情况2: 双方都有证据 - 比较强度
        strength_diff = abs(pro_strength - con_strength)

        if strength_diff > 0.15:  # 差距明显
            if pro_strength > con_strength:
                confidence = 0.6 + (strength_diff * 0.4)
                return "Supported", min(0.90, confidence)
            else:
                confidence = 0.6 + (strength_diff * 0.4)
                return "Refuted", min(0.90, confidence)

        # 情况3: 势均力敌 - 比较最高优先级证据
        max_pro_priority = max((e.get_priority() for e in pro_accepted), default=0)
        max_con_priority = max((e.get_priority() for e in con_accepted), default=0)

        if max_pro_priority > max_con_priority + 0.1:
            return "Supported", 0.6
        elif max_con_priority > max_pro_priority + 0.1:
            return "Refuted", 0.6

        # 情况4: 真正无法判断
        # 比较数量
        if len(pro_accepted) > len(con_accepted) + 1:
            return "Supported", 0.55
        elif len(con_accepted) > len(pro_accepted) + 1:
            return "Refuted", 0.55
        else:
            return "NEI", 0.5

    def _generate_reasoning(
        self,
        claim: str,
        arg_graph: ArgumentationGraph,
        accepted_ids: Set[str],
        decision: str,
        pro_accepted: List[Evidence],
        con_accepted: List[Evidence]
    ) -> str:
        """生成推理解释"""

        # 准备证据描述
        pro_desc = ""
        if pro_accepted:
            pro_lines = []
            for i, ev in enumerate(pro_accepted[:2], 1):
                pro_lines.append(f"{i}. [{ev.source}] {ev.content[:150]}... (可信度:{ev.credibility}, 优先级:{ev.get_priority():.2f})")
            pro_desc = "\n".join(pro_lines)
        else:
            pro_desc = "无被接受的支持证据"

        con_desc = ""
        if con_accepted:
            con_lines = []
            for i, ev in enumerate(con_accepted[:2], 1):
                con_lines.append(f"{i}. [{ev.source}] {ev.content[:150]}... (可信度:{ev.credibility}, 优先级:{ev.get_priority():.2f})")
            con_desc = "\n".join(con_lines)
        else:
            con_desc = "无被接受的反驳证据"

        system = """你是事实核查专家,需要生成清晰的判决解释。

要求:
1. 说明考虑了哪些证据来源
2. 解释为什么某些证据更权威(可信度、来源)
3. 说明攻击关系如何影响判决
4. 给出最终结论的依据
5. 200-300字,自然流畅,不要使用列表格式"""

        prompt = f"""待核查主张: {claim}

判决结果: {decision}

被接受的支持证据({len(pro_accepted)}条):
{pro_desc}

被接受的反驳证据({len(con_accepted)}条):
{con_desc}

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
            return f"基于{len(accepted_ids)}个被接受的证据,判决为{decision}。正方被接受{len(pro_accepted)}个证据,反方被接受{len(con_accepted)}个证据。"

    def _extract_key_evidence(
        self,
        pro_accepted: List[Evidence],
        con_accepted: List[Evidence],
        decision: str
    ) -> List[str]:
        """提取关键证据ID"""
        if decision == "Supported":
            # 返回Pro最强的2-3个证据ID
            sorted_pro = sorted(pro_accepted, key=lambda e: e.get_priority(), reverse=True)
            return [e.id for e in sorted_pro[:3]]
        elif decision == "Refuted":
            # 返回Con最强的2-3个证据ID
            sorted_con = sorted(con_accepted, key=lambda e: e.get_priority(), reverse=True)
            return [e.id for e in sorted_con[:3]]
        else:
            # NEI: 返回双方最强的证据
            all_evidences = sorted(
                pro_accepted + con_accepted,
                key=lambda e: e.get_priority(),
                reverse=True
            )
            return [e.id for e in all_evidences[:3]]
