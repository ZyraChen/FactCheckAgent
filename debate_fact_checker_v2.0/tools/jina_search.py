"""
Jina Search API 封装
支持批量并行搜索
"""
import os
os.environ["JINA_API_KEY"] = "jina_518b9cb292b249139bedce5123349109HnqXMjmaY94laLNX3J50eXfmd9E5"

import asyncio
import aiohttp
from typing import List, Dict
import time


class JinaSearch:
    """Jina Reader Search API 封装"""

    def __init__(self, api_key: str, max_results_per_query: int = 5):
        self.api_key = api_key
        self.max_results = max_results_per_query
        self.base_url = "https://s.jina.ai/"

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        同步搜索方法 (兼容性接口)

        参数:
        - query: 搜索查询
        - top_k: 返回结果数量

        返回: [{"title": ..., "content": ..., "url": ...}, ...]
        """
        self.max_results = top_k
        return asyncio.run(self.search_single(query))

    async def search_single(self, query: str, task_context: str = None) -> List[Dict]:
        """
        单次搜索

        参数:
        - query: 搜索查询(可以是问句或任务描述)
        - task_context: 任务上下文,例如"作为事实核查专家,请帮我..."

        返回: [{"title": ..., "content": ..., "url": ...}, ...]
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Retain-Images": "none"
        }

        # 如果提供了任务上下文,组合查询
        if task_context:
            full_query = f"{task_context} {query}"
        else:
            full_query = query

        url = f"{self.base_url}{full_query}"

        print(f"[Jina] 查询URL: {url[:100]}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    print(f"[Jina] 状态码: {response.status}")

                    if response.status == 200:
                        text = await response.text()
                        print(f"[Jina] 返回长度: {len(text)} 字符")

                        # 解析Jina的Markdown格式返回
                        results = self._parse_jina_response(text)
                        print(f"[Jina] 解析出 {len(results)} 条结果")

                        return results[:self.max_results]
                    elif response.status == 401:
                        print(f"[Jina] API Key无效或未设置!")
                        print(f"[Jina] 当前Key: {self.api_key[:10]}...")
                        return []
                    elif response.status == 429:
                        print(f"[Jina] API调用次数超限!")
                        return []
                    else:
                        error_text = await response.text()
                        print(f"[Jina] 搜索失败: {response.status}")
                        print(f"[Jina] 错误信息: {error_text[:200]}")
                        return []
        except asyncio.TimeoutError:
            print(f"[Jina] 请求超时(30秒)")
            return []
        except Exception as e:
            print(f"[Jina] 搜索异常: {query[:50]} - {e}")
            return []

    def _parse_jina_response(self, markdown_text: str) -> List[Dict]:
        """
        解析Jina返回的格式
        新格式:
        [1] Title: xxx
        [1] URL Source: xxx
        [1] Description: xxx
        Content...
        """
        results = []

        # 检查格式类型
        if "[1] Title:" in markdown_text:
            # 新格式: [n] Title: ...
            print(f"[Jina解析] 检测到新格式 [n] Title:")

            # 按[数字]分割
            import re
            blocks = re.split(r'\[\d+\] Title:', markdown_text)

            for block in blocks[1:]:  # 跳过第一个空块
                lines = block.strip().split('\n')

                title = lines[0].strip() if lines else ""
                url = ""
                description = ""
                content = ""

                # 提取URL和描述
                for i, line in enumerate(lines):
                    if line.startswith('[') and '] URL Source:' in line:
                        url = line.split('] URL Source:')[1].strip()
                    elif line.startswith('[') and '] Description:' in line:
                        description = line.split('] Description:')[1].strip()
                    elif i > 3:  # 内容在metadata后面
                        content += line + "\n"

                content = content.strip()[:1000]

                # 如果没有独立内容,用描述
                if not content and description:
                    content = description

                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "content": content if content else description
                    })

        elif "---" in markdown_text:
            # 旧格式: --- Title: ... ---
            print(f"[Jina解析] 检测到旧格式 ---")
            blocks = markdown_text.split("---\n")

            for i in range(1, len(blocks), 2):
                if i + 1 >= len(blocks):
                    break

                metadata_block = blocks[i]
                content_block = blocks[i + 1] if i + 1 < len(blocks) else ""

                title = ""
                url = ""
                for line in metadata_block.split("\n"):
                    if line.startswith("Title:"):
                        title = line.replace("Title:", "").strip()
                    elif line.startswith("URL:"):
                        url = line.replace("URL:", "").strip()

                content = content_block.strip()[:1000]

                if title and url and content:
                    results.append({
                        "title": title,
                        "url": url,
                        "content": content
                    })
        else:
            print(f"[Jina解析]  未识别的格式")
            print(f"[Jina解析] 前300字符: {markdown_text[:300]}")
            return []

        print(f"[Jina解析] 成功解析 {len(results)} 条结果")
        print(results)
        return results

    async def search_batch(self, queries: List[str]) -> Dict[str, List[Dict]]:
        """
        批量并行搜索
        返回: {query: [results...], ...}
        """
        tasks = [self.search_single(q) for q in queries]
        results = await asyncio.gather(*tasks)

        return {
            query: result
            for query, result in zip(queries, results)
        }

    def search_batch_sync(self, queries: List[str]) -> Dict[str, List[Dict]]:
        """同步版本的批量搜索"""
        return asyncio.run(self.search_batch(queries))


# 测试代码
if __name__ == "__main__":
    import os
    api_key = os.getenv("JINA_API_KEY", "your_api_key_here")

    search = JinaSearch(api_key)

    results = asyncio.run(search.search_single("Python programming language"))
    print(f"找到 {len(results)} 条结果")
    for r in results:
        print(f"- {r['title']}: {r['url']}")