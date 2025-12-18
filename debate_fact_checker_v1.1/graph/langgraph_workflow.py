"""
基于LangGraph构建辩论工作流 - 改进版
每个证据作为独立节点,多轮攻击图更新
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Literal
from operator import add

from llm.qwen_client import QwenClient
from tools.jina_search import JinaSearch
import config

# 导入改进的模块
sys.path.insert(0, '/mnt/user-data/outputs')
from core.evidence_pool import Evidence, EvidencePool
from core.argumentation_graph import ArgumentationGraph, AttackEdge
from agents.pro_agent import ProAgent
from agents.con_agent import ConAgent
from agents.judge_agent import JudgeAgent


# ===== State定义 =====
class DebateState(TypedDict):
    """辩论状态"""
    claim: str
    current_round: int
    max_rounds: int

    # 共享数据(改进:存储Evidence节点)
    evidence_pool_data: dict  # 用于序列化
    arg_graph_data: dict       # 用于序列化

    # Agent输出
    pro_queries: Annotated[list, add]
    con_queries: Annotated[list, add]
    new_evidence_ids: Annotated[list, add]

    # 控制流
    should_continue: bool
    verdict: dict


# ===== 辅助函数 =====
def assess_evidence_quality(evidence: Evidence, claim: str) -> float:
    """评估证据质量"""
    cred_score = {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(evidence.credibility, 0.5)
    length_score = min(1.0, len(evidence.content) / 500)
    return cred_score * 0.7 + length_score * 0.3


# ===== 节点函数 =====
def initialize_round_node(state: DebateState) -> dict:
    """初始化一轮"""
    new_round = state.get("current_round", 0) + 1
    print(f"\n{'='*70}")
    print(f"第 {new_round}/{state['max_rounds']} 轮论辩")
    print(f"{'='*70}")
    return {"current_round": new_round}


def pro_query_node(state: DebateState) -> dict:
    """Pro生成查询"""
    llm = QwenClient(config.DASHSCOPE_API_KEY)
    pro_agent = ProAgent(state["claim"], llm)

    # 重建论辩图
    arg_graph = ArgumentationGraph(state["claim"])
    for ev_data in state.get("arg_graph_data", {}).get("evidence_nodes", []):
        arg_graph.evidence_nodes[ev_data["id"]] = Evidence(**ev_data)
    for edge_data in state.get("arg_graph_data", {}).get("attack_edges", []):
        arg_graph.attack_edges.append(AttackEdge(**edge_data))

    # 重建证据池
    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences[ev_data["id"]] = Evidence(**ev_data)

    queries = pro_agent.generate_search_queries(state["current_round"], arg_graph, pool)

    print(f"  [Pro] 生成{len(queries)}个查询")
    return {"pro_queries": queries}


def con_query_node(state: DebateState) -> dict:
    """Con生成查询"""
    llm = QwenClient(config.DASHSCOPE_API_KEY)
    con_agent = ConAgent(state["claim"], llm)

    arg_graph = ArgumentationGraph(state["claim"])
    for ev_data in state.get("arg_graph_data", {}).get("evidence_nodes", []):
        arg_graph.evidence_nodes[ev_data["id"]] = Evidence(**ev_data)
    for edge_data in state.get("arg_graph_data", {}).get("attack_edges", []):
        arg_graph.attack_edges.append(AttackEdge(**edge_data))

    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences[ev_data["id"]] = Evidence(**ev_data)

    queries = con_agent.generate_search_queries(state["current_round"], arg_graph, pool)

    print(f"  [Con] 生成{len(queries)}个查询")
    return {"con_queries": queries}


def search_and_create_evidences_node(state: DebateState) -> dict:
    """
    搜索并创建证据节点 - 核心改进

    流程:
    1. 获取本轮查询
    2. 并行搜索
    3. 每个搜索结果创建Evidence对象
    4. 评估质量,筛选
    5. 加入证据池和论辩图
    """
    print("\n▶ 搜索并创建证据节点...")

    jina = JinaSearch(config.JINA_API_KEY)
    round_num = state["current_round"]
    claim = state["claim"]

    # 获取本轮查询(最后1-2个)
    pro_queries = state.get("pro_queries", [])[-2:]
    con_queries = state.get("con_queries", [])[-2:]

    # 重建数据结构
    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences[ev_data["id"]] = Evidence(**ev_data)

    arg_graph = ArgumentationGraph(claim)
    for ev_data in state.get("arg_graph_data", {}).get("evidence_nodes", []):
        arg_graph.evidence_nodes[ev_data["id"]] = Evidence(**ev_data)
    for edge_data in state.get("arg_graph_data", {}).get("attack_edges", []):
        arg_graph.attack_edges.append(AttackEdge(**edge_data))

    new_evidence_ids = []

    # 同步搜索 - 使用asyncio.run
    import asyncio

    async def do_searches():
        results = []

        # 处理Pro搜索
        for i, query in enumerate(pro_queries):
            try:
                search_results = await jina.search_single(query, task_context=None)
                for j, item in enumerate(search_results[:3]):
                    evidence = Evidence(
                        id=f"pro_r{round_num}_q{i}_e{j}",
                        content=item.get("content", item.get("description", ""))[:1000],
                        url=item.get("url", ""),
                        source=item.get("title", "Unknown"),
                        credibility="High" if any(d in item.get("url", "") for d in ["gov", "edu", "org"]) else "Medium",
                        retrieved_by="pro",
                        round_num=round_num,
                        search_query=query,
                        timestamp=datetime.now()
                    )

                    # 质量评估
                    evidence.quality_score = assess_evidence_quality(evidence, claim)

                    if evidence.quality_score >= 0.5:
                        results.append(evidence)
            except Exception as e:
                print(f"  Pro搜索错误: {e}")

        # 处理Con搜索
        for i, query in enumerate(con_queries):
            try:
                search_results = await jina.search_single(query, task_context=None)
                for j, item in enumerate(search_results[:3]):
                    evidence = Evidence(
                        id=f"con_r{round_num}_q{i}_e{j}",
                        content=item.get("content", item.get("description", ""))[:1000],
                        url=item.get("url", ""),
                        source=item.get("title", "Unknown"),
                        credibility="High" if any(d in item.get("url", "") for d in ["gov", "edu", "org"]) else "Medium",
                        retrieved_by="con",
                        round_num=round_num,
                        search_query=query,
                        timestamp=datetime.now()
                    )

                    evidence.quality_score = assess_evidence_quality(evidence, claim)

                    if evidence.quality_score >= 0.5:
                        results.append(evidence)
            except Exception as e:
                print(f"  Con搜索错误: {e}")

        return results

    # 运行异步搜索
    evidences = asyncio.run(do_searches())

    # 添加到pool和graph
    for evidence in evidences:
        pool.add_evidence(evidence)
        arg_graph.add_evidence_node(evidence)
        new_evidence_ids.append(evidence.id)

    print(f"  新增{len(new_evidence_ids)}个证据节点")
    print(f"  证据池:{len(pool)}, 论辩图:{len(arg_graph.evidence_nodes)}个节点")

    # 序列化保存
    pool_data = {
        "evidences": [
            {
                "id": e.id,
                "content": e.content,
                "url": e.url,
                "source": e.source,
                "credibility": e.credibility,
                "retrieved_by": e.retrieved_by,
                "round_num": e.round_num,
                "search_query": e.search_query,
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                "quality_score": e.quality_score
            }
            for e in pool.evidences.values()
        ]
    }

    graph_data = {
        "evidence_nodes": [
            {
                "id": e.id,
                "content": e.content,
                "url": e.url,
                "source": e.source,
                "credibility": e.credibility,
                "retrieved_by": e.retrieved_by,
                "round_num": e.round_num,
                "search_query": e.search_query,
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                "quality_score": e.quality_score
            }
            for e in arg_graph.evidence_nodes.values()
        ],
        "attack_edges": [
            {
                "attacker_id": edge.attacker_id,
                "target_id": edge.target_id,
                "strength": edge.strength,
                "rationale": edge.rationale,
                "round_num": edge.round_num
            }
            for edge in arg_graph.attack_edges
        ]
    }

    return {
        "new_evidence_ids": new_evidence_ids,
        "evidence_pool_data": pool_data,
        "arg_graph_data": graph_data
    }


def attack_analysis_node(state: DebateState) -> dict:
    """攻击关系分析"""
    print("\n▶ 攻击关系分析...")

    llm = QwenClient(config.DASHSCOPE_API_KEY)
    pro_agent = ProAgent(state["claim"], llm)
    con_agent = ConAgent(state["claim"], llm)

    # 重建数据结构
    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences[ev_data["id"]] = Evidence(**ev_data)

    arg_graph = ArgumentationGraph(state["claim"])
    for ev_data in state.get("arg_graph_data", {}).get("evidence_nodes", []):
        arg_graph.evidence_nodes[ev_data["id"]] = Evidence(**ev_data)
    for edge_data in state.get("arg_graph_data", {}).get("attack_edges", []):
        arg_graph.attack_edges.append(AttackEdge(**edge_data))

    # Pro攻击
    pro_attacks = pro_agent.select_and_attack(pool, arg_graph, state["current_round"])
    for attack in pro_attacks:
        arg_graph.add_attack(attack)
    print(f"  Pro发起{len(pro_attacks)}个攻击")

    # Con攻击
    con_attacks = con_agent.select_and_attack(pool, arg_graph, state["current_round"])
    for attack in con_attacks:
        arg_graph.add_attack(attack)
    print(f"  Con发起{len(con_attacks)}个攻击")
    print(f"  论辩图:{len(arg_graph.attack_edges)}条攻击边")

    # 更新图数据
    graph_data = {
        "evidence_nodes": [
            {
                "id": e.id,
                "content": e.content,
                "url": e.url,
                "source": e.source,
                "credibility": e.credibility,
                "retrieved_by": e.retrieved_by,
                "round_num": e.round_num,
                "search_query": e.search_query,
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                "quality_score": e.quality_score
            }
            for e in arg_graph.evidence_nodes.values()
        ],
        "attack_edges": [
            {
                "attacker_id": edge.attacker_id,
                "target_id": edge.target_id,
                "strength": edge.strength,
                "rationale": edge.rationale,
                "round_num": edge.round_num
            }
            for edge in arg_graph.attack_edges
        ]
    }

    return {"arg_graph_data": graph_data}


def check_continue_node(state: DebateState) -> dict:
    """检查是否继续"""
    should_continue = state["current_round"] < state["max_rounds"]
    print(f"  轮次: {state['current_round']}/{state['max_rounds']} → {'继续' if should_continue else '结束'}")
    return {"should_continue": should_continue}


def judge_node(state: DebateState) -> dict:
    """Judge判决"""
    print(f"\n{'='*70}")
    print("最终判决")
    print(f"{'='*70}\n")

    llm = QwenClient(config.DASHSCOPE_API_KEY)
    judge = JudgeAgent(llm)

    # 重建数据结构
    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences[ev_data["id"]] = Evidence(**ev_data)

    arg_graph = ArgumentationGraph(state["claim"])
    for ev_data in state.get("arg_graph_data", {}).get("evidence_nodes", []):
        arg_graph.evidence_nodes[ev_data["id"]] = Evidence(**ev_data)
    for edge_data in state.get("arg_graph_data", {}).get("attack_edges", []):
        arg_graph.attack_edges.append(AttackEdge(**edge_data))

    # 判决
    verdict = judge.make_verdict(state["claim"], arg_graph, pool)

    return {"verdict": verdict}


# ===== 路由函数 =====
def should_continue_routing(state: DebateState) -> Literal["continue", "end"]:
    return "continue" if state.get("should_continue", False) else "end"


# ===== 构建工作流 =====
def create_debate_graph():
    """创建LangGraph工作流"""
    workflow = StateGraph(DebateState)

    # 添加节点
    workflow.add_node("initialize_round", initialize_round_node)
    workflow.add_node("pro_query", pro_query_node)
    workflow.add_node("con_query", con_query_node)
    workflow.add_node("search_and_create_evidences", search_and_create_evidences_node)
    workflow.add_node("attack_analysis", attack_analysis_node)
    workflow.add_node("check_continue", check_continue_node)
    workflow.add_node("judge", judge_node)

    # 设置入口
    workflow.set_entry_point("initialize_round")

    # 定义流程
    workflow.add_edge("initialize_round", "pro_query")
    workflow.add_edge("initialize_round", "con_query")
    workflow.add_edge("pro_query", "search_and_create_evidences")
    workflow.add_edge("con_query", "search_and_create_evidences")
    workflow.add_edge("search_and_create_evidences", "attack_analysis")
    workflow.add_edge("attack_analysis", "check_continue")

    # 条件分支
    workflow.add_conditional_edges(
        "check_continue",
        should_continue_routing,
        {
            "continue": "initialize_round",
            "end": "judge"
        }
    )

    workflow.add_edge("judge", END)

    return workflow.compile()


# ===== 主函数 =====
def run_langgraph_debate(claim: str, max_rounds: int = 3):
    """运行辩论系统 - 同步版本"""

    graph = create_debate_graph()

    initial_state = {
        "claim": claim,
        "current_round": 0,
        "max_rounds": max_rounds,
        "evidence_pool_data": {"evidences": []},
        "arg_graph_data": {"evidence_nodes": [], "attack_edges": []},
        "pro_queries": [],
        "con_queries": [],
        "new_evidence_ids": [],
        "should_continue": True,
        "verdict": {}
    }

    print(f"\n{'='*70}")
    print("LangGraph双Agent辩论系统(改进版:证据节点架构)")
    print(f"待核查: {claim}")
    print(f"{'='*70}")

    final_state = graph.invoke(initial_state)

    return final_state