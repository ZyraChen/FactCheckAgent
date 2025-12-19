"""
Judge Agent - LangChain 版本
法官Agent，使用LangChain的Agent框架分析论辩图并做出判决
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

from langchain_version.tools.argument_graph_tool import ArgumentGraphTool
from langchain_version.tools.evidence_pool_tool import EvidencePoolTool


JUDGE_AGENT_SYSTEM_PROMPT = """你是一个专业且公正的事实核查法官。

你的任务:
1. 分析论辩图中被接受的证据 (Grounded Extension)
2. 判断每个证据是支持还是反对claim
3. 基于证据强度做出最终判决: Supported, Refuted, 或 NEI (Not Enough Information)

当前Claim: {claim}

判决标准:
- Supported: 有充分的高质量证据支持claim
- Refuted: 有充分的高质量证据反驳claim
- NEI: 证据不足或双方势均力敌

关键原则:
1. 只考虑被接受的证据 (通过了论辩图的攻击检测)
2. 基于证据内容判断立场，而不是谁搜索的
3. 权威来源 (政府、学术) 权重更高
4. 必须给出清晰的推理过程

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


def create_judge_agent(
    claim: str,
    llm_client,  # QwenClient
    arg_graph_tool: ArgumentGraphTool,
    evidence_pool_tool: EvidencePoolTool
) -> AgentExecutor:
    """
    创建Judge Agent (LangChain版本)

    Args:
        claim: 要核查的claim
        llm_client: Qwen LLM client
        arg_graph_tool: 论辩图工具
        evidence_pool_tool: 证据池工具

    Returns:
        AgentExecutor
    """
    from langchain_version.utils.qwen_wrapper import QwenLLMWrapper

    llm = QwenLLMWrapper(qwen_client=llm_client)

    # 工具列表
    tools = [arg_graph_tool, evidence_pool_tool]

    # 创建 Prompt
    prompt = PromptTemplate.from_template(JUDGE_AGENT_SYSTEM_PROMPT)

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
        max_iterations=10,  # Judge 需要更多推理步骤
        handle_parsing_errors=True
    )

    return agent_executor


def run_judge_agent(
    agent_executor: AgentExecutor,
    claim: str
) -> str:
    """
    运行 Judge Agent 做出最终判决

    Args:
        agent_executor: Judge Agent executor
        claim: Claim

    Returns:
        判决结果 (包含 decision, confidence, reasoning)
    """
    task = f"""请作为公正的法官，对以下claim做出判决:

Claim: {claim}

你需要:
1. 使用 query_argument_graph 工具 (query_type='accepted') 获取被接受的证据
2. 使用 query_evidence_pool 工具查看证据详情
3. 分析每个被接受的证据是支持还是反对claim
4. 计算支持vs反对的强度
5. 做出最终判决

输出格式（严格按照以下JSON格式）:
{{
  "decision": "Supported/Refuted/NEI",
  "confidence": 0.85,
  "reasoning": "详细的推理过程，说明为什么做出这个判决",
  "key_evidence_ids": ["证据ID1", "证据ID2"],
  "support_strength": 0.8,
  "refute_strength": 0.2
}}

现在开始分析:
"""

    # 运行 Agent
    result = agent_executor.invoke({
        "claim": claim,
        "input": task
    })

    return result.get('output', '')
