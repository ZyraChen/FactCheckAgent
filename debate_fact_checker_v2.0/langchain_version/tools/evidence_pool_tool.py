"""
Evidence Pool Tool - 让 Agent 可以查询证据池
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun


class EvidencePoolInput(BaseModel):
    """Evidence pool query input schema"""
    query_type: str = Field(description="查询类型: 'all', 'by_agent', 'by_round', 'stats'")
    agent_type: Optional[str] = Field(default=None, description="Agent类型: 'pro' 或 'con' (仅用于 by_agent 查询)")
    round_num: Optional[int] = Field(default=None, description="轮次编号 (仅用于 by_round 查询)")


class EvidencePoolTool(BaseTool):
    """
    Evidence Pool Tool - 查询证据池中的证据

    支持的查询类型:
    - all: 获取所有证据
    - by_agent: 获取特定agent检索的证据
    - by_round: 获取特定轮次的证据
    - stats: 获取证据池统计信息
    """
    name: str = "query_evidence_pool"
    description: str = """
    查询证据池中的证据信息。
    输入: query_type (查询类型), agent_type (可选), round_num (可选)
    输出: 证据信息或统计数据
    """
    args_schema: Type[BaseModel] = EvidencePoolInput

    evidence_pool: any  # EvidencePool instance

    def __init__(self, evidence_pool):
        super().__init__()
        self.evidence_pool = evidence_pool

    def _run(
        self,
        query_type: str,
        agent_type: Optional[str] = None,
        round_num: Optional[int] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """执行证据池查询"""
        try:
            if query_type == "stats":
                # 返回统计信息
                stats = self.evidence_pool.get_statistics()
                return f"证据池统计:\n总证据数: {stats['total']}\nPro: {stats['pro']}个\nCon: {stats['con']}个"

            elif query_type == "by_agent":
                if not agent_type:
                    return "错误: by_agent 查询需要指定 agent_type 参数"

                evidences = self.evidence_pool.get_by_agent(agent_type)
                if not evidences:
                    return f"没有找到 {agent_type} 检索的证据"

                result = f"{agent_type.upper()} 检索的证据 ({len(evidences)}个):\n"
                for ev in evidences[:5]:  # 最多显示5个
                    result += f"- [{ev.id}] R{ev.round_num} {ev.source} (可信度:{ev.credibility})\n"
                    result += f"  内容: {ev.content[:100]}...\n"

                if len(evidences) > 5:
                    result += f"... 还有 {len(evidences) - 5} 个证据\n"

                return result

            elif query_type == "by_round":
                if round_num is None:
                    return "错误: by_round 查询需要指定 round_num 参数"

                all_evidences = self.evidence_pool.get_all()
                round_evidences = [e for e in all_evidences if e.round_num == round_num]

                if not round_evidences:
                    return f"没有找到第 {round_num} 轮的证据"

                result = f"第 {round_num} 轮的证据 ({len(round_evidences)}个):\n"
                for ev in round_evidences:
                    result += f"- [{ev.id}] ({ev.retrieved_by.upper()}) {ev.source}\n"

                return result

            elif query_type == "all":
                all_evidences = self.evidence_pool.get_all()
                if not all_evidences:
                    return "证据池为空"

                result = f"所有证据 ({len(all_evidences)}个):\n"
                for ev in all_evidences[:10]:  # 最多显示10个
                    result += f"- [{ev.id}] R{ev.round_num} ({ev.retrieved_by.upper()}) {ev.source}\n"

                if len(all_evidences) > 10:
                    result += f"... 还有 {len(all_evidences) - 10} 个证据\n"

                return result

            else:
                return f"不支持的查询类型: {query_type}"

        except Exception as e:
            return f"查询失败: {str(e)}"
