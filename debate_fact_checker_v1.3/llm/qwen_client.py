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

