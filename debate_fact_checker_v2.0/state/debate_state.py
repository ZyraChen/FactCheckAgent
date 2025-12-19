"""
辩论系统的全局状态
类似LangGraph的State,所有节点共享
"""

from typing import TypedDict, List, Annotated, Optional
from operator import add
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from utils.models import SearchQuery, Verdict


class DebateState(TypedDict):
    """全局辩论状态"""
    
    # ========== 输入 ==========
    claim: str                         # 待核查的主张
    max_rounds: int                    # 最大轮次(默认3)
    
    # ========== 控制流 ==========
    current_round: int                 # 当前轮次(1-3)
    should_continue: bool              # 是否继续下一轮
    is_complete: bool                  # 是否完成所有轮次
    
    # ========== 共享数据结构 ==========
    evidence_pool: EvidencePool        # 证据池(双方共享)
    arg_graph: ArgumentationGraph      # 论辩图(双方共享)
    
    # ========== Pro Agent的状态 ==========
    pro_search_queries: Annotated[List[SearchQuery], add]  # 累积的搜索query对象
    pro_arguments: Annotated[List[ArgumentNode], add]      # Pro的所有论证节点
    pro_reflection: str                                    # Pro当前轮的反思
    pro_search_results: List[dict]                         # Pro本轮搜索结果(临时)
    
    # ========== Con Agent的状态 ==========
    con_search_queries: Annotated[List[SearchQuery], add]
    con_arguments: Annotated[List[ArgumentNode], add]
    con_reflection: str
    con_search_results: List[dict]
    
    # ========== 最终判决 ==========
    verdict: Optional[Verdict]         # Judge的判决结果
    
    # ========== 日志/调试 ==========
    logs: Annotated[List[str], add]    # 系统日志
