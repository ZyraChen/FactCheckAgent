# 使用阿里云Qwen API

## 已改为使用阿里云Qwen!

系统已完全改为使用**阿里云通义千问(Qwen)**,不再需要Claude API。

## 快速开始

### 1. 获取API Key

访问: https://dashscope.console.aliyun.com/
- 登录阿里云账号
- 开通DashScope服务
- 创建API Key

### 2. 安装依赖

```bash
pip install openai pydantic aiohttp langgraph langchain
```

### 3. 设置API Key

**Windows:**
```cmd
set DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
set JINA_API_KEY=jina_xxxxxxxx
```

**Linux/Mac:**
```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxx"
export JINA_API_KEY="jina_xxxxxxxx"
```

或者直接编辑 `config.py`:
```python
DASHSCOPE_API_KEY = "sk-xxxxxxxxxxxxx"
JINA_API_KEY = "jina_xxxxxxxx"
```

### 4. 运行

```bash
# 测试LLM
python llm/qwen_client.py

# 运行系统(LangGraph版本)
python main_langgraph.py --claim "你的主张" --rounds 2
```

## 技术细节

### API兼容性

阿里云Qwen使用**OpenAI兼容接口**,所以代码中使用`openai`库:

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-dashscope-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="qwen-plus-latest",
    messages=[{"role": "user", "content": "你好"}]
)
```

### 可用模型

- `qwen-plus-latest` - 推荐(默认)
- `qwen-turbo-latest` - 更快
- `qwen-max-latest` - 最强

修改 `config.py` 中的 `LLM_MODEL` 切换模型。

### 代码改动说明

1. **llm/claude_client.py**
   - 从 `anthropic` 改为 `openai`
   - base_url 指向阿里云
   - 保持类名`ClaudeClient`(方便兼容)

2. **config.py**
   - `ANTHROPIC_API_KEY` → `DASHSCOPE_API_KEY`
   - `LLM_MODEL` → `qwen-plus-latest`

3. **所有文件中的环境变量**
   - 全部改为 `DASHSCOPE_API_KEY`

### 完整示例

```python
from llm.qwen_client import ClaudeClient

# 初始化(会自动使用Qwen)
client = ClaudeClient("your-dashscope-key")

# 对话
response = client.chat([
   {"role": "user", "content": "解释一下什么是论证推理"}
])
print(response)

# 生成JSON
result = client.chat_with_json([
   {"role": "user", "content": "生成3个搜索关键词,返回JSON"}
], system="你是一个搜索专家")
print(result)  # {"keywords": [...]}
```

## 测试

```bash
# 1. 测试LLM
python llm/qwen_client.py

# 2. 测试基础功能
python test_basic.py

# 3. 运行完整系统
python main_langgraph.py --claim "测试主张"
```

## 费用说明

阿里云Qwen计费:
- qwen-plus: ¥0.004/1K tokens
- qwen-turbo: ¥0.002/1K tokens
- qwen-max: ¥0.04/1K tokens

单次核查约消耗10K-20K tokens,成本约¥0.04-0.08

## 常见问题

### Q: 提示"没有权限"
A: 确认已在阿里云控制台开通DashScope服务

### Q: API调用超时
A: 设置更长的timeout或切换到qwen-turbo

### Q: 返回格式不对
A: Qwen的JSON格式可能不够稳定,可以在prompt中强调"只返回JSON,不要markdown"

### Q: 想用回Claude
A: 修改`llm/claude_client.py`,改回使用anthropic库即可

## 优势

✅ 国内访问快  
✅ 中文理解好  
✅ 价格便宜  
✅ 无需科学上网  
✅ API兼容OpenAI  

---

**现在你可以直接使用阿里云API运行系统了!**
