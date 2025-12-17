"""
Con Agent - 改进版
使用LangGraph框架,每个证据作为独立节点
"""
from typing import List, Dict
from datetime import datetime
import re

import sys

sys.path.insert(0, '/mnt/user-data/outputs')
from core.evidence_pool import Evidence, EvidencePool
from core.argumentation_graph import ArgumentationGraph, AttackEdge


class ConAgent:
    """
    反对方Agent - 改进版

    核心改进:
    1. 不再构建ArgumentNode,直接操作Evidence节点
    2. select_and_attack()从证据池选择证据并生成攻击边
    """

    def __init__(self, claim: str, llm_client):
        self.claim = claim
        self.llm = llm_client
        self.agent_name = "con"
        self.stance = "refute"

    def generate_search_queries(
            self,
            round_num: int,
            arg_graph: ArgumentationGraph,
            evidence_pool: EvidencePool
    ) -> List[str]:
        """生成搜索查询 - 寻找反驳证据"""
        # 获取正方证据
        pro_evidences = arg_graph.get_nodes_by_agent("pro")

        # 构建上下文
        if round_num == 1:
            context = f"这是第1轮。你需要找到反驳这个claim的证据。"
        else:
            context = f"这是第{round_num}轮。"
            if pro_evidences:
                context += f"\n正方已找到{len(pro_evidences)}个支持证据。"
                context += "\n你需要找到更强的反驳证据。"

        system_prompt = f"""你是事实核查的反方,需要找证据反驳claim: {self.claim}

你的目标是找到权威证据来证明这个claim是错误的或不准确的。"""

        user_prompt = f"""{context}

请生成{2 if round_num == 1 else 1}个搜索查询来反驳这个claim。

要求:
1. 查询要具体,能找到权威来源
2. 寻找反例、错误信息、过时数据，考虑从不同的角度反驳claim
3. 每个查询用一行,格式: 动机+查询claim

示例:
寻找蚂蚁集团官网的董事会成员信息，来证明程立目前不是蚂蚁集团的董事。

现在生成查询:"""

        messages = [{"role": "user", "content": user_prompt}]

        response = self.llm.chat(messages, system=system_prompt, temperature=0.7)

        # 解析查询
        queries = []
        for line in response.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 1:
                    query_text = parts[0].strip()
                    if query_text:
                        queries.append(query_text)

        return queries[:3]

    def select_and_attack(
            self,
            pool: EvidencePool,
            arg_graph: ArgumentationGraph,
            round_num: int
    ) -> List[AttackEdge]:
        """从证据池选择有利证据,攻击对方证据节点"""
        # 1. 获取己方高质量证据
        my_evidences = [e for e in pool.get_by_agent("con") if e.quality_score >= 0.6]

        # 2. 获取对方证据节点
        opponent_evidences = [e for e in arg_graph.evidence_nodes.values() if e.retrieved_by == "pro"]

        if not my_evidences or not opponent_evidences:
            return []

        # 3. 构建LLM prompt
        system_prompt = f"""你是反方,要用证据攻击正方的证据。

Claim: {self.claim}

你的任务:
1. 分析我方证据和对方证据的内容
2. 找出我方证据可以攻击对方证据的地方
3. 攻击必须基于:内容矛盾、可信度差异、权威性差异"""

        my_ev_text = "\n".join([
            f"[CON-{i + 1}] {e.content[:200]}... (来源:{e.source}, 可信度:{e.credibility}, 优先级:{e.get_priority():.2f})"
            for i, e in enumerate(my_evidences[:5])
        ])
        opp_ev_text = "\n".join([
            f"[PRO-{i + 1}] {e.content[:200]}... (来源:{e.source}, 可信度:{e.credibility}, 优先级:{e.get_priority():.2f})"
            for i, e in enumerate(opponent_evidences[:5])
        ])

        user_prompt = f"""我方证据:
{my_ev_text}

对方证据:
{opp_ev_text}

请分析哪些我方证据可以攻击对方证据。

要求:
1. 只有当我方证据的可信度/权威性更高时才能攻击
2. 必须有实质性的内容矛盾
3. 每行格式: CON-X攻击PRO-Y | 理由(50字内)

示例:
CON-1攻击PRO-2 | 我方来自IAU官方定义,对方是科普网站,权威性更高
CON-2攻击PRO-1 | 我方数据更新,直接反驳对方过时信息

现在分析(最多5个攻击):"""

        messages = [{"role": "user", "content": user_prompt}]

        response = self.llm.chat(messages, system=system_prompt, temperature=0.5)

        # 4. 解析攻击关系
        attacks = []
        for line in response.split('\n'):
            match = re.search(r'CON-(\d+)攻击PRO-(\d+)\s*\|\s*(.+)', line)
            if match:
                con_idx = int(match.group(1)) - 1
                pro_idx = int(match.group(2)) - 1
                rationale = match.group(3).strip()

                if con_idx < len(my_evidences) and pro_idx < len(opponent_evidences):
                    attacker = my_evidences[con_idx]
                    target = opponent_evidences[pro_idx]

                    # 验证优先级规则
                    if attacker.get_priority() > target.get_priority():
                        strength = attacker.get_priority() - target.get_priority()
                        attacks.append(AttackEdge(
                            attacker_id=attacker.id,
                            target_id=target.id,
                            strength=strength,
                            rationale=rationale,
                            round_num=round_num
                        ))

        return attacks