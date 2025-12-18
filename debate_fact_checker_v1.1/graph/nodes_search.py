"""
LangGraph工作流节点
每个函数对应一个节点,接收state并返回更新后的state
"""

import asyncio
from typing import Dict
from state.debate_state import DebateState
from utils.models import Evidence
from datetime import datetime
import uuid


def initialize_round(state: DebateState) -> Dict:
    """初始化轮次"""
    current = state.get("current_round", 0)
    new_round = current + 1
    
    print(f"\n{'='*60}")
    print(f"第 {new_round} 轮辩论开始")
    print(f"{'='*60}\n")
    
    return {
        "current_round": new_round,
        "logs": [f"开始第{new_round}轮"]
    }


def pro_generate_queries_node(state: DebateState) -> Dict:
    """Pro Agent生成搜索词"""
    from agents.pro_agent import ProAgent
    from llm.qwen_client import QwenClient
    
    # 获取LLM客户端(实际应该从配置注入)
    llm = state.get("_llm_client")  # 假设在初始state中注入
    
    if not llm:
        print("警告: LLM客户端未初始化")
        return {"pro_search_queries": []}
    
    pro_agent = ProAgent(state["claim"], llm)
    
    # 生成搜索词
    queries = pro_agent.generate_search_queries(
        round_num=state["current_round"],
        arg_graph=state["arg_graph"],
        evidence_pool=state["evidence_pool"]
    )
    
    print(f"[Pro] 生成了 {len(queries)} 个搜索查询")
    for q in queries:
        print(f"  - {q.query}")
    
    return {
        "pro_search_queries": queries,
        "logs": [f"Pro生成了{len(queries)}个查询"]
    }


def con_generate_queries_node(state: DebateState) -> Dict:
    """Con Agent生成搜索词"""
    from agents.con_agent import ConAgent
    from llm.qwen_client import QwenClient
    
    llm = state.get("_llm_client")
    
    if not llm:
        print("警告: LLM客户端未初始化")
        return {"con_search_queries": []}
    
    con_agent = ConAgent(state["claim"], llm)
    
    queries = con_agent.generate_search_queries(
        round_num=state["current_round"],
        arg_graph=state["arg_graph"],
        evidence_pool=state["evidence_pool"]
    )
    
    print(f"[Con] 生成了 {len(queries)} 个搜索查询")
    for q in queries:
        print(f"  - {q.query}")
    
    return {
        "con_search_queries": queries,
        "logs": [f"Con生成了{len(queries)}个查询"]
    }


async def parallel_search_node(state: DebateState) -> Dict:
    """并行搜索"""
    from tools.jina_search import JinaSearch
    
    # 获取搜索引擎(应该从配置注入)
    jina_api_key = state.get("_jina_api_key", "")
    search_engine = JinaSearch(jina_api_key)
    
    # 获取本轮的搜索词
    pro_queries = [
        q.query for q in state.get("pro_search_queries", [])
        if q.round == state["current_round"]
    ]
    con_queries = [
        q.query for q in state.get("con_search_queries", [])
        if q.round == state["current_round"]
    ]
    
    print(f"\n开始并行搜索...")
    print(f"Pro查询: {len(pro_queries)}个")
    print(f"Con查询: {len(con_queries)}个")
    
    # 并行搜索
    pro_results_dict, con_results_dict = await asyncio.gather(
        search_engine.search_batch(pro_queries),
        search_engine.search_batch(con_queries)
    )
    
    # 将结果转换为Evidence对象并添加到证据池
    evidence_pool = state["evidence_pool"]
    round_num = state["current_round"]
    
    # 处理Pro的结果
    pro_evidence_count = 0
    for query, results in pro_results_dict.items():
        for result in results:
            evidence = Evidence(
                id=f"e_pro_{round_num}_{uuid.uuid4().hex[:8]}",
                content=result.get("content", ""),
                url=result.get("url", ""),
                credibility="High",  # 简化版,实际应该评估
                retrieved_by="pro",
                round_num=round_num,
                search_query=query,
                timestamp=datetime.now()
            )
            if evidence_pool.add_evidence(evidence):
                pro_evidence_count += 1
    
    # 处理Con的结果
    con_evidence_count = 0
    for query, results in con_results_dict.items():
        for result in results:
            evidence = Evidence(
                id=f"e_con_{round_num}_{uuid.uuid4().hex[:8]}",
                content=result.get("content", ""),
                url=result.get("url", ""),
                credibility="High",
                retrieved_by="con",
                round_num=round_num,
                search_query=query,
                timestamp=datetime.now()
            )
            if evidence_pool.add_evidence(evidence):
                con_evidence_count += 1
    
    print(f"✓ Pro获得 {pro_evidence_count} 条新证据")
    print(f"✓ Con获得 {con_evidence_count} 条新证据")
    print(f"证据池总数: {len(evidence_pool)}")
    
    return {
        "evidence_pool": evidence_pool,
        "logs": [f"搜索完成: Pro+{pro_evidence_count}, Con+{con_evidence_count}"]
    }
