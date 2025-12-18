# LangGraph版本说明

## 已添加LangGraph实现!

### 新文件

1. **`graph/langgraph_workflow.py`** (400+行)
   - 完整的LangGraph StateGraph实现
   - 定义了DebateState类型
   - 9个节点函数
   - 条件分支路由

2. **`main_langgraph.py`**
   - 使用LangGraph的主程序入口

### LangGraph工作流结构

```python
from langgraph.graph import StateGraph, END

# 节点
workflow.add_node("initialize_round", ...)
workflow.add_node("pro_query", ...)
workflow.add_node("con_query", ...)
workflow.add_node("search", ...)
workflow.add_node("pro_argue", ...)
workflow.add_node("con_argue", ...)
workflow.add_node("update_attacks", ...)
workflow.add_node("check_continue", ...)
workflow.add_node("judge", ...)

# 流程
workflow.set_entry_point("initialize_round")
workflow.add_edge("initialize_round", "pro_query")
workflow.add_edge("initialize_round", "con_query")
...

# 条件分支
workflow.add_conditional_edges(
    "check_continue",
    should_continue_routing,
    {
        "continue": "initialize_round",  # 循环
        "end": "judge"                   # 结束
    }
)
```

### 状态管理

```python
class DebateState(TypedDict):
    claim: str
    current_round: int
    max_rounds: int
    
    # 共享数据
    evidence_pool_data: dict
    arg_graph_data: dict
    
    # Agent输出(使用add operator累积)
    pro_queries: Annotated[list, add]
    con_queries: Annotated[list, add]
    pro_arguments: Annotated[list, add]
    con_arguments: Annotated[list, add]
    
    # 控制流
    should_continue: bool
    verdict: dict
```

### 使用方法

```bash
# 使用LangGraph版本
python main_langgraph.py --claim "你的主张" --rounds 3

# 或使用原版(更完整)
python main.py --claim "你的主张" --rounds 3
```

### 两个版本对比

| 特性 | main.py (原版) | main_langgraph.py (LangGraph) |
|------|----------------|-------------------------------|
| 框架 | 手写async控制流 | LangGraph StateGraph |
| 代码量 | 450行 | 400行(工作流) + 主程序 |
| 状态管理 | 手动传递对象 | LangGraph State |
| 可视化 | 需自行实现 | LangGraph内置 |
| 灵活性 | 高 | 中(受框架约束) |
| 学习曲线 | 低 | 中 |

### LangGraph核心优势

1. **声明式流程**: 清晰的节点+边定义
2. **自动状态管理**: State自动在节点间传递
3. **内置可视化**: 可以导出流程图
4. **条件分支**: 简洁的路由逻辑
5. **社区生态**: 与LangChain无缝集成

### 节点设计说明

每个节点函数:
- 输入: `DebateState`
- 输出: `dict` (更新state的部分字段)
- LangGraph自动合并返回的dict到state中

例如:
```python
def pro_query_node(state: DebateState) -> dict:
    # 从state获取信息
    claim = state["claim"]
    round_num = state["current_round"]
    
    # 执行逻辑
    queries = generate_queries(...)
    
    # 返回要更新的字段
    return {"pro_queries": queries}
```

### 依赖

```bash
pip install langgraph langchain langchain-anthropic
```

### 推荐

- **学习/演示**: 使用LangGraph版本(更清晰)
- **生产/论文**: 使用原版(更完整,测试更全)

两个版本功能相同,选择你喜欢的即可!
