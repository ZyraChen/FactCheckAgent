# 双Agent论辩事实核查系统 - 重构版

## 重构说明

本次重构解决了以下问题：
1. ✅ 统一数据模型 - 移除重复的Evidence定义
2. ✅ 修复Judge逻辑 - 移除重复代码，改进判决策略
3. ✅ 简化架构 - 使用Evidence作为唯一节点类型
4. ✅ 优化攻击检测 - 更精准的矛盾识别
5. ✅ 清晰的工作流 - 简化序列化/反序列化

## 核心架构

### 1. 数据模型 (`utils/models.py`)

```python
Evidence         # 证据节点 (每个搜索结果)
├── id
├── content      # 内容
├── url          # 来源URL
├── credibility  # 可信度 (High/Medium/Low)
├── retrieved_by # 谁检索的 (pro/con)
├── quality_score# 质量分数 (0-1)
└── get_priority()  # 优先级 = credibility * quality_score

AttackEdge       # 攻击边
├── from_evidence_id
├── to_evidence_id
├── strength     # 攻击强度
└── rationale    # 攻击理由

Verdict          # 最终判决
├── decision     # Supported/Refuted/NEI
├── confidence   # 置信度 (0-1)
├── reasoning    # 推理过程
└── key_evidence_ids  # 关键证据ID列表
```

### 2. 核心模块

**EvidencePool (`core/evidence_pool.py`)**
- 存储所有证据
- 支持按agent/轮次/可信度筛选
- 提供统计信息

**ArgumentationGraph (`core/argumentation_graph.py`)**
- 证据节点 + 攻击边
- 计算Grounded Extension (可接受的证据集合)
- 验证攻击规则 (高优先级→低优先级)

### 3. Agent

**ProAgent (`agents/pro_agent.py`)**
- 生成搜索查询 (支持claim)
- 第1轮: 2个查询
- 后续轮: 1个查询 (根据反方证据调整)

**ConAgent (`agents/con_agent.py`)**
- 生成搜索查询 (反驳claim)
- 第1轮: 2个查询
- 后续轮: 1个查询 (根据正方证据调整)

**JudgeAgent (`agents/judge_agent.py`)**
- 计算Grounded Extension
- 分析双方强度
- 做出判决 (Supported/Refuted/NEI)
- 生成解释

### 4. 工具

**AttackDetector (`tools/attack_detector.py`)**
- 使用LLM检测证据矛盾
- 只添加高优先级→低优先级的攻击
- 降级策略: 基于可信度比较

**JinaSearch (`tools/jina_search.py`)**
- 调用Jina Search API
- 返回搜索结果

## 工作流程

```
1. 初始化
   ├── 创建 LLM、JinaSearch
   ├── 创建 EvidencePool、ArgumentationGraph
   └── 创建 ProAgent、ConAgent、JudgeAgent

2. 多轮辩论 (默认3轮)
   For each round:
   ├── 2.1 Pro和Con生成查询
   │   ├── ProAgent.generate_search_queries()
   │   └── ConAgent.generate_search_queries()
   │
   ├── 2.2 搜索并创建证据
   │   ├── JinaSearch.search(query)
   │   ├── 评估可信度 (基于URL)
   │   ├── 评估质量分数
   │   ├── 创建Evidence对象
   │   ├── 添加到EvidencePool
   │   └── 添加到ArgumentationGraph
   │
   └── 2.3 检测攻击关系
       ├── AttackDetector.detect_attacks_for_round()
       └── ArgumentationGraph.add_attacks()

3. Judge判决
   ├── ArgumentationGraph.compute_grounded_extension()
   ├── 分析Pro/Con被接受的证据
   ├── 计算双方强度
   ├── 做出判决 (Supported/Refuted/NEI)
   └── 生成推理解释
```

## 使用方法

### 方法1: 使用简化工作流 (推荐)

```bash
# 单个claim测试
python main_simple.py --claim "欧盟计划在2030年全面禁止销售燃油车。" --rounds 3

# 批量处理数据集
python main_simple.py --dataset data/dataset_part_1.json --max-samples 5 --output output/results.json
```

### 方法2: 直接调用

```python
from simple_workflow import run_debate_workflow

claim = "程立目前是蚂蚁集团的董事。"
result = run_debate_workflow(claim, max_rounds=3)

print(f"判决: {result['verdict']['decision']}")
print(f"置信度: {result['verdict']['confidence']}")
print(f"推理: {result['verdict']['reasoning']}")
```

## 判决逻辑

Judge的判决基于以下规则：

1. **一方没有被接受的证据** → 另一方胜出
   - 无Pro证据 → Refuted (0.6-0.9)
   - 无Con证据 → Supported (0.6-0.9)

2. **双方强度差距明显** (>0.15) → 强者胜出
   - Pro更强 → Supported (0.6-0.9)
   - Con更强 → Refuted (0.6-0.9)

3. **势均力敌** → 比较最高优先级证据
   - Pro最高证据更好 → Supported (0.6)
   - Con最高证据更好 → Refuted (0.6)

4. **无法判断** → 比较数量
   - Pro数量多2个以上 → Supported (0.55)
   - Con数量多2个以上 → Refuted (0.55)
   - 其他 → NEI (0.5)

## 输出文件

运行后会在`output/`目录生成：

```
output/
├── argumentation_graph.json   # 论辩图 (证据节点+攻击边)
├── verdict.json                # 判决结果
└── results.json                # 批量测试结果
```

## 关键改进点

### 1. 数据模型统一
- 只使用`utils/models.py`中的Evidence
- 移除`core/evidence_pool.py`中重复的定义
- 统一使用Pydantic模型

### 2. Judge逻辑修复
- 移除`judge_agent.py`中的重复代码
- 改进判决策略 - 降低NEI阈值
- 即使双方都有被接受的证据也能判决

### 3. 攻击检测优化
- 使用LLM判断证据矛盾
- 优先级差>5%才允许攻击
- 降级策略: 基于可信度

### 4. 工作流简化
- 不依赖LangGraph的复杂序列化
- 直接编排Pro/Con/Judge交互
- 清晰的单向数据流

## 配置

编辑`config.py`：

```python
JINA_API_KEY = "your_jina_api_key"
DASHSCOPE_API_KEY = "your_qwen_api_key"
```

## 测试

```bash
# 快速测试
python main_simple.py

# 运行2轮
python main_simple.py --rounds 2

# 测试数据集前3条
python main_simple.py --dataset data/dataset_part_1.json --max-samples 3
```

## 常见问题

**Q: 为什么不使用LangGraph?**
A: LangGraph的序列化/反序列化过于复杂，简化工作流更清晰。

**Q: 如何调整判决严格程度?**
A: 修改`JudgeAgent._make_decision()`中的阈值，如`strength_diff > 0.15`。

**Q: 如何增加更多轮次?**
A: 使用`--rounds N`参数，建议2-3轮即可。

**Q: 为什么有些claim判决为NEI?**
A: 可能是：
1. 搜索结果质量低
2. 双方证据势均力敌
3. 攻击关系不够明确

可以通过查看`argumentation_graph.json`分析原因。

## 下一步优化建议

1. **证据质量评估** - 使用LLM评估相关性
2. **攻击强度** - 考虑论证深度和反驳力度
3. **可视化** - 生成论辩图可视化
4. **缓存** - 缓存搜索结果避免重复调用
5. **并行搜索** - 使用异步提高速度
