"""
论辩图(Argumentation Graph)
动态增量构建,边全部表示攻击关系
"""

from typing import List, Optional, Dict
from utils.models import ArgumentNode, AttackEdge
import json


class ArgumentationGraph:
    """论辩图"""
    
    def __init__(self, claim: str):
        self.claim = claim
        self.nodes: List[ArgumentNode] = []
        self.edges: List[AttackEdge] = []
    
    def add_nodes(self, new_nodes: List[ArgumentNode]):
        """添加新的论证节点"""
        self.nodes.extend(new_nodes)
    
    def add_edges(self, new_edges: List[AttackEdge]):
        """
        添加新的攻击边
        验证: 只允许高优先级→低优先级的攻击
        """
        for edge in new_edges:
            attacker = self.get_node_by_id(edge.from_node_id)
            target = self.get_node_by_id(edge.to_node_id)
            
            if not attacker or not target:
                print(f"警告: 节点不存在 {edge.from_node_id} -> {edge.to_node_id}")
                continue
            
            if attacker.priority <= target.priority:
                print(
                    f"警告: 非法攻击被拒绝: {attacker.id}(优先级{attacker.priority:.2f}) "
                    f"无法攻击 {target.id}(优先级{target.priority:.2f})"
                )
                continue
        
            self.edges.append(edge)
    
    def get_node_by_id(self, node_id: str) -> Optional[ArgumentNode]:
        """通过ID获取节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_nodes_by_agent(self, agent: str) -> List[ArgumentNode]:
        """获取特定Agent的所有节点"""
        return [n for n in self.nodes if n.agent == agent]
    
    def get_nodes_by_round(self, round_num: int) -> List[ArgumentNode]:
        """获取特定轮次的节点"""
        return [n for n in self.nodes if n.round == round_num]
    
    def get_attackers(self, node_id: str) -> List[str]:
        """获取攻击某节点的所有节点ID"""
        return [e.from_node_id for e in self.edges if e.to_node_id == node_id]
    
    def get_attacked_by(self, node_id: str) -> List[str]:
        """获取某节点攻击的所有目标ID"""
        return [e.to_node_id for e in self.edges if e.from_node_id == node_id]
    
    def is_attacked(self, node_id: str) -> bool:
        """检查某节点是否被攻击"""
        return len(self.get_attackers(node_id)) > 0
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "total_nodes": len(self.nodes),
            "pro_nodes": len([n for n in self.nodes if n.agent == "pro"]),
            "con_nodes": len([n for n in self.nodes if n.agent == "con"]),
            "total_edges": len(self.edges),
            "nodes_by_round": {
                r: len(self.get_nodes_by_round(r))
                for r in set(n.round for n in self.nodes)
            }
        }
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "claim": self.claim,
            "nodes": [n.dict() for n in self.nodes],
            "edges": [e.dict() for e in self.edges],
            "statistics": self.get_statistics()
        }
    
    def save_to_file(self, filepath: str):
        """保存到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    
    def __len__(self):
        return len(self.nodes)
    
    def __str__(self):
        stats = self.get_statistics()
        return (
            f"ArgumentationGraph(claim='{self.claim[:50]}...', "
            f"nodes={stats['total_nodes']}, edges={stats['total_edges']})"
        )
