"""
配置文件
"""

import os
from pathlib import Path

# API Keys
DASHSCOPE_API_KEY = "sk-8faa7214041347609e67d5d09cec7266"
ANTHROPIC_API_KEY = "sk-8faa7214041347609e67d5d09cec7266"
JINA_API_KEY = "jina_518b9cb292b249139bedce5123349109HnqXMjmaY94laLNX3J50eXfmd9E5"

# 模型配置
LLM_MODEL = "qwen-plus-2025-12-01"  # 阿里云Qwen模型
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 4000

# 搜索配置
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_SEARCH_QUERIES_PER_AGENT = 5

# 辩论配置
MAX_DEBATE_ROUNDS = 3
EVIDENCE_POOL_MAX_SIZE = 100

# 优先级阈值
PRIORITY_THRESHOLD = 0.05  # 优先级差异小于此值视为相等

# 目录配置
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"

# 创建目录
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# 日志配置
LOG_LEVEL = "INFO"
