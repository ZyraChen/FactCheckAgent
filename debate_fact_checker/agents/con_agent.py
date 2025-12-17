"""
Con Agent: 反对claim的辩论方
"""

from typing import List, Dict
from utils.models import ArgumentNode, Evidence, SearchQuery
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from llm.qwen_client import QwenClient
from tools.priority_calculator import calculate_priority
import uuid


class ConAgent:
    """反对方Agent"""
    
    def __init__(self, claim: str, llm_client: QwenClient):
        self.claim = claim
        self.llm = llm_client
        self.stance = "refute"
        self.agent_name = "con"
    
    def generate_search_queries(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[SearchQuery]:
        """生成搜索查询 - 寻找反驳证据"""
        # 获取Pro的最新论点
        pro_nodes = [
            n for n in arg_graph.get_nodes_by_agent("pro")
            if n.round == round_num - 1 or round_num == 1
        ]
        opponent_args = [n.content for n in pro_nodes]
        
        # 已有主题
        existing_queries = [e.search_query for e in evidence_pool.evidences]
        
        # 调用LLM生成查询词
        queries = self.llm.generate_search_queries(
            claim=self.claim,
            agent_role="反对方(Con) - 寻找反驳claim的证据",
            current_round=round_num,
            opponent_args=opponent_args,
            existing_topics=existing_queries
        )
        
        # 包装为SearchQuery对象
        search_queries = []
        for q in queries[:5]:
            search_queries.append(SearchQuery(
                query=q,
                agent="con",
                round=round_num,
                rationale=f"第{round_num}轮反对方搜索"
            ))
        
        return search_queries
    
    def construct_arguments(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[ArgumentNode]:
        """
        构建反驳论证
        Con可以看到Pro本轮新增的节点!
        """
        new_nodes = []
        
        # 1. 选择有利证据(反驳性证据)
        relevant_evidences = self._select_refuting_evidences(
            evidence_pool, arg_graph, round_num
        )
        
        if not relevant_evidences:
            print(f"Con Agent第{round_num}轮未找到反驳证据")
            return []
        
        # 2. 获取Pro的论点(特别是本轮的)
        pro_nodes = arg_graph.get_nodes_by_agent("pro")
        opponent_args = [
            {"id": n.id, "content": n.content, "priority": n.priority}
            for n in pro_nodes
        ]
        
        # 3. 调用LLM构建反驳论证
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
            agent_role="反对方(Con) - 你要证明这个claim是错误的或不准确的",
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
            id=f"con_arg_{round_num}_{uuid.uuid4().hex[:8]}",
            agent="con",
            round=round_num,
            content=llm_result.get("argument", ""),
            evidence_ids=used_evidence_ids,
            priority=priority,
            stance="refute_claim"
        )
        
        new_nodes.append(node)
        
        return new_nodes
    
    def _select_refuting_evidences(
        self,
        evidence_pool: EvidencePool,
        arg_graph: ArgumentationGraph,
        round_num: int
    ) -> List[Evidence]:
        """选择反驳性证据"""
        candidates = []
        
        for evidence in evidence_pool.evidences:
            if evidence.round_num <= round_num:
                # 简单的反驳性判断
                # 实际应该用语义分析判断是否与claim矛盾
                candidates.append(evidence)
        
        # 按可信度排序
        candidates.sort(
            key=lambda e: {"High": 3, "Medium": 2, "Low": 1}[e.credibility],
            reverse=True
        )
        
        return candidates[:5]
