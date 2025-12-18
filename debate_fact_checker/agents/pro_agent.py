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
        生成搜索查询

        策略:
        - 第1轮: 直接搜索支持claim的证据,2个查询
        - 后续轮: 根据反方证据调整策略,1-2个查询
        """
        # 获取反方已有的证据
        con_evidences = evidence_pool.get_by_agent("con")

        # 构建上下文
        if round_num == 1:
            context = "这是第1轮。请直接搜索支持该claim的权威证据。"
        else:
            context = f"这是第{round_num}轮。"
            if con_evidences:
                # 分析反方证据
                con_summary = self._summarize_opponent_evidences(con_evidences)
                context += f"\n\n反方已找到以下证据反驳claim:\n{con_summary}\n\n你需要找到更强的证据来反击。"

        system_prompt = f"""你是事实核查的支持方,需要找证据支持claim: {self.claim}

目标: 找到权威、可信的证据来支持这个claim。"""

        user_prompt = f"""{context}

请生成{2 if round_num == 1 else 1}个搜索查询。

要求:
1. 查询要具体,能找到权威来源(如官方网站、学术机构、政府数据)
2. 考虑不同角度的支持证据
3. 每行一个查询

示例:
世界卫生组织 疫苗安全性 官方声明
Nature期刊 疫苗效果 临床试验数据

现在生成查询:"""

        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = self.llm.chat(messages, system=system_prompt, temperature=0.7)

            # 解析查询(每行一个)
            queries = []
            for line in response.split('\n'):
                line = line.strip()
                # 移除序号
                if line and len(line) > 3:
                    # 移除开头的数字/点号
                    cleaned = line.lstrip('0123456789.、）)- ').strip()
                    if cleaned and len(cleaned) > 5:
                        queries.append(cleaned)

            # 限制数量
            max_queries = 2 if round_num == 1 else 1
            return queries[:max_queries]

        except Exception as e:
            print(f"⚠ Pro查询生成失败: {e}")
            # 降级策略
            return [self.claim] if round_num == 1 else []

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
