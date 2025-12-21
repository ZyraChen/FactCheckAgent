"""
LLM API 客户端封装 - 支持阿里云Qwen
"""

from openai import OpenAI
from typing import List, Dict, Optional
import json
import os


class QwenClient:
    """LLM API封装 - 使用阿里云Qwen"""

    def __init__(self, api_key: str = None, model: str = "qwen-plus-2025-12-01"):
        # 如果没传api_key,从环境变量获取
        api_key = "sk-8faa7214041347609e67d5d09cec7266"

        # 阿里云Qwen使用OpenAI兼容接口
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",

        )
        self.model = model
        print(f"[LLM] 使用模型: {model}, API Key: {api_key[:8]}...")

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        enable_search: bool = False,
        force_search: bool = False,
        enable_thinking: bool = True,
        search_strategy: str = "auto"
    ) -> str:
        """
        标准对话接口

        Args:
            messages: 对话消息列表
            system: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            enable_search: 是否启用搜索功能（默认False）
            force_search: 是否强制搜索（默认False，仅在enable_search=True时有效）
            enable_thinking: 是否启用思考模式（默认True）
            search_strategy: 搜索策略 "auto"/"max"（默认auto）
        """
        # 如果有system prompt,添加到messages开头
        if system:
            messages = [{"role": "system", "content": system}] + messages

        try:
            # 根据参数构建 extra_body
            extra_body = {}

            if enable_thinking:
                extra_body["enable_thinking"] = True

            if enable_search:
                extra_body["enable_search"] = True
                extra_body["search_options"] = {
                    "forced_search": force_search,
                    "search_strategy": search_strategy
                }

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body if extra_body else None,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Qwen API调用失败: {e}")
            return ""

    def chat_with_json(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> dict:
        """
        要求返回JSON格式
        """
        if system:
            system += "\n\n你必须返回有效的JSON格式,不要包含任何其他文本。"
        else:
            system = "你必须返回有效的JSON格式,不要包含任何其他文本。"

        response_text = self.chat(messages, system, temperature)

        # 尝试解析JSON
        try:
            # 移除可能的markdown代码块
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            return json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response_text[:500]}")
            return {}

    def generate_search_queries(
        self,
        claim: str,
        agent_role: str,
        current_round: int,
        opponent_args: List[str],
        existing_topics: List[str]
    ) -> List[str]:
        """生成搜索查询词"""
        system = f"""你是一个{agent_role}的事实核查辩论Agent。

重要规则:
1. 必须用中文
2. 必须是问句形式,以"?"结尾
3. 问句要具体、可搜索

好的例子:
- "冥王星距离太阳最远是多少公里?"
- "欧盟什么时候开始禁售燃油车?"
- "有哪些官方数据显示冥王星的远日点距离?"

坏的例子(不要这样):
- "Pluto aphelion distance" (不是问句)
- "欧盟燃油车禁令" (不是问句)
- "查找数据" (太模糊)
"""

        prompt = f"""
待核查主张: {claim}

你的立场: {agent_role}
当前第{current_round}轮

请生成1个中文问句来搜索证据,必须以"?"结尾。

返回JSON格式:
{{
  "query": "你的中文问句?",
  "rationale": "为什么这样搜索"
}}

例如:
{{
  "query": "冥王星的远日点距离是多少?",
  "rationale": "直接搜索冥王星远日点的精确数据"
}}
"""

        messages = [{"role": "user", "content": prompt}]
        result = self.chat_with_json(messages, system)

        query = result.get("query", "")

        # 验证是否是中文问句
        if not query or not query.endswith("?") or not any('\u4e00' <= c <= '\u9fff' for c in query):
            print(f"[LLM警告] 生成的查询不符合要求: {query}")
            # 生成默认查询
            if "支持" in agent_role:
                query = f"{claim} 是真的吗?"
            else:
                query = f"{claim} 有什么证据反驳?"

        return [query] if query else []

    def construct_argument(
        self,
        claim: str,
        agent_role: str,
        evidence_list: List[Dict],
        opponent_args: List[Dict],
        round_num: int
    ) -> Dict:
        """构建论证"""
        system = f"""你是一个{agent_role}的事实核查辩论Agent。
你的任务是基于证据构建论证,支持你的立场。

返回JSON格式:
{{
  "argument": "论证内容",
  "key_evidence_indices": [0, 2],
  "priority": 0.85,
  "attacks_opponent": ["opponent_arg_id1", ...]
}}
"""

        prompt = f"""
待核查主张: {claim}

可用证据:
{chr(10).join(f"{i}. {e.get('content', '')[:200]}... (来源: {e.get('url', 'N/A')})" for i, e in enumerate(evidence_list))}

对手论点:
{chr(10).join(f"- ID:{arg.get('id')}: {arg.get('content', '')[:100]}" for arg in opponent_args)}

请构建你的论证。
"""

        messages = [{"role": "user", "content": prompt}]
        return self.chat_with_json(messages, system)

