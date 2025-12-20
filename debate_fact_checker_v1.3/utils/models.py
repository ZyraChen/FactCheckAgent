"""
统一数据模型定义
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Evidence(BaseModel):
    """
    证据数据模型
    每个搜索结果对应一个证据对象
    """
    id: str
    content: str  # 证据内容
    url: str  # 来源URL
    title: str = ""  # 网页标题
    source: str = ""  # 来源网站名称(如wikipedia.org)
    credibility: Literal["High", "Medium", "Low"]  # 可信度
    retrieved_by: Literal["pro", "con"]  # 谁检索的
    round_num: int  # 第几轮检索的
    search_query: str  # 使用的搜索词
    timestamp: datetime = Field(default_factory=datetime.now)
    quality_score: float = 0.0  # 质量分数(0-1)

    class Config:
        frozen = False

    def get_priority(self) -> float:
        """计算优先级分数"""
        cred_map = {"High": 1.0, "Medium": 0.6, "Low": 0.3}
        base = cred_map.get(self.credibility, 0.5)
        return base * self.quality_score


class AttackEdge(BaseModel):
    """
    攻击边
    表示一个证据攻击另一个证据
    """
    from_evidence_id: str  # 攻击者证据ID
    to_evidence_id: str  # 被攻击者证据ID
    strength: float  # 攻击强度(优先级差)
    rationale: str  # 攻击理由
    round_num: int  # 哪一轮产生的攻击

    class Config:
        frozen = False


class SearchQuery(BaseModel):
    """搜索查询"""
    query: str
    agent: Literal["pro", "con"]
    round: int
    rationale: str  # 为什么要搜这个


class Verdict(BaseModel):
    """最终判决"""
    decision: Literal["Supported", "Refuted", "Not Enough Evidence"]
    confidence: float  # 0-1
    reasoning: str  # 推理过程
    key_evidence_ids: List[str] = []  # 关键证据ID列表
    accepted_evidence_ids: List[str] = []  # 被接受的证据ID列表
    pro_strength: float = 0.0
    con_strength: float = 0.0
    total_evidences: int = 0
    accepted_evidences: int = 0
    publish_date: Optional[datetime] = None  # 证据发布时间
    retrieved_at: datetime = Field(default_factory=datetime.now)  # 检索时间


class ClaimData(BaseModel):
    """数据集中的一条claim"""
    claim: str
    verdict: Optional[str] = None
    error_type: Optional[str] = None
    category: Optional[str] = None
    justification: Optional[str] = None
    evidence_sources: Optional[List[dict]] = None
    correct_answer: Optional[str] = None
    topic: Optional[str] = None
