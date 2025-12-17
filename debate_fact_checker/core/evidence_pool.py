"""
证据池(Evidence Pool)
存储所有检索到的证据
"""

from typing import List, Optional
from utils.models import Evidence
import hashlib


class EvidencePool:
    """证据池 - 双方共享"""
    
    def __init__(self):
        self.evidences: List[Evidence] = []
        self._content_hashes = set()  # 用于去重
    
    def add_evidence(self, evidence: Evidence) -> bool:
        """
        添加单条证据
        返回: 是否成功添加(False表示重复)
        """
        # 基于内容去重
        content_hash = self._hash_content(evidence.content)
        if content_hash in self._content_hashes:
            return False
        
        self.evidences.append(evidence)
        self._content_hashes.add(content_hash)
        return True
    
    def add_evidences(self, evidences: List[Evidence]) -> int:
        """
        批量添加证据
        返回: 成功添加的数量
        """
        count = 0
        for evidence in evidences:
            if self.add_evidence(evidence):
                count += 1
        return count
    
    def _hash_content(self, content: str) -> str:
        """计算内容哈希用于去重"""
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        """通过ID获取证据"""
        for evidence in self.evidences:
            if evidence.id == evidence_id:
                return evidence
        return None
    
    def get_by_agent(self, agent: str) -> List[Evidence]:
        """获取特定Agent检索的证据"""
        return [e for e in self.evidences if e.retrieved_by == agent]
    
    def get_by_round(self, round_num: int) -> List[Evidence]:
        """获取特定轮次的证据"""
        return [e for e in self.evidences if e.round_num == round_num]
    
    def get_by_credibility(self, credibility: str) -> List[Evidence]:
        """获取特定可信度的证据"""
        return [e for e in self.evidences if e.credibility == credibility]
    
    def get_high_credibility(self) -> List[Evidence]:
        """获取高可信度证据"""
        return self.get_by_credibility("High")
    
    def __len__(self):
        return len(self.evidences)
    
    def __iter__(self):
        return iter(self.evidences)
    
    def __str__(self):
        return f"EvidencePool(size={len(self.evidences)})"
