"""
Con Agent - 反驳方代理
"""

from typing import List
from utils.models import Evidence
from core.evidence_pool import EvidencePool
from core.argumentation_graph import ArgumentationGraph
from llm.qwen_client import QwenClient


class ConAgent:
    """
    反驳方Agent
    职责:
    1. 生成搜索查询(寻找反驳claim的证据)
    2. 根据正方论证调整策略
    """

    def __init__(self, claim: str, llm_client: QwenClient):
        self.claim = claim
        self.llm = llm_client
        self.agent_name = "con"
        self.stance = "refute"

    def generate_search_queries(
        self,
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[str]:
        """
        生成搜索查询

        策略:
        - 第1轮: 直接搜索反驳claim的证据,2个查询
        - 后续轮: 根据正方证据调整策略,1-2个查询
        """
        # 获取正方已有的证据
        pro_evidences = evidence_pool.get_by_agent("pro")

        # 构建上下文
        if round_num == 1:
            context = "这是第1轮。请搜索反驳该claim的证据,包括反例、错误信息、过时数据等。"
        else:
            context = f"这是第{round_num}轮。"
            if pro_evidences:
                # 分析正方证据
                pro_summary = self._summarize_opponent_evidences(pro_evidences)
                context += f"\n\n正方已找到以下证据支持claim:\n{pro_summary}\n\n你需要找到更强的证据来反驳。"

        system_prompt = f"""你是事实核查的反驳方,需要找证据反驳claim: {self.claim}

目标: 找到权威、可信的证据来反驳这个claim或指出其错误。"""

        user_prompt = f"""{context}

请生成{2 if round_num == 1 else 1}个搜索查询。

要求:
1. 查询要具体,能找到权威来源
2. 寻找反例、错误信息、过时数据,考虑不同角度
3. 每行一个查询

示例:
欧盟2035燃油车禁令 最新进展 官方声明
欧盟燃油车政策 豁免条款 合成燃料

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
            print(f"⚠ Con查询生成失败: {e}")
            # 降级策略
            return [f"{self.claim} 反驳 证据"] if round_num == 1 else []

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
