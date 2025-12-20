"""
攻击关系检测器
使用LLM检测证据之间的矛盾关系
"""

from typing import List
from utils.models import Evidence, AttackEdge
from core.argumentation_graph import ArgumentationGraph
from llm.qwen_client import QwenClient


class AttackDetector:
    """攻击关系检测器"""

    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client

    def detect_attacks_for_round(
        self,
        arg_graph: ArgumentationGraph,
        round_num: int
    ) -> List[AttackEdge]:
        """
        检测本轮新增证据与已有证据之间的攻击关系

        策略:
        1. 获取本轮新增的证据
        2. 与对方已有证据进行两两比较
        3. 只添加高优先级→低优先级的攻击
        """
        new_edges = []

        # 获取本轮新增的证据
        new_evidences = [e for e in arg_graph.evidence_nodes.values() if e.round_num == round_num]

        # 获取所有已有证据(包括本轮)
        all_evidences = list(arg_graph.evidence_nodes.values())

        print(f"\n[攻击检测] 检测 {len(new_evidences)} 个新证据 vs {len(all_evidences)} 个已有证据")

        for new_ev in new_evidences:
            for existing_ev in all_evidences:
                # 跳过自己
                if new_ev.id == existing_ev.id:
                    continue

                # 只检测对立立场
                if new_ev.retrieved_by == existing_ev.retrieved_by:
                    continue

                # 只检测高优先级→低优先级
                priority_diff = new_ev.get_priority() - existing_ev.get_priority()
                if priority_diff <= 0.05:  # 至少高5%
                    continue

                # 使用LLM判断是否存在矛盾
                is_attack, rationale = self._check_if_attacks(new_ev, existing_ev)

                if is_attack:
                    edge = AttackEdge(
                        from_evidence_id=new_ev.id,
                        to_evidence_id=existing_ev.id,
                        strength=priority_diff,
                        rationale=rationale,
                        round_num=round_num
                    )
                    new_edges.append(edge)

        print(f"[攻击检测] 发现 {len(new_edges)} 个攻击关系")
        return new_edges

    def _check_if_attacks(
        self,
        attacker: Evidence,
        target: Evidence
    ) -> tuple[bool, str]:
        """
        使用LLM判断两个证据是否存在攻击关系

        攻击关系的判断标准:
        1. 内容直接矛盾(时间、数字、事实不符)
        2. attacker提供更权威/更新的信息
        3. attacker指出target的局限性或错误
        """
        system = """你是论辩图分析专家,判断两个证据是否存在攻击关系。

攻击关系的标准:
1. 证据1的内容直接反驳证据2(如时间、数字、事实矛盾)
2. 证据1提供了更权威/更新的信息,使证据2失效
3. 证据1指出证据2的错误或局限性

请判断证据1是否攻击证据2,并给出理由。"""

        prompt = f"""证据1 (来自{attacker.retrieved_by.upper()}, 可信度:{attacker.credibility}, 优先级:{attacker.get_priority():.2f}):
来源: {attacker.source}
内容: {attacker.content[:300]}

证据2 (来自{target.retrieved_by.upper()}, 可信度:{target.credibility}, 优先级:{target.get_priority():.2f}):
来源: {target.source}
内容: {target.content[:300]}

请回答:
1. 证据1是否攻击证据2? (是/否)
2. 理由 (一句话,30字内)

格式: 是/否 | 理由"""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.llm.chat(messages, system=system, temperature=0.3)

            # 解析响应
            if '|' in response:
                parts = response.split('|')
                decision = parts[0].strip()
                rationale = parts[1].strip() if len(parts) > 1 else "LLM判断存在攻击"

                is_attack = '是' in decision or 'Yes' in decision or 'yes' in decision
                return is_attack, rationale
            else:
                # 简单判断
                is_attack = '是' in response[:10] or 'Yes' in response[:10]
                return is_attack, response[:50]

        except Exception as e:
            print(f"⚠ LLM调用失败: {e}")
            # 降级策略:基于可信度和关键词
            return self._fallback_attack_check(attacker, target)

    def _fallback_attack_check(
        self,
        attacker: Evidence,
        target: Evidence
    ) -> tuple[bool, str]:
        """降级策略:不使用LLM时的简单攻击判断"""
        # 如果attacker的可信度明显更高且优先级更高
        cred_rank = {"High": 3, "Medium": 2, "Low": 1}
        if cred_rank[attacker.credibility] > cred_rank[target.credibility]:
            return True, f"更高可信度证据({attacker.credibility} vs {target.credibility})"

        return False, ""
