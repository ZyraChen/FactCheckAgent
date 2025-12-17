"""
Judge Agent - 改进版
处理证据节点并生成判决
"""
from typing import List, Set, Dict

import sys

sys.path.insert(0, '/mnt/user-data/outputs')
from core.evidence_pool import Evidence, EvidencePool
from core.argumentation_graph import ArgumentationGraph


class JudgeAgent:
    """
    法官Agent - 改进版

    核心改进:
    1. 处理Evidence节点而不是ArgumentNode
    2. 基于证据节点计算Grounded Extension
    3. 生成详细的推理解释
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    def make_verdict(
            self,
            claim: str,
            arg_graph: ArgumentationGraph,
            evidence_pool: EvidencePool
    ) -> Dict:
        """
        生成最终判决

        流程:
        1. 计算Grounded Extension(可接受的证据集合)
        2. 统计双方强度
        3. 决策(Supported/Refuted/NEI)
        4. 生成详细解释
        """
        print("\n" + "=" * 80)
        print("Judge开始判决")
        print("=" * 80)

        # 1. 计算Grounded Extension
        accepted_ids = arg_graph.compute_grounded_extension()
        print(f"\n可接受的证据节点: {len(accepted_ids)}个")

        # 2. 统计双方强度
        pro_evidences = [
            e for eid, e in arg_graph.evidence_nodes.items()
            if eid in accepted_ids and e.retrieved_by == "pro"
        ]
        con_evidences = [
            e for eid, e in arg_graph.evidence_nodes.items()
            if eid in accepted_ids and e.retrieved_by == "con"
        ]

        pro_strength = sum(e.get_priority() for e in pro_evidences) / max(len(pro_evidences),
                                                                          1) if pro_evidences else 0.0
        con_strength = sum(e.get_priority() for e in con_evidences) / max(len(con_evidences),
                                                                          1) if con_evidences else 0.0

        print(f"Pro强度: {pro_strength:.3f} ({len(pro_evidences)}个被接受证据)")
        print(f"Con强度: {con_strength:.3f} ({len(con_evidences)}个被接受证据)")

        # 3. 决策
        if len(accepted_ids) < 2:
            decision = "NEI"
            confidence = 0.3
        elif pro_strength > con_strength * 1.2:
            decision = "Supported"
            confidence = min(0.95, pro_strength)
        elif con_strength > pro_strength * 1.2:
            decision = "Refuted"
            confidence = min(0.95, con_strength)
        else:
            decision = "NEI"
            confidence = 0.5

        print(f"\n判决: {decision}, 置信度: {confidence:.2f}")

        # 4. 生成解释
        reasoning = self._generate_explanation(
            claim, arg_graph, accepted_ids, decision, pro_evidences, con_evidences
        )

        return {
            "decision": decision,
            "confidence": float(confidence),
            "reasoning": reasoning,
            "accepted_evidence_ids": list(accepted_ids),
            "pro_strength": float(pro_strength),
            "con_strength": float(con_strength),
            "total_evidences": len(arg_graph.evidence_nodes),
            "accepted_evidences": len(accepted_ids),
            "pro_accepted": len(pro_evidences),
            "con_accepted": len(con_evidences)
        }

    def _generate_explanation(
            self,
            claim: str,
            arg_graph: ArgumentationGraph,
            accepted_ids: Set[str],
            decision: str,
            pro_evidences: List[Evidence],
            con_evidences: List[Evidence]
    ) -> str:
        """
        生成人类可读的推理过程
        参考图片风格:说明证据来源、优先级评估、攻击关系、结论
        """
        system_prompt = """你是事实核查专家,需要生成清晰的判决解释。

要求:
1. 说明考虑了哪些证据来源
2. 解释为什么某些证据更权威(可信度、优先级)
3. 说明证据之间的冲突如何解决(攻击关系)
4. 给出最终结论的依据
5. 风格参考图片中的解释"""

        # 准备证据描述
        pro_desc = "\n".join([
            f"• {e.source}: {e.content[:150]}... (可信度:{e.credibility}, 优先级:{e.get_priority():.2f})"
            for e in pro_evidences[:3]
        ]) if pro_evidences else "无被接受的支持证据"

        con_desc = "\n".join([
            f"• {e.source}: {e.content[:150]}... (可信度:{e.credibility}, 优先级:{e.get_priority():.2f})"
            for e in con_evidences[:3]
        ]) if con_evidences else "无被接受的反驳证据"

        # 攻击关系
        attack_desc = ""
        if len(arg_graph.attack_edges) > 0:
            sample_attacks = arg_graph.attack_edges[:3]
            attack_lines = []
            for attack in sample_attacks:
                attacker = arg_graph.get_node_by_id(attack.attacker_id)
                target = arg_graph.get_node_by_id(attack.target_id)
                if attacker and target:
                    attack_lines.append(
                        f"{attacker.retrieved_by.upper()}-{attacker.source}攻击{target.retrieved_by.upper()}-{target.source}: {attack.rationale}"
                    )
            attack_desc = "\n".join(attack_lines)
        else:
            attack_desc = "无攻击关系"

        user_prompt = f"""待核查主张: {claim}

判决结果: {decision}

被接受的支持证据({len(pro_evidences)}条):
{pro_desc}

被接受的反驳证据({len(con_evidences)}条):
{con_desc}

关键攻击关系:
{attack_desc}

总计: {len(arg_graph.evidence_nodes)}个证据节点, {len(arg_graph.attack_edges)}个攻击边

请生成详细的推理过程(200-300字),参考以下结构:
1. 首先说明从不同来源检索到多少证据
2. 说明哪一方提供了更权威的证据(具体来源和可信度)
3. 解释关键的攻击关系(高优先级如何击败低优先级)
4. 给出最终结论

要自然、清晰,不要使用列表格式。"""

        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = self.llm.chat(messages, system=system_prompt, temperature=0.5)
            return response if response else "推理生成失败"
        except Exception as e:
            print(f"生成推理失败: {e}")
            return f"基于论辩分析,判决为{decision}。"