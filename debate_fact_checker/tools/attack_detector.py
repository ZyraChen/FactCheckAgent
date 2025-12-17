"""
攻击关系检测
检测论辩图中的攻击关系(仅高优先级→低优先级)
"""

from typing import List
from core.argumentation_graph import ArgumentationGraph
from utils.models import AttackEdge, ArgumentNode
from llm.qwen_client import QwenClient


class AttackDetector:
    """攻击关系检测器"""
    
    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client
    
    def detect_attacks_for_round(
        self,
        arg_graph: ArgumentationGraph,
        round_num: int
    ) -> List[AttackEdge]:
        """
        检测本轮新增节点与已有节点之间的攻击关系
        
        规则:
        1. 只检测高优先级→低优先级的攻击
        2. 对立立场之间才可能存在攻击(pro vs con)
        3. 使用LLM判断是否构成攻击
        """
        new_edges = []
        
        # 获取本轮新增的节点
        new_nodes = arg_graph.get_nodes_by_round(round_num)
        
        # 获取所有已有节点(包括本轮)
        all_nodes = arg_graph.nodes
        
        for new_node in new_nodes:
            for existing_node in all_nodes:
                # 跳过自己
                if new_node.id == existing_node.id:
                    continue
                
                # 只检测对立立场
                if new_node.agent == existing_node.agent:
                    continue
                
                # 只检测高优先级→低优先级
                if new_node.priority <= existing_node.priority:
                    continue
                
                # 使用LLM判断是否攻击
                is_attack, rationale = self._check_if_attacks(
                    attacker=new_node,
                    target=existing_node
                )
                
                if is_attack:
                    edge = AttackEdge(
                        from_node_id=new_node.id,
                        to_node_id=existing_node.id,
                        strength=new_node.priority - existing_node.priority,
                        rationale=rationale
                    )
                    new_edges.append(edge)
        
        return new_edges
    
    def _check_if_attacks(
        self,
        attacker: ArgumentNode,
        target: ArgumentNode
    ) -> tuple[bool, str]:
        """
        使用LLM判断node_a是否攻击node_b
        
        返回: (是否攻击, 理由)
        """
        system = """你是一个论辩分析专家。
你的任务是判断论证A是否攻击(反驳/削弱)论证B。

攻击的定义:
- A的内容与B相矛盾
- A提供的证据否定了B的结论
- A指出了B的逻辑漏洞
- A提供了更权威的相反信息

返回JSON格式:
{
  "is_attack": true/false,
  "rationale": "判断理由"
}
"""
        
        prompt = f"""
论证A (攻击方):
- 立场: {attacker.stance}
- 内容: {attacker.content}
- 优先级: {attacker.priority}

论证B (被攻击方):
- 立场: {target.stance}
- 内容: {target.content}
- 优先级: {target.priority}

请判断A是否攻击B。
"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self.llm.chat_with_json(messages, system, temperature=0.3)
        
        is_attack = result.get("is_attack", False)
        rationale = result.get("rationale", "未提供理由")
        
        return is_attack, rationale


# 简化版本(不使用LLM,基于规则)
def detect_attacks_simple(
    arg_graph: ArgumentationGraph,
    round_num: int
) -> List[AttackEdge]:
    """
    简化版攻击检测(不使用LLM)
    规则: 对立立场 + 高优先级 → 自动攻击
    """
    new_edges = []
    new_nodes = arg_graph.get_nodes_by_round(round_num)
    all_nodes = arg_graph.nodes
    
    for new_node in new_nodes:
        for existing_node in all_nodes:
            if new_node.id == existing_node.id:
                continue
            
            # 对立立场
            if new_node.agent == existing_node.agent:
                continue
            
            # 高优先级攻击低优先级
            if new_node.priority > existing_node.priority:
                edge = AttackEdge(
                    from_node_id=new_node.id,
                    to_node_id=existing_node.id,
                    strength=new_node.priority - existing_node.priority,
                    rationale=f"{new_node.agent}的论证(优先级{new_node.priority:.2f})攻击{existing_node.agent}的论证(优先级{existing_node.priority:.2f})"
                )
                new_edges.append(edge)
    
    return new_edges
