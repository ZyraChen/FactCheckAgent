"""
论证框架的形式化语义计算
实现 Grounded Extension
"""

from typing import Set, List
from core.argumentation_graph import ArgumentationGraph


def compute_grounded_extension(arg_graph: ArgumentationGraph) -> Set[str]:
    """
    计算grounded extension
    
    算法:
    1. 初始化可接受集合为空
    2. 迭代添加没有被攻击的论证
    3. 添加被已接受论证防御的论证
    4. 直到不再有新的论证被添加
    
    返回: 可接受的论证节点ID集合
    """
    # 所有节点
    all_node_ids = {n.id for n in arg_graph.nodes}
    
    if not all_node_ids:
        return set()
    
    # 初始化
    accepted = set()
    
    # 迭代计算
    while True:
        new_accepted = accepted.copy()
        
        for node_id in all_node_ids:
            if node_id in accepted:
                continue
            
            # 检查该节点是否被攻击
            attackers = arg_graph.get_attackers(node_id)
            
            if not attackers:
                # 没有攻击者 → 可接受
                new_accepted.add(node_id)
            else:
                # 检查所有攻击者是否都被反击(被accepted中的节点攻击)
                all_attackers_defeated = True
                for attacker_id in attackers:
                    # 检查attacker是否被accepted中的节点攻击
                    attacker_attackers = arg_graph.get_attackers(attacker_id)
                    if not any(aa in accepted for aa in attacker_attackers):
                        # attacker未被击败
                        all_attackers_defeated = False
                        break
                
                if all_attackers_defeated and attackers:
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
) -> dict:
    """
    解释extension的计算结果
    """
    accepted_nodes = [arg_graph.get_node_by_id(nid) for nid in extension]
    rejected_nodes = [
        n for n in arg_graph.nodes 
        if n.id not in extension
    ]
    
    explanation = {
        "accepted_count": len(extension),
        "rejected_count": len(rejected_nodes),
        "accepted_by_agent": {
            "pro": len([n for n in accepted_nodes if n.agent == "pro"]),
            "con": len([n for n in accepted_nodes if n.agent == "con"])
        },
        "rejected_by_agent": {
            "pro": len([n for n in rejected_nodes if n.agent == "pro"]),
            "con": len([n for n in rejected_nodes if n.agent == "con"])
        },
        "acceptance_reasons": []
    }
    
    # 分析接受原因
    for node_id in extension:
        attackers = arg_graph.get_attackers(node_id)
        if not attackers:
            reason = "无攻击者"
        else:
            reason = f"所有{len(attackers)}个攻击者均被击败"
        
        explanation["acceptance_reasons"].append({
            "node_id": node_id,
            "reason": reason
        })
    
    return explanation


# 测试
if __name__ == "__main__":
    from core.argumentation_graph import ArgumentationGraph
    from utils.models import ArgumentNode, AttackEdge
    
    # 创建测试图
    graph = ArgumentationGraph("测试claim")
    
    # 添加节点
    n1 = ArgumentNode(
        id="n1", agent="pro", round=1, content="A1", 
        evidence_ids=[], priority=0.5, stance="support_claim"
    )
    n2 = ArgumentNode(
        id="n2", agent="con", round=1, content="A2",
        evidence_ids=[], priority=0.8, stance="refute_claim"
    )
    n3 = ArgumentNode(
        id="n3", agent="pro", round=2, content="A3",
        evidence_ids=[], priority=0.9, stance="support_claim"
    )
    
    graph.add_nodes([n1, n2, n3])
    
    # 添加攻击边 (n2攻击n1, n3攻击n2)
    graph.add_edges([
        AttackEdge(from_node_id="n2", to_node_id="n1", strength=0.3, rationale="test"),
        AttackEdge(from_node_id="n3", to_node_id="n2", strength=0.1, rationale="test")
    ])
    
    # 计算extension
    extension = compute_grounded_extension(graph)
    print(f"Grounded Extension: {extension}")
    
    # 解释
    explanation = explain_extension(graph, extension)
    print(f"Explanation: {explanation}")
