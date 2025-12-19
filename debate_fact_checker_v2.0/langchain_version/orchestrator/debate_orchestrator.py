"""
Debate Orchestrator - 多Agent辩论编排器 (LangChain版本)

负责编排Pro, Con, Judge三个Agent的交互
"""

import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from llm.qwen_client import QwenClient
from tools.jina_search import JinaSearch
from core.evidence_pool import EvidencePool
from core.argumentation_graph import ArgumentationGraph
from tools.attack_detector import AttackDetector
from utils.models import Verdict

# 导入 LangChain agents 和 tools
from langchain_version.agents.pro_agent_lc import create_pro_agent, run_pro_agent
from langchain_version.agents.con_agent_lc import create_con_agent, run_con_agent
from langchain_version.agents.judge_agent_lc import create_judge_agent, run_judge_agent
from langchain_version.tools.search_tool import SearchTool
from langchain_version.tools.evidence_pool_tool import EvidencePoolTool
from langchain_version.tools.argument_graph_tool import ArgumentGraphTool


class DebateOrchestrator:
    """
    辩论编排器 - LangChain 多Agent版本

    职责:
    1. 初始化所有组件 (LLM, Tools, Agents)
    2. 编排多轮辩论流程
    3. 协调Pro, Con, Judge三个Agent
    4. 管理共享状态 (证据池, 论辩图)
    """

    def __init__(self, claim: str, max_rounds: int = 3):
        """
        初始化编排器

        Args:
            claim: 要核查的claim
            max_rounds: 最大辩论轮次
        """
        self.claim = claim
        self.max_rounds = max_rounds

        # 初始化核心组件
        print(f"\n{'='*80}")
        print(f"初始化LangChain多Agent辩论系统")
        print(f"{'='*80}\n")

        self.llm = QwenClient(config.DASHSCOPE_API_KEY)
        self.jina = JinaSearch(config.JINA_API_KEY)
        self.evidence_pool = EvidencePool()
        self.arg_graph = ArgumentationGraph(claim)
        self.attack_detector = AttackDetector(self.llm)

        # 初始化 LangChain Tools
        print("创建 LangChain Tools...")
        self.search_tool = SearchTool(
            jina_client=self.jina,
            evidence_pool=self.evidence_pool,
            arg_graph=self.arg_graph
        )
        self.evidence_pool_tool = EvidencePoolTool(evidence_pool=self.evidence_pool)
        self.arg_graph_tool = ArgumentGraphTool(arg_graph=self.arg_graph)

        print("✓ 组件初始化完成\n")

    def run_debate(self) -> dict:
        """
        运行完整的辩论流程

        Returns:
            包含判决结果和统计信息的字典
        """
        print(f"\n{'='*80}")
        print(f"开始辩论: {self.claim}")
        print(f"{'='*80}\n")

        # 多轮辩论
        for round_num in range(1, self.max_rounds + 1):
            print(f"\n{'='*70}")
            print(f"第 {round_num}/{self.max_rounds} 轮")
            print(f"{'='*70}\n")

            # 创建本轮的 Agents
            print(f"[创建Agents]")
            pro_agent = create_pro_agent(
                claim=self.claim,
                round_num=round_num,
                llm_client=self.llm,
                search_tool=self.search_tool,
                evidence_pool_tool=self.evidence_pool_tool
            )

            con_agent = create_con_agent(
                claim=self.claim,
                round_num=round_num,
                llm_client=self.llm,
                search_tool=self.search_tool,
                evidence_pool_tool=self.evidence_pool_tool
            )

            # Pro Agent 行动
            print(f"\n[Pro Agent 行动]")
            con_evidences = self.evidence_pool.get_by_agent("con")
            con_summary = self._summarize_evidences(con_evidences[-3:]) if con_evidences else ""

            try:
                pro_result = run_pro_agent(
                    agent_executor=pro_agent,
                    claim=self.claim,
                    round_num=round_num,
                    opponent_evidences_summary=con_summary
                )
                print(f"Pro Agent 完成: {pro_result[:200]}...")
            except Exception as e:
                print(f"⚠ Pro Agent 执行失败: {e}")

            # Con Agent 行动
            print(f"\n[Con Agent 行动]")
            pro_evidences = self.evidence_pool.get_by_agent("pro")
            pro_summary = self._summarize_evidences(pro_evidences[-3:]) if pro_evidences else ""

            try:
                con_result = run_con_agent(
                    agent_executor=con_agent,
                    claim=self.claim,
                    round_num=round_num,
                    opponent_evidences_summary=pro_summary
                )
                print(f"Con Agent 完成: {con_result[:200]}...")
            except Exception as e:
                print(f"⚠ Con Agent 执行失败: {e}")

            # 检测攻击关系
            print(f"\n[攻击检测]")
            new_attacks = self.attack_detector.detect_attacks_for_round(self.arg_graph, round_num)
            self.arg_graph.add_attacks(new_attacks)
            print(f"✓ 新增 {len(new_attacks)} 个攻击边")

            # 本轮统计
            stats = self.evidence_pool.get_statistics()
            print(f"\n[本轮统计] Pro:{stats['pro']}个, Con:{stats['con']}个, 总计:{stats['total']}个证据")

        # Judge 判决
        print(f"\n{'='*80}")
        print("Judge Agent 判决")
        print(f"{'='*80}\n")

        judge_agent = create_judge_agent(
            claim=self.claim,
            llm_client=self.llm,
            arg_graph_tool=self.arg_graph_tool,
            evidence_pool_tool=self.evidence_pool_tool
        )

        try:
            judge_result = run_judge_agent(
                agent_executor=judge_agent,
                claim=self.claim
            )
            print(f"\nJudge 判决结果:\n{judge_result}")

            # 解析判决结果 (假设是 JSON 格式)
            verdict_data = self._parse_judge_output(judge_result)

        except Exception as e:
            print(f"⚠ Judge Agent 执行失败: {e}")
            # 回退到简单判决
            verdict_data = {
                "decision": "NEI",
                "confidence": 0.3,
                "reasoning": f"Judge Agent 执行失败: {e}",
                "key_evidence_ids": [],
                "support_strength": 0.0,
                "refute_strength": 0.0
            }

        # 构建最终结果
        verdict = Verdict(
            decision=verdict_data.get("decision", "NEI"),
            confidence=verdict_data.get("confidence", 0.5),
            reasoning=verdict_data.get("reasoning", ""),
            key_evidence_ids=verdict_data.get("key_evidence_ids", []),
            accepted_evidence_ids=list(self.arg_graph.compute_grounded_extension()),
            pro_strength=verdict_data.get("support_strength", 0.0),
            con_strength=verdict_data.get("refute_strength", 0.0),
            total_evidences=len(self.arg_graph.evidence_nodes),
            accepted_evidences=len(self.arg_graph.compute_grounded_extension())
        )

        # 打印最终报告
        self._print_final_report(verdict)

        return {
            "claim": self.claim,
            "verdict": verdict.model_dump(),
            "evidence_pool_stats": self.evidence_pool.get_statistics(),
            "arg_graph_data": self.arg_graph.to_dict()
        }

    def _summarize_evidences(self, evidences) -> str:
        """生成证据摘要"""
        if not evidences:
            return ""

        summary = []
        for ev in evidences:
            summary.append(f"- [{ev.source}] {ev.content[:100]}...")

        return "\n".join(summary)

    def _parse_judge_output(self, judge_output: str) -> dict:
        """解析 Judge Agent 的输出"""
        try:
            # 尝试从输出中提取 JSON
            import re
            json_match = re.search(r'\{[^}]+\}', judge_output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # 如果没有找到 JSON，返回默认值
                return {
                    "decision": "NEI",
                    "confidence": 0.5,
                    "reasoning": judge_output,
                    "key_evidence_ids": [],
                    "support_strength": 0.0,
                    "refute_strength": 0.0
                }
        except:
            return {
                "decision": "NEI",
                "confidence": 0.5,
                "reasoning": judge_output,
                "key_evidence_ids": [],
                "support_strength": 0.0,
                "refute_strength": 0.0
            }

    def _print_final_report(self, verdict: Verdict):
        """打印最终报告"""
        print(f"\n\n{'='*80}")
        print("📊 最终判决")
        print(f"{'='*80}\n")
        print(f"Claim: {self.claim}\n")
        print(f"判决: {verdict.decision}")
        print(f"置信度: {verdict.confidence:.2%}")
        print(f"\n推理过程:")
        print("-" * 80)
        print(verdict.reasoning)
        print(f"\n统计:")
        print(f"- 总证据: {verdict.total_evidences}")
        print(f"- 被接受: {verdict.accepted_evidences}")
        print(f"- 支持强度: {verdict.pro_strength:.2f}")
        print(f"- 反对强度: {verdict.con_strength:.2f}")


def run_langchain_debate(claim: str, max_rounds: int = 3) -> dict:
    """
    运行 LangChain 多Agent辩论 (便捷函数)

    Args:
        claim: 要核查的claim
        max_rounds: 最大辩论轮次

    Returns:
        辩论结果字典
    """
    orchestrator = DebateOrchestrator(claim=claim, max_rounds=max_rounds)
    return orchestrator.run_debate()


if __name__ == "__main__":
    # 测试
    test_claim = "欧盟计划在2030年全面禁止销售燃油车。"
    result = run_langchain_debate(test_claim, max_rounds=2)

    print(f"\n\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}")
    print(f"判决: {result['verdict']['decision']}")
    print(f"置信度: {result['verdict']['confidence']:.2f}")
