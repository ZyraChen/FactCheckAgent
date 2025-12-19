"""
Qwen LLM Wrapper - 将 QwenClient 包装为 LangChain compatible LLM
"""

from typing import Any, List, Optional, Dict
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun


class QwenLLMWrapper(LLM):
    """
    Qwen LLM Wrapper for LangChain

    将原有的 QwenClient 包装为 LangChain compatible LLM
    """
    qwen_client: Any  # QwenClient instance
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "qwen"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        调用 Qwen LLM

        Args:
            prompt: 输入 prompt
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数

        Returns:
            LLM 响应
        """
        # 将 prompt 转换为 messages 格式
        messages = [{"role": "user", "content": prompt}]

        # 调用 QwenClient
        try:
            response = self.qwen_client.chat(
                messages=messages,
                temperature=kwargs.get('temperature', self.temperature)
            )
            return response

        except Exception as e:
            return f"Error calling Qwen: {str(e)}"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """获取识别参数"""
        return {
            "model_name": "qwen",
            "temperature": self.temperature
        }
