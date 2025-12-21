"""
Con Agent Query Chain - 生成搜索查询词
使用 LangChain 来组织 Prompt + LLM + Output Parsing
"""

from typing import List
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import BaseOutputParser


class QueryOutputParser(BaseOutputParser[List[str]]):
    """解析 LLM 输出为查询词列表"""

    def parse(self, text: str) -> List[str]:
        """解析输出"""
        queries = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 5:
                cleaned = line.lstrip('0123456789.、）)- *#').strip()
                if cleaned and len(cleaned) > 10:
                    queries.append(cleaned)

        return queries[:2]


class ConQueryChain:
    """
    Con Agent 查询生成链

    职责：根据当前状态生成反驳 claim 的搜索查询
    """

    def __init__(self, llm):
        """
        初始化

        Args:
            llm: LangChain compatible LLM (QwenLLMWrapper)
                 应配置为 enable_search=True, force_search=False
        """
        self.llm = llm

        # 定义 Prompt Template
        self.prompt_template = PromptTemplate(
            input_variables=["claim", "round_num", "opponent_summary", "existing_topics"],
            template="""You are a fact-checking expert for the opposing side, responsible for finding refuting evidence for the following claim.
Claim: {claim}

Current round: Round {round_num}
{opponent_summary}
{existing_topics}

Task objective:
Generate 1 precise search query to find authoritative evidence in Jina Search to refute this claim.

Query generation requirements:
1. Precision: The query should directly correspond to the core content of the claim, including key entities and key information points
2. Authority: Prioritize locating credible sources such as official websites, government agencies, academic journals, authoritative media, etc.
3. Targeting: If affirmative arguments exist, the query should target their weak points for counterattack
4. Differentiation: Avoid repetition with already searched topics
5. Fidelity: Strictly based on the original claim text, must not modify, misinterpret, or exaggerate the claim content

Query format specifications (important):
- Chinese queries: Use natural sentences with no spaces between words
  Example: `蚂蚁集团官方网站最新董事会成员中没有程立`
- English queries: Use natural sentences and connect keywords with plus signs (+)
  Example: `Fact-checking+website+debunks+Craigslist+ad+recruiting+LA+protests+evidence`

Output requirements:
Only output 1 search query, do not include any explanations, punctuation, or extra text.

Now please provide the query:"""
        )

        # 创建 Chain
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.prompt_template,
            output_parser=QueryOutputParser()
        )

    def generate_queries(
        self,
        claim: str,
        round_num: int,
        opponent_evidences: List = None,
        existing_queries: List[str] = None
    ) -> List[str]:
        """
        生成搜索查询

        Args:
            claim: 要核查的 claim
            round_num: 当前轮次
            opponent_evidences: 支持方的证据列表
            existing_queries: 已有的查询（避免重复）

        Returns:
            查询词列表
        """
        # 构建对手论证摘要
        opponent_summary = ""
        if opponent_evidences and round_num > 1:
            opponent_summary = "支持方最新论证:\n"
            for i, ev in enumerate(opponent_evidences[-3:], 1):
                opponent_summary += f"{i}. [{ev.source}] {ev.content[:150]}...\n"

        # 已有主题
        existing_topics = ""
        if existing_queries:
            existing_topics = "已搜索过的主题(请避免重复):\n" + "\n".join([f"- {q}" for q in existing_queries[-5:]])

        # 调用 Chain
        try:
            result = self.chain.invoke({
                "claim": claim,
                "round_num": round_num,
                "opponent_summary": opponent_summary,
                "existing_topics": existing_topics
            })

            if isinstance(result, dict):
                queries = result.get('text', [])
            else:
                queries = result

            # 过滤重复
            if existing_queries:
                queries = [q for q in queries if q not in existing_queries]

            return queries[:1]  # 每轮只返回1个查询

        except Exception as e:
            print(f" Con Chain 调用失败: {e}")
            return []
