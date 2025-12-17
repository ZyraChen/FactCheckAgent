"""
Judge Agent: 独立法官
基于完整的论辩图做最终判决
"""

from typing import List, Set
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from utils.models import Verdict, ArgumentNode
from llm.qwen_client import QwenClient
from reasoning.semantics import compute_grounded_extension


class JudgeAgent:
    """法官Agent"""
    
    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client
    
    def make_verdict(
        self,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> Verdict:
        """
        做出最终判决
        
        步骤:
        1. 计算grounded extension(可接受论证集)
        2. 分析双方论证强度
        3. 评估证据质量
        4. 生成判决
        """
        print("\n========== Judge开始判决 ==========")
        
        # 1. 计算可接受论证集
        acceptable_args = compute_grounded_extension(arg_graph)
        print(f"可接受的论证: {len(acceptable_args)} 个")
        
        # 2. 分析双方强度
        pro_strength = self._evaluate_side(
            arg_graph, acceptable_args, "pro"
        )
        con_strength = self._evaluate_side(
            arg_graph, acceptable_args, "con"
        )
        
        print(f"Pro强度: {pro_strength:.3f}, Con强度: {con_strength:.3f}")
        
        # 3. 确定判决
        if abs(pro_strength - con_strength) < 0.1:
            decision = "NEI"  # 证据不足
            confidence = 0.5
        elif pro_strength > con_strength:
            decision = "Supported"
            confidence = pro_strength / (pro_strength + con_strength)
        else:
            decision = "Refuted"
            confidence = con_strength / (pro_strength + con_strength)
        
        # 4. 提取关键证据
        key_evidence_ids = self._extract_key_evidence(
            arg_graph, acceptable_args, evidence_pool
        )
        
        # 5. 生成详细推理
        reasoning = self._generate_reasoning(
            arg_graph, acceptable_args, decision, evidence_pool
        )
        
        # 6. 构建判决对象
        verdict = Verdict(
            decision=decision,
            confidence=float(confidence),
            reasoning=reasoning,
            key_evidence=key_evidence_ids,
            acceptable_arguments=[node_id for node_id in acceptable_args],
            argument_analysis={
                "pro_strength": float(pro_strength),
                "con_strength": float(con_strength),
                "total_pro_args": len(arg_graph.get_nodes_by_agent("pro")),
                "total_con_args": len(arg_graph.get_nodes_by_agent("con")),
                "accepted_pro_args": sum(
                    1 for nid in acceptable_args 
                    if arg_graph.get_node_by_id(nid).agent == "pro"
                ),
                "accepted_con_args": sum(
                    1 for nid in acceptable_args
                    if arg_graph.get_node_by_id(nid).agent == "con"
                )
            }
        )
        
        return verdict
    
    def _evaluate_side(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        agent: str
    ) -> float:
        """评估某一方的论证强度"""
        side_nodes = arg_graph.get_nodes_by_agent(agent)
        
        if not side_nodes:
            return 0.0
        
        # 统计被接受的论证
        accepted_nodes = [
            n for n in side_nodes 
            if n.id in acceptable_args
        ]
        
        if not accepted_nodes:
            return 0.0
        
        # 强度 = 被接受论证的平均优先级 * 接受比例
        avg_priority = sum(n.priority for n in accepted_nodes) / len(accepted_nodes)
        acceptance_ratio = len(accepted_nodes) / len(side_nodes)
        
        strength = avg_priority * acceptance_ratio
        
        return strength
    
    def _extract_key_evidence(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        evidence_pool: EvidencePool
    ) -> List[str]:
        """提取关键证据"""
        key_evidence_ids = set()
        
        for node_id in acceptable_args:
            node = arg_graph.get_node_by_id(node_id)
            if node:
                key_evidence_ids.update(node.evidence_ids)
        
        return list(key_evidence_ids)
    
    def _generate_reasoning(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        decision: str,
        evidence_pool: EvidencePool
    ) -> str:
        """
        使用LLM生成人类可读的推理过程
        """
        # 准备上下文
        accepted_nodes_info = []
        for node_id in acceptable_args:
            node = arg_graph.get_node_by_id(node_id)
            if node:
                evidences = [
                    evidence_pool.get_by_id(eid)
                    for eid in node.evidence_ids
                ]
                evidence_texts = [
                    f"{e.content[:100]}... (来源: {e.url}, 可信度: {e.credibility})"
                    for e in evidences if e
                ]
                
                accepted_nodes_info.append({
                    "agent": node.agent,
                    "content": node.content,
                    "priority": node.priority,
                    "evidences": evidence_texts
                })
        
        system = """你是一个事实核查判决专家。
基于论辩分析的结果,生成清晰的推理过程说明。

要求:
1. 解释为什么做出这个判决
2. 说明关键证据的作用
3. 解释双方论证的优劣
4. 保持客观中立
"""
        
        prompt = f"""
待核查主张: {arg_graph.claim}

判决结果: {decision}

被接受的论证:
{chr(10).join(f"{i+1}. [{info['agent'].upper()}] {info['content'][:200]}... (优先级: {info['priority']:.2f})" for i, info in enumerate(accepted_nodes_info))}

请生成详细的推理过程(200-300字):
"""
        
        messages = [{"role": "user", "content": prompt}]
        reasoning = self.llm.chat(messages, system, temperature=0.5, max_tokens=1000)
        
        return reasoning if reasoning else "推理生成失败"
