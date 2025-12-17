"""
基于LangGraph构建辩论工作流
使用LangGraph的StateGraph来管理多Agent辩论流程
"""
import asyncio
import sys
from pathlib import Path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Literal
from operator import add
from datetime import datetime
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from llm.qwen_client import QwenClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.pro_agent import ProAgent
from agents.con_agent import ConAgent
from agents.judge_agent import JudgeAgent
from core.argumentation_graph import ArgumentationGraph
from core.evidence_pool import EvidencePool
from utils.models import ArgumentNode, AttackEdge, Evidence
import config
# 定义State类型
class DebateState(TypedDict):
    """LangGraph的State定义"""
    claim: str
    current_round: int
    max_rounds: int

    # 共享数据
    evidence_pool_data: dict
    arg_graph_data: dict

    # Agent输出
    pro_queries: Annotated[list, add]
    con_queries: Annotated[list, add]
    pro_arguments: Annotated[list, add]
    con_arguments: Annotated[list, add]

    # 控制流
    should_continue: bool
    verdict: dict


def create_debate_graph():
    """
    创建LangGraph工作流

    流程:
    初始化 → [Pro查询 + Con查询] → 搜索 → Pro论证 → Con论证 → 更新图 → 检查 → Judge
                                                                        ↑              ↓
                                                                        └──────继续────┘
    """

    workflow = StateGraph(DebateState)

    # 添加所有节点
    workflow.add_node("initialize_round", initialize_round_node)
    workflow.add_node("pro_query", pro_query_node)
    workflow.add_node("con_query", con_query_node)
    workflow.add_node("search", search_node)
    workflow.add_node("pro_argue", pro_argue_node)
    workflow.add_node("con_argue", con_argue_node)
    workflow.add_node("update_attacks", update_attacks_node)
    workflow.add_node("check_continue", check_continue_node)
    workflow.add_node("judge", judge_node)

    # 设置入口
    workflow.set_entry_point("initialize_round")

    # 定义流程
    workflow.add_edge("initialize_round", "pro_query")
    workflow.add_edge("initialize_round", "con_query")
    workflow.add_edge("pro_query", "search")
    workflow.add_edge("con_query", "search")
    workflow.add_edge("search", "pro_argue")
    workflow.add_edge("pro_argue", "con_argue")
    workflow.add_edge("con_argue", "update_attacks")
    workflow.add_edge("update_attacks", "check_continue")

    # 条件分支:继续or结束
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


# ========== 节点函数 ==========

def initialize_round_node(state: DebateState) -> dict:
    """初始化新一轮"""
    new_round = state.get("current_round", 0) + 1
    print(f"\n{'='*60}")
    print(f"第 {new_round} 轮辩论")
    print(f"{'='*60}")
    return {"current_round": new_round}


def pro_query_node(state: DebateState) -> dict:
    """Pro生成搜索查询"""

    # 使用config中的API key
    llm = QwenClient(config.DASHSCOPE_API_KEY)
    agent = ProAgent(state["claim"], llm)

    # 从state恢复论辩图
    arg_graph = ArgumentationGraph(state["claim"])
    for node_data in state.get("arg_graph_data", {}).get("nodes", []):
        arg_graph.nodes.append(ArgumentNode(**node_data))
    for edge_data in state.get("arg_graph_data", {}).get("edges", []):
        arg_graph.edges.append(AttackEdge(**edge_data))

    # 从state恢复证据池
    pool = EvidencePool()

    queries = agent.generate_search_queries(
        state["current_round"], arg_graph, pool
    )

    print(f"[Pro] 生成 {len(queries)} 个查询")
    return {"pro_queries": [q.query for q in queries]}


def con_query_node(state: DebateState) -> dict:
    """Con生成搜索查询"""
    llm = QwenClient(config.DASHSCOPE_API_KEY)
    agent = ConAgent(state["claim"], llm)

    arg_graph = ArgumentationGraph(state["claim"])
    pool = EvidencePool()

    queries = agent.generate_search_queries(
        state["current_round"], arg_graph, pool
    )

    print(f"[Con] 生成 {len(queries)} 个查询")
    return {"con_queries": [q.query for q in queries]}


async def search_node_async(state: DebateState) -> dict:
    """并行搜索 - 异步版本"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.jina_search import JinaSearch
    from utils.models import Evidence
    import config

    jina = JinaSearch(config.JINA_API_KEY)

    # 获取本轮最新1个查询
    pro_q = state.get("pro_queries", [])[-1] if state.get("pro_queries") else None
    con_q = state.get("con_queries", [])[-1] if state.get("con_queries") else None

    claim = state["claim"]

    print(f"[搜索] Pro查询: {pro_q}")
    print(f"[搜索] Con查询: {con_q}")

    # 不添加任务上下文 - 避免URL过长导致422错误
    # Agent已经生成了问句形式的查询,直接搜索即可
    pro_res = {}
    con_res = {}

    if pro_q:
        pro_results = await jina.search_single(pro_q, task_context=None)
        pro_res = {pro_q: pro_results}

    if con_q:
        con_results = await jina.search_single(con_q, task_context=None)
        con_res = {con_q: con_results}

    # 转换为Evidence对象 - 包含完整信息
    evidences = []
    for query, results in pro_res.items():
        for r in results[:3]:  # 每个查询取前3条结果
            evidences.append(Evidence(
                id=f"e_pro_{state['current_round']}_{uuid.uuid4().hex[:6]}",
                content=r.get("content", ""),
                title=r.get("title", ""),
                url=r.get("url", ""),
                source="",  # 会从URL自动提取
                credibility="High",
                retrieved_by="pro",
                round_num=state["current_round"],
                search_query=query,
                timestamp=datetime.now()
            ).dict())

    for query, results in con_res.items():
        for r in results[:3]:
            evidences.append(Evidence(
                id=f"e_con_{state['current_round']}_{uuid.uuid4().hex[:6]}",
                content=r.get("content", ""),
                title=r.get("title", ""),
                url=r.get("url", ""),
                source="",
                credibility="High",
                retrieved_by="con",
                round_num=state["current_round"],
                search_query=query,
                timestamp=datetime.now()
            ).dict())

    print(f"[搜索] 获得 {len(evidences)} 条证据 (Pro: {len(pro_res.get(pro_q, [])) if pro_q else 0}, Con: {len(con_res.get(con_q, [])) if con_q else 0})")

    # 更新证据池
    pool_data = state.get("evidence_pool_data", {"evidences": []})
    pool_data["evidences"].extend(evidences)

    return {"evidence_pool_data": pool_data}


def search_node(state: DebateState) -> dict:
    """并行搜索 - 同步包装"""
    # 检查是否已在event loop中
    try:
        loop = asyncio.get_running_loop()
        # 如果已在loop中,创建新线程运行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, search_node_async(state))
            return future.result()
    except RuntimeError:
        # 没有运行的loop,直接运行
        return asyncio.run(search_node_async(state))


def pro_argue_node(state: DebateState) -> dict:
    """Pro构建论证"""

    print("[Pro] 构建论证...")

    llm = QwenClient(config.DASHSCOPE_API_KEY)
    agent = ProAgent(state["claim"], llm)

    # 重建对象
    arg_graph = ArgumentationGraph(state["claim"])
    for node_data in state.get("arg_graph_data", {}).get("nodes", []):
        arg_graph.nodes.append(ArgumentNode(**node_data))

    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences.append(Evidence(**ev_data))

    # 构建论证
    new_args = agent.construct_arguments(
        state["current_round"], arg_graph, pool
    )

    print(f"Pro添加 {len(new_args)} 个论证")

    # 更新图数据
    graph_data = state.get("arg_graph_data", {"nodes": [], "edges": []})
    graph_data["nodes"].extend([n.dict() for n in new_args])

    return {
        "pro_arguments": [n.dict() for n in new_args],
        "arg_graph_data": graph_data
    }


def con_argue_node(state: DebateState) -> dict:
    """Con构建论证"""

    print("[Con] 构建论证...")

    llm = QwenClient(config.DASHSCOPE_API_KEY)
    agent = ConAgent(state["claim"], llm)

    # 重建对象
    arg_graph = ArgumentationGraph(state["claim"])
    for node_data in state.get("arg_graph_data", {}).get("nodes", []):
        arg_graph.nodes.append(ArgumentNode(**node_data))

    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences.append(Evidence(**ev_data))

    new_args = agent.construct_arguments(
        state["current_round"], arg_graph, pool
    )

    print(f"Con添加 {len(new_args)} 个论证")

    # 更新图数据
    graph_data = state.get("arg_graph_data", {"nodes": [], "edges": []})
    graph_data["nodes"].extend([n.dict() for n in new_args])

    return {
        "con_arguments": [n.dict() for n in new_args],
        "arg_graph_data": graph_data
    }


def update_attacks_node(state: DebateState) -> dict:
    from core.argumentation_graph import ArgumentationGraph
    from tools.attack_detector import detect_attacks_simple
    from utils.models import ArgumentNode, AttackEdge
    """更新攻击关系"""

    print("更新攻击边...")

    # 重建论辩图
    arg_graph = ArgumentationGraph(state["claim"])
    for node_data in state.get("arg_graph_data", {}).get("nodes", []):
        arg_graph.nodes.append(ArgumentNode(**node_data))
    for edge_data in state.get("arg_graph_data", {}).get("edges", []):
        arg_graph.edges.append(AttackEdge(**edge_data))

    # 检测攻击
    new_edges = detect_attacks_simple(arg_graph, state["current_round"])

    print(f"添加 {len(new_edges)} 条攻击边")

    # 更新图数据
    graph_data = state.get("arg_graph_data", {"nodes": [], "edges": []})
    graph_data["edges"].extend([e.dict() for e in new_edges])

    return {"arg_graph_data": graph_data}


def check_continue_node(state: DebateState) -> dict:
    """检查是否继续"""
    should_continue = state["current_round"] < state["max_rounds"]
    status = "继续" if should_continue else "结束"
    print(f"轮次检查: {state['current_round']}/{state['max_rounds']} → {status}")
    return {"should_continue": should_continue}


def judge_node(state: DebateState) -> dict:
    """Judge判决"""

    print("\n[Judge] 开始判决...")

    llm = QwenClient(config.DASHSCOPE_API_KEY)
    judge = JudgeAgent(llm)

    # 重建对象
    arg_graph = ArgumentationGraph(state["claim"])
    for node_data in state.get("arg_graph_data", {}).get("nodes", []):
        arg_graph.nodes.append(ArgumentNode(**node_data))
    for edge_data in state.get("arg_graph_data", {}).get("edges", []):
        arg_graph.edges.append(AttackEdge(**edge_data))

    pool = EvidencePool()
    for ev_data in state.get("evidence_pool_data", {}).get("evidences", []):
        pool.evidences.append(Evidence(**ev_data))

    # 判决
    verdict = judge.make_verdict(arg_graph, pool)

    print(f"判决: {verdict.decision}, 置信度: {verdict.confidence:.2%}")

    return {"verdict": verdict.dict()}


def should_continue_routing(state: DebateState) -> Literal["continue", "end"]:
    """路由函数"""
    return "continue" if state.get("should_continue", False) else "end"


# ========== 主函数 ==========

async def run_langgraph_debate(claim: str, max_rounds: int = 3):
    """使用LangGraph运行辩论"""

    # 创建图
    graph = create_debate_graph()

    # 初始状态
    initial_state = {
        "claim": claim,
        "current_round": 0,
        "max_rounds": max_rounds,
        "evidence_pool_data": {"evidences": []},
        "arg_graph_data": {"nodes": [], "edges": []},
        "pro_queries": [],
        "con_queries": [],
        "pro_arguments": [],
        "con_arguments": [],
        "should_continue": True,
        "verdict": {}
    }

    # 运行图
    print(f"\n{'='*70}")
    print(f"LangGraph双Agent辩论系统")
    print(f"待核查: {claim}")
    print(f"{'='*70}")

    final_state = graph.invoke(initial_state)

    return final_state


if __name__ == "__main__":

    # 添加项目路径
    sys.path.insert(0, str(Path(__file__).parent.parent))

    claim = "冥王星距太阳最远约为74亿公里。"
    result = asyncio.run(run_langgraph_debate(claim, max_rounds=2))

    print(f"\n\n最终判决:")
    print(f"决策: {result['verdict'].get('decision')}")
    print(f"置信度: {result['verdict'].get('confidence')}")