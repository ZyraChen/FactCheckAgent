"""
论证框架的形式化语义计算 - 修复版
实现 Grounded Extension

修复: 兼容ArgumentationGraph使用evidence_nodes而非nodes
"""

from typing import Set, List, Dict
from core.argumentation_graph import ArgumentationGraph


def compute_grounded_extension(arg_graph: ArgumentationGraph) -> Set[str]:
    """
    计算grounded extension - 兼容evidence_nodes

    算法:
    1. 初始化可接受集合为空
    2. 迭代添加没有被攻击的证据
    3. 添加被已接受证据防御的证据
    4. 直到不再有新的证据被添加

    返回: 可接受的证据节点ID集合
    """
    # 获取所有证据节点ID
    all_node_ids = set(arg_graph.evidence_nodes.keys())

    if not all_node_ids:
        return set()

    # 构建攻击关系索引 - {target_id: [attacker_ids]}
    attacks_to = {}
    for edge in arg_graph.attack_edges:
        if edge.target_id not in attacks_to:
            attacks_to[edge.target_id] = []
        attacks_to[edge.target_id].append(edge.attacker_id)

    # 初始化
    accepted = set()

    # 迭代计算
    max_iterations = 100
    for iteration in range(max_iterations):
        new_accepted = accepted.copy()

        for node_id in all_node_ids:
            if node_id in accepted:
                continue

            # 获取攻击者列表
            attackers = attacks_to.get(node_id, [])

            if not attackers:
                # 没有攻击者 → 可接受
                new_accepted.add(node_id)
            else:
                # 检查所有攻击者是否都被击败
                all_attackers_defeated = True
                for attacker_id in attackers:
                    # 检查attacker是否被accepted中的节点攻击
                    attacker_attackers = attacks_to.get(attacker_id, [])
                    if not any(aa in accepted for aa in attacker_attackers):
                        # attacker未被击败
                        all_attackers_defeated = False
                        break

                if all_attackers_defeated and len(attackers) > 0:
                    # 所有攻击者都被击败 → 可接受
                    new_accepted.add(node_id)

        # 如果没有新增,结束
        if new_accepted == accepted:
            break

        accepted = new_accepted

    return accepted


def compute_preferred_extension(arg_graph: ArgumentationGraph) -> Set[str]:
    """
    计算preferred extension (更复杂,暂时用grounded代替)
    """
    return compute_grounded_extension(arg_graph)


def explain_extension(
    arg_graph: ArgumentationGraph,
    extension: Set[str]
) -> Dict:
    """
    解释extension的计算结果
    """
    accepted_evidences = [arg_graph.evidence_nodes[eid] for eid in extension if eid in arg_graph.evidence_nodes]
    rejected_evidences = [
        e for eid, e in arg_graph.evidence_nodes.items()
        if eid not in extension
    ]

    explanation = {
        "accepted_count": len(extension),
        "rejected_count": len(rejected_evidences),
        "accepted_by_agent": {
            "pro": len([e for e in accepted_evidences if e.retrieved_by == "pro"]),
            "con": len([e for e in accepted_evidences if e.retrieved_by == "con"])
        },
        "rejected_by_agent": {
            "pro": len([e for e in rejected_evidences if e.retrieved_by == "pro"]),
            "con": len([e for e in rejected_evidences if e.retrieved_by == "con"])
        },
        "acceptance_reasons": []
    }

    # 构建攻击索引
    attacks_to = {}
    for edge in arg_graph.attack_edges:
        if edge.target_id not in attacks_to:
            attacks_to[edge.target_id] = []
        attacks_to[edge.target_id].append(edge.attacker_id)

    # 分析接受原因
    for node_id in extension:
        attackers = attacks_to.get(node_id, [])
        if not attackers:
            reason = "无攻击者"
        else:
            reason = f"所有{len(attackers)}个攻击者均被击败"

        explanation["acceptance_reasons"].append({
            "node_id": node_id,
            "reason": reason
        })

    return explanation