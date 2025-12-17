"""
证据池 - 改进版
核心改进:每个证据作为独立节点,不再合并
"""
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class Evidence:
    """证据节点 - 每个证据是独立的论证节点"""
    id: str
    content: str
    url: str
    source: str  # 来源网站/机构
    credibility: str  # High/Medium/Low
    retrieved_by: str  # pro/con
    round_num: int
    search_query: str
    timestamp: datetime
    quality_score: float = 0.0  # 新增:质量分数(0-1)

    def get_priority(self) -> float:
        """计算优先级分数"""
        cred_map = {"High": 1.0, "Medium": 0.6, "Low": 0.3}
        base = cred_map.get(self.credibility, 0.5)
        return base * self.quality_score


class EvidencePool:
    """
    证据池 - 改进版

    核心改进:
    1. 每个证据作为独立节点存储
    2. 支持质量筛选
    3. 双方共享证据池
    """

    def __init__(self):
        self.evidences: Dict[str, Evidence] = {}
        self._evidence_count = 0

    def add_evidence(self, evidence: Evidence):
        """添加证据节点"""
        if evidence.id not in self.evidences:
            self.evidences[evidence.id] = evidence
            self._evidence_count += 1

    def add_batch(self, evidences: List[Evidence]):
        """批量添加证据"""
        for evidence in evidences:
            self.add_evidence(evidence)

    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        """根据ID获取证据"""
        return self.evidences.get(evidence_id)

    def get_by_agent(self, agent: str, round_num: int = None) -> List[Evidence]:
        """
        获取某个agent检索的证据
        可选:只返回特定轮次的证据
        """
        result = [e for e in self.evidences.values() if e.retrieved_by == agent]
        if round_num is not None:
            result = [e for e in result if e.round_num == round_num]
        return result

    def get_by_round(self, round_num: int) -> List[Evidence]:
        """获取某轮的所有证据"""
        return [e for e in self.evidences.values() if e.round_num == round_num]

    def get_high_quality(self, min_score: float = 0.6) -> List[Evidence]:
        """获取高质量证据(quality_score >= min_score)"""
        return [e for e in self.evidences.values() if e.quality_score >= min_score]

    def get_by_credibility(self, credibility: str) -> List[Evidence]:
        """根据可信度筛选"""
        return [e for e in self.evidences.values() if e.credibility == credibility]

    def get_all(self) -> List[Evidence]:
        """获取所有证据"""
        return list(self.evidences.values())

    def __len__(self) -> int:
        return len(self.evidences)

    def __repr__(self):
        return f"EvidencePool({len(self)} evidences)"

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self.evidences)
        if total == 0:
            return {"total": 0}

        pro_count = len(self.get_by_agent("pro"))
        con_count = len(self.get_by_agent("con"))
        high_quality = len(self.get_high_quality())
        high_cred = len(self.get_by_credibility("High"))

        return {
            "total": total,
            "pro": pro_count,
            "con": con_count,
            "high_quality": high_quality,
            "high_credibility": high_cred
        }