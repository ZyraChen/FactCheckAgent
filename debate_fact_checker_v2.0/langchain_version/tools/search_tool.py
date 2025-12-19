"""
Search Tool - 封装 JinaSearch 为 LangChain Tool
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
import uuid
from datetime import datetime
from urllib.parse import urlparse

from tools.jina_search import JinaSearch
from utils.models import Evidence


class SearchInput(BaseModel):
    """Search tool input schema"""
    query: str = Field(description="搜索查询词，应该具体且有针对性")
    agent_type: str = Field(description="调用agent的类型: 'pro' 或 'con'")
    round_num: int = Field(description="当前辩论轮次")


class SearchTool(BaseTool):
    """
    Search Tool - 使用 Jina Search API 搜索证据

    用法: Agent 调用此工具搜索支持/反对claim的证据
    """
    name: str = "search_evidence"
    description: str = """
    使用搜索引擎查找相关证据。
    输入: 搜索查询词(query), agent类型(agent_type: pro/con), 轮次(round_num)
    输出: 搜索到的证据列表
    """
    args_schema: Type[BaseModel] = SearchInput

    # 使用 Field 标记这些字段，设置 exclude=True 避免验证
    jina_client: JinaSearch = Field(default=None, exclude=True)
    evidence_pool: any = Field(default=None, exclude=True)
    arg_graph: any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, jina_client: JinaSearch, evidence_pool, arg_graph, **kwargs):
        super().__init__(**kwargs)
        self.jina_client = jina_client
        self.evidence_pool = evidence_pool
        self.arg_graph = arg_graph

    def _assess_credibility(self, url: str) -> str:
        """评估证据可信度"""
        domain = urlparse(url).netloc.lower()
        high_cred = ['gov', 'edu', 'who.int', 'wikipedia.org', 'nature.com',
                     'reuters.com', 'bbc.com', 'un.org']

        for keyword in high_cred:
            if keyword in domain:
                return "High"

        if any(ext in domain for ext in ['com', 'org', 'net']):
            return "Medium"

        return "Low"

    def _assess_quality(self, content: str, credibility: str) -> float:
        """评估证据质量"""
        cred_score = {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(credibility, 0.5)
        length_score = min(1.0, len(content) / 500)
        return cred_score * 0.7 + length_score * 0.3

    def _run(
        self,
        query: str,
        agent_type: str,
        round_num: int,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """执行搜索"""
        try:
            # 调用 Jina Search
            results = self.jina_client.search(query, top_k=2)

            added_count = 0
            evidence_summaries = []

            for result in results:
                # 创建 Evidence 对象
                evidence_id = f"{agent_type}_{round_num}_{uuid.uuid4().hex[:8]}"
                content = result.get('content', result.get('description', ''))

                if len(content) < 50:  # 过滤太短的内容
                    continue

                url = result.get('url', '')
                credibility = self._assess_credibility(url)
                quality_score = self._assess_quality(content, credibility)

                evidence = Evidence(
                    id=evidence_id,
                    content=content,
                    url=url,
                    title=result.get('title', ''),
                    source=urlparse(url).netloc or '未知',
                    credibility=credibility,
                    retrieved_by=agent_type,
                    round_num=round_num,
                    search_query=query,
                    timestamp=datetime.now(),
                    quality_score=quality_score
                )

                # 添加到证据池和论辩图
                self.evidence_pool.add_evidence(evidence)
                self.arg_graph.add_evidence_node(evidence)

                added_count += 1
                evidence_summaries.append(
                    f"[{evidence_id}] {evidence.source} (可信度:{credibility}, 质量:{quality_score:.2f})"
                )

            result_text = f"搜索查询 '{query}' 成功！\n添加了 {added_count} 个证据:\n" + "\n".join(evidence_summaries)
            return result_text

        except Exception as e:
            return f"搜索失败: {str(e)}"
