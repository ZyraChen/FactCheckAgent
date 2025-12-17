"""
主程序入口
运行双Agent辩论式事实核查系统
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from state.debate_state import DebateState
from llm.qwen_client import QwenClient
from tools.jina_search import JinaSearch
from agents.pro_agent import ProAgent
from agents.con_agent import ConAgent
from agents.judge_agent import JudgeAgent
from tools.attack_detector import detect_attacks_simple
from utils.models import ClaimData
import config


async def run_debate_system(claim: str, max_rounds: int = 3):
    """
    运行完整的辩论系统
    """
    print(f"\n{'='*70}")
    print(f"双Agent辩论式事实核查系统")
    print(f"{'='*70}")
    print(f"\n待核查主张: {claim}\n")
    
    # 初始化组件
    llm_client = QwenClient(config.DASHSCOPE_API_KEY)
    search_engine = JinaSearch(config.JINA_API_KEY)
    
    pro_agent = ProAgent(claim, llm_client)
    con_agent = ConAgent(claim, llm_client)
    judge_agent = JudgeAgent(llm_client)
    
    # 初始化共享数据结构
    evidence_pool = EvidencePool()
    arg_graph = ArgumentationGraph(claim)
    
    # 运行辩论轮次
    for round_num in range(1, max_rounds + 1):
        print(f"\n{'='*70}")
        print(f"第 {round_num}/{max_rounds} 轮辩论")
        print(f"{'='*70}\n")
        
        # 1. 生成搜索词
        print("▶ 生成搜索查询...")
        pro_queries = pro_agent.generate_search_queries(
            round_num, arg_graph, evidence_pool
        )
        con_queries = con_agent.generate_search_queries(
            round_num, arg_graph, evidence_pool
        )
        
        print(f"  Pro查询: {[q.query for q in pro_queries]}")
        print(f"  Con查询: {[q.query for q in con_queries]}")
        
        # 2. 并行搜索
        print("\n▶ 并行搜索证据...")
        pro_query_strs = [q.query for q in pro_queries]
        con_query_strs = [q.query for q in con_queries]
        
        pro_results, con_results = await asyncio.gather(
            search_engine.search_batch(pro_query_strs),
            search_engine.search_batch(con_query_strs)
        )
        
        # 3. 添加证据到证据池
        from utils.models import Evidence
        from datetime import datetime
        import uuid
        
        for query, results in pro_results.items():
            for result in results[:3]:  # 每个查询取前3条
                evidence = Evidence(
                    id=f"e_pro_{round_num}_{uuid.uuid4().hex[:6]}",
                    content=result.get("content", "")[:500],
                    url=result.get("url", ""),
                    credibility="High",
                    retrieved_by="pro",
                    round_num=round_num,
                    search_query=query,
                    timestamp=datetime.now()
                )
                evidence_pool.add_evidence(evidence)
        
        for query, results in con_results.items():
            for result in results[:3]:
                evidence = Evidence(
                    id=f"e_con_{round_num}_{uuid.uuid4().hex[:6]}",
                    content=result.get("content", "")[:500],
                    url=result.get("url", ""),
                    credibility="High",
                    retrieved_by="con",
                    round_num=round_num,
                    search_query=query,
                    timestamp=datetime.now()
                )
                evidence_pool.add_evidence(evidence)
        
        print(f"  证据池大小: {len(evidence_pool)}")
        
        # 4. Pro构建论证(先手)
        print("\n▶ Pro构建论证...")
        pro_new_args = pro_agent.construct_arguments(
            round_num, arg_graph, evidence_pool
        )
        arg_graph.add_nodes(pro_new_args)
        print(f"  Pro添加了 {len(pro_new_args)} 个论证节点")
        
        # 5. Con构建论证(后手)
        print("\n▶ Con构建论证...")
        con_new_args = con_agent.construct_arguments(
            round_num, arg_graph, evidence_pool
        )
        arg_graph.add_nodes(con_new_args)
        print(f"  Con添加了 {len(con_new_args)} 个论证节点")
        
        # 6. 更新攻击关系
        print("\n▶ 更新攻击关系...")
        new_attacks = detect_attacks_simple(arg_graph, round_num)
        arg_graph.add_edges(new_attacks)
        print(f"  添加了 {len(new_attacks)} 条攻击边")
        
        # 统计信息
        stats = arg_graph.get_statistics()
        print(f"\n  当前论辩图: {stats['total_nodes']}节点, {stats['total_edges']}边")
        print(f"  Pro节点: {stats['pro_nodes']}, Con节点: {stats['con_nodes']}")
    
    # Judge判决
    print(f"\n{'='*70}")
    print("法官判决")
    print(f"{'='*70}\n")
    
    verdict = judge_agent.make_verdict(arg_graph, evidence_pool)
    
    print(f"\n判决结果: {verdict.decision}")
    print(f"置信度: {verdict.confidence:.2%}")
    print(f"\n推理过程:")
    print(verdict.reasoning)
    print(f"\n关键证据: {len(verdict.key_evidence)}条")
    print(f"双方分析: {verdict.argument_analysis}")
    
    # 保存结果
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 保存论辩图
    arg_graph.save_to_file(output_dir / "argumentation_graph.json")
    print(f"\n✓ 论辩图已保存到: output/argumentation_graph.json")
    
    # 保存判决
    with open(output_dir / "verdict.json", "w", encoding="utf-8") as f:
        json.dump(verdict.dict(), f, ensure_ascii=False, indent=2, default=str)
    print(f"✓ 判决结果已保存到: output/verdict.json")
    
    return verdict


async def process_dataset(dataset_path: str, output_path: str, max_samples: int = None):
    """
    处理数据集
    """
    # 加载数据集
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    
    if max_samples:
        dataset = dataset[:max_samples]
    
    print(f"加载了 {len(dataset)} 条数据")
    
    results = []
    
    for i, item in enumerate(dataset):
        claim_data = ClaimData(**item)
        print(f"\n\n{'#'*70}")
        print(f"处理第 {i+1}/{len(dataset)} 条")
        print(f"{'#'*70}")
        
        try:
            verdict = await run_debate_system(claim_data.claim, max_rounds=3)
            
            result = {
                "claim": claim_data.claim,
                "predicted_verdict": verdict.decision,
                "confidence": verdict.confidence,
                "ground_truth": claim_data.verdict,
                "correct": verdict.decision == claim_data.verdict if claim_data.verdict else None
            }
            
            results.append(result)
            
            # 保存中间结果
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"错误: {e}")
            continue
    
    # 计算准确率
    correct_count = sum(1 for r in results if r.get("correct"))
    total_count = len([r for r in results if r.get("correct") is not None])
    accuracy = correct_count / total_count if total_count > 0 else 0
    
    print(f"\n\n{'='*70}")
    print(f"评估结果")
    print(f"{'='*70}")
    print(f"总数: {total_count}")
    print(f"正确: {correct_count}")
    print(f"准确率: {accuracy:.2%}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="双Agent辩论式事实核查")
    parser.add_argument("--claim", type=str, help="单个claim")
    parser.add_argument("--dataset", type=str, help="数据集路径")
    parser.add_argument("--output", type=str, default="output/results.json", help="输出路径")
    parser.add_argument("--max-samples", type=int, help="最大处理样本数")
    parser.add_argument("--rounds", type=int, default=3, help="辩论轮次")
    
    args = parser.parse_args()
    
    if args.claim:
        # 单个claim模式
        asyncio.run(run_debate_system(args.claim, args.rounds))
    elif args.dataset:
        # 数据集模式
        asyncio.run(process_dataset(args.dataset, args.output, args.max_samples))
    else:
        # 默认测试
        test_claim = "冥王星距太阳最远约为74亿公里。"
        asyncio.run(run_debate_system(test_claim))
