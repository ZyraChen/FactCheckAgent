
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class AttackEdge:
    """
    攻击边
    表示一个证据节点攻击另一个证据节点
    """
    attacker_id: str  # 攻击者证据ID
    target_id: str    # 被攻击者证据ID
    strength: float   # 攻击强度
    rationale: str    # 攻击理由
    round_num: int    # 哪一轮产生的攻击


class ArgumentationGraph:
    """
    论辩图 - 改进版

    核心改进:
    1. 节点是Evidence对象(每个证据独立)
    2. 边是AttackEdge(基于优先级的攻击关系)
    3. 支持Grounded Extension计算
    """

    def __init__(self, claim: str):
        self.claim = claim
        self.evidence_nodes: Dict[str, 'Evidence'] = {}  # 证据节点
        self.attack_edges: List[AttackEdge] = []  # 攻击边

    def add_evidence_node(self, evidence: 'Evidence'):
        """添加证据节点"""
        self.evidence_nodes[evidence.id] = evidence

    def add_evidence_nodes(self, evidences: List['Evidence']):
        """批量添加证据节点"""
        for evidence in evidences:
            self.add_evidence_node(evidence)

    def add_attack(self, edge: AttackEdge):
        """
        添加攻击边
        验证:只允许高优先级攻击低优先级
        """
        attacker = self.evidence_nodes.get(edge.attacker_id)
        target = self.evidence_nodes.get(edge.target_id)

        if not attacker or not target:
            print(f"警告:攻击边的节点不存在 {edge.attacker_id} -> {edge.target_id}")
            return

        # 验证优先级规则
        if attacker.get_priority() <= target.get_priority():
            print(f"警告:攻击被拒绝,优先级不足 {attacker.get_priority():.2f} <= {target.get_priority():.2f}")
            return

        self.attack_edges.append(edge)

    def add_attacks(self, edges: List[AttackEdge]):
        """批量添加攻击边"""
        for edge in edges:
            self.add_attack(edge)

    def get_attackers(self, target_id: str) -> List['Evidence']:
        """获取攻击某个节点的所有证据"""
        attacker_ids = [e.attacker_id for e in self.attack_edges if e.target_id == target_id]
        return [self.evidence_nodes[aid] for aid in attacker_ids if aid in self.evidence_nodes]

    def get_targets(self, attacker_id: str) -> List['Evidence']:
        """获取某个证据攻击的所有目标"""
        target_ids = [e.target_id for e in self.attack_edges if e.attacker_id == attacker_id]
        return [self.evidence_nodes[tid] for tid in target_ids if tid in self.evidence_nodes]

    def get_nodes_by_agent(self, agent: str) -> List['Evidence']:
        """获取某方的所有证据节点"""
        return [e for e in self.evidence_nodes.values() if e.retrieved_by == agent]

    def get_node_by_id(self, node_id: str) -> Optional['Evidence']:
        """根据ID获取节点"""
        return self.evidence_nodes.get(node_id)

    def compute_grounded_extension(self) -> Set[str]:
        """
        计算Grounded Extension - 可接受的证据集合

        算法:
        一个证据节点被接受,当且仅当:
        1. 没有攻击者, OR
        2. 所有攻击者都被击败
        """
        accepted = set()
        defeated = set()

        # 迭代直到稳定
        changed = True
        max_iterations = 100
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            for eid, evidence in self.evidence_nodes.items():
                if eid in accepted or eid in defeated:
                    continue

                # 检查所有攻击者
                attackers = self.get_attackers(eid)

                if not attackers:
                    # 没有攻击者,接受
                    accepted.add(eid)
                    changed = True
                else:
                    # 检查攻击者是否都被击败
                    all_defeated = all(a.id in defeated for a in attackers)
                    if all_defeated:
                        accepted.add(eid)
                        changed = True

                    # 检查是否被高优先级攻击
                    for attacker in attackers:
                        if attacker.id in accepted and attacker.get_priority() > evidence.get_priority():
                            defeated.add(eid)
                            changed = True
                            break

        return accepted

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        pro_nodes = self.get_nodes_by_agent("pro")
        con_nodes = self.get_nodes_by_agent("con")

        return {
            "total_evidences": len(self.evidence_nodes),
            "total_attacks": len(self.attack_edges),
            "pro_evidences": len(pro_nodes),
            "con_evidences": len(con_nodes),
            "avg_pro_priority": sum(e.get_priority() for e in pro_nodes) / max(len(pro_nodes), 1),
            "avg_con_priority": sum(e.get_priority() for e in con_nodes) / max(len(con_nodes), 1)
        }

    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "claim": self.claim,
            "evidence_nodes": [
                {
                    "id": e.id,
                    "content": e.content[:200],
                    "url": e.url,
                    "source": e.source,
                    "credibility": e.credibility,
                    "retrieved_by": e.retrieved_by,
                    "round_num": e.round_num,
                    "priority": e.get_priority(),
                    "quality_score": e.quality_score
                }
                for e in self.evidence_nodes.values()
            ],
            "attack_edges": [
                {
                    "attacker_id": edge.attacker_id,
                    "target_id": edge.target_id,
                    "strength": edge.strength,
                    "rationale": edge.rationale,
                    "round_num": edge.round_num
                }
                for edge in self.attack_edges
            ],
            "statistics": self.get_statistics()
        }

    def save_to_file(self, filepath: str):
        """保存到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)