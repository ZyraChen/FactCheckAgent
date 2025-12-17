"""
数据模型定义
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Evidence(BaseModel):
    """证据数据模型 - 完整信息"""
    id: str                                          # 证据ID
    content: str                                     # 证据主要内容
    url: str                                         # 证据来源URL
    title: str = ""                                  # 网页标题
    source: str = ""                                 # 来源网站名称(如wikipedia.org)
    credibility: Literal["High", "Medium", "Low"]    # 可信度
    retrieved_by: Literal["pro", "con"]              # 谁检索的
    round_num: int                                   # 第几轮检索的
    search_query: str                                # 使用的搜索词
    timestamp: datetime = Field(default_factory=datetime.now)  # 检索时间戳

    def to_display_dict(self):
        """转换为适合展示的字典格式"""
        from urllib.parse import urlparse

        # 从URL提取域名作为来源
        if self.url:
            parsed = urlparse(self.url)
            source = parsed.netloc.replace('www.', '')
        else:
            source = self.source or "未知来源"

        return {
            "证据ID": self.id,
            "主要内容": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "完整内容": self.content,
            "标题": self.title,
            "来源": source,
            "URL": self.url,
            "可信度": self.credibility,
            "检索者": "支持方" if self.retrieved_by == "pro" else "反驳方",
            "检索轮次": self.round_num,
            "搜索查询": self.search_query,
            "时间戳": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }


class ArgumentNode(BaseModel):
    """论证节点"""
    id: str
    agent: Literal["pro", "con"]
    round: int
    content: str  # 论证内容
    evidence_ids: List[str]  # 支持该论证的证据ID
    priority: float  # 优先级(基于证据可信度计算)
    stance: Literal["support_claim", "refute_claim"]  # 对原始claim的立场

    class Config:
        frozen = False


class AttackEdge(BaseModel):
    """攻击边(仅高优先级→低优先级)"""
    from_node_id: str
    to_node_id: str
    strength: float  # 攻击强度
    rationale: str  # 为什么攻击


class SearchQuery(BaseModel):
    """搜索查询"""
    query: str
    agent: Literal["pro", "con"]
    round: int
    rationale: str  # 为什么要搜这个


class Verdict(BaseModel):
    """最终判决"""
    decision: Literal["Supported", "Refuted", "NEI"]  # 支持/反驳/证据不足
    confidence: float  # 0-1
    reasoning: str  # 推理过程
    key_evidence: List[str]  # 关键证据ID
    acceptable_arguments: List[str]  # 被接受的论证节点ID
    argument_analysis: dict  # 双方论证分析


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