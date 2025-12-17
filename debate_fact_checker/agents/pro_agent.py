"""
Pro Agent: 支持claim的辩论方
"""

from typing import List, Dict
from utils.models import ArgumentNode, Evidence, SearchQuery
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from llm.qwen_client import QwenClient
from tools.priority_calculator import calculate_priority
import uuid


class ProAgent:
    """支持方Agent"""
    
    def __init__(self, claim: str, llm_client: QwenClient):
        self.claim = claim
        self.llm = llm_client
        self.stance = "support"
        self.agent_name = "pro"
    
    def generate_search_queries(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[SearchQuery]:
        """
        生成搜索查询
        策略:
        - 第1轮: 直接搜索claim相关证据
        - 第2-3轮: 针对对手论点的防御性搜索
        """
        # 获取对手最新论点
        con_nodes = [
            n for n in arg_graph.get_nodes_by_agent("con")
            if n.round == round_num - 1 or round_num == 1
        ]
        opponent_args = [n.content for n in con_nodes]
        
        # 已有主题(避免重复)
        existing_queries = [e.search_query for e in evidence_pool.evidences]
        
        # 调用LLM生成查询词
        queries = self.llm.generate_search_queries(
            claim=self.claim,
            agent_role="支持方(Pro)",
            current_round=round_num,
            opponent_args=opponent_args,
            existing_topics=existing_queries
        )
        
        # 包装为SearchQuery对象
        search_queries = []
        for q in queries[:5]:  # 最多5个
            search_queries.append(SearchQuery(
                query=q,
                agent="pro",
                round=round_num,
                rationale=f"第{round_num}轮支持方搜索"
            ))
        
        return search_queries
    
    def construct_arguments(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[ArgumentNode]:
        """
        构建论证节点
        """
        new_nodes = []
        
        # 1. 选择有利证据
        relevant_evidences = self._select_favorable_evidences(
            evidence_pool, arg_graph, round_num
        )
        
        if not relevant_evidences:
            print(f"Pro Agent第{round_num}轮未找到有利证据")
            return []
        
        # 2. 获取对手论点(用于攻击)
        con_nodes = arg_graph.get_nodes_by_agent("con")
        opponent_args = [
            {"id": n.id, "content": n.content, "priority": n.priority}
            for n in con_nodes
        ]
        
        # 3. 调用LLM构建论证
        evidence_list = [
            {
                "id": e.id,
                "content": e.content,
                "url": e.url,
                "credibility": e.credibility
            }
            for e in relevant_evidences
        ]
        
        llm_result = self.llm.construct_argument(
            claim=self.claim,
            agent_role="支持方(Pro) - 你要证明这个claim是正确的",
            evidence_list=evidence_list,
            opponent_args=opponent_args,
            round_num=round_num
        )
        
        if not llm_result:
            return []
        
        # 4. 创建论证节点
        used_evidence_ids = [
            relevant_evidences[i].id 
            for i in llm_result.get("key_evidence_indices", [0])
            if i < len(relevant_evidences)
        ]
        
        # 计算优先级
        used_evidences = [evidence_pool.get_by_id(eid) for eid in used_evidence_ids]
        priority = calculate_priority(used_evidences)
        
        node = ArgumentNode(
            id=f"pro_arg_{round_num}_{uuid.uuid4().hex[:8]}",
            agent="pro",
            round=round_num,
            content=llm_result.get("argument", ""),
            evidence_ids=used_evidence_ids,
            priority=priority,
            stance="support_claim"
        )
        
        new_nodes.append(node)
        
        return new_nodes
    
    def _select_favorable_evidences(
        self,
        evidence_pool: EvidencePool,
        arg_graph: ArgumentationGraph,
        round_num: int
    ) -> List[Evidence]:
        """
        从证据池筛选对己方有利的证据
        优先选择:
        1. 高可信度
        2. 本轮或最近轮次的
        3. 内容与claim相关
        """
        candidates = []
        
        for evidence in evidence_pool.evidences:
            # 优先本轮和上一轮的证据
            if evidence.round_num <= round_num:
                # 简单的相关性判断(实际应该用语义相似度)
                if any(word in evidence.content for word in self.claim.split()):
                    candidates.append(evidence)
        
        # 按可信度排序
        candidates.sort(
            key=lambda e: {"High": 3, "Medium": 2, "Low": 1}[e.credibility],
            reverse=True
        )
        
        # 返回top 5
        return candidates[:5]
