"""
Argument Graph Tool - 让 Agent 可以查询论辩图状态
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun


class ArgumentGraphInput(BaseModel):
    """Argument graph query input schema"""
    query_type: str = Field(description="查询类型: 'stats', 'attacks', 'accepted', 'node_info'")
    node_id: Optional[str] = Field(default=None, description="节点ID (仅用于 node_info 查询)")


class ArgumentGraphTool(BaseTool):
    """
    Argument Graph Tool - 查询论辩图信息

    支持的查询类型:
    - stats: 获取论辩图统计信息
    - attacks: 获取所有攻击边
    - accepted: 计算并返回被接受的证据
    - node_info: 获取特定节点的详细信息
    """
    name: str = "query_argument_graph"
    description: str = """
    查询论辩图中的信息。
    输入: query_type (查询类型), node_id (可选)
    输出: 论辩图信息
    """
    args_schema: Type[BaseModel] = ArgumentGraphInput

    arg_graph: any  # ArgumentationGraph instance

    def __init__(self, arg_graph):
        super().__init__()
        self.arg_graph = arg_graph

    def _run(
        self,
        query_type: str,
        node_id: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """执行论辩图查询"""
        try:
            if query_type == "stats":
                # 统计信息
                total_nodes = len(self.arg_graph.evidence_nodes)
                total_attacks = len(self.arg_graph.attack_edges)
                pro_nodes = len([n for n in self.arg_graph.evidence_nodes.values() if n.retrieved_by == "pro"])
                con_nodes = len([n for n in self.arg_graph.evidence_nodes.values() if n.retrieved_by == "con"])

                return f"""论辩图统计:
总节点数: {total_nodes}
- Pro节点: {pro_nodes}
- Con节点: {con_nodes}
总攻击边: {total_attacks}"""

            elif query_type == "attacks":
                if not self.arg_graph.attack_edges:
                    return "当前没有攻击边"

                result = f"攻击关系 ({len(self.arg_graph.attack_edges)}个):\n"
                for i, edge in enumerate(self.arg_graph.attack_edges[:10], 1):
                    attacker = self.arg_graph.get_node_by_id(edge.from_evidence_id)
                    target = self.arg_graph.get_node_by_id(edge.to_evidence_id)

                    if attacker and target:
                        result += f"{i}. [{edge.from_evidence_id}] ({attacker.retrieved_by.upper()}) "
                        result += f"攻击 [{edge.to_evidence_id}] ({target.retrieved_by.upper()})\n"
                        result += f"   强度: {edge.strength:.2f} | 理由: {edge.rationale[:60]}...\n"

                if len(self.arg_graph.attack_edges) > 10:
                    result += f"... 还有 {len(self.arg_graph.attack_edges) - 10} 个攻击边\n"

                return result

            elif query_type == "accepted":
                # 计算 Grounded Extension
                accepted_ids = self.arg_graph.compute_grounded_extension()

                if not accepted_ids:
                    return "没有被接受的证据节点"

                result = f"被接受的证据节点 ({len(accepted_ids)}个):\n"
                for eid in list(accepted_ids)[:10]:
                    node = self.arg_graph.get_node_by_id(eid)
                    if node:
                        result += f"- [{eid}] ({node.retrieved_by.upper()}) {node.source}\n"
                        result += f"  优先级: {node.get_priority():.2f}\n"

                if len(accepted_ids) > 10:
                    result += f"... 还有 {len(accepted_ids) - 10} 个节点\n"

                return result

            elif query_type == "node_info":
                if not node_id:
                    return "错误: node_info 查询需要指定 node_id 参数"

                node = self.arg_graph.get_node_by_id(node_id)
                if not node:
                    return f"未找到节点: {node_id}"

                # 获取攻击者和被攻击者
                attackers = self.arg_graph.get_attackers(node_id)
                attacked = self.arg_graph.get_attacked_by(node_id)

                result = f"节点信息: [{node_id}]\n"
                result += f"来源: {node.source}\n"
                result += f"检索方: {node.retrieved_by.upper()}\n"
                result += f"轮次: {node.round_num}\n"
                result += f"可信度: {node.credibility}\n"
                result += f"优先级: {node.get_priority():.2f}\n"
                result += f"被攻击者: {list(attackers) if attackers else '无'}\n"
                result += f"攻击目标: {list(attacked) if attacked else '无'}\n"
                result += f"内容: {node.content[:150]}...\n"

                return result

            else:
                return f"不支持的查询类型: {query_type}"

        except Exception as e:
            return f"查询失败: {str(e)}"
