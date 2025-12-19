"""
Con Agent - LangChain 版本
反对方Agent，使用LangChain的Agent框架
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

from langchain_version.tools.search_tool import SearchTool
from langchain_version.tools.evidence_pool_tool import EvidencePoolTool


CON_AGENT_SYSTEM_PROMPT = """你是一个专业的事实核查反对方专家。

你的任务:
1. 分析claim并找到反驳它的高质量证据
2. 使用搜索工具查找权威来源的证据
3. 观察支持方的论证并进行反驳
4. 避免重复搜索相同主题

当前Claim: {claim}
当前轮次: {round_num}

可用工具:
- search_evidence: 搜索反驳claim的证据
- query_evidence_pool: 查询已有的证据

策略建议:
- 第1轮: 直接搜索反驳claim的权威证据
- 后续轮: 查看支持方证据，针对性地搜索更强的反驳证据
- 优先使用: 官方网站、政府数据、学术期刊、权威媒体
- 寻找矛盾、夸大、过时等问题

你有以下工具可以使用:

{tools}

使用以下格式:

Question: 你需要回答的问题
Thought: 你应该思考该怎么做
Action: 要采取的行动，应该是 [{tool_names}] 中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个 Thought/Action/Action Input/Observation 可以重复 N 次)
Thought: 我现在知道最终答案了
Final Answer: 对原始输入问题的最终答案

开始!

Question: {input}
Thought: {agent_scratchpad}
"""


def create_con_agent(
    claim: str,
    round_num: int,
    llm_client,  # QwenClient
    search_tool: SearchTool,
    evidence_pool_tool: EvidencePoolTool
) -> AgentExecutor:
    """
    创建Con Agent (LangChain版本)

    Args:
        claim: 要核查的claim
        round_num: 当前轮次
        llm_client: Qwen LLM client
        search_tool: 搜索工具
        evidence_pool_tool: 证据池工具

    Returns:
        AgentExecutor
    """
    from langchain_version.utils.qwen_wrapper import QwenLLMWrapper

    llm = QwenLLMWrapper(qwen_client=llm_client)

    # 工具列表
    tools = [search_tool, evidence_pool_tool]

    # 创建 Prompt
    prompt = PromptTemplate.from_template(CON_AGENT_SYSTEM_PROMPT)

    # 创建 Agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )

    # 创建 Agent Executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True
    )

    return agent_executor


def run_con_agent(
    agent_executor: AgentExecutor,
    claim: str,
    round_num: int,
    opponent_evidences_summary: str = ""
) -> str:
    """
    运行 Con Agent 生成搜索查询并执行搜索

    Args:
        agent_executor: Con Agent executor
        claim: Claim
        round_num: 当前轮次
        opponent_evidences_summary: 支持方证据摘要

    Returns:
        Agent 的执行结果
    """
    if round_num == 1:
        task = f"""这是第{round_num}轮辩论。

请你作为反对方:
1. 使用 query_evidence_pool 工具查看当前证据池状态
2. 生成1个高质量的搜索查询来反驳这个claim
3. 使用 search_evidence 工具执行搜索 (参数: query, agent_type='con', round_num={round_num})

记住: 寻找权威来源，如政府网站、学术期刊等，找出claim中的矛盾或夸大之处。
"""
    else:
        task = f"""这是第{round_num}轮辩论。

支持方最近的论证:
{opponent_evidences_summary}

请你作为反对方:
1. 使用 query_evidence_pool 工具查看对方证据
2. 针对性地生成1个搜索查询来反驳支持方论证
3. 使用 search_evidence 工具执行搜索 (参数: query, agent_type='con', round_num={round_num})

策略: 找到更权威、更强有力的证据来证明claim是错误的或不准确的。
"""

    # 运行 Agent
    result = agent_executor.invoke({
        "claim": claim,
        "round_num": round_num,
        "input": task
    })

    return result.get('output', '')
