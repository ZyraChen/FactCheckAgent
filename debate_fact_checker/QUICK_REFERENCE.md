# 🚀 快速参考卡

## 立即运行(3个命令)

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置(在config.py中设置或使用环境变量)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export JINA_API_KEY="jina_xxxxx"

# 3. 运行
python main.py --claim "冥王星距太阳最远约为74亿公里。"
```

## 核心命令

| 命令 | 用途 |
|------|------|
| `python test_basic.py` | 运行测试 |
| `python main.py --claim "xxx"` | 核查单个claim |
| `python main.py --dataset data/xxx.json --max-samples 10` | 批量处理 |
| `python EXAMPLES.py` | 查看使用示例 |

## 核心文件(必看)

| 文件 | 说明 |
|------|------|
| `main.py` | 主程序入口(450行) |
| `utils/models.py` | 数据模型定义 |
| `core/argumentation_graph.py` | 论辩图核心 |
| `agents/judge_agent.py` | 判决逻辑 |
| `reasoning/semantics.py` | 形式化推理 |

## 关键概念(5个)

1. **ArgumentNode**: 论证节点,包含内容+证据+优先级
2. **AttackEdge**: 攻击边,仅高优先级→低优先级
3. **EvidencePool**: 双方共享的证据池
4. **Grounded Extension**: 可接受的论证集合
5. **Verdict**: 判决(Supported/Refuted/NEI)

## 工作流程(一图流)

```
Claim → [3轮辩论] → 论辩图 → Judge → Verdict
         ↓
   每轮: Pro搜索→构建论证
         Con搜索→构建论证→攻击更新
```

## 输出文件

- `output/verdict.json` - 判决结果
- `output/argumentation_graph.json` - 论辩图
- `output/results.json` - 批量结果

## 配置项(config.py)

```python
MAX_DEBATE_ROUNDS = 3                    # 辩论轮次
MAX_SEARCH_QUERIES_PER_AGENT = 5        # 每轮搜索数
LLM_MODEL = "claude-sonnet-4-20250514"  # Claude模型
LLM_TEMPERATURE = 0.7                    # 温度
```

## 常用API

### Python API
```python
import asyncio
from main import run_debate_system

verdict = asyncio.run(run_debate_system("your claim"))
print(verdict.decision, verdict.confidence)
```

### 自定义Agent

```python
from agents.pro_agent import ProAgent
from llm.qwen_client import ClaudeClient

llm = ClaudeClient("api-key")
agent = ProAgent("claim", llm)
queries = agent.generate_search_queries(1, graph, pool)
```

### 读取结果
```python
import json

with open("output/verdict.json") as f:
    verdict = json.load(f)
    print(f"判决: {verdict['decision']}")
    print(f"置信度: {verdict['confidence']}")
```

## 故障排除

| 问题 | 解决 |
|------|------|
| 找不到模块 | `pip install pydantic anthropic aiohttp` |
| API调用失败 | 检查config.py中的API keys |
| 搜索无结果 | 检查Jina API key和网络 |
| 判决总是NEI | 增加轮次:`--rounds 5` |

## 性能建议

- 单个claim: 约1-2分钟(3轮)
- 批量处理: 约5-10分钟(10条)
- 可并行处理多个claim
- 使用`--max-samples`限制数量

## 目录结构(简化)

```
debate_fact_checker/
├── main.py              ⭐ 主程序
├── config.py            ⚙️ 配置
├── test_basic.py        ✅ 测试
├── agents/              🤖 三个Agent
├── core/                📊 论辩图+证据池
├── tools/               🔧 工具函数
├── reasoning/           🧠 推理引擎
├── llm/                 💬 Claude API
└── data/                📁 数据集
```

## 扩展点

1. 新语义: 修改`reasoning/semantics.py`
2. 新Agent: 继承`BaseAgent`
3. 新搜索: 替换`jina_search.py`
4. 可视化: 读取JSON渲染

## 测试覆盖

✅ 数据模型  
✅ 论辩图  
✅ 证据池  
✅ 优先级计算  
✅ 形式化语义  

## 支持的数据集格式

```json
{
  "claim": "待核查主张",
  "verdict": "Supported/Refuted/NEI",
  "evidence_sources": [...],
  "justification": "..."
}
```

## 核心依赖

- anthropic >= 0.40.0
- pydantic >= 2.0.0
- aiohttp >= 3.9.0

## 项目统计

- **代码行数**: ~3000行
- **Python文件**: 27个
- **测试通过**: ✅
- **文档页数**: 5个MD文件

## 快速调试

```bash
# 查看详细输出
python main.py --claim "xxx" 2>&1 | tee debug.log

# 测试单个模块
python -c "from reasoning.semantics import compute_grounded_extension; print('OK')"
```

## 文档索引

- 📖 README.md - 项目说明
- 🎯 USAGE_GUIDE.md - 使用指南(最详细)
- 🏗️ ARCHITECTURE.md - 系统架构
- 📊 PROJECT_OVERVIEW.md - 项目概览
- 💡 EXAMPLES.py - 代码示例

## 一行命令测试

```bash
# 完整流程测试
python test_basic.py && python main.py --claim "测试claim" --rounds 1
```

---

**提示**: 首次运行建议先执行`test_basic.py`确认环境OK!
