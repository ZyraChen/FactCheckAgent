"""
简化的工作流 - 不使用LangGraph
直接编排Pro/Con/Judge三方交互
"""

import uuid
from datetime import datetime
from typing import List
from urllib.parse import urlparse

from utils.models import Evidence, Verdict
from core.evidence_pool import EvidencePool
from core.argumentation_graph import ArgumentationGraph
from agents.pro_agent import ProAgent
from agents.con_agent import ConAgent
from agents.judge_agent import JudgeAgent
from tools.attack_detector import AttackDetector
from tools.jina_search import JinaSearch
from llm.qwen_client import QwenClient
import config


def assess_evidence_credibility(url: str, title: str) -> str:
    """
    评估证据可信度

    规则:
    - 政府/学术机构/知名媒体 → High
    - 一般网站 → Medium
    - 其他 → Low
    """
    domain = urlparse(url).netloc.lower()

    # High可信度域名
    high_cred_domains = [
        'gov', 'edu', 'who.int', 'wikipedia.org', 'nature.com', 'science.org',
        'reuters.com', 'bbc.com', 'cnn.com', 'nytimes.com', 'un.org'
    ]

    # Medium可信度域名
    medium_cred_domains = [
        'com', 'org', 'net'
    ]

    for keyword in high_cred_domains:
        if keyword in domain:
            return "High"

    for keyword in medium_cred_domains:
        if keyword in domain:
            return "Medium"

    return "Low"


def assess_evidence_quality(content: str, credibility: str) -> float:
    """
    评估证据质量分数

    考虑因素:
    - 可信度
    - 内容长度
    """
    cred_score = {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(credibility, 0.5)
    length_score = min(1.0, len(content) / 500)

    return cred_score * 0.7 + length_score * 0.3


def run_debate_workflow(claim: str, max_rounds: int = 3) -> dict:
    """
    运行辩论工作流

    流程:
    1. 初始化LLM和搜索工具
    2. 多轮辩论:
       - Pro和Con生成查询
       - 并行搜索
       - 创建证据节点
       - 检测攻击关系
    3. Judge做出判决
    """
    print(f"\n{'='*80}")
    print(f"开始事实核查: {claim}")
    print(f"{'='*80}\n")

    # 初始化
    llm = QwenClient(config.DASHSCOPE_API_KEY)
    jina = JinaSearch(config.JINA_API_KEY)
    evidence_pool = EvidencePool()
    arg_graph = ArgumentationGraph(claim)

    pro_agent = ProAgent(claim, llm)
    con_agent = ConAgent(claim, llm)
    attack_detector = AttackDetector(llm)

    # 多轮辩论
    for round_num in range(1, max_rounds + 1):
        print(f"\n{'='*70}")
        print(f"第 {round_num}/{max_rounds} 轮")
        print(f"{'='*70}")

        # 1. Pro和Con生成查询
        print("\n[查询生成]")
        pro_queries = pro_agent.generate_search_queries(round_num, arg_graph, evidence_pool)
        con_queries = con_agent.generate_search_queries(round_num, arg_graph, evidence_pool)
        #
        # print(f"Pro查询 ({len(pro_queries)}个): {pro_queries}")
        # print(f"Con查询 ({len(con_queries)}个): {con_queries}")

        # 2. 搜索并创建证据
        print("\n[证据搜索]")
        all_queries = [
            (q, "pro", round_num) for q in pro_queries
        ] + [
            (q, "con", round_num) for q in con_queries
        ]

        for query, agent, r_num in all_queries:
            try:
                print(f"搜索: [{agent.upper()}] {query}")
                results = jina.search(query, top_k=2)  # 每个查询最多2个结果

                for result in results:
                    # 创建Evidence对象
                    evidence_id = f"{agent}_{r_num}_{uuid.uuid4().hex[:8]}"
                    credibility = assess_evidence_credibility(result.get('url', ''), result.get('title', ''))
                    content = result.get('content', result.get('description', ''))

                    if len(content) < 50:  # 过滤太短的内容
                        continue

                    quality_score = assess_evidence_quality(content, credibility)

                    evidence = Evidence(
                        id=evidence_id,
                        content=content,
                        url=result.get('url', ''),
                        title=result.get('title', ''),
                        source=urlparse(result.get('url', '')).netloc or '未知',
                        credibility=credibility,
                        retrieved_by=agent,
                        round_num=r_num,
                        search_query=query,
                        timestamp=datetime.now(),
                        quality_score=quality_score
                    )

                    # 添加到证据池和论辩图
                    evidence_pool.add_evidence(evidence)
                    arg_graph.add_evidence_node(evidence)

                    print(f"  ✓ 添加证据: {evidence_id} (可信度:{credibility}, 质量:{quality_score:.2f})")

            except Exception as e:
                print(f"  ⚠ 搜索失败: {e}")

        # 3. 检测攻击关系
        print("\n[攻击检测]")
        new_attacks = attack_detector.detect_attacks_for_round(arg_graph, round_num)
        arg_graph.add_attacks(new_attacks)

        # 显示本轮统计
        stats = evidence_pool.get_statistics()
        print(f"\n[本轮统计] Pro:{stats['pro']}个, Con:{stats['con']}个, 总计:{stats['total']}个证据")

    # 4. Judge判决
    print(f"\n{'='*80}")
    print("辩论结束, Judge开始判决")
    print(f"{'='*80}")

    judge_agent = JudgeAgent(llm)
    verdict = judge_agent.make_verdict(claim, arg_graph, evidence_pool)

    # 5. 返回结果
    return {
        "claim": claim,
        "verdict": verdict.model_dump(),
        "evidence_pool_stats": evidence_pool.get_statistics(),
        "arg_graph_data": arg_graph.to_dict()
    }


if __name__ == "__main__":
    # 测试
    test_claim = "欧盟计划在2030年全面禁止销售燃油车。"
    result = run_debate_workflow(test_claim, max_rounds=2)

    print(f"\n\n{'='*80}")
    print("最终判决")
    print(f"{'='*80}")
    print(f"Claim: {result['claim']}")
    print(f"Decision: {result['verdict']['decision']}")
    print(f"Confidence: {result['verdict']['confidence']:.2f}")
    print(f"Reasoning: {result['verdict']['reasoning']}")
