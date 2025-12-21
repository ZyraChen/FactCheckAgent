"""
辩论工作流 - LangChain Lite 版本

完全保留原始 workflow，只用 LangChain Chain 替代 LLM 调用部分
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uuid
from datetime import datetime
from urllib.parse import urlparse

import config
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from llm.qwen_client import QwenClient
from tools.attack_detector import AttackDetector
from tools.jina_search import JinaSearch
from utils.models import Evidence, Verdict

# 导入 LangChain Chains
from chains import ProQueryChain, ConQueryChain, JudgeChain
from utils.qwen_wrapper import QwenLLMWrapper


def assess_evidence_credibility(url: str, title: str) -> str:
    """评估证据可信度"""
    domain = urlparse(url).netloc.lower()
    high_cred_domains = ['gov', 'edu', 'who.int', 'wikipedia.org', 'nature.com',
                        'science.org', 'reuters.com', 'bbc.com', 'cnn.com',
                        'nytimes.com', 'un.org']

    for keyword in high_cred_domains:
        if keyword in domain:
            return "High"

    if any(ext in domain for ext in ['com', 'org', 'net']):
        return "Medium"

    return "Low"


def assess_evidence_quality(content: str, credibility: str) -> float:
    """评估证据质量分数"""
    cred_score = {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(credibility, 0.5)
    length_score = min(1.0, len(content) / 500)
    return cred_score * 0.7 + length_score * 0.3


def run_debate_workflow_lc(claim: str, max_rounds: int = 3) -> dict:
    """
    运行辩论工作流 - LangChain Lite 版本

    流程（完全保留原始）:
    1. 初始化组件
    2. 多轮辩论:
       a. Pro & Con 生成查询（使用 Chain）
       b. 搜索并创建 Evidence 节点
       c. 检测攻击关系
       d. 更新论辩图
    3. Judge 判决（使用 Chain）
    """
    print(f"\n{'='*80}")
    print(f"LangChain Lite 辩论系统（保留原始 workflow）")
    print(f"{'='*80}\n")
    print(f"Claim: {claim}\n")

    # 1. 初始化组件
    llm_client = QwenClient(config.DASHSCOPE_API_KEY)

    jina = JinaSearch(config.JINA_API_KEY)
    evidence_pool = EvidencePool()
    arg_graph = ArgumentationGraph(claim)
    attack_detector = AttackDetector(llm_client)

    # 创建 LangChain Chains，每个使用独立的 LLM wrapper 实例以便配置不同的搜索参数
    # Pro Chain: enable_search=True, force_search=False (智能搜索)
    pro_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=True,
        force_search=False,
        search_strategy="auto"
    )
    pro_chain = ProQueryChain(llm=pro_llm)

    # Con Chain: enable_search=True, force_search=False (智能搜索)
    con_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=True,
        force_search=False,
        search_strategy="auto"
    )
    con_chain = ConQueryChain(llm=con_llm)

    # Judge Chain: 将在 JudgeChain 内部为不同方法配置不同参数
    judge_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=False,  # 默认关闭，在 make_verdict 时再开启
        force_search=False
    )
    judge_chain = JudgeChain(llm=judge_llm)

    # 记录所有查询（避免重复）
    all_queries = []

    # 2. 多轮辩论
    for round_num in range(1, max_rounds + 1):
        print(f"\n{'='*70}")
        print(f"第 {round_num}/{max_rounds} 轮")
        print(f"{'='*70}\n")

        # 2.1 Pro & Con 生成查询（使用 LangChain Chain）
        print("[查询生成]")

        # Pro 生成查询
        con_evidences = evidence_pool.get_by_agent("con")
        pro_queries = pro_chain.generate_queries(
            claim=claim,
            round_num=round_num,
            opponent_evidences=con_evidences,
            existing_queries=all_queries
        )

        # Con 生成查询
        pro_evidences = evidence_pool.get_by_agent("pro")
        con_queries = con_chain.generate_queries(
            claim=claim,
            round_num=round_num,
            opponent_evidences=pro_evidences,
            existing_queries=all_queries
        )

        print(f"Pro 查询: {pro_queries}")
        print(f"Con 查询: {con_queries}")

        all_queries.extend(pro_queries)
        all_queries.extend(con_queries)

        # 2.2 搜索并创建 Evidence 节点
        print("\n[证据搜索]")
        all_search_queries = [(q, "pro", round_num) for q in pro_queries] + \
                            [(q, "con", round_num) for q in con_queries]

        for query, agent, r_num in all_search_queries:
            try:
                print(f"搜索: [{agent.upper()}] {query}")
                results = jina.search(query, top_k=2)

                for result in results:
                    # 创建 Evidence 对象
                    evidence_id = f"{agent}_{r_num}_{uuid.uuid4().hex[:8]}"
                    credibility = assess_evidence_credibility(
                        result.get('url', ''),
                        result.get('title', '')
                    )
                    content = result.get('content', result.get('description', ''))

                    if len(content) < 50:
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

                    # 添加到证据池和论辩图（每个证据是一个节点）
                    evidence_pool.add_evidence(evidence)
                    arg_graph.add_evidence_node(evidence)

                    print(f"  ✓ 证据节点: {evidence_id} (可信度:{credibility}, 质量:{quality_score:.2f})")

            except Exception as e:
                print(f"  ⚠ 搜索失败: {e}")

        # 2.3 检测攻击关系（证据节点之间互相攻击）
        print("\n[攻击检测]")
        new_attacks = attack_detector.detect_attacks_for_round(arg_graph, round_num)
        arg_graph.add_attacks(new_attacks)
        print(f"✓ 新增 {len(new_attacks)} 个攻击边")

        # 本轮统计
        stats = evidence_pool.get_statistics()
        print(f"\n[本轮统计] Pro:{stats['pro']}个, Con:{stats['con']}个, 总计:{stats['total']}个证据节点")

    # 3. Judge 判决（使用 LangChain Chain）
    print(f"\n{'='*80}")
    print("Judge 判决")
    print(f"{'='*80}\n")

    # 计算被接受的证据（Grounded Extension）
    accepted_ids = arg_graph.compute_grounded_extension()
    accepted_evidences = [
        arg_graph.get_node_by_id(eid)
        for eid in accepted_ids
        if arg_graph.get_node_by_id(eid)
    ]

    print(f"被接受的证据节点: {len(accepted_evidences)} 个")

    # 使用 Judge Chain 生成判决
    verdict = judge_chain.make_verdict(
        claim=claim,
        accepted_evidences=accepted_evidences,
        all_evidences_count=len(arg_graph.evidence_nodes)
    )

    # 4. 打印最终报告
    _print_final_report(claim, evidence_pool, arg_graph, verdict)

    # 5. 构建完整日志
    complete_log = _build_complete_log(
        claim=claim,
        evidence_pool=evidence_pool,
        arg_graph=arg_graph,
        verdict=verdict,
        ground_truth=None  # 将在 main 中设置
    )

    # 6. 返回结果
    return {
        "claim": claim,
        "verdict": verdict.model_dump(),
        "evidence_pool_stats": evidence_pool.get_statistics(),
        "arg_graph_data": arg_graph.to_dict(),
        "complete_log": complete_log  # 新增：完整日志
    }


def _print_final_report(
    claim: str,
    evidence_pool: EvidencePool,
    arg_graph: ArgumentationGraph,
    verdict: Verdict
):
    """打印最终报告"""
    print(f"\n\n{'='*80}")
    print("📊 最终判决")
    print(f"{'='*80}\n")
    print(f"Claim: {claim}\n")

    decision_emoji = {"Supported": "✓", "Refuted": "✗", "NEI": "❓"}
    print(f"判决: {decision_emoji.get(verdict.decision, '')} {verdict.decision}")
    print(f"置信度: {verdict.confidence:.2%}")
    print(f"\n推理过程:")
    print("-" * 80)
    print(verdict.reasoning)

    if verdict.key_evidence_ids:
        print(f"\n关键证据节点:")
        print("-" * 80)
        for eid in verdict.key_evidence_ids[:3]:
            ev = arg_graph.get_node_by_id(eid)
            if ev:
                print(f"• [{ev.id}] {ev.source}")
                print(f"  {ev.content[:150]}...")
                print()

    print(f"\n统计信息:")
    print("-" * 80)
    print(f"总证据节点: {verdict.total_evidences}")
    print(f"被接受: {verdict.accepted_evidences}")
    print(f"支持强度: {verdict.pro_strength:.2f}")
    print(f"反对强度: {verdict.con_strength:.2f}")


def _build_complete_log(
    claim: str,
    evidence_pool: EvidencePool,
    arg_graph: ArgumentationGraph,
    verdict: Verdict,
    ground_truth: str = None
) -> dict:
    """
    构建完整的运行日志

    Args:
        claim: Claim
        evidence_pool: 证据池
        arg_graph: 论辩图
        verdict: 判决结果
        ground_truth: 数据集中的真实标签

    Returns:
        完整日志字典
    """
    # 1. 所有证据节点（格式化）
    all_evidences = []
    for ev in evidence_pool.get_all():
        all_evidences.append({
            "id": ev.id,
            "content": ev.content,
            "url": ev.url,
            "source": ev.source,
            "credibility": ev.credibility,
            "quality_score": ev.quality_score,
            "priority": ev.get_priority(),
            "retrieved_by": ev.retrieved_by,
            "round_num": ev.round_num,
            "search_query": ev.search_query,
            "timestamp": ev.timestamp.isoformat() if hasattr(ev.timestamp, 'isoformat') else str(ev.timestamp)
        })

    # 2. 攻击关系
    attack_edges = []
    for edge in arg_graph.attack_edges:
        attacker = arg_graph.get_node_by_id(edge.from_evidence_id)
        target = arg_graph.get_node_by_id(edge.to_evidence_id)

        attack_edges.append({
            "from_evidence_id": edge.from_evidence_id,
            "from_agent": attacker.retrieved_by if attacker else "unknown",
            "from_priority": attacker.get_priority() if attacker else 0,
            "to_evidence_id": edge.to_evidence_id,
            "to_agent": target.retrieved_by if target else "unknown",
            "to_priority": target.get_priority() if target else 0,
            "strength": edge.strength,
            "rationale": edge.rationale,
            "round_num": edge.round_num
        })

    # 3. 被接受的证据（Grounded Extension）
    accepted_ids = arg_graph.compute_grounded_extension()
    accepted_evidences = []
    for eid in accepted_ids:
        ev = arg_graph.get_node_by_id(eid)
        if ev:
            accepted_evidences.append({
                "id": ev.id,
                "agent": ev.retrieved_by,
                "priority": ev.get_priority(),
                "source": ev.source,
                "content_preview": ev.content[:200] + "..."
            })

    # 4. 被击败的证据
    defeated_ids = set(arg_graph.evidence_nodes.keys()) - accepted_ids
    defeated_evidences = []
    for eid in defeated_ids:
        ev = arg_graph.get_node_by_id(eid)
        if ev:
            attackers = arg_graph.get_attackers(eid)
            defeated_evidences.append({
                "id": ev.id,
                "agent": ev.retrieved_by,
                "priority": ev.get_priority(),
                "defeated_by": list(attackers)
            })

    # 5. 判决结果
    verdict_data = {
        "decision": verdict.decision,
        "confidence": verdict.confidence,
        "reasoning": verdict.reasoning,
        "key_evidence_ids": verdict.key_evidence_ids,
        "pro_strength": verdict.pro_strength,
        "con_strength": verdict.con_strength,
        "total_evidences": verdict.total_evidences,
        "accepted_evidences": verdict.accepted_evidences
    }

    # 6. 统计信息
    stats = evidence_pool.get_statistics()

    # 7. 构建完整日志
    complete_log = {
        "claim": claim,
        "ground_truth": ground_truth,  # 数据集真实标签
        "timestamp": datetime.now().isoformat(),

        "statistics": {
            "total_evidences": stats['total'],
            "pro_evidences": stats['pro'],
            "con_evidences": stats['con'],
            "total_attacks": len(attack_edges),
            "accepted_evidences": len(accepted_evidences),
            "defeated_evidences": len(defeated_evidences)
        },

        "evidences": {
            "all_evidences": all_evidences,
            "accepted_evidences": accepted_evidences,
            "defeated_evidences": defeated_evidences
        },

        "argumentation": {
            "attack_edges": attack_edges,
            "grounded_extension": list(accepted_ids)
        },

        "verdict": verdict_data,

        "evaluation": {
            "predicted": verdict.decision,
            "ground_truth": ground_truth,
            "correct": verdict.decision == ground_truth if ground_truth else None
        }
    }

    return complete_log


if __name__ == "__main__":
    # 测试
    test_claim = "欧盟计划在2030年全面禁止销售燃油车。"
    result = run_debate_workflow_lc(test_claim, max_rounds=2)

    print(f"\n\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}")
    print(f"判决: {result['verdict']['decision']}")
    print(f"置信度: {result['verdict']['confidence']:.2f}")