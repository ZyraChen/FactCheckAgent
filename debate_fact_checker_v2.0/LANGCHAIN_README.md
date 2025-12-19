# LangChain 多Agent 辩论式事实核查系统

## 🎯 概述

这是 `debate_fact_checker_v2.0` 的 **LangChain 版本改写**，将原有的简单函数式编排改为使用 **LangChain 多Agent框架**。

### 核心改进

✅ **使用 LangChain Agent 框架**
- Pro Agent, Con Agent, Judge Agent 都是 LangChain Agents
- 具有推理能力 (ReAct pattern)
- 可以自主调用工具

✅ **工具化 (Tools)**
- SearchTool: 封装 Jina Search API
- EvidencePoolTool: 查询证据池
- ArgumentGraphTool: 查询论辩图

✅ **保留核心逻辑**
- 证据池 (EvidencePool)
- 论辩图 (ArgumentationGraph)
- 攻击检测 (AttackDetector)
- Grounded Semantics

---

## 📁 项目结构

```
debate_fact_checker_v2.0/
├── langchain_version/           # LangChain 版本 (新增)
│   ├── agents/                  # LangChain Agents
│   │   ├── pro_agent_lc.py     # Pro Agent
│   │   ├── con_agent_lc.py     # Con Agent
│   │   └── judge_agent_lc.py   # Judge Agent
│   ├── tools/                   # LangChain Tools
│   │   ├── search_tool.py      # 搜索工具
│   │   ├── evidence_pool_tool.py
│   │   └── argument_graph_tool.py
│   ├── orchestrator/            # 多Agent编排器
│   │   └── debate_orchestrator.py
│   └── utils/                   # 工具类
│       └── qwen_wrapper.py     # Qwen LLM Wrapper
│
├── core/                        # 核心模块 (保留)
│   ├── evidence_pool.py
│   └── argumentation_graph.py
├── tools/                       # 原有工具 (保留)
│   ├── jina_search.py
│   └── attack_detector.py
├── utils/models.py              # 数据模型 (保留)
│
├── main_langchain.py            # LangChain版本入口 (新)
├── main_simple.py               # 原版本入口 (保留)
└── LANGCHAIN_README.md          # 本文档
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install langchain langchain-openai  # 安装 LangChain
```

### 2. 配置 API Keys

在 `config.py` 中配置:
```python
DASHSCOPE_API_KEY = "your-qwen-api-key"
JINA_API_KEY = "your-jina-api-key"
```

### 3. 运行单个Claim

```bash
python main_langchain.py --claim "欧盟计划在2030年全面禁止销售燃油车。" --rounds 2
```

### 4. 批量处理数据集

```bash
python main_langchain.py --dataset data/dataset_part_1.json --max-samples 5
```

---

## 🏗️ 架构说明

### 原版 vs LangChain 版本

| 组件 | 原版 (simple_workflow.py) | LangChain 版本 |
|------|---------------------------|----------------|
| **Pro Agent** | 简单函数 `generate_search_queries()` | LangChain Agent + Tools |
| **Con Agent** | 简单函数 `generate_search_queries()` | LangChain Agent + Tools |
| **Judge Agent** | 简单函数 `make_verdict()` | LangChain Agent + Tools |
| **编排** | 循环调用 | DebateOrchestrator |
| **工具** | 直接调用 | LangChain Tools (search_evidence, query_evidence_pool, etc.) |
| **推理** | 单次 LLM 调用 | ReAct (Reason + Act) 循环 |

### LangChain 多Agent 工作流

```
┌─────────────────────────────────────────────────────────────┐
│                    DebateOrchestrator                        │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Pro Agent   │    │  Con Agent   │    │ Judge Agent  │  │
│  │  (LangChain) │    │  (LangChain) │    │ (LangChain)  │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                    │                    │          │
│         ├─ SearchTool       ├─ SearchTool        ├─ ArgumentGraphTool
│         ├─ EvidencePoolTool ├─ EvidencePoolTool  └─ EvidencePoolTool
│         │                    │                                │
│         └────────────────────┴────────────────────────────────┘
│                              │                                 │
│                    ┌─────────▼─────────┐                      │
│                    │  Shared State     │                      │
│                    │  - EvidencePool   │                      │
│                    │  - ArgumentGraph  │                      │
│                    └───────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### LangChain Agent 推理流程 (ReAct)

```
Pro Agent 示例:

Thought: 我需要查看对方的证据来制定搜索策略
Action: query_evidence_pool
Action Input: {"query_type": "by_agent", "agent_type": "con"}
Observation: Con 检索的证据 (2个): ...

Thought: 对方说欧盟没有全面禁止燃油车，我需要找更权威的证据
Action: search_evidence
Action Input: {"query": "欧盟2030禁售燃油车官方政策", "agent_type": "pro", "round_num": 2}
Observation: 搜索成功！添加了 2 个证据...

Thought: 我现在知道最终答案了
Final Answer: 已完成搜索，添加了支持claim的权威证据
```

---

## 🛠️ LangChain Tools 说明

### 1. SearchTool (search_evidence)

**功能**: 使用 Jina Search API 搜索证据并自动添加到证据池

**输入参数**:
- `query` (str): 搜索查询词
- `agent_type` (str): "pro" 或 "con"
- `round_num` (int): 当前轮次

**示例**:
```python
{
  "query": "欧盟2030燃油车禁令官方文件",
  "agent_type": "pro",
  "round_num": 1
}
```

### 2. EvidencePoolTool (query_evidence_pool)

**功能**: 查询证据池中的证据

**输入参数**:
- `query_type` (str): "all", "by_agent", "by_round", "stats"
- `agent_type` (str, 可选): "pro" 或 "con"
- `round_num` (int, 可选): 轮次编号

**示例**:
```python
# 查看对方证据
{"query_type": "by_agent", "agent_type": "con"}

# 查看统计信息
{"query_type": "stats"}
```

### 3. ArgumentGraphTool (query_argument_graph)

**功能**: 查询论辩图信息

**输入参数**:
- `query_type` (str): "stats", "attacks", "accepted", "node_info"
- `node_id` (str, 可选): 节点ID

**示例**:
```python
# 查看被接受的证据 (Grounded Extension)
{"query_type": "accepted"}

# 查看攻击关系
{"query_type": "attacks"}
```

---

## 📊 输出文件

运行后会在 `output/` 目录生成:

1. **argumentation_graph_langchain.json** - 论辩图 (所有证据节点和攻击边)
2. **verdict_langchain.json** - 判决结果

判决结果格式:
```json
{
  "decision": "Supported/Refuted/NEI",
  "confidence": 0.85,
  "reasoning": "详细的推理过程...",
  "key_evidence_ids": ["pro_1_abc123", "con_2_def456"],
  "accepted_evidence_ids": [...],
  "pro_strength": 0.8,
  "con_strength": 0.3,
  "total_evidences": 12,
  "accepted_evidences": 8
}
```

---

## 🔬 核心技术

### 1. LangChain Agent (ReAct Pattern)

使用 `create_react_agent` 创建具有推理能力的 Agents:
- **Reason**: Agent 思考下一步该做什么
- **Act**: Agent 调用工具执行操作
- **Observe**: Agent 观察工具返回结果
- 循环执行直到得出结论

### 2. 保留的核心算法

以下核心算法从原版保留，未使用 LangChain:

- **Grounded Semantics**: 计算可接受论证集合
- **Attack Detection**: 检测论证间的攻击关系
- **Priority Calculation**: 基于可信度和质量计算优先级

### 3. 共享状态管理

`DebateOrchestrator` 维护共享状态:
- `EvidencePool`: 所有证据
- `ArgumentationGraph`: 论辩图 (节点+边)

所有 Agents 通过 Tools 访问这些共享状态。

---

## 🆚 对比测试

### 运行原版

```bash
python main_simple.py --claim "测试claim" --rounds 2
```

### 运行 LangChain 版本

```bash
python main_langchain.py --claim "测试claim" --rounds 2
```

### 预期差异

| 方面 | 原版 | LangChain 版本 |
|------|------|---------------|
| **搜索策略** | 单次 LLM 生成查询 | ReAct 推理，可能多次尝试 |
| **运行时间** | 更快 | 稍慢 (因为有推理循环) |
| **可解释性** | 较弱 | 更强 (可看到 Agent 思考过程) |
| **灵活性** | 固定流程 | Agent 可自主决策 |

---

## 📝 开发笔记

### 为什么使用 LangChain?

1. **模块化**: Tools 可复用
2. **推理能力**: ReAct pattern 让 Agent 更智能
3. **可扩展**: 容易添加新工具和 Agent
4. **可观察**: 内置 logging 和 callback

### 局限性

1. **需要更多 LLM 调用**: 因为 ReAct 推理循环
2. **解析错误**: Agent 可能生成错误格式的工具调用
3. **依赖 LangChain**: 增加了外部依赖

---

## 🐛 故障排除

### 问题: Agent 不调用工具

**原因**: Prompt 可能不够清晰

**解决**: 修改 `*_agent_lc.py` 中的 System Prompt，使指令更明确

### 问题: 解析错误

**原因**: Agent 输出格式不符合预期

**解决**: 在 `AgentExecutor` 中设置 `handle_parsing_errors=True`

### 问题: Qwen LLM 不兼容

**原因**: QwenClient 接口与 LangChain 不完全兼容

**解决**: 使用 `QwenLLMWrapper` 包装器 (已实现)

---

## 📚 参考资料

- [LangChain Agent Documentation](https://python.langchain.com/docs/modules/agents/)
- [ReAct Pattern](https://react-lm.github.io/)
- [原版框架文档](README.md)

---

## ✅ 总结

这个 LangChain 版本保留了原版的**核心算法**和**数据结构**，但用 **LangChain 多Agent框架**替代了简单的函数式编排。

**适用场景**:
- ✅ 需要更强的推理能力
- ✅ 需要 Agent 自主决策
- ✅ 需要更好的可解释性
- ❌ 追求极致性能 (建议用原版)
- ❌ 环境限制无法安装 LangChain

**下一步**:
1. 运行测试对比两个版本的性能
2. 根据需求选择合适的版本
3. 扩展: 可添加更多 Tools (如 Wikipedia Tool, Calculator Tool 等)
