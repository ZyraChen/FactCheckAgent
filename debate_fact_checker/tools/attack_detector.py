"""
攻击关系检测 - 改进版
解决问题: 增加攻击关系,减少冲突节点被同时接受

改进:
1. 放宽优先级限制 - 允许优先级接近的节点攻击
2. LLM更积极识别冲突
3. 每轮重新评估所有节点对
"""

from typing import List
from core.argumentation_graph import ArgumentationGraph
from utils.models import AttackEdge, ArgumentNode
from llm.qwen_client import QwenClient


class AttackDetector:
    """攻击关系检测器 - 改进版"""

    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client

    def detect_attacks_for_round(
        self,
        arg_graph: ArgumentationGraph,
        round_num: int
    ) -> List[AttackEdge]:
        """
        检测攻击关系 - 改进版

        关键改进:
        1. 不只检测本轮新增节点,而是重新评估所有对立节点对
        2. 放宽优先级限制:差距<0.15也允许攻击(基于内容矛盾)
        3. 每轮都全面检测,确保冲突被识别
        """
        new_edges = []

        # 获取Pro和Con的所有节点
        pro_nodes = [n for n in arg_graph.nodes if n.agent == "pro"]
        con_nodes = [n for n in arg_graph.nodes if n.agent == "con"]

        print(f"\n[攻击检测] Pro {len(pro_nodes)}个节点 vs Con {len(con_nodes)}个节点")

        # Pro攻击Con
        pro_attacks = self._detect_attacks_between(
            pro_nodes, con_nodes, "Pro", "Con"
        )
        new_edges.extend(pro_attacks)

        # Con攻击Pro
        con_attacks = self._detect_attacks_between(
            con_nodes, pro_nodes, "Con", "Pro"
        )
        new_edges.extend(con_attacks)

        # 去重
        seen = set()
        unique_edges = []
        for edge in new_edges:
            key = (edge.from_node_id, edge.to_node_id)
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)

        print(f"[攻击检测] 检测到 {len(unique_edges)} 个新攻击关系")

        return unique_edges

    def _detect_attacks_between(
        self,
        my_nodes: List[ArgumentNode],
        their_nodes: List[ArgumentNode],
        my_side: str,
        their_side: str
    ) -> List[AttackEdge]:
        """检测我方对他方的所有可能攻击"""

        if not my_nodes or not their_nodes:
            return []

        # 限制数量避免LLM调用过多
        my_nodes = sorted(my_nodes, key=lambda n: n.priority, reverse=True)[:5]
        their_nodes = sorted(their_nodes, key=lambda n: n.priority, reverse=True)[:5]

        # 构建prompt - 强调找出所有冲突
        system = f"""你是论辩分析专家,要找出{my_side}和{their_side}之间的所有冲突。

关键要求:
1. 积极识别内容上的任何矛盾(数据冲突、结论相反、时效性差异)
2. 只要有实质性矛盾,就应该标记为攻击
3. 不要过分纠结优先级 - 内容矛盾更重要
4. 尽可能多地识别冲突(目标:至少3-5个攻击)

返回格式(每行一个攻击):
{my_side}-X攻击{their_side}-Y | 理由(50字内)

如果真的没有任何冲突,返回"无攻击"
"""

        my_text = "\n\n".join([
            f"{my_side}-{i+1} [ID:{n.id}, 优先级:{n.priority:.2f}]\n{n.content[:300]}..."
            for i, n in enumerate(my_nodes)
        ])

        their_text = "\n\n".join([
            f"{their_side}-{i+1} [ID:{n.id}, 优先级:{n.priority:.2f}]\n{n.content[:300]}..."
            for i, n in enumerate(their_nodes)
        ])

        prompt = f"""{my_side}方论证:
{my_text}

{their_side}方论证:
{their_text}

请识别所有可能的攻击关系。要求:
1. 只要内容有矛盾就标记(数据冲突、结论相反、来源权威性差异)
2. 理由要具体说明矛盾点
3. 尽可能多地识别冲突

示例:
Pro-1攻击Con-2 | 我方数据74亿公里,对方49亿公里,直接矛盾
Pro-2攻击Con-1 | 我方2024年数据,对方2015年数据过时"""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.llm.chat(messages, system=system, temperature=0.7)

            attacks = []
            import re

            for line in response.split('\n'):
                # 匹配格式: Pro-1攻击Con-2 | 理由
                match = re.search(rf'{my_side}-(\d+)攻击{their_side}-(\d+)\s*[|丨]\s*(.+)', line, re.IGNORECASE)
                if match:
                    my_idx = int(match.group(1)) - 1
                    their_idx = int(match.group(2)) - 1
                    rationale = match.group(3).strip()

                    if 0 <= my_idx < len(my_nodes) and 0 <= their_idx < len(their_nodes):
                        attacker = my_nodes[my_idx]
                        target = their_nodes[their_idx]

                        # 放宽优先级限制:只要差距不超过0.15就允许
                        priority_diff = attacker.priority - target.priority

                        if priority_diff >= -0.15:  # 允许攻击者略低
                            # 基础强度 + 优先级差异
                            strength = max(0.1, 0.5 + priority_diff)

                            attacks.append(AttackEdge(
                                from_node_id=attacker.id,
                                to_node_id=target.id,
                                strength=strength,
                                rationale=rationale[:150]
                            ))

                            print(f"  ✓ {attacker.id}(P={attacker.priority:.2f}) → {target.id}(P={target.priority:.2f})")

            return attacks

        except Exception as e:
            print(f"  ⚠️  LLM攻击检测失败: {e}")
            return []


# 简化版本 - 基于规则,更激进
def detect_attacks_simple(
    arg_graph: ArgumentationGraph,
    round_num: int
) -> List[AttackEdge]:
    """
    简化版攻击检测 - 改进版

    改进:
    1. 检测所有对立节点对,不只是本轮
    2. 放宽优先级限制
    """
    new_edges = []

    pro_nodes = [n for n in arg_graph.nodes if n.agent == "pro"]
    con_nodes = [n for n in arg_graph.nodes if n.agent == "con"]

    # Pro攻击Con
    for pro_node in pro_nodes:
        for con_node in con_nodes:
            # 放宽:只要Pro优先级不低于Con太多就攻击
            if pro_node.priority >= con_node.priority - 0.1:
                edge = AttackEdge(
                    from_node_id=pro_node.id,
                    to_node_id=con_node.id,
                    strength=max(0.1, pro_node.priority - con_node.priority + 0.2),
                    rationale=f"Pro论证(P={pro_node.priority:.2f})攻击Con论证(P={con_node.priority:.2f})"
                )
                new_edges.append(edge)

    # Con攻击Pro
    for con_node in con_nodes:
        for pro_node in pro_nodes:
            if con_node.priority >= pro_node.priority - 0.1:
                edge = AttackEdge(
                    from_node_id=con_node.id,
                    to_node_id=pro_node.id,
                    strength=max(0.1, con_node.priority - pro_node.priority + 0.2),
                    rationale=f"Con论证(P={con_node.priority:.2f})攻击Pro论证(P={pro_node.priority:.2f})"
                )
                new_edges.append(edge)

    return new_edges