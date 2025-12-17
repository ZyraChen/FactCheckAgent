"""
Judge Agent - 改进版
解决问题: 即使有冲突证据也能做出判决

改进:
1. 计算Grounded Extension后,评估冲突程度
2. 如果冲突严重,使用"最强论证胜出"策略
3. 降低NEI的阈值,增加Supported/Refuted判决

注意: 完全兼容原框架接口 - 使用ArgumentNode,接收3个参数
"""

from typing import List, Set
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from utils.models import Verdict, ArgumentNode
from llm.qwen_client import QwenClient
from reasoning.semantics import compute_grounded_extension


class JudgeAgent:
    """法官Agent - 改进版(兼容原框架)"""

    def __init__(self, llm_client: QwenClient):
        self.llm = llm_client

    def make_verdict(
        self,
        claim: str,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> Verdict:
        """
        做出最终判决 - 改进版

        参数:
            claim: 原始claim文本
            arg_graph: 论辩图(包含ArgumentNode)
            evidence_pool: 证据池

        关键改进:
        1. 即使双方都有被接受的论证,也能做出判决
        2. 基于"最强论证"和"主导方"策略
        3. 只有在真正无法判断时才返回NEI
        """
        print("\n========== Judge判决 (改进版) ==========")
        print(f"Claim: {claim}")

        # 1. 计算Grounded Extension
        acceptable_args = compute_grounded_extension(arg_graph)
        print(f"可接受的论证: {len(acceptable_args)} 个")

        # 2. 分析双方
        pro_accepted = [n for n in arg_graph.nodes if n.id in acceptable_args and n.agent == "pro"]
        con_accepted = [n for n in arg_graph.nodes if n.id in acceptable_args and n.agent == "con"]

        print(f"Pro被接受: {len(pro_accepted)}个, Con被接受: {len(con_accepted)}个")

        # 3. 计算双方强度
        pro_strength = self._calculate_strength(pro_accepted)
        con_strength = self._calculate_strength(con_accepted)

        print(f"Pro强度: {pro_strength:.3f}, Con强度: {con_strength:.3f}")

        # 4. 判决策略 - 改进版
        decision, confidence = self._make_decision_improved(
            pro_accepted, con_accepted, pro_strength, con_strength
        )

        print(f"判决: {decision}, 置信度: {confidence:.2f}")

        # 5. 生成推理
        reasoning = self._generate_reasoning(
            claim, arg_graph, acceptable_args, decision, pro_accepted, con_accepted
        )

        # 6. 提取关键证据
        key_evidence = self._extract_key_evidence(pro_accepted, con_accepted, decision)

        return Verdict(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_evidence=key_evidence
        )

    def _calculate_strength(self, accepted_nodes: List[ArgumentNode]) -> float:
        """计算一方的强度"""
        if not accepted_nodes:
            return 0.0

        # 加权平均优先级
        total_priority = sum(n.priority for n in accepted_nodes)
        avg_priority = total_priority / len(accepted_nodes)

        # 考虑数量因素
        count_factor = min(1.0, len(accepted_nodes) / 3)  # 3个论证达到满分

        return avg_priority * 0.7 + count_factor * 0.3

    def _make_decision_improved(
        self,
        pro_accepted: List[ArgumentNode],
        con_accepted: List[ArgumentNode],
        pro_strength: float,
        con_strength: float
    ) -> tuple[str, float]:
        """
        改进的判决策略

        关键改进:
        1. 只有双方势均力敌时才NEI
        2. 即使双方都有论证,只要有明显优势就判决
        3. 降低NEI阈值从0.1到0.05
        """
        # 情况1: 一方没有被接受的论证
        if not pro_accepted and not con_accepted:
            return "NEI", 0.3

        if not pro_accepted:
            return "Refuted", min(0.95, 0.7 + con_strength * 0.3)

        if not con_accepted:
            return "Supported", min(0.95, 0.7 + pro_strength * 0.3)

        # 情况2: 双方都有论证 - 比较强度
        strength_diff = abs(pro_strength - con_strength)

        # 改进:只要差距>5%就判决,不再要求>10%
        if strength_diff > 0.05:  # 降低阈值
            if pro_strength > con_strength:
                confidence = 0.5 + (strength_diff * 0.5)  # 0.5-1.0
                return "Supported", min(0.95, confidence)
            else:
                confidence = 0.5 + (strength_diff * 0.5)
                return "Refuted", min(0.95, confidence)

        # 情况3: 真正的势均力敌 - 比较论证质量
        max_pro_priority = max((n.priority for n in pro_accepted), default=0)
        max_con_priority = max((n.priority for n in con_accepted), default=0)

        if max_pro_priority > max_con_priority + 0.05:
            return "Supported", 0.55
        elif max_con_priority > max_pro_priority + 0.05:
            return "Refuted", 0.55
        else:
            # 最后手段:比较数量
            if len(pro_accepted) > len(con_accepted):
                return "Supported", 0.52
            elif len(con_accepted) > len(pro_accepted):
                return "Refuted", 0.52
            else:
                return "NEI", 0.50

    def _generate_reasoning(
        self,
        claim: str,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        decision: str,
        pro_accepted: List[ArgumentNode],
        con_accepted: List[ArgumentNode]
    ) -> str:
        """生成推理过程"""

        # 准备论证描述
        pro_desc = ", ".join([f"{n.id}(P={n.priority:.2f})" for n in pro_accepted[:3]])
        con_desc = ", ".join([f"{n.id}(P={n.priority:.2f})" for n in con_accepted[:3]])

        # 攻击关系统计
        total_attacks = len(arg_graph.edges)

        system = """你是事实核查专家,生成简洁的判决解释。

要求:
1. 说明考虑了哪些论证(Pro/Con)
2. 解释为什么某一方更有说服力
3. 提及关键的攻击关系
4. 200字以内"""

        prompt = f"""Claim: {claim}
判决: {decision}

被接受的Pro论证({len(pro_accepted)}个): {pro_desc or "无"}
被接受的Con论证({len(con_accepted)}个): {con_desc or "无"}

论辩图统计:
- 总论证: {len(arg_graph.nodes)}个
- 攻击边: {total_attacks}条
- 被接受: {len(acceptable_args)}个

请生成判决推理(200字内):"""

        messages = [{"role": "user", "content": prompt}]

        try:
            reasoning = self.llm.chat(messages, system=system, temperature=0.5)
            return reasoning if reasoning else f"基于论辩分析,判决为{decision}。"
        except Exception as e:
            print(f"推理生成失败: {e}")
            return f"基于{len(acceptable_args)}个被接受的论证,判决为{decision}。"

    def _extract_key_evidence(
        self,
        pro_accepted: List[ArgumentNode],
        con_accepted: List[ArgumentNode],
        decision: str
    ) -> List[str]:
        """提取关键证据ID"""
        if decision == "Supported":
            key_nodes = sorted(pro_accepted, key=lambda n: n.priority, reverse=True)[:3]
        elif decision == "Refuted":
            key_nodes = sorted(con_accepted, key=lambda n: n.priority, reverse=True)[:3]
        else:
            # NEI: 取双方最强的
            all_nodes = sorted(
                pro_accepted + con_accepted,
                key=lambda n: n.priority,
                reverse=True
            )[:3]
            key_nodes = all_nodes

        # 返回证据ID
        evidence_ids = []
        for node in key_nodes:
            evidence_ids.extend(node.evidence_ids[:2])  # 每个节点取前2个证据

        return evidence_ids[:5]  # 最多5个

    def _evaluate_side(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        agent: str
    ) -> float:
        """评估一方的强度(旧方法,兼容性保留)"""
        side_nodes = [
            n for n in arg_graph.nodes
            if n.id in acceptable_args and n.agent == agent
        ]

        if not side_nodes:
            return 0.0

        avg_priority = sum(n.priority for n in side_nodes) / len(side_nodes)
        count_factor = len(side_nodes) / (len(side_nodes) + 3)

        return avg_priority * count_factor


        # 2. 分析双方
        pro_accepted = [n for n in arg_graph.nodes if n.id in acceptable_args and n.agent == "pro"]
        con_accepted = [n for n in arg_graph.nodes if n.id in acceptable_args and n.agent == "con"]

        print(f"Pro被接受: {len(pro_accepted)}个, Con被接受: {len(con_accepted)}个")

        # 3. 计算双方强度
        pro_strength = self._calculate_strength(pro_accepted)
        con_strength = self._calculate_strength(con_accepted)

        print(f"Pro强度: {pro_strength:.3f}, Con强度: {con_strength:.3f}")

        # 4. 判决策略 - 改进版
        decision, confidence = self._make_decision_improved(
            pro_accepted, con_accepted, pro_strength, con_strength
        )

        print(f"判决: {decision}, 置信度: {confidence:.2f}")

        # 5. 生成推理
        reasoning = self._generate_reasoning(
            arg_graph, acceptable_args, decision, pro_accepted, con_accepted
        )

        # 6. 提取关键证据
        key_evidence = self._extract_key_evidence(pro_accepted, con_accepted, decision)

        return Verdict(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_evidence=key_evidence
        )

    def _calculate_strength(self, accepted_nodes: List) -> float:
        """计算一方的强度"""
        if not accepted_nodes:
            return 0.0

        # 加权平均优先级
        total_priority = sum(n.priority for n in accepted_nodes)
        avg_priority = total_priority / len(accepted_nodes)

        # 考虑数量因素
        count_factor = min(1.0, len(accepted_nodes) / 3)  # 3个论证达到满分

        return avg_priority * 0.7 + count_factor * 0.3

    def _make_decision_improved(
        self,
        pro_accepted: List,
        con_accepted: List,
        pro_strength: float,
        con_strength: float
    ) -> tuple[str, float]:
        """
        改进的判决策略

        关键改进:
        1. 只有双方势均力敌时才NEI
        2. 即使双方都有论证,只要有明显优势就判决
        3. 降低NEI阈值从0.1到0.05
        """
        # 情况1: 一方没有被接受的论证
        if not pro_accepted and not con_accepted:
            return "NEI", 0.3

        if not pro_accepted:
            return "Refuted", min(0.95, 0.7 + con_strength * 0.3)

        if not con_accepted:
            return "Supported", min(0.95, 0.7 + pro_strength * 0.3)

        # 情况2: 双方都有论证 - 比较强度
        strength_diff = abs(pro_strength - con_strength)

        # 改进:只要差距>5%就判决,不再要求>10%
        if strength_diff > 0.05:  # 降低阈值
            if pro_strength > con_strength:
                confidence = 0.5 + (strength_diff * 0.5)  # 0.5-1.0
                return "Supported", min(0.95, confidence)
            else:
                confidence = 0.5 + (strength_diff * 0.5)
                return "Refuted", min(0.95, confidence)

        # 情况3: 真正的势均力敌 - 比较论证质量
        max_pro_priority = max((n.priority for n in pro_accepted), default=0)
        max_con_priority = max((n.priority for n in con_accepted), default=0)

        if max_pro_priority > max_con_priority + 0.05:
            return "Supported", 0.55
        elif max_con_priority > max_pro_priority + 0.05:
            return "Refuted", 0.55
        else:
            # 最后手段:比较数量
            if len(pro_accepted) > len(con_accepted):
                return "Supported", 0.52
            elif len(con_accepted) > len(pro_accepted):
                return "Refuted", 0.52
            else:
                return "NEI", 0.50

    def _generate_reasoning(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        decision: str,
        pro_accepted: List,
        con_accepted: List
    ) -> str:
        """生成推理过程"""

        # 准备证据描述
        pro_desc = ", ".join([f"{n.id}(优先级{n.priority:.2f})" for n in pro_accepted[:3]])
        con_desc = ", ".join([f"{n.id}(优先级{n.priority:.2f})" for n in con_accepted[:3]])

        # 攻击关系统计
        total_attacks = len(arg_graph.edges)

        system = """你是事实核查专家,生成简洁的判决解释。

要求:
1. 说明考虑了哪些论证(Pro/Con)
2. 解释为什么某一方更有说服力
3. 提及关键的攻击关系
4. 200字以内"""

        prompt = f"""判决: {decision}

被接受的Pro论证({len(pro_accepted)}个): {pro_desc or "无"}
被接受的Con论证({len(con_accepted)}个): {con_desc or "无"}

论辩图统计:
- 总论证: {len(arg_graph.nodes)}个
- 攻击边: {total_attacks}条
- 被接受: {len(acceptable_args)}个

请生成判决推理(200字内):"""

        messages = [{"role": "user", "content": prompt}]

        try:
            reasoning = self.llm.chat(messages, system=system, temperature=0.5)
            return reasoning if reasoning else f"基于论辩分析,判决为{decision}。"
        except Exception as e:
            print(f"推理生成失败: {e}")
            return f"基于{len(acceptable_args)}个被接受的论证,判决为{decision}。"

    def _extract_key_evidence(
        self,
        pro_accepted: List,
        con_accepted: List,
        decision: str
    ) -> List[str]:
        """提取关键证据ID"""
        if decision == "Supported":
            key_nodes = sorted(pro_accepted, key=lambda n: n.priority, reverse=True)[:3]
        elif decision == "Refuted":
            key_nodes = sorted(con_accepted, key=lambda n: n.priority, reverse=True)[:3]
        else:
            # NEI: 取双方最强的
            all_nodes = sorted(
                pro_accepted + con_accepted,
                key=lambda n: n.priority,
                reverse=True
            )[:3]
            key_nodes = all_nodes

        # 返回证据ID
        evidence_ids = []
        for node in key_nodes:
            evidence_ids.extend(node.evidence_ids[:2])  # 每个节点取前2个证据

        return evidence_ids[:5]  # 最多5个

    def _evaluate_side(
        self,
        arg_graph: ArgumentationGraph,
        acceptable_args: Set[str],
        agent: str
    ) -> float:
        """评估一方的强度(旧方法,兼容性保留)"""
        side_nodes = [
            n for n in arg_graph.nodes
            if n.id in acceptable_args and n.agent == agent
        ]

        if not side_nodes:
            return 0.0

        avg_priority = sum(n.priority for n in side_nodes) / len(side_nodes)
        count_factor = len(side_nodes) / (len(side_nodes) + 3)

        return avg_priority * count_factor