"""
Pro Agent - 支持方代理
"""

from typing import List
from utils.models import Evidence
from core.evidence_pool import EvidencePool
from core.argumentation_graph import ArgumentationGraph
from llm.qwen_client import QwenClient


class ProAgent:
    """
    支持方Agent
    职责:
    1. 生成搜索查询(寻找支持claim的证据)
    2. 根据反方论证调整策略
    """

    def __init__(self, claim: str, llm_client: QwenClient):
        self.claim = claim
        self.llm = llm_client
        self.agent_name = "pro"
        self.stance = "support"

    def generate_search_queries(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[str]:
        """
        生成搜索查询 - 改进版

        策略:
        - 考虑反方论证
        - 避免重复已有主题
        - 生成更有针对性的查询
        """
        # 1. 获取反方证据(尤其是上一轮的)
        con_evidences = evidence_pool.get_by_agent("con")
        recent_con = [e for e in con_evidences if e.round_num >= round_num - 1]

        # 2. 获取已有查询主题(避免重复)
        existing_queries = list(set([e.search_query for e in evidence_pool.get_all()]))

        # 3. 构建上下文
        opponent_args_text = ""
        if recent_con:
            opponent_args_text = "反方最新论证:\n"
            for i, ev in enumerate(recent_con[:3], 1):
                opponent_args_text += f"{i}. [{ev.source}] {ev.content[:150]}...\n"

        existing_topics_text = ""
        if existing_queries:
            existing_topics_text = f"\n已搜索过的主题(请避免重复):\n" + "\n".join([f"- {q}" for q in existing_queries[-5:]])

        system_prompt = f"""你是事实核查的支持方专家。

Claim: {self.claim}

你的任务: 生成高质量的搜索查询,找到**权威证据**来支持这个claim。

要求:
1. 查询要具体、可执行,能定位到权威来源
2. 针对反方论证进行反击
3. 避免重复已有主题
4. 优先搜索: 官方网站、政府数据、学术期刊、权威媒体"""

        user_prompt = f"""当前是第 {round_num} 轮。

{opponent_args_text}

{existing_topics_text}

请生成 {2 if round_num == 1 else 1} 个搜索查询。

输出格式 (每行一个查询,不要序号):
世界卫生组织官网 疫苗安全性报告
Nature期刊 疫苗效果 随机对照试验

现在生成:"""

        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = self.llm.chat(messages, system=system_prompt, temperature=0.7)

            # 解析查询(每行一个)
            queries = []
            for line in response.split('\n'):
                line = line.strip()
                # 移除序号和特殊字符
                if line and len(line) > 5:
                    cleaned = line.lstrip('0123456789.、）)- *#').strip()
                    # 过滤太短或重复的
                    if cleaned and len(cleaned) > 10 and cleaned not in existing_queries:
                        queries.append(cleaned)

            # 限制数量
            max_queries = 2 if round_num == 1 else 1
            result = queries[:max_queries]

            if not result:  # 降级策略
                result = [f"{self.claim} 官方证据"] if round_num == 1 else []

            return result

        except Exception as e:
            print(f"⚠ Pro查询生成失败: {e}")
            return [f"{self.claim} 官方证据"] if round_num == 1 else []

    def _summarize_opponent_evidences(self, evidences: List[Evidence]) -> str:
        """总结对方证据"""
        if not evidences:
            return "无"

        summary_lines = []
        for i, ev in enumerate(evidences[:3], 1):  # 最多显示3个
            summary_lines.append(
                f"{i}. [{ev.source}] {ev.content[:100]}... (可信度:{ev.credibility})"
            )

        return "\n".join(summary_lines)
