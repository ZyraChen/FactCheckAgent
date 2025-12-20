# 🎯 双Agent辩论式事实核查系统 - 完整使用指南

## 📦 已交付内容

### ✅ 完整系统代码(27个Python文件)
1. **核心模块**: 论辩图、证据池、数据模型
2. **Agent实现**: Pro Agent、Con Agent、Judge Agent
3. **工具模块**: Jina Search、优先级计算、攻击检测
4. **推理引擎**: Grounded Semantics形式化语义
5. **LLM接口**: Claude API封装
6. **主程序**: 完整的运行流程
7. **测试代码**: 基础功能测试(全部通过✓)

### 📁 项目结构

```
debate_fact_checker/
├── agents/           # 三个Agent(Pro/Con/Judge)
├── core/             # 论辩图+证据池
├── tools/            # Jina搜索+攻击检测
├── reasoning/        # 形式化语义计算
├── llm/              # Qwen API
├── utils/            # 数据模型
├── data/             # 数据集(已包含dataset_part_1.json)
├── main.py           # 主程序⭐
├── config.py         # 配置文件
├── test_basic.py     # 测试(已通过✓)
├── README.md         # 说明文档
├── PROJECT_OVERVIEW.md  # 项目概览
└── EXAMPLES.py       # 使用示例
```

## 🚀 快速开始(5步)

### 第1步: 安装依赖
```bash
cd debate_fact_checker_v2.0
pip install -r requirements.txt
```

### 第2步: 配置API Keys
编辑 `config.py` 或设置环境变量:
```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export JINA_API_KEY="jina_xxxxx"
```

### 第3步: 运行测试(确认环境)
```bash
python test_basic.py
```
应该看到:
```
✓ 数据模型测试通过
✓ 论辩图测试通过
✓ 证据池测试通过
✓ 优先级计算测试通过
✓ 形式化语义测试通过
✓ 所有测试通过!
```

### 第4步: 运行单个例子
```bash
python main.py --claim "冥王星距太阳最远约为74亿公里。" --rounds 3
```

### 第5步: 批量处理数据集
```bash
python main.py --dataset data/dataset_part_1.json --output output/results.json --max-samples 5
```

## 🔧 系统工作原理

### 完整流程

```
输入: "欧盟计划在2030年全面禁止销售燃油车"
    ↓
[第1轮]
├─ Pro生成查询: ["欧盟燃油车禁令", "2030禁售政策"]
├─ Con生成查询: ["欧盟2035政策", "燃油车禁售时间"]
├─ 并行搜索Jina → 获得10-15条证据
├─ Pro构建论证节点1个(优先级0.75)
├─ Con构建论证节点1个(优先级0.90)
└─ 更新攻击边: Con节点→Pro节点(因为0.90>0.75)
    ↓
[第2-3轮] 重复上述过程,论辩图逐渐完善
    ↓
[Judge判决]
├─ 计算Grounded Extension: {con_arg_1, con_arg_2}
├─ Pro强度: 0.45, Con强度: 0.82
└─ 判决: Refuted(反驳), 置信度: 0.85
    ↓
输出: verdict.json + argumentation_graph.json
```

### 关键机制

1. **优先级规则**: 
   - High credibility → 1.0
   - Medium → 0.6
   - Low → 0.3
   - 仅高优先级可以攻击低优先级

2. **Grounded Extension**:
   - 找出没有被攻击OR所有攻击者都被击败的论证
   - 这些论证被Judge认为"可接受"

3. **双方强度计算**:
   ```
   强度 = 平均优先级 × 接受率
   例: Con有3个节点,2个被接受,平均优先级0.85
       强度 = 0.85 × (2/3) = 0.57
   ```

## 📊 输出文件详解

### 1. argumentation_graph.json
完整的论辩图,包含:
- 所有论证节点(Pro和Con)
- 所有攻击边
- 统计信息

```json
{
  "claim": "xxx",
  "nodes": [
    {
      "id": "pro_arg_1_a3f2",
      "agent": "pro",
      "content": "根据XX证据,该主张成立",
      "priority": 0.75,
      "evidence_ids": ["e1", "e2"]
    }
  ],
  "edges": [
    {
      "from_node_id": "con_arg_1_b4e1",
      "to_node_id": "pro_arg_1_a3f2",
      "strength": 0.15
    }
  ]
}
```

### 2. verdict.json
最终判决结果:
```json
{
  "decision": "Refuted",
  "confidence": 0.85,
  "reasoning": "详细推理过程(200-300字)...",
  "key_evidence": ["证据ID列表"],
  "argument_analysis": {
    "pro_strength": 0.45,
    "con_strength": 0.82
  }
}
```

### 3. results.json (批量模式)
```json
[
  {
    "claim": "xxx",
    "predicted_verdict": "Refuted",
    "ground_truth": "Refuted",
    "correct": true,
    "confidence": 0.85
  }
]
```

## ⚙️ 高级配置

### 修改辩论参数
编辑 `config.py`:
```python
MAX_DEBATE_ROUNDS = 3           # 改为5轮
MAX_SEARCH_QUERIES_PER_AGENT = 5  # 每轮搜索词数
LLM_TEMPERATURE = 0.7            # Claude温度
```

### 使用简化版攻击检测
在 `main.py` 中:
```python
from tools.attack_detector import detect_attacks_simple

# 简化版(不调用LLM,基于规则)
new_attacks = detect_attacks_simple(arg_graph, round_num)
```

### 自定义Agent行为
```python
from agents.pro_agent import ProAgent

class CustomProAgent(ProAgent):
    def generate_search_queries(self, ...):
        # 自定义搜索策略
        queries = ["我的自定义查询1", "查询2"]
        return [SearchQuery(query=q, agent="pro", ...) for q in queries]
```

## 🐛 常见问题

### Q1: 测试失败 - "No module named 'pydantic'"
```bash
pip install pydantic anthropic aiohttp --break-system-packages
```

### Q2: Jina Search返回空结果
- 检查API Key是否正确
- 检查网络连接
- 查看 `tools/jina_search.py` 的响应解析逻辑

### Q3: Claude API调用失败
- 检查ANTHROPIC_API_KEY
- 检查模型名称: `claude-sonnet-4-20250514`
- 查看错误信息: `llm/claude_client.py`

### Q4: 判决总是NEI(证据不足)
- 增加搜索轮次: `--rounds 5`
- 增加每轮搜索词数: 修改`config.py`
- 检查Jina搜索是否正常

### Q5: 如何可视化论辩图?
可以使用NetworkX+Matplotlib:
```python
import networkx as nx
import matplotlib.pyplot as plt
import json

with open("output/argumentation_graph.json") as f:
    data = json.load(f)

G = nx.DiGraph()
for node in data["nodes"]:
    G.add_node(node["id"], agent=node["agent"])
for edge in data["edges"]:
    G.add_edge(edge["from_node_id"], edge["to_node_id"])

nx.draw(G, with_labels=True)
plt.show()
```

## 📈 性能优化建议

1. **并行处理多个claim**: 使用`asyncio.gather()`
2. **缓存搜索结果**: 避免重复搜索相同query
3. **减少LLM调用**: 使用简化版攻击检测
4. **批量API调用**: Anthropic支持batch API

## 🔬 研究扩展方向

1. **更复杂的语义**: Preferred/Stable Semantics
2. **动态优先级**: 基于辩论过程调整优先级
3. **多轮反思**: Agent在每轮后反思并调整策略
4. **可视化界面**: Web UI展示辩论过程
5. **多语言支持**: 扩展到中文以外的语言

## 📚 相关资源

- **Argumentation Theory**: Dung (1995) - On the acceptability of arguments
- **Fact-checking**: Augenstein et al. (2024) - Factuality challenges
- **LLM+论证**: 你的论文!

## 🤝 如何贡献

1. Fork项目
2. 创建功能分支: `git checkout -b feature/xxx`
3. 提交更改: `git commit -am 'Add xxx'`
4. 推送分支: `git push origin feature/xxx`
5. 提交Pull Request

## 📞 联系方式

如有问题,请通过以下方式联系:
- 项目Issues
- Email: [你的邮箱]

---

## ✨ 特别说明

这个系统完全实现了你论文中的核心思想:
- ✅ 双Agent辩论式证据收集
- ✅ 论辩图动态构建
- ✅ 优先级约束的攻击关系
- ✅ Grounded Semantics推理
- ✅ 可解释的判决生成

所有核心模块都已实现并测试通过!可以直接运行。

**Good luck with your research! 🚀**
